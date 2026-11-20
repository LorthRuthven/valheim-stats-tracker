# Valheim Stats Tracker V2.5.0 — Archives de personnages et statistiques cumulées

## Mes personnages dans « Statistiques du Viking »
- Importer plusieurs anciens fichiers `.fch` simultanément, sans les modifier.
- Choisir dans la même page le Viking actif, chacun des personnages archivés, ou **Tous les personnages**.
- Afficher les 47 cartes existantes et les filtres par catégorie/difficulté, avec favoris indépendants par personnage et pour le total.
- Stockage local des profils décodés dans la base SQLite existante, indépendant des fichiers originaux ; les archives restent consultables après redémarrage.
- Réimporter le même personnage actualise son archive : les fichiers d'un seul Viking ne sont jamais additionnés entre eux, même si leurs noms de fichier diffèrent. Deux personnages homonymes restent distincts grâce à leur identifiant Valheim.
- Possibilité de retirer une archive du tracker sans effacer la sauvegarde originale.

## Précision des totaux
- **Somme entre personnages** pour les activités, distances, temps et éliminations.
- **Maximum** pour les records (confort, hauteur de construction, série de jours).
- **Union** pour les critères binaires d'exploration.
- Les difficultés `Any`, `Default`, `Hard`, `VeryHard`, `Hardcore` ne sont jamais additionnées entre elles.
- Le personnage actif prévaut sur une archive portant le même identifiant : aucun double comptage.
- La progression des succès Steam et celle du personnage actif ne sont pas affectées par la somme du tracker.

## Mise à jour Windows sans exécution silencieuse
Pour réduire les comportements susceptibles de déclencher les protections Windows, l'updater Windows **ne lance plus PowerShell**, n'écrase plus l'exécutable en arrière-plan et ne redémarre pas le programme automatiquement. Il continue de vérifier la version GitHub, de télécharger l'archive Windows officielle et d'en contrôler l'empreinte SHA-256. L'installation se fait ensuite **manuellement**, avec ouverture des dossiers dans l'Explorateur : fermer le programme, renommer l'ancien dossier pour en garder une sauvegarde, copier le nouveau dossier et relancer.

**Transition depuis V2.4 :** le bouton d'installation de V2.4 utilise encore son ancien mécanisme PowerShell ; pour éviter de le déclencher, installer la V2.5 une première fois depuis l'archive GitHub Releases après fermeture du programme.

**Aucune garantie antivirus absolue** : les EXE restent non signés et la réputation SmartScreen peut varier selon Windows et les mises à jour Defender. Ne pas désactiver les protections pour installer.

## Compatibilité
Le lecteur intégré accepte les sauvegardes Valheim `.fch` **v46 et v47** avec 205 compteurs et validation SHA-512 ; les fichiers d'éditions plus anciennes non compatibles sont signalés individuellement, sans bloquer les autres imports. La fonction est intégrée à l'application **Windows Qt** ; le ZIP Python historique conserve son interface sans nouvelle page.

Les 12 pages existantes, l'historique, les favoris des succès, la collection, les médias, l'extraction des icônes et l'updater sont conservés. Les données d'archives ne quittent jamais le PC.

---

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
