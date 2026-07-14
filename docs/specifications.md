# Spécifications fonctionnelles

## Contexte

Le club organise chaque année en février un concours officiel FFTL comprenant :

- **2 manches Indoor** : chacune composée de 2 séries de 6 volées de 5 flèches.
- **1 manche Flint** : composée de 2 séries suivant les règles Flint FFTL (voir ci-dessous).

Le logiciel doit gérer le chronométrage et l'affichage pour ces deux types de manches,
avec une architecture assez générique pour accueillir d'autres modes FFTL/World Archery
par la suite.

## Règles du round Flint (rappel)

Une **unité standard** consiste en 7 manches de 4 flèches, tirées à 7 distances
différentes (20 pieds, 10, 15, 20, 25, 30 yards + une volée finale). Un **parcours**
Flint = 2 unités standards.

Point structurant pour le chronométrage : les volées suivent deux régimes de temps
différents :

- **Volées standards** : temps fixe par volée (à paramétrer, ex. 3 minutes / 4 flèches),
  une seule distance par volée.
- **Volée finale ("walk-up")** : 4 flèches à 4 distances différentes, **45 secondes par
  flèche**, tout le groupe avance ensemble entre chaque flèche.

Les archers tirent en alternance sur deux couloirs (cibles inversées entre couloirs
adjacents), avec rotation A-B / C-D selon la position de départ (cible du haut ou du bas).

## Exigences fonctionnelles

### Chronométrage

- Configuration du temps par volée, par mode (Indoor / Flint standard / Flint walk-up).
- Trois phases visuelles : attente (rouge), tir (vert), fin de tir imminente (orange).
- Gestion de la séquence walk-up Flint : 4 comptes à rebours de 45s enchaînés
  automatiquement, avec signal entre chaque flèche.
- Gestion des lignes de rotation A-B / C-D avec affichage clair du côté actif.
- Bouton d'urgence (arrêt immédiat, signal visuel/sonore dédié).
- Correction manuelle du temps restant (cas d'incident matériel, cf. règlement FFTL).

### Affichage (par pas de tir / lane)

Chaque écran affiche a minima :

- Le temps restant, avec code couleur.
- La ligne en cours de tir (A-B ou C-D).
- Le type de cible en cours (image : blason 20 cm, 35 cm, etc. selon la distance/manche).
- Le nom du pas de tir / lane.
- La distance ou le libellé de la volée en cours.

En dehors des phases de tir actif (attente entre manches, avant le début du concours) :

- Logo du club (permanent ou plein écran selon configuration).
- Date et heure courantes.
- Messages ponctuels envoyés par le DOS.
- Banderoles publicitaires, uniquement pendant les phases neutres (jamais pendant le tir).

### Son

- Packs de sons interchangeables (buzzer classique inclus par défaut, packs personnalisés
  possibles côté club, non versionnés dans le dépôt public pour raisons de droits d'auteur).
- Association configurable événement → son (début de tir, alerte orange, fin de tir,
  urgence).

### Configuration / administration

- Paramétrage sans édition de fichier : presets de mode (Indoor, Flint) sélectionnables
  depuis l'interface de contrôle.
- Upload du logo du club, des banderoles, des packs de sons via formulaire.
- Utilisable par une personne non-développeuse (bénévole du club, arbitre).

### Multi-écrans

- Un service centralisé pilote l'état de la compétition.
- N'importe quel navigateur sur le réseau local peut devenir un écran d'affichage,
  synchronisé en temps réel avec les autres.
- Le poste de contrôle (DOS) et un écran peuvent cohabiter sur le même appareil si besoin.

## Hors périmètre (pour l'instant)

- Pilotage de matériel physique (feux tricolores, buzzer externe Arduino/GPIO) — non
  nécessaire pour ce club, mais l'architecture ne doit pas l'exclure définitivement.
- Gestion des scores / feuilles de marque (hors sujet chronométrage).
- Accès distant hors réseau local (pas de cloud, tout doit fonctionner sans Internet).
