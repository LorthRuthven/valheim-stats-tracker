"""Audit du pack d'images exactes des constructions Valheim (V2.7.1).

Tests purs sous Linux, tests de pixels réels après montage du pack dans Windows.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from tools.bundle_piece_sprites import load_piece_manifest, git_blob_sha, sprite_name
from valheim_reader import _BUILDABLE

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class PieceImageManifestTests(unittest.TestCase):
    def test_all_buildable_prefabs_have_an_exact_pinned_image(self):
        manifest = load_piece_manifest()
        prefabs = {x for x in _BUILDABLE.split("|") if x.startswith("$piece_")}
        self.assertEqual(len(prefabs), 386)
        self.assertEqual(set(manifest["pieces"]), prefabs)
        self.assertEqual(
            manifest["source_commit"], "18a0b624ceaf757abcfeb5cb1386d111a6dec9b2"
        )
        for token, entry in manifest["pieces"].items():
            with self.subTest(token=token):
                self.assertTrue(entry["file"].endswith(".png"))
                self.assertEqual(len(entry["git_blob_sha"]), 40)
                self.assertTrue(sprite_name(token).startswith("piece"))

    def test_wrong_external_associations_are_corrected(self):
        pieces = load_piece_manifest()["pieces"]
        if "$piece_armorstand" in pieces:
            self.assertEqual(pieces["$piece_armorstand"]["file"], "ArmorStand.png")
        if "$piece_sapling_oat" in pieces:
            self.assertEqual(pieces["$piece_sapling_oat"]["file"], "sapling_oat.png")
        if "$piece_sapling_vineash" in pieces:
            self.assertEqual(pieces["$piece_sapling_vineash"]["file"], "VineAsh_sapling.png")
        if "$piece_repair" in pieces:
            self.assertNotEqual(pieces["$piece_repair"]["file"], "Raspberry.png")

    def test_previous_wrong_piece_photos_are_corrected(self):
        images = load_piece_manifest()["pieces"]
        self.assertEqual(images["$piece_bathtub"]["file"], "piece_bathtub.png")
        self.assertEqual(images["$piece_woodstack"]["file"], "wood_stack.png")

    def test_git_blob_digest_is_for_entire_binary_file(self):
        import hashlib
        blob = b"\x89PNG\r\n\x1a\ncontents"
        header = b"blob " + str(len(blob)).encode("ascii") + b"\0"
        self.assertEqual(git_blob_sha(blob), hashlib.sha1(header + blob).hexdigest())

    def test_bundle_contains_genuine_png_and_no_placeholder(self):
        audit_path = ROOT / "assets" / "PIECE_ICONS_AUDIT.json"
        if not audit_path.is_file():
            self.skipTest("Pack construit seulement dans GitHub Actions Windows")
        try:
            from PIL import Image
            from PySide6.QtWidgets import QApplication
            from real_assets import piece_icon, collection_icon
            from collection_catalog import catalogue
        except ImportError:
            self.skipTest("Pillow / PySide6 requis sur le runner Windows")
        manifest = load_piece_manifest()
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(audit["source_commit"], manifest["source_commit"])
        self.assertGreaterEqual(audit["included"], 380)
        app = QApplication.instance() or QApplication([])
        index = json.loads((ROOT / "assets" / "index.json").read_text(encoding="utf-8"))
        for token in audit["tokens"]:
            with self.subTest(token=token):
                name = index["pieces"].get(sprite_name(token).removesuffix(".png"))
                self.assertEqual(name, sprite_name(token))
                file = ROOT / "assets" / "pieces" / name
                self.assertTrue(file.is_file(), file)
                with Image.open(file) as img:
                    self.assertEqual(img.format, "PNG")
                    self.assertGreater(img.width, 11)
                self.assertFalse(piece_icon(token).isNull())
                self.assertFalse(collection_icon(token).isNull())
        illustrated = sum(
            1 for entry in catalogue()
            if entry["token"].startswith("$piece_") and not piece_icon(entry["token"]).isNull()
        )
        self.assertGreaterEqual(illustrated, 380, illustrated)


if __name__ == "__main__":
    unittest.main()
