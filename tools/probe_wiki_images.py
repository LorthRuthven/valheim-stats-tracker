"""Diagnostic réseau facultatif du Wiki sur un runner, sans sauvegarde joueur."""
from __future__ import annotations

import json
import tempfile

from wiki_images import WikiImageCache, wiki_title

TOKENS = ("$enemy_greyling", "$enemy_abomination", "$item_sword_iron")


def main():
    result = []
    with tempfile.TemporaryDirectory(prefix="valheim_wiki_diagnostic_") as root:
        cache = WikiImageCache(root)
        for token in TOKENS:
            picture = cache.fetch(token)
            reason = cache.last_error(token)
            result.append({
                "token": token,
                "titre": wiki_title(token),
                "reussi": bool(picture),
                "erreur": reason,
            })
    print("DIAGNOSTIC PUBLIC WIKI :", json.dumps(result, ensure_ascii=False), flush=True)
    # Accès à un Wiki tiers non critique : les tests ne dépendent pas du réseau.


if __name__ == "__main__":
    main()
