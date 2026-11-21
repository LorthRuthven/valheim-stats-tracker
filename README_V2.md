# Valheim Stats Tracker V2.5.1

**Mise à jour officielle Windows :** dans l'application, ouvrir Réglages → Mises à jour Windows → Vérifier les mises à jour. La V2.5.1 est proposée uniquement lorsqu'elle est publiée avec son ZIP et son empreinte SHA-256 sur GitHub Releases.

Le téléchargement vérifie le ZIP mais ne le lance pas : analyse Defender, décompression dans un **nouveau dossier**, puis exécution manuelle de `ValheimStatsTracker.exe`. Ne pas remplacer ni supprimer l'ancienne installation avant de contrôler ses données.

**Sauvegarde automatique de la progression au premier lancement V2.5.1 :** l'historique, les archives et les fichiers JSON de favoris/réglages sont conservés dans `%LOCALAPPDATA%\\ValheimStatsTracker\\backups\\avant_v2.5.1`. Il est également recommandé d'effectuer une copie personnelle du dossier de données. Les fichiers `.fch` du jeu ne sont jamais écrits par le tracker.

# Valheim Stats Tracker V2.1

## Windows 10/11 — sans Python
Téléchargez la release officielle `Valheim_Stats_Tracker_v2.1.0_Windows.zip`, décompressez-la intégralement et lancez `ValheimStatsTracker.exe`. Il ne faut pas sortir l'exécutable du dossier `ValheimStatsTracker`, car il utilise les fichiers de `_internal` fournis par PyInstaller.

La nouvelle interface Qt comporte : tableau de bord, 55 succès suivis, objectifs restants, favoris, boss et créatures, courbes interactives et rapports de sessions estimées. Les sessions sont reconstruites à partir des sauvegardes séparées de 90 minutes au maximum ; au moins deux sauvegardes sont nécessaires.

## Compatibilité V1.9
L'application Qt V2 et l'ancienne application Tkinter lisent les mêmes fichiers locaux :
- `%LOCALAPPDATA%\ValheimStatsTracker\historique.sqlite3`
- `%LOCALAPPDATA%\ValheimStatsTracker\favoris.json`
- `%LOCALAPPDATA%\ValheimStatsTracker\config.json`

Les sauvegardes de personnages Valheim `.fch` ne sont jamais modifiées. N'exécutez pas simultanément les deux interfaces pour éviter des accès concurrents inutiles au fichier SQLite.

## Mise à jour
Le ZIP `Valheim_Stats_Tracker_v2.0.0.zip` est **réservé aux installations historiques Python** et reste compatible avec l'updater de la V1.9. Il ajoute un lien vers la nouvelle interface. Pour utiliser Qt sans Python, installez **séparément** le ZIP nommé `_Windows.zip`.

Les prochaines mises à jour de l'application Windows se téléchargeront depuis [GitHub Releases](https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest). L'application permet d'ouvrir la page officielle depuis Réglages.

## Développement
- Lecture sauvegarde : `valheim_reader.py` (pure Python)
- État et suivi : `v2_core.py` (pure Python, tests autonomes)
- Interface : `desktop_v2.py` (PySide6)
- Installation des dépendances : `pip install -r requirements-windows.txt`
- Lancement Python : `python desktop_v2.py`
- Tests : `python -m unittest discover -s tests -v`
- Construction Windows : `python -m PyInstaller --noconfirm --clean --onedir --windowed --name ValheimStatsTracker --add-data "fr_names.json;." desktop_v2.py`

Le workflow GitHub Actions lance les tests Linux, construit l'archive Windows sur un runner Windows et publie l'archive ainsi que le paquet compatible avec l'ancien updater. Le manifeste `update.json` pointe uniquement vers le paquet historique Python.

## Chroniques nordiques (V2.1)
La version Windows Qt utilise un bandeau graphique SVG original, une identité visuelle nordique et des icônes d'inventaire Valheim authentiques pour toutes les catégories. Les transitions, compteurs circulaires et barres de progression sont animés avec Qt et désactivables dans les réglages (fichier local appearance.json). Les images sont embarquées et ne nécessitent ni connexion ni mod. La lecture .fch et le répertoire des données restent identiques à la V2.0.


### V2.1.1 — correctif de style Qt
Les étiquettes de texte ont un fond transparent pour éviter les rectangles noirs visibles dans la V2.1 sur Windows. Le système de données, le lecteur `.fch` et les favoris sont inchangés. Les utilisateurs de l'exécutable Windows remplacent leur dossier d'application ; l'ancien updater Python ne convertit pas une installation Tkinter en exécutable PySide6.


## V2.2 — parité fonctionnelle et médias officiels

La V2.2 restaure les pages Centre de progression, Boss, Activités, Compétences et Compteurs bruts ; Combats inclut les catégories de dégâts, Succès toutes ses conditions (sans limite 50/200), Historique l'export CSV et les gains entre relevés.

**Images :** le décor et les icônes de succès Steam sont des ressources réellement publiées par les propriétaires du jeu et de la plateforme. Aucun dessin de substitution n'est présenté comme une icône officielle. Les vrais sprites d'inventaire peuvent être extraits localement, sans mod, via Réglages → Icônes Valheim ; nécessite que Valheim soit installé sur le PC. L'extraction ne modifie aucun fichier du jeu.

**Mises à jour :** à partir de V2.2, les versions Windows autonomes ont leur propre updater avec SHA-256, sauvegarde et redémarrage. Les utilisateurs de V2.0/V2.1 doivent installer manuellement V2.2 une dernière fois.

**Données :** toujours dans %LOCALAPPDATA%\ValheimStatsTracker ; jamais de réinitialisation des historiques ou favoris.

### V2.2.1 — correctif des sprites Windows
Les versions antérieures à la V2.2.1 pouvaient afficher « No module named UnityPy.resources ». Le paquet Windows embarque maintenant les ressources de UnityPy et vérifie leur présence en exécutant le programme compilé. L'écran de réglages ne conserve qu'un seul panneau de mise à jour Windows.


### V2.2.2 — Redémarrage après mise à jour
Le programme Windows fait maintenant contrôler son propre installateur sur un runner Windows avant publication : lancement de l'exécutable compilé après remplacement, sauvegarde précédente et journal de diagnostic. Si une mise à jour antérieure s'est arrêtée sans redémarrer, consulter `%LOCALAPPDATA%\\ValheimStatsTracker\\updates\\install.log`, relancer l'exécutable présent ou réinstaller manuellement dans un dossier propre.


### V2.2.3 — meilleure lisibilité et diagnostic des icônes
Dans Réglages, sélectionner Compact, Normal, Grand (défaut) ou Très grand. Le choix est immédiat et conservé dans appearance.json. Pour l'extraction, sélectionner le dossier contenant valheim.exe. Si aucune icône ne peut être extraite, ouvrir « Rapport de diagnostic » : `%LOCALAPPDATA%\\ValheimStatsTracker\\game_icons\\extraction-report.json`. L'extracteur couvre Sprite et Texture2D et n'ajoute aucune icône artificielle. Les fichiers du jeu et les sauvegardes restent intacts.


## V2.5 — Archives et cumul des statistiques
Dans **Statistiques du Viking**, choisir **Importer des .fch** pour sélectionner plusieurs sauvegardes d'anciens personnages. Le menu **Personnages** permet d'afficher la fiche de chacun ou **Tous les personnages**. Les archives restent en mémoire locale SQLite, sans copie des fichiers originaux ni modification de sauvegarde. Si le même identifiant Valheim est réimporté, sa fiche est remplacée et non additionnée. Le personnage actif supplante son ancienne archive dans le total. Utiliser **Retirer l'archive** pour cesser de compter un ancien personnage sans effacer son `.fch`. La fonction prend en charge les formats v46/v47 ; une ancienne version de fichier non décodable est affichée comme erreur individuelle.

### V2.5 — Téléchargement Windows sécurisé
L'updater reprend le mécanisme de sécurité V2.4.1 : vérification de GitHub Releases et du SHA-256, puis conservation du ZIP officiel **sans extraction automatique, exécution de script ni remplacement de l'EXE en cours d'utilisation**. L'utilisateur ouvre son dossier, vérifie le fichier avec Defender, ferme l'ancienne application et extrait le ZIP dans un nouveau dossier. Les données locales restent dans `%LOCALAPPDATA%\\ValheimStatsTracker`.

Depuis une installation V2.4, utiliser une fois le ZIP officiel depuis le navigateur plutôt que son ancien bouton d'installation PowerShell. Aucune exception antivirus n'est requise ou recommandée.


### Détail des statistiques de plusieurs personnages
Dans **Statistiques du Viking**, choisir **CUMUL • Tous les Vikings** puis cliquer sur n'importe quelle carte ou sur **Voir le détail par Viking**. Une fiche présente le total, la règle de regroupement (somme, meilleur record, validé par au moins un Viking), les valeurs individuelles de chaque personnage, et, pour les sommes positives, leur pourcentage de contribution. Les personnes sont affichées par valeur décroissante, y compris celles à zéro. Une valeur absente de la sauvegarde s'affiche **—**, jamais comme une activité nulle inventée. La difficulté sélectionnée est respectée. Il est impossible de consulter ce détail en mode Individuel, où la présentation habituelle est préservée.

Les captures de validation comprennent un exemple avec un deuxième Viking **fictif**, créé uniquement en mémoire pour illustrer la fenêtre sans modifier ni inventer de véritable fichier `.fch`.

### V2.5 — Images Valheim dans toutes les pages
Les cartes de statistiques, les cartes de leur détail cumulatif, le menu latéral, les huit boss, les compétences et les indicateurs du tableau de bord n'utilisent plus de pictogrammes génériques dessinés. Ils utilisent une sélection embarquée de PNG issus de l'inventaire de Valheim (objets, ressources, équipements, trophées), validés image par image à la compilation. Les associations à une statistique sans icône dédiée sont thématiques, sans présenter l'image comme une récompense officielle.

Les autres écrans privilégient toujours les vrais assets locaux extraits du jeu, puis les images wiki mises en cache lorsque c'est applicable. Lorsqu'aucune image vérifiée n'existe, aucun faux sprite n'est inventé. Le build Windows vérifie aussi les pixels depuis le véritable EXE PyInstaller. Les droits des images du jeu sont réservés à Iron Gate / Coffee Stain.


### Page Activités : une galerie plutôt qu'un tableau
Le menu **Activités** affiche désormais les objets sous forme de **cartes illustrées avec des sprites Valheim**. Choisis le type d'activité (récolte, ramassage, fabrication, pose, nourriture), une difficulté et une famille ; recherche ensuite une ressource ou un objet et trie les résultats. Les cartes sont organisées par 16 avec boutons Précédent / Suivant. Les tableaux techniques d'origine sont toujours disponibles via **Afficher les tableaux détaillés**.

Pour le diagnostic du lecteur de fichiers `.fch`, les **205 compteurs bruts** et leurs indices sont conservés dans **Réglages → Diagnostic avancé**. Cette vue est en lecture seule. Les pages internes gardent leurs anciens indices pour préserver les tests et les raccourcis existants.


### V2.5.2 — Mise à jour Windows directement dans l'application

Depuis V2.5.2, Réglages → Mises à jour Windows → Télécharger et installer effectue le téléchargement SHA-256, l'extraction dans un répertoire versionné, la vérification via Windows Security Center qu'un antivirus est sain, puis un contrôle de démarrage, puis propose de redémarrer. Aucun remplacement d'EXE en cours ni script PowerShell. Une installation dont le contrôle de protection ou de démarrage échoue n'est pas activée.

Le nouveau programme se trouve dans %LOCALAPPDATA%\Programs\ValheimStatsTracker\versions, les données dans %LOCALAPPDATA%\ValheimStatsTracker. L'ancienne version reste disponible. Le raccourci vers V2.5.2 ou une version suivante redirige automatiquement vers la nouvelle version validée.

Une dernière installation manuelle est nécessaire depuis V2.5.1. Si Windows Security ne confirme pas un antivirus sain, le ZIP vérifié reste accessible via « Ouvrir le dossier du ZIP », mais l'application refuse de l'exécuter automatiquement. Aucun contournement de Defender n'est recommandé.

**Retour manuel :** l'ancien EXE reste disponible. Pour démarrer une version V2.5.2 ou ultérieure sans redirection automatique vers la dernière version installée, ajoute l'argument de lancement `--no-update-handoff` au raccourci de secours. Ce mode ne désactive aucune protection antivirus et ne modifie pas les données.

### V2.6.0 — Une véritable galerie pour l'Encyclopédie

La page Encyclopédie affiche désormais par défaut une **galerie de 18 images par page** avec la provenance vérifiable (sprite Valheim, portrait wiki ou trophée associé). Toutes les entrées référencées restent consultables : pas de coupure à 350 comme dans l'ancien tableau. Le bouton **Liste détaillée** donne toujours accès au tableau traditionnel. Cliquer sur une carte ouvre sa fiche de collection.

La page Activités affiche la répartition graphique des cinq principales familles, selon les filtres ; les tableaux techniques restent disponibles. En mode Statistiques du Viking → CUMUL, le panneau de détail met en avant le meilleur contributeur et permet de copier les valeurs de chaque Viking.

Les données locales sont sauvegardées avant la première ouverture V2.6.0. Les mises à jour intégrées de la V2.5.2 restent compatibles.
