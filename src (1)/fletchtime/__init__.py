"""FletchTime -- chronométrage de compétitions d'archerie FFTL."""

try:
    # Généré par setuptools_scm à la construction (voir pyproject.toml,
    # write_to) -- fonctionne aussi bien pip-installé qu'empaqueté par
    # PyInstaller, contrairement à importlib.metadata qui suppose des
    # métadonnées de paquet correctement préservées.
    from fletchtime._version import __version__
except ImportError:
    # Checkout source jamais construit/installé (ex. Pydroid avec juste
    # `pip install websockets` + `python run_server.py`, sans jamais faire
    # `pip install -e .`) -- dernier repli, sans faire planter l'import.
    try:
        from importlib.metadata import version as _pkg_version

        __version__ = _pkg_version("fletchtime")
    except Exception:
        __version__ = "dev"

__all__ = ["__version__"]
