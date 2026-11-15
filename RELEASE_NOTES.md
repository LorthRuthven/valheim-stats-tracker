# Valheim Stats Tracker V2.3.0 — Collections & progression

## Une encyclopédie illustrée et une interface plus lisible

- **Nouvel onglet « Encyclopédie »** (11e page, sans supprimer les 10 précédentes) : créatures, trophées, armes, armures, nourriture, constructions et ressources.
- Recherche par nom français ou identifiant du jeu, filtres par catégorie et par activité, icônes extraites de ton installation Valheim, affichage agrandi et fiche détaillée.
- **Statuts fiables** : « Activité enregistrée » uniquement si les compteurs de la sauvegarde contiennent une preuve (fabrication, ramassage, construction, consommation, élimination). Sinon « Statut inconnu » : l'absence de compteur ne veut jamais dire que l'objet a été perdu ou jamais découvert.
- **Succès retravaillés** : icônes officielles agrandies, lignes plus lisibles, grande illustration dans le détail, progression, catégorie, objectifs restants et favoris conservés.
- **Icônes d'objets et créatures** : correspondances exactes avec les prefabs `$item_*`, `$enemy_*`, `$piece_*`, etc., ajoutées au bestiaire, aux boss, aux activités et au tableau de bord lorsque l'image authentique est disponible.
- **Navigation** dans une zone défilante : les onze pages restent accessibles même à faible hauteur d'écran.
- **Performances** : index local d'icônes mis en cache et invalidé au prochain import, au lieu de relire `index.json` pour chaque ligne.
- La bibliothèque affiche les 350 premières correspondances d'une recherche large pour garder l'interface fluide ; affiner les filtres permet de retrouver l'ensemble des entrées.

## Compatibilité et stabilité

Les dix pages existantes restent aux mêmes indices : Vue d'ensemble, Succès, Combat, Historique, Réglages, Centre de progression, Boss, Activités, Compétences, Compteurs bruts. Les historiques SQLite, les favoris, les exports, les animations et les profils de lisibilité restent en place. L'extracteur de véritables sprites (FMOD + archspec) et l'updater Windows sont conservés.

Aucune sauvegarde `.fch` n'est modifiée. Les critères de succès reflètent les données accessibles du jeu, **pas une attestation de validation Steam**. Le catalogue ne prétend pas lire des objets et trophées individuels qui ne sont pas identifiables dans la sauvegarde.

## Validation

- Tests unitaires du catalogue : unicité, familles, compteurs et statuts non trompeurs.
- Tests Qt : navigation sur 11 pages, réglages conservés, filtres, fiche visuelle, correspondances des sprites extraits, icônes officielles et historique.
- Tests Windows existants conservés : PyInstaller, UnityPy, fmod.dll, archspec, extraction simulée, redémarrage automatique et rollback.

**Remarque :** l'encyclopédie ne redistribue pas les fichiers du jeu ; elle affiche les icônes extraites localement ou les éléments officiellement diffusés et intégrés à l'application.
