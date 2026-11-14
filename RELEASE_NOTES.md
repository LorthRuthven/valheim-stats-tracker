# Valheim Stats Tracker v1.5.0 — SUIVI DES SUCCÈS

## Nouvelle page « Succès » (page d'accueil)
- 31 succès dont les conditions sont mesurables automatiquement par les sauvegardes `.fch` Valheim 1.0.21.
- Affichage des objectifs atteints, en cours et non commencés, avec filtres par domaine et par état.
- Barre de progression par succès, détail de chaque critère et calcul précis du reste à faire.
- Évolution entre deux relevés enregistrés dans l'historique SQLite.
- Suivi des huit boss avec distinction des difficultés, des morts par 16 causes et des 10 variétés d'arbres.
- Suivi des arbres réellement abattus, pièces construites comptabilisées, récoltes, miel, nourriture, navigation, survie, confort, poissons et mini-boss.

## Correction des statistiques
- Correspondance vérifiée des 205 indices PlayerStatType pour les profils v46/v47.
- `Tree` (arbres abattus) n'est pas `TreeChops` (coups de hache).
- Règles de succès calculées dans le groupe `Any` ou, pour les boss, `Default`/`Hard` : les statistiques brutes ne sont pas considérées comme des succès.
- Les noms techniques deviennent consultables dans l'onglet « Compteurs bruts ».

## Technique et limites
- Lecture seule, aucun mod, aucune modification des sauvegardes ou de l'historique existant.
- Le statut « objectif atteint » est déduit des compteurs et ne constitue pas une preuve de déblocage sur Steam ou dans le jeu.
- Les succès basés sur la fabrication de toutes les recettes/armes/structures ne sont pas encore inclus : ils nécessitent la liste exhaustive des objets exigés par le jeu.
- Mise à jour compatible avec l'updater de la V1.4.0 : aucun fichier exécutable supplémentaire dans l'archive.
