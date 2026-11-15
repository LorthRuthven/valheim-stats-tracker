# Valheim Stats Tracker V2.3.1 — Images Valheim Wiki

## Ce qui change
- **Images de complément depuis Valheim Wiki** pour les entrées dont aucune icône authentique locale n'a été associée. Le wiki indépendant de la communauté utilise `valheim.wiki` (miroir `valheim.weirdgloop.org`), et non l'ancien Fandom.
- **Ordre de priorité préservé** : 1. vrai sprite extrait du jeu, 2. ressource officielle intégrée, 3. image du wiki téléchargée dans le cache utilisateur.
- La **grande image de droite** est téléchargée automatiquement quand on sélectionne une entrée manquante sur la page Encyclopédie. La miniature de gauche se met ensuite à jour sans redémarrer le programme.
- Bouton **« Compléter 20 images via Valheim Wiki »** : télécharge au plus 20 illustrations manquantes parmi les entrées visibles, à un rythme limité et sans bloquer l'interface.
- Bouton **« Vider les images wiki »** : efface uniquement le cache wiki, jamais les images extraites de Valheim ni les données personnelles.
- Accès supplémentaire depuis **Réglages → Images du wiki Valheim**.
- Correspondances wiki à partir du **prefab anglais**, avec dictionnaire d'exceptions contrôlées. Aucune recherche approximative FR→image : une page inexistante reste sans image plutôt que d'afficher la mauvaise créature.
- **Attribution et contrôle** : chaque image enregistrée conserve la page exacte du wiki et l'URL de provenance ; bouton **« Voir l'image sur le wiki »**. Les conditions de réutilisation des médias se vérifient depuis leur page source.

## Fiabilité, réseau et données
- Utilise exclusivement les pages exactes de l'API MediaWiki des domaines autorisés, en HTTPS. Aucune recherche auprès d'autres services, aucun code externe téléchargé.
- Cache local sous `%LOCALAPPDATA%\\ValheimStatsTracker\\wiki_cache` ; une image déjà enregistrée reste accessible hors connexion.
- Limite de taille et validation du format d'image avant écriture, cache des échecs temporaires pour limiter les requêtes répétées ; erreurs non bloquantes.
- Tests : URL/titres exacts, cache, attribution, refus des mauvais noms, rendu Qt grande image et vignette, chargement Pillow dans l'EXE, récupération d'une vraie image du wiki en CI.
- Conserve les **11 pages**, la lecture seule des sauvegardes `.fch`, les favoris, graphiques, réglages et l'updater Windows.

**Important :** une image wiki n'est pas un sprite officiel extrait du jeu ; elle est indiquée explicitement comme image communautaire et n'est pas redistribuée dans l'archive Windows.
