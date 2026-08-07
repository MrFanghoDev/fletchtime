# Instructions pour Claude sur FletchTime

Ce fichier condense les règles techniques et les leçons spécifiques à
FletchTime. Pour notre façon de travailler ensemble (commune aux trois
projets frères -- fletchapps/fletchscore/fletchtime), voir le `CLAUDE.md`
global (`~/.claude/CLAUDE.md`), toujours chargé automatiquement.

Ce fichier remplace une version antérieure qui existait (fletchscore
s'en réclame comme référence dans son propre `CLAUDE.md`) mais n'avait
jamais été committée dans ce dépôt -- reconstitué à partir du code, de
`docs/dev-guide/index.md` et du `CLAUDE.md` de FletchScore, adapté aux
spécificités réelles de ce projet-ci.

## Contexte en une phrase

FletchTime est le chronométreur de compétitions d'archerie FFTL (Indoor,
Flint), indépendant de FletchScore : un serveur (`websockets` + HTTP)
piloté par une fenêtre graphique (customtkinter, repli automatique en
mode `--headless` si absente), déployé sur un réseau local multi-écrans.

## Conventions techniques

- **Pas de dépendance ajoutée à la légère.** Toute nouvelle dépendance
  doit fonctionner de façon fiable sur Pydroid 3 (Android) -- contrainte
  réelle du club (pas de PC disponible à l'origine du projet). C'est ce
  qui explique `websockets` plutôt que FastAPI/uvicorn, et `tomllib`
  (stdlib depuis 3.11) plutôt que PyYAML pour la config.
- **Tout en français** : docstrings dans le code source (`src/`) comme
  commentaires utilisateur (fichiers TOML, README destinés au club).
  Ancienne règle "docstrings en anglais" abandonnée le 2026-08-06 (même
  décision que côté FletchScore, voir son CLAUDE.md) -- incohérente avec
  le reste du projet déjà tout en français. Le module `engine/` (et une
  partie de `server/`) garde ses docstrings existantes en anglais, pas de
  reprise rétroactive ; nouvelles docstrings partout en français
  désormais, y compris dans `engine/`.
- **Un test qui échoue avant livraison n'est pas un problème** -- c'est le
  système qui fonctionne. Ne jamais contourner un test qui échoue sans
  comprendre pourquoi.
- `tkinter`/`customtkinter` **non installés par défaut** dans
  l'environnement de travail habituel -- même précaution que pour
  FletchScore : tout module qui doit rester testable sans eux doit
  pouvoir s'importer sans eux (repli `--headless` déjà prévu par le
  code, `fletchtime.gui` importé en
  `try/except` dans `main()`).
- **Deux ports réseau séparés et tous deux nécessaires** : 8000 HTTP,
  8765 WebSocket. Dans un conteneur/VM, les deux doivent être exposés --
  sans le port WS, les pages se chargent mais restent bloquées sur "en
  attente de connexion" indéfiniment.
- Ajouter un nouveau mode de tir = une nouvelle classe `ShootingMode`
  (voir `docs/dev-guide/index.md`, section correspondante) -- pas de
  dispatch par chaînes de caractères éparpillé (c'est précisément ce qui
  rendait l'ancien logiciel de référence, ArcheryClock, difficile à
  maintenir -- raison d'être de la réécriture).

## Pièges déjà documentés (voir `docs/dev-guide/index.md` pour le détail)

- **PyInstaller 6.0+ / `--onedir`** place le contenu dans `_internal/`
  par défaut ; le code suppose l'ancien layout plat --
  `fletchtime.spec` restaure ça via `contents_directory="."`. Symptôme
  si ce paramètre disparaît : le serveur démarre normalement mais
  naviguer vers son adresse (même `127.0.0.1` en local) n'affiche qu'un
  listing de `assets/` -- pas un problème réseau/pare-feu malgré les
  apparences.
- **PyInstaller + `customtkinter`** : thèmes/polices ne sont pas
  détectés automatiquement comme données de paquet -- `fletchtime.spec`
  les inclut via `collect_data_files("customtkinter")`. Sans ça,
  l'exécutable construit sans erreur mais plante au lancement de la
  fenêtre.
- **macOS retiré de la matrice de build** après plusieurs corrections
  infructueuses sur un `ModuleNotFoundError: No module named
  'fletchtime.runtime'` reproductible uniquement sur macOS/ARM64 (pistes
  non résolues : re-signature ad-hoc de l'exécutable par PyInstaller).
  Ne pas réintroduire macOS sans accès à une vraie machine pour tester.
  Installation macOS actuelle : `pip install fletchtime` uniquement.
  Risque associé à garder en tête : le même défaut sur
  `fletchtime.gui` (importé en `try/except`) échouerait silencieusement
  sur toutes les plateformes, pas seulement macOS.

## Publication (PyPI/TestPyPI)

Se fait par **trusted publishing** (OIDC GitHub Actions <-> PyPI, pas de
token API stocké en secret GitHub) -- confirmé par l'utilisateur
2026-08-06, cohérent avec `gh secret list` qui ne montre aucun secret
sur ce dépôt.

## Vérifications spécifiques avant de livrer

En plus de la checklist générique (voir le `CLAUDE.md` global) :

- Mettre à jour `docs/roadmap.md` et `docs/architecture.md` si le
  changement touche à un mécanisme déjà documenté.
- GUI (customtkinter) -- capture d'écran réelle ou scénario réel
  (possible depuis le 2026-08-07 même sans écran physique, voir le
  `CLAUDE.md` global section Environnement -- `apk add python3-tkinter
  tk xvfb xdotool scrot` + `Xvfb`) ; pages web servies (contrôle,
  affichage) -- Playwright ou vérification réseau réelle (les deux
  ports, pas juste HTTP), pas une relecture du HTML/JS/CSS.
- Nettoyage particulier à ce dépôt (voir `.gitignore` pour la liste
  complète et le pourquoi de chaque exclusion) : `config/auth.toml`
  (secret réel), `config/gui.toml` et `config/match_state.json`
  (propres à une machine/session), `web/assets/club/`,
  `web/assets/targets/`, `web/assets/banners/`,
  `web/assets/sounds/packs/*` (assets réels d'un club -- jamais dans le
  dépôt public).

## Erreurs déjà commises, à ne pas répéter

- **`build.yml::build-executables` excluait `release`, même bug que
  FletchScore.** Corrigé le 2026-08-06 sans attendre un vrai incident ici
  (contrairement à FletchScore où le bug a été détecté après coup, en
  vérifiant la cohérence entre les trois dépôts frères) : le job supposait
  qu'une Release GitHub arrive toujours dans la même exécution CI que le
  push du tag correspondant -- faux si la Release est publiée séparément
  (via l'UI) après coup sur un tag déjà poussé. Dans ce cas,
  `build-executables` restait skip, et `archive-on-release` (qui en
  dépend via `needs:`) aussi -- silencieusement, sans erreur dans les
  logs. `archive-on-release` avait le même souci (condition uniquement sur
  `refs/tags/v`, sans le OR sur `event_name == 'release'`). Alignés tous
  les deux sur la version corrigée de FletchScore. Non vérifié en
  exécution réelle (impossible de déclencher une vraie Release GitHub
  dans cet environnement) -- à confirmer à la prochaine Release publiée
  séparément d'un push de tag.
