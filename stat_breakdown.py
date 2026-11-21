"""Répartition vérifiable de chaque statistique entre personnages Valheim.

Pas de lecture/écriture des sauvegardes. Les valeurs individuelles passent par le
même calcul que les cartes. Le total passe par combine_profiles, à l'identique
du mode Cumul. On ne mélange jamais les groupes de difficulté.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from character_archive import aggregation_mode, combine_profiles
from viking_stats import value


@dataclass(frozen=True)
class CharacterContribution:
    identity: str
    name: str
    source: str
    filename: str
    amount: float | None
    percentage: float | None
    leading: bool


@dataclass(frozen=True)
class CumulativeBreakdown:
    total: float | None
    policy: str
    group: str
    rows: tuple[CharacterContribution, ...]


def breakdown(stat, people, group="Any"):
    """Calcule les lignes à afficher avec les mêmes règles que le total.

    Les membres sont dédupliqués par identité persistante. L'actif prime sur
    son éventuelle ancienne archive, comme dans CharacterArchive.entries().
    Les valeurs non enregistrées restent None, jamais converties en zéro.
    """
    unique = {}
    for item in people:
        identity = str(item["id"])
        if identity not in unique or (item.get("source") == "active"
                                       and unique[identity].get("source") != "active"):
            unique[identity] = item
    members = list(unique.values())
    profiles = [item["profile"] for item in members]
    aggregate = combine_profiles(profiles)
    total = value(aggregate, stat, group)
    policy = ("sum" if stat.counter == "@world_hours"
              else aggregation_mode(stat.counter))

    pairs = []
    for item in members:
        number = value(item["profile"], stat, group)
        if number is not None and not math.isfinite(number):
            number = None
        pairs.append((item, number))
    pairs.sort(key=lambda pair: (
        pair[1] is None,
        -(pair[1] if pair[1] is not None else 0),
        pair[0]["name"].casefold(),
        str(pair[0]["id"]),
    ))
    rows = []
    for item, number in pairs:
        percentage = None
        if (policy == "sum" and number is not None and total is not None
                and total > 0 and number >= 0):
            percentage = 100.0 * number / total
        leading = (number is not None and total is not None
                   and policy in ("max", "any") and number > 0
                   and math.isclose(number, total, rel_tol=1e-9, abs_tol=1e-9))
        rows.append(CharacterContribution(
            identity=str(item["id"]),
            name=str(item["name"]),
            source=str(item.get("source", "archive")),
            filename=str(item.get("filename", "")),
            amount=number,
            percentage=percentage,
            leading=leading,
        ))
    return CumulativeBreakdown(total, policy, group, tuple(rows))
