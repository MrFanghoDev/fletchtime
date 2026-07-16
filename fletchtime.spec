# Spec PyInstaller pour FletchTime -- exécutable autoporteur.
#
# Construction locale :
#   pip install pyinstaller websockets
#   pyinstaller fletchtime.spec
#
# Produit dist/FletchTime/ (mode --onedir : un dossier, pas un seul .exe) --
# démarrage quasi instantané, et surtout web/ et config/ restent des
# fichiers normaux, éditables à côté de l'exécutable (logo du club, packs
# de sons, réglages TOML...), pas enfouis dans une archive à extraire à
# chaque lancement comme le ferait --onefile.
#
# Les données propres à un club (logo, bannières, cibles, sons) ne sont PAS
# embarquées ici : elles sont bootstrapées au premier lancement, exactement
# comme pour une installation pip -- voir fletchtime.__main__.
#
# Le résultat est spécifique à l'OS sur lequel tourne PyInstaller : lancer
# ce spec sous Windows produit un .exe Windows, sous Linux un binaire Linux
# -- voir .github/workflows/release.yml qui construit les deux séparément
# via les runners windows-latest/ubuntu-latest de GitHub Actions.

from pathlib import Path

project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "src" / "fletchtime" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "src" / "fletchtime" / "web"), "web"),
        (str(project_root / "config"), "config"),
    ],
    hiddenimports=["websockets"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FletchTime",
    debug=False,
    console=True,  # fenêtre console visible -- affiche l'adresse IP à ouvrir
    upx=False,
    # Depuis PyInstaller 6.0, un build --onedir place par défaut tout son
    # contenu (hors l'exécutable lui-même) dans un sous-dossier _internal/,
    # au lieu de le mettre directement à côté de l'exe comme avant. Notre
    # code (fletchtime.__main__._app_web_dir, ensure_directories) suppose
    # le layout historique (web/ et config/ directement à côté de l'exe) --
    # sans ce paramètre, le serveur ne trouve pas les pages de l'appli une
    # fois empaqueté et ne sert que ce qu'il a lui-même créé (le dossier
    # assets/ du bootstrap), d'où un serveur qui tourne mais ne sert rien
    # d'utile. "." restaure explicitement l'ancien comportement.
    contents_directory=".",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FletchTime",
)
