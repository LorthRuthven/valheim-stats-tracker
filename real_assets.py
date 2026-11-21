"""Affiche exclusivement des ressources réellement présentes (Steam / installation Valheim).

Aucun pictogramme généré ne prétend être un logo officiel.
Les sources et droits sont décrits dans assets/ATTRIBUTIONS.txt.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

def _slug(text):
    normalized = unicodedata.normalize('NFKD',str(text)).casefold()
    return re.sub(r'[^a-z0-9]+','',normalized)

def bundled_assets():
    base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return base/'assets'

@lru_cache(maxsize=1)
def manifest():
    try:
        value=json.loads((bundled_assets()/'index.json').read_text(encoding='utf8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

@lru_cache(maxsize=3000)
def _qicon(path):
    try:
        if path.is_file() and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp') and path.stat().st_size < 2_000_000:
            pix=QPixmap(str(path))
            if not pix.isNull():
                return QIcon(pix)
    except OSError:
        pass
    return QIcon()

def _find_asset(kind,key):
    entries=manifest().get(kind,{})
    name=entries.get(_slug(key))
    if not isinstance(name,str) or '/' in name or '\\' in name or '..' in name:
        return QIcon()
    return _qicon(bundled_assets()/('achievements' if kind=='achievements' else 'items')/name)

def achievement_icon(title):
    # La clé d'affichage française n'est jamais utilisée pour attribuer une mauvaise icône.
    if not isinstance(title,str):return QIcon()
    return _find_asset('achievements',title)

@lru_cache(maxsize=8)
def _local_aliases(index_file, modified_ns):
    """Lit l'index une fois par révision, pas à chaque ligne de catalogue."""
    try:
        value=json.loads(Path(index_file).read_text(encoding='utf-8'))
        aliases=value.get('aliases',{}) if isinstance(value,dict) else {}
        return aliases if isinstance(aliases,dict) else {}
    except (OSError, ValueError, TypeError):
        return {}

def _icon_candidates(token):
    """Correspondances exactes seulement : aucun rapprochement flou."""
    if not isinstance(token,str):
        return ()
    raw=token.strip().removeprefix('$')
    candidates=[raw]
    prefixes=('item_', 'enemy_', 'piece_', 'pickable_', 'animal_', 'ship_', 'tool_')
    for prefix in prefixes:
        if raw.casefold().startswith(prefix):
            candidates.append(raw[len(prefix):])
            break
    result=[]
    for item in candidates:
        key=_slug(item)
        if key and key not in result:
            result.append(key)
    return tuple(result)

def game_icon(prefab):
    """Icône authentique extraite localement, sinon ressource officielle embarquée."""
    if not isinstance(prefab,str):
        return QIcon()
    from v2_core import app_dir
    local=app_dir()/'game_icons'
    index_file=local/'index.json'
    try:
        revision=index_file.stat().st_mtime_ns
    except OSError:
        revision=0
    aliases=_local_aliases(str(index_file),revision)
    variants=_icon_candidates(prefab)
    for variant in variants:
        value=aliases.get(variant)
        if (isinstance(value,str) and value.endswith('.png')
                and '/' not in value and '\\' not in value and '..' not in value):
            matched=_qicon(local/value)
            if not matched.isNull():
                return matched
    for variant in variants:
        for ext in ('.png','.jpg'):
            icon=_qicon(local/(variant+ext))
            if not icon.isNull():
                return icon
    for variant in variants:
        icon=_find_asset('items',variant)
        if not icon.isNull():
            return icon
    return QIcon()

def creature_trophy_icon(prefab):
    """Trophée exact du monstre (jamais présenté comme une photo de lui)."""
    if not isinstance(prefab, str):
        return QIcon()
    raw = prefab.strip().lstrip("$")
    if not raw.startswith(("enemy_", "animal_")):
        return QIcon()
    creature = raw.split("_", 1)[-1]
    return game_icon("Trophy" + creature)


def collection_icon(prefab):
    """Sprite exact > Wiki attribué > véritable trophée du même monstre."""
    icon=game_icon(prefab)
    if not icon.isNull():
        return icon
    image=_wiki_cache().cached_image(prefab)
    if image is not None:
        image_icon = _qicon(image)
        if not image_icon.isNull():
            return image_icon
    return creature_trophy_icon(prefab)


@lru_cache(maxsize=1)
def _wiki_cache():
    from wiki_images import WikiImageCache
    return WikiImageCache()


def reset_icon_cache():
    """Appelé après une nouvelle extraction pour actualiser immédiatement toutes les pages."""
    _local_aliases.cache_clear()
    _qicon.cache_clear()


def hero_photo():
    path=bundled_assets()/'hero.jpg'
    if not path.is_file():
        return QPixmap()
    return QPixmap(str(path))

def asset_coverage():
    index=manifest()
    return len(index.get('achievements',{})),len(index.get('items',{}))
