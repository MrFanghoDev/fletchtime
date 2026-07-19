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


def configure_logging(log_dir: Path) -> Path:
    """Idempotent -- rappelable sans dupliquer les handlers si déjà
    configuré (utile si un test ou un rechargement appelle ceci plusieurs
    fois dans le même processus). Retourne le chemin du fichier de
    journal, pour affichage à l'utilisateur si besoin."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "fletchtime.log"

    logger = logging.getLogger("fletchtime")
    logger.setLevel(logging.INFO)

    already_has_file_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
    )
    if not already_has_file_handler:
        formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # La sortie standard (stdout) est déjà affichée dans un terminal ou
        # captée par la fenêtre graphique (voir fletchtime.gui) -- ce
        # handler-ci fait en sorte que les logs applicatifs y apparaissent
        # aussi, avec les mêmes horodatages/niveaux que dans le fichier.
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return log_file
