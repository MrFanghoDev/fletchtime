"""In-process state shared by every websocket connection: owns the
(optional) running :class:`MatchEngine`, ticks it on a timer, and
broadcasts its state to every connected client (control page and every
display page).

Deliberately dependency-free beyond the engine + stdlib json/asyncio, so
this stays easy to reason about on a phone.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, replace
from typing import Dict, Optional, Set

from fletchtime_engine import (
    FlintMode,
    IndoorMode,
    MatchEngine,
    MatchState,
)

from . import config_store

TICK_INTERVAL = 0.2  # seconds between engine ticks / broadcasts


def _state_to_dict(state: MatchState) -> dict:
    data = asdict(state)
    data["phase"] = state.phase.value  # Enum -> plain string for JSON
    return data


class MatchServer:
    def __init__(self) -> None:
        self.engine: Optional[MatchEngine] = None
        self.clients: Set = set()
        self._lock = asyncio.Lock()
        # Message global (toutes les lanes) -- indépendant de l'engine sur
        # le principe : un message ("Retard de 15 minutes...") doit rester
        # affichable même avant un match, entre deux matchs, ou après la fin.
        self._message: Optional[str] = None
        # Messages ciblés sur une seule lane -- prennent le pas sur le
        # message global pour cette lane précise si les deux sont définis.
        self._lane_messages: Dict[str, str] = {}
        # Langue de diffusion pour les écrans -- choisie par le DOS, envoyée
        # à tous les clients (control + display) pour que les libellés
        # statiques (phase, série/volée, etc.) s'affichent dans la bonne langue.
        self._language: str = "fr"
        # Titre de l'événement (ex. "Concours FFTL Indoor -- Février 2026"),
        # choisi par le DOS, affiché en permanence sur les écrans -- persiste
        # à travers les matchs, contrairement au message ponctuel.
        self._event_title: Optional[str] = None
        # Lane déclarée par chaque écran d'affichage à la connexion (voir
        # action "register_display") -- absent pour les postes de contrôle,
        # qui ne s'enregistrent jamais comme lane.
        self._display_lanes: Dict[object, str] = {}
        # Mode ("indoor"/"flint") du match actuellement chargé dans
        # self.engine, quel que soit son état (actif, pause, urgence) --
        # sert uniquement à bloquer la modification de la config de ce mode
        # tant qu'un match de ce type est en cours (voir _handle_config_action).
        self._current_mode_kind: Optional[str] = None
        # Pack de sons actif, diffusé à tous les écrans (ex. "classic") --
        # chargé une fois au démarrage, mis à jour via save_config("app", ...).
        self._sound_pack: str = config_store.load_app_config()["sound_pack"]

    # -- connection lifecycle ---------------------------------------------

    async def register(self, websocket) -> None:
        self.clients.add(websocket)
        await self._send_state_to(websocket)

    async def unregister(self, websocket) -> None:
        self.clients.discard(websocket)
        self._display_lanes.pop(websocket, None)

    # -- commands from /control ---------------------------------------------

    async def handle_command(self, raw_message: str, websocket=None) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        action = data.get("action")

        if action in ("get_config", "save_config"):
            await self._handle_config_action(action, data, websocket)
            return

        async with self._lock:
            if action == "start_indoor":
                try:
                    base = config_store.load_indoor_config()
                    overrides = {}
                    if "turn_mode" in data:
                        overrides["turn_mode"] = data["turn_mode"]
                    if "alternate" in data:
                        overrides["alternate_relay_order_each_series"] = bool(data["alternate"])
                    cfg = replace(base, **overrides) if overrides else base
                    self.engine = MatchEngine(IndoorMode(cfg))
                    self._current_mode_kind = "indoor"
                except ValueError:
                    pass  # invalid turn_mode from a malformed command -- ignore
            elif action == "start_flint":
                try:
                    base = config_store.load_flint_config()
                    overrides = {}
                    if "turn_mode" in data:
                        overrides["turn_mode"] = data["turn_mode"]
                    if "alternate" in data:
                        overrides["alternate_relay_order_each_unit"] = bool(data["alternate"])
                    cfg = replace(base, **overrides) if overrides else base
                    self.engine = MatchEngine(FlintMode(cfg))
                    self._current_mode_kind = "flint"
                except ValueError:
                    pass  # invalid turn_mode from a malformed command -- ignore
            elif action == "register_display":
                lane = str(data.get("lane", "")).strip()
                if lane and websocket is not None:
                    self._display_lanes[websocket] = lane
            elif action == "message":
                lane = str(data.get("lane") or "").strip()
                value = data.get("value") or None
                if lane:
                    if value is None:
                        self._lane_messages.pop(lane, None)
                    else:
                        self._lane_messages[lane] = value
                else:
                    self._message = value
                    # Un message "à tous" doit remplacer tout message ciblé
                    # existant -- sinon une lane restée sur un message ciblé
                    # ne verrait jamais le nouveau message global.
                    self._lane_messages.clear()
            elif action == "set_language":
                lang = data.get("value")
                if lang in ("fr", "en"):
                    self._language = lang
            elif action == "set_event_title":
                self._event_title = data.get("value") or None
            elif self.engine is not None:
                try:
                    if action == "next":
                        self.engine.next()
                    elif action == "stop":
                        self.engine.stop()
                    elif action == "restart":
                        self.engine.restart()
                    elif action == "goto":
                        self.engine.goto(
                            unit_number=int(data.get("unit", 1)),
                            end_number=int(data.get("end", 1)),
                            arrow_in_end=int(data.get("arrow", 0)),
                            turn=data.get("turn", ""),
                        )
                    elif action == "emergency":
                        self.engine.emergency()
                    elif action == "resume":
                        self.engine.resume()
                    elif action == "pause":
                        self.engine.pause()
                    elif action == "play":
                        self.engine.play()
                except ValueError:
                    pass  # e.g. goto target that doesn't exist -- ignore silently

        await self.broadcast_state()

    # -- config get/save (no match-state broadcast involved) -----------------

    async def _handle_config_action(self, action: str, data: dict, websocket) -> None:
        """Handles get_config/save_config directly, without going through
        the usual broadcast_state() at the end of handle_command -- these
        don't change any match state, and broadcasting would overwrite the
        direct reply we just sent to the requesting client."""
        async with self._lock:
            if action == "get_config":
                if websocket is not None:
                    try:
                        await websocket.send(json.dumps({
                            "type": "config",
                            "indoor": asdict(config_store.load_indoor_config()),
                            "flint": asdict(config_store.load_flint_config()),
                            "app": config_store.load_app_config(),
                        }))
                    except Exception:
                        pass
            elif action == "save_config":
                mode = data.get("mode")
                values = data.get("values") or {}
                reply: Dict[str, object] = {"type": "config_saved", "mode": mode}
                if self._mode_in_progress(mode):
                    reply["ok"] = False
                    reply["error"] = "match_in_progress"
                else:
                    try:
                        if mode == "indoor":
                            saved = config_store.save_indoor_config(values)
                            reply["ok"] = True
                            reply["values"] = asdict(saved)
                        elif mode == "flint":
                            saved = config_store.save_flint_config(values)
                            reply["ok"] = True
                            reply["values"] = asdict(saved)
                        elif mode == "app":
                            saved = config_store.save_app_config(values)
                            self._sound_pack = saved["sound_pack"]
                            reply["ok"] = True
                            reply["values"] = saved
                        else:
                            reply["ok"] = False
                            reply["error"] = f"unknown mode {mode!r}"
                    except (ValueError, TypeError) as exc:
                        reply["ok"] = False
                        reply["error"] = str(exc)
                if websocket is not None:
                    try:
                        await websocket.send(json.dumps(reply))
                    except Exception:
                        pass
                if reply.get("ok") and mode == "app":
                    # Le pack de sons s'applique immédiatement à tous les
                    # écrans déjà connectés, contrairement à la config
                    # Indoor/Flint qui n'agit qu'au prochain démarrage.
                    await self.broadcast_state()

    def _mode_in_progress(self, mode: str) -> bool:
        """True if a match of this same mode is currently loaded and not
        finished (active, paused, or in emergency) -- saving new config
        values for that mode is blocked in that case, so nobody edits the
        rules of a competition while it's actually being shot."""
        return (
            self.engine is not None
            and self._current_mode_kind == mode
            and not self.engine.current_state.finished
        )

    # -- background ticking -------------------------------------------------

    async def tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL)
            events = []
            async with self._lock:
                if self.engine is not None:
                    self.engine.tick(TICK_INTERVAL)
                    events = self.engine.pop_pending_events()
            await self.broadcast_state()
            if events:
                await self._broadcast({"type": "events", "events": events})

    # -- broadcasting ---------------------------------------------------------

    async def broadcast_state(self) -> None:
        """Sends each connected client its own tailored payload -- not a
        single shared broadcast -- since a display registered on a given
        lane may have a message targeted just at it (see
        :meth:`_payload_for`)."""
        if not self.clients:
            return
        for ws in list(self.clients):
            try:
                await ws.send(json.dumps(self._payload_for(ws)))
            except Exception:
                self.clients.discard(ws)
                self._display_lanes.pop(ws, None)

    async def _send_state_to(self, websocket) -> None:
        try:
            await websocket.send(json.dumps(self._payload_for(websocket)))
        except Exception:
            self.clients.discard(websocket)
            self._display_lanes.pop(websocket, None)

    def _payload_for(self, websocket) -> dict:
        state_dict = _state_to_dict(self.engine.current_state) if self.engine is not None else None
        lane = self._display_lanes.get(websocket)
        message = self._lane_messages.get(lane) if lane and lane in self._lane_messages else self._message
        def _lane_sort_key(lane: str):
            return (0, int(lane)) if lane.isdigit() else (1, lane)

        connected_lanes = sorted(
            {l for l in self._display_lanes.values() if l != "apercu"},
            key=_lane_sort_key,
        )
        match_in_progress = self.engine is not None and not self.engine.current_state.finished
        return {
            "type": "state", "state": state_dict,
            "message": message, "language": self._language,
            "event_title": self._event_title,
            "connected_lanes": connected_lanes,
            "active_mode": self._current_mode_kind if match_in_progress else None,
            "sound_pack": self._sound_pack,
        }

    async def _broadcast(self, payload: dict) -> None:
        if not self.clients:
            return
        message = json.dumps(payload)
        for ws in list(self.clients):
            try:
                await ws.send(message)
            except Exception:
                self.clients.discard(ws)
                self._display_lanes.pop(ws, None)
