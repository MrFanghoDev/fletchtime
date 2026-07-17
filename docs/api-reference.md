# Référence de l'API Python

```{note}
Cette page est générée automatiquement à partir des docstrings du code
source (`sphinx.ext.autodoc`) -- elle reflète toujours le code réel, jamais
en retard sur une doc écrite à la main. Pour une vue d'ensemble plus
narrative de l'architecture, voir {doc}`architecture`.
```

## `fletchtime.engine` -- moteur de séquencement

Pur Python, aucune dépendance -- voir {doc}`dev-guide/index` pour comment y
ajouter un nouveau mode de tir.

::::{tab-set}

:::{tab-item} Modèle d'état
```{eval-rst}
.. automodule:: fletchtime.engine.models
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Séquence (Step)
```{eval-rst}
.. automodule:: fletchtime.engine.sequence
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Moteur (MatchEngine)
```{eval-rst}
.. automodule:: fletchtime.engine.engine
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Modes de tir
```{eval-rst}
.. automodule:: fletchtime.engine.modes.base
   :members:
   :show-inheritance:

.. automodule:: fletchtime.engine.modes.indoor
   :members:
   :show-inheritance:

.. automodule:: fletchtime.engine.modes.flint
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Ordre des relais
```{eval-rst}
.. automodule:: fletchtime.engine.turn_modes
   :members:
   :show-inheritance:
```
:::

::::

## `fletchtime.server` -- serveur temps réel

Construit par-dessus le moteur sans jamais le modifier -- voir
{doc}`architecture` pour le modèle de communication (HTTP + WebSocket sur
deux ports séparés).

::::{tab-set}

:::{tab-item} État du match (MatchServer)
```{eval-rst}
.. automodule:: fletchtime.server.match_server
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Configuration (TOML)
```{eval-rst}
.. automodule:: fletchtime.server.config_store
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Serveur WebSocket
```{eval-rst}
.. automodule:: fletchtime.server.ws_server
   :members:
   :show-inheritance:
```
:::

:::{tab-item} Serveur HTTP statique
```{eval-rst}
.. automodule:: fletchtime.server.http_static
   :members:
   :show-inheritance:
```
:::

::::
