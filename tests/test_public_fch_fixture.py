"""Intégration contre un véritable fichier public .fch v46.

Définir VALHEIM_TEST_FCH vers la fixture Nichael du projet
github.com/lanchelms/fch-decoder. Le CI télécharge une révision figée.
Sans fixture locale, le test est ignoré (pas de téléchargement implicite).
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from character_archive import CharacterArchive, character_key, combine_profiles
from valheim_reader import GROUPS, STAT_INDEX, decode
from v2_core import TrackerStore
from viking_stats import STATS, value


class PublicFchIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = os.environ.get("VALHEIM_TEST_FCH", "")
        cls.filename = Path(name) if name else None
        if not cls.filename or not cls.filename.is_file():
            raise unittest.SkipTest("Fixture publique .fch non téléchargée")

    def test_actual_save_decode_archive_reimport_and_totals(self):
        original = self.filename.read_bytes()
        profile = decode(original)
        # Valeurs connues du fichier Nichael version46_test.go de fch-decoder.
        self.assertEqual(profile["name"], "Nichael")
        self.assertEqual(profile["player_id"], 444444)
        self.assertEqual(profile["version"], 46)
        self.assertEqual(len(profile["groups"]), 10)
        self.assertEqual(set(profile["groups"]), set(GROUPS))
        self.assertEqual(len(profile["groups"]["RawStats"]["stats"]), 205)
        self.assertEqual(profile["groups"]["RawStats"]["stats"][STAT_INDEX["Deaths"]], 34)
        self.assertEqual(profile["groups"]["RawStats"]["stats"][STAT_INDEX["Builds"]], 29793)
        self.assertEqual(profile["groups"]["Default"]["stats"][STAT_INDEX["Deaths"]], 0)

        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "nichael.fch"
            local.write_bytes(original)
            store = TrackerStore(Path(directory) / "tracker")
            try:
                imported = store.archive.import_files([str(local)])
                self.assertEqual(imported["added"], 1, imported)
                self.assertFalse(imported["errors"], imported)
                again = store.archive.import_files([str(local)])
                self.assertEqual(again["unchanged"], 1, again)
                self.assertEqual(len(store.archive.entries()), 1)
                key = character_key(profile)
                self.assertEqual(store.archive.entries()[0]["id"], key)

                # La sauvegarde active doit remplacer sa propre archive :
                # une seule entrée et donc aucun cumul artificiel.
                active = store.archive.entries(active_profile=profile)
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0]["source"], "active")
                total = combine_profiles(x["profile"] for x in active)
                self.assertEqual(total["groups"]["RawStats"]["stats"][STAT_INDEX["Deaths"]], 34)

                # Même le bouton « Retirer » ne touche jamais à la sauvegarde.
                self.assertTrue(store.archive.remove(key))
                self.assertEqual(local.read_bytes(), original)
                self.assertEqual(store.archive.entries(), [])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
