# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

project = "FletchTime"
copyright = "2026, [Nom du club]"
author = "[Nom du club]"
release = "0.1.1"

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
