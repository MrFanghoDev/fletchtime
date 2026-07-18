# Guide développeur

Ce guide vise à permettre à d'autres développeurs (ou la FFTL) de contribuer
au projet sans devoir relire tout le code.

## Installation de l'environnement de développement

FletchTime n'a qu'une seule dépendance externe (`websockets`) ; tout le reste
est stdlib Python 3.10+ (Python 3.11+ pour `config_store.py`, qui utilise
`tomllib`).

```bash
git clone https://github.com/MrFanghoDev/fletchtime.git
cd fletchtime
pip install websockets          # seule dépendance de runtime
pip install -e ".[docs]"        # optionnel, pour construire cette doc
```

Aucun environnement virtuel n'est strictement nécessaire (le projet est
volontairement minimal en dépendances, y compris pour rester installable
depuis Pydroid 3 sur Android -- voir *Choix historiques* plus bas), mais rien
n'empêche d'en utiliser un si tu préfères isoler ton installation.

## Lancer les tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

ou, de façon équivalente et sans variable d'environnement à poser (pensé
pour tourner directement depuis Pydroid) :

```bash
python3 run_tests.py
```

Tous les tests sont en `unittest` (stdlib), aucune dépendance de test à
installer. Le paquet `websockets` n'est pas nécessaire pour lancer les
tests : la logique serveur (`fletchtime.server.match_server`) est testée via
un faux client WebSocket (`FakeWebSocket` dans `tests/test_match_server.py`),
justement pour rester testable dans un environnement qui n'a pas accès au
réseau.

## Gestion de version (automatique depuis les tags git)

Aucune ligne `version = "..."` à maintenir dans `pyproject.toml` : la version
est dérivée automatiquement du tag git le plus proche par
[`setuptools_scm`](https://github.com/pypa/setuptools_scm) (voir la section
`[tool.setuptools_scm]` de `pyproject.toml`).

- Sur un commit qui correspond exactement à un tag (`v0.1.2`) : version
  `0.1.2`.
- Sur un commit quelconque entre deux tags : version de développement
  conforme PEP 440 incluant le nombre de commits depuis le dernier tag
  (ex. `0.1.3.dev4`) -- jamais en conflit avec une version déjà
  publiée sur PyPI/TestPyPI, sans bricolage manuel.

**Pour publier une nouvelle version** : il suffit de taguer et pousser --
```bash
git tag v0.1.3
git push --tags
```
`release.yml` et `pypi.yml` s'occupent du reste (voir `README.md`, section
"Publication").

**Piège à connaître** : `setuptools_scm` a besoin de l'historique complet du
dépôt (tags compris) pour fonctionner -- un clone superficiel
(`actions/checkout` sans `fetch-depth: 0`) ne verrait aucun tag et
produirait une version de secours (`0.0.0`, voir `fallback_version` dans
`pyproject.toml`). Tous les workflows qui construisent le paquet
(`docs.yml`, `pypi.yml`, `release.yml`, `testpypi.yml`) ont donc
`fetch-depth: 0` sur leur étape de checkout -- à ne pas retirer en pensant
que c'est superflu.

**Deux autres pièges rencontrés en pratique** (version affichée restée
sur "dev" après une vraie release, aussi bien dans le terminal du serveur
que dans la doc publiée) :

- **`release.yml` (exécutables PyInstaller)** : PyInstaller lit les
  sources directement via `pathex`, sans jamais "construire" le paquet --
  `setuptools_scm` ne se déclenche donc que si on installe explicitement
  le paquet (`pip install -e .`) *avant* `pyinstaller fletchtime.spec`,
  puisque c'est cette installation qui génère
  `src/fletchtime/_version.py` (voir `pyproject.toml`, `write_to`) que
  `fletchtime.__version__` lit ensuite. Sans cette étape, le fichier
  n'existe jamais et `fletchtime.__version__` retombe sur `"dev"` --
  même sur un vrai tag de release.
- **`docs.yml` (doc publiée sur GitHub Pages)** : ne se déclenchait qu'au
  push d'une branche (`branches: [main, master]`), jamais au push d'un
  tag -- taguer une release ne redéclenchait donc jamais ce workflow, et
  la doc publiée restait bloquée sur la version de développement du
  dernier push de branche. Ajout de `tags: ["v*.*.*"]` au déclencheur.
  Les filtres `paths` de ce même workflow ne s'appliquent de toute façon
  jamais aux push de tags (comportement documenté par GitHub) : un tag
  reconstruit donc toujours la doc, peu importe si `docs/`/`src/` ont
  changé depuis -- exactement ce qu'on veut ici.

## Architecture générale

Voir {doc}`../architecture` pour le détail complet. En résumé :

- `src/fletchtime/engine/` : le moteur de séquencement, pur Python, aucune
  dépendance. C'est la partie la plus testée et la plus stable du projet.
  Publiable seul (`from fletchtime.engine import ...`) sans le reste.
- `src/fletchtime/server/` : le serveur (WebSocket + HTTP statique + config
  TOML), construit par-dessus le moteur sans jamais le modifier.
- `src/fletchtime/web/` : les pages HTML/CSS/JS de l'application
  elles-mêmes (control.html, display.html...), incluses dans le paquet
  installé comme *package data* -- servies en lecture seule, jamais
  modifiées par un club.
- `src/fletchtime/__main__.py` : point d'entrée (`python -m fletchtime`),
  résout où vivent les pages de l'appli (dans le paquet) et où vivent les
  données du club (répertoire courant, ou à côté de l'exécutable si
  PyInstaller) -- voir sa docstring pour le détail de cette distinction.
- `web/assets/` (à la racine du dépôt, **pas** dans `src/`) : les données
  propres à un club (logo, bannières, images de cible, packs de sons) --
  doivent rester modifiables, jamais embarquées dans le paquet lui-même.
- `config/` : fichiers TOML lus/écrits par `config_store.py`, même logique
  que `web/assets/` (répertoire courant, pas dans le paquet).
- `docs/` : cette documentation (Sphinx + MyST).

## Comment ajouter un nouveau mode de tir (`ShootingMode`)

1. Crée `src/fletchtime/engine/modes/ton_mode.py`, avec une classe qui hérite
   de `ShootingMode` (voir `modes/base.py`) et implémente
   `build_sequence() -> List[Step]`. Regarde `indoor.py`/`flint.py` comme
   modèles -- la logique de ton mode n'a besoin de rien connaître du réseau,
   du serveur, ni de l'affichage : elle ne fait que décrire, à l'avance, la
   liste ordonnée des `Step` (phases temporisées) du match.
2. Ajoute un dataclass de config (ex. `TonModeConfig`) avec `__post_init__`
   qui valide les valeurs (voir les validations existantes dans
   `IndoorConfig`/`FlintConfig` comme exemples : cohérence des durées, des
   listes de distances, etc.).
3. Écris les tests dans `tests/test_ton_mode.py` : ce sont des tests sur la
   liste de `Step` produite par `build_sequence()`, pas besoin de faire
   tourner de minuteur ni de serveur pour ça (voir `test_indoor_mode.py`,
   `test_flint_mode.py`).
4. Câble ton mode dans `src/fletchtime/server/match_server.py` (actions
   `start_<ton_mode>` dans `handle_command`, plus `load_<ton_mode>_config`/
   `save_<ton_mode>_config` dans `config_store.py` si tu veux qu'il soit
   configurable via `config.html`).
5. Ajoute les boutons/champs correspondants dans `src/fletchtime/web/control.html`
   et `src/fletchtime/web/config.html`.

**Pièges à éviter** :
- Ne mets aucun état mutable dans la classe `ShootingMode` elle-même --
  `build_sequence()` doit être une fonction pure, appelée une seule fois.
  Tout l'état vivant (position courante, pause, urgence) appartient à
  `MatchEngine`, qui rejoue la séquence produite.
- Un `Step` avec `duration=None` signifie "attente indéfinie" (utilisé pour
  la pause de fin de volée) -- l'engine ne décompte jamais ce genre de step,
  seul un `next()` manuel du responsable du chronométrage le fait avancer.
- Si ton mode a besoin d'un seuil d'alerte (orange) qui ne redémarre pas le
  décompte, utilise `orange_threshold`/`orange_sound_event` sur le `Step`
  plutôt que de créer un step séparé (voir `engine.py`,
  `_maybe_emit_orange_threshold_event`).

## Conventions de code

- Pas de dépendance ajoutée à la légère : toute nouvelle dépendance doit
  fonctionner de façon fiable sur Pydroid 3 (Android). En cas de doute,
  privilégier la stdlib ou un fallback pur Python.
- Docstrings en anglais dans le code (`src/`), commentaires utilisateur
  (fichiers TOML, README destinés au club) en français.
- Un test qui échoue avant livraison n'est pas un problème -- c'est le
  système qui fonctionne. Ne pas contourner un test qui échoue sans
  comprendre pourquoi.

## Process de contribution

Projet encore jeune, pas de process lourd : ouvre une issue ou une PR sur
[GitHub](https://github.com/MrFanghoDev/fletchtime). Merci d'inclure des
tests pour tout changement de comportement dans `src/`.

## Choix historiques et alternatives écartées

- **Pourquoi pas un fork d'ArcheryClock ?** Le code source réel (Pascal,
  ~12 000 lignes dans un seul fichier, dispatch par chaînes de caractères
  scattered dans des dizaines d'endroits) rendait l'ajout d'un mode Flint
  risqué et difficile à maintenir. Repartir de zéro en Python a permis une
  architecture plus modulaire (un mode = une classe) dès le départ.
- **Pourquoi Pydroid 3 / développement mobile-only ?** Contrainte réelle du
  club : pas de PC disponible. Toutes les décisions de dépendances
  (`websockets` plutôt que FastAPI/uvicorn, `tomllib` stdlib plutôt que
  PyYAML) découlent de cette contrainte.
- **Pourquoi TOML plutôt que JSON/YAML pour la config ?** `tomllib` est dans
  la stdlib depuis Python 3.11 (donc disponible sur Pydroid sans rien
  installer) ; TOML est aussi plus lisible qu'un JSON pour un bénévole non
  développeur qui irait éditer le fichier à la main.
- **Pourquoi pas de formulaire d'upload pour le logo/bannières/sons ?**
  Simplicité : le dépôt de fichier dans un dossier + découverte automatique
  par listing de répertoire HTTP évite de construire et maintenir un
  formulaire d'upload, sans perdre en fonctionnalité pour l'usage réel du
  club.

```{warning}
**Piège PyInstaller 6.0+** : depuis cette version, un build `--onedir`
place par défaut tout son contenu (hors l'exécutable) dans un sous-dossier
`_internal/`, plutôt que directement à côté de l'exe comme avant. Notre
code (`fletchtime.__main__._app_web_dir`) suppose l'ancien layout plat --
`fletchtime.spec` restaure ce comportement via `contents_directory="."`
sur l'appel à `EXE(...)`. Si ce paramètre disparaît un jour d'une
réécriture du spec, le symptôme est trompeur : le serveur démarre, la
console affiche l'adresse normalement, mais naviguer vers cette adresse
n'affiche qu'un listing de répertoire avec juste `assets/` dedans (le
dossier bootstrapé), sans les pages de l'appli -- **et ça touche même
127.0.0.1 sur la machine qui héberge le serveur**, donc ce n'est pas un
problème de pare-feu/réseau si ce symptôme précis apparaît.
```

```{warning}
**Piège PyInstaller + `customtkinter`** : cette bibliothèque embarque ses
thèmes (`.json`) et polices (`.otf`) comme données de paquet, que
PyInstaller ne détecte pas automatiquement (piège documenté par le projet
customtkinter lui-même). `fletchtime.spec` les inclut explicitement via
`collect_data_files("customtkinter")` -- sans ça, l'exécutable construit
plante au lancement de la fenêtre (thème introuvable), même si la
construction elle-même s'est terminée sans erreur apparente.
```

```{warning}
**Piège PyInstaller + modules internes du paquet** : constaté sur un vrai
build macOS -- `ModuleNotFoundError: No module named 'fletchtime.runtime'`
au lancement, alors que ce module est importé sans condition en tête de
`fletchtime/__main__.py`. Deux tentatives via `collect_submodules` (avec
puis sans `sys.path.insert` préalable) n'ont pas réglé le problème : le
journal de build complet d'un vrai run ne montrait qu'une seule ligne
`Analyzing hidden import` pour l'un de nos modules
(`fletchtime.web` -- via un mécanisme différent, sans lien avec
`collect_submodules`), jamais pour `fletchtime.runtime` ni les autres --
signe que la découverte dynamique ne fonctionnait pas comme attendu dans
cet environnement précis, pour une raison qui reste floue.

`fletchtime.spec` liste désormais chaque sous-module explicitement, en
dur, dans `hiddenimports` -- plus rien laissé à un mécanisme de
découverte dynamique. Liste vérifiée en énumérant réellement le paquet
(`pkgutil.walk_packages`) : 17 modules, correspondance exacte confirmée.
**À tenir à jour si de nouveaux modules sont ajoutés à `src/fletchtime/`**
-- un module ajouté sans être ajouté à cette liste reproduirait
exactement ce bug.

**Pourquoi c'est plus grave qu'il n'y paraît** : ce même problème,
survenant sur `fletchtime.gui` plutôt que `fletchtime.runtime`, échouerait
**silencieusement** -- `fletchtime.gui` est importé dans un `try/except`
(voir `main()`), donc son absence retomberait sur le mode terminal sans
aucune erreur visible, sur toutes les plateformes, sans que personne ne
s'en aperçoive avant qu'un utilisateur signale que la fenêtre ne s'ouvre
jamais.

**Pour déboguer ce genre de souci sans attendre une vraie release** :
`release.yml` construit désormais aussi les exécutables sur chaque push
touchant à l'empaquetage (`src/`, `fletchtime.spec`, `pyproject.toml`),
sans publier de Release -- artefacts téléchargeables directement depuis
la page du run (section "Artifacts"). `fail-fast: false` sur la matrice
évite qu'un échec sur une plateforme n'annule les autres, pour pouvoir
comparer leurs résultats.
```

```{warning}
**Ne pas écrire un thème `customtkinter` entièrement personnalisé (JSON
maison).** Tenté une première fois pour reprendre la palette de marque de
l'appli -- a cassé la construction de la fenêtre en conditions réelles
(`KeyError: 'corner_radius'`) car le fichier fait à la main oubliait une
clé interne attendue par la version de `customtkinter` installée. Le
schéma exact de ces fichiers n'est pas garanti stable d'une version à
l'autre et est difficile à valider sans lancer réellement la fenêtre (pas
possible dans l'environnement où ce module est habituellement modifié,
voir plus bas). À la place, `fletchtime.gui._apply_brand_colors` part d'un
thème **intégré** ("dark-blue", garanti complet) et ne surcharge que les
valeurs de couleur déjà présentes -- jamais de clé nouvelle -- le tout
protégé par un `try/except` : en cas d'incompatibilité future, l'appli
retombe sur le thème intégré tel quel plutôt que de planter.
```

```{note}
**Fenêtre graphique et tests** : `fletchtime.gui` n'a pas pu être testé
visuellement (aucun affichage graphique disponible dans l'environnement où
ce module a été écrit). Ce qui est testé pour de vrai, c'est la logique
qu'elle pilote : `fletchtime.runtime.ServerRuntime` (voir
`tests/test_runtime.py` -- démarrage, requête HTTP réelle, arrêt propre,
port libéré, redémarrage). Si tu modifies `fletchtime/gui.py`, un
lancement réel sur PC (et si possible sur Pydroid) reste nécessaire avant
de considérer le changement fiable -- l'exécution de `ci.yml` ne le
détecterait pas (ni GitHub Actions, dont les runners n'ont pas
d'affichage graphique, ce qui est justement pourquoi `main()` propose un
mode `--headless`, utilisé par les tests de fumée de `release.yml`).

**Confirmé en conditions réelles** : Pydroid 3 refuse catégoriquement
d'ouvrir une fenêtre Tk quand le script est lancé depuis son **Terminal**
("GUI applications cannot be ran from terminal... Use IDE to run these
applications") -- l'échec se produit à la construction de `CTk()`
elle-même (`AttributeError` sur `createcommand`), pas à l'import de
`customtkinter`. `main()` intercepte donc une exception large (pas
seulement `ImportError`) autour de tout `run_gui()`, et
`fletchtime.gui.run_gui` arrête proprement tout serveur déjà démarré avant
de la laisser remonter -- sans ça, le repli en mode terminal se heurterait
à un port déjà occupé. Sur Pydroid, seul le bouton ▶️ Run de l'éditeur
(pas le Terminal) permet réellement d'ouvrir la fenêtre graphique.
```

```{note}
**macOS -- jamais vérifié sur une vraie machine**, contrairement à
Windows et Linux dont les problèmes réels remontés ont pu être corrigés
et re-testés. `macos-latest` est dans la matrice de `release.yml` (test
de fumée `--headless` uniquement -- confirme le démarrage du serveur,
pas le rendu de la fenêtre) depuis que ce point a été soulevé, mais
plusieurs limites connues restent non résolues faute de machine
disponible pour les traiter :

- `fletchtime.spec` ne définit pas de cible `BUNDLE()` -- sans elle,
  PyInstaller produit un simple dossier avec un exécutable dedans (comme
  pour Linux), pas une vraie `.app` cliquable avec icône dans le Dock/
  Applications. Fonctionnerait techniquement, mais pas une expérience
  aussi soignée que sur Windows/Linux.
- Gatekeeper (faute de certificat développeur Apple et de notarisation,
  ni l'un ni l'autre en place ici) bloquera plus agressivement qu'un
  simple SmartScreen Windows -- passage par *Réglages Système →
  Confidentialité et sécurité → Ouvrir quand même* à prévoir dans la doc
  utilisateur le jour où ce point sera traité.
- Le runner `macos-latest` de GitHub Actions produit un binaire Apple
  Silicon (ARM64) -- un Mac Intel pourrait nécessiter Rosetta 2 ou un
  build séparé (`macos-13` reste en Intel au moment où ceci est écrit,
  à vérifier sur la page officielle des runners GitHub le cas échéant).

**Décision délibérée, pas un oubli** : ne pas construire d'artefact séparé
par architecture (Windows/Linux ARM64, macOS Intel) tant qu'aucun
utilisateur réel n'en a exprimé le besoin. Windows/Linux x86_64 couvrent
l'écrasante majorité des PC de club ; Windows sait émuler x86_64 sur
ARM64 nativement ; un besoin Linux ARM (ex. Raspberry Pi) passerait de
toute façon plus naturellement par `pip install fletchtime` (fonctionne
sur n'importe quelle architecture) que par un exécutable PyInstaller
dédié. Pour macOS, doubler la matrice (Intel + Apple Silicon) sans
utilisateur Mac avéré ajouterait de la complexité CI pour un besoin
encore hypothétique -- à reconsidérer si un vrai retour utilisateur le
justifie.
```

```{note}
La publication automatique de cette doc sur GitHub Pages est déjà en place
(`.github/workflows/docs.yml`) -- voir le README à la racine du dépôt pour
l'activer (une seule fois, côté réglages GitHub).
```
