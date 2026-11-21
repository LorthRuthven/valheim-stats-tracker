"""Tests de l'updater de sécurité V2.4.1 réutilisé dans V2.5.

Aucun lancement d'EXE, aucune extraction de ZIP ni script caché.
"""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import windows_update
from windows_update import UpdateError, stage_release, validate_archive


class FakeResponse(io.BytesIO):
    def __init__(self, content, url):
        super().__init__(content)
        self.url = url
        self.headers = {"Content-Length": str(len(content))}

    def geturl(self):
        return self.url


def package_bytes():
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("ValheimStatsTracker/ValheimStatsTracker.exe", b"MZ-tracker-test")
        archive.writestr("ValheimStatsTracker/_internal/asset.txt", b"safe-file")
    return target.getvalue()


def info_for(data):
    version = "2.5.0"
    name = f"Valheim_Stats_Tracker_v{version}_Windows.zip"
    return {
        "version": version,
        "url": f"https://github.com/{windows_update.REPO}/releases/download/v{version}/{name}",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


class SafeWindowsUpdateTests(unittest.TestCase):
    def test_verified_zip_not_extracted_or_executed(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = root / "installed" / "ValheimStatsTracker.exe"
            installed.parent.mkdir()
            installed.write_bytes(b"OLD")
            info = info_for(data)
            archive = stage_release(
                info, root / "updates",
                opener=lambda *_, **__: FakeResponse(data, info["url"]),
            )
            self.assertTrue(archive.is_file())
            self.assertEqual(archive.read_bytes(), data)
            self.assertEqual(installed.read_bytes(), b"OLD")
            self.assertEqual(len(list((root / "updates").rglob("*.exe"))), 0)
            self.assertEqual(len(list((root / "updates").rglob("*.ps1"))), 0)
            validate_archive(archive)

    def test_official_251_is_detected_as_new_version_with_digest(self):
        import json
        version = "2.5.1"
        name = "Valheim_Stats_Tracker_v2.5.1_Windows.zip"
        url = f"https://github.com/{windows_update.REPO}/releases/download/v{version}/{name}"
        payload = json.dumps({
            "tag_name": "v2.5.1",
            "assets": [{"name": name, "browser_download_url": url,
                        "digest": "sha256:" + "a" * 64}],
        }).encode("utf8")
        result = windows_update.check_release(
            "2.5.0",
            opener=lambda *_, **__: FakeResponse(payload, windows_update.API),
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["version"], "2.5.1")
        self.assertEqual(result["url"], url)
        self.assertEqual(result["sha256"], "a" * 64)
        result_same = windows_update.check_release(
            "2.5.1",
            opener=lambda *_, **__: FakeResponse(payload, windows_update.API),
        )
        self.assertFalse(result_same["available"])

    def test_sha256_mismatch_refuses_download(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            info = info_for(data)
            info["sha256"] = "0" * 64
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                stage_release(
                    info, folder,
                    opener=lambda *_, **__: FakeResponse(data, info["url"]),
                )
            self.assertFalse(list(Path(folder).rglob("*.zip")))

    def test_nonofficial_url_refused_before_network(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            info = info_for(data)
            info["url"] = "https://example.org/fake.zip"
            with self.assertRaisesRegex(UpdateError, "non officiel"):
                stage_release(
                    info, folder,
                    opener=lambda *_, **__: self.fail("Le réseau ne doit pas être appelé"),
                )

    def test_non_https_redirect_refused(self):
        data = package_bytes()
        with tempfile.TemporaryDirectory() as folder:
            info = info_for(data)
            with self.assertRaisesRegex(UpdateError, "HTTPS"):
                stage_release(
                    info, folder,
                    opener=lambda *_, **__: FakeResponse(data, "http://fake.example/file.zip"),
                )

    def test_archive_directory_traversal_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "bad.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("ValheimStatsTracker/../../outside.exe", b"MZ")
                z.writestr("ValheimStatsTracker/ValheimStatsTracker.exe", b"MZ")
            with self.assertRaises(UpdateError):
                validate_archive(bad)

    def test_no_hidden_power_shell_or_automatic_installer_code(self):
        source = Path(windows_update.__file__).read_text(encoding="utf-8")
        self.assertNotIn("INSTALL_PS1", source)
        self.assertNotIn("ExecutionPolicy", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("extractall", source)
        self.assertNotIn("install_and_restart", source)


if __name__ == "__main__":
    unittest.main()
