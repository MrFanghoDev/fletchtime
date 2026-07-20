"""Lance le serveur FletchTime : ouvrir ce fichier dans Pydroid et appuyer
sur "Run". Simple raccourci vers `python -m fletchtime` pour qui a juste
cloné le dépôt sans faire `pip install` (cas Pydroid le plus courant) --
voir `src/fletchtime/__main__.py` pour la vraie logique.

Nécessite le paquet `websockets` (pip install websockets -- dans Pydroid :
menu ☰ → Pip → chercher "websockets" → Installer). Aucune autre dépendance.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Fixe explicitement le répertoire de travail à la racine du projet, plutôt
# que de faire confiance au CWD hérité du processus qui a lancé ce script
# -- c'est ce CWD que `fletchtime.__main__._data_root()` utilise pour
# savoir où créer les dossiers propres au club (web/assets/, config/).
# Sur Pydroid, ce CWD ne correspond pas forcément à l'emplacement de ce
# fichier (ex. il peut rester sur le dernier dossier consulté dans
# l'explorateur de fichiers) : sans ce chdir(), les dossiers du club
# pouvaient se retrouver créés n'importe où -- notamment DANS
# src/fletchtime/web/, qui doit pourtant rester le contenu du paquet,
# jamais un dossier de données du club.
os.chdir(PROJECT_ROOT)

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fletchtime.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
