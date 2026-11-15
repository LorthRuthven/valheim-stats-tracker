# Valheim Stats Tracker V2.2.7 — Ressources archspec de l'extracteur Valheim

## Diagnostic reçu
Un nouveau rapport de l'extracteur indique 802 bundles lus, 2 098 sprites, 3 359 textures et toujours 0 image. Les 2 120 erreurs proviennent cette fois d'un fichier manquant :
`archspec/json/cpu/microarchitectures.json`.

**Attention :** le chemin de l'exécutable mentionné dans ce rapport porte encore le nom de dossier `Valheim_Stats_Tracker_v2.2.5_Windows`. Il faut vérifier la version réelle du programme utilisé ; le correctif FMOD de la V2.2.6 est indépendant de cette anomalie de données archspec.

## Correctifs
- Empaqueter explicitement toutes les données JSON de `archspec` (bibliothèque Python utilisée lors du décodage), dont `microarchitectures.json`.
- Vérifier la présence du fichier dans le ZIP Windows AVANT de publier.
- Tester dans le véritable EXE compilé **l'accès au catalogue CPU archspec**, dont la lecture est différée jusqu'au premier décodage.
- En cas de paquet incomplet, afficher une erreur immédiatement avant l'analyse des 802 fichiers Valheim.
- Conserver l'intégration de `fmod.dll` et ses tests, l'updater V2.2.5 et tous les écrans existants.
- Tests unitaires : simulation de JSON absent / présent.

L'extraction des vraies données Valheim ne peut être vérifiée sur GitHub Actions, faute d'installation du jeu. Le résultat réel devra être contrôlé dans `%LOCALAPPDATA%\\ValheimStatsTracker\\game_icons\\extraction-report.json`.

Aucune sauvegarde personnelle, aucun favori et aucun historique n'est modifié.
