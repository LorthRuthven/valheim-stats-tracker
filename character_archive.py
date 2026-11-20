"""Archives de personnages .fch et totaux inter-personnages (lecture seule).

Les archives contiennent une copie des statistiques décodées, jamais une
sauvegarde .fch modifiée ou le fichier brut du joueur. Les personnages sont
identifiés par l'identifiant persistant Valheim, non par le nom du fichier.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import zlib
from pathlib import Path

from valheim_reader import GROUPS, PLAYER_STAT_NAMES, SaveError, decode

# Records, valeurs atteintes et états : ils ne sont jamais additionnés.
RECORDS = frozenset({
    "ConsecutiveDaysSurvived", "ConsecutiveDaysSurvivedMax",
    "MaxBuildingHeight", "MaxBuildingHeightWorld", "MaxComfort",
    "VillagePointsMax", "DeepestDungeon",
})
MAX_FILE_BYTES = 100 * 1024 * 1024


def character_key(profile):
    """Un nom peut être partagé par plusieurs personnages et sauvegardes."""
    player_id = profile.get("player_id")
    if player_id not in (None, "", 0, "0"):
        return "id:" + str(player_id)
    return "legacy:" + str(profile.get("created") or 0) + ":" + str(profile.get("name") or "")


def aggregation_mode(counter):
    """sum / max / any, à appliquer ENTRE personnages, jamais entre groupes."""
    if counter.startswith("Explore"):
        return "any"
    if counter in RECORDS or counter.startswith("Max") or counter.endswith("Max"):
        return "max"
    return "sum"


def _finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def combine_profiles(profiles):
    """Construit une vue synthétique sans la confondre avec un vrai personnage.

    La somme concerne uniquement les compteurs d'activité. Les records prennent
    leur maximum, les jalons sont des unions logiques. Aucune statistique d'un
    groupe de difficulté n'est ajoutée à celle d'un autre groupe.
    """
    profiles = list(profiles)
    if not profiles:
        return None
    if len(profiles) == 1:
        return profiles[0]
    groups = {}
    for group in GROUPS:
        group_data = [p.get("groups", {}).get(group, {}) for p in profiles]
        if not any(item for item in group_data):
            continue
        stats = []
        for index, counter in enumerate(PLAYER_STAT_NAMES):
            vals = []
            for item in group_data:
                raw = item.get("stats")
                if isinstance(raw, (list, tuple)) and index < len(raw):
                    num = _finite(raw[index])
                    if num is not None:
                        vals.append(num)
            policy = aggregation_mode(counter)
            stats.append((max(vals) if policy in ("max", "any") else sum(vals))
                         if vals else None)
        data = {"stats": stats}
        for name in ("worlds", "picked_up", "crafted", "pickables",
                     "foods_eaten", "pieces_built", "commands"):
            combined = {}
            for item in group_data:
                mapping = item.get(name, {})
                if not isinstance(mapping, dict):
                    continue
                for key, raw in mapping.items():
                    value = _finite(raw)
                    if value is not None:
                        combined[key] = combined.get(key, 0.0) + value
            data[name] = combined
        enemies = []
        for position in range(5):
            combined = {}
            for item in group_data:
                entries = item.get("enemies", [])
                if not isinstance(entries, list) or position >= len(entries):
                    continue
                mapping = entries[position]
                if not isinstance(mapping, dict):
                    continue
                for key, raw in mapping.items():
                    value = _finite(raw)
                    if value is not None:
                        combined[key] = combined.get(key, 0.0) + value
            enemies.append(combined)
        data["enemies"] = enemies
        # Les clés de découverte de monde ne sont pas des volumes d'activité.
        data["worldkeys"] = {}
        groups[group] = data
    return {
        "name": "Tous les personnages",
        "combined_count": len(profiles),
        "aggregate": True,
        "groups": groups,
    }


class CharacterArchive:
    """Registre local indépendant du suivi automatique et de l'historique."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.execute("""CREATE TABLE IF NOT EXISTS archived_characters (
            character_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sha TEXT NOT NULL,
            filename TEXT NOT NULL,
            observed_at REAL NOT NULL,
            data BLOB NOT NULL
        )""")
        self.connection.commit()

    def import_files(self, filenames):
        """Import multiple avec bilan individuel; même identité = remplacement."""
        result = {"added": 0, "updated": 0, "unchanged": 0, "errors": []}
        for filename in filenames:
            target = Path(filename).expanduser()
            try:
                if target.suffix.lower() != ".fch" or not target.is_file():
                    raise ValueError("Ce fichier n'est pas une sauvegarde .fch")
                if target.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("Fichier anormalement volumineux")
                raw = target.read_bytes()
                profile = decode(raw)  # Contrôle d'intégrité SHA-512 intégré.
                identity = character_key(profile)
                digest = hashlib.sha256(raw).hexdigest()
                existing = self.connection.execute(
                    "SELECT sha FROM archived_characters WHERE character_id=?",
                    (identity,),
                ).fetchone()
                if existing and existing[0] == digest:
                    result["unchanged"] += 1
                    continue
                payload = zlib.compress(json.dumps(
                    profile, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8"))
                self.connection.execute("""INSERT INTO archived_characters
                    (character_id, name, sha, filename, observed_at, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(character_id) DO UPDATE SET
                        name=excluded.name, sha=excluded.sha,
                        filename=excluded.filename,
                        observed_at=excluded.observed_at, data=excluded.data
                """, (identity, profile["name"], digest, target.name,
                      target.stat().st_mtime, payload))
                self.connection.commit()
                result["updated" if existing else "added"] += 1
            except (OSError, ValueError, IndexError, SaveError, sqlite3.Error) as error:
                result["errors"].append(f"{target.name} : {error}")
        return result

    def entries(self, active_profile=None):
        """L'actif prime sur une archive de même ID, évitant le double comptage."""
        records = self.connection.execute("""SELECT character_id, name, filename,
            observed_at, data FROM archived_characters
            ORDER BY name COLLATE NOCASE, character_id""").fetchall()
        people = []
        for identity, name, filename, observed_at, data in records:
            try:
                profile = json.loads(zlib.decompress(data))
                if not isinstance(profile, dict):
                    continue
            except (ValueError, TypeError, zlib.error):
                continue
            people.append({"id": identity, "name": name,
                           "source": "archive", "filename": filename,
                           "observed_at": observed_at, "profile": profile})
        if active_profile:
            identity = character_key(active_profile)
            people = [p for p in people if p["id"] != identity]
            people.insert(0, {"id": identity, "name": active_profile["name"],
                              "source": "active", "filename": "",
                              "observed_at": None, "profile": active_profile})
        return people

    def remove(self, identity):
        """Retire seulement l'import du tracker, jamais le vrai fichier .fch."""
        cursor = self.connection.execute(
            "DELETE FROM archived_characters WHERE character_id=?", (identity,)
        )
        self.connection.commit()
        return bool(cursor.rowcount)
