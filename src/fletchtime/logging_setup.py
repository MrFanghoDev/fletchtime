"""Configuration du journal applicatif : fichier persistant avec rotation,
en plus de la sortie standard (déjà captée par la fenêtre graphique et
visible dans un terminal, mais perdue à la fermeture de l'appli -- voir
fletchtime.gui._QueueWriter). Utile pour comprendre après coup ce qui
s'est passé pendant un concours (quelles commandes reçues, pertes de
connexion, erreurs...) sans dépendre de cette mémoire volatile.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 1 Mo par fichier, 5 fichiers conservés (dont le courant) -- quelques
# concours de suite avant qu'un fichier ne soit écrasé, sans grossir
# indéfiniment sur un usage au long cours.
MAX_BYTES = 1_000_000
BACKUP_COUNT = 5


def configure_logging(
    log_dir: Path, console_level: int = logging.WARNING, file_level: int = logging.INFO
) -> Path:
    """Idempotent -- rappelable sans dupliquer les handlers si déjà
    configuré (utile si un test ou un rechargement appelle ceci plusieurs
    fois dans le même processus). Retourne le chemin du fichier de
    journal, pour affichage à l'utilisateur si besoin.

    ``console_level``/``file_level`` indépendants l'un de l'autre : par
    défaut, le fichier reste toujours à INFO (diagnostic après-coup
    fiable, voir docstring du module) même si le terminal reste
    silencieux (WARNING par défaut). Voir ``fletchtime.__main__``,
    options ``-v``/``--verbose`` (INFO sur le terminal) et
    ``-d``/``--debug`` (DEBUG partout, fichier compris).
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "fletchtime.log"

    logger = logging.getLogger("fletchtime")
    # Le logger lui-même laisse tout passer (DEBUG) -- c'est à chaque
    # handler de filtrer selon son propre niveau, pas au logger de le
    # faire en amont (sinon impossible d'avoir un fichier plus détaillé
    # que le terminal, ou l'inverse).
    logger.setLevel(logging.DEBUG)

    already_has_file_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
    )
    if not already_has_file_handler:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # La sortie standard (stdout) est déjà affichée dans un terminal ou
        # captée par la fenêtre graphique (voir fletchtime.gui) -- ce
        # handler-ci fait en sorte que les logs applicatifs y apparaissent
        # aussi, avec les mêmes horodatages/niveaux que dans le fichier.
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(console_level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    else:
        # Rappel avec des niveaux différents (ex. --debug après un
        # premier appel par défaut) -- met à jour les handlers existants
        # au lieu de rester bloqué sur les niveaux du tout premier appel.
        for handler in logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                handler.setLevel(file_level)
            elif isinstance(handler, logging.StreamHandler):
                handler.setLevel(console_level)

    return log_file
