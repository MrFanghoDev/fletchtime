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

import shutil
import signal
import socket
import sys
import threading
from importlib import resources
from pathlib import Path

from fletchtime.runtime import ServerRuntime

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


def _print_banner(ip: str, data_root: Path) -> None:
    print("=" * 60)
    print("  FletchTime -- serveur de contrôle et d'affichage")
    print("  FletchTime -- control and display server")
    print("=" * 60)
    print(f"  Accueil / Home      : http://{ip}:{HTTP_PORT}/")
    print(f"  Contrôle / Control  : http://{ip}:{HTTP_PORT}/control.html")
    print(f"  Affichage / Display : http://{ip}:{HTTP_PORT}/display.html?lane=1")
    print()
    print("  Depuis CET appareil, remplace l'IP par 127.0.0.1 si besoin.")
    print("  From THIS device, replace the IP with 127.0.0.1 if needed.")
    print()
    print("  Depuis un autre appareil sur le même réseau WiFi, utilise l'IP ci-dessus.")
    print("  From another device on the same WiFi network, use the IP above.")
    print()
    print("  (si l'IP semble fausse, vérifie-la dans les réglages réseau)")
    print("  (if the IP looks wrong, check it in your network settings)")
    print()
    print(f"  Données du club (logo, sons, config...) / Club data: {data_root}")
    print("=" * 60)
    if sys.platform == "win32":
        print("  Windows : si un autre appareil n'arrive pas à se connecter,")
        print("  autorise FletchTime dans le pare-feu Windows (Autoriser une")
        print("  application... -- coche réseaux privés) quand la fenêtre")
        print("  d'alerte apparaît, ou vérifie-le dans les paramètres.")
        print("  Windows: if another device can't connect, allow FletchTime")
        print("  through Windows Firewall (Allow an app... -- check private")
        print("  networks) when the alert pops up, or check it in settings.")
        print("=" * 60)


def _run_headless() -> None:
    """Mode terminal classique -- utilisé si l'interface graphique n'a pas
    pu être chargée (ex. `customtkinter` absent), ou explicitement demandé
    via `--headless`/`--no-gui`."""
    data_root = _data_root()
    app_web_dir = _app_web_dir()
    ensure_directories(data_root, app_web_dir)
    assets_dir = data_root / "web" / "assets"

    _print_banner(local_ip(), data_root)

    runtime = ServerRuntime(str(app_web_dir), str(assets_dir), HTTP_PORT, WS_PORT)
    runtime.start()

    stop_event = threading.Event()
    if sys.platform != "win32":
        # SIGTERM (ex. arrêt de service) en plus de Ctrl+C -- pas
        # nécessaire sous Windows, où signal.SIGTERM n'est pas géré de la
        # même façon et n'apporte rien de plus que KeyboardInterrupt ici.
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
    try:
        stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        print("Arrêt du serveur. / Server stopped.")


def main() -> None:
    if "--headless" in sys.argv or "--no-gui" in sys.argv:
        _run_headless()
        return

    try:
        from fletchtime.gui import run_gui

        run_gui()
    except Exception as exc:
        # Couvre à la fois un import qui échoue (ex. customtkinter absent)
        # ET un échec plus tardif à la construction de la fenêtre elle-même
        # -- notamment sur Pydroid, qui refuse catégoriquement d'ouvrir une
        # fenêtre Tk quand le script est lancé depuis son terminal plutôt
        # que via le bouton ▶️ Run de l'éditeur ("GUI applications cannot
        # be ran from terminal"). run_gui() se charge d'arrêter proprement
        # tout serveur qu'elle aurait déjà démarré avant l'échec, donc ce
        # repli ne risque pas un conflit de port avec _run_headless().
        print(f"Interface graphique indisponible ({exc}) -- mode terminal.")
        print(f"Graphical interface unavailable ({exc}) -- terminal mode.")
        _run_headless()


if __name__ == "__main__":
    main()
