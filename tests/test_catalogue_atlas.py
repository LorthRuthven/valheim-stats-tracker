"""Valide le catalogue Jötunn complet et les images réellement embarquées."""
import json
import os
import unittest
from pathlib import Path

from tools.bundle_catalogue_atlas import (
    KINDS, load_manifest, pack_filename, slug, git_blob_hash,
)

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class AtlasManifestTests(unittest.TestCase):
    def test_pinned_source_and_1535_real_image_records(self):
        atlas = load_manifest()
        self.assertEqual(
            atlas["source_commit"],
            "18a0b624ceaf757abcfeb5cb1386d111a6dec9b2",
        )
        expected = {"items":1231, "characters":162, "prefabs":134, "world":8}
        self.assertEqual({k:len(atlas["images"][k]) for k in KINDS},expected)
        self.assertGreaterEqual(len(atlas["item_token_aliases"]), 895)
        self.assertIn("$enemy_greydwarfbrute",atlas["creature_token_aliases"])
        self.assertEqual(atlas["creature_token_aliases"]["$enemy_greydwarfbrute"],
                         "Greydwarf_Elite.png")
        self.assertEqual(atlas["creature_token_aliases"]["$enemy_skeletonfire"],
                         "Skeleton_Hildir.png")
        self.assertEqual(atlas["creature_token_aliases"]["$enemy_goblin_hildir"],
                         "GoblinShaman_Hildir.png")

    def test_identified_ships_and_hardrock_have_exact_images(self):
        atlas = load_manifest()
        expected = {
            "$ship_karve": "Karve.png",
            "$ship_longship": "VikingShip.png",
            "$ship_longship_ashlands": "VikingShip_Ashlands.png",
            "$ship_raft": "Raft.png",
            "$item_hardrock": "Placeable_HardRock.png",
        }
        for token, file in expected.items():
            with self.subTest(token=token):
                self.assertEqual(atlas["world_token_aliases"][token], file)
                self.assertIn(file, atlas["images"]["world"])

    def test_standard_catalogue_has_no_missing_images(self):
        """No 100% claim before all 1012 standard prefabs render real pixels."""
        report = ROOT / "assets" / "CATALOGUE_ATLAS_AUDIT.json"
        if not report.exists():
            self.skipTest("Pack valide uniquement apres compilation des images Windows")
        from PySide6.QtWidgets import QApplication
        from collection_catalog import catalogue
        from real_assets import collection_icon
        app = QApplication.instance() or QApplication([])
        missing = [entry["token"] for entry in catalogue()
                   if collection_icon(entry["token"]).isNull()]
        self.assertEqual(missing, [],
                         f"{len(missing)} identifiants du catalogue de base sans image : "
                         + ", ".join(missing))

    def test_transparent_images_are_not_marked_as_authentic_icons(self):
        from PySide6.QtWidgets import QApplication
        from real_assets import (
            bundled_assets, related_icon, character_icon, game_icon, collection_icon,
        )
        app = QApplication.instance() or QApplication([])
        root = bundled_assets()
        if not (root / "CATALOGUE_ATLAS_AUDIT.json").exists():
            self.skipTest("Contrôles de pixels sur le paquet Windows construit.")
        # Ces sprites Jötunn sont réellement transparents, malgré un PNG valide.
        self.assertTrue(character_icon("$enemy_aspect_dragon").isNull())
        self.assertFalse(related_icon("$enemy_aspect_dragon").isNull())
        self.assertFalse(collection_icon("$enemy_aspect_dragon").isNull())
        self.assertTrue(game_icon("$item_lingonberries").isNull())
        self.assertFalse(related_icon("$item_lingonberries").isNull())

    def test_ambiguous_filenames_get_distinct_real_png_paths(self):
        manifest = load_manifest()
        a=manifest["images"]["items"]["Hair32.png"]
        b=manifest["images"]["items"]["Hair3_2.png"]
        self.assertNotEqual(pack_filename("Hair32.png",a["sha"]),
                            pack_filename("Hair3_2.png",b["sha"]))
        self.assertEqual(slug("SwordIron"),"swordiron")
        self.assertEqual(len(git_blob_hash(b"test")),40)

    def test_packaged_atlas_has_real_verified_images_and_prefabs(self):
        report=ROOT/"assets"/"CATALOGUE_ATLAS_AUDIT.json"
        if not report.exists():
            self.skipTest("L'atlas est téléchargé au build Windows uniquement.")
        try:
            from PySide6.QtWidgets import QApplication
            from PIL import Image
            from collection_catalog import catalogue
            from real_assets import game_icon, character_icon, world_icon, collection_icon
        except ImportError:
            self.skipTest("Qt et Pillow indisponibles hors Windows.")
        audit=json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(audit["total"],1535)
        self.assertEqual(audit["errors"],{})
        app=QApplication.instance() or QApplication([])
        manifest=load_manifest()
        index=json.loads((ROOT/"assets"/"index.json").read_text(encoding="utf-8"))
        for kind in KINDS:
            self.assertGreaterEqual(len(index["jotunn_"+kind]),len(manifest["images"][kind])-2)
            folder=ROOT/"assets"/("jotunn_"+kind)
            for filename, info in manifest["images"][kind].items():
                with self.subTest(kind=kind,file=filename):
                    image=folder/pack_filename(filename,info["sha"])
                    self.assertTrue(image.is_file(),str(image))
                    payload=image.read_bytes()
                    self.assertEqual(len(payload),info["size"])
                    self.assertEqual(git_blob_hash(payload),info["sha"])
                    # L'ouverture stricte par Pillow est effectuée lors du téléchargement ;
                    # une image réelle de chaque famille doit aussi être rendue par Qt.
        self.assertFalse(game_icon("$item_sword_iron").isNull())
        self.assertFalse(game_icon("$item_trophy_wolf").isNull())
        self.assertFalse(character_icon("$enemy_greydwarfbrute").isNull())
        self.assertFalse(character_icon("$enemy_dvergr_mage").isNull())
        self.assertFalse(world_icon("$tool_catapult").isNull())
        self.assertFalse(collection_icon("$enemy_greydwarfbrute").isNull())
        total = sum(1 for entry in catalogue()
                    if not collection_icon(entry["token"]).isNull())
        self.assertGreaterEqual(total,990,
                                f"Trop d'illustrations manquantes dans les données standard : {total}")
        self.assertGreaterEqual(len(catalogue()),1012)


if __name__=="__main__":
    unittest.main()
