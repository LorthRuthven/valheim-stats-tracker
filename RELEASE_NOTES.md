# Valheim Stats Tracker v1.8.4 — correction Actualiser maintenant

- Le bouton « Actualiser maintenant » relit le fichier `.fch` et affiche une confirmation horodatée.
- Quand la sauvegarde n'a pas changé, l'application l'indique clairement au lieu de laisser croire que le bouton ne répond pas.
- Si une nouvelle sauvegarde est disponible, la progression des succès, les autres statistiques et l'historique sont recalculés.
- Les erreurs de lecture déclenchées par le bouton s'affichent dans une fenêtre explicite, sans planter silencieusement.
- Un indicateur visible en haut de la page rappelle la date du dernier relevé.
- Le suivi automatique toutes les cinq secondes et le système de mise à jour restent inchangés.
- Limite sans mod : le bouton ne peut pas demander à Valheim de sauvegarder ses données en jeu ; il lit le dernier fichier disponible.

Aucune modification de la sauvegarde, de l'historique SQLite ou du serveur Valheim.
