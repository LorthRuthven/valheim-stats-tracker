# Valheim Stats Tracker V2.2.2 — fiabilisation des mises à jour Windows

- Correction du redémarrage après installation : le script vérifie que l'application relancée ne se ferme pas immédiatement.
- Journal détaillé dans `%LOCALAPPDATA%\\ValheimStatsTracker\\updates\\install.log` avec étapes `BACKUP_OK`, `COPY_OK`, `RELAUNCH_OK` et erreurs.
- Attente bornée de la fermeture de l'ancien tracker, sans blocage infini.
- Sauvegarde avant remplacement et restauration automatique en cas d'échec de copie ou de lancement.
- Test Windows **de bout en bout** : copie des fichiers de la nouvelle version, sauvegarde de l'ancienne, lancement du véritable exécutable PyInstaller et contrôle du résultat avant publication.
- Correction UnityPy de la V2.2.1 conservée.
- Aucun changement à la lecture des sauvegardes Valheim, au SQLite, aux succès ou aux favoris.

**Si une ancienne version s'est déjà fermée sans redémarrer :** vérifier `updates\\install.log` et lancer manuellement `ValheimStatsTracker.exe`. Si les fichiers sont endommagés, installer le ZIP Windows complet V2.2.2 dans un nouveau dossier. Les données sont conservées dans `%LOCALAPPDATA%\\ValheimStatsTracker`.
