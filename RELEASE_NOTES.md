# Valheim Stats Tracker V2.2.5 — Lancement automatique de l'updater Windows

## Correction du lancement de l'installateur
Après confirmation sur le PC utilisateur : les ZIP et le script `install.ps1` sont bien créés, le script fonctionne manuellement, mais aucun `install.log` n'apparaît depuis l'application.

- PowerShell est maintenant lancé via son **chemin Windows absolu** plutôt que via une recherche dans le PATH de l'application.
- En environnement **PyInstaller**, la recherche des DLL système est rétablie temporairement pour lancer PowerShell, comme le recommande la documentation PyInstaller.
- Le lancement est indépendant du processus Qt, sans `DETACHED_PROCESS`, mais sans fenêtre console.
- L'environnement enfant est marqué comme indépendant de PyInstaller pour le lancement ultérieur du nouvel exécutable.
- Deux journaux distincts sont désormais conservés dès la tentative de lancement :
  - `%LOCALAPPDATA%\\ValheimStatsTracker\\updates\\launcher.log` : demande et PID du lancement, erreurs immédiates.
  - `%LOCALAPPDATA%\\ValheimStatsTracker\\updates\\powershell-output.log` : sortie et erreurs PowerShell avant la création éventuelle de `install.log`.
- `install.log` reste le journal de l'installation, de la copie et du redémarrage.

## Validation
- Nouveau **test de lancement de PowerShell depuis le véritable exécutable Windows PyInstaller**, et non seulement depuis Python ou PowerShell manuellement.
- Tests existants inchangés : lecture des sauvegardes, écrans Qt, extraction d'icônes, contrôles d'intégrité ZIP, redémarrage et rollback.
- Aucune désactivation ou exclusion de Microsoft Defender ou SmartScreen.

Les sauvegardes de personnages, l'historique et les favoris restent dans le dossier local habituel.
