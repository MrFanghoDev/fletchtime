"""Serves the static pages (control.html, display.html) over plain HTTP,
stdlib only -- no risk of incompatible native dependencies on Pydroid.

Kept on a separate port from the WebSocket server on purpose: combining
HTTP + WS on a single port requires APIs that have shifted across
``websockets`` releases, while two plain servers on two ports is boring
and guaranteed to work everywhere, including on a phone.
"""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


def start_http_server(directory: str, port: int) -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=directory)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    httpd.serve_forever()
