# Plan de développement

Approche incrémentale : chaque étape est utilisable seule, testable, et ne dépend
pas des étapes suivantes pour fonctionner en conditions réelles minimales.

## Étape 1 — Moteur de séquencement (Python pur, sans UI)

- Modélisation `MatchState`, `ShootingMode`.
- Implémentation `IndoorMode` (2 séries de 6 volées de 5 flèches).
- Implémentation `FlintMode` (volées standards + walk-up final).
- Tests unitaires couvrant les transitions de phase et les cas limites (incident
  matériel, arrêt d'urgence, correction manuelle du temps).

*Livrable : bibliothèque Python testée, utilisable en ligne de commande pour
valider le comportement avant d'ajouter le réseau.*

## Étape 2 — Serveur FastAPI + WebSocket

- Endpoint `/control` (contrôle basique : next/stop/urgence).
- Endpoint `/display?lane=n` (affichage brut, sans habillage).
- Diffusion de l'état en temps réel à tous les clients connectés.

*Livrable : chrono fonctionnel multi-écrans sur le réseau local, sans logo/pub/son.*

## Étape 3 — Écran d'affichage complet

- Affichage soigné (couleurs, typographie lisible à distance).
- Image de cible selon la distance/manche.
- Affichage ligne A-B/C-D.
- Overlay logo club / date-heure en phase neutre.

## Étape 4 — Interface de contrôle complète

- Presets de mode sélectionnables (Indoor, Flint) sans édition de fichier.
- Envoi de messages ponctuels (ciblés ou globaux).
- Upload logo / banderoles.

## Étape 5 — Son

- Packs de sons interchangeables.
- Sélecteur de pack + import de pack personnalisé via l'UI.

## Étape 6 — Documentation et packaging

- Manuel utilisateur (ce dépôt Sphinx/MyST), guide "premier concours" pas à pas.
- Guide développeur : comment ajouter un mode de tir.
- Script de lancement simplifié (voire exécutable packagé) pour un déploiement
  sans compétences techniques.

## Étape 7 — Partage FFTL

- Nettoyage, licence open source claire, README d'accueil.
- Contact fédération pour retour d'expérience / adoption éventuelle par d'autres
  clubs.

## Backlog — à discuter / non encore programmé dans une étape précise

- ~~**Revamping du logo**~~ -- fait : nouveau logo cadran/flèche noir-or-blanc,
  wordmark "FletchTime" bicolore Fletch/Time, cohérent avec le thème clair/sombre.
- **Sécurisation cyber** : le serveur WebSocket n'a actuellement aucune
  authentification -- n'importe qui sur le même réseau WiFi local peut se
  connecter et envoyer des commandes de contrôle (stop, urgence, etc.). Sans
  gravité tant que le réseau du concours est fermé/dédié, mais à documenter
  clairement (voire à durcir, ex. mot de passe simple sur `/control`) avant un
  partage plus large ou un usage sur un réseau moins maîtrisé.
- **Exécutable autoporteur** : livrer FletchTime en `.exe`/binaire autonome
  (Windows/macOS/Linux), en plus du parcours Pydroid actuel, pour les clubs
  qui préfèrent un PC dédié sans installer Python. Implique :
  - empaqueter `run_server.py` + `src/` + `web/` dans un seul exécutable
    (voir recommandation ci-dessous) ;
  - au premier lancement, créer automatiquement les dossiers/fichiers
    attendus chez l'utilisateur s'ils n'existent pas (`web/assets/club/`,
    `web/assets/banners/`, `web/assets/targets/`, `sounds/packs/_custom/`)
    -- aujourd'hui ces dossiers sont gitignorés et n'existent que si le club
    les a créés manuellement en suivant la doc ; un exécutable autoporteur ne
    doit pas dépendre de ça ;
  - documenter ce nouveau mode de déploiement dans le manuel utilisateur
    (étape 6), en plus du parcours Pydroid déjà couvert.
- **Web app côté client (PWA)** : transformer `control.html`/`display.html`
  (voire `index.html`) en Progressive Web App -- `manifest.json` + service
  worker + icônes. Permettrait d'"installer" l'app sur l'écran d'accueil
  d'une tablette/téléphone (lancement direct, sans retaper l'URL ni passer
  par le navigateur), et de mettre en cache les fichiers statiques (HTML/CSS/
  JS/logo) pour un chargement instantané même en cas de WiFi capricieux --
  le WebSocket, lui, resterait bien sûr en temps réel, seul l'habillage
  statique serait mis en cache. Chantier indépendant du reste, à ne traiter
  qu'une fois l'interface stabilisée.
