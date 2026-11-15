# Valheim Stats Tracker V2.4.0 — Statistiques du Viking

## Nouvelle page « Statistiques du Viking »
La **12ᵉ page** du tracker s'inspire des statistiques de Minecraft, avec **47 cartes** lisibles, des valeurs importantes en grand et une identité visuelle Valheim.

### Les cinq rubriques
- **Déplacements** : distance totale, marche, course, navigation, distance passée à la barre, distance aérienne, sauts, portails.
- **Survie** : morts, record de jours consécutifs sans décès, nuits dormies, repas, confort, causes de décès, temps à la base et hors de la base.
- **Récolte & construction** : arbres abattus (à ne pas confondre avec les coups de hache), troncs, minerai, récoltes, objets fabriqués, améliorations, bâtiments placés ou retirés, hauteur maximale.
- **Combat** : créatures éliminées, coups donnés, coups reçus, flèches, boss vaincus, boss en solo et en coopération.
- **Exploration** : poissons pêchés/perdus, trésors enfouis, temps en jeu et les quatre directions du succès Exploration.

### Présentation
- **47 cartes illustrées** avec les vraies icônes du jeu lorsqu'un prefab exact convient ; sinon, pictogrammes vectoriels d'interface (jamais présentés comme des images officielles).
- **Favoris en haut de page**, possibilité d'épingler ou retirer chaque statistique par l'étoile ★.
- **Favoris par personnage** dans le nouveau fichier `stats_favorites.json`, séparé de `favoris.json` (succès) et des autres données.
- **Recherche instantanée**, filtrage par catégorie ou favoris uniquement.
- **Difficulté sélectionnable** : « toutes », « normal ou + », « difficile ou + », « très difficile ou + » et « extrême ». Ces groupes se recouvrent et ne doivent pas être additionnés.
- **Gains entre les deux derniers relevés** lorsqu'ils sont disponibles et que le compteur ne diminue pas.
- Cartes responsive : 1, 2 ou 3 colonnes selon la largeur.

### Transparence des données
Chaque statistique correspond à un **vrai compteur indexé parmi les 205 PlayerStatType** de Valheim, ou au temps des mondes déjà lu par le tracker. Les distances sont converties automatiquement de mètres en kilomètres. Le compteur de nage distinct n'existe pas dans les sauvegardes actuellement prises en charge : aucune distance de nage fictive n'est affichée.

### Compatibilité
Les **11 pages précédentes restent aux indices 0 à 10**, y compris l'Encyclopédie avec les images du wiki. Aucun changement du moteur des succès, des historiques SQLite, des sauvegardes `.fch`, de l'extracteur d'images, du cache wiki ni de l'updater Windows.

Tests ajoutés : identité exacte des compteurs, distances et unités, records, indicateurs de progression, resets de sauvegarde, favoris par personnage, interaction Qt, navigation à 12 pages, rendus SVG.
