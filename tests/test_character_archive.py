"""V2.5 (proposition) : archives .fch et totaux vérifiables, sans Qt."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from character_archive import (
    CharacterArchive, aggregation_mode, character_key, combine_profiles,
)
from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX, SaveError
from viking_stats import STATS, value


def profile(name, identity, **values):
    arr = [0.0] * len(PLAYER_STAT_NAMES)
    for key, number in values.items():
        arr[STAT_INDEX[key]] = number
    return {
        "name": name, "player_id": identity, "created": 1234,
        "groups": {
            "Any": {"stats": arr, "worlds": {}, "enemies": [{} for _ in range(5)]},
            "Default": {"stats": arr.copy()},
            "RawStats": {"stats": arr.copy(), "worlds": {"Fiskeby": 3600}},
        },
    }


def stat(key):
    return next(item for item in STATS if item.key == key)


class CharacterArchiveTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.archive = CharacterArchive(self.db)

    def tearDown(self):
        self.db.close()

    def test_distinct_id_even_with_same_name(self):
        a = profile("Ragnar", 111, Deaths=4)
        b = profile("Ragnar", 222, Deaths=7)
        self.assertNotEqual(character_key(a), character_key(b))
        self.assertEqual(value(combine_profiles([a, b]), stat("deaths")), 11)
        self.assertEqual(value(combine_profiles([a, b]), stat("world_hours")), 2)

    def test_achievements_and_records_are_not_summed(self):
        a = profile("A", 1, Deaths=3, MaxComfort=15, MaxBuildingHeight=200,
                    ConsecutiveDaysSurvivedMax=12, ExploreNorth=1)
        b = profile("B", 2, Deaths=6, MaxComfort=18, MaxBuildingHeight=150,
                    ConsecutiveDaysSurvivedMax=9, ExploreNorth=1)
        total = combine_profiles([a, b])
        self.assertEqual(value(total, stat("deaths")), 9)
        self.assertEqual(value(total, stat("comfort")), 18)
        self.assertEqual(value(total, stat("height")), 200)
        self.assertEqual(value(total, stat("survivor")), 12)
        self.assertEqual(value(total, stat("explore_north")), 1)
        self.assertEqual(aggregation_mode("ExploreNorth"), "any")
        self.assertEqual(aggregation_mode("MaxComfort"), "max")
        self.assertEqual(aggregation_mode("Deaths"), "sum")
        self.assertTrue(total["aggregate"])

    def test_difficulty_groups_never_added_together(self):
        a = profile("A", 1, EnemyKills=20)
        b = profile("B", 2, EnemyKills=40)
        a["groups"]["Default"]["stats"][STAT_INDEX["EnemyKills"]] = 11
        b["groups"]["Default"]["stats"][STAT_INDEX["EnemyKills"]] = 13
        total = combine_profiles([a, b])
        self.assertEqual(value(total, stat("kills"), "Any"), 60)
        self.assertEqual(value(total, stat("kills"), "Default"), 24)

    def test_import_update_unchanged_and_remove(self):
        first = profile("Ragnar", 444, Deaths=3)
        newer = profile("Ragnar", 444, Deaths=6)
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "ancien.fch"
            file.write_bytes(b"version1")
            with patch("character_archive.decode", return_value=first):
                report = self.archive.import_files([file])
                self.assertEqual(report["added"], 1)
                self.assertEqual(self.archive.import_files([file])["unchanged"], 1)
            file.write_bytes(b"version2")
            with patch("character_archive.decode", return_value=newer):
                report = self.archive.import_files([file])
                self.assertEqual(report["updated"], 1)
            self.assertEqual(len(self.archive.entries()), 1)
            self.assertEqual(value(self.archive.entries()[0]["profile"], stat("deaths")), 6)
            self.assertTrue(self.archive.remove(character_key(first)))
            self.assertEqual(self.archive.entries(), [])
            self.assertTrue(file.exists())  # Le .fch original n'est jamais effacé.

    def test_active_replaces_its_older_archive_in_total(self):
        archived = profile("A", 55, Deaths=12)
        other = profile("B", 66, Deaths=4)
        active = profile("A", 55, Deaths=21)
        with tempfile.TemporaryDirectory() as root:
            a = Path(root) / "a.fch"
            b = Path(root) / "b.fch"
            a.write_bytes(b"a")
            b.write_bytes(b"b")
            with patch("character_archive.decode", side_effect=[archived, other]):
                report = self.archive.import_files([a, b])
            self.assertEqual(report["added"], 2)
            entries = self.archive.entries(active)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["source"], "active")
            self.assertEqual(value(combine_profiles(p["profile"] for p in entries),
                                   stat("deaths")), 25)

    def test_invalid_files_are_reported_without_touching_database(self):
        with tempfile.TemporaryDirectory() as root:
            invalid = Path(root) / "old.fch"
            invalid.write_bytes(b"corrupt")
            strange = Path(root) / "nope.txt"
            strange.write_text("not a character")
            with patch("character_archive.decode", side_effect=SaveError("Fichier invalide")):
                report = self.archive.import_files([invalid, strange])
            self.assertEqual(report["added"], 0)
            self.assertEqual(len(report["errors"]), 2)
            self.assertEqual(self.archive.entries(), [])

    def test_empty_and_single_profile(self):
        self.assertIsNone(combine_profiles([]))
        a = profile("A", 1, Deaths=2)
        self.assertIs(combine_profiles([a]), a)


if __name__ == "__main__":
    unittest.main()
