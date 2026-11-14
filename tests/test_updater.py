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
        self.assertEqual(url,'https://raw.githubusercontent.com/exemple/valheim-stats-tracker/main/update.json')
        self.assertEqual(updater.repo_from_manifest_url(url),'exemple/valheim-stats-tracker')
        with self.assertRaises(updater.UpdateError):
            updater.github_manifest_url('hello/../bad')

    def test_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            current=updater.current_version()
            archive,manifest_path=build(f'v{current}','exemple/valheim-stats-tracker',Path(tmp),allow_test_fixture=True)
            version,members=updater.verify_zip(archive,minimum_version='1.1.0')
            self.assertEqual(version,current)
            self.assertIn('app.py',members)
            # Compatibilité avec la liste autorisée de l'updater V1.7.0.
            self.assertEqual(set(members), {'app.py','updater.py','update_worker.py','valheim_reader.py','Lancer_Tracker.bat','README.txt','version.json','manifest.example.json'})
            manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            self.assertEqual(manifest['sha256'],updater.sha256_file(archive))
            self.assertEqual(manifest['version'],version)
            self.assertEqual(manifest['url'].split('/')[-1],archive.name)
            with __import__('zipfile').ZipFile(archive) as z:
                self.assertFalse(any(name.endswith('.fch') or 'historique' in name for name in z.namelist()))
                reader = z.read('Valheim_Stats_Tracker/valheim_reader.py').decode('utf-8')
                compile(reader, 'valheim_reader.py', 'exec')
                self.assertNotIn('from localization_fr import localized_name', reader)
                self.assertIn('PICKABLE_TO_ITEM', reader)
                from types import ModuleType
                probe = ModuleType('_valheim_zip_probe')
                sys.modules[probe.__name__] = probe
                try:
                    exec(compile(reader, 'valheim_reader.py', 'exec'), probe.__dict__)
                    self.assertEqual(probe.localized_name('Wood'), 'Bois')
                    self.assertEqual(probe.localized_name('$enemy_root'), 'Racine')
                finally:
                    sys.modules.pop(probe.__name__, None)

    def test_legacy_manifest_link_migrates(self):
        from unittest.mock import patch
        old='https://github.com/LorthRuthven/valheim-stats-tracker/releases/latest/download/update.json'
        self.assertEqual(updater.repo_from_manifest_url(old),'LorthRuthven/valheim-stats-tracker')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'update_config.json'
            path.write_text(json.dumps({'manifest_url':old,'check_at_startup':True}),encoding='utf8')
            with patch.object(updater,'config_path',return_value=path):
                self.assertEqual(updater.read_config()['manifest_url'],updater.DEFAULT_MANIFEST_URL)

    def test_html_error_is_explanatory(self):
        from unittest.mock import patch
        from io import BytesIO
        class DummyResponse(BytesIO):
            headers={'Content-Type':'text/html; charset=UTF-8'}
        with patch.object(updater,'_https_open',return_value=DummyResponse(b'x'*70000)):
            with self.assertRaisesRegex(updater.UpdateError,'page HTML'):
                updater.load_manifest('https://github.com/example/test')

if __name__=='__main__':unittest.main()
