# Revue de sécurité — V2.5.2 (mise à jour intégrée candidate)

## Objectif et changement d'architecture
L'application Windows V2.5.1 ne proposait que le téléchargement manuel du ZIP pour éviter l'ancien mécanisme PowerShell mis en cause après les alertes Defender. V2.5.2 rétablit une installation depuis l'interface **sans écraser un EXE ouvert**.

### Contrôles conservés
- Versions annoncées exclusivement par la dernière GitHub Release officielle ; URL du ZIP attendue et SHA-256 de l'asset obligatoire.
- Téléchargement avec HTTPS, taille limitée et empreinte vérifiée.
- ZIP refusé en cas de dépassement de taille, sortie de dossier, lien symbolique, doublon de nom ou structure incorrecte.
- Vérification CRC par lecture intégrale du ZIP avant extraction.
- Analyse du ZIP et des fichiers extraits par Microsoft Defender via l'outil système MpCmdRun.exe **sans option de contournement**. Si l'outil est absent ou en échec, aucune activation ni aucun lancement du nouvel EXE.
- Contrôle de démarrage du vrai programme avec --verify-update-ready et contrôle de version, avant la bascule.
- Données historiques et favoris dans %LOCALAPPDATA%\ValheimStatsTracker, indépendantes des exécutables ; sauvegarde transactionnelle de SQLite et des JSON avant activation.
- Publication de l'installation par renommage atomique d'un dossier temporaire sur le même volume ; fichier d'état activé atomiquement seulement après la validation du nouveau dossier.
- L'EXE en cours et les anciens dossiers de versions ne sont jamais supprimés ou remplacés.

### Fonctionnement et limites
- L'installation se fait dans %LOCALAPPDATA%\Programs\ValheimStatsTracker\versions, non dans Program Files (aucun privilège administrateur demandé).
- Le lancement d'une nouvelle version exige le consentement de l'utilisateur, ainsi qu'une seconde confirmation pour le redémarrage.
- L'application ne désactive pas Defender, ne demande aucune exclusion, n'exécute pas PowerShell, n'installe aucun service ou tâche planifiée, et n'utilise pas de processus caché.
- Le ZIP reste disponible pour installation manuelle si un antivirus tiers remplace Defender et que le scan Defender ne peut pas être lancé.
- Le retour à une ancienne version est **manuel** : ses fichiers sont conservés, mais il n'y a pas encore de bouton « Rollback » ni de réparation automatique d'une version qui ne fonctionnerait plus après activation.
- La confiance dans le SHA-256 publié sur GitHub ne remplace pas une signature Authenticode indépendante : si le dépôt ou la release était compromis, ce mécanisme seul ne suffirait pas.
- Le contrôle de démarrage ne garantit pas la compatibilité avec toutes les machines ou les futures mises à jour de Windows.
- Les binaires PyInstaller non signés peuvent encore déclencher Defender ou SmartScreen, même avec des tests CI réussis. Toute détection doit bloquer l'utilisation et être analysée ; ne pas demander de désactiver Windows Security.

### Validation nécessaire avant diffusion
1. Tests Linux des scénarios d'installation, CRC, SHA-256, activation, échecs antivirus, échecs du contrôle de démarrage et conservation des données.
2. Tests Windows Qt sur la PR, compilation du vrai EXE, tests des sprites originaux, contrôle de lancement depuis le binaire compilé.
3. Contrôle Defender sur le binaire **exact** et le ZIP de publication, si Defender est actif sur le runner. Si Defender est indisponible, le job signale explicitement la limite.
4. Approbation de publication V2.5.2 explicite dans le workflow, non activée par un push ordinaire sur main.
5. Installation manuelle de transition V2.5.1 → V2.5.2 ; les nouvelles mises à jour intégrées ne fonctionnent qu'à partir de V2.5.2.

## Note sur les binaires distribués
Le code est public et les utilisateurs sont invités à vérifier le ZIP/EXE avec leur antivirus. Les fichiers Valheim .fch ne sont ni envoyés ni modifiés par la mise à jour.