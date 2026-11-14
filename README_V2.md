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
