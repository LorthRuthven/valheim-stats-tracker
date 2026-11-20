"""Mise à jour Windows transparente : ni script caché ni remplacement silencieux."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from windows_update import (
    UpdateError, manual_update_instructions, stage_release,
)


class FakeResponse(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}


def package_bytes():
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("ValheimStatsTracker/ValheimStatsTracker.exe", b"MZ-tracker-test")
        archive.writestr("ValheimStatsTracker/_internal/asset.txt", b"safe-file")
    return target.getvalue()


class SafeWindowsUpdateTests(unittest.TestCase):
    def test_verified_download_prepares_without_launching_or_replacing(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = root / "installed" / "ValheimStatsTracker.exe"
            installed.parent.mkdir()
            installed.write_bytes(b"OLD")
            update = {
                "version": "2.5.0", "url": "https://github.com/example/test",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            staged = stage_release(update, root / "updates", opener=lambda *_, **__: FakeResponse(data))
            self.assertTrue((staged / "ValheimStatsTracker.exe").exists())
            info = manual_update_instructions(staged, installed)
            self.assertEqual(Path(info["source"]), staged)
            self.assertEqual(Path(info["target"]), installed.parent)
            self.assertEqual(installed.read_bytes(), b"OLD")
            self.assertFalse((root / "installed" / "install.ps1").exists())
            self.assertTrue((root / "updates" / "Valheim_2.5.0.zip").exists())

    def test_sha256_mismatch_blocks_staging(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            update = {
                "version": "2.5.0", "url": "https://github.com/example/test",
                "sha256": "0" * 64,
            }
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                stage_release(update, folder, opener=lambda *_, **__: FakeResponse(data))
            self.assertFalse(list(Path(folder).rglob("*.exe")))

    def test_missing_staged_executable_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(UpdateError):
                manual_update_instructions(folder, Path(folder) / "ValheimStatsTracker.exe")

    def test_wrong_install_name_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "new"
            source.mkdir()
            (source / "ValheimStatsTracker.exe").write_bytes(b"MZ")
            with self.assertRaises(UpdateError):
                manual_update_instructions(source, Path(folder) / "other.exe")


if __name__ == "__main__":
    unittest.main()
