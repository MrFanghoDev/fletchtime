# Contribuer à FletchTime

*[English version below](#contributing-to-fletchtime)*

Merci de t'intéresser à FletchTime ! C'est un projet né d'un usage de club
(Les Aigles 77 / Archers Libres de Fontaine le Port), publié en open source
sous licence [GPL-3.0-or-later](LICENSE) pour être utile à d'autres clubs et
à la FFTL. On garde le processus de contribution volontairement simple.

## Signaler un bug ou proposer une idée

Passe par les [Issues GitHub](https://github.com/MrFanghoDev/fletchtime/issues) --
pas besoin de formulaire compliqué. Pour un bug, ce qui aide le plus :
- Ce que tu as fait, ce que tu attendais, ce qui s'est passé à la place
- Comment tu as lancé FletchTime (`pip install`, exécutable, Pydroid...)
- Ton système (Windows/Linux/macOS/Android) et la version de FletchTime
  (visible en bas de la fenêtre ou dans le terminal)

Pas besoin d'avoir déjà une solution en tête -- un problème bien décrit
suffit amplement.

## Proposer un changement de code

Le flux classique de l'open source, rien de plus :

1. **Fork** le dépôt, puis clone ton fork
2. Crée une branche (`git checkout -b ma-fonctionnalite`)
3. Fais tes changements
4. Vérifie que la suite de tests passe (voir ci-dessous)
5. Ouvre une **Pull Request** vers `master`, en expliquant le *pourquoi* du
   changement, pas seulement le *quoi*

Pas besoin de discuter d'un gros changement à l'avance si tu préfères
montrer du code directement -- mais pour quelque chose de structurant
(nouveau mode de tir, changement d'architecture...), ouvrir une Issue
d'abord pour en discuter évite de coder dans le vide.

### Installation pour développer

```bash
git clone https://github.com/MrFanghoDev/fletchtime.git
cd fletchtime
pip install -e ".[dev]"
```

### Style de code

[Black](https://black.readthedocs.io/) et [Ruff](https://docs.astral.sh/ruff/)
formatent et vérifient le code. Sur une Pull Request, la CI les fait tourner
en mode vérification seule (elle ne modifie jamais ta branche) -- si elle
signale un souci, corrige-le localement avant de proposer :

```bash
black src tests demo.py run_server.py run_tests.py
ruff check --fix src tests demo.py run_server.py run_tests.py
```

### Lancer les tests

Aucune dépendance externe nécessaire pour les tests (`websockets` compris --
la logique serveur est testée via un faux client WebSocket) :

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Ou, plus simple : `python3 run_tests.py` (pensé aussi pour Pydroid --
ouvrir le fichier et appuyer sur Run, sans terminal).

### Pour aller plus loin

Le [guide développeur](https://mrfanghodev.github.io/fletchtime/dev-guide/index.html)
détaille l'architecture, les choix techniques, et pas mal de pièges déjà
rencontrés (empaquetage, versionnage, CI) -- utile avant de se lancer dans
un changement conséquent.

## Le ton qu'on essaie de garder

Projet porté par un club, pas une entreprise -- pas de pression, pas
d'attente de réactivité instantanée. Sois patient·e avec les retours,
bienveillant·e dans les échanges, et n'hésite pas si quelque chose dans
cette doc (ou dans le code) n'est pas clair : c'est aussi un signal utile
pour l'améliorer. Voir aussi le [code de conduite](CODE_OF_CONDUCT.md).

---

# Contributing to FletchTime

Thanks for your interest in FletchTime! This project started from a club's
real-world use (Les Aigles 77 / Archers Libres de Fontaine le Port),
published open source under [GPL-3.0-or-later](LICENSE) to be useful to
other clubs and to the FFTL federation. The contribution process is kept
deliberately simple.

## Reporting a bug or suggesting an idea

Use [GitHub Issues](https://github.com/MrFanghoDev/fletchtime/issues) --
no complicated form needed. For a bug, what helps most:
- What you did, what you expected, what happened instead
- How you launched FletchTime (`pip install`, executable, Pydroid...)
- Your platform (Windows/Linux/macOS/Android) and FletchTime's version
  (shown at the bottom of the window or in the terminal)

You don't need a solution in mind already -- a well-described problem is
plenty.

## Proposing a code change

The classic open-source flow, nothing more:

1. **Fork** the repository, then clone your fork
2. Create a branch (`git checkout -b my-feature`)
3. Make your changes
4. Check that the test suite passes (see below)
5. Open a **Pull Request** against `master`, explaining the *why* of the
   change, not just the *what*

No need to discuss a big change beforehand if you'd rather show code
directly -- but for anything structural (new shooting mode, architecture
change...), opening an Issue first to discuss it avoids coding in a
direction that might not fit.

### Setting up for development

```bash
git clone https://github.com/MrFanghoDev/fletchtime.git
cd fletchtime
pip install -e ".[dev]"
```

### Code style

[Black](https://black.readthedocs.io/) and [Ruff](https://docs.astral.sh/ruff/)
format and check the code. On a Pull Request, CI runs them in check-only
mode (it never modifies your branch) -- if it flags something, fix it
locally before proposing:

```bash
black src tests demo.py run_server.py run_tests.py
ruff check --fix src tests demo.py run_server.py run_tests.py
```

### Running the tests

No external dependencies needed for tests (`websockets` included -- server
logic is tested through a fake WebSocket client):

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Or, simpler: `python3 run_tests.py` (also designed for Pydroid -- open the
file and tap Run, no terminal needed).

### Going further

The [developer guide](https://mrfanghodev.github.io/fletchtime/dev-guide/index.html)
covers the architecture, technical decisions, and quite a few pitfalls
already run into (packaging, versioning, CI) -- worth a read before
starting anything substantial.

## The tone we're aiming for

This is a club-run project, not a company -- no pressure, no expectation of
instant responsiveness. Please be patient with feedback, kind in
discussions, and don't hesitate to flag if anything in this doc (or the
code) isn't clear: that's useful signal for improving it too. See also the
[Code of Conduct](CODE_OF_CONDUCT.md).
