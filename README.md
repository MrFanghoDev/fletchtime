<img src="web/logo.svg" width="80" height="80" alt="FletchTime logo">

# FletchTime

Logiciel open source de gestion du temps pour compétitions d'archerie FFTL
(Indoor et Flint), pensé pour être simple à déployer sur un réseau local
multi-écrans et à paramétrer sans compétences techniques.

## Documentation

La documentation complète (specs, architecture, plan de dev, manuels) est dans
`docs/`, construite avec Sphinx + MyST.

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
```

Ouvrir ensuite `docs/_build/html/index.html` dans un navigateur.

## État du projet

Étapes 1 et 2 terminées (moteur de séquencement, serveur temps réel), étapes 3
et 4 en cours (affichage, interface de contrôle) — voir `docs/roadmap.md` pour
le détail du plan de développement par étapes.
