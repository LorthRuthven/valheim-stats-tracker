"""Catalogue local Valheim V2.3.0, sans lecture ni modification de sauvegarde.

Les listes de prefabs appartiennent au suivi des succès. Les activités des
sauvegardes ne prouvent pas une découverte exhaustive ou un succès Steam.
"""
from __future__ import annotations

from valheim_reader import (
    _BUILDABLE, _CRAFT_EXTRA, _EATEN, _ENEMIES, _TROPHIES, _WEAPONS,
    localized_name, prefab_label,
)

CATEGORIES = (
    "Toutes catégories", "Créatures", "Trophées", "Armes",
    "Armures", "Nourritures", "Constructions", "Ressources", "Divers",
)
ACTIVITIES = (
    ("enemies", "Éliminations"),
    ("crafted", "Fabrications"),
    ("picked_up", "Ramassages"),
    ("pickables", "Récoltes"),
    ("pieces_built", "Constructions"),
    ("foods_eaten", "Consommations"),
)

def _tokens(text):
    return (token.strip() for token in text.split("|") if token.strip())

def _category(token):
    text = token.casefold()
    armor = ("helmet_", "chest_", "legs_", "cape_", "shield_")
    if any(text.startswith("$item_" + part) for part in armor):
        return "Armures"
    if text.startswith("$enemy_") or text.startswith("$animal_"):
        return "Créatures"
    if text.startswith("$piece_"):
        return "Constructions"
    if text.startswith("$item_"):
        return "Ressources"
    return "Divers"

def catalogue(profile=None):
    """Une ligne par prefab : catégorie, preuve d'activité et compteur exact.

    L'absence de compteur ne signifie pas que l'objet n'a jamais été obtenu.
    """
    entries = {}
    def add(token, category):
        token = str(token).strip()
        if not token or token in entries:
            return
        title = localized_name(token, prefab_label(token))
        entries[token] = {
            "token": token,
            "name": title if isinstance(title, str) and title else prefab_label(token),
            "category": category,
            "observed": False,
            "amount": 0.0,
            "evidence": [],
            "status": "Statut inconnu",
        }

    for token in _tokens(_ENEMIES):
        add(token, "Créatures")
    for token in _tokens(_TROPHIES):
        add(token, "Trophées")
    for token in _tokens(_WEAPONS):
        add(token, "Armes")
    for token in _tokens(_EATEN):
        add(token, "Nourritures")
    for token in _tokens(_BUILDABLE):
        add(token, "Constructions")
    for token in _tokens(_CRAFT_EXTRA):
        add(token, _category(token) if _category(token) == "Armures" else "Divers")

    group = (profile or {}).get("groups", {}).get("Any", {})
    for activity, label in ACTIVITIES:
        values = group.get(activity, {})
        if activity == "enemies":
            values = values[0] if isinstance(values, list) and values else {}
        if not isinstance(values, dict):
            continue
        for token, raw in values.items():
            if activity == "enemies":
                category = "Créatures"
            elif activity == "pieces_built":
                category = "Constructions"
            elif activity == "foods_eaten":
                category = "Nourritures"
            elif activity in ("picked_up", "pickables"):
                category = _category(token)
            else:
                category = _category(token)
            add(token, category)
            try:
                amount = max(0, float(raw))
            except (TypeError, ValueError):
                continue
            if amount <= 0:
                continue
            entry = entries[token]
            entry["observed"] = True
            entry["amount"] += amount
            entry["evidence"].append(f"{label} : {amount:g}")
            entry["status"] = "Activité enregistrée"
    return sorted(entries.values(), key=lambda e: (CATEGORIES.index(e["category"]),
                                                    e["name"].casefold(), e["token"].casefold()))
