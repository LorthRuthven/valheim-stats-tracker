# Valheim Stats Tracker

Application Windows sans mod pour suivre les statistiques de personnages **Valheim** via leurs sauvegardes `.fch`. Les informations sont relevées à chaque sauvegarde, et non à chaque seconde de jeu.

## Installation
1. Télécharger la dernière archive dans [Releases](https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest).
2. Décompresser l'archive puis lancer `Lancer_Tracker.bat` avec Python 3.10+ installé.
3. Sélectionner le personnage si la détection automatique ne trouve pas le fichier.

**Confidentialité :** aucune sauvegarde personnelle ou historique n'est stocké dans ce dépôt. Les fichiers `.fch` sont lus en lecture seule ; l'historique local est conservé dans `%LOCALAPPDATA%\ValheimStatsTracker`.

## Page Succès
La page d’accueil répertorie **55 entrées issues des ressources du jeu** : 53 succès actifs sur Steam et deux entrées internes non confirmées (*The Pugilist*, *The Most Worthy*). 43 succès actifs ont une progression calculable à partir des compteurs `Any` et des groupes de difficulté des boss. Dix autres nécessitent des listes de prefabs versionnées ou le statut de jeu qui n'est pas dans les statistiques du `.fch`.

Pour les deux entrées internes, aucune méthode de déblocage n'est confirmée. Les éliminations classées « Poings » sont montrées uniquement comme un diagnostic, pas comme une preuve de combat intégral. **Objectif atteint dans la sauvegarde ne signifie pas succès Steam ou en jeu débloqué.**

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
