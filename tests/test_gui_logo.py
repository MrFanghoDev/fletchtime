"""Chemin du logo de la GUI -- en source comme empaqueté par PyInstaller.

Régression : en mode gelé (``contents_directory="."`` dans
``fletchtime.spec``), ``Path(__file__).parent / "web"`` pointait vers
``<exe>/fletchtime/web/`` alors que ``web/`` est livré directement à côté
de l'exécutable -- la fenêtre ne s'ouvrait pas (logo introuvable).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

try:
    from fletchtime.gui import chemin_logo
except ImportError:  # customtkinter/PIL absents de cet environnement
    chemin_logo = None


@unittest.skipIf(chemin_logo is None, "fletchtime.gui non importable (customtkinter/PIL absents)")
class TestCheminLogo(unittest.TestCase):
    def test_depuis_les_sources_existe(self) -> None:
        self.assertTrue(chemin_logo().is_file())

    def test_gele_pointe_a_cote_de_l_executable(self) -> None:
        exe = Path("/opt/FletchTime/FletchTime.exe")
        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", str(exe)),
        ):
            self.assertEqual(chemin_logo(), exe.resolve().parent / "web" / "logo.ico")


if __name__ == "__main__":
    unittest.main()
