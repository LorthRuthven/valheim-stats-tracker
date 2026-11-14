"""Tests de traduction française et d'isolation des difficultés Valheim."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from valheim_reader import SPECS, ACHIEVEMENTS_FR, achievement_title, evaluate_all, evaluate_one
from app import GROUP_FR

def synthetic():
    groups = {}
    for name in ('Any', 'Default', 'Hard'):
        groups[name] = {'stats': [0.] * 205, 'enemies': [{}, {}, {}, {}, {}],
                        'pickables': {}, 'crafted': {}, 'picked_up': {},
                        'foods_eaten': {}, 'pieces_built': {}}
    return {'groups': groups}

class FrenchAchievementTests(unittest.TestCase):
    def test_official_translations_cover_55_achievements(self):
        self.assertEqual(len(ACHIEVEMENTS_FR), 55)
        self.assertEqual(set(ACHIEVEMENTS_FR), {s.key for s in SPECS})
        results = evaluate_all(synthetic())
        self.assertEqual(len(results), 55)
        self.assertEqual(next(x['title'] for x in results if x['key'] == 'master_hunter'), 'Maîtrise de la chasse')
        self.assertEqual(next(x['title'] for x in results if x['key'] == 'pugilist_internal'), 'Pugilat')
        self.assertEqual(next(x['title_en'] for x in results if x['key'] == 'master_hunter'), 'The Master Hunter')

    def test_master_hunter_is_not_miscounted_in_normal(self):
        p = synthetic()
        monster = '$enemy_greydwarf'
        p['groups']['Any']['enemies'][0][monster] = 6
        p['groups']['Default']['enemies'][0][monster] = 6
        specifications = {s.key: s for s in SPECS}
        self.assertEqual(evaluate_one(p, specifications['hunter'])['completed_conditions'], 1)
        self.assertEqual(evaluate_one(p, specifications['master_hunter'])['completed_conditions'], 0)
        p['groups']['Hard']['enemies'][0][monster] = 1
        self.assertEqual(evaluate_one(p, specifications['master_hunter'])['completed_conditions'], 1)

    def test_french_difficulty_labels_keep_stable_internal_ids(self):
        self.assertEqual(GROUP_FR['Any'], 'Toutes difficultés')
        self.assertEqual(GROUP_FR['Hard'], 'Difficile ou +')
        self.assertEqual(achievement_title('boss_single_kall'), 'Kall Mandefimbul')

if __name__ == '__main__':
    unittest.main()
