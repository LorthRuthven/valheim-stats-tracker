import tempfile
import unittest

from forge_checklist import ForgeChecklist


class ForgeChecklistTests(unittest.TestCase):
    def test_persists_separately_by_character(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = ForgeChecklist(folder)
            journal.set_checked("Viking 1", "$item_sword_iron", True)
            journal.set_checked("Viking 1", "$item_sword_iron", True)
            journal.set_checked("Viking 2", "$item_sword_iron", True)
            self.assertEqual(journal.count("Viking 1"), 1)
            journal.set_checked("Viking 1", "$item_sword_iron", False)
            restored = ForgeChecklist(folder)
            self.assertFalse(restored.checked("Viking 1", "$item_sword_iron"))
            self.assertTrue(restored.checked("Viking 2", "$item_sword_iron"))

    def test_invalid_data_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            from pathlib import Path
            path = Path(folder) / "forge_checklist.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                ForgeChecklist(folder).set_checked("Viking", "$item_axe", True)
            self.assertEqual(path.read_text(encoding="utf-8"), "{invalid")

    def test_invalid_character_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                ForgeChecklist(folder).set_checked("", "$item_axe", True)


if __name__ == "__main__":
    unittest.main()
