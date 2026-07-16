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
        (str(project_root / "web" / "assets"), "web/assets"),
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FletchTime",
)
