## V2.7.0 — Encyclopédie fluide et plein écran
- Suppression du page par page, grille virtualisée et scroll continu.
- Fiche repliable, bandeau compact, trois tailles de cartes.
- Sources Wiki exactes pour nouvelles constructions ; visuels de matériaux correctement étiquetés.
- Sauvegardes et updater intégrés conservés.

## V2.6.0 — Galerie encyclopédie et activités plus lisibles
- Encyclopédie : galerie paginée par images authentiques, provenance visible, sélection des fiches, bascule vers le tableau.
- Activités : répartition graphique des familles selon les filtres, conservant cartes, détails et données brutes.
- Cumul : mise en avant de la plus forte contribution et copie locale de chaque décomposition.
- Tous les anciens écrans et succès conservés, nouvelles sauvegardes préalables et updater V2.5.2 compatible.

## V2.5.2 — retour de l'installation Windows intégrée
- ZIP vérifié, extraction versionnée, scan Defender, contrôle du démarrage, activation atomique et redémarrage après confirmation.
- Ancienne installation préservée, sans PowerShell ni remplacement de l'EXE en cours ; données du joueur protégées.
- Sauvegarde transactionnelle avant activation et refus en cas d'échec des contrôles.
- Ancien raccourci compatible grâce à la redirection vers la version activée.

## V2.2.3 — lisibilité et extraction des objets
- Quatre tailles d’interface, « Grand » par défaut ; modification immédiate et sauvegarde de la préférence.
- Analyse Sprite et Texture2D, alias entre noms Unity et objets Valheim, compteur de progression.
- Rapport d'extraction détaillé même en cas d'absence d'icône ; fin des réussites trompeuses « 0 icône ».
- Tests sous Windows sur jeux de données synthétiques et test de l'exécutable final.

## V2.2.2 — mise à jour Windows avec contrôle du redémarrage
- Contrôle du processus réellement relancé, journal d'installation détaillé et restauration de l'ancienne version en cas d'échec.
- Test Windows du script d'installation : copie, sauvegarde et exécution réelle du programme compilé.
- Les fichiers .fch, l'historique et les favoris restent inchangés.

## V2.2.1 — correction extraction de sprites et réglages
- Embarque l'ensemble des modules et ressources UnityPy dans l'archive Windows.
- Vérifie l'import `UnityPy.resources` et ses données depuis l'exécutable final.
- Supprime l'ancien panneau « Mises à jour » redondant.
- Corrige une régression constatée dans la V2.2.0 sur l'extraction des icônes.

## V2.2.0 — restauration et ressources réelles
- Restaure les cinq pages supprimées et complète les pages Boss, Combat, Historique et Succès.
- Rétablit toutes les listes de critères, filtres, export CSV, compteur bruts et XP des compétences.
- Visuels de Valheim issus du kit presse et badges officiels Steam ; sprites d'objets importables depuis le jeu installé.
- Met en place le vrai système de mise à jour de l'application Windows autonome, avec sauvegarde.
- Tests de non-régression et compatibilité avec les données V1.x.

## V2.1.1 — correctif de l'interface
- Supprime les rectangles noirs créés par l'application du style Qt à tous les QWidget.
- Améliore lisibilité des cartes et tableaux ; affine les espacements et les bordures.
- Tests dédiés à la transparence des QLabel et au démarrage Qt Windows.

## v2.0.0
- Interface Windows Qt autonome : tableau de bord moderne, graphiques interactifs, succès, boss et rapports.
- Nouveau moteur indépendant de Tkinter conservant l'historique SQLite et les favoris existants.
- Double distribution : ZIP historique compatible avec l'updater V1.x + ZIP Windows autonome.

## v1.9.0
- Centre de progression : classement des succès mesurables, critères restants, favoris persistants par personnage.
- Rapports des sessions estimées avec comparaisons de sauvegardes, compétences et nouveaux objectifs.
- Tests des filtres, favoris, périodes et compteurs remis à zéro.

## v1.8.4
- Bouton « Actualiser maintenant » avec confirmation horodatée et erreurs visibles.
- Détection explicite de sauvegarde inchangée ; actualisation des succès si nouvelle sauvegarde.
- Tests des scénarios de relecture, de modification et d'erreur.

## v1.8.3
- Corrections des 50 identifiants de récolte affichés sans traduction française (par exemple Raspberry, Mushroom, AncientGemstoneBlack).
- Sept noms descriptifs indicatifs pour identifiants récents absents des ressources françaises documentées.
- Le code de traduction embarqué dans le ZIP utilise désormais la même logique que le module de développement.
- Tests du code réellement empaqueté ; aucune modification des compteurs, sauvegardes ou succès.

## V1.8.2
- 55 succès traduits selon la localisation française du jeu.
- Sélecteurs de difficulté en français, sans changement des identifiants internes.
- Diagnostic de la progression difficile pour « Maîtrise de la chasse ».
- Noms de boss et objectifs composés localisés.

## V1.8.1
- Corrige le refus de la V1.8 par les anciens updaters.
- Embarque 1 763 noms français dans valheim_reader.py.

## V1.7.0
- Collections exactes Valheim 1.0.21 : créatures, trophées, armes, nourritures et constructions.
- Deux méta-succès suivis par leurs prérequis.
- Critères manquants affichés en premier, pagination pour grandes listes.

## v1.5.0
- Nouvel onglet Succès (31 objectifs mesurables), suivi complet des critères chiffrés.
- Statistiques liées aux succès mappées sur les 205 indices PlayerStatType, avec tests de régression.
- Visualisation des conditions manquantes et gains entre sauvegardes.

# Changelog

## v1.4.0
- Refonte graphique majeure de l'application.
- Nouvelle navigation latérale et cartes statistiques modernisées.
- Réécriture de l'onglet Activités pour rendre les données plus propres et lisibles.
- Ajout d'un regroupement des activités par grandes familles (bois, métaux, nourriture, construction, etc.).
- Amélioration de la lisibilité générale des tableaux et résumés.

## v1.3.1
- Correction de l'URL de manifeste de mise à jour.
- Migration automatique de l'ancien lien GitHub release vers le manifeste direct.

## v1.3.0
- Suivi détaillé des boss et de l'historique.

## v1.8.0 — Noms français
- Localisation française des objets, ennemis, trophées, poissons et constructions.
- Recherche dans les critères des succès par nom français et identifiant.
- Dictionnaire embarqué pour consultation hors ligne.
