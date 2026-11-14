# Valheim Stats Tracker V2.1.1 — correctif d'affichage

Cette version corrige un défaut visuel majeur de la V2.1 : les textes de l'interface avaient un fond sombre opaque, produisant des rectangles noirs autour des titres, valeurs et descriptions.

## Corrections visuelles
- Les étiquettes Qt sont désormais transparentes sur les cartes et l'illustration.
- Le style global n'applique plus une couleur de fond à tous les composants indiscriminément.
- Cartes et panneaux avec un contraste plus harmonieux, bordures moins lourdes et tableaux plus lisibles.
- En-têtes, valeurs et barres de progression affinés ; navigation et cartes moins volumineuses.
- Test de régression visant explicitement les anciens rectangles noirs.
- Les illustrations et animations de « Chroniques nordiques » restent présentes.

## Données et installation
- Aucun changement au lecteur de sauvegardes, aux statistiques, aux favoris ou à l'historique SQLite.
- Test automatique Linux + test de démarrage et de rendu sous Qt sur Windows.
- **Windows :** installe l'archive `Valheim_Stats_Tracker_v2.1.1_Windows.zip` en remplaçant l'ancien dossier. L'updater Python historique ne met pas à jour directement l'exécutable Qt autonome.
- Sans mod. Sauvegardes `.fch` en lecture seule.
