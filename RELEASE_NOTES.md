# Valheim Stats Tracker V2.2.6 — Correctif d'extraction des véritables icônes

## Cause confirmée par le rapport de la V2.2.5
La lecture de 802 ressources locales Valheim a détecté **2 098 sprites** et **3 359 textures**, mais enregistré **0 image**. Les erreurs répétées indiquent :
`PyInstallerImportError: Failed to load dynlib/dll ... fmod_toolkit/libfmod/Windows/x64/fmod.dll`.

L'exécutable PyInstaller embarquait `UnityPy`, mais pas explicitement la DLL native de sa dépendance `fmod_toolkit`. Les tests existants créaient de faux sprites et ne chargeaient pas la bibliothèque native.

## Changements
- Construction Windows : inclure `fmod_toolkit` et `fmod.dll` sous le chemin attendu `_internal/fmod_toolkit/libfmod/Windows/x64/fmod.dll`.
- Bloquer la publication si la DLL source est absente ou si elle manque dans le programme construit.
- Dans le programme compilé, tester **le chargement réel de fmod.dll** avec `ctypes.WinDLL`, en plus des tests UnityPy et des sprites fictifs.
- L'extraction signale immédiatement un paquet Windows incomplet au lieu d'analyser des centaines de bundles pour aboutir à zéro image.
- Conserver les autres tests : 10 pages Qt, affichage, statuts, statistiques, lecture des sauvegardes et updater.
- Aucun fichier Valheim n'est modifié et aucune icône artificielle ne remplace les vrais sprites.

**Validation sur ton PC encore nécessaire :** le nouveau test de packaging certifie que la bibliothèque native se charge sur Windows CI ; il ne peut pas garantir à lui seul le nombre final d'icônes extraites de ta version de Valheim.

Pour tester : dans Réglages → Véritables icônes Valheim, relancer l'extraction et consulter `%LOCALAPPDATA%\\ValheimStatsTracker\\game_icons\\extraction-report.json` si nécessaire.
