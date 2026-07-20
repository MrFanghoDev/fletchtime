# Découvrir FletchTime pour son club

Cette page s'adresse à quelqu'un qui découvre FletchTime pour la première
fois -- un⋅e archer⋅ère, un⋅e responsable de club. Pas besoin de
connaître quoi que ce soit du projet au préalable.

## C'est quoi

FletchTime est un logiciel de chronométrage pour les compétitions
d'archerie FFTL (Indoor et Flint) : il gère le décompte du temps de tir,
les phases de préparation et de repos, les sons qui rythment le
concours, sur autant d'écrans que nécessaire. Gratuit, open source, né
de l'usage réel d'un club.

## Pourquoi s'en servir

::::{grid} 2
:gutter: 3

:::{grid-item-card} 📺 Un écran par pas de tir
Pas juste un chrono près du starter -- chaque archer voit le temps
restant sans avoir à se retourner.
:::

:::{grid-item-card} 🔊 Les sons rythment le concours tout seuls
Début de préparation, passage à l'orange, fin de volée... plus besoin
qu'une personne déclenche chaque signal à la main.
:::

:::{grid-item-card} 💻 Du matériel qu'un club a probablement déjà
Un vieux PC, des tablettes ou téléphones pour les écrans -- pas de
matériel spécialisé à acheter.
:::

:::{grid-item-card} 🔌 Résiste aux coupures et aux plantages
Le chrono ne perd pas le fil, la reprise se fait sans intervention
manuelle -- voir {doc}`architecture` pour le détail technique.
:::

::::

## Ce qu'il faut avant de commencer

- Un appareil pour héberger le serveur (PC ou téléphone selon la méthode
  d'installation choisie) -- pas besoin d'être puissant.
- Un réseau WiFi local reliant cet appareil et les écrans.
- Des écrans pour l'affichage : tablettes, téléphones, ou même un vieux
  moniteur relié à un PC secondaire.
- Aucune compétence technique nécessaire pour l'usage courant -- voir
  plus bas si l'installation elle-même te semble intimidante.

## Premiers pas

1. **Installer** : plusieurs façons possibles selon le matériel -- voir le
   [README](https://github.com/MrFanghoDev/fletchtime#installation)
   pour le détail de chacune.
2. **Premier lancement** : une fenêtre s'ouvre avec les adresses à
   utiliser depuis les autres appareils du réseau.
3. **Ouvrir la page de contrôle** depuis l'appareil hôte ou n'importe
   quel appareil du réseau, choisir le mode (Indoor ou Flint), ajuster
   les réglages si besoin (temps de tir, nombre de volées...).
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

::::{grid} 2
:gutter: 3

:::{grid-item-card} 📖 Usage au quotidien
Réglages, pilotage d'un match : le manuel utilisateur intégré à
l'application, accessible depuis sa page d'accueil une fois installée.
:::

:::{grid-item-card} 🐛 Un bug, une question
Les [Issues GitHub](https://github.com/MrFanghoDev/fletchtime/issues).
:::

:::{grid-item-card} 🤝 Envie de contribuer
Code, documentation, idée -- voir
[CONTRIBUTING.md](https://github.com/MrFanghoDev/fletchtime/blob/master/CONTRIBUTING.md).
:::

:::{grid-item-card} 🔧 Fonctionnement technique
Le reste de cette documentation : {doc}`specifications`, {doc}`architecture`.
:::

::::
