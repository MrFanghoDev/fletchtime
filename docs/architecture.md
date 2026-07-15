# Architecture technique

## Vue d'ensemble

```{code-block} text
                     ┌──────────────────────────┐
                     │   Serveur Python (asyncio) │
                     │  (tourne sur le poste DOS,  │
                     │   testé sur Pydroid 3)      │
                     │                             │
                     │  - MatchServer : état du     │
                     │    match, source de vérité   │
                     │    unique                    │
                     │  - MatchEngine (Indoor/Flint) │
                     │  - HTTP statique (stdlib)     │
                     │  - WebSocket (paquet          │
                     │    `websockets`)               │
                     └────────────┬────────────────┘
                                  │  réseau local (WiFi)
              ┌───────────────────┼───────────────────┐
              │                   │                   │
       ┌──────▼──────┐    ┌──────▼──────┐     ┌──────▼──────┐
       │ control.html │    │display.html │     │display.html │
       │  (poste DOS) │    │  (lane 1)    │     │  (lane 2)    │
       └──────────────┘    └──────────────┘     └──────────────┘
```

Un seul service Python centralise l'état de la compétition. Tous les clients
(contrôle et écrans) sont de simples pages web connectées en WebSocket : aucune
installation logicielle sur les tablettes d'affichage.

## Choix techniques

| Composant | Choix | Justification |
|---|---|---|
| Backend WebSocket | Paquet `websockets` (asyncio) | Pas de FastAPI/Pydantic (dépendance Rust `pydantic-core` à risque sur Android/Pydroid) ni d'uvicorn `[standard]` (extensions C `uvloop`/`httptools`) ; `websockets` a un fallback pur Python si son extension C optionnelle ne compile pas — installable de façon fiable sur Pydroid 3. |
| Serveur HTTP statique | `http.server` (stdlib) | Sert les pages et assets sur un port séparé du WebSocket (évite l'API instable de combinaison HTTP+WS selon les versions de `websockets`) ; utilisé aussi pour la découverte de fichiers (bannières, packs de sons) via le listing de répertoire natif. |
| Communication temps réel | WebSocket | Évite la dérive du polling, tous les écrans restent synchronisés à la seconde près. |
| Frontend | HTML/CSS/JS vanilla | Pas de build, une tablette ouvre juste une URL. |
| Config des modes (Indoor/Flint) | Fichiers **TOML** (`config/*.toml`) | Lu via `tomllib`, stdlib depuis Python 3.11 (donc Pydroid) -- zéro dépendance. Écriture via un petit sérialiseur maison (pas de support d'écriture en stdlib). |
| Assets (logo, bannières, cibles, sons) | Dépôt de fichiers dans `web/assets/...`, découverte par listing de répertoire HTTP | Pas de formulaire d'upload à construire ni maintenir. |
| Déploiement | Développé et testé sur Pydroid 3 (Android) ; lancement via un script Python unique (`run_server.py`) | Contrainte du club : développement mobile-only, pas de PC. |

## Modèle d'état

Le serveur maintient un objet d'état, source de vérité unique, recalculé à
chaque tick du moteur de séquencement (`MatchEngine.tick()`, ~5 fois/seconde)
et diffusé à tous les écrans connectés. Chaque connexion reçoit un payload
individualisé (pas un broadcast identique pour tous), car un message peut être
ciblé sur une seule lane.

```{code-block} json
:caption: Payload diffusé à un client donné (exemple)

{
  "type": "state",
  "state": {
    "phase": "green",
    "time_left": 87.0,
    "current_turn": "A-B",
    "end_number": 3,
    "total_ends": 6,
    "unit_number": 1,
    "arrow_in_end": 0,
    "total_arrows_in_end": 0,
    "distance_label": "20 yards",
    "target_image": "assets/targets/indoor_recurve.jpg",
    "target_image_2": "assets/targets/indoor_compound.jpg",
    "finished": false
  },
  "message": null,
  "language": "fr",
  "event_title": "Concours FFTL Indoor -- Février 2026",
  "connected_lanes": ["1", "2", "3"],
  "active_mode": "indoor",
  "sound_pack": "classic"
}
```

`state` vaut `null` quand aucun match n'est en cours (écran neutre). Chaque
écran ne fait qu'interpréter ce payload ; toute la logique de décision (quand
passer à l'orange, quand enchaîner la volée suivante, quand mettre en pause
entre deux relais, etc.) vit côté serveur, dans le moteur de séquencement.

## Moteur de séquencement

Contrairement à l'approche legacy observée dans ArcheryClock (dispatch par
chaînes de caractères `if archerysystem = 'fita' then ...` dispersées dans un
fichier de 12 000 lignes), le moteur est structuré en deux couches
indépendantes :

- **`ShootingMode`** (`IndoorMode`, `FlintMode`) : ne fait qu'une chose,
  produire à l'avance la liste ordonnée et complète des `Step` d'un match
  (mise en place, tir, pause...) à partir d'une config (`IndoorConfig`,
  `FlintConfig`). Aucun état, aucune notion de temps qui s'écoule -- juste une
  fonction pure `build_sequence() -> List[Step]`. C'est ce qui permet de
  tester chaque mode en asserting directement sur la liste de steps produite,
  sans faire tourner de minuteur.
- **`MatchEngine`** : rejoue cette liste. C'est la seule classe avec de l'état
  (index courant, temps restant, pause, urgence). Expose les commandes du DOS :
  `tick(dt)`, `next()`, `stop()`, `restart()`, `goto(unit, end, arrow, turn)`,
  `emergency()`/`resume()`, `pause()`/`play()`.

```{code-block} python
:caption: Step -- un segment temporisé (extrait réel)

@dataclass(frozen=True)
class Step:
    phase: Phase                       # RED, GREEN, ORANGE, PAUSE, EMERGENCY...
    duration: Optional[float]          # None = attente indéfinie (fin de volée)
    current_turn: str = ""             # "A-B", "C-D"
    end_number: int = 0
    total_ends: int = 0
    unit_number: int = 1               # série (Indoor) / unité standard (Flint)
    arrow_in_end: int = 0              # flèche du walk-up
    distance_label: str = ""
    target_image: str = ""
    target_image_2: str = ""           # Indoor seulement (2 blasons)
    sound_event: Optional[str] = None
    orange_threshold: Optional[float] = None   # seuil de passage à l'orange
    orange_sound_event: Optional[str] = None
```

Le décompte est **continu** : `orange_threshold` ne crée pas un deuxième step
séparé, c'est juste un seuil vérifié à chaque tick sur le même step -- le
temps affiché ne redémarre jamais.

- `IndoorMode` : construit un bloc de steps par relais (A-B, C-D) et par
  volée ; insère un step `PAUSE` (`duration=None`) entre chaque volée. Le
  relais suivant démarre directement par sa propre mise en place (RED), pas
  besoin de pause entre A-B et C-D puisqu'ils partagent le même blason.
- `FlintMode` : idem pour les volées standards, mais chaque relais tire
  l'**unité entière** (7 volées) avant que l'autre ne la reprenne -- pas de
  `PAUSE` au sein d'une volée, seulement entre volées et entre relais/unités.
  La volée walk-up est un bloc de 4 flèches contiguës (pas de `PAUSE` entre
  elles, conformément à la règle "tout le monde avance ensemble").

Ce découpage permet d'ajouter un nouveau mode sans toucher aux modes
existants (voir {doc}`dev-guide/index`).

## Configuration (TOML)

`src/fletchtime_server/config_store.py` charge/sauvegarde trois fichiers :

- `config/indoor.toml`, `config/flint.toml` : tous les réglages de chaque
  mode (temps, distances, nombre de volées/flèches, images de cible, ordre
  des relais par défaut). Chargés à chaque démarrage de match (pas mis en
  cache), donc un changement via `config.html` prend effet dès le prochain
  match sans redémarrer le serveur.
- `config/app.toml` : réglages globaux non liés à un mode (actuellement, le
  pack de sons actif). Pris en compte **immédiatement** sur tous les écrans
  déjà connectés (contrairement à `indoor.toml`/`flint.toml`).

Un champ non reconnu dans un fichier TOML est ignoré silencieusement (pas
d'erreur bloquante) ; un fichier absent retombe sur les valeurs par défaut du
dataclass Python correspondant. Toute tentative de sauvegarde invalide (ex.
seuil orange supérieur au temps de tir total) est rejetée **avant** écriture,
avec le message d'erreur renvoyé à `config.html`.

**Garde-fou** : `save_config` refuse de modifier la configuration d'un mode
(Indoor ou Flint) tant qu'un match de ce même mode est en cours (actif, en
pause, ou en urgence) -- vérifié côté serveur (autoritaire), avec un signal
`active_mode` diffusé en continu pour que `config.html` grise le bouton
correspondant de façon proactive.

## Packs de sons

```{code-block} text
web/assets/sounds/packs/
  classic/            # généré par synthèse (scripts/generate_classic_sounds.py),
    prep_start.wav     # libre de droits, inclus dans le dépôt
    shoot_start.wav
    warning_orange.wav
    countdown_tick.wav
    emergency_start.wav
    emergency_end.wav
    end_of_volee.wav
    pause_start.wav
    pause_end.wav
    end_of_match.wav
  _custom/            # dossier gabarit (README uniquement, gitignored sinon)
  <pack_du_club>/     # n'importe quel autre nom -- jamais versionné
```

Le serveur diffuse un **identifiant d'événement** (10 au total, voir
`docs/specifications.md`) plus le nom du pack actif (`sound_pack`) ; chaque
écran résout localement le fichier audio correspondant
(`assets/sounds/packs/<pack>/<événement>.{wav,mp3,ogg}`, testés dans cet
ordre) et met en cache l'extension qui a fonctionné pour ne pas re-sonder à
chaque déclenchement. Un événement sans fichier retombe sur un bip Web Audio
synthétisé. Aucun flux audio ne transite par le serveur -- chaque écran joue
son propre fichier localement.

```{important}
Seul le pack "classic" (généré par synthèse, donc libre de droits) est suivi
par Git. N'importe quel autre dossier sous `packs/` -- quel que soit son nom --
est ignoré par `.gitignore` et reste local à chaque club.
```

## Multi-écrans et ciblage

Chaque écran se connecte au WebSocket et s'enregistre avec son numéro de lane
(`register_display`, extrait de `?lane=<n>` dans l'URL). Le serveur garde une
table connexion → lane, ce qui permet :

- d'afficher sur `control.html` la liste des lanes effectivement connectées ;
- d'envoyer un message à une seule lane (`message` avec un champ `lane`) sans
  affecter les autres écrans, avec repli sur le message global si aucun
  message ciblé n'est actif pour cette lane ;
- un message global envoyé après un message ciblé **remplace** ce dernier
  (pas de message ciblé qui reste bloqué indéfiniment sur un écran).

La miniature d'aperçu de `control.html` est un vrai `display.html` chargé
dans une `<iframe>` (mise à l'échelle en CSS) plutôt qu'une logique de rendu
dupliquée -- elle s'enregistre avec la lane spéciale `"apercu"`, exclue du
comptage des écrans connectés.
