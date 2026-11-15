"""Qt V2.1 : tests exécutés sur Windows, ignorés sur Linux sans Qt."""
import os
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from nordic_ui import NordicWindow, rune_icon
    from desktop_v2 import TrendChart
    from v2_core import TrackerStore
except ImportError:
    QApplication=None


@unittest.skipIf(QApplication is None,'Qt non installé dans cet environnement')
class QtWindowTests(unittest.TestCase):


    def test_display_modes_enlarge_readability_and_persist(self):
        app=QApplication.instance() or QApplication([])
        from PySide6.QtWidgets import QTableWidget, QComboBox
        from display_scaling import SCALES, DEFAULT_SCALE
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(DEFAULT_SCALE,'Grand')
            self.assertEqual(w.display_mode,'Grand')
            self.assertIn('TAILLE DE L’INTERFACE',
                          [x.text() for x in w.findChildren(__import__('PySide6.QtWidgets',fromlist=['QLabel']).QLabel)])
            self.assertEqual(w.nav_buttons[0].minimumHeight(),SCALES['Grand']['nav'])
            old_row=w.ach_parts.verticalHeader().defaultSectionSize()
            w.set_display_mode('Très grand')
            self.assertEqual(w.nav_buttons[0].minimumHeight(),SCALES['Très grand']['nav'])
            self.assertGreater(w.ach_parts.verticalHeader().defaultSectionSize(),old_row)
            w.set_motion(False)
            w.close()
            w.store.db.close()
            w2=NordicWindow(TrackerStore(tmp))
            self.assertEqual(w2.display_mode,'Très grand')
            self.assertFalse(w2.motion)
            w2.close()
            w2.store.db.close()

    def test_settings_no_legacy_update_panel(self):
        app=QApplication.instance() or QApplication([])
        from PySide6.QtWidgets import QLabel
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            settings=w.stack.widget(4)
            labels=[x.text() for x in settings.findChildren(QLabel)]
            self.assertEqual(labels.count('MISES À JOUR WINDOWS'),1)
            self.assertEqual(labels.count('MISES À JOUR'),0)
            self.assertIn('VÉRITABLES ICÔNES VALHEIM',labels)
            w.close()

    def test_all_restored_pages_and_windows_updater(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(w.stack.count(),11)
            self.assertTrue(hasattr(w,'activity_items'))
            self.assertTrue(hasattr(w,'skills_table'))
            self.assertTrue(hasattr(w,'raw_table_restored'))
            self.assertTrue(hasattr(w,'boss_table'))
            self.assertTrue(hasattr(w,'focus_table'))
            self.assertTrue(hasattr(w,'history_changes_restored'))
            self.assertTrue(hasattr(w,'combat_details'))
            self.assertTrue(hasattr(w,'update_controller'))
            self.assertTrue(hasattr(w,'collection_page'))
            self.assertEqual(w.NAV[-1][0],'Encyclopédie')
            self.assertIs(w.stack.widget(10),w.collection_page)
            w.close()

    def test_collection_filters_and_achievement_image_panel(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertTrue(hasattr(w,'ach_large_icon'))
            self.assertTrue(hasattr(w,'ach_state'))
            collection=w.collection_page
            self.assertGreater(len(collection.entries),250)
            self.assertTrue(collection.table.rowCount()>0)
            self.assertEqual(collection.table.columnCount(),3)
            collection.search.setText('boar')
            app.processEvents()
            self.assertTrue(collection.table.rowCount()>0)
            self.assertTrue(all('boar' in item['token'].casefold()
                                or 'boar' in item['name'].casefold()
                                for item in collection.visible_entries))
            collection.search.clear()
            collection.activity.setCurrentText('Activité enregistrée')
            character={'groups':{'Any':{'enemies':[{'$enemy_boar':1}]}}}
            collection.refresh(character)
            self.assertTrue(collection.visible_entries)
            self.assertTrue(all(x['observed'] for x in collection.visible_entries))
            collection.activity.setCurrentText('Toutes les activités')
            w.show_page(10)
            self.assertEqual(w.stack.currentIndex(),10)
            w.close()

    def test_local_sprite_aliases_match_real_prefabs(self):
        app=QApplication.instance() or QApplication([])
        import json
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtGui import QColor, QPixmap
        from real_assets import game_icon, reset_icon_cache, _icon_candidates
        self.assertIn('boar',_icon_candidates('$enemy_boar'))
        self.assertIn('swordiron',_icon_candidates('$item_sword_iron'))
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            icons=directory/'game_icons'
            icons.mkdir()
            pixel=QPixmap(30,30)
            pixel.fill(QColor(245,132,49))
            self.assertTrue(pixel.save(str(icons/'spriteboar.png')))
            (icons/'index.json').write_text(
                json.dumps({'aliases':{'boar':'spriteboar.png'}}),encoding='utf-8')
            with patch('v2_core.app_dir',return_value=directory):
                self.assertFalse(game_icon('$enemy_boar').isNull())
                self.assertTrue(game_icon('$enemy_nonexistent_bad_icon_123').isNull())
                reset_icon_cache()

    def test_labels_have_transparent_background(self):
        # Régression visuelle V2.1 : les QLabel ne doivent pas devenir
        # des rectangles opaques autour de chaque texte.
        from nordic_ui import QSS
        import re
        self.assertRegex(QSS, r'QLabel\s*\{\s*background:transparent')
        self.assertNotRegex(QSS, r'QMainWindow\s*,\s*QWidget\s*\{\s*background')
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            window=NordicWindow(TrackerStore(tmp))
            window.show()
            app.processEvents()
            self.assertTrue(window.hero.title.isVisible())
            self.assertTrue(window.hero.renderer.isValid())
            self.assertTrue(window.hero.title.parentWidget().isVisible())
            self.assertFalse(window.grab().isNull())
            window.close()

    def test_navigation_graphics_and_motion(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            w.show()
            app.processEvents()
            self.assertEqual(w.stack.count(),11)
            self.assertTrue(w.hero.renderer.isValid())
            self.assertFalse(rune_icon('trophy').pixmap(28,28).isNull())
            self.assertFalse(w.grab().isNull())
            w.hero.ring.move_to(48,animated=False)
            self.assertAlmostEqual(w.hero.ring.get_value(),48)
            for i in range(11):
                w.show_page(i)
                self.assertEqual(w.stack.currentIndex(),i)
                self.assertTrue(w.nav_buttons[i].isChecked())
            w.set_motion(False)
            self.assertFalse(w.motion)
            self.assertFalse(w.motion_checkbox.isChecked()==True and w.motion)
            w.history_chart.set_data([(100,1),(200,3),(300,2)],'Test')
            self.assertEqual(len(w.history_chart.points),3)
            self.assertFalse(w.history_chart.grab().isNull())
            w.close()
            newer=NordicWindow(TrackerStore(tmp))
            self.assertFalse(newer.motion)
            newer.close()


if __name__=='__main__':
    unittest.main()
