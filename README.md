# Valheim Stats Tracker

Application Windows sans mod pour suivre les statistiques de personnages **Valheim** via leurs sauvegardes `.fch`. Les informations sont relevées à chaque sauvegarde, et non à chaque seconde de jeu.

## Installation Windows 10/11 (sans Python)
1. Dans [GitHub Releases](https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest), télécharger l'archive portant le suffixe **`_Windows.zip`**.
2. L'analyser avec Windows Security, extraire **tout le dossier** `ValheimStatsTracker` puis lancer `ValheimStatsTracker.exe` sans séparer le sous-dossier `_internal`.
3. Sélectionner le personnage si la détection automatique ne trouve pas le fichier. Depuis V2.5.2, les prochaines versions s'installent depuis **Réglages → Mises à jour Windows** après confirmation.

Le ZIP **sans** suffixe `_Windows` est réservé à l'ancienne interface Python/Tkinter et à son mécanisme de mise à jour.

**Confidentialité :** aucune sauvegarde personnelle ou historique n'est stocké dans ce dépôt. Les fichiers `.fch` sont lus en lecture seule ; l'historique local est conservé dans `%LOCALAPPDATA%\ValheimStatsTracker`.

## Page Succès
La page Succès suit 53 succès actifs et présente 2 entrées internes non vérifiées à partir des compteurs `Any` et des groupes de difficulté des boss.
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


V1.7 : suivi des listes exhaustives (Valheim 1.0.21) pour créatures, trophées, armes, recettes, aliments et constructions. Toutes les entrées attendues sont visibles dans la page Succès, avec pagination et critères manquants en priorité.

## Localisation française (V1.8)
Les noms de créatures, objets, trophées, poissons et constructions viennent de la traduction française du jeu publiée dans la documentation [Jötunn / Valheim-Modding](https://github.com/Valheim-Modding/Jotunn/blob/main/JotunnLib/Documentation/data/localization/translations/French.md). La base publiée correspond à une version antérieure du jeu (1.0.7) ; les noms récents qui ne figurent pas dans cette source conservent une étiquette de secours.

Le dictionnaire français est intégré dans le lecteur fourni dans l’archive pour une utilisation hors connexion. Les clés utilisées pour compter la progression des succès ne sont jamais traduites : seul le texte affiché change.


### Localisation française de la V1.8.3

Le tracker conserve les clés d'origine de la sauvegarde et traduit uniquement leur affichage. Par exemple, la récolte `Raspberry` est reliée au nom officiel `$item_raspberries` (« Framboises »). Les sept libellés d'éléments récents absents de la localisation publiée sont descriptifs, non garantis comme noms officiels. Le ZIP reste compatible avec les anciens updaters : aucun mod ni fichier additionnel requis.


## Centre de progression V1.9
L'écran d'accueil classe les objectifs mesurables à terminer par pourcentage accompli. Tu peux enregistrer des favoris propres à chaque personnage (stockés dans `%LOCALAPPDATA%\ValheimStatsTracker\favoris.json`), consulter les critères restants et ouvrir la fiche complète d’un succès. Le rapport de session compare des relevés séparés d'au plus 90 min. Ce n'est pas un suivi temps réel ni un relevé exact des connexions.


## V2.0 Windows (Qt)
La nouvelle interface PySide6 et ses graphiques interactifs sont livrés dans l'archive séparée `Valheim_Stats_Tracker_v2.0.0_Windows.zip`, avec l'exécutable autonome `ValheimStatsTracker.exe` (aucun Python requis). Le ZIP standard reste le programme Python historique, installable par l'updater V1.x. Les deux versions utilisent le même historique et les mêmes favoris. Voir [README_V2.md](README_V2.md) pour les instructions de transition.


## Interface Windows V2.1 — Chroniques nordiques

La [dernière release](https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest) contient une application Qt autonome pour Windows (archive avec suffixe \`_Windows.zip\`), sans installation de Python. La V2.1 ajoute un panorama de fjord et maison longue, un emblème runique, des pictogrammes de navigation, une jauge d'objectifs et des transitions animées désactivables. Les graphiques interactifs, succès et données de la V2 restent présents.

**Note de compatibilité :** le ZIP sans suffixe \`_Windows\` est destiné à l'ancien updater Python et conserve l'interface historique. Il ne transforme pas l'ancien programme Tkinter en nouvelle application autonome. Les données locales sont partagées et préservées.


## Mise à jour intégrée de Windows (depuis V2.5.2)

L'application Windows autonome installe et relance les futures versions depuis Réglages → Mises à jour Windows. Le ZIP est vérifié par SHA-256, extrait dans une installation versionnée, soumis à une vérification de l'état antivirus Windows Security et testé avant le redémarrage. L'EXE en cours n'est pas remplacé. Les archives et succès restent dans %LOCALAPPDATA%\ValheimStatsTracker. Les utilisateurs en V2.5.1 doivent installer V2.5.2 une dernière fois manuellement. Voir README_V2.md.


## V2.7.0 — Encyclopédie sur grand écran
La galerie n'a plus de pages : scroll vertical continu, cartes Compact/Normal/Grand, fiche latérale ouvrable au clic, recherche et liste technique conservées. L'application met en avant les images de jeu et Wiki vérifiées ; les éventuels visuels de matériaux sont explicitement indiqués comme thématiques. Mise à jour intégrée depuis V2.5.2.


## V2.7.2 — Atlas Jötunn et audit de couverture
1 530 illustrations authentiques de créatures, objets et éléments du monde complètent les 386 pièces. Les identifiants encore manquants peuvent être copiés depuis l'Encyclopédie, sans lire ni transmettre les sauvegardes des personnages.
