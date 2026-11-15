"""Compteurs utiles Valheim — V2.4.0.

Une fiche = un vrai compteur du format v46/v47 (205 PlayerStatType) ou un
agrégat explicitement existant. Pas de distance de nage inventée.
Lecture seule, sans accès réseau ni dépendance Qt.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from valheim_reader import STAT_INDEX, metrics

@dataclass(frozen=True)
class Stat:
    key: str
    title: str
    category: str
    counter: str
    unit: str = "nombre"
    icon: str = ""
    glyph: str = "ᛟ"
    note: str = ""

# Les clés "counter" sont vérifiées contre les 205 noms de la sauvegarde
# (ou 3 métriques calculées déjà utilisées ailleurs dans le programme).
STATS = (
    Stat("distance", "Distance totale", "Déplacements", "DistanceTraveled", "distance", "$item_boots", "ᚱ", "Distance totale enregistrée"),
    Stat("walk", "Distance à pied", "Déplacements", "DistanceWalk", "distance", "$item_helmet_leather", "ᚱ", "Marche uniquement"),
    Stat("run", "Distance en courant", "Déplacements", "DistanceRun", "distance", "$item_cape_deerhide", "ᚱ", "Course uniquement"),
    Stat("sail", "Distance en bateau", "Déplacements", "DistanceSail", "distance", "$item_wood", "ᛟ", "Distance parcourue en navigation"),
    Stat("helm", "Distance à la barre", "Déplacements", "DistanceSailHelm", "distance", "$item_finewood", "ᛟ", "Distance parcourue en pilotant"),
    Stat("air", "Distance dans les airs", "Déplacements", "DistanceAir", "distance", "$item_cape_feather", "ᛝ", "Distance aérienne enregistrée"),
    Stat("jumps", "Sauts effectués", "Déplacements", "Jumps", "number", "$item_cape_feather", "ᛝ", "Nombre total de sauts"),
    Stat("portals", "Portails utilisés", "Déplacements", "PortalsUsed", "number", "$item_greydwarfeye", "ᛟ", "Traversées de portails"),
    Stat("deaths", "Décès", "Survie", "Deaths", "number", "$item_tombstone", "ᛟ", "Décès enregistrés par la sauvegarde"),
    Stat("survivor", "Record de jours survécus", "Survie", "ConsecutiveDaysSurvivedMax", "number", "$item_honey", "ᛉ", "Jours consécutifs sans décès (record)"),
    Stat("food", "Nourritures mangées", "Survie", "FoodEaten", "number", "$item_boar_meat", "ᛟ", "Consommations enregistrées"),
    Stat("sleep", "Nuits dormies", "Survie", "Sleep", "number", "$item_bed", "ᛟ", "Sommeil enregistré"),
    Stat("comfort", "Confort maximal", "Survie", "MaxComfort", "number", "$item_wood", "ᛉ", "Plus haut niveau de confort atteint"),
    Stat("fall_deaths", "Morts par chute", "Survie", "DeathByFall", "number", "$item_stone", "ᛟ", "Causes de décès : chute"),
    Stat("tree_deaths", "Morts écrasé par un arbre", "Survie", "DeathByTree", "number", "$item_wood", "ᛟ", "Causes de décès : arbre"),
    Stat("time_base", "Temps à la base", "Survie", "TimeInBase", "duration", "$piece_workbench", "ᛟ", "Temps enregistré dans la base"),
    Stat("time_outside", "Temps hors de la base", "Survie", "TimeOutOfBase", "duration", "$item_torch", "ᛟ", "Temps enregistré hors de la base"),
    Stat("trees", "Arbres abattus", "Récolte & construction", "Tree", "number", "$item_wood", "ᛏ", "Nombre d'arbres, pas les coups de hache"),
    Stat("tree_hits", "Coups portés aux arbres", "Récolte & construction", "TreeChops", "number", "$item_axe_iron", "ᛏ", "Coups de hache enregistrés"),
    Stat("logs", "Troncs débités", "Récolte & construction", "Logs", "number", "$item_wood", "ᛏ", "Troncs débités (compteur Logs)"),
    Stat("mines", "Gisements exploités", "Récolte & construction", "Mines", "number", "$item_iron", "ᚷ", "Compteur Mines du personnage"),
    Stat("mine_hits", "Coups de pioche", "Récolte & construction", "MineHits", "number", "$item_pickaxe_iron", "ᚷ", "Coups de pioche enregistrés"),
    Stat("crops", "Cultures récoltées", "Récolte & construction", "HarvestCrop", "number", "$item_carrot", "ᛒ", "Récoltes de cultures"),
    Stat("berries", "Baies récoltées", "Récolte & construction", "HarvestBerry", "number", "$item_raspberries", "ᛒ", "Récoltes de baies"),
    Stat("mushrooms", "Champignons récoltés", "Récolte & construction", "HarvestMushroom", "number", "$item_mushroom", "ᛒ", "Récoltes de champignons"),
    Stat("bees", "Miel récolté", "Récolte & construction", "BeesHarvested", "number", "$item_honey", "ᛒ", "Quantité de miel récoltée"),
    Stat("crafted", "Objets fabriqués", "Récolte & construction", "Crafts", "number", "$piece_workbench", "ᛟ", "Fabrications enregistrées"),
    Stat("upgraded", "Améliorations d'objets", "Récolte & construction", "Upgrades", "number", "$item_iron", "ᛟ", "Améliorations effectuées"),
    Stat("built", "Constructions placées", "Récolte & construction", "Builds", "number", "$item_hammer", "ᚨ", "Pièces posées"),
    Stat("removed", "Constructions démontées", "Récolte & construction", "BuildPiecesRemoved", "number", "$item_hammer", "ᚨ", "Pièces retirées"),
    Stat("height", "Hauteur de construction max.", "Récolte & construction", "MaxBuildingHeight", "metres", "$item_wood", "ᚨ", "Hauteur maximale d'une structure"),
    Stat("kills", "Créatures vaincues", "Combat", "EnemyKills", "number", "$item_trophy_boar", "ᛉ", "Éliminations enregistrées"),
    Stat("enemy_hits", "Coups portés aux ennemis", "Combat", "EnemyHits", "number", "$item_sword_iron", "ᛉ", "Touches réussies"),
    Stat("hits_taken", "Coups reçus", "Combat", "HitsTakenEnemies", "number", "$item_shield_iron", "ᛉ", "Touches reçues des ennemis"),
    Stat("arrows", "Flèches tirées", "Combat", "ArrowsShot", "number", "$item_arrow_wood", "ᛉ", "Projectiles tirés"),
    Stat("boss_kills", "Boss éliminés", "Combat", "BossKills", "number", "$item_trophy_eikthyr", "ᛉ", "Total des combats de boss gagnés"),
    Stat("solo", "Boss éliminés en solo", "Combat", "BossKillSolo", "number", "$item_trophy_bonemass", "ᛉ", "Victoires en solo enregistrées"),
    Stat("coop", "Boss éliminés en coopération", "Combat", "BossKillMultiplayer", "number", "$item_trophy_elder", "ᛉ", "Victoires en groupe enregistrées"),
    Stat("fish", "Poissons pêchés", "Exploration", "FishCaught", "number", "$item_fish_raw", "ᚱ", "Prises enregistrées"),
    Stat("lost_fish", "Poissons perdus", "Exploration", "FishLost", "number", "$item_fish_raw", "ᚱ", "Poissons décrochés"),
    Stat("treasures", "Trésors enfouis trouvés", "Exploration", "TreasureBuriedFound", "number", "$item_coins", "ᚱ", "Coffres ou trésors enterrés"),
    Stat("world_loads", "Entrées dans un monde", "Exploration", "WorldLoads", "number", "$item_wood", "ᚱ", "Chargements de mondes"),
    Stat("world_hours", "Temps en jeu", "Exploration", "@world_hours", "hours", "$item_torch", "ᚱ", "Temps cumulé des mondes visités"),
    Stat("explore_north", "Extrémité nord atteinte", "Exploration", "ExploreNorth", "binary", "$item_cape_wolf", "ᚱ", "Critère d'Exploration : nord"),
    Stat("explore_south", "Extrémité sud atteinte", "Exploration", "ExploreSouth", "binary", "$item_cape_asksvin", "ᚱ", "Critère d'Exploration : sud"),
    Stat("explore_east", "Extrémité est atteinte", "Exploration", "ExploreEast", "binary", "$item_finewood", "ᚱ", "Critère d'Exploration : est"),
    Stat("explore_west", "Extrémité ouest atteinte", "Exploration", "ExploreWest", "binary", "$item_finewood", "ᚱ", "Critère d'Exploration : ouest"),
)
KEYS = frozenset(s.key for s in STATS)
CATEGORIES = ("Déplacements", "Survie", "Récolte & construction", "Combat", "Exploration")
DEFAULT_FAVORITES = frozenset({"walk", "sail", "trees", "built", "kills", "deaths"})

if len(KEYS) != len(STATS):
    raise RuntimeError("Identifiants du tableau de statistiques en double")
if any(s.counter not in STAT_INDEX and s.counter != "@world_hours" for s in STATS):
    raise RuntimeError("Statistique absente des 205 compteurs Valheim")
if any(s.category not in CATEGORIES for s in STATS):
    raise RuntimeError("Catégorie de statistique inconnue")


def value(profile, stat, group="Any"):
    """Valeur brute; None si le profil demandé n'est pas disponible."""
    if not profile:
        return None
    if stat.counter == "@world_hours":
        raw_worlds = profile.get("groups", {}).get("RawStats", {}).get("worlds", {})
        if not isinstance(raw_worlds, dict):
            return None
        return sum(max(0.0, float(v)) for v in raw_worlds.values()) / 3600
    stats = profile.get("groups", {}).get(group, {}).get("stats")
    idx = STAT_INDEX.get(stat.counter)
    if not isinstance(stats, (tuple, list)) or idx is None or idx >= len(stats):
        return None
    try:
        number = float(stats[idx])
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def pretty(value, unit):
    if value is None:
        return "—"
    if unit == "binary":
        return "Validé" if value >= 1 else "À atteindre"
    if unit == "distance":
        return (f"{value / 1000:,.1f} km" if abs(value) >= 1000
                else f"{value:,.0f} m").replace(",", " ").replace(".", ",")
    if unit == "duration":
        return (f"{value / 3600:,.1f} h" if abs(value) >= 3600
                else f"{value / 60:,.0f} min").replace(",", " ").replace(".", ",")
    if unit == "hours":
        return f"{value:,.1f} h".replace(",", " ").replace(".", ",")
    if unit == "metres":
        return f"{value:,.1f} m".replace(",", " ").replace(".", ",")
    return f"{value:,.0f}".replace(",", " ")


def change(current, earlier, stat, group="Any"):
    """Progression uniquement si deux relevés sont disponibles sans reset."""
    first = value(current, stat, group)
    last = value(earlier, stat, group)
    if first is None or last is None or first < last:
        return None
    return first - last


def _path(directory):
    return Path(directory) / "stats_favorites.json"


def favorites(character, directory):
    """Favoris distincts des favoris de succès, propres à chaque personnage."""
    if not character:
        return set(DEFAULT_FAVORITES)
    try:
        doc = json.loads(_path(directory).read_text(encoding="utf-8"))
        per_character = doc.get("characters", {}).get(str(character))
        if isinstance(per_character, list):
            return {key for key in per_character if isinstance(key, str) and key in KEYS}
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    return set(DEFAULT_FAVORITES)


def save_favorites(character, selected, directory):
    if not character:
        return
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    path = _path(folder)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            doc = {}
    except (OSError, ValueError):
        doc = {}
    people = doc.get("characters")
    if not isinstance(people, dict):
        people = {}
    people[str(character)] = sorted(set(selected) & KEYS)
    doc["characters"] = people
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
