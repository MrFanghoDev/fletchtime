# Architecture technique

## Vue d'ensemble

```{code-block} text
                     ┌──────────────────────────┐
                     │      Serveur FastAPI       │
                     │  (tourne sur le poste DOS) │
                     │                            │
                     │  - État du match (source   │
                     │    de vérité unique)       │
                     │  - Moteur de séquencement  │
                     │    (Indoor / Flint / ...)  │
                     │  - WebSocket broadcast     │
                     └────────────┬───────────────┘
                                  │  réseau local (WiFi)
              ┌───────────────────┼───────────────────┐
              │                   │                   │
       ┌──────▼──────┐    ┌──────▼──────┐     ┌──────▼──────┐
       │  /control    │    │  /display    │     │  /display    │
       │  (poste DOS) │    │  (lane 1)    │     │  (lane 2)    │
       └──────────────┘    └──────────────┘     └──────────────┘
```

Un seul service Python centralise l'état de la compétition. Tous les clients
(contrôle et écrans) sont de simples pages web connectées en WebSocket : aucune
installation logicielle sur les tablettes d'affichage.

## Choix techniques

| Composant | Choix | Justification |
|---|---|---|
| Backend | `websockets` (asyncio, stdlib + un seul paquet) | Pas de FastAPI/Pydantic (dépendance Rust `pydantic-core` à risque sur Android/Pydroid) ni d'uvicorn `[standard]` (extensions C `uvloop`/`httptools`) ; `websockets` a un fallback pur Python si son extension C optionnelle ne compile pas — installable de façon fiable sur Pydroid 3. Peut servir à la fois le HTTP (pages `/control`, `/display`) et le WebSocket sur un seul port. |
| Communication temps réel | WebSocket | Évite la dérive du polling, tous les écrans restent synchronisés à la seconde près |
| Frontend | HTML/CSS/JS vanilla | Pas de build, une tablette ouvre juste une URL |
| Config | Fichiers JSON (presets de mode, packs de sons, assets) | Éditable via l'UI de contrôle, pas de code à toucher |
| Déploiement | Développé et testé sur Pydroid 3 (Android, pas de PC disponible) ; lancement via un script Python unique | Contrainte du club : développement mobile-only |

## Modèle d'état

Le serveur maintient un objet d'état, source de vérité unique, recalculé à chaque
tick du moteur de séquencement et poussé à tous les écrans connectés.

```{code-block} json
:caption: État poussé à un écran donné (exemple)

{
  "phase": "green",
  "time_left": 87,
  "current_turn": "A-B",
  "target_image": "field_20cm.png",
  "lane_number": 3,
  "distance_label": "15 yards",
  "message": null,
  "club_logo": "logo_club.png",
  "banner": null,
  "datetime": "2026-07-14T10:32:00",
  "sound_event": "turn_start"
}
```

Chaque écran ne fait qu'interpréter cet état ; toute la logique de décision (quand
passer au orange, quand enchaîner la volée suivante, etc.) vit côté serveur.

## Moteur de séquencement

Contrairement à l'approche legacy observée dans ArcheryClock (dispatch par chaînes
de caractères `if archerysystem = 'fita' then ...` dispersées dans un fichier de
12 000 lignes), on structure ici **un mode = une classe**, avec une interface commune :

```{code-block} python
:caption: Interface commune (esquisse)

class ShootingMode(Protocol):
    def next_phase(self, current_state: MatchState) -> MatchState:
        """Calcule l'état suivant à partir de l'état courant."""

    def on_tick(self, current_state: MatchState, elapsed: float) -> MatchState:
        """Appelé à chaque tick du timer (ex. 10x/seconde)."""
```

- `IndoorMode` : volées à temps fixe, rotation A-B/C-D classique.
- `FlintMode` : compose en interne deux sous-séquenceurs — un pour les volées
  standards (temps fixe, 1 distance), un pour la volée finale walk-up (4 x 45s,
  4 distances) — et bascule de l'un à l'autre automatiquement selon la position
  dans le parcours.

Ce découpage permet d'ajouter un nouveau mode sans toucher aux modes existants
(voir le {doc}`dev-guide/index` pour le détail).

## Packs de sons

```{code-block} text
sounds/
  packs/
    classic/          # inclus dans le dépôt, libre de droits
      start.wav
      warning.wav
      end.wav
      emergency.wav
    _custom/          # gitignored — sons propres à chaque club
      start.wav
      ...
```

Le serveur n'envoie qu'un **identifiant d'événement** (`turn_start`, `warning_orange`,
`turn_end`, `emergency`) via WebSocket ; chaque écran résout localement le fichier
audio correspondant selon le pack actif, chargé une fois au démarrage. Aucun flux
audio ne transite par le réseau.

```{important}
Le dépôt public ne contient que des sons libres de droits. Les packs personnalisés
(y compris ceux réutilisant des œuvres protégées) restent la responsabilité de
chaque club et ne sont jamais commités dans le projet partagé avec la FFTL.
```

## Configuration multi-écrans

Chaque écran se connecte à `/display?lane=<n>` et reçoit uniquement l'état pertinent
pour son pas de tir (numéro de lane, distance, cible). Le poste de contrôle voit
l'ensemble des lanes et peut envoyer un message ciblé (une lane) ou global (toutes
les lanes).
