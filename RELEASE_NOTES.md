# Valheim Stats Tracker V2.0.0 — interface Windows moderne

La V2 passe à **PySide6 / Qt** pour les utilisateurs de Windows 11 : une application autonome, sans installation de Python. Nouvelle navigation, tableau de bord sombre, graphiques interactifs avec survol, zoom temporel, suivi des 55 entrées de succès et de leurs critères, vue des boss par difficulté et rapport de session estimé.

**Téléchargements :**
- `Valheim_Stats_Tracker_v2.0.0_Windows.zip` : **nouvelle interface Qt Windows**. Décompresser et lancer `ValheimStatsTracker.exe` dans le dossier extrait. Conserver le dossier `_internal` avec l'exécutable.
- `Valheim_Stats_Tracker_v2.0.0.zip` : version **historique Python/Tkinter**, compatible avec l'updater V1.x et dotée d'un lien vers l'interface Windows. Elle ne transforme pas automatiquement l'installation Python en EXE.

**Données préservées :** historique `historique.sqlite3`, favoris `favoris.json` et configuration `config.json` dans `%LOCALAPPDATA%\ValheimStatsTracker`. Les fichiers `.fch` ne sont ouverts qu'en lecture.

**Limites :** la V2 lit la dernière sauvegarde, pas les événements en direct. La progression des succès n'est pas leur statut Steam officiel. La distribution Windows se met à jour par téléchargement d'une nouvelle archive officielle (la fonction d'installation automatique de la V1.x concerne uniquement le paquet historique Python).
