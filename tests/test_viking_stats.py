"""Tests non-régression V2.4.0 : statistiques exactes, unités et favoris séparés."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX
from viking_stats import (
    CATEGORIES, DEFAULT_FAVORITES, KEYS, STATS, change, favorites,
    pretty, save_favorites, value,
)


def make_profile(name="Viking", **counters):
    data = [0.0] * len(PLAYER_STAT_NAMES)
    for key, val in counters.items():
        data[STAT_INDEX[key]] = val
    return {
        "name": name,
        "groups": {
            "Any": {"stats": data},
            "Default": {"stats": data.copy()},
            "RawStats": {"stats": data.copy(), "worlds": {"Fiskeby": 21_600}},
        },
    }


def spec(key):
    return next(x for x in STATS if x.key == key)


class VikingStatsTests(unittest.TestCase):
    def test_every_card_is_grounded_in_readable_save_counters(self):
        self.assertGreaterEqual(len(STATS), 35)
        self.assertEqual(len(KEYS), len(STATS))
        self.assertEqual(len(CATEGORIES), 5)
        self.assertTrue(all(stat.counter in STAT_INDEX or stat.counter == "@world_hours"
                            for stat in STATS))
        self.assertNotIn("swim", KEYS)
        self.assertEqual(spec("trees").counter, "Tree")
        self.assertEqual(spec("walk").counter, "DistanceWalk")
        self.assertEqual(spec("run").counter, "DistanceRun")
        self.assertEqual(spec("sail").counter, "DistanceSail")
        self.assertEqual(spec("helm").counter, "DistanceSailHelm")
        self.assertEqual(spec("built").counter, "Builds")
        self.assertEqual(spec("height").counter, "MaxBuildingHeight")

    def test_distance_units_and_separate_travel_modes(self):
        hero = make_profile(DistanceTraveled=18532, DistanceWalk=6420,
                            DistanceRun=10810, DistanceSail=1105, DistanceSailHelm=340)
        self.assertEqual(value(hero, spec("walk")), 6420)
        self.assertEqual(value(hero, spec("run")), 10810)
        self.assertEqual(value(hero, spec("sail")), 1105)
        self.assertEqual(value(hero, spec("helm")), 340)
        self.assertEqual(pretty(value(hero, spec("walk")), "distance"), "6,4 km")
        self.assertEqual(pretty(value(hero, spec("helm")), "distance"), "340 m")

    def test_raw_world_seconds_are_hours_and_dont_double_count_groups(self):
        hero = make_profile()
        self.assertEqual(value(hero, spec("world_hours")), 6)
        self.assertEqual(pretty(value(hero, spec("world_hours")), "hours"), "6,0 h")
        self.assertEqual(value(None, spec("world_hours")), None)
        self.assertEqual(value({"groups": {}}, spec("walk")), None)

    def test_live_binaries_and_counters(self):
        hero = make_profile(Tree=456, TreeChops=900, MaxBuildingHeight=47.5,
                            ExploreNorth=1, ExploreSouth=0)
        self.assertEqual(pretty(value(hero, spec("trees")), "number"), "456")
        self.assertEqual(pretty(value(hero, spec("height")), "metres"), "47,5 m")
        self.assertEqual(pretty(value(hero, spec("explore_north")), "binary"), "Validé")
        self.assertEqual(pretty(value(hero, spec("explore_south")), "binary"), "À atteindre")

    def test_deltas_never_report_saves_reset_as_loss_or_gain(self):
        old = make_profile(Tree=400, DistanceWalk=2234)
        current = make_profile(Tree=410, DistanceWalk=2424)
        self.assertEqual(change(current, old, spec("trees")), 10)
        self.assertEqual(change(current, old, spec("walk")), 190)
        self.assertEqual(change(old, current, spec("trees")), None)
        self.assertIsNone(change(current, None, spec("trees")))
        self.assertIsNone(change(None, old, spec("trees")))

    def test_favorites_are_per_character_and_do_not_touch_achievement_favorites(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            achievements = root / "favoris.json"
            achievements.write_text('{"characters":{"Ruthvenson":["explorer"]}}', encoding="utf-8")
            self.assertEqual(favorites("Ruthvenson", root), set(DEFAULT_FAVORITES))
            save_favorites("Ruthvenson", {"trees", "walk", "invalid"}, root)
            save_favorites("Fiskeby", {"fish"}, root)
            self.assertEqual(favorites("Ruthvenson", root), {"trees", "walk"})
            self.assertEqual(favorites("Fiskeby", root), {"fish"})
            self.assertEqual(achievements.read_text(encoding="utf-8"),
                             '{"characters":{"Ruthvenson":["explorer"]}}')
            save_favorites("Ruthvenson", set(), root)
            self.assertEqual(favorites("Ruthvenson", root), set())


if __name__ == "__main__":
    unittest.main()
