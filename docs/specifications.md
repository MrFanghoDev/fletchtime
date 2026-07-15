# Spécifications fonctionnelles

## Contexte

Le club organise chaque année en février un concours officiel FFTL comprenant :

- **2 manches Indoor** : chacune composée de 2 séries de 6 volées de 5 flèches, à
  20 yards (règle IFAA).
- **1 manche Flint** : composée de 2 unités standards (= 1 parcours), selon les
  règles Flint FFTL (voir ci-dessous).

Le logiciel gère le chronométrage et l'affichage pour ces deux types de manches,
avec une architecture générique (un mode = une classe) pensée pour accueillir
d'autres modes FFTL/World Archery par la suite sans toucher aux modes existants.

## Règles de l'Indoor (rappel)

- 2 séries de 6 volées de 5 flèches, 20 yards, 4 minutes de tir par volée
  (240s, passage à l'orange dans les 30 dernières secondes), 10s de mise en place
  avant chaque volée.
- Les archers tirent en deux relais (A-B et C-D) qui partagent le même blason :
  les deux relais tirent **la même volée** (le numéro ne change pas entre eux),
  seul le tireur actif change. Le numéro de volée n'incrémente qu'une fois les
  deux relais passés.
- L'ordre des relais (A-B puis C-D, ou l'inverse) est configurable, et alterne
  automatiquement d'une série à l'autre par défaut (série 1 : A-B puis C-D ;
  série 2 : C-D puis A-B) — comportement désactivable.
- Deux blasons affichés simultanément à l'écran (recourbe/trad et poulies),
  côte à côte, puisque les deux catégories tirent souvent ensemble.

## Règles du round Flint (rappel)

Une **unité standard** consiste en 7 manches de 4 flèches : 6 volées standards à
distance fixe (25 yards, 20 pieds, 30 yards, 15 yards, 20 yards, 10 yards, dans
cet ordre précis — celui des lignes de tir réelles, pas un ordre croissant) plus
une **volée finale walk-up** (4 flèches à 4 distances différentes, décroissantes :
30, 25, 20, 15 yards). Un **parcours** Flint = 2 unités standards.

Points structurants pour le chronométrage :

- **Volées standards** : 180s de tir continu (3 min), passage à l'orange dans
  les 20 dernières secondes, 10s de mise en place avant chacune.
- **Volée walk-up** : 45 secondes par flèche, 10s de mise en place avant
  chaque flèche, passage à l'orange dans les 10 dernières secondes — le groupe
  avance ensemble entre chaque flèche, sans pause de récupération entre elles
  (contrairement aux volées standards, où on récupère les flèches à chaque fois).
- **Blason** : alterne selon la parité de la volée — 1 spot (35cm) pour les
  volées impaires (1, 3, 5, et la volée 7/walk-up), 4 spots (20cm) pour les
  volées paires (2, 4, 6).
- **Relais A-B/C-D** : contrairement à l'Indoor, un relais tire l'**unité
  entière** (les 7 volées) avant que l'autre relais ne reprenne la même unité
  depuis le début — pas d'alternance au sein d'une volée (pas de place pour
  deux blasons par ligne de tir, changer de tireur à chaque volée serait
  dangereux). L'ordre alterne par défaut d'une unité à l'autre, comme pour
  l'Indoor.

## Exigences fonctionnelles

### Chronométrage

- Décompte continu par volée (pas deux minuteurs qui s'enchaînent) : le temps
  affiché ne redémarre ni ne saute jamais, seule la couleur change au passage
  du seuil d'alerte (orange).
- Phases visuelles : mise en place (rouge), tir (vert puis orange), pause de
  fin de volée (récupération des flèches, décompte à l'arrêt), urgence.
- Séquence walk-up Flint : 4 flèches enchaînées automatiquement (45s chacune),
  sans pause entre elles.
- Commandes DOS : avancer manuellement (Next), mettre en pause temporairement
  et reprendre, arrêter le match, recommencer depuis le début, aller
  directement à une volée précise (utile en cas d'erreur ou d'incident).
- Urgence : arrêt immédiat, décompte figé, reprise avec possibilité de
  corriger le temps restant (cf. règlement FFTL sur les défaillances
  matérielles).
- Tous les réglages (temps, distances, nombre de volées/flèches, images de
  cible) sont configurables sans toucher au code (voir Configuration).

### Affichage (par pas de tir / lane)

Chaque écran affiche :

- Le temps restant, avec code couleur, et le relais actif (A-B / C-D ou
  numéro de flèche pour le walk-up).
- Série et volée distinctement (pas un compteur global qui grimperait jusqu'à
  12 pour l'Indoor par exemple).
- Le blason de la volée en cours : deux images côte à côte pour l'Indoor
  (recourbe/trad et poulies), une seule pour le Flint (alternance 1 spot/4
  spots selon la parité de la volée).
- Le numéro du pas de tir et un titre d'événement permanent (choisi par le
  DOS, ex. "Concours FFTL Indoor — Février 2026").

En dehors des phases de tir actif (avant le concours, après sa fin, en cas de
déconnexion réseau) : un **écran neutre unique et cohérent** — logo du club et
horloge en direct, sans texte superflu (les messages du DOS restent
indépendants et s'affichent par-dessus si besoin). Un diaporama alterne
automatiquement cet écran neutre avec des bannières sponsors déposées par le
club, jamais pendant le tir actif.

L'interface est bilingue (français/anglais, choix du DOS, appliqué à tous les
écrans) et propose un thème clair/sombre (suit la préférence système ou choix
explicite).

### Son

- Système de packs de sons interchangeables : un pack = un dossier
  (`web/assets/sounds/packs/<nom>/`) contenant un fichier par événement,
  nommé exactement comme l'événement (`.wav`, `.mp3` ou `.ogg`).
- Pack "classic" fourni par défaut (généré par synthèse, libre de droits) ;
  les clubs peuvent créer autant de packs personnalisés qu'ils veulent, non
  versionnés dans le dépôt public.
- Un événement sans fichier correspondant retombe automatiquement sur un bip
  générique — pas besoin de fournir tous les sons d'un coup.
- 10 événements distincts : début de mise en place, début de tir, passage à
  l'orange, décompte des 5 dernières secondes, fin de volée, pause/reprise
  manuelle du DOS, urgence/fin d'urgence, fin de match.
- Réglage global (pas par mode) : un seul pack actif à la fois pour toute
  l'application, changement pris en compte immédiatement sur tous les écrans
  déjà connectés.

### Configuration / administration

- Paramétrage sans édition de code : fichiers TOML lisibles
  (`config/indoor.toml`, `config/flint.toml`, `config/app.toml`), modifiables
  à la main ou via une page dédiée (`config.html`) qui lit les valeurs
  actuelles et écrit le fichier à l'enregistrement.
- Impossible de modifier la configuration d'un mode (Indoor ou Flint) tant
  qu'un match de ce même mode est en cours (actif, en pause, ou en urgence) —
  évite de changer les règles d'une compétition en plein déroulement.
- Logo du club, bannières sponsors et images de cible : dépôt manuel de
  fichiers dans les dossiers prévus (`web/assets/club/`, `web/assets/banners/`,
  `web/assets/targets/`), détection automatique par le serveur (listing de
  répertoire), sans upload à construire.
- Utilisable par une personne non-développeuse (bénévole du club, arbitre).

### Multi-écrans

- Un service centralisé pilote l'état de la compétition et diffuse à tous
  les clients connectés.
- N'importe quel navigateur sur le réseau local peut devenir un écran
  d'affichage via `/display.html?lane=<n>`, synchronisé en temps réel.
- Le poste de contrôle voit quels pas de tir sont effectivement connectés, et
  peut envoyer un message à tous les écrans ou à un seul en particulier.
- Le poste de contrôle (DOS) et un écran peuvent cohabiter sur le même
  appareil (miniature d'aperçu en direct intégrée à l'interface de contrôle).

## Hors périmètre (pour l'instant)

- Pilotage de matériel physique (feux tricolores, buzzer externe Arduino/GPIO) —
  non nécessaire pour ce club, mais l'architecture ne l'exclut pas.
- Gestion des scores / feuilles de marque (hors sujet chronométrage).
- Accès distant hors réseau local (pas de cloud, tout fonctionne sans Internet).
- Authentification sur le serveur WebSocket (n'importe qui sur le même WiFi
  peut actuellement envoyer des commandes de contrôle) — noté en backlog,
  voir `docs/roadmap.md`.
- Exécutable autoporteur (Windows/Mac/Linux) et web app installable (PWA) —
  idées notées en backlog, pas encore programmées dans une étape.
