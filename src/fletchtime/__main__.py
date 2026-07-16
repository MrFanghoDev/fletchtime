"""Point d'entrée `python -m fletchtime` (ou la commande `fletchtime` si le
paquet est installé -- voir `[project.scripts]` dans pyproject.toml) : lance
le serveur de contrôle et d'affichage.

Deux notions de dossier bien distinctes ici, à ne pas confondre :

- Les **pages de l'application** (control.html, display.html, i18n.js,
  logo.svg...) : toujours en lecture seule du point de vue du club, peu
  importe comment FletchTime a été installé -- elles vivent dans le paquet
  installé (``fletchtime.web``), ou à côté de l'exécutable pour un build
  PyInstaller.
- Les **données propres à un club** (logo, bannières, images de cible,
  packs de sons, réglages TOML) : doivent rester modifiables, donc jamais
  dans le paquet installé lui-même. Vivent dans le répertoire courant
  (comme la plupart des outils en ligne de commande -- jekyll, hugo...),
  ou à côté de l'exécutable pour un build PyInstaller (pour rester
  cohérent avec le comportement historique de cette distribution-là).
"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
from importlib import resources
from pathlib import Path

from fletchtime.server.http_static import start_http_server
from fletchtime.server.ws_server import run_ws_server

HTTP_PORT = 8000
WS_PORT = 8765

BOOTSTRAP_ASSET_DIRS = {
    "club": (
        "Dépose ici le logo de ton club (ex. logo.jpg) pour qu'il\n"
        "apparaisse sur l'écran neutre entre les phases de tir.\n"
    ),
    "banners": (
        "Dépose ici les images de bannières sponsors (.jpg/.png/...) --\n"
        "elles défilent automatiquement sur l'écran neutre.\n"
    ),
    "targets": (
        "Dépose ici les images de blasons utilisées par l'Indoor et le\n"
        "Flint (voir config.html pour les noms de fichiers attendus).\n"
    ),
    "sounds/packs/_custom": (
        "Gabarit pour créer un pack de sons personnalisé -- voir le\n"
        "README à côté de ce fichier pour la convention de nommage.\n"
    ),
}


def _app_web_dir() -> Path:
    """Où vivent les pages de l'application elles-même."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "web"
    return Path(str(resources.files("fletchtime.web")))


def _data_root() -> Path:
    """Où vivent les données propres au club (voir docstring du module)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def ensure_directories(data_root: Path) -> None:
    """Crée les dossiers attendus s'ils manquent -- idempotent, sans danger
    à chaque redémarrage. Nécessaire pour qu'un premier lancement (paquet
    tout juste installé, ou exécutable tout juste décompressé) fonctionne
    du premier coup."""
    for rel, readme_text in BOOTSTRAP_ASSET_DIRS.items():
        directory = data_root / "web" / "assets" / rel
        if directory.exists():
            continue
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "README.txt").write_text(readme_text, encoding="utf-8")
    (data_root / "config").mkdir(parents=True, exist_ok=True)


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
    data_root = _data_root()
    ensure_directories(data_root)
    app_web_dir = _app_web_dir()
    assets_dir = data_root / "web" / "assets"

    ip = local_ip()
    print("=" * 60)
    print("  FletchTime -- serveur de contrôle et d'affichage")
    print("=" * 60)
    print(f"  Accueil   : http://{ip}:{HTTP_PORT}/")
    print(f"  Contrôle  : http://{ip}:{HTTP_PORT}/control.html")
    print(f"  Affichage : http://{ip}:{HTTP_PORT}/display.html?lane=1")
    print()
    print("  Depuis CE téléphone, remplace l'IP par 127.0.0.1 si besoin.")
    print("  Depuis une tablette/PC sur le même WiFi, utilise l'IP ci-dessus.")
    print("  (si l'IP semble fausse : vérifie-la dans les réglages WiFi du téléphone)")
    print(f"  Données du club (logo, sons, config...) : {data_root}")
    print("=" * 60)

    http_thread = threading.Thread(
        target=start_http_server,
        args=(str(app_web_dir), HTTP_PORT, str(assets_dir)),
        daemon=True,
    )
    http_thread.start()

    try:
        asyncio.run(run_ws_server(WS_PORT))
    except KeyboardInterrupt:
        print("Arrêt du serveur.")


if __name__ == "__main__":
    main()
