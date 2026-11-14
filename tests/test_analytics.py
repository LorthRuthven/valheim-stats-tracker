import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import boss_matrix, boss_progress, history_series


def profile():
    groups={}
    token='$enemy_eikthyr'
    for g,v,fists in [('Any',3,1),('Default',3,1),('Hard',1,0),('VeryHard',0,0),('Hardcore',0,0)]:
        groups[g]={'enemies':[{token:v},{token:fists},{},{},{}]}
    return {'groups':groups, 'skills':{'Poings': {'level': 15.5}}}


class AnalyticsTests(unittest.TestCase):
    def test_boss_progress_groups_are_not_added(self):
        p=profile()
        result=boss_matrix(p)
        self.assertEqual(result['$enemy_eikthyr']['Any'],3)
        self.assertEqual(result['$enemy_eikthyr']['Default'],3)
        self.assertEqual(result['$enemy_eikthyr']['Hard'],1)
        self.assertEqual(result['$enemy_eikthyr']['Default_unarmed'],1)
        self.assertEqual(boss_progress(p,'Hard'),1)
        self.assertEqual(boss_progress(p,'VeryHard'),0)

    def test_history_timestamps_and_deltas_across_filter(self):
        rows=[(1,100,'first',{'skills':{'Poings':{'level':10}}}),
              (2,200,'second',{'skills':{'Poings':{'level':12}}}),
              (3,86400*9,'third',{'skills':{'Poings':{'level':15}}})]
        all_series=history_series(rows,'skill:Poings',changes=True)
        self.assertEqual([s[1] for s in all_series],[0,2,3])
        filtered=history_series(rows,'skill:Poings',period_days=1,changes=True)
        self.assertEqual([s[1] for s in filtered],[3])
        self.assertEqual(filtered[0][0],86400*9)

if __name__=='__main__':unittest.main()
