"""Tests for fletchtime.runtime.ServerRuntime -- the start/stop lifecycle
shared by the CLI and the (future) GUI.

A minimal fake ``websockets`` module is injected into ``sys.modules``
before importing anything, since the real library isn't a test dependency
(see test.yml, which deliberately doesn't install it) and the WS server's
real code only needs the small subset of its API exercised here (an async
context manager returned by ``serve()``). This mirrors how
``fletchtime.server.ws_server`` now imports ``websockets`` lazily inside
the function body specifically so this stays possible.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path


def _install_fake_websockets() -> None:
    if getattr(sys.modules.get("websockets"), "_fletchtime_fake", False):
        return  # déjà en place, pas besoin de le refaire à chaque test

    class ConnectionClosed(Exception):
        pass

    exceptions_mod = types.ModuleType("websockets.exceptions")
    exceptions_mod.ConnectionClosed = ConnectionClosed

    class _FakeServeContext:
        def __init__(self, handler, host, port, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    def serve(handler, host, port, **kwargs):
        return _FakeServeContext(handler, host, port, **kwargs)

    fake = types.ModuleType("websockets")
    fake._fletchtime_fake = True
    fake.exceptions = exceptions_mod
    fake.serve = serve
    sys.modules["websockets"] = fake
    sys.modules["websockets.exceptions"] = exceptions_mod


_install_fake_websockets()

from fletchtime.runtime import ServerRuntime  # noqa: E402


class TestServerRuntime(unittest.TestCase):
    HTTP_PORT = 8563
    WS_PORT = 8964

    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        (self.tmpdir / "assets").mkdir(parents=True)
        (self.tmpdir / "index.html").write_text("<html>test</html>", encoding="utf-8")
        self.runtime = ServerRuntime(
            str(self.tmpdir), str(self.tmpdir / "assets"), self.HTTP_PORT, self.WS_PORT
        )

    def tearDown(self) -> None:
        self.runtime.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_not_running_initially(self) -> None:
        self.assertFalse(self.runtime.is_running)

    def test_start_makes_http_server_reachable(self) -> None:
        self.runtime.start()
        time.sleep(0.3)
        self.assertTrue(self.runtime.is_running)
        res = urllib.request.urlopen(f"http://127.0.0.1:{self.HTTP_PORT}/index.html")
        self.assertEqual(res.status, 200)

    def test_stop_frees_the_port(self) -> None:
        self.runtime.start()
        time.sleep(0.3)
        self.runtime.stop()
        self.assertFalse(self.runtime.is_running)
        with self.assertRaises((urllib.error.URLError, ConnectionRefusedError)):
            urllib.request.urlopen(f"http://127.0.0.1:{self.HTTP_PORT}/", timeout=1)

    def test_restart_works_on_the_same_port(self) -> None:
        self.runtime.start()
        time.sleep(0.3)
        self.runtime.stop()
        self.runtime.start()
        time.sleep(0.3)
        res = urllib.request.urlopen(f"http://127.0.0.1:{self.HTTP_PORT}/index.html")
        self.assertEqual(res.status, 200)

    def test_double_start_is_a_noop(self) -> None:
        self.runtime.start()
        time.sleep(0.2)
        first_thread = self.runtime._http_thread
        self.runtime.start()
        self.assertIs(self.runtime._http_thread, first_thread)

    def test_stop_without_start_does_not_raise(self) -> None:
        self.runtime.stop()  # ne doit pas lever d'exception


if __name__ == "__main__":
    unittest.main()
