# Moteur de séquencement — Étape 1

Bibliothèque Python pure (aucune dépendance externe), qui modélise le
déroulé chronométré d'un concours FFTL (Indoor, Flint) et le rejoue via un
moteur pilotable (tick, next manuel, urgence, pause).

## Lancer les tests — sur PC

Aucune dépendance à installer (tout est en `unittest`, stdlib) :

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

33 tests, tous verts à date.

## Lancer les tests — sur téléphone (Pydroid 3)

Pas de terminal ni de variable d'environnement nécessaire :

1. Dézipper `fletchtime.zip` quelque part sur le stockage du téléphone
   (n'importe quel gestionnaire de fichiers Android sait dézipper).
2. Dans Pydroid 3 : ouvrir le fichier **`run_tests.py`** à la racine du
   projet (menu ☰ → Ouvrir → naviguer jusqu'au dossier `fletchtime`).
3. Appuyer sur le bouton ▶️ **Run**.

`run_tests.py` ajoute lui-même `src/` au chemin d'import (`sys.path`), donc
aucune configuration manuelle n'est nécessaire — contrairement à la commande
PC qui utilise `PYTHONPATH`. Le résultat (33 tests, OK ou détail des
échecs) s'affiche directement dans la console de sortie de Pydroid.

## Voir le moteur tourner (démo visuelle)

Toujours sans terminal : ouvrir **`demo.py`** dans Pydroid et appuyer sur
Run. Ça affiche le déroulé complet d'une manche Indoor réduite puis d'une
unité Flint réduite, étape par étape (phase, temps restant, distance,
ligne A-B/C-D, événements sonores) — utile pour vérifier visuellement que
la logique correspond bien au règlement avant de continuer.

## Ce qui est fait (étape 1 de la roadmap)

- `MatchState` / `Phase` : le modèle d'état, tel qu'il sera plus tard
  sérialisé en JSON par le serveur (voir `docs/architecture.md`).
- `IndoorMode` : 2 séries de 6 volées de 5 flèches (configurable), rotation
  A-B/C-D.
- `FlintMode` : 6 volées standards (1 distance, ~3 min) + 1 volée finale
  walk-up (4 flèches, 4 distances, 45s/flèche), pour `units` unités
  standards (2 par défaut = 1 parcours).
- `MatchEngine` : lecture de la séquence (`tick`, `next`, `emergency`,
  `resume`, `pause`, `play`), gestion des messages, événements sonores
  consommés une seule fois par transition.
- `run_tests.py` / `demo.py` : lancement sans terminal, pensé pour Pydroid.

## Ce qui n'est pas encore fait

- Aucun réseau, aucune UI — c'est prévu à l'étape 2 (serveur WebSocket),
  qui viendra se brancher par-dessus cette bibliothèque sans la modifier.
  Stack révisée pour rester compatible Pydroid (pas de FastAPI/Pydantic,
  voir `docs/architecture.md`).
- Pas encore de configuration chargée depuis un fichier JSON/YAML (les
  `IndoorConfig`/`FlintConfig` sont construits en Python pour l'instant) —
  prévu avec l'interface de contrôle (étape 4).
