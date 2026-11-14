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

def game_icon(prefab):
    if not isinstance(prefab,str):return QIcon()
    from v2_core import app_dir
    variants=[prefab,prefab.removeprefix('$item_'),prefab.removeprefix('$piece_')]
    local=app_dir()/'game_icons'
    try:
        local_index=json.loads((local/'index.json').read_text(encoding='utf-8'))
        if not isinstance(local_index,dict):
            local_index={}
        aliases=local_index.get('aliases',{})
    except (OSError,ValueError):
        aliases={}
    if isinstance(aliases,dict):
        for variant in variants:
            value=aliases.get(_slug(variant))
            if isinstance(value,str) and value.endswith('.png') and '/' not in value and '\\' not in value and '..' not in value:
                matched=_qicon(local/value)
                if not matched.isNull():
                    return matched
    for variant in variants:
        safe=_slug(variant)
        if not safe:continue
        for ext in ('.png','.jpg'):
            path=local/(safe+ext)
            ico=_qicon(path)
            if not ico.isNull():return ico
    for variant in variants:
        ico=_find_asset('items',variant)
        if not ico.isNull():return ico
    return QIcon()

def hero_photo():
    path=bundled_assets()/'hero.jpg'
    if not path.is_file():
        return QPixmap()
    return QPixmap(str(path))

def asset_coverage():
    index=manifest()
    return len(index.get('achievements',{})),len(index.get('items',{}))
