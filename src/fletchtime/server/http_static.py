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

    def __init__(self, *args, directory: str, assets_dir: str, ws_port: int, **kwargs) -> None:
        self._assets_dir = assets_dir
        self._ws_port = ws_port
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
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

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
    directory: str, port: int, assets_dir: str | None = None, ws_port: int | None = None
) -> ThreadingHTTPServer:
    """``assets_dir`` defaults to ``<directory>/assets`` when not given,
    matching the historical single-root behaviour (dev checkout, or a
    PyInstaller build where everything sits together next to the exe).

    ``ws_port`` defaults to ``port + 765`` (matching the historical
    8000/8765 default pair) when not given -- only used as a last-resort
    fallback, callers should normally pass the real configured value
    (see ``fletchtime.runtime.ServerRuntime``).

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
    )
    return ThreadingHTTPServer(("0.0.0.0", port), handler)
