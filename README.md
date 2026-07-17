<img src="https://mrfanghodev.github.io/fletchtime/_static/logo.svg" width="80" height="80" alt="FletchTime logo">

# FletchTime

Logiciel open source de gestion du temps pour compétitions d'archerie FFTL
(Indoor et Flint), pensé pour être simple à déployer sur un réseau local
multi-écrans et à paramétrer sans compétences techniques.

Se lance avec une fenêtre graphique (démarrage/arrêt du serveur, liens
rapides vers les pages, journal réseau) sur toutes les plateformes, y
compris Pydroid 3. Ajoute `--headless` pour retrouver l'ancien mode
terminal (aussi utilisé automatiquement si la fenêtre ne peut pas se
charger, ex. `customtkinter` absent).

## Installation

Trois façons d'obtenir et faire tourner FletchTime, selon ton matériel --
toutes lancent le **même** serveur complet (contrôle + affichage + tout le
nécessaire), pas juste un morceau :

### 1. `pip install fletchtime` -- Android (Pydroid 3), PC, n'importe où avec Python

```bash
pip install fletchtime    # menu ☰ → Pip → chercher "fletchtime" sur Pydroid
python -m fletchtime       # ou juste : fletchtime
```

Les données propres à ton club (logo, bannières, images de cible, packs de
sons, réglages) se créent automatiquement dans le dossier **depuis lequel tu
lances la commande** au premier démarrage -- lance-la toujours depuis le
même dossier pour retrouver tes réglages d'une fois sur l'autre.

Sans passer par PyPI (depuis un clone du dépôt) :

```bash
git clone https://github.com/MrFanghoDev/fletchtime.git && cd fletchtime
pip install websockets     # ou : pip install -e .
python run_server.py       # raccourci équivalent à `python -m fletchtime`
```

### 2. Exécutable autoporteur (Windows / Linux) -- PC dédié, sans Python

Télécharge `FletchTime-<version>-windows.zip` ou
`FletchTime-<version>-linux.tar.gz` (ex. `FletchTime-v0.1.1-windows.zip`)
depuis les [Releases GitHub](https://github.com/MrFanghoDev/fletchtime/releases),
décompresse, lance `FletchTime.exe` (Windows) ou `./FletchTime` (Linux).
Aucune installation de Python nécessaire. Les dossiers `web/assets/...` et
`config/` sont créés automatiquement à côté de l'exécutable au premier
lancement s'ils manquent.

Chaque Release inclut aussi `FletchTime-<version>-docs.tar.gz` : la
documentation technique (Sphinx) telle qu'elle était pour ce tag précis --
contrairement à la version publiée sur GitHub Pages (toujours celle de
`main`), utile pour consulter la doc correspondant exactement à une
version installée. Décompresse et ouvre `index.html`.

**Windows -- pare-feu** : au premier lancement, Windows affiche une alerte
"Le Pare-feu Windows Defender a bloqué certaines fonctionnalités de cette
application" -- coche au moins **Réseaux privés** puis clique **Autoriser
l'accès**. Sans ça, le serveur démarre normalement et fonctionne depuis
l'appareil qui l'héberge, mais reste **injoignable depuis les autres
appareils** (tablettes/PC de pas de tir) sur le même réseau WiFi. Si
l'alerte a été fermée par erreur ou n'est jamais apparue : *Paramètres
Windows → Confidentialité et sécurité → Pare-feu Windows Defender →
Autoriser une application via le pare-feu* -- coche `FletchTime.exe` pour
les réseaux privés.

**Ports réseau utilisés** : **8000** en HTTP (pages web) et **8765** en
WebSocket (synchronisation temps réel) -- deux ports séparés, tous deux
nécessaires. Si le serveur tourne dans un conteneur/VM (Docker, WSL2...),
les deux doivent être redirigés vers l'hôte, pas seulement le 8000 : sans
le 8765, les pages se chargent normalement mais restent bloquées sur "en
attente de connexion" indéfiniment (la synchronisation temps réel ne peut
jamais s'établir).

Pour construire ces exécutables toi-même (ou ajouter macOS à la matrice) :
voir `.github/workflows/release.yml` et `fletchtime.spec` (PyInstaller). Un
`git tag v0.1.0 && git push --tags` déclenche la construction et publie les
deux archives automatiquement.

### 3. `import fletchtime.engine` -- pour réutiliser juste le moteur de séquencement

Le moteur (`fletchtime.engine`, pur Python, zéro dépendance) est aussi
utilisable seul dans un autre projet, sans le serveur ni les pages web :

```python
from fletchtime.engine import IndoorMode, IndoorConfig, MatchEngine
engine = MatchEngine(IndoorMode(IndoorConfig()))
```

## Qualité continue

Chaque push et pull request déclenche `.github/workflows/ci.yml` :
formatage/lint (Black + Ruff -- corrigés et recommités automatiquement sur
un push direct, juste vérifiés sur une pull request) puis la suite de
tests complète. Aucune dépendance externe nécessaire pour les tests,
`websockets` compris (voir `docs/dev-guide/index.md`).

En local :

```bash
pip install -e ".[dev]"
black src tests demo.py run_server.py run_tests.py
ruff check --fix src tests demo.py run_server.py run_tests.py
python -m unittest discover -s tests -v
```

## Publication (pour les mainteneurs)

- **TestPyPI** (essai avant publication réelle) : publication automatique
  via `.github/workflows/testpypi.yml` à chaque push sur `main`/`master` qui
  touche au code. Génère un numéro de version unique à chaque fois
  (`0.1.0.devN`) pour ne jamais entrer en conflit. Configuration ponctuelle
  sur [test.pypi.org/manage/account/publishing](https://test.pypi.org/manage/account/publishing/)
  -- **compte séparé de pypi.org**, à créer indépendamment sur
  [test.pypi.org](https://test.pypi.org).

  Pour installer une version publiée sur TestPyPI et vérifier qu'elle
  fonctionne avant de publier pour de vrai :

  ```bash
  pip install --index-url https://test.pypi.org/simple/ \
              --extra-index-url https://pypi.org/simple/ \
              fletchtime
  ```

  Le `--extra-index-url` vers le vrai PyPI est nécessaire : TestPyPI ne
  contient que les paquets qu'on y a explicitement publiés, pas leurs
  dépendances (ici, `websockets`) -- sans ça, l'installation échouerait en
  cherchant `websockets` sur TestPyPI où il n'existe pas.

- **PyPI** (`pip install fletchtime`) : publication automatique via
  `.github/workflows/pypi.yml` (Trusted Publishing OIDC, sans jeton API) à
  chaque Release GitHub. Configuration ponctuelle nécessaire sur
  [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)
  -- voir les commentaires du fichier de workflow. À faire une fois que les
  essais sur TestPyPI sont concluants : contrairement à TestPyPI, un numéro
  de version publié sur PyPI ne peut plus jamais être réutilisé ni supprimé.
- **Exécutables** : voir section 2 ci-dessus.

## Documentation

Il y a **deux documentations distinctes**, pour deux publics différents :

- **Manuel utilisateur** (`manual.html`) : pour le DOS et les bénévoles du
  club. Servi localement par FletchTime lui-même (ouvre "Manuel utilisateur"
  depuis la page d'accueil de l'application) — fonctionne sans connexion
  Internet, comme le reste de l'outil.
- **Documentation développeur** (`docs/`, Sphinx + MyST) : specs, architecture,
  plan de développement, guide de contribution. En local :

  ```bash
  pip install -e ".[docs]"      # ou : pip install -r docs/requirements.txt
  sphinx-build -b html docs docs/_build/html
  ```

  Ouvrir ensuite `docs/_build/html/index.html` dans un navigateur.

  Elle est aussi publiée automatiquement sur **GitHub Pages** à chaque push sur
  `main` (voir `.github/workflows/docs.yml`). Configuration à faire une seule
  fois sur GitHub : *Settings → Pages → Source : "GitHub Actions"*.

## État du projet

Étapes 1 à 5 terminées (moteur de séquencement, serveur temps réel, affichage,
interface de contrôle, son) — étape 6 en cours (documentation, packaging). Voir
`docs/roadmap.md` pour le détail du plan de développement par étapes.
