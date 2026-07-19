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

- ~~Licence open source claire~~ -- déjà en place : `LICENSE`
  (GPL-3.0-or-later), cohérent avec `pyproject.toml`.
- ~~Guide de contribution~~ -- fait : `CONTRIBUTING.md` (français/anglais),
  flux classique fork/branche/Pull Request, volontairement simple.
- Nettoyage : vérifier qu'aucun contenu spécifique au club (nom, logo,
  détails propres à Les Aigles 77) ne traîne en dur dans le code ou la
  doc, en dehors de `web/assets/` où c'est normal et attendu.
- Un vrai guide "premier club" : point d'entrée pour quelqu'un qui
  découvre l'outil sans le contexte déjà connu (c'est quoi, pourquoi
  l'utiliser, comment démarrer).
- Contact fédération pour retour d'expérience / adoption éventuelle par
  d'autres clubs -- démarche humaine, hors du champ du dépôt lui-même.

## Backlog — à discuter / non encore programmé dans une étape précise

- **Fenêtre graphique -- améliorations restant à faire** :
  - Paramétrage du serveur (ports, etc.) et de l'adresse IP exposée sur le
    réseau local, directement depuis la fenêtre plutôt que fichiers de
    config seuls.
  - Affichage des adresses exposées (accueil/contrôle/affichage) dans la
    fenêtre elle-même, pas seulement via les boutons de raccourci
    actuels.
  - Choix du thème clair/sombre dans la fenêtre -- actuellement forcé en
    sombre (`ctk.set_appearance_mode("dark")`), cohérent avec
    `display.html` mais pas ajustable par l'utilisateur comme le sont les
    autres pages web.
  - Couleur du bouton Quitter à revoir (actuellement neutre/transparent).
- ~~**Récupération après plantage/redémarrage du serveur**~~ -- fait :
  `MatchServer` persiste un instantané JSON de l'état du match
  (`config/match_state.json`, jamais versionné) à chaque commande qui
  change l'état et périodiquement pendant le décompte, et tente une
  restauration silencieuse à la construction -- avant ça, un plantage en
  plein match perdait toute la progression (série, volée, temps écoulé).
  Voir {doc}`architecture`, section dédiée, pour le détail complet
  (écriture atomique, repli silencieux sur un démarrage normal si la
  reprise échoue).
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
  `.github/workflows/build.yml` construisent automatiquement un `.zip`
  Windows et un `.tar.gz` Linux à chaque tag de version (`git tag v0.1.0 &&
  git push --tags`), publiés en Release GitHub. `fletchtime/__main__.py`
  détecte le mode empaqueté (`sys.frozen`) et crée/pré-remplit
  automatiquement au premier lancement les dossiers attendus
  (`web/assets/club/`, `banners/`, `targets/`, `sounds/packs/`) s'ils
  manquent -- avec un vrai contenu par défaut pour les blasons et le pack
  de sons "classic". **macOS retiré de la matrice** après plusieurs
  tentatives de correction infructueuses sur un bug d'empaquetage
  reproductible (`ModuleNotFoundError` au lancement, cause exacte jamais
  confirmée) -- voir le détail de l'investigation dans
  {doc}`dev-guide/index`. Pas de besoin utilisateur macOS avéré à ce jour ;
  à reconsidérer si ça change.
- **Web app côté client (PWA)** : transformer `control.html`/`display.html`
  (voire `index.html`) en Progressive Web App -- `manifest.json` + service
  worker + icônes. Permettrait d'"installer" l'app sur l'écran d'accueil
  d'une tablette/téléphone (lancement direct, sans retaper l'URL ni passer
  par le navigateur), et de mettre en cache les fichiers statiques (HTML/CSS/
  JS/logo) pour un chargement instantané même en cas de WiFi capricieux --
  le WebSocket, lui, resterait bien sûr en temps réel, seul l'habillage
  statique serait mis en cache. Chantier indépendant du reste, à ne traiter
  qu'une fois l'interface stabilisée.
- **Documentation Sphinx versionnée** : `docs.yml` publie aujourd'hui une
  seule version de la doc sur GitHub Pages, écrasée à chaque nouveau tag
  (voir plus bas pourquoi ce n'est plus à chaque push depuis peu) -- pas
  de moyen de consulter la doc telle qu'elle était pour une release
  précédente (ex. v0.1.2) si le code a changé depuis. À terme : une doc
  par tag de version (ex. `/v0.1.2/`, `/v0.1.3/`) en plus d'une version
  `/latest/`, avec un sélecteur de version dans le thème Furo (voir
  `sphinx-multiversion` ou équivalent).
