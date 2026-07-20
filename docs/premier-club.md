# Découvrir FletchTime pour son club

Cette page s'adresse à quelqu'un qui découvre FletchTime pour la première
fois -- un⋅e archer⋅ère, un⋅e responsable de club, quelqu'un qui a
entendu parler de l'outil via la fédération. Pas besoin de connaître quoi
que ce soit du projet au préalable.

## C'est quoi

FletchTime est un logiciel de chronométrage pour les compétitions
d'archerie FFTL (Indoor et Flint) : il gère le décompte du temps de tir,
les phases de préparation et de repos, les sons qui rythment le
concours, sur autant d'écrans que nécessaire. Gratuit, open source, né
de l'usage réel d'un club puis partagé avec la fédération.

## Pourquoi s'en servir

- **Un écran par pas de tir**, pas juste un chrono près du starter --
  chaque archer voit le temps restant sans avoir à se retourner.
- **Les sons rythment le concours tout seuls** (début de préparation,
  passage à l'orange, fin de volée...) -- plus besoin qu'une personne
  déclenche chaque signal à la main.
- **Fonctionne sur du matériel qu'un club a probablement déjà** : un
  vieux PC, des tablettes ou téléphones pour les écrans -- pas de
  matériel spécialisé à acheter.
- **Continue de fonctionner en cas de coupure réseau ou de plantage** :
  le chrono ne perd pas le fil, la reprise se fait sans intervention
  manuelle -- voir {doc}`architecture` pour le détail technique si ça
  t'intéresse.

## Ce qu'il faut avant de commencer

- Un ordinateur (Windows, Linux, ou même un téléphone Android via
  Pydroid 3) pour héberger le serveur -- pas besoin d'être puissant, un
  vieux PC suffit largement.
- Un réseau WiFi local reliant le PC et les écrans.
- Des écrans pour l'affichage : tablettes, téléphones, ou même un vieux
  moniteur relié à un PC secondaire.
- Aucune compétence technique nécessaire pour l'usage courant -- voir
  plus bas si l'installation elle-même te semble intimidante.

## Premiers pas

1. **Installer** : trois façons possibles selon le matériel (`pip
   install fletchtime`, exécutable autoporteur Windows/Linux, ou
   directement sur Android via Pydroid 3) -- voir le
   [README](https://github.com/MrFanghoDev/fletchtime#installation)
   pour le détail de chacune, selon ton matériel.
2. **Premier lancement** : une fenêtre s'ouvre avec les adresses à
   utiliser depuis les autres appareils du réseau.
3. **Ouvrir la page de contrôle** depuis le PC ou n'importe quel
   appareil du réseau, choisir le mode (Indoor ou Flint), ajuster les
   réglages si besoin (temps de tir, nombre de volées...).
4. **Ouvrir la page d'affichage** sur chaque écran destiné aux archers.
5. **Faire un match d'essai** avant le premier vrai concours -- le
   temps de se familiariser avec les boutons (démarrer, pause, urgence)
   sans pression.

Une fois ces cinq étapes passées une fois, le pilotage d'un vrai
concours se résume à quelques clics : voir le manuel utilisateur
intégré à l'application (accessible depuis sa page d'accueil) pour le
détail de chaque réglage et bouton.

## Peut-on lui faire confiance

Question légitime avant de l'utiliser en compétition officielle :

- **Open source** : le code est public, inspectable par qui veut --
  rien de caché.
- **Testé en conditions réelles de concours**, pas seulement "ça
  compile" -- voir {doc}`roadmap` pour l'historique des versions et ce
  qui a été vérifié en pratique.
- **Récupère après un plantage ou un redémarrage du serveur** sans
  perdre la progression du match en cours.
- Reste un projet de club, sans obligation de résultat ni support
  garanti -- voir la
  [licence](https://github.com/MrFanghoDev/fletchtime/blob/master/LICENSE)
  et le ton du
  [guide de contribution](https://github.com/MrFanghoDev/fletchtime/blob/master/CONTRIBUTING.md)
  pour ce que ça implique concrètement.

## Où chercher de l'aide

- **Usage au quotidien** (réglages, pilotage d'un match) : le manuel
  utilisateur intégré à l'application, accessible depuis sa page
  d'accueil une fois installée.
- **Un bug, une question** : les
  [Issues GitHub](https://github.com/MrFanghoDev/fletchtime/issues).
- **Envie de contribuer** (code, documentation, idée) : voir
  [CONTRIBUTING.md](https://github.com/MrFanghoDev/fletchtime/blob/master/CONTRIBUTING.md).
- **Le fonctionnement technique en détail** : le reste de cette
  documentation ({doc}`specifications`, {doc}`architecture`).
