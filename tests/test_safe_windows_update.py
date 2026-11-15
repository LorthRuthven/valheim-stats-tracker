"""Tests V2.4.1 de l'updater sans exécution et de la validation des archives."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from windows_update import (
    UpdateError, check_release, open_download_folder,
    stage_release, validate_archive, version_tuple,
)

REPO="LorthRuthven/valheim-stats-tracker"


def zip_bytes(*files):
    data=io.BytesIO()
    with zipfile.ZipFile(data,"w") as archive:
        for path, content in files:
            archive.writestr(path,content)
    return data.getvalue()


class Response(io.BytesIO):
    def __init__(self, content, url):
        super().__init__(content)
        self.url=url
        self.headers={"Content-Length":str(len(content))}
    def geturl(self):
        return self.url


class SafeWindowsUpdateTests(unittest.TestCase):
    def test_archive_validation_rejects_traversal_and_missing_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            archive=root/"test.zip"
            archive.write_bytes(zip_bytes(("ValheimStatsTracker/ValheimStatsTracker.exe",b"MZ")))
            validate_archive(archive)
            for name in (
                "ValheimStatsTracker/../evil.exe",
                "ValheimStatsTracker/../../outside",
                "ValheimStatsTracker\\..\\malicious.exe",
                "/ValheimStatsTracker/escape",
            ):
                archive.write_bytes(zip_bytes(
                    ("ValheimStatsTracker/ValheimStatsTracker.exe",b"MZ"),
                    (name,b"bad"),
                ))
                with self.subTest(name=name),self.assertRaises(UpdateError):
                    validate_archive(archive)
            archive.write_bytes(zip_bytes(("ValheimStatsTracker/readme.txt",b"ok")))
            with self.assertRaisesRegex(UpdateError,"manquant"):
                validate_archive(archive)

    def test_invalid_and_duplicate_archives_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=Path(folder)/"test.zip"
            archive.write_bytes(b"not zip")
            with self.assertRaisesRegex(UpdateError,"corrompue"):
                validate_archive(archive)
            archive.write_bytes(zip_bytes(
                ("ValheimStatsTracker/ValheimStatsTracker.exe",b"MZ"),
                ("ValheimStatsTracker/valheimstatstracker.EXE",b"MZx"),
            ))
            with self.assertRaisesRegex(UpdateError,"double"):
                validate_archive(archive)

    def test_download_is_verified_but_never_extracted_or_executed(self):
        content=zip_bytes(
            ("ValheimStatsTracker/ValheimStatsTracker.exe",b"MZ"),
            ("ValheimStatsTracker/_internal/file.bin",b"library"),
        )
        version="2.4.1"
        url=f"https://github.com/{REPO}/releases/download/v{version}/Valheim_Stats_Tracker_v{version}_Windows.zip"
        info={"version":version,"url":url,"sha256":hashlib.sha256(content).hexdigest()}
        with tempfile.TemporaryDirectory() as folder:
            with patch("os.startfile",create=True) as start, \
                 patch("subprocess.Popen") as popen:
                archive=stage_release(info,folder,opener=lambda req,timeout:Response(content,url))
                self.assertEqual(archive.suffix,".zip")
                self.assertTrue(archive.is_file())
                self.assertEqual(list(Path(folder).rglob("*.exe")),[])
                self.assertFalse(start.called)
                self.assertFalse(popen.called)
            archive.unlink()
            with self.assertRaisesRegex(UpdateError,"SHA-256"):
                stage_release({**info,"sha256":"a"*64},folder,
                              opener=lambda req,timeout:Response(content,url))
            self.assertEqual(list(Path(folder).glob("*.download")),[])

    def test_no_non_official_download_and_no_http_redirect(self):
        content=zip_bytes(("ValheimStatsTracker/ValheimStatsTracker.exe",b"MZ"))
        version="2.4.1"
        url=f"https://github.com/{REPO}/releases/download/v{version}/Valheim_Stats_Tracker_v{version}_Windows.zip"
        info={"version":version,"url":url,"sha256":hashlib.sha256(content).hexdigest()}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(UpdateError,"non officiel"):
                stage_release({**info,"url":"https://example.org/file.zip"},folder)
            with self.assertRaisesRegex(UpdateError,"HTTPS"):
                stage_release(info,folder,opener=lambda req,timeout:Response(content,"http://example.net/m"))
            self.assertEqual(list(Path(folder).rglob("*.exe")),[])

    def test_official_release_metadata_must_have_sha_and_exact_asset(self):
        version="2.4.1"
        url=f"https://github.com/{REPO}/releases/download/v{version}/Valheim_Stats_Tracker_v{version}_Windows.zip"
        def response(asset):
            import json
            result={"tag_name":"v"+version,"assets":[asset]}
            return io.BytesIO(json.dumps(result).encode())
        base={"name":f"Valheim_Stats_Tracker_v{version}_Windows.zip",
              "browser_download_url":url,"digest":"sha256:"+"e"*64}
        self.assertTrue(check_release("2.4.0",opener=lambda req,timeout:response(base))["available"])
        with self.assertRaisesRegex(UpdateError,"SHA-256"):
            check_release("2.4.0",opener=lambda req,timeout:response({**base,"digest":""}))
        with self.assertRaisesRegex(UpdateError,"non officielle"):
            check_release("2.4.0",opener=lambda req,timeout:response(
                {**base,"browser_download_url":"https://evil.example/"}
            ))

    def test_version_and_folder_open_are_deterministic(self):
        self.assertGreater(version_tuple("2.4.1"),version_tuple("2.4.0"))
        with self.assertRaises(UpdateError):
            version_tuple("../2.4.1")
        with tempfile.TemporaryDirectory() as folder:
            missing=Path(folder)/"missing.zip"
            with self.assertRaisesRegex(UpdateError,"introuvable"):
                open_download_folder(missing)
