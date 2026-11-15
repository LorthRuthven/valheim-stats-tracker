"""Pictogrammes vectoriels Qt pour les actions sans sprite Valheim.

Ce sont des icônes d'interface, PAS des objets/illustrations officielles du jeu.
Les véritables sprites extraits passent toujours en premier.
"""
from __future__ import annotations

from functools import lru_cache
from xml.sax.saxutils import escape

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Tracé SVG net, cohérent avec les cartes nordiques, aucun pixel-art inventé.
SHAPES = {
    "route": '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M7 17c5-2-3-9 5-11l4-1 M13 13l3 3 5-5"/>',
    "walk": '<path d="M9 20c-2 1-4 0-4-2 0-2 2-4 4-5l2 4-2 3z M15 11c-2 1-4 0-4-2 0-2 2-4 4-5l2 4-2 3z"/><circle cx="5" cy="15" r=".9"/><circle cx="17" cy="3" r=".9"/>',
    "run": '<circle cx="14" cy="4" r="2"/><path d="m11 8-3 4 4 2 3-3 3 2h3 M9 8l3-1 4 2 M12 14l-3 5-5 2 M15 14l2 5-1 3 M4 12h4"/>',
    "sail": '<path d="M3 17h18l-3 5H6z M12 2v15 M12 3 4 15h8z M14 6l7 9h-7z"/>',
    "helm": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 1v7m0 8v7M1 12h7m8 0h7M4 4l5 5m6 6 5 5M20 4l-5 5m-6 6-5 5"/>',
    "air": '<path d="M4 18h13a4 4 0 0 0 0-8h-1A6 6 0 1 0 5 12a3 3 0 0 0-1 6z M10 22l2-3 2 3"/>',
    "jumps": '<path d="M12 21V3m-7 7 7-7 7 7 M5 21h14"/>',
    "portal": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 5c-4 2 4 5 0 8-3 2 1 5 3 4 M8 18l2-2"/>',
    "skull": '<path d="M5 12a7 7 0 1 1 14 0c0 3-2 4-3 5v4H8v-4c-2-1-3-3-3-5z M9 12v1m6-1v1 M10 17h4"/>',
    "shield": '<path d="m12 2 9 4v7c0 6-5 9-9 10-4-1-9-4-9-10V6z"/><path d="m8 12 3 3 5-6"/>',
    "tree": '<path d="M12 2 4 12h4l-5 7h18l-5-7h4z M12 19v4"/>',
    "pickaxe": '<path d="M5 21 17 5m-9 0q5-5 12 2c-4-1-7 1-9 4z"/>',
    "hammer": '<path d="M13 3h8v7h-8l-3-3z M14 10 6 22l-3-3 9-11"/>',
    "sword": '<path d="M3 21 17 7l-2-4 6-2-2 6-4-2L4 20 M3 16l5 5"/>',
    "crown": '<path d="M3 8 8 13l4-9 4 9 5-5-2 12H5z M5 20h14"/>',
    "fish": '<path d="M3 12q6-9 16 0-10 9-16 0z M19 12l4-6v12z"/><circle cx="8" cy="11" r="1"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><path d="m15 9-3 6-3 1 2-6z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/>',
    "moon": '<path d="M20 16A8 8 0 0 1 8 4a8 8 0 1 0 12 12z"/>',
    "food": '<path d="M8 3v9m-3-9v6a3 3 0 0 0 6 0V3m-3 9v9M18 3c-4 4-4 10 0 11h2V3z M19 14v7"/>',
}

ICONS = {
    "distance":"route","walk":"walk","run":"run","sail":"sail","helm":"helm",
    "air":"air","jumps":"jumps","portals":"portal","deaths":"skull",
    "survivor":"shield","food":"food","sleep":"moon","comfort":"shield",
    "fall_deaths":"skull","tree_deaths":"skull","time_base":"clock",
    "time_outside":"clock","trees":"tree","tree_hits":"tree","logs":"tree",
    "mines":"pickaxe","mine_hits":"pickaxe","crops":"tree","berries":"tree",
    "mushrooms":"tree","bees":"food","crafted":"hammer","upgraded":"hammer",
    "built":"hammer","removed":"hammer","height":"hammer",
    "kills":"sword","enemy_hits":"sword","hits_taken":"shield","arrows":"sword",
    "boss_kills":"crown","solo":"crown","coop":"crown","fish":"fish",
    "lost_fish":"fish","treasures":"compass","world_loads":"compass",
    "world_hours":"clock","explore_north":"compass","explore_south":"compass",
    "explore_east":"compass","explore_west":"compass",
}

@lru_cache(maxsize=128)
def pictogram(key, size=52):
    shape=SHAPES[ICONS.get(key,"compass")]
    svg=('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
         '<g fill="none" stroke="#edbd82" stroke-width="1.65" '
         'stroke-linecap="round" stroke-linejoin="round">'
         +shape+'</g></svg>')
    pix=QPixmap(size,size)
    pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer=QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return QIcon(pix)
