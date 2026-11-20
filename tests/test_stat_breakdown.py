"""Détail de la contribution des Vikings : mêmes valeurs et règles que le cumul."""
import unittest

from stat_breakdown import breakdown
from viking_stats import STATS
from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX

STAT_BY_KEY = {s.key: s for s in STATS}


def character(name, player_id, counters=None, hard=None, world_seconds=None):
    def data(counter_values):
        stats = [0.0] * len(PLAYER_STAT_NAMES)
        for key, val in (counter_values or {}).items():
            stats[STAT_INDEX[key]] = float(val)
        return {"stats": stats, "worlds": {}}
    groups = {"Any": data(counters), "RawStats": data(counters)}
    groups["RawStats"]["worlds"] = (
        {"monde": float(world_seconds)} if world_seconds is not None else {})
    if hard is not None:
        groups["Hard"] = data(hard)
    return {"name": name, "player_id": player_id, "groups": groups}


def person(profile, source="archive", filename="ancien.fch"):
    return {"id": "id:" + str(profile["player_id"]),
            "name": profile["name"],
            "source": source, "filename": filename, "profile": profile}


class CharacterBreakdownTests(unittest.TestCase):
    def setUp(self):
        self.a = person(character(
            "Joueur 1", 111, {
                "DistanceRun": 29492, "Deaths": 5,
                "ConsecutiveDaysSurvivedMax": 19, "ExploreNorth": 0,
            }, hard={"Deaths": 2}, world_seconds=7200))
        self.b = person(character(
            "Joueur 2", 222, {
                "DistanceRun": 1948292, "Deaths": 8,
                "ConsecutiveDaysSurvivedMax": 34, "ExploreNorth": 1,
            }, hard={"Deaths": 3}, world_seconds=3600))

    def test_sum_shows_every_person_and_exact_total(self):
        result = breakdown(STAT_BY_KEY["run"], [self.a, self.b])
        self.assertEqual(result.policy, "sum")
        self.assertEqual(result.total, 1977784.0)
        self.assertEqual([r.name for r in result.rows], ["Joueur 2", "Joueur 1"])
        self.assertEqual([r.amount for r in result.rows], [1948292, 29492])
        self.assertAlmostEqual(sum(r.percentage for r in result.rows), 100)
        self.assertAlmostEqual(result.rows[0].percentage, 100 * 1948292 / 1977784)

    def test_max_keeps_best_record_without_adding(self):
        result = breakdown(STAT_BY_KEY["survivor"], [self.a, self.b])
        self.assertEqual(result.policy, "max")
        self.assertEqual(result.total, 34)
        self.assertTrue(result.rows[0].leading)
        self.assertFalse(result.rows[1].leading)
        self.assertTrue(all(r.percentage is None for r in result.rows))

    def test_boolean_uses_any_not_sum(self):
        result = breakdown(STAT_BY_KEY["explore_north"], [self.a, self.b])
        self.assertEqual(result.policy, "any")
        self.assertEqual(result.total, 1)
        self.assertEqual([r.amount for r in result.rows], [1, 0])
        self.assertTrue(result.rows[0].leading)
        self.assertTrue(all(r.percentage is None for r in result.rows))

    def test_hours_from_raw_world_times_are_summed(self):
        result = breakdown(STAT_BY_KEY["world_hours"], [self.a, self.b])
        self.assertEqual(result.policy, "sum")
        self.assertEqual(result.total, 3)
        self.assertEqual([r.amount for r in result.rows], [2, 1])

    def test_difficulty_groups_are_not_added_to_each_other(self):
        normal = breakdown(STAT_BY_KEY["deaths"], [self.a, self.b], "Any")
        hard = breakdown(STAT_BY_KEY["deaths"], [self.a, self.b], "Hard")
        self.assertEqual(normal.total, 13)
        self.assertEqual(hard.total, 5)
        self.assertEqual(hard.group, "Hard")
        self.assertEqual([r.amount for r in hard.rows], [3, 2])

    def test_unsupported_stat_shows_missing_not_zero(self):
        short = character("Ancien", 333, {"Deaths": 3})
        short["groups"]["Any"]["stats"] = [3.0]
        short["groups"]["RawStats"]["stats"] = [3.0]
        missing = person(short)
        result = breakdown(STAT_BY_KEY["run"], [self.a, missing])
        self.assertEqual(result.total, 29492)
        self.assertEqual(result.rows[-1].name, "Ancien")
        self.assertIsNone(result.rows[-1].amount)
        self.assertIsNone(result.rows[-1].percentage)
        self.assertEqual(
            breakdown(STAT_BY_KEY["run"], [missing]).total, None
        )

    def test_active_overrides_archived_same_id(self):
        old = person(character("Ancien", 111, {"Deaths": 200}))
        updated = person(character("Actuel", 111, {"Deaths": 5}), "active")
        result = breakdown(STAT_BY_KEY["deaths"], [old, updated, self.b])
        self.assertEqual(result.total, 13)
        self.assertEqual(len(result.rows), 2)
        self.assertTrue(any(r.source == "active" for r in result.rows))

    def test_zero_sum_does_not_invent_percentages(self):
        x = person(character("Zéro", 333, {"Deaths": 0}))
        result = breakdown(STAT_BY_KEY["deaths"], [x])
        self.assertEqual(result.total, 0)
        self.assertEqual(result.rows[0].amount, 0)
        self.assertIsNone(result.rows[0].percentage)


if __name__ == "__main__":
    unittest.main()
