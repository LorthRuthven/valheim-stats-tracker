VALHEIM STATS TRACKER V1.3.0 — SANS MOD
=====================================

INSTALLATION
------------
1. Extraire le ZIP depuis les Releases GitHub vers un dossier permanent.
2. Installer Python 3.10+ sur Windows (avec tkinter inclus).
3. Double-cliquer sur Lancer_Tracker.bat.
4. Choisir le personnage si la détection automatique ne convient pas.
5. Aucune écriture n'est faite dans les sauvegardes .fch.

NOUVEAUTÉS V1.3
---------------
- Onglet Boss : huit boss, comptages par difficulté et catégorie poings.
- Historique : périodes 7/30/90 jours, chronologie réelle, cumul ou gains.
- Survol des graphiques : date et valeur des relevés.
- Historique des niveaux de magie, poings, course et épées.
Les catégories de difficulté sont imbriquées : leurs compteurs ne s'additionnent pas.
La catégorie « Poings » n'atteste pas d'un combat entier exclusivement à mains nues.

MISES À JOUR GITHUB
-------------------
Vérification automatique au démarrage via :
https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest/download/update.json
Les mises à jour nécessitent l'accord de l'utilisateur avant installation.

POUR PASSER DE LA V1.2 À LA V1.3
--------------------------------
Fermer le tracker, utiliser le bouton « Mises à jour » de la V1.2,
ou extraire le nouveau ZIP dans le même dossier en remplaçant les fichiers.

HISTORIQUE ET PROTECTION
-----------------------
Historique : %LOCALAPPDATA%\ValheimStatsTracker\historique.sqlite3
Personnage choisi : %LOCALAPPDATA%\ValheimStatsTracker\config.json
Mises à jour : %LOCALAPPDATA%\ValheimStatsTracker\update_config.json
L'application lit les données à chaque sauvegarde et non en direct du jeu.
Aucune donnée de personnage n'est envoyée vers GitHub par le programme.

SÉCURITÉ
--------
Installer uniquement des mises à jour depuis une source de confiance :
SHA-256 vérifie l'intégrité, mais ne remplace pas une signature d'éditeur.
L'installeur conserve une sauvegarde des anciens fichiers du programme.

Mise à jour : le manifeste est lu via raw.githubusercontent.com/LorthRuthven/valheim-stats-tracker/main/update.json.


Nouveautés V1.4.0 : grosse refonte graphique et vue Activités beaucoup plus lisible.


V1.5.0 : nouvel écran Succès. 31 objectifs chiffrés avec progression par critère, objectifs restants et filtres.


Version 1.6.0 : la page Succès répertorie 55 entrées (53 actives sur Steam + 2 internes non vérifiées).
43 sont mesurables depuis les sauvegardes .fch ; les autres sont signalées non calculables.


V1.7 : suivi des listes exhaustives (Valheim 1.0.21) pour créatures, trophées, armes, recettes, aliments et constructions. Toutes les entrées attendues sont visibles dans la page Succès, avec pagination et critères manquants en priorité.

V1.8.0 : noms français des objets, créatures, trophées, poissons et constructions dans les listes et la page Succès.
