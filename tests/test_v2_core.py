"""Régressions V2 : données 1.x et lecture seule."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import v2_core as v2
from valheim_reader import SPECS, STAT_INDEX


class V2CoreTests(unittest.TestCase):
    def test_ranking_and_missing_actions(self):
        rows = [
            {'key':'near','title':'Près','fraction':.95,'complete':False,'measurable':True,
             'completed_conditions':9,'total_conditions':10},
            {'key':'far','title':'Loin','fraction':.2,'complete':False,'measurable':True,
             'completed_conditions':1,'total_conditions':10},
            {'key':'unknown','title':'Interne','fraction':None,'complete':False,'measurable':False},
            {'key':'done','title':'Atteint','fraction':1,'complete':True,'measurable':True},
        ]
        ranking = v2.progress_ranking(rows, {'far'})
        self.assertEqual([r['key'] for r in ranking], ['near','far'])
        self.assertTrue(ranking[1]['favorite'])
        actions = v2.pending_actions({'measurable':True,'complete':False, 'parts': [
            {'label':'Plus proche','complete':False,'current':8,'goal':10,'remaining':2},
            {'label':'Lointain','complete':False,'current':1,'goal':10,'remaining':9},
            {'label':'Fini','complete':True,'current':10,'goal':10,'remaining':0},
        ]})
        self.assertEqual([x['label'] for x in actions], ['Plus proche','Lointain'])

    def test_compatible_v1_sqlite_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            existing=sqlite3.connect(root/'historique.sqlite3')
            existing.execute('''CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character TEXT NOT NULL,sha TEXT NOT NULL,observed_at REAL NOT NULL,
                filename TEXT NOT NULL,data BLOB NOT NULL,UNIQUE(character,sha))''')
            existing.commit();existing.close()
            db=v2.db_open(root)
            x={'name':'Ruthvenson','groups':{'Any':{'stats':[0]*205}}}
            v2.save_snapshot(db,x,'sha1','first.fch',100)
            v2.save_snapshot(db,x,'sha1','first.fch',100)
            rows=v2.sample_rows(db,'Ruthvenson')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0][3],x)
            db.close()

    def test_shared_character_favorites_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            v2.save_favorites('Ruthvenson',{'hunter','lumberjack'},root)
            v2.save_favorites('Autre',{'builder'},root)
            self.assertEqual(v2.load_favorites('Ruthvenson',root), {'hunter','lumberjack'})
            self.assertEqual(v2.load_favorites('Autre',root), {'builder'})
            v2.write_config_save('C:/characters/Ruthvenson.fch',root)
            self.assertEqual(v2.read_config(root)['path'], 'C:/characters/Ruthvenson.fch')
            self.assertEqual(v2.load_favorites('Ruthvenson',root), {'hunter','lumberjack'})

    def test_no_false_session(self):
        self.assertFalse(v2.session_report([])['available'])
        self.assertFalse(v2.session_report([(1,1,'a',{})])['available'])
        self.assertFalse(v2.session_report([(1,1,'a',{}),(2,10000,'b',{})])['available'])

    def test_series_time_window(self):
        def profile(n):
            return {'groups':{'Any':{'stats':[n]*205}}}
        data=[(1,100,'a',profile(1)),(2,200,'b',profile(2)),(3,300,'c',profile(3))]
        self.assertEqual(v2.history_series(data,'Tree'),[(100,1),(200,2),(300,3)])
        self.assertEqual(v2.history_series(data,'Tree',since_seconds=100),[(200,2),(300,3)])

    def test_refresh_is_read_only_and_does_not_duplicate_rows(self):
        src=Path('/mnt/data/ruthvenson.fch')
        if not src.exists():
            self.skipTest('Sauvegarde de référence non disponible dans CI')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dest=root/'ruthvenson.fch';dest.write_bytes(src.read_bytes())
            store=v2.TrackerStore(root)
            store.choose(str(dest))
            before=dest.read_bytes()
            self.assertEqual(store.refresh(force=True)['state'],'updated')
            self.assertEqual(store.refresh(force=True)['state'],'unchanged')
            self.assertEqual(dest.read_bytes(),before)
            self.assertEqual(len(store.rows()),1)
            self.assertEqual(len(v2.evaluate_all(store.profile)),55)
            store.close()


if __name__=='__main__':unittest.main()
