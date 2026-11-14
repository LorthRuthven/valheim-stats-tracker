"""Valheim Stats Tracker 2.0: moteur sans dépendance graphique.

Compatible avec l'historique SQLite et les favoris de la série 1.x.
Toutes les lectures .fch sont en lecture seule. Le statut Steam n'est pas lu.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

from valheim_reader import (
    BOSSES, SPECS, STAT_INDEX, SaveError, decode, evaluate_all,
    metrics, prefab_label,
)

VERSION = "2.0.0"
DATA_FOLDER = "ValheimStatsTracker"
GAP_SECONDS = 90 * 60


def app_dir() -> Path:
    folder = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / DATA_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def db_open(directory: Path | None = None):
    directory = Path(directory) if directory is not None else app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / "historique.sqlite3", timeout=12)
    connection.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character TEXT NOT NULL,
        sha TEXT NOT NULL,
        observed_at REAL NOT NULL,
        filename TEXT NOT NULL,
        data BLOB NOT NULL,
        UNIQUE(character,sha)
    )""")
    connection.execute("CREATE INDEX IF NOT EXISTS ix_snap_character ON snapshots(character,observed_at)")
    connection.commit()
    return connection


def sample_rows(connection, character: str, limit: int = 250):
    """Dans le même format (id, timestamp, filename, profile) que la V1.9."""
    records = connection.execute(
        """SELECT id, observed_at, filename, data FROM snapshots
           WHERE character=? ORDER BY observed_at DESC, id DESC LIMIT ?""",
        (character, max(1, min(5000, int(limit)))),
    ).fetchall()
    return [(idx, ts, fname, json.loads(zlib.decompress(payload)))
            for idx, ts, fname, payload in reversed(records)]


def save_snapshot(connection, profile, digest: str, filename: str, modified: float):
    connection.execute("INSERT OR IGNORE INTO snapshots(character,sha,observed_at,filename,data) VALUES (?,?,?,?,?)",
                       (profile["name"], digest, modified, filename,
                        zlib.compress(json.dumps(profile, ensure_ascii=False,
                                                 separators=(",", ":")).encode("utf8"))))
    connection.commit()


def default_save() -> str:
    files = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as reg:
            steam = Path(winreg.QueryValueEx(reg, "SteamPath")[0])
        for path in ("userdata/*/892970/remote/characters/*.fch",
                     "userdata/*/892970/remote/characters_local/*.fch"):
            files.extend(steam.glob(path))
    except (ImportError, OSError, ValueError):
        pass
    for base in (Path.home() / "AppData/LocalLow/IronGate/Valheim/characters_local",
                 Path.home() / "AppData/LocalLow/IronGate/Valheim/characters"):
        files.extend(base.glob("*.fch"))
    valid = [p for p in files if p.is_file() and not p.name.lower().endswith(".fch_backup")]
    return str(max(valid, key=lambda p: p.stat().st_mtime)) if valid else ""


def read_config(directory: Path | None = None) -> dict:
    path = (Path(directory) if directory is not None else app_dir()) / "config.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (ValueError, OSError):
        return {}


def write_config_save(path: str, directory: Path | None = None):
    dest = (Path(directory) if directory is not None else app_dir()) / "config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = read_config(dest.parent)
    content["path"] = path
    # Mise à jour atomique pour ne pas abîmer les réglages 1.x.
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(dest)


def load_favorites(character: str, directory: Path | None = None) -> set[str]:
    path = (Path(directory) if directory is not None else app_dir()) / "favoris.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        saved = obj.get("characters", {}).get(character, [])
        valid = {spec.key for spec in SPECS}
        return {s for s in saved if isinstance(s, str) and s in valid} if isinstance(saved, list) else set()
    except (OSError, ValueError, TypeError, AttributeError):
        return set()


def save_favorites(character: str, selected: set[str], directory: Path | None = None):
    folder = Path(directory) if directory is not None else app_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "favoris.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            obj = {}
    except (ValueError, OSError):
        obj = {}
    characters = obj.get("characters", {})
    if not isinstance(characters, dict):
        characters = {}
    valid = {spec.key for spec in SPECS}
    characters[str(character)] = sorted(selected & valid)
    obj["characters"] = characters
    tmp = folder / "favoris.json.tmp"
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def progress_ranking(results: list[dict], favorites=()) -> list[dict]:
    fav = set(favorites)
    eligible = [a for a in results if a.get("measurable") and not a.get("complete")
                and a.get("fraction") is not None]
    eligible.sort(key=lambda a: (-float(a.get("fraction") or 0),
                                 -int(a.get("completed_conditions") or 0),
                                 a.get("title", "").casefold()))
    return [{**a, "favorite": a["key"] in fav} for a in eligible]


def pending_actions(result: dict, limit: int = 12) -> list[dict]:
    if not result.get("measurable") or result.get("complete"):
        return []
    parts = [p for p in result.get("parts", ()) if not p.get("complete") and p.get("goal") is not None]
    parts.sort(key=lambda p: (max(0.0, float(p.get("remaining") or 0)) / max(1.0, float(p["goal"])),
                              str(p.get("label", "")).casefold()))
    return parts[:max(0, limit)]


SESSION_METRICS = (
    ("Ennemis vaincus", "kills"),
    ("Décès", "deaths"),
    ("Objets fabriqués", "crafted"),
    ("Constructions", "built"),
    ("Objets ramassés", "picked_up"),
    ("Arbres abattus", "Tree"),
    ("Cultures récoltées", "HarvestCrop"),
    ("Miel récolté", "BeesHarvested"),
)


def _stat(profile: dict, key: str):
    if key in {"kills", "deaths", "crafted", "built", "picked_up", "world_hours"}:
        return float(metrics(profile, "Any")[key])
    if key.startswith("skill:"):
        return float(profile.get("skills", {}).get(key[6:], {}).get("level", 0))
    pos = STAT_INDEX.get(key)
    if pos is not None:
        return float(profile["groups"]["Any"]["stats"][pos])
    return 0.0


def session_report(rows: list, gap_seconds=GAP_SECONDS) -> dict:
    if not rows:
        return {"available": False, "reason": "Aucune sauvegarde enregistrée."}
    ordered = sorted(rows, key=lambda r: (r[1], r[0]))
    i = len(ordered) - 1
    while i > 0 and 0 <= ordered[i][1] - ordered[i-1][1] <= gap_seconds:
        i -= 1
    part = ordered[i:]
    if len(part) < 2:
        return {"available": False, "reason": "Une seule sauvegarde dans la dernière session estimée."}
    first, last = part[0], part[-1]
    changes = {}
    reset = []
    for title, key in SESSION_METRICS:
        difference = _stat(last[3], key) - _stat(first[3], key)
        if difference < -0.0001:
            reset.append(title)
        else:
            changes[title] = difference
    skills = []
    for name, entry in last[3].get("skills", {}).items():
        prior = first[3].get("skills", {}).get(name)
        if prior:
            delta = float(entry.get("level", 0)) - float(prior.get("level", 0))
            if delta > .0001:
                skills.append((name, delta))
    skills.sort(key=lambda item: (-item[1], item[0]))
    previous = {a["key"]: a for a in evaluate_all(first[3]) if a["measurable"]}
    reached = [a["title"] for a in evaluate_all(last[3]) if a["measurable"] and a["complete"]
               and a["key"] in previous and not previous[a["key"]]["complete"]]
    left_seconds = sum(first[3]["groups"]["RawStats"]["worlds"].values())
    right_seconds = sum(last[3]["groups"]["RawStats"]["worlds"].values())
    return {"available": True, "start": first[1], "end": last[1], "samples": len(part),
            "changes": changes, "resets": reset, "skills": skills[:8], "reached": reached,
            "game_minutes": max(0, (right_seconds-left_seconds)/60)}


def history_series(rows: list, key: str, since_seconds: float | None = None) -> list[tuple[float, float]]:
    data = [(float(r[1]), _stat(r[3], key)) for r in rows]
    if since_seconds is not None and data:
        cutoff = max(x[0] for x in data) - since_seconds
        data = [x for x in data if x[0] >= cutoff]
    return data


class TrackerStore:
    """État partagé avec la V1.x, aucune écriture sur les sauvegardes."""
    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory) if directory is not None else app_dir()
        self.db = db_open(self.directory)
        config = read_config(self.directory)
        configured = config.get("path", "")
        self.path = str(configured) if configured and Path(str(configured)).is_file() else default_save()
        self.profile = None
        self.sha = None
        self.stamp = None

    def choose(self, filename: str):
        target = Path(filename).expanduser().resolve()
        if target.suffix.lower() != ".fch" or not target.is_file():
            raise ValueError("Sélectionne un fichier de personnage Valheim .fch existant.")
        self.path = str(target)
        self.sha = None
        self.stamp = None
        self.profile = None
        write_config_save(str(target), self.directory)

    def refresh(self, force=False):
        if not self.path:
            return {"state": "missing", "message": "Choisis une sauvegarde .fch pour commencer."}
        target = Path(self.path)
        stat_before = target.stat()
        stamp = stat_before.st_mtime_ns, stat_before.st_size
        if not force and stamp == self.stamp:
            return {"state": "unchanged", "message": "Aucune nouvelle sauvegarde."}
        raw = target.read_bytes()
        after = target.stat()
        if (after.st_mtime_ns, after.st_size) != stamp:
            return {"state": "busy", "message": "Écriture en cours ; nouvelle vérification dans 5 secondes."}
        digest = hashlib.sha256(raw).hexdigest()
        if digest == self.sha and self.profile is not None:
            self.stamp = stamp
            return {"state": "unchanged", "message": "Sauvegarde inchangée : " +
                    datetime.fromtimestamp(after.st_mtime).strftime("%d/%m/%Y %H:%M:%S")}
        profile = decode(raw)
        # Reprise de la sauvegarde .old pour enrichir le premier historique, sans modification.
        old = Path(str(target) + ".old")
        if old.is_file() and not sample_rows(self.db, profile["name"], limit=1):
            try:
                prior_raw = old.read_bytes()
                prior = decode(prior_raw)
                if prior["name"] == profile["name"]:
                    save_snapshot(self.db, prior, hashlib.sha256(prior_raw).hexdigest(),
                                  old.name, old.stat().st_mtime)
            except (OSError, SaveError, IndexError, ValueError):
                pass
        save_snapshot(self.db, profile, digest, target.name, stat_before.st_mtime)
        self.profile = profile
        self.sha = digest
        self.stamp = stamp
        return {"state": "updated", "message": "Relevé du " +
                datetime.fromtimestamp(after.st_mtime).strftime("%d/%m/%Y %H:%M:%S")}

    def rows(self, limit=300):
        return sample_rows(self.db, self.profile["name"], limit) if self.profile else []

    def favorites(self):
        return load_favorites(self.profile["name"], self.directory) if self.profile else set()

    def toggle_favorite(self, key):
        if not self.profile:
            return set()
        previous = self.favorites()
        updated = previous ^ {key}
        save_favorites(self.profile["name"], updated, self.directory)
        return updated

    def close(self):
        self.db.close()
