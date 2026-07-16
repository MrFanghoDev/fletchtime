"""Lance le serveur FletchTime : ouvrir ce fichier dans Pydroid et appuyer
sur "Run". Simple raccourci vers `python -m fletchtime` pour qui a juste
cloné le dépôt sans faire `pip install` (cas Pydroid le plus courant) --
voir `src/fletchtime/__main__.py` pour la vraie logique.

Nécessite le paquet `websockets` (pip install websockets -- dans Pydroid :
menu ☰ → Pip → chercher "websockets" → Installer). Aucune autre dépendance.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fletchtime.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
