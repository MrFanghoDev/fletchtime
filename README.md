<img src="src/fletchtime/web/logo.svg" width="80" height="80" alt="FletchTime logo">

# FletchTime

Logiciel open source de gestion du temps pour compétitions d'archerie FFTL
(Indoor et Flint), pensé pour être simple à déployer sur un réseau local
multi-écrans et à paramétrer sans compétences techniques.

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

Télécharge `FletchTime-windows.zip` ou `FletchTime-linux.tar.gz` depuis les
[Releases GitHub](https://github.com/MrFanghoDev/fletchtime/releases),
décompresse, lance `FletchTime.exe` (Windows) ou `./FletchTime` (Linux).
Aucune installation de Python nécessaire. Les dossiers `web/assets/...` et
`config/` sont créés automatiquement à côté de l'exécutable au premier
lancement s'ils manquent.

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

## Publication (pour les mainteneurs)

- **PyPI** (`pip install fletchtime`) : publication automatique via
  `.github/workflows/pypi.yml` (Trusted Publishing OIDC, sans jeton API) à
  chaque Release GitHub. Configuration ponctuelle nécessaire sur
  [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)
  -- voir les commentaires du fichier de workflow.
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
