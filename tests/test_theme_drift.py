"""Détection de dérive entre les palettes CSS inline des pages web et la
palette canonique fletchapps/theme.css.

Décision documentée dans le CLAUDE.md global (section "Design partagé
entre GUI/pages web", décision fletchapps#1) : pas de synchronisation
automatique (pas de submodule, pas de paquet partagé) -- juste un test
qui compare les jetons CSS (variables --xxx du bloc :root sombre par
défaut) entre chaque page web de FletchTime et fletchapps/theme.css, et
échoue si l'une d'elles a dérivé sans que l'autre ait été mise à jour.

Contrairement à FletchScore, FletchTime n'a pas de fichier theme.css
dédié -- chaque page (config.html, control.html, index.html,
manual.html) définit son propre bloc ``:root { ... }`` inline dans une
balise ``<style>``. display.html n'en a volontairement aucun (écran
grand format, contraste fort, palette dédiée pour la lisibilité à
distance -- pas le thème clair/sombre de l'appli) : ignoré, pas une
dérive.

Skip silencieusement si fletchapps/theme.css est injoignable (pas
d'accès réseau dans cet environnement, ou hors ligne) -- ce n'est pas
un test métier, juste un garde-fou de cohérence.
"""

from __future__ import annotations

import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path

URL_THEME_CANONIQUE = "https://raw.githubusercontent.com/MrFanghoDev/fletchapps/master/theme.css"
DOSSIER_WEB = Path(__file__).resolve().parent.parent / "src" / "fletchtime" / "web"


def _extraire_jetons_root(contenu_css: str) -> dict[str, str]:
    """Jetons ``--nom: valeur;`` du premier bloc ``:root { ... }`` --
    ignore les blocs ``:root[data-theme=...]`` qui suivent (variantes
    clair/sombre explicites, pas la palette par défaut)."""
    correspondance = re.search(r":root\s*\{([^}]*)\}", contenu_css)
    if not correspondance:
        return {}
    return dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", correspondance.group(1)))


def _theme_canonique_disponible() -> bool:
    try:
        with urllib.request.urlopen(URL_THEME_CANONIQUE, timeout=5):
            return True
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


THEME_CANONIQUE_DISPONIBLE = _theme_canonique_disponible()


@unittest.skipUnless(
    THEME_CANONIQUE_DISPONIBLE,
    "fletchapps/theme.css injoignable dans cet environnement de test (pas de réseau ?)",
)
class TestDeriveThemeCss(unittest.TestCase):
    def test_jetons_partages_identiques_a_fletchapps_par_page(self):
        with urllib.request.urlopen(URL_THEME_CANONIQUE, timeout=5) as reponse:
            contenu_distant = reponse.read().decode("utf-8")
        jetons_distants = _extraire_jetons_root(contenu_distant)
        self.assertTrue(
            jetons_distants, "Aucun jeton trouvé dans fletchapps/theme.css -- format changé ?"
        )

        pages_html = sorted(DOSSIER_WEB.glob("*.html"))
        self.assertTrue(pages_html, f"Aucune page HTML trouvée dans {DOSSIER_WEB}")

        derives_par_page: dict[str, dict[str, tuple[str, str]]] = {}
        pages_avec_jetons = 0

        for page in pages_html:
            jetons_page = _extraire_jetons_root(page.read_text(encoding="utf-8"))
            if not jetons_page:
                # Ex. display.html : pas de bloc :root, palette dédiée
                # écran grand format -- pas une dérive, juste hors sujet.
                continue
            pages_avec_jetons += 1

            jetons_partages = set(jetons_distants) & set(jetons_page)
            derives = {
                nom: (jetons_page[nom], jetons_distants[nom])
                for nom in sorted(jetons_partages)
                if jetons_page[nom] != jetons_distants[nom]
            }
            if derives:
                derives_par_page[page.name] = derives

        self.assertTrue(
            pages_avec_jetons,
            "Aucune page web n'a de bloc :root -- vérifier que l'extraction n'est pas cassée.",
        )
        self.assertFalse(
            derives_par_page,
            "Des pages web ont dérivé de la palette canonique fletchapps/theme.css : "
            + "; ".join(
                f"{page} ("
                + ", ".join(
                    f"{nom} local={local!r} vs fletchapps={distant!r}"
                    for nom, (local, distant) in jetons.items()
                )
                + ")"
                for page, jetons in derives_par_page.items()
            ),
        )
