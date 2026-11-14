# Valheim Stats Tracker

Application Windows sans mod pour suivre les statistiques de personnages **Valheim** via leurs sauvegardes `.fch`. Les informations sont relevées à chaque sauvegarde, et non à chaque seconde de jeu.

## Installation
1. Télécharger la dernière archive dans [Releases](https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest).
2. Décompresser l'archive puis lancer `Lancer_Tracker.bat` avec Python 3.10+ installé.
3. Sélectionner le personnage si la détection automatique ne trouve pas le fichier.

**Confidentialité :** aucune sauvegarde personnelle ou historique n'est stocké dans ce dépôt. Les fichiers `.fch` sont lus en lecture seule ; l'historique local est conservé dans `%LOCALAPPDATA%\ValheimStatsTracker`.

## Page Succès
La page d’accueil suit 31 succès chiffrés à partir des compteurs `Any` et des groupes de difficulté des boss.
Elle affiche la progression, les critères précis et le nombre d’actions restantes. Les données ne sont **pas** une lecture du statut des succès Steam.

## Suivi de progression
- **Boss** : huit boss et compteurs par difficulté (`Normal +`, `Difficile +`, etc.) ; les groupes sont imbriqués et ne doivent pas être additionnés.
- **Poings** : catégorie de l’élimination enregistrée par la sauvegarde ; elle ne certifie pas un combat entier sans arme.
- **Historique** : dates des sauvegardes réelles, filtres de période, courbes cumulées ou variations entre relevés, et suivi des niveaux de compétences.
- **Limite** : pas de lecture des dégâts à la seconde, pas de preuve de victoire solo.

## Mise à jour automatique
La recherche de nouvelles versions est configurée vers ce dépôt. Le programme vérifie `https://raw.githubusercontent.com/LorthRuthven/valheim-stats-tracker/main/update.json` au lancement, et propose une installation après confirmation. L'archive publiée dispose d'un SHA-256 contrôlé avant l'installation.

## Développement et publication
- `python3 -m unittest discover -s tests -v` lance les tests.
- Chaque `push` sur `main` exécute les tests et crée une release si la version de `version.json` n'est pas encore publiée.
- Pour publier une nouvelle version, incrémenter `version.json`, actualiser `RELEASE_NOTES.md`, puis pousser sur `main`.
- `tools/build_release.py` construit la même archive localement.

## Limites
Ce programme ne modifie ni les fichiers du jeu, ni les succès, ni les sauvegardes. Il ne fournit pas les statistiques de combat à la seconde : l'actualisation suit les sauvegardes.
