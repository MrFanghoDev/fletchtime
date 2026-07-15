# Pack de sons personnalisé

Pour créer un pack perso, copie ce dossier `_custom/` (ou crée-en un autre à
côté, ex. `mon_club/`) et remplis-le avec des fichiers portant **exactement**
ces noms (extension `.mp3`, `.wav` ou `.ogg`) :

- `prep_start` — début de la mise en place (rouge)
- `shoot_start` — début du tir (vert)
- `warning_orange` — passage à l'orange
- `countdown_tick` — chaque seconde des 5 dernières secondes
- `emergency_start` — déclenchement de l'urgence
- `emergency_end` — reprise après urgence
- `end_of_volee` — fin de volée (récupération des flèches)
- `end_of_match` — fin de match (arrêt ou fin naturelle)

Un événement sans fichier correspondant retombe automatiquement sur un bip
générique -- pas besoin de fournir les 8 sons d'un coup.

Sélectionne ensuite ce pack dans `config.html` → section "Son".
