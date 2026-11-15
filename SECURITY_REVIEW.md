## Candidat V2.4.2 : installateur Windows visible, non publié

Le comportement V2.4.1 (ZIP uniquement) a été conservé en secours.
Pour les releases contenant un installateur Inno Setup :
- SHA-256 de l'installateur et provenance GitHub vérifiés au téléchargement,
  puis SHA-256 et structure PE vérifiés de nouveau juste avant l'ouverture.
- Une confirmation utilisateur explicite est requise ; le programme
  ouvre l'assistant Windows normal via os.startfile, sans session cachée,
  sans script PowerShell, sans commande d'élévation forcée.
- Installer par utilisateur dans LocalAppData/Programs, AppId fixe,
  mises à jour successives dans le même dossier, interaction Windows Restart Manager.
- Aucune exclusion antivirus, modification de Defender, tâche planifiée
  ou suppression des données utilisateur.
- Tests GitHub : deux installations successives sur runner Windows,
  vérification du SHA-256 installé, conservation d'un marqueur utilisateur.

Les deux anciens signalements Defender restent non résolus.
**Un binaire compilé et fonctionnel n'est pas automatiquement sûr.**
Le workflow de release impose toujours l'approbation spécifique V2.4.2
via la variable VALHEIM_WINDOWS_APPROVED_VERSION=2.4.2 avant publication.
La signature Authenticode et une revue indépendante du binaire restent
des prérequis recommandés pour une distribution publique.

---
# Analyse de sécurité — distribution Windows V2.4.1 (non approuvée)

## Incident du 15 novembre 2026

Microsoft Defender a détecté sur un poste Windows 11 les exécutables Windows
de Valheim Stats Tracker (dont V2.4.0 et une V2.2.x), avec notamment :
- \`Trojan:Win32/Bearfoos.A!ml\` (gravité Severe / 5) ;
- \`Behavior:Win32/DefenseEvasion.A!ml\` (gravité Severe / 5).

Aucun verdict indépendant n'a confirmé que ces détections étaient de faux positifs.
Les utilisateurs ne doivent **pas** désactiver l'antivirus ni exclure le dossier
du tracker en attendant une analyse.

## Revue du code (pas un audit de malware)

L'ancien updater \`windows_update.py\` :
- écrivait \`install.ps1\` dans LOCALAPPDATA ;
- lançait PowerShell en processus sans fenêtre avec \`-ExecutionPolicy Bypass\` ;
- copiadait les nouveaux fichiers au-dessus des exécutables en place ;
- redémarrait automatiquement le tracker.

Ces opérations peuvent attirer l'attention d'un outil de protection
comportementale ; elles n'établissent pas, à elles seules, la cause de la
détection de cheval de Troie.

### Changements V2.4.1

- L'updater conserve la vérification de la version officielle GitHub et de
  l'empreinte SHA-256 du ZIP.
- Contrôle du ZIP : taille, structure, doublons et chemins de traversée.
- **L'application ne décompresse, n'installe et ne lance plus aucun EXE**
  téléchargé. Elle conserve le ZIP vérifié et ouvre simplement son dossier.
- Suppression du script PowerShell, du remplacement de fichiers en cachette et
  de la fermeture/reprise automatique pendant la mise à jour.
- L'interface explique que l'utilisateur doit faire vérifier le nouvel
  exécutable avant toute installation manuelle.
- Tests automatisés Linux et Qt Windows ; scan de l'exécutable par Defender sur
  GitHub Actions **uniquement si la protection est active**, sans prétendre que
  cela constitue un verdict antivirus indépendant.

### Publication verrouillée

Le workflow refuse de publier une release V2.4.1 automatiquement tant que la
variable GitHub Actions \`VALHEIM_WINDOWS_APPROVED_VERSION\` n'est pas définie
précisément à \`2.4.1\` par un responsable après revue des fichiers.
Une construction réussie ou un scan non probant du runner ne suffisent pas.

Pour une release ultérieure, changer la version dans ce contrôle et
documenter explicitement la revue.

## Plan d'analyse préalable à toute release publique

1. Préserver la détection et son nom exact, ses horodatages et les empreintes
   SHA-256 sans restaurer ni lancer le fichier sur un poste non isolé.
2. Vérifier le ZIP officiel et le hash de l'EXE produit de manière reproductible
   dans GitHub Actions.
3. Soumettre **l'exécutable précis détecté** à l'analyse Microsoft :
   https://www.microsoft.com/en-us/wdsi/filesubmission
   Catégorie « Software developer » ou « Home customer », suivant le profil.
   Fournir les deux noms de détection et l'origine publique du programme.
4. Conserver l'identifiant de soumission et attendre une réponse Microsoft.
   Si le binaire est confirmé malveillant, ne pas le redistribuer et lancer
   une investigation sur le pipeline, les dépendances et l'intégrité du dépôt.
5. Avant toute diffusion, faire vérifier le binaire candidat séparément de
   l'ancien EXE et vérifier sa signature/code provenance ; prévoir une signature
   Authenticode pour les releases officielles.
6. Ne valider la variable de publication qu'après revue de sécurité explicite.

### Limites

Un SHA-256 de GitHub prouve la cohérence avec la release hébergée par GitHub ;
il ne prouve **pas** qu'un exécutable est exempt de logiciels malveillants.

La suppression du lancement PowerShell caché réduit un comportement à risque,
mais ne garantit pas que les alertes Defender disparaîtront.
