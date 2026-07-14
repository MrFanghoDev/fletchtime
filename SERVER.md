# Serveur temps réel — Étape 2

Un seul process, deux serveurs simples :
- **HTTP** (port 8000, stdlib pur `http.server`) : sert `web/control.html` et `web/display.html`.
- **WebSocket** (port 8765, paquet `websockets`) : diffuse l'état du match en temps réel.

Séparés volontairement sur deux ports plutôt que combinés sur un seul,
pour éviter de dépendre d'une API `websockets` qui a changé entre versions
récentes de la lib (voir `docs/architecture.md`).

## Installer la dépendance — sur Pydroid

1. Menu ☰ → **Pip**.
2. Cocher *Use prebuilt libraries repository*.
3. Chercher **`websockets`** → Installer.

C'est la seule dépendance externe de cette étape (le reste est stdlib).

## Lancer le serveur — sur Pydroid

1. Ouvrir **`run_server.py`** à la racine du projet.
2. Appuyer sur ▶️ **Run**.
3. La console affiche l'adresse à ouvrir, par exemple :
   ```
   Contrôle  : http://192.168.1.42:8000/control.html
   Affichage : http://192.168.1.42:8000/display.html?lane=1
   ```
4. Depuis le **même téléphone** : ouvrir Chrome et coller l'URL en
   remplaçant l'IP par `127.0.0.1`.
5. Depuis **une autre tablette/PC sur le même WiFi** : ouvrir l'URL
   affichée telle quelle. Changer `lane=1` en `lane=2`, `lane=3`, etc.
   pour chaque pas de tir (c'est juste une étiquette affichée, purement
   côté navigateur).
6. Sur la page contrôle : bouton "Démarrer Indoor" ou "Démarrer Flint",
   puis "Next" pour avancer manuellement les phases (rouge → vert →
   orange → volée suivante), et tester Urgence/Reprise.

Le serveur tourne tant que Pydroid reste ouvert au premier plan (voir la
remarque sur l'optimisation de batterie Android dans la conversation
précédente).

## Lancer les tests de cette étape

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
ou, sur Pydroid, ouvrir `run_tests.py` et appuyer sur Run — comme pour
l'étape 1. 40 tests au total (33 moteur + 7 serveur), tous testables
**sans** avoir `websockets` installé : les tests du serveur utilisent un
faux client WebSocket (`FakeWebSocket` dans `tests/test_match_server.py`)
qui n'a besoin d'aucun paquet externe.

```{important}
Ce que je n'ai **pas** pu tester moi-même : la partie réellement réseau
(`websockets.serve`, ouverture de deux ports, connexion depuis un vrai
navigateur). Mon bac à sable n'a pas d'accès réseau pour installer le
paquet `websockets`, donc je n'ai validé que la logique métier (via le
faux client). Le premier vrai test grandeur nature, c'est le tien sur
Pydroid -- dis-moi ce qui se passe (erreurs éventuelles au démarrage,
comportement des boutons, etc.).
```

## Ce qui est fait

- Démarrage d'un match (Indoor ou Flint, config par défaut) depuis la page
  contrôle.
- Next / Urgence / Reprise / Pause / Reprendre / Message, synchronisés en
  temps réel sur tous les écrans connectés.
- Affichage brut mais fonctionnel : temps restant, phase (couleur de
  fond), ligne A-B/C-D ou n° de flèche walk-up, distance, n° de volée.
- Un bip sonore basique par événement (Web Audio, généré à la volée) --
  provisoire, sera remplacé par le vrai système de packs de sons à
  l'étape 5.

## Ce qui n'est pas encore fait (prévu aux étapes suivantes)

- Image de la cible (étape 3).
- Presets de mode sans coder en dur `IndoorConfig()`/`FlintConfig()` par
  défaut (étape 4).
- Logo du club, banderoles publicitaires (étape 4).
- Vrais packs de sons interchangeables (étape 5).
