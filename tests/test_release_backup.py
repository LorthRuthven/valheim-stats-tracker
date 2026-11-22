"""La première exécution de V2.7.3 protège les progrès de l'utilisateur."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from v2_core import VERSION, TrackerStore, backup_before_update


class ReleaseBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        with sqlite3.connect(self.root / "historique.sqlite3") as db:
            db.execute("""
                CREATE TABLE snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character TEXT NOT NULL, sha TEXT NOT NULL,
                    observed_at REAL NOT NULL, filename TEXT NOT NULL,
                    data BLOB NOT NULL, UNIQUE(character,sha)
                )
            """)
            db.execute(
                "INSERT INTO snapshots(character,sha,observed_at,filename,data) "
                "VALUES (?,?,?,?,?)",
                ("Ruthvenson", "save-hash", 0, "Ruthvenson.fch", b"historique"),
            )
            db.execute("""
                CREATE TABLE archived_characters (
                    character_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    sha TEXT NOT NULL, filename TEXT NOT NULL,
                    observed_at REAL NOT NULL, data BLOB NOT NULL
                )
            """)
            db.execute(
                "INSERT INTO archived_characters VALUES (?,?,?,?,?,?)",
                ("id:123", "Kelsrun", "archive-hash", "Kelsrun.fch", 0, b"archive"),
            )
        (self.root / "favoris.json").write_text('{"characters":{"Ruthvenson":["forge"]}}', encoding="utf8")
        (self.root / "stats_favorites.json").write_text('{"run":true}', encoding="utf8")
        (self.root / "config.json").write_text('{"path":""}', encoding="utf8")

    def test_backup_is_atomic_and_keeps_all_progress(self):
        self.assertEqual(VERSION, "2.7.3")
        store = TrackerStore(self.root)
        copy = self.root / "backups" / "avant_v2.7.3"
        self.assertEqual(store.release_backup, copy)
        store.close()
        self.assertTrue((copy / "sauvegarde_complete.json").is_file())
        data = json.loads((copy / "sauvegarde_complete.json").read_text(encoding="utf8"))
        self.assertTrue(data["database_included"])
        self.assertEqual(set(data["settings"]), {
            "favoris.json", "stats_favorites.json", "config.json"
        })
        self.assertEqual(
            (copy / "favoris.json").read_bytes(),
            (self.root / "favoris.json").read_bytes(),
        )
        with sqlite3.connect(copy / "historique.sqlite3") as db:
            self.assertEqual(db.execute("SELECT character FROM snapshots").fetchone()[0], "Ruthvenson")
            self.assertEqual(db.execute("SELECT name FROM archived_characters").fetchone()[0], "Kelsrun")

    def test_second_launch_does_not_overwrite_original_backup(self):
        copy = backup_before_update(self.root)
        original = (copy / "favoris.json").read_bytes()
        (self.root / "favoris.json").write_text('{"characters":{}}', encoding="utf8")
        self.assertEqual(backup_before_update(self.root), copy)
        self.assertEqual((copy / "favoris.json").read_bytes(), original)

    def test_incorrect_database_fails_closed_without_modifying_original(self):
        db = self.root / "historique.sqlite3"
        original = b"invalid sqlite header - user progression"
        db.write_bytes(original)
        with self.assertRaises(sqlite3.DatabaseError):
            TrackerStore(self.root)
        self.assertEqual(db.read_bytes(), original)
        self.assertFalse(
            (self.root / "backups" / "avant_v2.7.3" / "sauvegarde_complete.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
