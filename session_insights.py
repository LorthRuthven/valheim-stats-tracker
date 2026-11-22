"""Analyse des sessions estimées à partir de relevés .fch, sans écriture.

Les intervalles sont séparés par un écart supérieur à 90 min entre relevés.
Les durées entre relevés ne sont pas assimilées à du temps joué.
"""
from __future__ import annotations

from datetime import datetime
import math

from v2_core import GAP_SECONDS, _stat


METRICS = (
    ("kills", "kills"),
    ("builds", "built"),
    ("crafts", "crafted"),
    ("deaths", "deaths"),
)


def session_insights(rows, gap_seconds=GAP_SECONDS, limit=12):
    """Renvoie des sessions chronologiques inversées comportant >=2 relevés.

    Le gain d'un compteur est ignoré si sa valeur recule. Les profils manquants
    sont ignorés et aucun temps de jeu fictif n'est estimé.
    """
    if gap_seconds <= 0:
        raise ValueError("Écart de session invalide")
    ordered = sorted(
        (r for r in rows if len(r) >= 4 and isinstance(r[3], dict)
         and isinstance(r[1], (int, float)) and math.isfinite(r[1])),
        key=lambda r: (r[1], r[0])
    )
    groups = []
    current = []
    for row in ordered:
        if current and row[1] - current[-1][1] > gap_seconds:
            groups.append(current)
            current = []
        current.append(row)
    if current:
        groups.append(current)

    results = []
    for group in reversed(groups):
        if len(group) < 2:
            continue
        first, last = group[0], group[-1]
        gains = {}
        resets = []
        for label, key in METRICS:
            try:
                earlier = _stat(first[3], key)
                later = _stat(last[3], key)
            except (KeyError, ValueError, TypeError, IndexError, OverflowError):
                continue
            if not (math.isfinite(earlier) and math.isfinite(later)):
                continue
            delta = later - earlier
            if delta < -0.0001:
                resets.append(label)
            else:
                gains[label] = max(0.0, delta)
        results.append({
            "start": float(first[1]),
            "end": float(last[1]),
            "samples": len(group),
            "span_minutes": (float(last[1]) - float(first[1])) / 60,
            "gains": gains,
            "resets": resets,
        })
        if len(results) >= max(1, int(limit)):
            break
    return results


def session_records(sessions):
    """Records des gains mesurables entre les sauvegardes d'une session.

    Un recul de compteur est exclu et non transformé en record.
    """
    descriptions = {
        "kills": "Créatures vaincues",
        "builds": "Constructions",
        "crafts": "Objets fabriqués",
        "deaths": "Décès",
    }
    records = []
    for key, title in descriptions.items():
        candidates = [s for s in sessions
                      if key in s.get("gains", {}) and s["gains"][key] > 0]
        if not candidates:
            continue
        winning = max(candidates, key=lambda s: (s["gains"][key], s["end"]))
        records.append({
            "key": key, "title": title,
            "value": winning["gains"][key], "start": winning["start"],
            "end": winning["end"],
        })
    return records


def readable_session(item):
    start = datetime.fromtimestamp(item["start"]).strftime("%d/%m %H:%M")
    end = datetime.fromtimestamp(item["end"]).strftime("%H:%M")
    if datetime.fromtimestamp(item["end"]).date() != datetime.fromtimestamp(item["start"]).date():
        end = datetime.fromtimestamp(item["end"]).strftime("%d/%m %H:%M")
    return f"{start} → {end}"
