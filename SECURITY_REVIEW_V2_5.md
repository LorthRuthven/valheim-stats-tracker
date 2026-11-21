# Revue de sécurité — Valheim Stats Tracker V2.5.0 (candidate non publiée)

## Incident documenté

Le 15 novembre 2026, Windows Defender a mis `ValheimStatsTracker.exe` en quarantaine sur un poste utilisateur, avec notamment `Trojan:Win32/Bearfoos.A!ml` et `Behavior:Win32/DefenseEvasion.A!ml`. **Ces alertes ne doivent pas être ignorées ni qualifiées de faux positifs sans analyse.**

Un candidat V2.4.1 a ensuite passé un contrôle Defender ciblé et s'est lancé sur le poste, mais ce résultat n'établit pas l'innocuité de V2.5.0 ni son acceptation sur tous les PC.

## Mesures conservées depuis le correctif V2.4.1

- Suppression du script `install.ps1`, des commandes PowerShell avec `ExecutionPolicy Bypass`, des processus cachés et du remplacement automatique de l'EXE.
- Vérification de l'URL officielle de GitHub Releases et de l'empreinte SHA-256 annoncée sur l'asset.
- Validation des ZIP (structure, chemins, taille, doublons, liens symboliques).
- Le nouveau ZIP est conservé **sans extraction ni exécution par l'application** ; l'utilisateur vérifie avec son antivirus, puis extrait manuellement le programme dans un dossier distinct.
- Les données personnelles restent dans `%LOCALAPPDATA%\ValheimStatsTracker` et ne sont pas déplacées ni supprimées pendant un téléchargement.
- Les tests Python, Qt Windows, le build PyInstaller réel et une analyse Defender conditionnelle font partie des contrôles de la PR.

## Limites et critères avant publication

Un téléchargement SHA-256 vérifié confirme l'intégrité relative à la release GitHub, pas l'absence de malware. Le fonctionnement de SmartScreen et Defender évolue indépendamment des tests applicatifs. **Aucune version non signée ne peut être garantie acceptée à 100 % par Defender et SmartScreen.** Il n'est demandé ni de désactiver Defender ni d'ajouter une exclusion.

La publication de V2.5.0 est bloquée jusqu'à validation explicite dans GitHub Actions (`VALHEIM_WINDOWS_APPROVED_VERSION=2.5.0`) après examen du binaire candidat et des éventuelles détections. Un runner GitHub dont Defender est désactivé ne constitue pas un test antivirus valide.

Si un EXE est détecté, conserver le nom de la détection et l'empreinte SHA-256, ne pas le lancer et soumettre **ce binaire précis** à Microsoft pour analyse : https://www.microsoft.com/en-us/wdsi/filesubmission (catégorie développeur).

Pour la transition depuis V2.4, son updater installé utilise encore PowerShell : ne pas l'utiliser pour installer V2.5. Privilégier un téléchargement officiel dans le navigateur, analyser le ZIP puis installer manuellement dans un nouveau dossier.
