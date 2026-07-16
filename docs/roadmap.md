# Plan de développement

Approche incrémentale : chaque étape est utilisable seule, testable, et ne dépend
pas des étapes suivantes pour fonctionner en conditions réelles minimales.

## ✅ Étape 1 — Moteur de séquencement (Python pur, sans UI)

- Modélisation `MatchState`, `ShootingMode`.
- Implémentation `IndoorMode` (2 séries de 6 volées de 5 flèches).
- Implémentation `FlintMode` (volées standards + walk-up final).
- Tests unitaires couvrant les transitions de phase et les cas limites (incident
  matériel, arrêt d'urgence, correction manuelle du temps).

*Livrable : bibliothèque Python testée, utilisable en ligne de commande pour
valider le comportement avant d'ajouter le réseau.*

## ✅ Étape 2 — Serveur temps réel

- Endpoint `/control` (contrôle basique : next/stop/urgence).
- Endpoint `/display?lane=n` (affichage brut, sans habillage).
- Diffusion de l'état en temps réel à tous les clients connectés.

*Livrable : chrono fonctionnel multi-écrans sur le réseau local, sans logo/pub/son.*

```{note}
Construit avec le paquet `websockets` (asyncio) + `http.server` stdlib, **pas
FastAPI** comme envisagé au tout début de ce plan -- FastAPI/Pydantic
dépendent d'extensions compilées (Rust/C) peu fiables sur Pydroid 3, voir
{doc}`../architecture`.
```

## ✅ Étape 3 — Écran d'affichage complet

- Affichage soigné (couleurs, typographie lisible à distance).
- Image de cible selon la distance/manche.
- Affichage ligne A-B/C-D.
- Overlay logo club / date-heure en phase neutre.

## ✅ Étape 4 — Interface de contrôle complète

- Presets de mode sélectionnables (Indoor, Flint) sans édition de fichier.
- Envoi de messages ponctuels (ciblés ou globaux).
- Logo / banderoles (dépôt de fichier + découverte automatique, pas de
  formulaire d'upload -- plus simple à construire et maintenir).

## ✅ Étape 5 — Son

- Packs de sons interchangeables.
- Sélecteur de pack + pack "classic" fourni par défaut.

## ✅ Étape 6 — Documentation et packaging

- Manuel utilisateur (dans l'appli) + doc technique Sphinx/MyST (specs,
  architecture, guide développeur), publiée sur GitHub Pages.
- Script de lancement simplifié **et** bien au-delà : paquet PyPI
  (`pip install fletchtime` + commande `fletchtime`), exécutables
  autoporteurs Windows/Linux, CI (lint + tests à chaque push).

## ⬜ Étape 7 — Partage FFTL

- Nettoyage, licence open source claire, README d'accueil.
- Contact fédération pour retour d'expérience / adoption éventuelle par d'autres
  clubs.

## Backlog — à discuter / non encore programmé dans une étape précise

- ~~**Revamping du logo**~~ -- fait : nouveau logo cadran/flèche noir-or-blanc,
  wordmark "FletchTime" bicolore Fletch/Time, cohérent avec le thème clair/sombre.
- ~~**Sécurisation cyber**~~ -- en partie fait : mot de passe optionnel
  (vide par défaut = comportement historique inchangé) protégeant les
  actions de contrôle et la sauvegarde de configuration, réglable dans
  `config.html` → section "Sécurité". Reste en HTTP simple, non chiffré
  (voir {doc}`../architecture`) -- suffisant pour un réseau de concours
  dédié/fermé, mais pas pour un réseau partagé avec le grand public. Pas de
  liste blanche d'IP ni de HTTPS envisagés pour l'instant (complexité jugée
  disproportionnée par rapport au risque réel pour ce projet).
- ~~**Exécutable autoporteur**~~ -- fait : `fletchtime.spec` (PyInstaller) +
  `.github/workflows/release.yml` construisent automatiquement un `.zip`
  Windows et un `.tar.gz` Linux à chaque tag de version (`git tag v0.1.0 &&
  git push --tags`), publiés en Release GitHub. `fletchtime/__main__.py`
  détecte le mode empaqueté (`sys.frozen`) et crée/pré-remplit
  automatiquement au premier lancement les dossiers attendus
  (`web/assets/club/`, `banners/`, `targets/`, `sounds/packs/`) s'ils
  manquent -- avec un vrai contenu par défaut pour les blasons et le pack
  de sons "classic". macOS non testé (pas de machine disponible) mais
  devrait fonctionner de la même façon via un runner `macos-latest` à
  ajouter à la matrice si besoin.
- **Web app côté client (PWA)** : transformer `control.html`/`display.html`
  (voire `index.html`) en Progressive Web App -- `manifest.json` + service
  worker + icônes. Permettrait d'"installer" l'app sur l'écran d'accueil
  d'une tablette/téléphone (lancement direct, sans retaper l'URL ni passer
  par le navigateur), et de mettre en cache les fichiers statiques (HTML/CSS/
  JS/logo) pour un chargement instantané même en cas de WiFi capricieux --
  le WebSocket, lui, resterait bien sûr en temps réel, seul l'habillage
  statique serait mis en cache. Chantier indépendant du reste, à ne traiter
  qu'une fois l'interface stabilisée.
