"""Régression du bouton « Actualiser maintenant » sans mod Valheim."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import TrackerApp


class DummyVar:
    def __init__(self):
        self.value = ''

    def set(self, value):
        self.value = value


class ManualRefreshTests(unittest.TestCase):
    def instance(self, path):
        app = TrackerApp.__new__(TrackerApp)
        app.path = str(path)
        app.status = DummyVar()
        app.refresh_notice = DummyVar()
        app.sidebar_player = DummyVar()
        app.sidebar_subtitle = DummyVar()
        app.current = {'name': 'Test'}
        app.current_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        stat = Path(path).stat()
        app.file_stamp = (stat.st_mtime_ns, stat.st_size)
        app.refresh = lambda: None
        return app

    def test_force_read_unchanged_returns_state_and_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.fch'
            path.write_bytes(b'sauvegarde deja connue')
            app = self.instance(path)
            with patch('app.decode', side_effect=AssertionError('Ne doit pas redécoder la même sauvegarde')):
                result = app.read_and_record(force=True)
            self.assertEqual(result, 'unchanged')
            self.assertEqual(app.current['name'], 'Test')

    def test_manual_button_shows_verification_when_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.fch'
            path.write_bytes(b'sauvegarde non modifiee')
            app = self.instance(path)
            app.manual_refresh()
            self.assertIn('aucune nouvelle sauvegarde', app.status.value)
            self.assertIn('sauvegarde inchangée', app.refresh_notice.value)
            self.assertIn('Vérifié à', app.refresh_notice.value)

    def test_new_file_content_is_read_and_refreshes_view(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.fch'
            path.write_bytes(b'ancien')
            app = self.instance(path)
            path.write_bytes(b'nouveau contenu sauvegarde')
            calls = []
            app._save_snapshot = lambda *a: calls.append('snapshot')
            app.refresh = lambda: calls.append('refresh')
            with patch('app.decode', return_value={'name': 'Test', 'version': 47}):
                app.manual_refresh()
            self.assertEqual(calls, ['snapshot', 'refresh'])
            self.assertIn('Nouveau relevé chargé', app.status.value)
            self.assertEqual(app.current_digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_manual_read_error_is_visible_not_silent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'test.fch'
            path.write_bytes(b'ancien')
            app = self.instance(path)
            path.unlink()
            with patch('app.messagebox.showerror') as popup:
                app.manual_refresh()
            self.assertTrue(popup.called)
            self.assertIn('Échec de lecture', app.refresh_notice.value)

    def test_no_character_selected_is_explained(self):
        app = TrackerApp.__new__(TrackerApp)
        app.path = ''
        app.status = DummyVar()
        app.refresh_notice = DummyVar()
        with patch('app.messagebox.showwarning') as popup:
            app.manual_refresh()
        self.assertTrue(popup.called)
        self.assertIn('Aucun personnage', app.status.value)


if __name__ == '__main__':
    unittest.main()
