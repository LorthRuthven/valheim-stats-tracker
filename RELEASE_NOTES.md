# Valheim Stats Tracker V2.2.3 — Lisibilité et extraction d'icônes

## A. Interface plus grande et lisible
- Réglages → **Taille de l’interface** : Compact, Normal, Grand, Très grand.
- **Grand par défaut** pour tous les utilisateurs sans préférence enregistrée.
- Ajustement immédiat des textes, panneaux, menus, champs, boutons et hauteurs des tableaux (dont Succès, Activités et Compétences).
- Préférences conservées dans `%LOCALAPPDATA%\\ValheimStatsTracker\\appearance.json` ; les animations et la lisibilité restent indépendantes.
- Navigation plus large pour éviter les libellés coupés. Compatibilité avec Full HD.

## B. Correctif et diagnostic d'extraction des vrais objets Valheim
- Vérifie la présence de `valheim.exe` et `valheim_Data`.
- Analyse les asset bundles Valheim et les éventuels fichiers `.assets`.
- Accepte `Sprite` et les `Texture2D` dont les noms correspondent aux éléments d'interface et d'inventaire.
- Utilise `parse_as_object()` ou `read()` selon la version de UnityPy.
- Associe des variantes comme `Icon_Wood` au nom d'objet `Wood`, sans générer de faux dessins.
- Barre de progression et **rapport détaillé** dans `%LOCALAPPDATA%\\ValheimStatsTracker\\game_icons\\extraction-report.json` : fichiers lus, sprites trouvés, textures trouvées, images enregistrées, erreurs, exemples.
- **Zéro icône n'est plus une réussite silencieuse** : une erreur explicite pointe vers le rapport de diagnostic.
- Tests automatisés sur des sprites et textures de démonstration, dont un test depuis l'exécutable Windows assemblé.

**Limite :** aucune installation réelle de Valheim n’est disponible sur les runners de test. Ces tests valident le fonctionnement de l'extracteur et le diagnostic, mais pas le nombre d'icônes provenant de chaque version du jeu. S'il manque encore des icônes, fournir le rapport pour identifier les bundles problématiques.

La mise à jour Windows continue de conserver les fichiers locaux (sauvegardes, statistiques, historique et favoris).
