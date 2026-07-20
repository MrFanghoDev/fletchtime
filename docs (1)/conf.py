# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

project = "FletchTime"
copyright = "2026, [Nom du club]"
author = "[Nom du club]"
try:
    # Version dérivée du tag git via setuptools_scm (voir pyproject.toml) --
    # lue depuis le paquet installé, jamais codée en dur ici. Nécessite que
    # `pip install -e .` (ou équivalent) ait été fait avant de construire
    # cette doc, ce que fait déjà .github/workflows/docs.yml.
    release = _pkg_version("fletchtime")
except PackageNotFoundError:
    release = "dev"
version = release  # les deux valeurs Sphinx standard, identiques ici par simplicité

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autodoc",       # documentation de l'API Python interne
    "sphinx.ext.napoleon",      # comprend les docstrings de style Google/NumPy
    "sphinx.ext.viewcode",      # lien "voir le code source" sur chaque objet documenté
    "sphinxcontrib.mermaid",    # diagrammes ```mermaid dans les fichiers .md
    "sphinx_design",            # cartes/grilles/onglets pour aérer la mise en page
]

# -- Documentation de l'API Python (autodoc) ----------------------------------
# Nécessite que le paquet fletchtime soit installé (pip install -e .) avant
# de construire la doc -- déjà fait par .github/workflows/docs.yml.
autodoc_member_order = "bysource"  # ordre du fichier source, pas alphabétique
autodoc_typehints = "description"  # affiche les annotations de type dans la description, pas la signature
napoleon_google_docstring = True
napoleon_numpy_docstring = False

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",      # blocs ::: pour les admonitions (note, warning, etc.)
    "deflist",
    "fieldlist",
    "attrs_inline",
    "tasklist",
    "substitution",     # active {{ version }} etc. dans les fichiers .md
]

myst_substitutions = {"version": release}

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "fr"

# -- Options for HTML output --------------------------------------------------

html_theme = "furo"  # thème moderne, responsive, lisible sur mobile
html_static_path = ["_static"]
html_title = f"FletchTime {release} — Documentation"
html_logo = "_static/logo.svg"
html_favicon = "_static/logo.svg"
