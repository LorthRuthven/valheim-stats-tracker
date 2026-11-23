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

    def test_dashboard_local_clock_and_readable_priority_table(self):
        app=QApplication.instance() or QApplication([])
        from PySide6.QtWidgets import QHeaderView
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertTrue(w.dash_clock_timer.isActive())
            self.assertEqual(w.dash_clock_timer.interval(), 1000)
            self.assertRegex(w.dash_clock_time.text(), r'^\\d{2}:\\d{2}:\\d{2}
            self.assertTrue(w.dash_clock_date.text())
            self.assertEqual(w.dash_priority.objectName(), 'dashboardPriority')
            self.assertTrue(w.dash_priority.alternatingRowColors())
            self.assertEqual(
                w.dash_priority.horizontalHeader().sectionResizeMode(0),
                QHeaderView.ResizeMode.Stretch
            )
            self.assertEqual(w.dash_priority.columnWidth(1), 165)
            self.assertGreaterEqual(w.dash_chart.minimumHeight(), 230)
            w.dash_clock_timer.stop()
            w.close()
            w.store.db.close()

    def test_session_timeline_and_records_are_present(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertTrue(hasattr(w, "history_session_table"))
            self.assertEqual(w.history_session_table.columnCount(), 7)
            self.assertTrue(hasattr(w, "history_record_summary"))
            self.assertIn("sauvegardes", w.history_record_summary.text())
            w.close()
            w.store.db.close()

    def test_all_restored_pages_and_windows_updater(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(w.stack.count(),12)
            self.assertTrue(hasattr(w,'activity_items'))
            self.assertTrue(hasattr(w,'skills_table'))
            self.assertTrue(hasattr(w,'raw_table_restored'))
            self.assertTrue(hasattr(w,'boss_table'))
            self.assertTrue(hasattr(w,'focus_table'))
            self.assertTrue(hasattr(w,'history_changes_restored'))
            self.assertTrue(hasattr(w,'combat_details'))
            self.assertTrue(hasattr(w,'update_controller'))
            self.assertTrue(hasattr(w,'collection_page'))
            self.assertEqual(w.NAV[10][0],'Encyclopédie')
            self.assertIs(w.stack.widget(10),w.collection_page)
            self.assertEqual(w.NAV[11][0],'Statistiques du Viking')
            self.assertIs(w.stack.widget(11),w.viking_stats_page)
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
            self.assertIn('Illustrations :', collection.summary.text())
            collection.image_filter.setCurrentIndex(1)
            from real_assets import collection_icon
            self.assertTrue(all(
                not collection_icon(e['token']).isNull()
                for e in collection.visible_entries
            ))
            collection.image_filter.setCurrentIndex(2)
            self.assertTrue(all(
                collection_icon(e['token']).isNull()
                for e in collection.visible_entries
            ))
            collection.image_filter.setCurrentIndex(0)
            collection.activity.setCurrentText('Activité enregistrée')
            character={'groups':{'Any':{'enemies':[{'$enemy_boar':1}]}}}
            collection.refresh(character)
            self.assertTrue(collection.visible_entries)
            self.assertTrue(all(x['observed'] for x in collection.visible_entries))
            collection.activity.setCurrentText('Toutes les activités')
            from unittest.mock import patch
            from wiki_images import wiki_title
            eligible = next((
                e['token'] for e in collection.filtered_entries
                if (wiki_title(e['token']) is not None
                    and collection.image_state(e['token']) == 'missing')
            ), None)
            if eligible is None:
                # Un catalogue intégralement illustré n'offre plus de cible Wiki.
                collection._fetch_missing()
                self.assertFalse(collection._wiki_busy)
            else:
                pending = []
                with patch.object(collection.wiki_cache, 'can_attempt',
                                  side_effect=lambda token: token != eligible), patch.object(
                             collection, '_start_wiki_download',
                             side_effect=lambda tokens: pending.extend(tokens)):
                    collection._fetch_missing()
                self.assertTrue(pending)
                self.assertNotIn(eligible, pending)
                self.assertLessEqual(len(pending), 500)
            w.show_page(10)
            self.assertEqual(w.stack.currentIndex(),10)
            w.close()

    def test_encyclopedia_continuous_gallery_full_width_and_details(self):
        """Pas de pages : tout le catalogue dans un scroll Qt virtualisé."""
        from PySide6.QtWidgets import QListView
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp:
            window = NordicWindow(TrackerStore(temp))
            window.resize(1550, 900)
            window.show()
            window.show_page(10)
            app.processEvents()
            book = window.collection_page
            gallery = book.gallery
            self.assertIs(book.list_stack.currentWidget(), gallery)
            self.assertTrue(book.gallery_button.isChecked())
            self.assertGreater(len(gallery.entries), 350)
            self.assertEqual(gallery.model.rowCount(), len(gallery.entries))
            self.assertIsInstance(gallery.list, QListView)
            self.assertFalse(hasattr(gallery, "page_number"))
            self.assertTrue(book.detail_scroll.isHidden())
            self.assertEqual(book.coverage_bar.maximum(), 1000)
            self.assertIsNotNone(book.copy_missing_button)
            self.assertGreaterEqual(book.image_filter.count(), 9)
            book._copy_missing_report()
            self.assertIn("sans image",app.clipboard().text())
            self.assertIn("Valheim Stats Tracker",app.clipboard().text())
            self.assertGreater(book.coverage_bar.value(), 0)
            self.assertIsNotNone(book.game_import_button)
            self.assertGreaterEqual(book.image_filter.count(), 6)
            self.assertEqual(book.table.rowCount(), 350)
            self.assertGreater(gallery.list.verticalScrollBar().maximum(), 0)
            gallery.list.verticalScrollBar().setValue(
                gallery.list.verticalScrollBar().maximum() // 2)
            app.processEvents()
            middle_scroll = gallery.list.verticalScrollBar().value()
            book.refresh(None)
            app.processEvents()
            self.assertGreater(middle_scroll, 0)
            self.assertGreater(gallery.list.verticalScrollBar().value(), 0)
            self.assertEqual(gallery.size_mode, "normal")
            book.card_size.setCurrentText("Compact")
            self.assertEqual(gallery.size_mode, "compact")
            book.card_size.setCurrentText("Grand")
            self.assertEqual(gallery.size_mode, "large")
            entry = gallery.entries[400]
            self.assertTrue(gallery.select_token(entry["token"], emit=True))
            app.processEvents()
            self.assertTrue(book.detail_scroll.isVisible())
            self.assertTrue(book.detail_toggle.isChecked())
            self.assertEqual(book._selected_token(), entry["token"])
            self.assertIn(entry["token"], book.detail_category.text())
            book.detail_close_button.click()
            self.assertTrue(book.detail_scroll.isHidden())
            book.list_button.click()
            self.assertIs(book.list_stack.currentWidget(), book.table)
            book.search.setText(entry["token"])
            app.processEvents()
            self.assertTrue(any(
                e["token"] == entry["token"] for e in book.visible_entries))
            book.gallery_button.click()
            self.assertIs(book.list_stack.currentWidget(), gallery)
            self.assertEqual(gallery.model.rowCount(), len(book.filtered_entries))
            self.assertGreater(gallery.model.rowCount(), 0)
            self.assertFalse(book.detail_toggle.isChecked())
            window.close()
            window.store.close()

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

    def test_cached_wiki_fallback_illustrates_catalogue_and_credits_source(self):
        """Le fallback Wiki fonctionne même lorsque tous les prefabs réels ont une image."""
        app = QApplication.instance() or QApplication([])
        import json
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtGui import QColor, QPixmap
        from wiki_images import WikiImageCache
        from real_assets import reset_icon_cache
        from collection_catalog import catalogue

        # Une entrée de test distincte du jeu évite de rendre ce test obsolète
        # chaque fois qu'une nouvelle image authentique arrive dans le pack.
        token = "$item_test_wiki_fallback_987"
        fake = {
            "token": token, "name": "Objet de test Wiki",
            "category": "Divers", "observed": False,
            "amount": 0.0, "evidence": [], "status": "Statut inconnu",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = WikiImageCache(root / "wiki_cache")
            path, meta, _ = cache._paths(token)
            path.parent.mkdir(parents=True, exist_ok=True)
            picture = QPixmap(120, 120)
            picture.fill(QColor(74, 138, 81))
            self.assertTrue(picture.save(str(path)))
            meta.write_text(json.dumps({
                "token": token, "wiki_title": "Objet de test",
                "page_url": "https://valheim.wiki/w/Test",
                "source": "Valheim Wiki",
            }), encoding="utf-8")
            with patch("v2_core.app_dir", return_value=root), patch(
                    "real_assets._wiki_cache", return_value=cache), patch(
                    "collection_page.catalogue", side_effect=lambda profile=None:
                    catalogue(profile) + [dict(fake)]):
                w = NordicWindow(TrackerStore(tmp))
                try:
                    book = w.collection_page
                    book.wiki_cache = cache
                    book.search.setText(token)
                    app.processEvents()
                    self.assertEqual(book.table.rowCount(), 1)
                    item = book.table.item(0, 0)
                    self.assertFalse(item.icon().isNull())
                    self.assertFalse(book.preview.pixmap().isNull())
                    self.assertTrue(book.image_link.isEnabled())
                    self.assertIn("Valheim Wiki", book.image_source.text())
                    self.assertTrue(hasattr(w, "_open_collection_wiki"))
                finally:
                    w.close()
                    w.store.close()
                    reset_icon_cache()

    def test_viking_stats_cards_search_categories_and_favorites(self):
        from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX
        from viking_stats import STATS, favorites
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            stats=w.viking_stats_page
            self.assertGreaterEqual(len(stats.cards),35)
            self.assertIn("trees",stats.cards)
            self.assertIn("walk",stats.cards)
            self.assertIn("sail",stats.cards)
            self.assertGreaterEqual(len(stats.favorite_cards), 6)
            self.assertFalse(stats.cards["walk"].picture.pixmap().isNull())
            self.assertFalse(stats.cards["sail"].picture.pixmap().isNull())
            self.assertEqual(w.stack.count(),12)
            self.assertIs(w.stack.widget(11),stats)
            arr=[0.0]*len(PLAYER_STAT_NAMES)
            arr[STAT_INDEX["Tree"]]=1284
            arr[STAT_INDEX["DistanceWalk"]]=342700
            arr[STAT_INDEX["Builds"]]=98
            profile={"name":"Ruthvenson","groups":{
                "Any":{"stats":arr},
                "RawStats":{"stats":arr.copy(),"worlds":{"Fiskeby":7200}},
            }}
            stats.refresh(profile)
            self.assertEqual(stats.cards["trees"].amount.text(),"1 284")
            self.assertEqual(stats.cards["walk"].amount.text(),"342,7 km")
            self.assertIn("walk",stats.visible_stat_keys)
            stats.search.setText("arbres")
            app.processEvents()
            self.assertIn("trees",stats.visible_stat_keys)
            self.assertNotIn("walk",stats.visible_stat_keys)
            stats.search.clear()
            stats.category.setCurrentText("Favoris")
            app.processEvents()
            self.assertEqual(set(stats.visible_stat_keys),favorites("Ruthvenson",tmp))
            stats.toggle_favorite("trees")
            self.assertNotIn("trees",favorites("Ruthvenson",tmp))
            stats.refresh(profile)
            self.assertNotIn("trees",stats.visible_stat_keys)
            self.assertTrue(stats.cards["walk"].star.text()=="★")
            w.show_page(11)
            app.processEvents()
            self.assertFalse(w.grab().isNull())
            w.close()

    def test_character_archive_selector_and_cumulative_cards(self):
        from unittest.mock import patch
        from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root:
            w = NordicWindow(TrackerStore(root))
            archive = w.store.archive
            from pathlib import Path
            def profile(name, identity, deaths, builds):
                arr = [0.0] * len(PLAYER_STAT_NAMES)
                arr[STAT_INDEX["Deaths"]] = deaths
                arr[STAT_INDEX["Builds"]] = builds
                return {"name": name, "player_id": identity, "created": 42,
                        "groups": {"Any": {"stats": arr},
                                   "RawStats": {"stats": arr.copy(), "worlds": {}}}}
            first = Path(root) / "ancien1.fch"
            second = Path(root) / "ancien2.fch"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            with patch("character_archive.decode",
                       side_effect=[profile("Ulf", 1, 5, 80),
                                    profile("Ragna", 2, 8, 115)]):
                report = archive.import_files([first, second])
            self.assertEqual(report["added"], 2)
            stats = w.viking_stats_page
            stats.refresh(None)
            self.assertEqual(stats.character_selector.count(), 3)
            self.assertTrue(stats.total_mode_button.isEnabled())
            stats.show_total()
            self.assertTrue(stats.total_mode_button.isChecked())
            self.assertFalse(stats.remove_button.isEnabled())
            stats.show_individual()
            self.assertTrue(stats.individual_mode_button.isChecked())
            self.assertTrue(stats.remove_button.isEnabled())
            stats.character_selector.setCurrentIndex(0)
            self.assertEqual(stats.cards["deaths"].amount.text(), "13")
            self.assertEqual(stats.cards["built"].amount.text(), "195")
            self.assertFalse(stats.cards["deaths"].detail_button.isHidden())
            stats.cards["deaths"].detail_button.click()
            app.processEvents()
            dialog=stats._detail_dialog
            self.assertIsNotNone(dialog)
            self.assertEqual(dialog.model.total, 13)
            self.assertEqual([r.name for r in dialog.rows], ["Ragna", "Ulf"])
            self.assertEqual([r.amount for r in dialog.rows], [8, 5])
            self.assertEqual(dialog.total_amount.text(), "13")
            self.assertAlmostEqual(sum(r.percentage for r in dialog.rows),100)
            self.assertIn("Plus forte contribution",dialog.highlight.text())
            dialog.copy_button.click()
            self.assertIn("Ragna",app.clipboard().text())
            self.assertIn("Ulf",app.clipboard().text())
            self.assertEqual(dialog.contribution_labels["id:2"].text(), "8")
            dialog.close()
            stats.character_selector.setCurrentIndex(1)
            self.assertTrue(stats.cards["deaths"].detail_button.isHidden())
            self.assertIsNone(stats.open_stat_details("deaths"))
            self.assertEqual(stats.cards["deaths"].amount.text(), "8")
            self.assertTrue(stats.remove_button.isEnabled())
            stats.character_selector.setCurrentIndex(0)
            self.assertFalse(stats.remove_button.isEnabled())
            self.assertEqual(w.stack.count(), 12)
            w.close()

    def test_activity_gallery_cards_filters_pagination_and_advanced_tables(self):
        """La galerie est le rendu principal ; le tableau reste optionnel."""
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            w.show()
            w.set_motion(False)
            w.store.profile={
                "name":"Viking de test",
                "groups":{
                    "Any":{
                        "pickables":{f"$item_wood_{i:02d}":float(i+1)
                                     for i in range(25)},
                        "picked_up":{},"crafted":{},
                        "pieces_built":{},"foods_eaten":{}
                    }
                }
            }
            w.show_page(7)
            w._refresh_activity()
            app.processEvents()
            from restored_pages import _display_token
            self.assertEqual(_display_token("$item_raspberry"),"Framboise")
            self.assertEqual(_display_token("$item_mushroom"),"Champignon")
            self.assertEqual(len(w.activity_rows),25)
            self.assertEqual(w.activity_page_number,0)
            self.assertEqual(len(w.activity_tiles),16)
            self.assertEqual(sum(not tile[0].isHidden()
                                 for tile in w.activity_tiles),16)
            self.assertTrue(w.activity_next.isEnabled())
            self.assertFalse(w.activity_prev.isEnabled())
            self.assertTrue(w.activity_technical_content.isHidden())
            self.assertEqual(w.activity_items.rowCount(),25)
            self.assertEqual(w.activity_metrics["types"].text(),"25")
            self.assertEqual(len(w.activity_family_bars),5)
            self.assertEqual(w.activity_family_bars[0][1].text(),"Bois et arbres")
            self.assertEqual(w.activity_family_bars[0][2].value(),1000)
            w.resize(1100,800)
            app.processEvents()
            self.assertEqual(w.activity_columns,2)
            w.resize(1650,940)
            app.processEvents()
            self.assertEqual(w.activity_columns,4)
            w.activity_next.click()
            app.processEvents()
            self.assertEqual(w.activity_page_number,1)
            self.assertEqual(sum(not tile[0].isHidden()
                                 for tile in w.activity_tiles),9)
            # Le passage à la dernière page ne doit pas générer
            # d'énorme espace vide au-dessus du titre de la galerie.
            gallery_heading=w.activity_gallery_panel.layout().itemAt(0).widget()
            self.assertLess(gallery_heading.geometry().y(),90)
            self.assertTrue(w.activity_prev.isEnabled())
            self.assertFalse(w.activity_next.isEnabled())
            w.activity_sort.setCurrentText("Les moins nombreux")
            self.assertEqual(w.activity_page_number,0)
            self.assertEqual(w.activity_rows[0][2],1.0)
            w.activity_search.setText("wood_1")
            self.assertEqual(len(w.activity_rows),10)
            w.activity_family.setCurrentText("Métaux et minerais")
            self.assertFalse(w.activity_rows)
            self.assertFalse(w.activity_empty.isHidden())
            w.activity_family.setCurrentText("Toutes les familles")
            w.activity_search.clear()
            w.activity_technical_button.click()
            self.assertTrue(w.activity_technical_button.isChecked())
            self.assertFalse(w.activity_technical_content.isHidden())
            self.assertEqual(w.activity_items.rowCount(),25)

            self.assertTrue(w.nav_buttons[9].isHidden())
            w.show_page(4)
            w.raw_diagnostic_button.click()
            self.assertEqual(w.stack.currentIndex(),9)
            self.assertTrue(w.nav_buttons[4].isChecked())
            from PySide6.QtWidgets import QPushButton
            back=w.stack.widget(9).findChild(QPushButton,"rawBackToSettings")
            self.assertIsNotNone(back)
            back.click()
            self.assertEqual(w.stack.currentIndex(),4)
            w.close()
            w.store.close()

    def test_visual_review_widgets_and_security_update_text(self):
        app=QApplication.instance() or QApplication([])
        from PySide6.QtWidgets import QLabel
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(len(w.boss_cards), 8)
            self.assertIsNotNone(w.boss_overview)
            self.assertIsNotNone(w.skills_summary)
            self.assertEqual(set(w.combat_summary_labels),
                             {'kills','species','bosses'})
            w.open_cumulative_stats()
            self.assertEqual(w.stack.currentIndex(),11)
            self.assertTrue(w.sidebar_cumulative_button.isEnabled())
            self.assertEqual(w.collection_page.preview.height(), 184)
            self.assertEqual(w.collection_page.preview.minimumHeight(), 184)
            collection_layout=w.collection_page.detail_scroll.widget().layout()
            visible_widgets=[collection_layout.itemAt(i).widget()
                             for i in range(collection_layout.count())
                             if collection_layout.itemAt(i).widget() is not None]
            self.assertLess(
                visible_widgets.index(w.collection_page.detail_title),
                visible_widgets.index(w.collection_page.preview))
            self.assertEqual(
                w.collection_page.detail_scroll.widget().minimumHeight(), 0)
            self.assertTrue(w.collection_page.detail_scroll.isHidden())
            settings=w.stack.widget(4)
            text=' '.join(x.text() for x in settings.findChildren(QLabel))
            self.assertIn('installation intégrée',text)
            self.assertIn('redémarrage après confirmation',text)
            self.assertNotIn('installation manuelle sans PowerShell',text)
            w.close()
            w.store.close()

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
            self.assertEqual(w.stack.count(),12)
            self.assertTrue(w.hero.renderer.isValid())
            self.assertFalse(rune_icon('trophy').pixmap(28,28).isNull())
            self.assertFalse(w.grab().isNull())
            w.hero.ring.move_to(48,animated=False)
            self.assertAlmostEqual(w.hero.ring.get_value(),48)
            for i in range(12):
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
)
            self.assertTrue(w.dash_clock_date.text())
            self.assertEqual(w.dash_priority.objectName(), 'dashboardPriority')
            self.assertTrue(w.dash_priority.alternatingRowColors())
            self.assertEqual(
                w.dash_priority.horizontalHeader().sectionResizeMode(0),
                QHeaderView.ResizeMode.Stretch
            )
            self.assertEqual(w.dash_priority.columnWidth(1), 165)
            self.assertGreaterEqual(w.dash_chart.minimumHeight(), 230)
            w.dash_clock_timer.stop()
            w.close()
            w.store.db.close()

    def test_session_timeline_and_records_are_present(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertTrue(hasattr(w, "history_session_table"))
            self.assertEqual(w.history_session_table.columnCount(), 7)
            self.assertTrue(hasattr(w, "history_record_summary"))
            self.assertIn("sauvegardes", w.history_record_summary.text())
            w.close()
            w.store.db.close()

    def test_all_restored_pages_and_windows_updater(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(w.stack.count(),12)
            self.assertTrue(hasattr(w,'activity_items'))
            self.assertTrue(hasattr(w,'skills_table'))
            self.assertTrue(hasattr(w,'raw_table_restored'))
            self.assertTrue(hasattr(w,'boss_table'))
            self.assertTrue(hasattr(w,'focus_table'))
            self.assertTrue(hasattr(w,'history_changes_restored'))
            self.assertTrue(hasattr(w,'combat_details'))
            self.assertTrue(hasattr(w,'update_controller'))
            self.assertTrue(hasattr(w,'collection_page'))
            self.assertEqual(w.NAV[10][0],'Encyclopédie')
            self.assertIs(w.stack.widget(10),w.collection_page)
            self.assertEqual(w.NAV[11][0],'Statistiques du Viking')
            self.assertIs(w.stack.widget(11),w.viking_stats_page)
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
            self.assertIn('Illustrations :', collection.summary.text())
            collection.image_filter.setCurrentIndex(1)
            from real_assets import collection_icon
            self.assertTrue(all(
                not collection_icon(e['token']).isNull()
                for e in collection.visible_entries
            ))
            collection.image_filter.setCurrentIndex(2)
            self.assertTrue(all(
                collection_icon(e['token']).isNull()
                for e in collection.visible_entries
            ))
            collection.image_filter.setCurrentIndex(0)
            collection.activity.setCurrentText('Activité enregistrée')
            character={'groups':{'Any':{'enemies':[{'$enemy_boar':1}]}}}
            collection.refresh(character)
            self.assertTrue(collection.visible_entries)
            self.assertTrue(all(x['observed'] for x in collection.visible_entries))
            collection.activity.setCurrentText('Toutes les activités')
            from unittest.mock import patch
            from wiki_images import wiki_title
            eligible = next((
                e['token'] for e in collection.filtered_entries
                if (wiki_title(e['token']) is not None
                    and collection.image_state(e['token']) == 'missing')
            ), None)
            if eligible is None:
                # Un catalogue intégralement illustré n'offre plus de cible Wiki.
                collection._fetch_missing()
                self.assertFalse(collection._wiki_busy)
            else:
                pending = []
                with patch.object(collection.wiki_cache, 'can_attempt',
                                  side_effect=lambda token: token != eligible), patch.object(
                             collection, '_start_wiki_download',
                             side_effect=lambda tokens: pending.extend(tokens)):
                    collection._fetch_missing()
                self.assertTrue(pending)
                self.assertNotIn(eligible, pending)
                self.assertLessEqual(len(pending), 500)
            w.show_page(10)
            self.assertEqual(w.stack.currentIndex(),10)
            w.close()

    def test_encyclopedia_continuous_gallery_full_width_and_details(self):
        """Pas de pages : tout le catalogue dans un scroll Qt virtualisé."""
        from PySide6.QtWidgets import QListView
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp:
            window = NordicWindow(TrackerStore(temp))
            window.resize(1550, 900)
            window.show()
            window.show_page(10)
            app.processEvents()
            book = window.collection_page
            gallery = book.gallery
            self.assertIs(book.list_stack.currentWidget(), gallery)
            self.assertTrue(book.gallery_button.isChecked())
            self.assertGreater(len(gallery.entries), 350)
            self.assertEqual(gallery.model.rowCount(), len(gallery.entries))
            self.assertIsInstance(gallery.list, QListView)
            self.assertFalse(hasattr(gallery, "page_number"))
            self.assertTrue(book.detail_scroll.isHidden())
            self.assertEqual(book.coverage_bar.maximum(), 1000)
            self.assertIsNotNone(book.copy_missing_button)
            self.assertGreaterEqual(book.image_filter.count(), 9)
            book._copy_missing_report()
            self.assertIn("sans image",app.clipboard().text())
            self.assertIn("Valheim Stats Tracker",app.clipboard().text())
            self.assertGreater(book.coverage_bar.value(), 0)
            self.assertIsNotNone(book.game_import_button)
            self.assertGreaterEqual(book.image_filter.count(), 6)
            self.assertEqual(book.table.rowCount(), 350)
            self.assertGreater(gallery.list.verticalScrollBar().maximum(), 0)
            gallery.list.verticalScrollBar().setValue(
                gallery.list.verticalScrollBar().maximum() // 2)
            app.processEvents()
            middle_scroll = gallery.list.verticalScrollBar().value()
            book.refresh(None)
            app.processEvents()
            self.assertGreater(middle_scroll, 0)
            self.assertGreater(gallery.list.verticalScrollBar().value(), 0)
            self.assertEqual(gallery.size_mode, "normal")
            book.card_size.setCurrentText("Compact")
            self.assertEqual(gallery.size_mode, "compact")
            book.card_size.setCurrentText("Grand")
            self.assertEqual(gallery.size_mode, "large")
            entry = gallery.entries[400]
            self.assertTrue(gallery.select_token(entry["token"], emit=True))
            app.processEvents()
            self.assertTrue(book.detail_scroll.isVisible())
            self.assertTrue(book.detail_toggle.isChecked())
            self.assertEqual(book._selected_token(), entry["token"])
            self.assertIn(entry["token"], book.detail_category.text())
            book.detail_close_button.click()
            self.assertTrue(book.detail_scroll.isHidden())
            book.list_button.click()
            self.assertIs(book.list_stack.currentWidget(), book.table)
            book.search.setText(entry["token"])
            app.processEvents()
            self.assertTrue(any(
                e["token"] == entry["token"] for e in book.visible_entries))
            book.gallery_button.click()
            self.assertIs(book.list_stack.currentWidget(), gallery)
            self.assertEqual(gallery.model.rowCount(), len(book.filtered_entries))
            self.assertGreater(gallery.model.rowCount(), 0)
            self.assertFalse(book.detail_toggle.isChecked())
            window.close()
            window.store.close()

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

    def test_cached_wiki_fallback_illustrates_catalogue_and_credits_source(self):
        """Le fallback Wiki fonctionne même lorsque tous les prefabs réels ont une image."""
        app = QApplication.instance() or QApplication([])
        import json
        from pathlib import Path
        from unittest.mock import patch
        from PySide6.QtGui import QColor, QPixmap
        from wiki_images import WikiImageCache
        from real_assets import reset_icon_cache
        from collection_catalog import catalogue

        # Une entrée de test distincte du jeu évite de rendre ce test obsolète
        # chaque fois qu'une nouvelle image authentique arrive dans le pack.
        token = "$item_test_wiki_fallback_987"
        fake = {
            "token": token, "name": "Objet de test Wiki",
            "category": "Divers", "observed": False,
            "amount": 0.0, "evidence": [], "status": "Statut inconnu",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = WikiImageCache(root / "wiki_cache")
            path, meta, _ = cache._paths(token)
            path.parent.mkdir(parents=True, exist_ok=True)
            picture = QPixmap(120, 120)
            picture.fill(QColor(74, 138, 81))
            self.assertTrue(picture.save(str(path)))
            meta.write_text(json.dumps({
                "token": token, "wiki_title": "Objet de test",
                "page_url": "https://valheim.wiki/w/Test",
                "source": "Valheim Wiki",
            }), encoding="utf-8")
            with patch("v2_core.app_dir", return_value=root), patch(
                    "real_assets._wiki_cache", return_value=cache), patch(
                    "collection_page.catalogue", side_effect=lambda profile=None:
                    catalogue(profile) + [dict(fake)]):
                w = NordicWindow(TrackerStore(tmp))
                try:
                    book = w.collection_page
                    book.wiki_cache = cache
                    book.search.setText(token)
                    app.processEvents()
                    self.assertEqual(book.table.rowCount(), 1)
                    item = book.table.item(0, 0)
                    self.assertFalse(item.icon().isNull())
                    self.assertFalse(book.preview.pixmap().isNull())
                    self.assertTrue(book.image_link.isEnabled())
                    self.assertIn("Valheim Wiki", book.image_source.text())
                    self.assertTrue(hasattr(w, "_open_collection_wiki"))
                finally:
                    w.close()
                    w.store.close()
                    reset_icon_cache()

    def test_viking_stats_cards_search_categories_and_favorites(self):
        from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX
        from viking_stats import STATS, favorites
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            stats=w.viking_stats_page
            self.assertGreaterEqual(len(stats.cards),35)
            self.assertIn("trees",stats.cards)
            self.assertIn("walk",stats.cards)
            self.assertIn("sail",stats.cards)
            self.assertGreaterEqual(len(stats.favorite_cards), 6)
            self.assertFalse(stats.cards["walk"].picture.pixmap().isNull())
            self.assertFalse(stats.cards["sail"].picture.pixmap().isNull())
            self.assertEqual(w.stack.count(),12)
            self.assertIs(w.stack.widget(11),stats)
            arr=[0.0]*len(PLAYER_STAT_NAMES)
            arr[STAT_INDEX["Tree"]]=1284
            arr[STAT_INDEX["DistanceWalk"]]=342700
            arr[STAT_INDEX["Builds"]]=98
            profile={"name":"Ruthvenson","groups":{
                "Any":{"stats":arr},
                "RawStats":{"stats":arr.copy(),"worlds":{"Fiskeby":7200}},
            }}
            stats.refresh(profile)
            self.assertEqual(stats.cards["trees"].amount.text(),"1 284")
            self.assertEqual(stats.cards["walk"].amount.text(),"342,7 km")
            self.assertIn("walk",stats.visible_stat_keys)
            stats.search.setText("arbres")
            app.processEvents()
            self.assertIn("trees",stats.visible_stat_keys)
            self.assertNotIn("walk",stats.visible_stat_keys)
            stats.search.clear()
            stats.category.setCurrentText("Favoris")
            app.processEvents()
            self.assertEqual(set(stats.visible_stat_keys),favorites("Ruthvenson",tmp))
            stats.toggle_favorite("trees")
            self.assertNotIn("trees",favorites("Ruthvenson",tmp))
            stats.refresh(profile)
            self.assertNotIn("trees",stats.visible_stat_keys)
            self.assertTrue(stats.cards["walk"].star.text()=="★")
            w.show_page(11)
            app.processEvents()
            self.assertFalse(w.grab().isNull())
            w.close()

    def test_character_archive_selector_and_cumulative_cards(self):
        from unittest.mock import patch
        from valheim_reader import PLAYER_STAT_NAMES, STAT_INDEX
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root:
            w = NordicWindow(TrackerStore(root))
            archive = w.store.archive
            from pathlib import Path
            def profile(name, identity, deaths, builds):
                arr = [0.0] * len(PLAYER_STAT_NAMES)
                arr[STAT_INDEX["Deaths"]] = deaths
                arr[STAT_INDEX["Builds"]] = builds
                return {"name": name, "player_id": identity, "created": 42,
                        "groups": {"Any": {"stats": arr},
                                   "RawStats": {"stats": arr.copy(), "worlds": {}}}}
            first = Path(root) / "ancien1.fch"
            second = Path(root) / "ancien2.fch"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            with patch("character_archive.decode",
                       side_effect=[profile("Ulf", 1, 5, 80),
                                    profile("Ragna", 2, 8, 115)]):
                report = archive.import_files([first, second])
            self.assertEqual(report["added"], 2)
            stats = w.viking_stats_page
            stats.refresh(None)
            self.assertEqual(stats.character_selector.count(), 3)
            self.assertTrue(stats.total_mode_button.isEnabled())
            stats.show_total()
            self.assertTrue(stats.total_mode_button.isChecked())
            self.assertFalse(stats.remove_button.isEnabled())
            stats.show_individual()
            self.assertTrue(stats.individual_mode_button.isChecked())
            self.assertTrue(stats.remove_button.isEnabled())
            stats.character_selector.setCurrentIndex(0)
            self.assertEqual(stats.cards["deaths"].amount.text(), "13")
            self.assertEqual(stats.cards["built"].amount.text(), "195")
            self.assertFalse(stats.cards["deaths"].detail_button.isHidden())
            stats.cards["deaths"].detail_button.click()
            app.processEvents()
            dialog=stats._detail_dialog
            self.assertIsNotNone(dialog)
            self.assertEqual(dialog.model.total, 13)
            self.assertEqual([r.name for r in dialog.rows], ["Ragna", "Ulf"])
            self.assertEqual([r.amount for r in dialog.rows], [8, 5])
            self.assertEqual(dialog.total_amount.text(), "13")
            self.assertAlmostEqual(sum(r.percentage for r in dialog.rows),100)
            self.assertIn("Plus forte contribution",dialog.highlight.text())
            dialog.copy_button.click()
            self.assertIn("Ragna",app.clipboard().text())
            self.assertIn("Ulf",app.clipboard().text())
            self.assertEqual(dialog.contribution_labels["id:2"].text(), "8")
            dialog.close()
            stats.character_selector.setCurrentIndex(1)
            self.assertTrue(stats.cards["deaths"].detail_button.isHidden())
            self.assertIsNone(stats.open_stat_details("deaths"))
            self.assertEqual(stats.cards["deaths"].amount.text(), "8")
            self.assertTrue(stats.remove_button.isEnabled())
            stats.character_selector.setCurrentIndex(0)
            self.assertFalse(stats.remove_button.isEnabled())
            self.assertEqual(w.stack.count(), 12)
            w.close()

    def test_activity_gallery_cards_filters_pagination_and_advanced_tables(self):
        """La galerie est le rendu principal ; le tableau reste optionnel."""
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            w.show()
            w.set_motion(False)
            w.store.profile={
                "name":"Viking de test",
                "groups":{
                    "Any":{
                        "pickables":{f"$item_wood_{i:02d}":float(i+1)
                                     for i in range(25)},
                        "picked_up":{},"crafted":{},
                        "pieces_built":{},"foods_eaten":{}
                    }
                }
            }
            w.show_page(7)
            w._refresh_activity()
            app.processEvents()
            from restored_pages import _display_token
            self.assertEqual(_display_token("$item_raspberry"),"Framboise")
            self.assertEqual(_display_token("$item_mushroom"),"Champignon")
            self.assertEqual(len(w.activity_rows),25)
            self.assertEqual(w.activity_page_number,0)
            self.assertEqual(len(w.activity_tiles),16)
            self.assertEqual(sum(not tile[0].isHidden()
                                 for tile in w.activity_tiles),16)
            self.assertTrue(w.activity_next.isEnabled())
            self.assertFalse(w.activity_prev.isEnabled())
            self.assertTrue(w.activity_technical_content.isHidden())
            self.assertEqual(w.activity_items.rowCount(),25)
            self.assertEqual(w.activity_metrics["types"].text(),"25")
            self.assertEqual(len(w.activity_family_bars),5)
            self.assertEqual(w.activity_family_bars[0][1].text(),"Bois et arbres")
            self.assertEqual(w.activity_family_bars[0][2].value(),1000)
            w.resize(1100,800)
            app.processEvents()
            self.assertEqual(w.activity_columns,2)
            w.resize(1650,940)
            app.processEvents()
            self.assertEqual(w.activity_columns,4)
            w.activity_next.click()
            app.processEvents()
            self.assertEqual(w.activity_page_number,1)
            self.assertEqual(sum(not tile[0].isHidden()
                                 for tile in w.activity_tiles),9)
            # Le passage à la dernière page ne doit pas générer
            # d'énorme espace vide au-dessus du titre de la galerie.
            gallery_heading=w.activity_gallery_panel.layout().itemAt(0).widget()
            self.assertLess(gallery_heading.geometry().y(),90)
            self.assertTrue(w.activity_prev.isEnabled())
            self.assertFalse(w.activity_next.isEnabled())
            w.activity_sort.setCurrentText("Les moins nombreux")
            self.assertEqual(w.activity_page_number,0)
            self.assertEqual(w.activity_rows[0][2],1.0)
            w.activity_search.setText("wood_1")
            self.assertEqual(len(w.activity_rows),10)
            w.activity_family.setCurrentText("Métaux et minerais")
            self.assertFalse(w.activity_rows)
            self.assertFalse(w.activity_empty.isHidden())
            w.activity_family.setCurrentText("Toutes les familles")
            w.activity_search.clear()
            w.activity_technical_button.click()
            self.assertTrue(w.activity_technical_button.isChecked())
            self.assertFalse(w.activity_technical_content.isHidden())
            self.assertEqual(w.activity_items.rowCount(),25)

            self.assertTrue(w.nav_buttons[9].isHidden())
            w.show_page(4)
            w.raw_diagnostic_button.click()
            self.assertEqual(w.stack.currentIndex(),9)
            self.assertTrue(w.nav_buttons[4].isChecked())
            from PySide6.QtWidgets import QPushButton
            back=w.stack.widget(9).findChild(QPushButton,"rawBackToSettings")
            self.assertIsNotNone(back)
            back.click()
            self.assertEqual(w.stack.currentIndex(),4)
            w.close()
            w.store.close()

    def test_visual_review_widgets_and_security_update_text(self):
        app=QApplication.instance() or QApplication([])
        from PySide6.QtWidgets import QLabel
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            self.assertEqual(len(w.boss_cards), 8)
            self.assertIsNotNone(w.boss_overview)
            self.assertIsNotNone(w.skills_summary)
            self.assertEqual(set(w.combat_summary_labels),
                             {'kills','species','bosses'})
            w.open_cumulative_stats()
            self.assertEqual(w.stack.currentIndex(),11)
            self.assertTrue(w.sidebar_cumulative_button.isEnabled())
            self.assertEqual(w.collection_page.preview.height(), 184)
            self.assertEqual(w.collection_page.preview.minimumHeight(), 184)
            collection_layout=w.collection_page.detail_scroll.widget().layout()
            visible_widgets=[collection_layout.itemAt(i).widget()
                             for i in range(collection_layout.count())
                             if collection_layout.itemAt(i).widget() is not None]
            self.assertLess(
                visible_widgets.index(w.collection_page.detail_title),
                visible_widgets.index(w.collection_page.preview))
            self.assertEqual(
                w.collection_page.detail_scroll.widget().minimumHeight(), 0)
            self.assertTrue(w.collection_page.detail_scroll.isHidden())
            settings=w.stack.widget(4)
            text=' '.join(x.text() for x in settings.findChildren(QLabel))
            self.assertIn('installation intégrée',text)
            self.assertIn('redémarrage après confirmation',text)
            self.assertNotIn('installation manuelle sans PowerShell',text)
            w.close()
            w.store.close()

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
            self.assertEqual(w.stack.count(),12)
            self.assertTrue(w.hero.renderer.isValid())
            self.assertFalse(rune_icon('trophy').pixmap(28,28).isNull())
            self.assertFalse(w.grab().isNull())
            w.hero.ring.move_to(48,animated=False)
            self.assertAlmostEqual(w.hero.ring.get_value(),48)
            for i in range(12):
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
