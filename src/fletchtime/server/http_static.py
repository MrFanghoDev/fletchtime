"""Serves the static pages (control.html, display.html) over plain HTTP,
stdlib only -- no risk of incompatible native dependencies on Pydroid.

Kept on a separate port from the WebSocket server on purpose: combining
HTTP + WS on a single port requires APIs that have shifted across
``websockets`` releases, while two plain servers on two ports is boring
and guaranteed to work everywhere, including on a phone.
"""

from __future__ import annotations

import functools
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fletchtime import __version__


class _DualRootHandler(SimpleHTTPRequestHandler):
    """Serves the app's own static pages (control.html, i18n.js, logo.svg...)
    from ``directory`` as usual, but reroutes any ``/assets/...`` request to
    a separate ``assets_dir`` instead, and answers ``/api/version`` directly
    (used by index.html to display the running server's version -- see
    ``fletchtime.__version__``).

    This matters once FletchTime is a proper installed package: the app
    pages live read-only inside the installed package, while club-specific
    data (logo, banners, target images, sound packs) must stay writable and
    outside of it -- see ``fletchtime.__main__``. When running as a
    PyInstaller executable or straight from a git clone, ``assets_dir`` is
    simply ``directory / "assets"``, so this is a no-op in practice (same
    behaviour as before this existed).
    """

    def __init__(
        self, *args, directory: str, assets_dir: str, ws_port: int, match_server=None, **kwargs
    ) -> None:
        self._assets_dir = assets_dir
        self._ws_port = ws_port
        self._match_server = match_server
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/version":
            # ws_port inclus ici : c'est le seul moyen pour le JS des pages
            # (display.html/control.html) de connaître le port WebSocket
            # réellement configuré -- il ne peut plus être codé en dur
            # côté client depuis que les ports sont devenus modifiables
            # (voir fletchtime.gui, config_store.load_gui_config) ; il n'y
            # a que ce même port HTTP, connu implicitement via l'URL de la
            # page elle-même, qui est garanti correct sans configuration
            # supplémentaire côté client.
            body = json.dumps({"version": __version__, "ws_port": self._ws_port}).encode("utf-8")
            self._send_json(body)
            return
        if self.path == "/api/status":
            self._send_json(self._build_status_body())
            return
        super().do_GET()

    def _send_json(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _build_status_body(self) -> bytes:
        """Les mêmes données techniques que celles déjà affichées dans la
        page de contrôle (écrans connectés, mode actif...), exposées ici
        pour que la fenêtre graphique puisse les afficher aussi sans
        dupliquer la logique de rendu HTML -- voir fletchtime.gui,
        interrogé par sondage périodique plutôt qu'en temps réel (pas
        besoin d'une vraie connexion WebSocket juste pour un affichage de
        statut, voir sa docstring pour le détail de ce choix).

        Lu directement depuis l'instance MatchServer partagée avec le
        serveur WebSocket (voir fletchtime.runtime.ServerRuntime), depuis
        un thread différent de celui qui la modifie -- en lecture seule,
        sans le verrou asyncio de MatchServer (qui ne serait de toute
        façon pas utilisable depuis ce thread synchrone). Le GIL rend
        chaque lecture individuelle atomique ; au pire, une valeur d'un
        sondage sur deux légèrement obsolète pour un simple affichage de
        statut, jamais une valeur corrompue."""
        if self._match_server is None:
            return json.dumps({"available": False}).encode("utf-8")

        server = self._match_server
        engine = server.engine
        state = engine.current_state if engine is not None else None
        connected_lanes = sorted(
            {lane for lane in server._display_lanes.values() if lane != "apercu"}
        )
        payload = {
            "available": True,
            "connected_clients": len(server.clients),
            "connected_lanes": connected_lanes,
            "active_mode": server._current_mode_kind,
            "match_phase": state.phase.value if state is not None else None,
            "match_finished": state.finished if state is not None else None,
            "sound_pack": server._sound_pack,
            "password_configured": bool(server._password),
        }
        return json.dumps(payload).encode("utf-8")

    def translate_path(self, path: str) -> str:
        if path == "/assets" or path.startswith("/assets/"):
            rel = path[len("/assets") :].lstrip("/")
            # reproduit la logique de nettoyage de chemin de la classe de
            # base (retire la query string, etc.) en la réappliquant à un
            # chemin de base différent
            original_directory = self.directory
            try:
                self.directory = self._assets_dir
                return super().translate_path("/" + rel)
            finally:
                self.directory = original_directory
        return super().translate_path(path)


def start_http_server(
    directory: str,
    port: int,
    assets_dir: str | None = None,
    ws_port: int | None = None,
    match_server=None,
) -> ThreadingHTTPServer:
    """``assets_dir`` defaults to ``<directory>/assets`` when not given,
    matching the historical single-root behaviour (dev checkout, or a
    PyInstaller build where everything sits together next to the exe).

    ``ws_port`` defaults to ``port + 765`` (matching the historical
    8000/8765 default pair) when not given -- only used as a last-resort
    fallback, callers should normally pass the real configured value
    (see ``fletchtime.runtime.ServerRuntime``).

    ``match_server``, if given, is exposed read-only via ``/api/status``
    (see ``_DualRootHandler._build_status_body``) -- ``None`` by default,
    in which case that endpoint reports ``{"available": false}`` rather
    than erroring, since not every caller needs/has one to share (e.g.
    a bare ``start_http_server()`` call in isolation, as some tests do).

    Returns the bound (but not yet serving) server instance -- the caller
    is expected to run ``.serve_forever()`` on it (typically in a
    background thread) and can call ``.shutdown()`` from any other thread
    for a clean stop (standard library guarantee, see
    ``socketserver.BaseServer``)."""
    resolved_assets_dir = assets_dir or str(Path(directory) / "assets")
    resolved_ws_port = ws_port if ws_port is not None else port + 765
    handler = functools.partial(
        _DualRootHandler,
        directory=directory,
        assets_dir=resolved_assets_dir,
        ws_port=resolved_ws_port,
        match_server=match_server,
    )
    return ThreadingHTTPServer(("0.0.0.0", port), handler)
