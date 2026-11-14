"""Affichage français Valheim, sans toucher aux identifiants des sauvegardes.

Les noms sont lus depuis fr_names.json, généré à partir de la liste de la
localisation française du jeu publiée dans la documentation Jötunn. Lorsqu'un
identifiant récent est absent de la source, on conserve le nom de repli fourni
par le lecteur. Aucune requête Internet n'est nécessaire à l'exécution.
"""
from __future__ import annotations

import base64
import html
import json
import re
import zlib
from functools import lru_cache
from pathlib import Path


# Le ZIP contient le dictionnaire compressé dans le lecteur.
_FR_PACKED_NAMES = None

# Certains objets récoltés utilisent une autre clé que l'objet d'inventaire.
# Cette correspondance ne modifie jamais les statistiques du fichier .fch.
PICKABLE_TO_ITEM = {
    'raspberry': '$item_raspberries',
    'cloudberry': '$item_cloudberries',
    'lingonberry': '$item_lingonberries',
    'mushroom': '$item_mushroomcommon',
    'mushroommagecap': '$item_magecap',
    'mushroomjotunpuffs': '$item_jotunpuffs',
    'mushroomsmokepuff': '$item_smokepuff',
}

# Sept noms descriptifs non certifiés comme traduction officielle.
SUPPLEMENTAL_LABELS = {
    '$enemy_root': 'Racine',
    '$enemy_writhan': 'Writhan',
    '$spiritcaller_bjorn': 'Ours invoqué',
    '$spiritcaller_boar': 'Sanglier invoqué',
    '$spiritcaller_moose': 'Élan invoqué',
    '$spiritcaller_wolf': 'Loup invoqué',
    '$piece_darkwoodbeam67': 'Poutre en bois sombre 67°',
}


def _clean(text: str) -> str:
    return html.unescape(re.sub(r'</?(?:color|b|i|size)(?:=[^>]*)?>', '', text, flags=re.I)).replace('\u00a0', ' ').strip()


@lru_cache(maxsize=1)
def french_names() -> dict[str, str]:
    if _FR_PACKED_NAMES is not None:
        try:
            data = json.loads(zlib.decompress(base64.b64decode(_FR_PACKED_NAMES)).decode('utf-8'))
        except (ValueError, UnicodeError, zlib.error):
            return {}
    else:
        try:
            data = json.loads(Path(__file__).with_name('fr_names.json').read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            return {}
    if not isinstance(data, dict):
        return {}
    result = {}
    for key, value in data.items():
        if isinstance(key, str) and key.startswith('$') and isinstance(value, str):
            cleaned = _clean(value)
            if cleaned and not cleaned.startswith('$') and len(cleaned) <= 140:
                result[key.casefold()] = cleaned
    return result


def _plain_key(key: str) -> str:
    return re.sub('[^a-z0-9]', '', key.casefold())


@lru_cache(maxsize=1)
def _item_keys() -> dict[str, str]:
    return {_plain_key(token[6:]): token for token in french_names() if token.startswith('$item_')}


def localized_name(token: str, fallback: str | None = None) -> str:
    """Nom officiel si présent ; alias ou libellé indicatif sinon."""
    if not isinstance(token, str):
        return fallback or str(token)
    names = french_names()
    result = names.get(token.casefold()) or SUPPLEMENTAL_LABELS.get(token.casefold())
    if result:
        return result
    if not token.startswith('$'):
        normalized = _plain_key(token)
        mapped = PICKABLE_TO_ITEM.get(normalized) or _item_keys().get(normalized)
        if mapped and mapped.casefold() in names:
            return names[mapped.casefold()]
    return fallback if fallback is not None else token
