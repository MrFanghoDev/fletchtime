"""Encapsulates the start/stop lifecycle of both servers (HTTP static +
WebSocket) as one logical unit. Used by both the plain CLI entry point
(``fletchtime.__main__``) and the graphical one (``fletchtime.gui``), so
neither duplicates this logic nor risks drifting out of sync with the
other.

The WebSocket server needs its own asyncio event loop; since a GUI
mainloop (tkinter/customtkinter) must own the *main* thread, that loop
runs in a dedicated background thread here -- exactly the same shape as
the HTTP server, which already ran in a background thread even before
this module existed.
"""

from __future__ import annotations

import asyncio
import threading
from http.server import ThreadingHTTPServer

from fletchtime.server.http_static import start_http_server
from fletchtime.server.ws_server import run_ws_server


class ServerRuntime:
    """Not thread-safe for concurrent ``start()``/``stop()`` calls from
    multiple threads at once -- callers (CLI, GUI) are expected to only
    ever call these from a single "control" thread (e.g. the GUI's main
    thread reacting to button clicks), which is the normal case."""

    def __init__(self, app_web_dir: str, assets_dir: str, http_port: int, ws_port: int) -> None:
        self.app_web_dir = app_web_dir
        self.assets_dir = assets_dir
        self.http_port = http_port
        self.ws_port = ws_port

        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None
        self._ws_loop: asyncio.AbstractEventLoop | None = None
        self._ws_stop_event: asyncio.Event | None = None
        self._ws_ready = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._http_thread is not None and self._http_thread.is_alive()

    def start(self) -> None:
        """No-op if already running -- safe to call defensively (e.g. a
        GUI's "Démarrer" button handler doesn't need to separately check
        state first)."""
        if self.is_running:
            return

        self._httpd = start_http_server(
            self.app_web_dir, self.http_port, self.assets_dir, self.ws_port
        )
        self._http_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._http_thread.start()

        self._ws_ready.clear()
        self._ws_thread = threading.Thread(target=self._run_ws_loop, daemon=True)
        self._ws_thread.start()
        # Attend que la boucle asyncio du thread WS soit prête avant de
        # rendre la main -- évite une fenêtre où stop() pourrait être
        # appelé avant que self._ws_loop/_ws_stop_event n'existent.
        self._ws_ready.wait(timeout=5)

    def _run_ws_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._ws_loop = loop
        self._ws_stop_event = asyncio.Event()
        self._ws_ready.set()
        try:
            loop.run_until_complete(run_ws_server(self.ws_port, self._ws_stop_event))
        finally:
            loop.close()

    def stop(self, timeout: float = 5.0) -> None:
        """No-op if not running. Blocks (briefly) until both server
        threads have actually terminated, so a caller can safely assume
        the ports are free again once this returns -- important for a
        GUI's "Démarrer" button right after "Arrêter": binding to the
        same port again would otherwise race with the still-shutting-down
        previous server."""
        if self._httpd is not None:
            self._httpd.shutdown()  # débloque serve_forever() -- sûr depuis un autre thread
            self._httpd.server_close()
            self._httpd = None

        if self._ws_loop is not None and self._ws_stop_event is not None:
            self._ws_loop.call_soon_threadsafe(self._ws_stop_event.set)

        if self._http_thread is not None:
            self._http_thread.join(timeout=timeout)
            self._http_thread = None

        if self._ws_thread is not None:
            self._ws_thread.join(timeout=timeout)
            self._ws_thread = None

        self._ws_loop = None
        self._ws_stop_event = None

    def restart(self) -> None:
        self.stop()
        self.start()
