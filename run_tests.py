"""Lance toute la suite de tests, pensé pour Pydroid 3 (ou tout IDE mobile) :
pas besoin de terminal ni de variable d'environnement PYTHONPATH, juste
ouvrir ce fichier et appuyer sur "Run".

Sur PC, `PYTHONPATH=src python3 -m unittest discover -s tests -v` fait
exactement la même chose -- ce script existe uniquement pour l'usage mobile.
"""

import sys
import unittest
from pathlib import Path

# Ajoute src/ au chemin d'import, où que se trouve ce fichier sur le
# téléphone (pas besoin de PYTHONPATH).
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(str(PROJECT_ROOT / "tests"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print(f"OK -- {result.testsRun} tests passés.")
    else:
        print(
            f"ÉCHEC -- {len(result.failures)} échec(s), "
            f"{len(result.errors)} erreur(s) sur {result.testsRun} tests."
        )
