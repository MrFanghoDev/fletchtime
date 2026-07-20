```{image} _static/logo.svg
:alt: FletchTime
:width: 140px
:align: center
```

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/MrFanghoDev/fletchtime/blob/master/pyproject.toml)
[![Licence](https://img.shields.io/github/license/MrFanghoDev/fletchtime)](https://github.com/MrFanghoDev/fletchtime/blob/master/LICENSE)
[![Tests](https://github.com/MrFanghoDev/fletchtime/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/MrFanghoDev/fletchtime/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/fletchtime)](https://pypi.org/project/fletchtime/)

# FletchTime

Logiciel de gestion du temps pour compétitions d'archerie FFTL (Indoor et Flint),
open source, développé pour un usage club puis partagé avec la fédération.

Cette documentation couvre le fonctionnement interne de FletchTime :
spécifications fonctionnelles, architecture technique, plan de
développement, guide de contribution, et référence de l'API Python
générée depuis le code. Pour un guide d'utilisation côté club (premier
lancement, configuration d'un concours, pilotage d'un match...), voir le
manuel utilisateur intégré à l'application elle-même (accessible depuis sa
page d'accueil, pas ici) -- voir {doc}`user-guide/index`.

```{toctree}
:hidden:
:maxdepth: 2
:caption: Contenu

specifications
architecture
roadmap
remerciements
user-guide/index
dev-guide/index
api-reference
```

## En bref

::::{grid} 2
:gutter: 3

:::{grid-item-card} 🎛️ Contrôle
Une interface web unique, pilotée depuis un seul appareil (le responsable
du chronométrage).
:::

:::{grid-item-card} 📺 Affichage
Multi-écrans en réseau local, un navigateur suffit sur chaque tablette/PC
de pas de tir.
:::

:::{grid-item-card} 🏹 Modes supportés
Indoor (WA / FFTL), Flint (FFTL), extensible à d'autres -- voir
{doc}`dev-guide/index`.
:::

:::{grid-item-card} 🎯 Objectif
Simple à paramétrer pour un non-développeur, simple à étendre pour un
développeur.
:::

::::

## Liens utiles

- **Code source** : [github.com/MrFanghoDev/fletchtime](https://github.com/MrFanghoDev/fletchtime)
- **Releases** (exécutables Windows/Linux, historique des versions) :
  [github.com/MrFanghoDev/fletchtime/releases](https://github.com/MrFanghoDev/fletchtime/releases)

```{note}
Cette documentation en ligne correspond à la dernière **version publiée**
(dernier tag) -- elle ne se met plus à jour à chaque commit de `main`
(voir {doc}`dev-guide/index` pour pourquoi : GitHub Pages ignore un
second déploiement pour un commit déjà déployé, ce qui posait justement
problème quand la doc se reconstruisait à chaque push). **La
documentation correspondant exactement à une version précédente est
disponible dans chaque Release GitHub**, sous forme d'archive
téléchargeable : ouvre la Release voulue (ex. `v0.1.2`), télécharge
`FletchTime-v0.1.2-docs.tar.gz`, décompresse-la, puis ouvre `index.html`.
```

---

*Version {{ version }}*
