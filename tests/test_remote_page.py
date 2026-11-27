"""Garde-fous statiques sur la page télécommande (web/remote.html).

La page elle-même se vérifie avec un vrai navigateur (voir CLAUDE.md :
rendu réel, pas relecture) ; ces tests-ci attrapent seulement les dérives
bêtes qu'aucun rendu ne montre tout de suite : une action que le serveur ne
protège pas par mot de passe, une clé de traduction absente d'une langue.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from fletchtime.server.match_server import PROTECTED_ACTIONS

DOSSIER_WEB = Path(__file__).resolve().parent.parent / "src" / "fletchtime" / "web"
REMOTE = (DOSSIER_WEB / "remote.html").read_text(encoding="utf-8")
CONTROL = (DOSSIER_WEB / "control.html").read_text(encoding="utf-8")
I18N = (DOSSIER_WEB / "i18n.js").read_text(encoding="utf-8")

# Les huit commandes de la télécommande -- et rien d'autre : pas de goto,
# pas de message, pas de réglage (c'est le rôle du poste de contrôle).
ACTIONS_ATTENDUES = {
    "start_indoor",
    "start_flint",
    "next",
    "pause",
    "play",
    "stop",
    "emergency",
    "resume",
}


def _cles_par_langue() -> dict[str, set[str]]:
    debut_en = I18N.index("\n  en: {")
    blocs = {"fr": I18N[:debut_en], "en": I18N[debut_en:]}
    return {langue: set(re.findall(r"^\s{4}(\w+):", bloc, re.M)) for langue, bloc in blocs.items()}


class TestPageTelecommande(unittest.TestCase):
    def test_envoie_exactement_les_huit_commandes_prevues(self) -> None:
        envoyees = set(re.findall(r"press\(\{action:\s*'(\w+)'\}\)", REMOTE))
        self.assertEqual(envoyees, ACTIONS_ATTENDUES)

    def test_toutes_ses_commandes_sont_protegees_par_mot_de_passe(self) -> None:
        # Une commande absente de PROTECTED_ACTIONS serait exécutée sans
        # authentification même quand un mot de passe est configuré.
        self.assertEqual(ACTIONS_ATTENDUES - PROTECTED_ACTIONS, set())

    def test_chaque_bouton_a_sa_place_dans_le_pave(self) -> None:
        for identifiant in (
            "start-indoor-btn",
            "start-flint-btn",
            "next-btn",
            "pause-btn",
            "play-btn",
            "stop-btn",
            "emergency-btn",
            "resume-btn",
        ):
            self.assertIn(f'id="{identifiant}"', REMOTE)
            self.assertRegex(REMOTE, rf"#{identifiant}\s*\{{\s*grid-area:")

    def test_les_cles_de_traduction_utilisees_existent_en_fr_et_en(self) -> None:
        utilisees = set(re.findall(r'data-i18n(?:-placeholder)?="(\w+)"', REMOTE))
        utilisees |= set(re.findall(r't\(currentLanguage,\s*"(\w+)"\)', REMOTE))
        utilisees |= set(re.findall(r'"(remotePhase\w+)"', REMOTE))
        self.assertTrue(utilisees)
        cles = _cles_par_langue()
        for langue, definies in cles.items():
            self.assertEqual(
                sorted(utilisees - definies), [], f"clés absentes de la langue {langue!r}"
            )

    def test_le_panneau_de_controle_renvoie_vers_la_telecommande(self) -> None:
        self.assertIn('href="remote.html"', CONTROL)
        self.assertIn('data-i18n="remoteLink"', CONTROL)

    def test_pas_de_navigation_parasite_sur_la_telecommande(self) -> None:
        # Un lien vers l'extérieur (pied de page, GitHub...) sur une page
        # tout écran faite pour être tapée sans regarder est un piège :
        # seul le retour vers le poste de contrôle doit y figurer.
        liens = re.findall(r'<a\s[^>]*href="([^"]+)"', REMOTE)
        self.assertEqual(liens, ["control.html"])


if __name__ == "__main__":
    unittest.main()
