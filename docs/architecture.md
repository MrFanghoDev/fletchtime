# Architecture technique

## Vue d'ensemble

```{mermaid}
flowchart TB
    subgraph srv["Serveur Python (asyncio)<br/>tourne sur le poste du responsable<br/>du chronométrage, testé sur Pydroid 3"]
        MS["MatchServer<br/><i>état du match, source de vérité unique</i>"]
        ME["MatchEngine<br/><i>Indoor / Flint</i>"]
        HTTP["HTTP statique (stdlib)"]
        WS["WebSocket (paquet websockets)"]
        MS --- ME
        MS --- HTTP
        MS --- WS
    end

    srv -->|réseau local WiFi| C["control.html<br/><i>poste de contrôle</i>"]
    srv -->|réseau local WiFi| D1["display.html<br/><i>pas de tir 1</i>"]
    srv -->|réseau local WiFi| D2["display.html<br/><i>pas de tir 2</i>"]
```

Un seul service Python centralise l'état de la compétition. Tous les clients
(contrôle et écrans) sont de simples pages web connectées en WebSocket : aucune
installation logicielle sur les tablettes d'affichage.

## Choix techniques

| Composant | Choix | Justification |
|---|---|---|
| Backend WebSocket | Paquet `websockets` (asyncio) | Pas de FastAPI/Pydantic (dépendance Rust `pydantic-core` à risque sur Android/Pydroid) ni d'uvicorn `[standard]` (extensions C `uvloop`/`httptools`) ; `websockets` a un fallback pur Python si son extension C optionnelle ne compile pas — installable de façon fiable sur Pydroid 3. |
| Serveur HTTP statique | `http.server` (stdlib), port **8000** par défaut | Sert les pages et assets sur un port séparé du WebSocket (port **8765** par défaut) -- évite l'API instable de combinaison HTTP+WS selon les versions de `websockets` ; utilisé aussi pour la découverte de fichiers (bannières, packs de sons) via le listing de répertoire natif. Les deux ports sont modifiables (fenêtre graphique, `config/gui.toml`, ou `--http-port`/`--ws-port` en ligne de commande -- voir {doc}`dev-guide/index`), notamment pour plusieurs salles de compétition sur un même PC. **Les deux ports doivent être accessibles** depuis les écrans/postes clients (pare-feu, redirection de port si le serveur tourne dans un conteneur/VM -- ex. Docker, WSL2) : rediriger seulement le port HTTP charge les pages mais laisse la synchronisation temps réel bloquée ("en attente de connexion" indéfiniment). |
| Communication temps réel | WebSocket | Évite la dérive du polling, tous les écrans restent synchronisés à la seconde près. |
| Frontend | HTML/CSS/JS vanilla | Pas de build, une tablette ouvre juste une URL. |
| Config des modes (Indoor/Flint) | Fichiers **TOML** (`config/*.toml`) | Lu via `tomllib`, stdlib depuis Python 3.11 (donc Pydroid) -- zéro dépendance. Écriture via un petit sérialiseur maison (pas de support d'écriture en stdlib). |
| Assets (logo, bannières, cibles, sons) | Dépôt de fichiers dans `web/assets/...`, découverte par listing de répertoire HTTP | Pas de formulaire d'upload à construire ni maintenir. |
| Paquetage | Un seul paquet `fletchtime` (PyPI), sous-paquets `fletchtime.engine`/`fletchtime.server`, pages web incluses comme *package data* dans `fletchtime.web` | `pip install fletchtime` + `python -m fletchtime` (ou juste `fletchtime`) suffit partout -- Pydroid compris. Les données propres au club (logo, sons, config) restent hors du paquet installé, bootstrapées dans le répertoire courant au premier lancement. |
| Déploiement | Pydroid 3 (Android), pip/PyPI, ou exécutable autoporteur (PyInstaller) | Contrainte du club à l'origine : développement mobile-only, pas de PC -- le paquet PyPI et l'exécutable ont été ajoutés ensuite pour élargir l'usage à d'autres clubs. |

## Modèle d'état

Le serveur maintient un objet d'état, source de vérité unique, recalculé à
chaque tick du moteur de séquencement (`MatchEngine.tick()`, ~5 fois/seconde)
et diffusé à tous les écrans connectés. Chaque connexion reçoit un payload
individualisé (pas un broadcast identique pour tous), car un message peut être
ciblé sur une seule lane.

```{important}
`MatchServer.tick_loop()` mesure le temps **réellement écoulé** entre deux
ticks via `time.monotonic()`, plutôt que de supposer que l'intervalle visé
(`TICK_INTERVAL`, 0.2s) s'est écoulé pile. `asyncio.sleep()` ne dort jamais
exactement la durée demandée -- l'écart, minime à chaque tick, dérivait de
façon perceptible sur une volée longue (plusieurs secondes sur les 45s
d'un walk-up Flint, remonté sous Windows spécifiquement, dont la
granularité de l'ordonnanceur est plus grossière que sous Linux). Voir
`tests/test_match_server.py::test_tick_loop_uses_actual_elapsed_time_not_fixed_interval`.
```

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
  (index courant, temps restant, pause, urgence). Expose les commandes du
  responsable du chronométrage : `tick(dt)`, `next()`, `stop()`, `restart()`,
  `goto(unit, end, arrow, turn)`, `emergency()`/`resume()`, `pause()`/`play()`.

Les phases visuelles (`Phase`, voir {doc}`api-reference`) suivent ces
transitions :

```{mermaid}
stateDiagram-v2
    [*] --> RED: mise en place
    RED --> GREEN: fin de la mise en place
    GREEN --> ORANGE: seuil d alerte franchi, même décompte
    GREEN --> PAUSE: fin de volée standard
    ORANGE --> PAUSE: fin de volée
    PAUSE --> RED: next, relais ou volée suivante
    RED --> EMERGENCY: emergency
    GREEN --> EMERGENCY: emergency
    ORANGE --> EMERGENCY: emergency
    EMERGENCY --> RED: resume
    EMERGENCY --> GREEN: resume
    EMERGENCY --> ORANGE: resume
    GREEN --> [*]: fin de match
    ORANGE --> [*]: fin de match
```

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

`src/fletchtime/server/config_store.py` charge/sauvegarde trois fichiers :

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

## Données du club (assets bootstrapés)

Les fichiers réellement fournis avec FletchTime vivent dans le paquet
lui-même (`src/fletchtime/web/_defaults/`), pas dans `web/assets/` à la
racine du dépôt -- ce dernier n'est qu'une sortie générée au premier
lancement (voir `fletchtime.__main__.ensure_directories`), jamais
committée, et identique que FletchTime tourne en paquet pip ou en
exécutable PyInstaller (même logique de bootstrap dans les deux cas) :

```{code-block} text
src/fletchtime/web/_defaults/       # fourni avec le paquet, committé
  club/README.md        # explique comment ajouter le logo du club
  banners/README.md      # explique comment ajouter des bannières sponsors
  targets/                # images de blasons par défaut (Indoor + Flint)
  sounds/packs/
    classic/              # généré par synthèse (scripts/generate_classic_sounds.py),
      prep_start.wav       # libre de droits, inclus dans le paquet
      shoot_start.wav
      warning_orange.wav
      countdown_tick.wav
      emergency_start.wav
      emergency_end.wav
      end_of_volee.wav
      pause_start.wav
      pause_end.wav
      end_of_match.wav
    README.md             # explique comment créer un pack personnalisé

web/assets/                          # généré au 1er lancement, jamais committé
  club/README.md          # copié depuis _defaults/ une seule fois
  banners/README.md        # idem
  targets/                  # idem
  sounds/packs/
    classic/                # idem
    README.md               # idem
    <pack_du_club>/          # n'importe quel autre nom -- jamais copié ni versionné
```

Cette copie ne se fait qu'**une seule fois par fichier/dossier** (si la
destination n'existe pas déjà) : une personnalisation du club (logo ajouté,
packs ajoutés, fichiers du pack `classic` modifiés ou supprimés) est donc
toujours préservée, même après une mise à jour du paquet FletchTime.

Le serveur diffuse un **identifiant d'événement** (10 au total, voir
`docs/specifications.md`) plus le nom du pack actif (`sound_pack`) ; chaque
écran résout localement le fichier audio correspondant
(`assets/sounds/packs/<pack>/<événement>.{wav,mp3,ogg}`, testés dans cet
ordre) et met en cache l'extension qui a fonctionné pour ne pas re-sonder à
chaque déclenchement. Un événement sans fichier retombe sur un bip Web Audio
synthétisé. Aucun flux audio ne transite par le serveur -- chaque écran joue
son propre fichier localement.

```{important}
Seul `src/fletchtime/web/_defaults/` (et son contenu : README, images de
blasons, pack "classic") est suivi par Git. Le dossier `web/assets/` à la
racine du dépôt n'est qu'une sortie générée au premier lancement,
entièrement ignorée par `.gitignore` -- y compris ses copies de `_defaults/`.
```

## Authentification (optionnelle)

Un mot de passe optionnel (`config/auth.toml`, vide par défaut -- jamais
versionné, contrairement à `app.toml`/`indoor.toml`/`flint.toml` qui sont
des réglages partageables sans risque) protège les actions qui changent
l'état du match ou la configuration (`PROTECTED_ACTIONS` dans
`match_server.py`). `display.html` (lecture seule) n'est jamais concerné.

Mécanisme par **session de connexion WebSocket**, pas par mot de passe
persistant sur l'appareil : une action `authenticate` marque la connexion
en cours comme authentifiée (`self._authenticated_connections`, un
ensemble de connexions, remis à zéro à la déconnexion) ; rouvrir la page
(nouvelle connexion) redemande le mot de passe. Le mot de passe lui-même
n'est jamais renvoyé en clair au client -- seul un booléen `password_set`
circule.

Tant qu'aucun mot de passe n'est défini, `_auth_required()` retourne
toujours `False` : comportement strictement identique à avant l'ajout de
ce mécanisme, y compris pour définir le tout premier mot de passe (pas de
poule-et-l'œuf). Une fois un mot de passe actif, le changer ou le
supprimer nécessite d'être déjà authentifié avec l'ancien.

```{important}
Reste du HTTP simple, non chiffré : quelqu'un capturant le trafic réseau
sur le même WiFi pourrait intercepter le mot de passe. Adapté à un réseau
de concours dédié/fermé, pas à un réseau partagé avec le grand public
(voir `docs/roadmap.md`, backlog sécurité).
```

## Fenêtre graphique et cycle de vie des serveurs

Depuis l'introduction de la fenêtre graphique (`fletchtime.gui`, basée sur
`customtkinter`), point d'entrée par défaut sur toutes les plateformes
(`fletchtime.__main__.main`), les deux serveurs (HTTP statique et
WebSocket) doivent pouvoir démarrer et s'arrêter **proprement**, pas
seulement tourner jusqu'à un Ctrl+C -- boutons Démarrer/Arrêter obligent.
Cette logique vit dans `fletchtime.runtime.ServerRuntime`, partagée entre
le mode graphique et le mode terminal (`--headless`), pour ne jamais la
dupliquer.

```{mermaid}
flowchart LR
    subgraph main["Thread principal"]
        GUI["Fenêtre customtkinter<br/><i>mainloop -- doit posséder ce thread</i>"]
    end
    subgraph httpT["Thread HTTP"]
        HTTPD["ThreadingHTTPServer<br/><i>serve_forever / shutdown</i>"]
    end
    subgraph wsT["Thread WebSocket"]
        LOOP["Boucle asyncio dédiée<br/><i>run_ws_server -- attend un stop_event</i>"]
    end

    GUI -->|start / stop| HTTPD
    GUI -->|start / stop| LOOP
    HTTPD -.->|file thread-safe| GUI
    LOOP -.->|file thread-safe| GUI
```

Points clés :

- Une fenêtre graphique (tkinter et ses surcouches, dont `customtkinter`)
  doit posséder le thread principal -- contrairement à l'ancien
  `fletchtime.__main__.main`, qui y faisait tourner directement
  `asyncio.run(run_ws_server(...))`. Le serveur WebSocket tourne donc
  maintenant dans son **propre thread**, avec sa propre boucle asyncio
  (`asyncio.new_event_loop()`), exactement comme le serveur HTTP l'a
  toujours fait.
- Arrêt propre du serveur HTTP : `ThreadingHTTPServer.shutdown()` (offert
  par la stdlib, `socketserver.BaseServer`) débloque `serve_forever()`
  depuis n'importe quel autre thread -- rien à construire à la main.
- Arrêt propre du serveur WebSocket : `run_ws_server` attend maintenant un
  `asyncio.Event` (`stop_event`) plutôt qu'un `await asyncio.Future()` qui
  ne se résout jamais. Le déclencher depuis un autre thread (le thread
  graphique) passe par `loop.call_soon_threadsafe(stop_event.set)` --
  seule façon sûre d'interagir avec une boucle asyncio depuis l'extérieur
  de son propre thread.
- Le journal affiché dans la fenêtre est une redirection de `sys.stdout`/
  `sys.stderr` vers une `queue.Queue` (thread-safe par construction), lue
  et affichée via un `after()` périodique de tkinter -- capte le journal
  d'accès HTTP (`http.server` écrit sur stderr) sans avoir à instrumenter
  chaque site d'appel.

```{warning}
Le rendu de la fenêtre elle-même n'a pas pu être testé visuellement lors
de son écriture initiale (pas d'affichage graphique disponible dans
l'environnement de développement utilisé). La logique de cycle de vie
qu'elle pilote (`ServerRuntime`) est testée pour de vrai (voir
`tests/test_runtime.py` : démarrage, requête HTTP réelle, arrêt, vérifi-
cation que le port est bien libéré, redémarrage sur le même port). Un
premier lancement réel sur PC et sur Pydroid reste nécessaire pour
confirmer le rendu et l'ergonomie tactile -- voir aussi le piège
PyInstaller/`customtkinter` documenté dans {doc}`dev-guide/index`.
```

## Résilience de la boucle de décompte

`MatchServer.tick_loop()` capture désormais toute exception imprévue en
son sein (journalisée avec la trace complète) plutôt que de laisser
mourir la boucle silencieusement -- filet de sécurité ajouté suite à un
symptôme signalé en pratique : le chrono se figeait indéfiniment, sans
aucune erreur visible, le reste du serveur (connexions, réponse aux
commandes) continuant de fonctionner normalement à côté.

```{important}
**Cause la plus probable identifiée** : sous Windows, remplacer un
fichier (`Path.replace`) peut échouer avec une "violation de partage"
si un autre processus a le fichier cible ouvert au même instant
(antivirus, surveillance de fichiers d'un IDE, Git Bash...) -- une
différence fondamentale avec la sémantique POSIX (Linux/macOS), où ceci
n'arrive jamais. Observé une fois en pratique, précisément sur
`config/match_state.json` -- écrit à chaque tick depuis la persistance
après plantage (voir plus bas). Sans gestion d'erreur, cette exception
tuait silencieusement `tick_loop` pour de bon : exactement le symptôme
rapporté (gel permanent, aucune déconnexion, se produisant aussi bien
en fenêtre graphique qu'en mode terminal -- sans lien réel avec le
focus d'une fenêtre, malgré la corrélation observée au départ).

Deux correctifs complémentaires : ce filet dans `tick_loop` (n'importe
quelle exception, pas seulement celle-ci), et
`config_store.save_match_snapshot` qui retente quelques fois avant
d'abandonner proprement (jamais d'exception qui remonterait perturber
la diffusion de l'état aux écrans pour ce tick). Testé concrètement :
un échec transitoire (une fois puis réussite) est absorbé et le
contenu final reste correct ; un échec permanent (toutes les tentatives
échouent) est abandonné proprement, sans jamais lever d'exception.
```

## Statut technique exposé via HTTP (`/api/status`)

Les mêmes données déjà affichées dans `control.html` (écrans connectés,
mode actif, phase en cours, pack de sons, mot de passe configuré ou non)
sont aussi exposées via un simple GET HTTP, lues directement depuis
l'instance `MatchServer` partagée avec le serveur WebSocket (voir
`ServerRuntime`, qui construit maintenant ce `MatchServer` une seule fois
et le fait circuler vers les deux serveurs plutôt que de le laisser
`run_ws_server` en créer un nouveau à chaque démarrage).

Utilisé par la fenêtre graphique pour afficher ce même statut sans
dupliquer la logique de rendu HTML -- interrogé par sondage périodique
(toutes les 2s) depuis un thread séparé plutôt qu'en temps réel via une
vraie connexion WebSocket, volontairement : pas besoin de la précision
temps réel d'une vraie connexion juste pour un affichage de statut, et
ça évite de dupliquer toute la logique de reconnexion/état déjà présente
côté web. La requête HTTP elle-même tourne toujours dans un thread à
part, jamais directement depuis le thread principal de la fenêtre (une
requête bloquante, même locale, gèlerait sinon l'interface le temps de
sa réponse).

## Journal applicatif persistant

En plus du journal affiché dans la fenêtre graphique (en mémoire,
perdu à la fermeture -- voir `fletchtime.gui._QueueWriter`),
`fletchtime.logging_setup.configure_logging` écrit un fichier de journal
persistant (`<données du club>/logs/fletchtime.log`, avec rotation --
1 Mo par fichier, 5 fichiers conservés) : utile pour comprendre après
coup ce qui s'est passé pendant un concours, sans dépendre de la mémoire
volatile de la fenêtre.

`MatchServer` y journalise :
- chaque commande reçue (`next`, `stop`, `start_indoor`...), avec la lane
  d'origine si connue ;
- chaque connexion/déconnexion, avec le nombre de clients restants ;
- les pertes de connexion réseau détectées (WiFi, mise en veille...),
  distinguées d'une fermeture normale ;
- les messages malformés reçus (JSON invalide) ;
- les transitions d'état significatives (`prep_start`, `shoot_start`,
  `warning_orange`, `end_of_volee`, `pause_start`/`pause_end`,
  `emergency_start`/`emergency_end`, `end_of_match`), avec le contexte
  (unité, volée, tour, phase) -- qu'elles soient déclenchées naturellement
  par le décompte ou manuellement (`next`, `goto`...), puisque les deux
  passent par le même mécanisme de collecte d'événements. `countdown_tick`
  est volontairement exclu (se déclenche une fois par seconde dans les
  dernières secondes de chaque volée -- noierait le journal sans valeur
  diagnostique ajoutée).

```{important}
`configure_logging` prend un `console_level` séparé du niveau du fichier
(toujours INFO par défaut, lui) -- la fenêtre graphique doit l'appeler
avec `console_level=logging.INFO` explicitement, **pas** le défaut
(`WARNING`, pensé pour un terminal silencieux par défaut, voir
`fletchtime.__main__`, `-v`/`--verbose`). Un oubli de ce paramètre a
laissé le widget de journal de la fenêtre silencieux en usage normal
pendant un temps -- tous les journaux applicatifs ci-dessus sont à
INFO, donc filtrés par le `WARNING` par défaut, exactement l'inverse de
ce que ce widget est censé montrer. Confirmé par comparaison directe
avant/après correctif : file d'attente vide avant, message présent
après, avec un appel par ailleurs identique.
```


```{important}
Le mot de passe (action `authenticate`) n'est **jamais** journalisé -- le
code ne journalise jamais `data` tel quel, seulement le nom de l'action
et la lane, précisément pour éviter qu'un secret ne traîne en clair dans
un fichier qui persiste sur disque. Vérifié par un test dédié
(`test_password_never_appears_in_logs`).
```

## Récupération après un plantage ou redémarrage du serveur

Avant ce mécanisme, un plantage ou un redémarrage du serveur en plein
match perdait toute la progression (série, volée, temps écoulé) : le
`MatchServer` repartait d'un `self.engine = None`, sans aucun moyen de
savoir où en était le concours -- il fallait alors un `goto()` manuel du
responsable du chronométrage pour s'y retrouver.

`MatchServer` persiste maintenant un instantané JSON de l'état du match
(`config/match_state.json`, jamais versionné -- voir `.gitignore`) :

- **Écriture** : à chaque commande qui change l'état (`next`, `stop`,
  `restart`, `goto`, `emergency`, `resume`, `pause`, `play`,
  `start_indoor`, `start_flint`) et à chaque tick (~5x/seconde) pendant
  le décompte. Écriture atomique (fichier temporaire puis renommage, voir
  `config_store.save_match_snapshot`) : jamais de fichier à moitié écrit
  si le plantage survient pendant l'écriture elle-même.
- **Effacement** : dès que le match se termine (fin naturelle ou `stop()`
  explicite) -- rien à reprendre dans ce cas, un instantané qui traînerait
  redémarrerait un match déjà fini.
- **Lecture** : à la construction de `MatchServer`, tentative de
  restauration -- reconstruit la même séquence d'étapes à partir de la
  config Indoor/Flint actuelle, puis restaure la position exacte
  (`MatchEngine.snapshot`/`restore=`, voir {doc}`api-reference`). Une
  reprise ratée (config changée depuis rendant l'index hors bornes,
  fichier corrompu) efface l'instantané et se rabat silencieusement sur
  un démarrage normal -- ne bloque jamais le lancement du serveur.
- **Silencieuse** : contrairement à un vrai démarrage (`prep_start`), une
  reprise ne rejoue aucun son de transition -- les écrans reprennent
  juste où ça en était, sans redéclencher les sons du début de l'étape.

```{important}
**Le temps restauré est recalculé à partir d'une échéance en horloge
murale (`time.time()`), pas de la valeur `time_left` telle
qu'enregistrée.** Chaque instantané inclut `wallclock_deadline` :
l'instant exact (horloge murale) où le décompte en cours atteindra zéro.
À la restauration, `time_left = wallclock_deadline - time.time()` --
recalculé à l'instant présent, pas relu tel quel. Résultat : peu importe
combien de temps réel s'est écoulé entre la sauvegarde et la
restauration (y compris le temps où le serveur était concrètement
indisponible pendant son redémarrage), le temps restauré reste exact --
sans ça, la reprise affichait un temps figé à l'instant de la dernière
sauvegarde, revenant visiblement en arrière par rapport à ce que l'écran
avait déjà montré en extrapolant localement pendant la coupure (voir plus
bas, "Fonctionnement dégradé en cas de coupure réseau").

Volontairement `time.time()` et jamais `time.monotonic()` pour cette
échéance : `time.monotonic()` redémarre à une référence arbitraire à
chaque nouveau processus, une valeur sauvegardée avant un plantage n'aurait
donc plus aucun sens après redémarrage -- seule l'horloge murale reste
comparable à travers un redémarrage du processus.

`wallclock_deadline` vaut `None` pendant une pause/urgence (le décompte
est gelé, aucune échéance à calculer) : `time_left` reste alors la
valeur figée telle quelle, sans recalcul.
```

```{important}
**Si l'échéance est déjà dépassée à la restauration** (le temps
réellement écoulé pendant l'indisponibilité dépasse ce qui restait sur
l'étape en cours), le match est marqué **terminé** plutôt que de figer
`time_left` à 0. Sans ça, le tick normal suivant (`MatchEngine.tick()`,
voir plus haut) aurait déclenché son rattrapage automatique -- pensé
pour un simple ralentissement passager du serveur, pas une coupure de
plusieurs minutes -- et avancé à l'étape suivante avec une durée
fraîche : le chrono semblait alors "redémarrer" du point de vue des
archers, alors qu'en réalité bien plus de temps s'était écoulé que ce
que l'étape en cours pouvait raisonnablement absorber. Une coupure trop
longue pour être absorbée dans l'étape en cours demande donc une
intervention explicite du responsable du chronométrage (`restart`/
`goto`) plutôt qu'une reprise automatique qui devinerait une position
dans une coupure d'une durée arbitraire.
```

La sauvegarde à chaque tick (plutôt que périodiquement, ex. toutes les
5s) garde malgré tout sa valeur avec ce mécanisme : elle limite la
fenêtre pendant laquelle un changement d'étape aurait pu se produire
juste avant un plantage sans jamais être capturé dans l'instantané.

## Fonctionnement dégradé en cas de coupure réseau

`display.html` continue de décompter **localement** pendant une coupure
WebSocket brève, plutôt que d'afficher un écran figé ou neutre : dès la
perte de connexion, le temps restant est extrapolé à partir du temps
réellement écoulé (`performance.now()`, même principe que
`MatchServer.tick_loop()` côté serveur -- voir plus haut), uniquement
pendant une phase de décompte actif (rouge/vert/orange).

Deux champs sont diffusés spécifiquement pour permettre cette
extrapolation de reproduire fidèlement le comportement normal, sans
deviner quoi que ce soit :

- `MatchState.orange_threshold` (seuil de l'étape en cours) permet de
  reproduire localement le passage à l'orange, exactement comme
  `MatchEngine.current_state` le calcule côté serveur.
- `countdown_tick_seconds` (réglage global, voir `config.html` section
  Son) permet de reproduire localement les bips des dernières secondes,
  exactement comme `MatchEngine._maybe_emit_countdown_ticks`.

Chacun de ces deux événements sonores (`warning_orange`, `countdown_tick`)
ne se déclenche qu'**une seule fois** pendant l'extrapolation, avec le
même suivi que côté serveur (pas de re-déclenchement si on était déjà
orange au moment de la coupure, pas de bip répété pour la même seconde).

Volontairement limité à ce qui peut se dériver de l'étape **en cours**
sans ambiguïté : deviner la transition vers l'étape **suivante** (fin de
volée, walk-up...) sans confirmation du serveur demanderait de dupliquer
toute la logique de séquencement côté client, ce qu'on évite -- le chrono
se fige simplement à zéro en attendant la reconnexion plutôt que de
risquer d'afficher une transition incorrecte (et donc de jouer les sons
associés au mauvais moment). Les sons liés à une transition d'étape
(`shoot_start`, `end_of_volee`, `emergency_start`...) ne jouent donc
jamais pendant une coupure -- seuls `warning_orange` et `countdown_tick`,
qui restent des seuils au sein de la même étape, sont reproduits.

Dès qu'un état est de nouveau reçu du serveur, il fait autorité
immédiatement et corrige toute dérive locale (visuelle et sonore)
accumulée pendant la coupure. Un petit indicateur discret (⏱, coin
supérieur droit) signale ce mode sans alarmer les archers.

Le poste de contrôle, à l'inverse, affiche une bannière large et alarmante
(pas discrète) en cas de coupure -- c'est le responsable du chronométrage
qui doit être alerté clairement, pas les archers.

## Synchronisation du diaporama de l'écran neutre

L'écran neutre (hors concours, ou après sa fin) alterne logo/horloge et
bannières sponsors -- voir `display.html`, `showSlideshowStep`. Aucune
coordination serveur pour ça : chaque écran calcule sa slide actuelle en
divisant l'horloge murale (`Date.now()`) par la durée d'une slide, plutôt
que d'incrémenter un compteur local à partir de 0 à son propre démarrage.

```{important}
Une première version utilisait un compteur local (`slideshowStep`,
incrémenté par `setInterval`) -- deux écrans qui chargeaient ou se
reconnectaient à des instants différents affichaient alors des slides
différentes au même moment, chacun étant reparti de 0 à son propre
démarrage. Corrigé en dérivant la slide actuelle de l'horloge murale
(`Math.floor(Date.now() / SLIDE_DURATION_MS) % totalSlides`) : deux
écrans avec des horloges système raisonnablement synchronisées (le cas
normal sur un même réseau local) calculent alors la même slide,
indépendamment de quand chacun a démarré. Vérifié avec un vrai navigateur
(Chromium via Playwright) : deux pages chargées à 3 secondes d'écart
affichent bien la même slide.
```

## Découverte du port WebSocket côté client

`display.html` et `control.html` ne connaissent pas à l'avance le port
WebSocket à utiliser : depuis que les ports sont devenus modifiables
(voir la fenêtre graphique et `config/gui.toml`, pensé pour plusieurs
salles de compétition sur un même PC), le coder en dur côté client
casserait silencieusement toute page si le port avait été changé.

Chaque page interroge `/api/version` (servi par le même serveur HTTP qui
vient de la servir, donc forcément sur le bon port) avant d'ouvrir sa
connexion WebSocket -- la réponse inclut `ws_port`, le port réellement
configuré (`ServerRuntime.ws_port`, plombé jusqu'à
`http_static.start_http_server`). Un échec de cette requête (réseau,
serveur non démarré) se rabat silencieusement sur `8765` -- l'ancien
port fixe, qui reste une valeur par défaut raisonnable, jamais une
erreur bloquante pour l'utilisateur.

```{note}
Vérifié avec un vrai navigateur (Chromium via Playwright), pas seulement
en théorie : les deux pages utilisent bien le port récupéré
dynamiquement, et se rabattent proprement sur 8765 sans planter quand
`/api/version` échoue.
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

```{note}
**Cette même lane `"apercu"` ne joue jamais de son** (voir `display.html`,
`soundEnabled`) : sans ça, ouvrir la page de contrôle et un vrai écran
d'affichage sur le même PC faisait entendre chaque son deux fois --
l'aperçu est une simple vue visuelle pour le responsable du
chronométrage, pas un écran destiné aux archers. Un paramètre d'URL
`?mute=1` permet en plus de couper le son sur n'importe quel autre onglet
ouvert en trop sur la même machine (ex. pour surveiller une autre lane
sans dupliquer le son de l'écran qui joue réellement pour les archers).
```

