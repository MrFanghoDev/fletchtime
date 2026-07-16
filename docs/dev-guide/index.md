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
  seul un `next()` manuel du DOS le fait avancer.
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

```{note}
La publication automatique de cette doc sur GitHub Pages est déjà en place
(`.github/workflows/docs.yml`) -- voir le README à la racine du dépôt pour
l'activer (une seule fois, côté réglages GitHub).
```
