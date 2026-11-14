"""Regression tests for achievements' exact statistics and difficulty sets."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valheim_reader import (STAT_INDEX, PLAYER_STAT_NAMES, SPECS,
                            evaluate_one, evaluate_all, progress_delta)


def synthetic():
    groups = {}
    for name in ('Any', 'Default', 'Hard'):
        stats = [0.0] * 205
        groups[name] = {'stats': stats, 'enemies': [{}, {}, {}, {}, {}], 'pickables': {}}
    groups['RawStats'] = {'stats': [0.0]*205}
    return {'groups': groups}


def spec(name):
    return next(s for s in SPECS if s.key == name)


class AchievementRulesTests(unittest.TestCase):
    def test_stat_indices_v47(self):
        self.assertEqual(len(PLAYER_STAT_NAMES), 205)
        self.assertEqual(STAT_INDEX['Tree'], 28)
        self.assertEqual(STAT_INDEX['TreeChops'], 27)
        self.assertEqual(STAT_INDEX['BuiltPiecesNoDebt'], 169)
        self.assertEqual(STAT_INDEX['DeathByTree'], 68)
        self.assertEqual(STAT_INDEX['TreeFir'], 193)
        self.assertEqual(STAT_INDEX['DeathByAshlandsLava'], 204)

    def test_lumberjack_ignores_chops_and_raw_stats(self):
        p = synthetic()
        p['groups']['RawStats']['stats'][28] = 1000
        p['groups']['Any']['stats'][STAT_INDEX['TreeChops']] = 600
        p['groups']['Any']['stats'][STAT_INDEX['Tree']] = 18
        a = evaluate_one(p, spec('lumberjack'))
        self.assertFalse(a['complete'])
        self.assertEqual(a['parts'][0]['current'], 18)
        self.assertEqual(a['parts'][0]['remaining'], 482)
        p['groups']['Any']['stats'][STAT_INDEX['Tree']] = 500
        self.assertTrue(evaluate_one(p, spec('lumberjack'))['complete'])

    def test_multiparts_require_all_and_show_remaining(self):
        p = synthetic()
        p['groups']['Any']['stats'][STAT_INDEX['HarvestBerry']] = 250
        p['groups']['Any']['stats'][STAT_INDEX['HarvestMushroom']] = 67
        a = evaluate_one(p, spec('forager'))
        self.assertFalse(a['complete'])
        self.assertEqual(a['completed_conditions'], 1)
        self.assertEqual(a['parts'][1]['remaining'], 183)

    def test_tree_deaths_are_not_felled_trees(self):
        p = synthetic()
        p['groups']['Any']['stats'][STAT_INDEX['TreeFir']] = 1
        p['groups']['Any']['stats'][STAT_INDEX['Tree']] = 600
        result = evaluate_one(p, spec('treesall'))
        self.assertEqual(result['completed_conditions'], 1)
        self.assertEqual(result['total_conditions'], 10)
        self.assertFalse(result['complete'])

    def test_boss_difficulty_groups_are_separate(self):
        p = synthetic()
        p['groups']['Any']['enemies'][0]['$enemy_eikthyr'] = 1
        p['groups']['Default']['enemies'][0]['$enemy_eikthyr'] = 1
        self.assertEqual(evaluate_one(p, spec('viking'))['completed_conditions'], 1)
        self.assertEqual(evaluate_one(p, spec('tough'))['completed_conditions'], 1)
        self.assertEqual(evaluate_one(p, spec('toughest'))['completed_conditions'], 0)

    def test_fish_count_uses_pickables(self):
        p = synthetic()
        p['groups']['Any']['pickables']['$animal_fish1'] = 3
        r = evaluate_one(p, spec('fisherman'))
        self.assertEqual(r['completed_conditions'], 1)
        self.assertEqual(r['total_conditions'], 12)

    def test_delta_since_previous_snapshot(self):
        p = synthetic()
        before = evaluate_one(p, spec('farmer'))
        p['groups']['Any']['stats'][STAT_INDEX['HarvestCrop']] = 13
        after = evaluate_one(p, spec('farmer'))
        self.assertEqual(progress_delta(after, before), [('Récoltes cultivées', 13.0)])

    def test_no_steam_status_claim(self):
        p = synthetic()
        a = evaluate_all(p)
        self.assertTrue(all('complete' in r for r in a))
        self.assertTrue(all('steam_unlocked' not in r for r in a))
        self.assertGreaterEqual(len(a), 30)


if __name__ == '__main__':
    unittest.main()
