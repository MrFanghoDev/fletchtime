"""Lance le serveur Fletchtime : ouvrir ce fichier dans Pydroid et appuyer
sur "Run". Affiche l'adresse à ouvrir depuis les navigateurs (contrôle et
écrans d'affichage), sur le même réseau WiFi.

Nécessite le paquet `websockets` (pip install websockets -- dans Pydroid :
menu ☰ → Pip → chercher "websockets" → Installer). Aucune autre dépendance.
"""

import asyncio
import socket
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fletchtime_server.http_static import start_http_server  # noqa: E402
from fletchtime_server.ws_server import run_ws_server  # noqa: E402

HTTP_PORT = 8000
WS_PORT = 8765


def local_ip() -> str:
    """Best-effort local network IP (works even offline, since a UDP
    'connect' only consults the routing table, no packet is actually
    sent). Falls back to 127.0.0.1 if there is no network route at all."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ip = local_ip()
    print("=" * 60)
    print("  Fletchtime -- serveur de contrôle et d'affichage")
    print("=" * 60)
    print(f"  Accueil   : http://{ip}:{HTTP_PORT}/")
    print(f"  Contrôle  : http://{ip}:{HTTP_PORT}/control.html")
    print(f"  Affichage : http://{ip}:{HTTP_PORT}/display.html?lane=1")
    print()
    print("  Depuis CE téléphone, remplace l'IP par 127.0.0.1 si besoin.")
    print("  Depuis une tablette/PC sur le même WiFi, utilise l'IP ci-dessus.")
    print("  (si l'IP semble fausse : vérifie-la dans les réglages WiFi du téléphone)")
    print("=" * 60)

    http_thread = threading.Thread(
        target=start_http_server,
        args=(str(PROJECT_ROOT / "web"), HTTP_PORT),
        daemon=True,
    )
    http_thread.start()

    try:
        asyncio.run(run_ws_server(WS_PORT))
    except KeyboardInterrupt:
        print("Arrêt du serveur.")


if __name__ == "__main__":
    main()
