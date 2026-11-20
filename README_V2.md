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
La version Windows Qt utilise un bandeau graphique SVG original, une identité runique et des icônes par catégorie. Les transitions, compteurs circulaires et barres de progression sont animés avec Qt et désactivables dans les réglages (fichier local appearance.json). Les images sont embarquées et ne nécessitent ni connexion ni mod. La lecture .fch et le répertoire des données restent identiques à la V2.0.


### V2.1.1 — correctif de style Qt
Les étiquettes de texte ont un fond transparent pour éviter les rectangles noirs visibles dans la V2.1 sur Windows. Le système de données, le lecteur `.fch` et les favoris sont inchangés. Les utilisateurs de l'exécutable Windows remplacent leur dossier d'application ; l'ancien updater Python ne convertit pas une installation Tkinter en exécutable PySide6.


## V2.2 — parité fonctionnelle et médias officiels

La V2.2 restaure les pages Centre de progression, Boss, Activités, Compétences et Compteurs bruts ; Combats inclut les catégories de dégâts, Succès toutes ses conditions (sans limite 50/200), Historique l'export CSV et les gains entre relevés.

**Images :** le décor et les pictogrammes Steam sont des ressources réellement publiées par les propriétaires du jeu et de la plateforme. Aucun dessin de substitution n'est présenté comme une icône officielle. Les vrais sprites d'inventaire peuvent être extraits localement, sans mod, via Réglages → Icônes Valheim ; nécessite que Valheim soit installé sur le PC. L'extraction ne modifie aucun fichier du jeu.

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

### V2.5 — Mise à jour Windows et sécurité
L'outil Windows vérifie toujours la version officielle sur GitHub, télécharge le ZIP et vérifie son SHA-256, **sans lancer de script PowerShell ou de programme caché**. L'utilisateur ouvre ensuite les dossiers dans l'Explorateur Windows, ferme l'application, renomme l'ancien dossier en sauvegarde et copie le nouveau. Le redémarrage automatique de l'installeur a été retiré, pour privilégier un mécanisme transparent. Les données personnelles restent dans %LOCALAPPDATA%\\ValheimStatsTracker.

Depuis une installation V2.4, utiliser une fois le ZIP de GitHub Releases manuellement afin d'éviter que l'updater déjà installé déclenche son ancien script.

