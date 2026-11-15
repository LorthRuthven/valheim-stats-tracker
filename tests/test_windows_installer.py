"""Validation V2.4.2 : téléchargement officiel, installateur visible et continuité."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from windows_update import (
    UpdateError, asset_filename, check_release, launch_verified_installer,
    stage_release, validate_installer,
)

REPO="LorthRuthven/valheim-stats-tracker"
VERSION="2.4.2"


def sample_pe():
    # Image PE simulée : contrôles de structure, pas exécutable valide.
    blob=bytearray(2048)
    blob[:2]=b"MZ"
    blob[0x3C:0x40]=(0x100).to_bytes(4,"little")
    blob[0x100:0x104]=b"PE\x00\x00"
    return bytes(blob)


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.headers={"Content-Length":str(len(data))}
        self.url=url
    def geturl(self):
        return self.url


def info(content,kind="installer"):
    name=asset_filename(VERSION,kind)
    return {
        "version":VERSION,"kind":kind,
        "url":f"https://github.com/{REPO}/releases/download/v{VERSION}/{name}",
        "sha256":hashlib.sha256(content).hexdigest(),
    }


class WindowsInstallerTests(unittest.TestCase):
    def test_release_prefers_official_installer_over_portable_zip(self):
        content=sample_pe()
        win=info(content)
        archive=info(content,"zip")
        def metadata(*assets):
            rows=[{"name":asset_filename(VERSION,item["kind"]),
                   "browser_download_url":item["url"],
                   "digest":"sha256:"+item["sha256"]} for item in assets]
            data=json.dumps({"tag_name":"v"+VERSION,"assets":rows}).encode()
            return io.BytesIO(data)
        result=check_release("2.4.1",opener=lambda request,timeout:metadata(archive,win))
        self.assertTrue(result["available"])
        self.assertEqual(result["kind"],"installer")
        self.assertEqual(result["url"],win["url"])
        fallback=check_release("2.4.1",opener=lambda request,timeout:metadata(archive))
        self.assertEqual(fallback["kind"],"zip")
        self.assertFalse(check_release(VERSION,opener=lambda request,timeout:metadata(win))["available"])

    def test_download_installer_sha256_no_execution_and_cleanup(self):
        data=sample_pe()
        metadata=info(data)
        with tempfile.TemporaryDirectory() as directory:
            with patch("os.startfile",create=True) as start:
                location=stage_release(
                    metadata,directory,
                    opener=lambda request,timeout:Response(data,metadata["url"])
                )
                self.assertEqual(location.read_bytes(),data)
                self.assertFalse(start.called)
            location.unlink()
            with self.assertRaisesRegex(UpdateError,"SHA-256"):
                stage_release({**metadata,"sha256":"f"*64},directory,
                    opener=lambda request,timeout:Response(data,metadata["url"]))
            self.assertEqual(list(Path(directory).glob("*.download")),[])

    def test_bad_installer_signature_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            location=Path(directory)/"setup.exe"
            for data in (b"x"*2048, b"MZ"+b"Z"*2046,
                         b"MZ"+b"\0"*2046):
                location.write_bytes(data)
                with self.assertRaises(UpdateError):
                    validate_installer(location)
            location.write_bytes(sample_pe())
            validate_installer(location)

    def test_installer_launch_requires_new_integrity_check(self):
        data=sample_pe()
        metadata=info(data)
        with tempfile.TemporaryDirectory() as directory:
            location=Path(directory)/asset_filename(VERSION,"installer")
            location.write_bytes(data)
            with patch("windows_update.os.name","nt"),patch("os.startfile",create=True) as start:
                launch_verified_installer(metadata,location)
                start.assert_called_once_with(str(location))
                location.write_bytes(data[:-1]+b"\x01")
                with self.assertRaisesRegex(UpdateError,"changé"):
                    launch_verified_installer(metadata,location)
                self.assertEqual(start.call_count,1)
            with self.assertRaisesRegex(UpdateError,"officiel"):
                launch_verified_installer({**metadata,"kind":"zip"},location)

    def test_installer_version_matches_application(self):
        from v2_core import VERSION as current
        from pathlib import Path
        spec=(Path(__file__).resolve().parents[1]/"installer"/"valheim_stats_tracker.iss").read_text(encoding="utf-8")
        self.assertIn(f'#define AppVersion "{current}"',spec)
        self.assertIn("PrivilegesRequired=lowest",spec)
        self.assertIn("CloseApplications=yes",spec)
        self.assertIn("RestartApplications=no",spec)
        self.assertIn("UsePreviousAppDir=yes",spec)
        self.assertIn("{localappdata}\\Programs\\ValheimStatsTracker",spec)
        self.assertNotIn("PowerShell",spec.replace("aucun script PowerShell",""))

if __name__=="__main__":
    unittest.main()
