"""Visuels authentiques d'inventaire Valheim pour l'interface Qt.

Chaque association sélectionne un VRAI sprite de l'inventaire du jeu (et non
un pictogramme maison). Si aucun sprite n'est accessible, on laisse l'image
vide : jamais de faux trophée ni d'icône de succès inventée.

Les mots-clés thématiques (ex. course -> hydromel de rapidité) ne prétendent
pas représenter un insigne officiel de la statistique.
"""
from __future__ import annotations

from real_assets import game_icon

# Identifiants des cartes de statistiques -> noms des véritables objets.
STAT_ITEMS = {
    "distance": "Wishbone",
    "walk": "CapeDeerHide",
    "run": "MeadHasty",
    "sail": "SerpentScale",
    "helm": "TrophySerpent",
    "air": "CapeFeather",
    "jumps": "CapeFeather",
    "portals": "SurtlingCore",
    "deaths": "TrophySkeleton",
    "survivor": "MeadHealthLingering",
    "food": "CarrotSoup",
    "sleep": "DeerHide",
    "comfort": "WolfPelt",
    "fall_deaths": "Feathers",
    "tree_deaths": "Wood",
    "time_base": "Hammer",
    "time_outside": "Torch",
    "trees": "AxeIron",
    "tree_hits": "AxeStone",
    "logs": "FineWood",
    "mines": "PickaxeIron",
    "mine_hits": "PickaxeAntler",
    "crops": "Cultivator",
    "berries": "Raspberry",
    "mushrooms": "Mushroom",
    "bees": "Honey",
    "crafted": "Hammer",
    "upgraded": "Iron",
    "built": "Hammer",
    "removed": "Hammer",
    "height": "FineWood",
    "kills": "TrophyBoar",
    "enemy_hits": "SwordIron",
    "hits_taken": "ShieldBanded",
    "arrows": "ArrowWood",
    "boss_kills": "TrophyEikthyr",
    "solo": "TrophyBonemass",
    "coop": "TrophyTheElder",
    "fish": "FishRaw",
    "lost_fish": "FishingRod",
    "treasures": "Coins",
    "world_loads": "SurtlingCore",
    "world_hours": "Torch",
    "explore_north": "Wishbone",
    "explore_south": "Wishbone",
    "explore_east": "Wishbone",
    "explore_west": "Wishbone",
}

# Tous les symboles dessinés dans la navigation cèdent la place à des items.
NAV_ITEMS = {
    "home": "Hammer",
    "trophy": "TrophyEikthyr",
    "skull": "TrophySkeleton",
    "history": "Torch",
    "settings": "Hammer",
    "paw": "TrophyBoar",
    "shield": "ShieldBanded",
    "clock": "Torch",
    "compass": "Wishbone",
    "axe": "AxeIron",
    "tree": "Wood",
    "flame": "SurtlingCore",
}

# Chaque boss a son trophée Valheim si connu ; Kall reçoit un trophée
# nordique thématique, sans le présenter comme le trophée officiel de Kall.
BOSS_ITEMS = {
    "$enemy_eikthyr": "TrophyEikthyr",
    "$enemy_gdking": "TrophyTheElder",
    "$enemy_bonemass": "TrophyBonemass",
    "$enemy_dragon": "TrophyDragonQueen",
    "$enemy_goblinking": "TrophyGoblinKing",
    "$enemy_seekerqueen": "TrophySeekerQueen",
    "$enemy_fader": "TrophyFader",
    "$enemy_frozenking_p3": "TrophyFrostTroll",
}
THEMATIC_BOSS_ICONS = frozenset({"$enemy_frozenking_p3"})

SKILL_ITEMS = {
    "Épées": "SwordIron", "Couteaux": "AxeIron", "Masses": "Hammer",
    "Armes d’hast": "SwordIron", "Lances": "SwordIron",
    "Blocage": "ShieldBanded", "Haches": "AxeIron", "Arcs": "Bow",
    "Magie élémentaire": "SurtlingCore", "Magie du sang": "TrophyBonemass",
    "Poings": "TrophyBoar", "Pioches": "PickaxeIron",
    "Coupe du bois": "AxeIron", "Arbalètes": "CrossbowArbalest",
    "Saut": "CapeFeather", "Discrétion": "CapeDeerHide",
    "Course": "MeadHasty", "Natation": "MeadBaseLightFoot",
    "Pêche": "FishingRod", "Cuisine": "CarrotSoup",
    "Agriculture": "Cultivator", "Artisanat": "Hammer",
    "Esquive": "CapeFeather", "Équitation": "CapeAsksvin",
}


def stat_game_icon(stat):
    key = stat if isinstance(stat, str) else stat.key
    return game_icon(STAT_ITEMS[key])


def nav_game_icon(key):
    return game_icon(NAV_ITEMS[key])


def boss_game_icon(key):
    return game_icon(BOSS_ITEMS[key])


def skill_game_icon(skill):
    name = str(skill)
    return game_icon(SKILL_ITEMS.get(name, "Wishbone"))


def required_inventory_items():
    """Inventaire exact des items officiels à inclure dans l'EXE Windows."""
    return frozenset((*STAT_ITEMS.values(), *NAV_ITEMS.values(),
                      *BOSS_ITEMS.values(), *SKILL_ITEMS.values()))
