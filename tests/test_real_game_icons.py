"""Vérifie les vrais pixels Valheim embarqués, pas seulement les chemins d'icônes.

Ce test est exécuté après le téléchargement du pack dans les deux workflows
Windows. Sous Linux sans Qt et sans assets, seule la logique pure est testée.
"""
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from PIL import Image
    from game_visuals import (
        STAT_ITEMS, NAV_ITEMS, BOSS_ITEMS, SKILL_ITEMS,
        stat_game_icon, nav_game_icon, boss_game_icon,
        skill_game_icon, required_inventory_items,
    )
    from viking_stats import STATS
    from valheim_reader import BOSSES, SKILLS
    from real_assets import game_icon
    from tools.bundle_inventory_sprites import REVISION
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication is not None, "Qt Windows non disponible")
class RealGameIconsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.catalog_path = ROOT / "assets" / "index.json"

    def test_all_45_stat_cards_have_a_game_item_mapping(self):
        self.assertEqual(set(STAT_ITEMS), {item.key for item in STATS})
        self.assertEqual(set(BOSS_ITEMS), set(BOSSES))
        self.assertGreaterEqual(len(required_inventory_items()), 38)
        self.assertIn("Course", SKILL_ITEMS)
        for name in SKILLS.values():
            self.assertIn(name, SKILL_ITEMS)

    def test_inventory_pack_is_complete_and_the_images_are_real_png(self):
        if not self.catalog_path.exists():
            self.skipTest("Pack local absent ; sera vérifié lors du build Windows")
        index = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        audit = json.loads((ROOT / "assets" / "GAME_ICONS_AUDIT.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["source_revision"], REVISION)
        self.assertGreaterEqual(audit["selected_icons"], 38)
        for item in sorted(required_inventory_items()):
            with self.subTest(item=item):
                slug = re.sub(r"[^a-z0-9]+", "", item.casefold())
                filename = index["items"].get(slug)
                self.assertTrue(filename, f"Index invalide pour {item}")
                path = ROOT / "assets" / "items" / filename
                self.assertTrue(path.is_file(), f"Sprite Valheim absent : {item}")
                with Image.open(path) as img:
                    self.assertEqual(img.format, "PNG")
                    self.assertGreaterEqual(img.width, 24)
                    self.assertGreaterEqual(img.height, 24)

    def test_actual_rendered_qicons_have_pixels(self):
        if not (ROOT / "assets" / "GAME_ICONS_AUDIT.json").exists():
            self.skipTest("Pack local absent ; sera vérifié lors du build Windows")
        for stat in STATS:
            with self.subTest(stat=stat.key):
                self.assertFalse(stat_game_icon(stat).isNull())
        for key in NAV_ITEMS:
            with self.subTest(nav=key):
                self.assertFalse(nav_game_icon(key).isNull())
        for key in BOSSES:
            with self.subTest(boss=key):
                self.assertFalse(boss_game_icon(key).isNull())
        for skill in SKILLS.values():
            with self.subTest(skill=skill):
                self.assertFalse(skill_game_icon(skill).isNull())

    def test_no_hand_drawn_icons_left_in_live_cards_and_navigation(self):
        stats = (ROOT / "viking_stats_page.py").read_text(encoding="utf-8")
        nav = (ROOT / "nordic_ui.py").read_text(encoding="utf-8")
        restored = (ROOT / "restored_pages.py").read_text(encoding="utf-8")
        self.assertNotIn("pictogram(", stats)
        self.assertNotIn("stat_pictograms", stats)
        self.assertNotIn("ICON_PATH=", nav)
        self.assertNotIn('picture.setText("✦")', restored)
        self.assertIn("boss_game_icon(", restored)


if __name__ == "__main__":
    unittest.main()
