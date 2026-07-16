"""WebSocket endpoint: one connection handler shared by /control and every
/display client. Uses only the base ``websockets.serve`` + send/recv API
(stable across recent library versions), deliberately avoiding the
combined HTTP+WS-on-one-port trick whose API has shifted between
``websockets`` releases -- see docs/architecture.md for why HTTP (static
pages) is served separately by ``fletchtime.server.http_static``.
"""

from __future__ import annotations

import asyncio

import websockets

from .match_server import MatchServer


async def run_ws_server(port: int) -> None:
    server_state = MatchServer()

    async def handler(websocket, *_args):
        # *_args absorbs the optional "path" positional argument some
        # websockets versions still pass to the handler.
        await server_state.register(websocket)
        try:
            async for message in websocket:
                await server_state.handle_command(message, websocket)
        except websockets.exceptions.ConnectionClosed:
            # Expected when a phone/tablet screen locks or the browser tab
            # is backgrounded: Android suspends network activity, the
            # client stops answering keepalive pings, and the connection
            # times out. Not an error condition worth a traceback.
            pass
        finally:
            await server_state.unregister(websocket)

    tick_task = asyncio.create_task(server_state.tick_loop())
    try:
        async with websockets.serve(
            handler,
            "0.0.0.0",
            port,
            ping_interval=20,
            ping_timeout=20,
        ):
            await asyncio.Future()  # run forever
    finally:
        tick_task.cancel()
