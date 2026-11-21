"""Sécurité et réversibilité de la mise à jour intégrée Windows V2.5.2."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from windows_install import active_executable, install_release
from windows_update import UpdateError


def make_zip(root, version="2.5.2", *, traversal=False):
    archive = root / "release.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("ValheimStatsTracker/ValheimStatsTracker.exe", b"MZ-Windows-fake")
        out.writestr("ValheimStatsTracker/_internal/library.dll", b"MZ-bibliotheque")
        if traversal:
            out.writestr("ValheimStatsTracker/../../danger.exe", b"danger")
    return archive, {"version": version,
                     "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


class IntegratedUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.versions = self.base / "programs"
        self.state = self.base / "user_data" / "installed_windows.json"
        self.historical = self.base / "user_data" / "historique.sqlite3"
        self.historical.parent.mkdir(parents=True)
        self.historical.write_bytes(b"INTOUCHABLE - succes et archives utilisateur")
        self.original = self.base / "ancienne_version" / "ValheimStatsTracker.exe"
        self.original.parent.mkdir()
        self.original.write_bytes(b"ANCIEN EXE")

    def install(self, info, archive, *, scan=None, probe=None, backup=None):
        return install_release(
            info, archive, program_root=self.versions, marker=self.state,
            scan=scan or (lambda *_: None),
            probe=probe or (lambda *_: None),
            backup=backup or (lambda: None),
        )

    def test_installation_versionnee_n_altere_ni_ancien_exe_ni_progression(self):
        archive, info = make_zip(self.base)
        controls = []
        executable = self.install(
            info, archive,
            scan=lambda zip_path, folder: controls.append(("scan", zip_path, folder)),
            probe=lambda file, version: controls.append(("probe", file, version)),
            backup=lambda: controls.append(("backup",)),
        )
        self.assertTrue(executable.is_file())
        self.assertEqual(executable.read_bytes(), b"MZ-Windows-fake")
        self.assertEqual(self.original.read_bytes(), b"ANCIEN EXE")
        self.assertEqual(self.historical.read_bytes(), b"INTOUCHABLE - succes et archives utilisateur")
        self.assertEqual([c[0] for c in controls], ["scan", "probe", "backup"])
        self.assertEqual(active_executable("2.5.1", program_root=self.versions, marker=self.state), executable)
        self.assertIsNone(active_executable("2.5.2", program_root=self.versions, marker=self.state))
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["version"], "2.5.2")
        self.assertEqual(state["sha256"], info["sha256"])
        self.assertTrue((executable.parent.parent / "installation.json").exists())

    def test_antivirus_refuse_pas_d_activation_ni_ecrasement(self):
        archive, info = make_zip(self.base)
        def refuse(*_):
            raise UpdateError("Defender a bloqué l'installation")
        with self.assertRaisesRegex(UpdateError, "Defender"):
            self.install(info, archive, scan=refuse)
        self.assertFalse(self.state.exists())
        self.assertFalse(list((self.versions / "versions").glob("2.5.2-*")))
        self.assertFalse(list((self.versions / "versions").glob(".preparation_*")))
        self.assertEqual(self.historical.read_bytes(), b"INTOUCHABLE - succes et archives utilisateur")

    def test_controle_de_demarrage_echoue_et_conserve_ancienne_version(self):
        archive, info = make_zip(self.base)
        def fail(*_):
            raise UpdateError("Le programme ne démarre pas")
        with self.assertRaisesRegex(UpdateError, "démarre"):
            self.install(info, archive, probe=fail)
        self.assertFalse(self.state.exists())
        self.assertFalse(list((self.versions / "versions").glob("2.5.2-*")))
        self.assertEqual(self.original.read_bytes(), b"ANCIEN EXE")

    def test_sha_incorrect_et_zip_dangereux_refuses_avant_extraction(self):
        archive, info = make_zip(self.base)
        info["sha256"] = "0" * 64
        with self.assertRaisesRegex(UpdateError, "SHA-256"):
            self.install(info, archive)
        archive, info = make_zip(self.base, traversal=True)
        with self.assertRaises(UpdateError):
            self.install(info, archive)
        self.assertFalse(self.state.exists())

    def test_idempotence_et_ancienne_version_preservee(self):
        archive, info = make_zip(self.base)
        first = self.install(info, archive)
        second = self.install(info, archive)
        self.assertEqual(first, second)
        self.assertEqual(len(list((self.versions / "versions").glob("2.5.2-*"))), 1)
        self.assertEqual(first.read_bytes(), b"MZ-Windows-fake")

    def test_nouvelle_version_ne_supprime_pas_precedente(self):
        archive, info = make_zip(self.base, version="2.5.2")
        earlier = self.install(info, archive)
        archive, info = make_zip(self.base, version="2.5.3")
        later = self.install(info, archive)
        self.assertNotEqual(later, earlier)
        self.assertTrue(earlier.exists())
        self.assertEqual(active_executable("2.5.2", program_root=self.versions, marker=self.state), later)
        data = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(data["previous"]["version"], "2.5.2")

    def test_installation_violée_non_réutilisée(self):
        archive, info = make_zip(self.base)
        executable = self.install(info, archive)
        executable.write_bytes(b"remplacement malveillant")
        self.assertIsNone(active_executable("2.5.1", program_root=self.versions, marker=self.state))
        with self.assertRaisesRegex(UpdateError, "pas vérifiable"):
            self.install(info, archive)
        self.assertEqual(self.original.read_bytes(), b"ANCIEN EXE")

    def test_erreur_sauvegarde_bloque_activation(self):
        archive, info = make_zip(self.base)
        def no_backup():
            raise OSError("Impossible de sauvegarder les succès")
        with self.assertRaisesRegex(OSError, "succès"):
            self.install(info, archive, backup=no_backup)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.historical.read_bytes(), b"INTOUCHABLE - succes et archives utilisateur")


if __name__ == "__main__":
    unittest.main()
