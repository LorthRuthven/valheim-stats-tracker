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
            # Certaines images PNG du référentiel Jötunn ne contiennent
            # aucun pixel visible (textures d'effets, modèles non rendus).
            # Ne jamais compter un carré transparent comme une illustration.
            if any(part.startswith("jotunn_") for part in path.parts):
                try:
                    from PIL import Image
                    with Image.open(path) as source:
                        if "A" in source.getbands():
                            alpha=source.getchannel("A")
                            visible=sum(alpha.histogram()[1:])
                            if visible == 0:
                                return QIcon()
                            if "jotunn_characters" in path.parts and (
                                    visible < 100 or
                                    ("aspect" in path.name.casefold() and visible < 250)):
                                return QIcon()
                except (OSError, ValueError):
                    return QIcon()
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
    folders = {
        'achievements': 'achievements', 'pieces': 'pieces', 'items': 'items',
        'jotunn_items': 'jotunn_items', 'jotunn_characters': 'jotunn_characters',
        'jotunn_prefabs': 'jotunn_prefabs', 'jotunn_world': 'jotunn_world',
    }
    folder = folders.get(kind)
    return _qicon(bundled_assets()/folder/name) if folder else QIcon()

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
    # Atlas Jötunn authentique en recours pour les objets non couverts.
    is_item = (not prefab.startswith("$") or
               prefab.casefold().startswith(("$item_", "$pickable_")))
    if is_item:
        for variant in variants:
            icon = _find_asset("jotunn_items", variant)
            if not icon.isNull():
                return icon
    return QIcon()


def piece_icon(prefab):
    """Image authentique d'une construction Valheim référencée par le prefab exact.

    Provenance : documentation Jötunn. Ce n'est pas un sprite d'inventaire.
    """
    if not isinstance(prefab, str) or not prefab.lower().startswith("$piece_"):
        return QIcon()
    return _find_asset("pieces", prefab)


def character_icon(prefab):
    """Portrait de créature tiré des captures Valheim documentées par Jötunn."""
    if not isinstance(prefab,str) or not prefab.casefold().startswith(
            ('$enemy_', '$animal_', '$spiritcaller_')):
        return QIcon()
    for key in _icon_candidates(prefab):
        icon = _find_asset('jotunn_characters', key)
        if not icon.isNull():
            return icon
    return QIcon()


def world_icon(prefab):
    """Capture de prefab ou d'outil du monde, avec correspondance exacte."""
    if not isinstance(prefab,str) or not (
            prefab.casefold().startswith(('$ship_', '$tool_', '$pickable_', '$piece_'))
            or prefab.casefold() == '$item_hardrock'):
        return QIcon()
    for key in _icon_candidates(prefab):
        icon = _find_asset('jotunn_world', key)
        if not icon.isNull():
            return icon
        icon = _find_asset('jotunn_prefabs', key)
        if not icon.isNull():
            return icon
    return QIcon()


# Visuels réellement issus de Valheim mais représentant le boss/la plante
# d'origine, pas l'effet lui-même. Les fiches signalent leur statut associé.
RELATED_VALHEIM_IMAGES = {
    "$enemy_aspect_bonemass": ("jotunn_characters", "Bonemass"),
    "$enemy_aspect_eikthyr": ("jotunn_characters", "Eikthyr"),
    "$enemy_aspect_gdking": ("jotunn_characters", "gd_king"),
    "$enemy_aspect_dragon": ("jotunn_characters", "Dragon"),
    "$enemy_aspect_fader": ("jotunn_characters", "Fader"),
    "$enemy_aspect_goblinking": ("jotunn_characters", "GoblinKing"),
    "$enemy_aspect_seekerqueen": ("jotunn_characters", "SeekerQueen"),
    "$enemy_aspect_tentaroot": ("jotunn_characters", "TentaRoot"),
    "$item_lingonberries": ("jotunn_prefabs", "LingonberryBush"),
    "$enemy_ghost_old": ("jotunn_characters", "Ghost"),
}


def related_icon(prefab):
    """Véritable visuel d'un élément ASSOCIÉ, jamais image du prefab exact."""
    if not isinstance(prefab, str):
        return QIcon()
    match=RELATED_VALHEIM_IMAGES.get(prefab.casefold())
    if not match:
        return QIcon()
    return _find_asset(*match)


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
    image_piece=piece_icon(prefab)
    if not image_piece.isNull():
        return image_piece
    character = character_icon(prefab)
    if not character.isNull():
        return character
    world = world_icon(prefab)
    if not world.isNull():
        return world
    image=_wiki_cache().cached_image(prefab)
    if image is not None:
        image_icon = _qicon(image)
        if not image_icon.isNull():
            return image_icon
    trophy=creature_trophy_icon(prefab)
    return trophy if not trophy.isNull() else related_icon(prefab)


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
