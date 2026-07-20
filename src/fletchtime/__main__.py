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

import argparse
import logging
import shutil
import signal
import socket
import sys
import threading
from importlib import resources
from pathlib import Path

from fletchtime import __version__
from fletchtime.logging_setup import configure_logging
from fletchtime.runtime import ServerRuntime
from fletchtime.server import config_store

# Anciennement des constantes HTTP_PORT/WS_PORT figées ici -- les ports
# par défaut vivent maintenant uniquement dans
# config_store.DEFAULT_GUI_CONFIG, seule source de vérité (voir
# _run_headless ci-dessous et fletchtime.gui, qui lisent tous deux
# config_store.load_gui_config() plutôt qu'une constante figée). Permet
# de faire tourner plusieurs salles de compétition sur un même PC : une
# copie de dossier par salle, chacune avec son propre config/gui.toml.

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


def _print_banner(ip: str, data_root: Path, http_port: int) -> None:
    print("=" * 60)
    print(f"  FletchTime {__version__} -- serveur de contrôle et d'affichage")
    print(f"  FletchTime {__version__} -- control and display server")
    print("=" * 60)
    print(f"  Accueil / Home      : http://{ip}:{http_port}/")
    print(f"  Contrôle / Control  : http://{ip}:{http_port}/control.html")
    print(f"  Affichage / Display : http://{ip}:{http_port}/display.html?lane=1")
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


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fletchtime",
        description=(
            "Serveur de chronométrage pour compétitions d'archerie FFTL "
            "(Indoor et Flint)."
        ),
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"FletchTime {__version__}",
    )
    parser.add_argument(
        "--headless",
        "--no-gui",
        dest="headless",
        action="store_true",
        help="Mode terminal, sans fenêtre graphique.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Affiche les journaux applicatifs (commandes reçues, "
        "(dé)connexions...) dans le terminal, pas seulement dans le "
        "fichier de journal.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Journalisation la plus détaillée possible, fichier compris "
        "-- implique --verbose.",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        metavar="PORT",
        help="Port HTTP -- remplace la valeur de config/gui.toml pour "
        "cette exécution seulement, sans la modifier (voir aussi la "
        "fenêtre graphique pour un réglage persistant).",
    )
    parser.add_argument(
        "--ws-port",
        type=int,
        metavar="PORT",
        help="Port WebSocket -- remplace la valeur de config/gui.toml "
        "pour cette exécution seulement, sans la modifier.",
    )
    return parser


def _resolve_console_log_level(args: argparse.Namespace) -> int:
    if args.debug:
        return logging.DEBUG
    if args.verbose:
        return logging.INFO
    return logging.WARNING


def _resolve_ports(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[int, int]:
    """Priorité aux options de la ligne de commande sur config/gui.toml,
    sans jamais modifier ce fichier -- une exécution scriptée/CI ne doit
    pas laisser de trace persistante par accident. Revalide les deux
    ports ensemble (même règle que config_store.save_gui_config) même
    si un seul des deux vient de la ligne de commande, pour ne jamais se
    retrouver avec une combinaison invalide (identiques, hors bornes)."""
    gui_config = config_store.load_gui_config()
    http_port = args.http_port if args.http_port is not None else gui_config["http_port"]
    ws_port = args.ws_port if args.ws_port is not None else gui_config["ws_port"]
    for name, port in (("--http-port", http_port), ("--ws-port", ws_port)):
        if not (1 <= port <= 65535):
            parser.error(f"{name} : le port doit être entre 1 et 65535 (reçu {port}).")
    if http_port == ws_port:
        parser.error("--http-port et --ws-port doivent être différents.")
    return http_port, ws_port


def _run_headless(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Mode terminal classique -- utilisé si l'interface graphique n'a pas
    pu être chargée (ex. `customtkinter` absent), ou explicitement demandé
    via `--headless`/`--no-gui`."""
    data_root = _data_root()
    app_web_dir = _app_web_dir()
    ensure_directories(data_root, app_web_dir)
    assets_dir = data_root / "web" / "assets"

    console_level = _resolve_console_log_level(args)
    file_level = logging.DEBUG if args.debug else logging.INFO
    log_file = configure_logging(data_root / "logs", console_level, file_level)
    print(f"Journal détaillé / Detailed log: {log_file}")

    # Ports lus depuis config/gui.toml par défaut (mêmes préférences que
    # la fenêtre graphique, voir config_store.load_gui_config), sauf
    # remplacement explicite via --http-port/--ws-port pour cette seule
    # exécution -- permet de faire tourner plusieurs salles de
    # compétition sur un même PC sans dossier séparé par salle, utile
    # pour un lancement scripté/CI par exemple.
    http_port, ws_port = _resolve_ports(args, parser)

    _print_banner(local_ip(), data_root, http_port)

    runtime = ServerRuntime(str(app_web_dir), str(assets_dir), http_port, ws_port)
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
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.headless:
        _run_headless(args, parser)
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
        _run_headless(args, parser)


if __name__ == "__main__":
    main()
