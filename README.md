<img src="web/logo.svg" width="80" height="80" alt="FletchTime logo">

# FletchTime

Logiciel open source de gestion du temps pour compétitions d'archerie FFTL
(Indoor et Flint), pensé pour être simple à déployer sur un réseau local
multi-écrans et à paramétrer sans compétences techniques.

## Documentation

Il y a **deux documentations distinctes**, pour deux publics différents :

- **Manuel utilisateur** (`web/manual.html`) : pour le DOS et les bénévoles du
  club. Servi localement par FletchTime lui-même (ouvre `manual.html` depuis
  l'accueil de l'application) — fonctionne sans connexion Internet, comme le
  reste de l'outil.
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
