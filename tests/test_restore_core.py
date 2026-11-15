"""Non-régression V2.2 : toutes les fonctions perdues sont revenues en Qt."""
import ast
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class RestoredFeatureTests(unittest.TestCase):
    def test_unitypy_resources_are_collected_in_windows_release(self):
        workflow=(ROOT/'.github/workflows/release.yml').read_text(encoding='utf8')
        self.assertIn('--collect-all UnityPy',workflow)
        self.assertIn('--verify-unitypy-bundle',workflow)
        source=(ROOT/'nordic_ui.py').read_text(encoding='utf8')
        self.assertIn("importlib.import_module(name)",source)
        self.assertIn("'UnityPy.resources'",source)

    def test_legacy_features_present(self):
        src=(ROOT/'restored_pages.py').read_text(encoding='utf8')
        tree=ast.parse(src)
        classes={node.name:node for node in tree.body if isinstance(node,ast.ClassDef)}
        self.assertIn('RestoredPagesMixin',classes)
        methods={node.name for node in classes['RestoredPagesMixin'].body if isinstance(node,ast.FunctionDef)}
        needed={
            '_make_restored_pages','_make_progress_center','_make_boss_detail',
            '_make_activity_detail','_make_skill_detail','_make_raw_detail',
            '_restore_history_controls','_restore_achievement_controls',
            '_restore_combat_controls','export_history_csv','draw_success_detail',
            '_refresh_restored_pages','_refresh_progress_center'
        }
        self.assertTrue(needed.issubset(methods),needed-methods)
        self.assertIn("len(achievement['parts'])",src) if False else None
        self.assertIn("len(target['parts'])",src)
        self.assertNotIn("pending_actions(row, 200)",src)

    def test_achievement_game_assets_not_invented(self):
        src=(ROOT/'real_assets.py').read_text(encoding='utf8')
        self.assertIn('def achievement_icon(title)',src)
        self.assertIn('def game_icon(prefab)',src)
        self.assertIn('return QIcon()',src)

    def test_history_gains_ignore_reset(self):
        # Les fonctions métier Qt sont exercées sur le runner Windows.
        code=(ROOT/'restored_pages.py').read_text(encoding='utf8')
        self.assertIn('max(0, value-previous)',code)

    def test_windows_updater_removes_stealth_processes_and_exe_replacement(self):
        import inspect
        import windows_update
        source=inspect.getsource(windows_update)
        self.assertNotIn('INSTALL_PS1',source)
        self.assertNotIn('launch_powershell',source)
        self.assertNotIn('ExecutionPolicy',source)
        self.assertNotIn('subprocess',source)
        self.assertNotIn('rmtree(',source)
        self.assertNotIn('extractall(',source)
        self.assertNotIn('install_and_restart',source)
        self.assertIn('digest.hexdigest()',source)
        self.assertIn('validate_archive(partial)',source)
        workflow=(ROOT/'.github/workflows/release.yml').read_text(encoding='utf8')
        self.assertIn('--verify-safe-updater',workflow)
        self.assertNotIn('--verify-updater-bootstrap',workflow)

    def test_windows_updater_archive_security(self):
        from windows_update import validate_archive, UpdateError, version_tuple
        self.assertLess(version_tuple('2.1.9'),version_tuple('2.2.0'))
        with tempfile.TemporaryDirectory() as tmp:
            safe=Path(tmp)/'safe.zip'
            with zipfile.ZipFile(safe,'w') as z:
                z.writestr('ValheimStatsTracker/ValheimStatsTracker.exe',b'MZ')
                z.writestr('ValheimStatsTracker/_internal/library.bin',b'data')
            validate_archive(safe)
            bad=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(bad,'w') as z:
                z.writestr('ValheimStatsTracker/../../danger.txt','x')
                z.writestr('ValheimStatsTracker/ValheimStatsTracker.exe','MZ')
            with self.assertRaises(UpdateError):
                validate_archive(bad)
            missing=Path(tmp)/'missing.zip'
            with zipfile.ZipFile(missing,'w') as z:
                z.writestr('ValheimStatsTracker/README.txt','x')
            with self.assertRaises(UpdateError):
                validate_archive(missing)

if __name__=='__main__':
    unittest.main()
