import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater
from tools.build_release import build

class UpdaterTests(unittest.TestCase):
    def test_github_url(self):
        url=updater.github_manifest_url('exemple/valheim-stats-tracker')
        self.assertEqual(url,'https://github.com/exemple/valheim-stats-tracker/releases/latest/download/update.json')
        self.assertEqual(updater.repo_from_manifest_url(url),'exemple/valheim-stats-tracker')
        with self.assertRaises(updater.UpdateError):
            updater.github_manifest_url('hello/../bad')

    def test_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive,manifest_path=build('v1.2.0','exemple/valheim-stats-tracker',Path(tmp))
            version,members=updater.verify_zip(archive,minimum_version='1.1.0')
            self.assertEqual(version,'1.2.0')
            self.assertIn('app.py',members)
            manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            self.assertEqual(manifest['sha256'],updater.sha256_file(archive))
            self.assertEqual(manifest['version'],version)
            self.assertEqual(manifest['url'].split('/')[-1],archive.name)
            with __import__('zipfile').ZipFile(archive) as z:
                self.assertFalse(any(name.endswith('.fch') or 'historique' in name for name in z.namelist()))

if __name__=='__main__':unittest.main()
