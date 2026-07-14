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
from dataclasses import asdict
from typing import Optional, Set

from fletchtime_engine import (
    FlintConfig,
    FlintMode,
    IndoorConfig,
    IndoorMode,
    MatchEngine,
    MatchState,
)

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
        # Kept independent of the engine on purpose: a message ("Retard de
        # 15 minutes...") must be showable even before a match has started,
        # between matches, or after one has finished.
        self._message: Optional[str] = None

    # -- connection lifecycle ---------------------------------------------

    async def register(self, websocket) -> None:
        self.clients.add(websocket)
        await self._send_state_to(websocket)

    async def unregister(self, websocket) -> None:
        self.clients.discard(websocket)

    # -- commands from /control ---------------------------------------------

    async def handle_command(self, raw_message: str) -> None:
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return
        action = data.get("action")

        async with self._lock:
            if action == "start_indoor":
                turn_mode = data.get("turn_mode", "ab_then_cd")
                alternate = data.get("alternate", True)
                try:
                    self.engine = MatchEngine(IndoorMode(IndoorConfig(
                        turn_mode=turn_mode,
                        alternate_relay_order_each_series=bool(alternate),
                    )))
                except ValueError:
                    pass  # invalid turn_mode from a malformed command -- ignore
            elif action == "start_flint":
                self.engine = MatchEngine(FlintMode(FlintConfig()))
            elif action == "message":
                self._message = data.get("value") or None
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
        await self._broadcast(self._current_state_payload())

    async def _send_state_to(self, websocket) -> None:
        message = json.dumps(self._current_state_payload())
        try:
            await websocket.send(message)
        except Exception:
            self.clients.discard(websocket)

    def _current_state_payload(self) -> dict:
        state_dict = _state_to_dict(self.engine.current_state) if self.engine is not None else None
        return {"type": "state", "state": state_dict, "message": self._message}

    async def _broadcast(self, payload: dict) -> None:
        if not self.clients:
            return
        message = json.dumps(payload)
        for ws in list(self.clients):
            try:
                await ws.send(message)
            except Exception:
                self.clients.discard(ws)
