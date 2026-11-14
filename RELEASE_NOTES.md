# Valheim Stats Tracker V2.2.1 — correctif d'import des vraies icônes

## Correctif prioritaire
- Corrige `No module named 'UnityPy.resources'` dans l'application Windows compilée.
- Le paquet inclut désormais les sous-modules, ressources et fichiers de données de UnityPy via PyInstaller `--collect-all UnityPy`.
- Un test de l'**exécutable Windows final** charge `UnityPy.resources`, vérifie ses ressources et `UnityPy.load`. La publication échoue si ce test échoue.
- Le bouton `Importer depuis le dossier de Valheim` conserve le même fonctionnement : le dossier sélectionné doit contenir `valheim.exe` et `valheim_Data`.
- Les icônes récupérées restent dans `%LOCALAPPDATA%\\ValheimStatsTracker\\game_icons`.

## Interface
- Supprime le panneau obsolète « Mises à jour » qui indiquait encore une installation manuelle.
- Conserve uniquement le panneau « Mises à jour Windows » avec téléchargement et installation intégrés.
- Aucun changement des sauvegardes, du suivi des succès, de l'historique ou des favoris.

La mise à jour V2.2.1 peut être installée depuis **Réglages → Mises à jour Windows** dans la V2.2.0.
