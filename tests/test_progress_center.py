import tempfile
import unittest
from unittest.mock import patch

import app
from app import pending_actions, progress_ranking, load_favorites, save_favorites, estimate_last_session


def result(key, progress, complete=False, measurable=True):
    return {'key': key, 'title': key, 'measurable': measurable,
            'complete': complete, 'fraction': progress if measurable else None,
            'percent': progress * 100 if measurable else None,
            'completed_conditions': int(progress >= 1), 'total_conditions': 1,
            'parts': [{'label': 'Arbres', 'key': 'Tree', 'goal': 100,
                       'current': progress * 100, 'remaining': 100 - progress * 100,
                       'complete': complete}]}


def profile(marker=0, *, tree=0, kills=0, deaths=0, minutes=0, skills=10):
    stats = [0] * 205
    stats[app.STAT_INDEX['Tree']] = tree
    stats[app.STAT_INDEX['HarvestCrop']] = marker
    stats[app.STAT_INDEX['BeesHarvested']] = marker
    return {'marker': marker,
            'groups': {'Any': {'stats': stats}, 'RawStats': {'worlds': {'Fiskeby': minutes * 60}}},
            'skills': {'Course': {'level': skills}},
            'fake_metrics': {'kills': kills, 'deaths': deaths, 'crafted': marker,
                             'built': marker, 'picked_up': marker}}


class ProgressCenterTests(unittest.TestCase):
    def test_rank_excludes_finished_and_unverifiable(self):
        rows = [result('zero', 0), result('near', .9), result('mid', .5),
                result('done', 1, True), result('internal', 0, False, False)]
        ranked = progress_ranking(rows, {'mid'})
        self.assertEqual([x['key'] for x in ranked], ['near', 'mid', 'zero'])
        self.assertTrue(ranked[1]['favorite'])

    def test_pending_actions_prioritizes_closest_requirement(self):
        item = result('custom', .5)
        item['parts'] = [
            {'label': 'Long', 'key': 'long', 'complete': False,
             'goal': 100, 'current': 3, 'remaining': 97},
            {'label': 'Court', 'key': 'short', 'complete': False,
             'goal': 100, 'current': 92, 'remaining': 8},
            {'label': 'Atteint', 'key': 'done', 'complete': True,
             'goal': 1, 'current': 1, 'remaining': 0},
        ]
        self.assertEqual([x['label'] for x in pending_actions(item)], ['Court', 'Long'])
        self.assertEqual(pending_actions(result('done', 1, True)), [])
        self.assertEqual(pending_actions(result('unknown', 0, False, False)), [])

    def test_favourites_per_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_favorites('Ruthvenson', {'lumberjack', 'hunter', 'not-a-key'}, tmp)
            save_favorites('Autre', {'builder'}, tmp)
            self.assertEqual(load_favorites('Ruthvenson', tmp), {'lumberjack', 'hunter'})
            self.assertEqual(load_favorites('Autre', tmp), {'builder'})
            self.assertEqual(load_favorites('Inconnu', tmp), set())

    def test_session_report_with_new_objective(self):
        first = profile(1, tree=498, kills=10, minutes=100, skills=12)
        last = profile(3, tree=502, kills=15, minutes=115, skills=13.5)
        rows = [(1, 1000, 'before.fch', first), (2, 1600, 'after.fch', last)]
        def evaluated(profile):
            return [{'key': 'lumberjack', 'title': 'Bûcheronnage', 'measurable': True,
                     'complete': profile['groups']['Any']['stats'][app.STAT_INDEX['Tree']] >= 500}]
        with patch.object(app, 'metrics', side_effect=lambda p, g='Any': p['fake_metrics']), \
             patch.object(app, 'evaluate_all', side_effect=evaluated):
            report = estimate_last_session(rows)
        self.assertTrue(report['available'])
        self.assertEqual(report['changes']['Arbres abattus'], 4)
        self.assertEqual(report['changes']['Ennemis vaincus'], 5)
        self.assertEqual(report['minutes_played'], 15)
        self.assertEqual(report['new_goals'], ['Bûcheronnage'])
        self.assertEqual(report['skills'], [('Course', 1.5)])

    def test_session_gap_keeps_sessions_separate(self):
        rows = [(1, 100, 'old', profile(1)), (2, 100000, 'new', profile(2))]
        self.assertFalse(estimate_last_session(rows)['available'])
        self.assertFalse(estimate_last_session([])['available'])

    def test_reset_not_reported_as_negative_gain(self):
        left = profile(2, tree=100, kills=10)
        right = profile(3, tree=90, kills=11)
        rows = [(1, 100, 'old', left), (2, 101, 'new', right)]
        with patch.object(app, 'metrics', side_effect=lambda p, g='Any': p['fake_metrics']), \
             patch.object(app, 'evaluate_all', return_value=[]):
            report = estimate_last_session(rows)
        self.assertIn('Arbres abattus', report['resets'])
        self.assertNotIn('Arbres abattus', report['changes'])


if __name__ == '__main__':
    unittest.main()
