"""Affichage français Valheim, sans toucher aux identifiants des sauvegardes.

Les noms sont lus depuis fr_names.json, généré à partir de la liste de la
localisation française du jeu publiée dans la documentation Jötunn. Lorsqu'un
identifiant récent est absent de la source, on conserve le nom de repli fourni
par le lecteur. Aucune requête Internet n'est nécessaire à l'exécution.
"""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def french_names() -> dict[str, str]:
    location = Path(__file__).with_name('fr_names.json')
    try:
        payload = json.loads(location.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result = {}
    for key, value in payload.items():
        if isinstance(key, str) and key.startswith('$') and isinstance(value, str):
            cleaned = html.unescape(re.sub(r'</?(?:color|b|i|size)(?:=[^>]*)?>', '', value, flags=re.I)).replace('\u00a0', ' ').strip()
            if cleaned and not cleaned.startswith('$') and len(cleaned) <= 140:
                result[key.casefold()] = cleaned
    return result


def localized_name(token: str, fallback: str | None = None) -> str:
    """Nom français exact si disponible ; jamais de traduction devinée."""
    if not isinstance(token, str):
        return fallback or str(token)
    return french_names().get(token.casefold(), fallback if fallback is not None else token)
