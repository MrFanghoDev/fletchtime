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

## ✅ Étape 7 — Partage FFTL (hors contact fédération, démarche humaine)

- ~~Licence open source claire~~ -- déjà en place : `LICENSE`
  (GPL-3.0-or-later), cohérent avec `pyproject.toml`.
- ~~Guide de contribution~~ -- fait : `CONTRIBUTING.md` (français/anglais),
  flux classique fork/branche/Pull Request, volontairement simple.
- ~~Nettoyage~~ -- fait : balayage complet du dépôt, aucun contenu
  spécifique au club trouvé en dehors de `web/assets/` (normal et
  attendu là). Un vrai souci trouvé au passage, mais côté livraison
  plutôt que dans le dépôt lui-même : un logo de club réel se
  retrouvait dans les archives livrées malgré son exclusion de git --
  corrigé.
- ~~Guide "premier club"~~ -- fait : {doc}`premier-club`, point d'entrée
  pour quelqu'un qui découvre l'outil sans contexte préalable (c'est
  quoi, pourquoi s'en servir, prérequis, premiers pas, peut-on lui faire
  confiance, où chercher de l'aide).
- Contact fédération pour retour d'expérience / adoption éventuelle par
  d'autres clubs -- démarche humaine, hors du champ du dépôt lui-même.

## Backlog — à discuter / non encore programmé dans une étape précise

- ~~**Titre de l'événement en haut à droite**~~ -- fait : repositionné de
  centré à aligné à droite, en miroir de `#lane` (haut à gauche). Un
  premier essai (juste déplacer le titre) restait insuffisant : avec un
  titre long et un écran bas, le contenu centré verticalement (dont les
  images de cible) pouvait quand même chevaucher le titre -- détecté en
  testant rigoureusement les rectangles réels plutôt qu'en supposant que
  le repositionnement suffisait. Corrigé en réservant une bande fixe en
  haut de l'écran (`padding-top` sur `#root`) que le contenu centré ne
  peut plus chevaucher, quelle que soit la longueur du titre ou la
  hauteur de l'écran. Testé sur 4 combinaisons (écran large/bas, titre
  long/court) : plus aucun chevauchement. S'applique aussi à l'aperçu de
  la page de contrôle, un simple redimensionnement proportionnel du même
  `display.html`.

- ~~**Couleur orange trop marron**~~ -- fait : `#78350f` remplacé par
  `#b45309` -- plus saturé et plus lumineux, se lit comme un vrai orange
  plutôt qu'un brun terne, tout en restant cohérent avec la noirceur du
  rouge/vert déjà en place. Vérifié avec un vrai rendu (Chromium), pas
  seulement en théorie.
- ~~**Cibles par défaut en SVG**~~ -- fait, avec une vraie erreur en
  route corrigée : premier essai généré à partir de proportions World
  Archery génériques (blanc/noir/bleu/rouge/or) plutôt que des vraies
  images de référence pourtant déjà vues -- alors que les cibles réelles
  sont bleu marine (indoor) et noir/blanc alterné style NFAA/IFAA
  (Flint), rien à voir avec le motif WA. Corrigé en utilisant les 4 SVG
  faits à la main par le club (Inkscape), qui reproduisent fidèlement les
  vraies cibles. `.svg` ajouté aussi à la détection des bannières
  (`display.html`), pour la cohérence. Testé avec un vrai rendu de
  `display.html` : les deux images se chargent et s'affichent
  correctement.

- ~~**Choix de la lane/muet à l'ouverture d'un écran**~~ -- fait : la page
  d'accueil permet maintenant de cocher "muet" à côté du champ de lane
  déjà existant (ex. plusieurs écrans pilotés par le même PC, qui
  partagent le même haut-parleur -- voir la FAQ du manuel). Même chose
  dans la fenêtre graphique : le raccourci "Affichage", auparavant figé
  sur `lane=1`, permet maintenant de choisir la lane et de cocher "muet"
  avant l'ouverture. Testé avec un vrai navigateur (page d'accueil) et
  vérifié via la documentation officielle de `customtkinter` (case à
  cocher, fenêtre).

- ~~**Icône de l'exécutable**~~ -- fait : `web/logo.ico` (multi-résolution,
  16 à 256px, généré depuis `web/logo.svg`), utilisé par `fletchtime.spec`
  pour l'exécutable Windows. Sans effet sous Linux, qui n'a pas ce
  concept de métadonnées d'icône pour un simple binaire (vérifié). Le
  favicon des pages web était en fait déjà en place, rien à faire là.
- ~~**Son dupliqué sur plusieurs onglets**~~ -- fait : l'aperçu de
  `control.html` (une vraie instance de `display.html` en iframe) ne
  joue plus jamais de son -- c'est une simple vue visuelle, pas un écran
  destiné aux archers. `?mute=1` permet en plus de couper le son sur
  n'importe quel autre onglet ouvert en trop sur le même PC.
- ~~**Chrono figé (sous Windows, pas lié au focus en réalité)**~~ --
  cause la plus probable identifiée : sous Windows, remplacer un fichier
  peut échouer avec une "violation de partage" si un autre processus l'a
  ouvert au même instant (antivirus, surveillance de fichiers d'un
  IDE...) -- observé une fois en pratique, précisément sur
  `config/match_state.json`, écrit à chaque tick depuis la persistance
  après plantage. Sans gestion d'erreur, ça tuait silencieusement
  `tick_loop` pour de bon -- exactement le symptôme rapporté (gel
  permanent, pas de déconnexion, se produisant aussi bien en GUI qu'en
  headless, sans lien réel avec le focus). Deux correctifs : `tick_loop`
  capture désormais toute exception imprévue en son sein (journalisée
  avec sa trace complète, ne meurt plus silencieusement) et
  `save_match_snapshot` retente quelques fois avant d'abandonner
  proprement (jamais d'exception qui remonterait perturber la diffusion
  de l'état aux écrans). Testé concrètement : échec transitoire récupéré,
  échec permanent absorbé sans lever. **Confirmé résolu en conditions
  réelles sur Windows** (plus de blocage constaté après ce correctif).
- ~~**Bouton Quitter hors de la fenêtre**~~ -- fait : la taille de départ
  de la fenêtre datait d'avant l'ajout de plusieurs sections (ports,
  statut technique...), devenue trop petite pour tout montrer. Calcule
  désormais la taille réellement nécessaire à partir du contenu construit
  (`update_idletasks` + `winfo_reqheight`/`reqwidth`), plutôt qu'un
  nombre fixe qui redeviendrait insuffisant à la prochaine section
  ajoutée. **Réserve honnête** : ce motif est standard en Tkinter, mais
  une source a signalé un comportement parfois différent avec
  `customtkinter` selon si on l'applique à la fenêtre ou à un cadre
  interne -- non vérifiable ici (pas d'affichage disponible), à confirmer
  visuellement.
- ~~**Journal absent du widget de la fenêtre**~~ -- vrai bug trouvé en
  creusant le point précédent : `configure_logging` était appelé sans
  préciser `console_level`, retombant sur le défaut `WARNING` (pensé
  pour un terminal silencieux) -- qui filtrait justement tout ce que ce
  widget est censé montrer (commandes, connexions, transitions, toutes
  en `INFO`). Corrigé avec `console_level=INFO` explicite pour la
  fenêtre. Confirmé par comparaison directe avant/après : file vide
  avant, message présent après. **Confirmé résolu en conditions
  réelles** (le bon niveau de journal s'affiche bien dans la fenêtre).
- ~~**Données techniques dans la fenêtre**~~ -- fait : nouvel endpoint
  `/api/status` (les mêmes données déjà affichées dans `control.html`),
  affiché dans la fenêtre via sondage périodique. `ServerRuntime`
  construit maintenant le `MatchServer` une seule fois et le partage
  entre les deux serveurs, plutôt que d'en laisser `run_ws_server` créer
  un nouveau à chaque démarrage.


- ~~**Remerciements**~~ -- structure prête, à compléter : `REMERCIEMENTS.md`
  (modèle à remplir avec les noms), lié depuis le README et intégré à la
  doc Sphinx ({doc}`remerciements` -- même contenu, pas dupliqué, via une
  inclusion). Les membres du club ont aidé à tester et proposé des idées
  au fil du développement -- reste à toi d'ajouter les noms.

- ~~**Journal applicatif persistant**~~ -- fait : `MatchServer` journalise
  désormais chaque commande reçue, (dé)connexion, perte de connexion
  réseau et message malformé dans un fichier avec rotation
  (`logs/fletchtime.log`), en plus du journal déjà affiché dans la
  fenêtre (en mémoire, perdu à la fermeture). Voir {doc}`architecture`,
  section dédiée -- vérifié que le mot de passe ne s'y retrouve jamais.
- ~~**Fenêtre graphique -- améliorations**~~ -- toutes faites (paramétrage
  réseau, affichage des adresses, thème, couleur du bouton Quitter) :
  - ~~Paramétrage du serveur et de l'adresse IP exposée~~ -- fait :
    ports HTTP/WebSocket modifiables directement dans la fenêtre
    (`config/gui.toml`), avec redémarrage automatique du serveur si les
    ports changent pendant qu'il tourne. Objectif principal : plusieurs
    salles de compétition sur un même PC -- copier le dossier FletchTime
    une fois par salle (isole aussi `config/`, `logs/`, l'instantané de
    récupération, donc des urgences bien séparées), donner des ports
    différents à chaque copie, lancer chacune séparément. Testé
    concrètement : deux instances simultanées sur le même processus,
    ports différents, contenu totalement isolé entre les deux.
  - ~~Affichage des adresses exposées~~ -- fait : champ dédié (adresse
    d'accueil) dans la fenêtre elle-même, en plus des boutons de
    raccourci -- utile pour retaper l'adresse à la main sur un appareil
    sans bouton de raccourci. Non vérifié visuellement si le texte reste
    bien sélectionnable/copiable une fois le champ désactivé (`CTkEntry`
    n'a pas de vrai état "readonly" contrairement à `ttk.Entry`).
  - ~~Choix du thème clair/sombre dans la fenêtre~~ -- fait : sélecteur
    Système/Clair/Sombre dans l'en-tête, préférence persistée dans
    `config/gui.toml` (jamais versionné, propre à la machine -- voir
    `.gitignore`). Indépendant de `display.html`, qui reste lui, par
    choix délibéré, toujours sombre.
  - ~~Couleur du bouton Quitter à revoir~~ -- fait : couleur pleine
    (`#3a4354`) au lieu de transparent+contour, visible sans être
    alarmante (distincte du rouge d'Arrêter et du doré de Démarrer).
- ~~**Récupération après plantage/redémarrage du serveur**~~ -- fait et
  **confirmé en conditions réelles avec la v0.2.0** (synchronisation du
  temps testée, plus de retour en arrière du chrono ; reconnexion
  vérifiée) : `MatchServer` persiste un instantané JSON de l'état du
  match (`config/match_state.json`, jamais versionné) à chaque commande
  qui change l'état et périodiquement pendant le décompte, et tente une
  restauration silencieuse à la construction -- avant ça, un plantage en
  plein match perdait toute la progression (série, volée, temps écoulé).
  Voir {doc}`architecture`, section dédiée, pour le détail complet
  (échéance en horloge murale pour un temps exact quelle que soit la
  durée de l'indisponibilité, écriture atomique, repli silencieux sur un
  démarrage normal si la reprise échoue).
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
- ~~**Web app côté client (PWA)**~~ -- abandonné délibérément : pas jugé
  utile pour l'usage réel du club. (Aurait transformé
  `control.html`/`display.html` en Progressive Web App -- installation
  sur écran d'accueil, mise en cache des fichiers statiques.)
- ~~**Documentation Sphinx versionnée**~~ -- abandonné délibérément : les
  archives `.tar.gz` jointes à chaque Release GitHub suffisent pour
  consulter la doc d'une version précédente, pas besoin d'un système de
  versionnage complet côté GitHub Pages.
- ~~**Termux / lancer FletchTime sur Android sans Pydroid**~~ -- abandonné
  délibérément pour l'instant : usage réel actuel = téléphone en simple
  client (accès réseau local), PC pour héberger le serveur. Pas de besoin
  d'exécuter le serveur lui-même sur Android dans ces conditions. À
  reconsidérer si l'usage change.
