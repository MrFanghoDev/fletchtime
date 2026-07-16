# Packs de sons — comment en créer un

## Pour créer un pack utilisable

1. Crée un **nouveau dossier** ici, directement dans
   `web/assets/sounds/packs/` — donne-lui le nom que tu veux
   (ex. `mon_club`, `concours_fevrier`, peu importe).
2. Mets-y des fichiers portant **exactement** ces noms (extension `.mp3`,
   `.wav` ou `.ogg`) :

   - `prep_start` — début de la mise en place (rouge)
   - `shoot_start` — début du tir (vert)
   - `warning_orange` — passage à l'orange
   - `countdown_tick` — chaque seconde des dernières secondes du décompte
     (nombre configurable dans `config.html` → section "Son")
   - `emergency_start` — déclenchement de l'urgence
   - `emergency_end` — reprise après urgence
   - `end_of_volee` — fin de volée (récupération des flèches)
   - `pause_start` — mise en pause manuelle par le DOS
   - `pause_end` — reprise après une pause manuelle
   - `end_of_match` — fin de match (arrêt ou fin naturelle)

3. Ton dossier apparaît alors automatiquement dans `config.html` → section
   "Son" → liste déroulante. Sélectionne-le et enregistre.

Un événement sans fichier correspondant retombe automatiquement sur un bip
générique -- pas besoin de fournir les 10 sons d'un coup.

## Un seul pack par dossier

Chaque dossier sous `packs/` = un pack complet et indépendant. Si tu veux
plusieurs ambiances sonores (ex. une pour l'Indoor plus feutrée, une pour
le Flint plus franche), crée **plusieurs dossiers** distincts
(`packs/indoor_douce/`, `packs/flint_franc/`, etc.) et bascule de l'un à
l'autre dans `config.html` selon le concours -- il n'y a qu'un seul pack
actif à la fois pour toute l'application.

## Le pack "classic"

Fourni avec FletchTime (généré par synthèse, donc libre de droits) --
regarde son contenu (`packs/classic/`) comme exemple si tu veux t'en
inspirer pour créer le tien.

## Rien de personnalisé n'est versionné

Seuls `classic/` et ce README sont fournis avec FletchTime. N'importe quel
autre dossier que tu crées ici reste uniquement sur ton appareil, jamais
poussé vers le dépôt partagé.
