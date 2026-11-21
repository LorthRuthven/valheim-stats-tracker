# Valheim Stats Tracker V2.5.2 — Retour des mises à jour intégrées

## Mise à jour Windows : installation et redémarrage
- Réglages → Mises à jour Windows → Télécharger et installer : contrôle GitHub Releases et SHA-256 conservé.
- Après confirmation explicite, extraction dans un dossier versionné sous %LOCALAPPDATA%\Programs\ValheimStatsTracker\versions. L'EXE en cours n'est jamais remplacé.
- Avant activation, l'application consulte Windows Security Center (WSC) : un antivirus sain doit être signalé. Windows Defender ou l'antivirus tiers actif protège les fichiers en temps réel lors de l'extraction et du premier lancement. Le programme n'effectue **pas** de scan antivirus à la demande et ne requiert pas d'élévation UAC. Si WSC ne confirme pas un antivirus sain, l'activation est refusée.
- Vérification du démarrage du nouvel EXE et de son interface Qt avant activation.
- Activation atomique, puis proposition de redémarrage. Les raccourcis V2.5.2 ou ultérieurs redirigent vers une version installée plus récente.
- Anciennes installations conservées pour retour manuel en arrière. Aucun PowerShell, script masqué, tâche planifiée ni exception antivirus.
- Fichiers .fch lus sans modification. Historique SQLite, succès, favoris, archives dans %LOCALAPPDATA%\ValheimStatsTracker, avec nouvelle copie transactionnelle avant activation.
- Un échec de téléchargement, d'analyse, de démarrage ou de sauvegarde laisse la version courante active.

**Transition V2.5.1 → V2.5.2 :** il faut installer V2.5.2 une dernière fois manuellement depuis la release officielle (ZIP Windows, antivirus puis extraction dans un nouveau dossier). Les prochaines versions peuvent être installées depuis les Réglages.

**Sécurité :** le SHA-256 n'est pas une signature du code et ne garantit pas l'acceptation Defender/SmartScreen. La publication reste conditionnée à la revue explicite V2.5.2.

---
# Valheim Stats Tracker V2.5.1 — Encyclopédie enrichie, archives et galerie

## Sécurité de la mise à jour V2.5.1
- Avant la première ouverture de la V2.5.1, le tracker réalise automatiquement une **copie transactionnelle de `historique.sqlite3`**, incluant les anciens relevés de succès et archives de personnages, et des fichiers JSON de favoris et de réglages. Copie locale : `%LOCALAPPDATA%\\ValheimStatsTracker\\backups\\avant_v2.5.1`.
- L'original reste en place. Si la sauvegarde préalable échoue, la nouvelle version ne doit pas ouvrir ni modifier la base d'historique.
- La nouvelle version est proposée par le panneau **Réglages → Mises à jour Windows**, uniquement après sa publication officielle sur GitHub Releases avec empreinte SHA-256 reconnue.
- L'application télécharge un ZIP vérifié et l'ouvre dans l'Explorateur. **Aucune installation silencieuse ni exécution automatique** n'est autorisée ; l'utilisateur doit extraire le ZIP et lancer l'EXE manuellement après son analyse antivirus.
- Les fichiers `.fch` originaux et les succès Steam restent intacts.



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

## Encyclopédie — illustrations enrichies après les premiers tests sur PC
- **Problème constaté :** 1 379 entrées mais seulement 16 images Wiki en cache, et « 0/20 » nouvelles illustrations sur la capture réelle. Ce compteur ne reflétait pas les sprites du jeu déjà inclus dans le paquet.
- **Inventaire élargi :** en plus des 104 sprites indispensables à l'interface, le build identifie les correspondances **exactes** entre les prefabs d'objets de l'Encyclopédie et le registre de sprites Valheim. Chaque image facultative est validée en tant que PNG ; les éléments sans sprite exact restent visibles sans dessin inventé.
- **Créatures :** priorité au portrait Wiki si déjà disponible. À défaut, un **véritable trophée de cette créature** peut être affiché quand il existe, avec un libellé explicite pour ne pas le confondre avec une photo du monstre.
- **Bilan transparent :** les chiffres distinguent les sprites exacts du jeu, les portraits Wiki, les trophées associés et les éléments toujours sans illustration. Nouveau filtre « Avec illustration / Sans illustration ».
- **Wiki moins frustrant :** le bouton sélectionne désormais jusqu'à 20 nouvelles cibles parmi toutes les entrées filtrées, en excluant pendant six heures les recherches négatives. Les raisons des échecs sont affichées au lieu de toujours présenter « 0/20 » sans explication. Un diagnostic réseau non bloquant teste aussi trois pages connues sur le runner Windows.
- **Protection des sauvegardes :** toutes les images supplémentaires appartiennent au programme ou au cache utilisateur et n'altèrent jamais les fichiers `.fch`, la base des succès ni les favoris.

## Visuels 100 % issus du jeu — sprites Valheim
- Tous les anciens **pictogrammes dessinés** des cartes Statistiques du Viking et de la fenêtre de détail du cumul sont remplacés par des **objets et ressources authentiques du jeu**. Les associations sont thématiques pour les statistiques sans icône officielle dédiée.
- La barre latérale, les boutons et les cartes du tableau de bord utilisent maintenant des sprites du jeu à la place des icônes SVG maison.
- Les pages **Boss** (trophées réels), **Compétences** (armes, outils et équipements réels), **Combat** et **Activités** utilisent les vrais sprites lorsqu'ils existent. Kall Mandefimbul dispose actuellement d'une illustration Valheim thématique signalée comme telle, sans prétendre être son trophée officiel.
- Le ZIP Windows embarque un jeu de PNG originaux vérifiés, sélectionnés depuis la bibliothèque publique de sprites de Valheim (révision épinglée), avec un index et un inventaire SHA-256. L'application privilégie toujours les visuels extraits localement du jeu par l'utilisateur.
- **Protection contre les régressions :** compilation Windows interdite si un des sprites requis est absent ou ne peut pas être chargé par le véritable EXE PyInstaller. Les tests Qt vérifient les pixels au lieu de compter les seuls fichiers.
- Attributions et origine des images inscrites dans `assets/ATTRIBUTIONS.txt` ; droits des illustrations du jeu réservés à Iron Gate / Coffee Stain, compagnon non officiel.

## Activités : véritable galerie d'objets Valheim
- L'ancienne page **Activités**, principalement constituée de tableaux, devient une **galerie de cartes** avec les vraies images du jeu, le nom localisé, la famille et la quantité.
- Barre de recherche, filtres **action / difficulté / famille**, tri **quantité décroissante / ordre alphabétique / quantité croissante**, et **pagination de 16 objets**.
- Affichage en deux, trois ou quatre colonnes selon la taille de la fenêtre Windows. Chaque carte donne accès à l'identifiant exact dans son infobulle.
- Un petit tableau de bord présente le **nombre de ressources distinctes**, la **quantité totale enregistrée** et la **famille dominante**. Les visuels thématiques sont explicitement signalés lorsque l'icône exacte n'est pas disponible.
- Les tableaux d'origine sont conservés sous **« Afficher les tableaux détaillés »**, fermés par défaut, sans masquer aucune donnée.
- **Compteurs bruts** n'occupe plus le menu latéral. La page des 205 indices est conservée, accessible dans **Réglages → Diagnostic avancé**, avec bouton de retour. Tous les index internes de pages restent compatibles.
- Contrôles Qt supplémentaires : 25 objets fictifs, passage entre deux pages, recherche, tri, filtre, tableau repliable et accès au diagnostic.

## Améliorations de lisibilité et navigation
- **Modes « CUMUL • Tous les Vikings » et « INDIVIDUEL • Un Viking »** directement visibles dans Statistiques du Viking, en complément du sélecteur par personnage.
- **Détail cliquable de chaque statistique en mode Cumul** : valeur retenue, toutes les valeurs individuelles triées, source du personnage, pourcentage et barre de contribution pour les sommes. Pour les records, identification du meilleur Viking ; pour les objectifs, personnages ayant atteint la condition. Valeurs brutes précises disponibles pour distances et durées. Les règles des groupes de difficulté restent inchangées.
- **Raccourci « Cumul des Vikings »** dans la barre latérale ; après import de plusieurs fichiers `.fch`, le cumul s'affiche automatiquement.
- **Boss :** galerie des huit boss avec véritables icônes locales lorsqu'elles existent, nombre de victoires enregistrées et synthèse par difficulté.
- **Combat :** trois indicateurs (éliminations, espèces et boss distincts) calculés à partir des compteurs du groupe choisi.
- **Activités :** trois objets ou ressources les plus comptabilisés dans la sélection, avec icônes locales réelles, et message explicatif si le filtre ne renvoie rien.
- **Compétences :** barres de maîtrise (niveau / 100) et compétence la plus élevée ; les XP enregistrés restent affichés séparément.
- **Encyclopédie :** zone d'illustration à hauteur fixe et espacement renforcé pour éviter tout chevauchement.
- **Réglages :** texte mis en conformité avec la mise à jour par ZIP vérifié et installation manuelle sans PowerShell.
- Tests Qt et captures de chaque page sous Windows pour vérifier ces changements.

## Mise à jour Windows sans exécution silencieuse
Le mécanisme de sécurité **V2.4.1**, déjà testé sur Windows, est repris dans V2.5.0. L'application vérifie la version GitHub, télécharge le ZIP officiel et contrôle l'empreinte SHA-256, **sans décompresser, exécuter, ni remplacer elle-même un EXE**, et sans lancer PowerShell. Elle ouvre le dossier de téléchargement. L'utilisateur peut faire analyser le ZIP puis l'extraire **dans un nouveau dossier**, fermer l'ancienne version et lancer la nouvelle.

**Transition depuis V2.4 :** le bouton d'installation de V2.4 utilise encore son ancien mécanisme PowerShell. Pour éviter ce mécanisme, télécharger une fois le ZIP de la V2.5 depuis GitHub Releases, et l'installer manuellement après vérification.

**Diffusion contrôlée :** la compilation et les tests automatiques ne garantissent pas un verdict antivirus. La publication reste bloquée tant que `VALHEIM_WINDOWS_APPROVED_VERSION` n'est pas explicitement défini à `2.5.0` après revue.

**Aucune garantie antivirus absolue :** les EXE restent non signés et la réputation Defender/SmartScreen varie selon les machines et les mises à jour Microsoft. Ne pas désactiver de protections pour installer.

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
- **47 cartes illustrées** avec des sprites authentiques de l'inventaire Valheim, y compris pour les statistiques sans icône officielle dédiée (association thématique explicite). Aucun pictogramme vectoriel de substitution n'est utilisé.
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
