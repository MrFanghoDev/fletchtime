"""WebSocket endpoint: one connection handler shared by /control and every
/display client. Uses only the base ``websockets.serve`` + send/recv API
(stable across recent library versions), deliberately avoiding the
combined HTTP+WS-on-one-port trick whose API has shifted between
``websockets`` releases -- see docs/architecture.md for why HTTP (static
pages) is served separately by ``fletchtime.server.http_static``.
"""

from __future__ import annotations

import asyncio

from .match_server import MatchServer


async def run_ws_server(
    port: int,
    stop_event: asyncio.Event | None = None,
    server_state: MatchServer | None = None,
) -> None:
    # Import différé (pas en tête de fichier) : permet d'importer ce module
    # -- et fletchtime.runtime, qui en dépend -- sans que `websockets` soit
    # installé, utile pour les tests (voir test.yml, qui ne l'installe pas
    # volontairement). Seul un vrai démarrage du serveur en a besoin.
    import websockets

    server_state = server_state if server_state is not None else MatchServer()
    stop_event = stop_event if stop_event is not None else asyncio.Event()

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
            # Sans stop_event fourni (usage historique : Ctrl+C dans un
            # terminal), ceci équivaut à `await asyncio.Future()` -- tourne
            # indéfiniment jusqu'à l'annulation de la tâche. Avec un
            # stop_event (voir fletchtime.runtime.ServerRuntime), permet un
            # arrêt propre déclenché depuis un autre thread (ex. bouton
            # "Arrêter" de la fenêtre graphique).
            await stop_event.wait()
    finally:
        tick_task.cancel()
