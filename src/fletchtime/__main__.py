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
import shutil
import socket
import sys
import threading
from importlib import resources
from pathlib import Path

from fletchtime.server.http_static import start_http_server
from fletchtime.server.ws_server import run_ws_server

HTTP_PORT = 8000
WS_PORT = 8765

# Dossiers pré-remplis avec un contenu par défaut fourni avec FletchTime
# (copié une seule fois, au tout premier lancement -- jamais écrasé
# ensuite, donc une personnalisation du club est toujours préservée même
# après une mise à jour du paquet).
BOOTSTRAP_DEFAULT_DIRS = {
    "targets": "_defaults/targets",
    "sounds/packs/classic": "_defaults/sounds/packs/classic",
}

# Fichiers isolés copiés une seule fois (même logique que ci-dessus, mais
# pour un seul fichier plutôt qu'un dossier entier) -- des README qui
# expliquent la convention à suivre pour chaque type de donnée du club.
BOOTSTRAP_DEFAULT_FILES = {
    "club/README.md": "_defaults/club/README.md",
    "banners/README.md": "_defaults/banners/README.md",
    "sounds/packs/README.md": "_defaults/sounds/packs/README.md",
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


def ensure_directories(data_root: Path, app_web_dir: Path) -> None:
    """Crée les dossiers attendus s'ils manquent, et copie le contenu par
    défaut fourni avec FletchTime (README explicatifs, images de blasons,
    pack de sons "classic") au tout premier lancement -- idempotent, sans
    danger à chaque redémarrage, et ne touche jamais à un fichier/dossier
    déjà existant (donc ne casse ni n'écrase jamais une personnalisation
    faite par le club, y compris après une mise à jour)."""
    for rel, default_rel in BOOTSTRAP_DEFAULT_DIRS.items():
        directory = data_root / "web" / "assets" / rel
        if directory.exists():
            continue
        source = app_web_dir / default_rel
        if source.is_dir():
            shutil.copytree(source, directory)
        else:
            # ancien build sans _defaults (ou chemin inattendu) -- pas de
            # contenu par défaut à copier, mais ne doit jamais planter
            # le démarrage pour autant.
            directory.mkdir(parents=True, exist_ok=True)

    for rel, default_rel in BOOTSTRAP_DEFAULT_FILES.items():
        dest = data_root / "web" / "assets" / rel
        if dest.exists():
            continue
        source = app_web_dir / default_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, dest)

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
    app_web_dir = _app_web_dir()
    ensure_directories(data_root, app_web_dir)
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
