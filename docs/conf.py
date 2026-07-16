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

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx.ext.autosectionlabel",
]

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
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "fr"

# -- Options for HTML output --------------------------------------------------

html_theme = "furo"  # thème moderne, responsive, lisible sur mobile
html_static_path = ["_static"]
html_title = "FletchTime — Documentation"
html_logo = "_static/logo.svg"
html_favicon = "_static/logo.svg"
