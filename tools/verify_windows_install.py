"""Test de bout en bout de l'installateur avec le vrai ZIP PyInstaller Windows.

À lancer uniquement dans une CI Windows, après construction du ZIP.
Le scan est remplacé par un espion de test ; le vrai contrôle Defender est
réalisé par une autre étape distincte du workflow sur les binaires publiables.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from windows_install import active_executable, install_release, sha256_file


def main(archive: Path, version: str):
    if sys.platform != "win32":
        raise RuntimeError("Test d'intégration à réaliser sur Windows.")
    archive = Path(archive).resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    digest = sha256_file(archive)
    info = {"version": version, "sha256": digest}
    with tempfile.TemporaryDirectory(prefix="valheim_update_integration_") as temp:
        root = Path(temp)
        original = root / "ancienne_version.exe"
        original.write_bytes(b"MZ-original-preserve")
        data = root / "data" / "historique.sqlite3"
        data.parent.mkdir(parents=True)
        data.write_bytes(b"PROGRESSION A CONSERVER")
        marker = root / "data" / "installed_windows.json"
        scan_calls = []

        def fake_scan(source, folder):
            assert source == archive and folder.is_dir()
            scan_calls.append((source, folder))

        installed = install_release(
            info, archive, program_root=root / "programmes", marker=marker,
            scan=fake_scan,
            # Lancement du VRAI EXE en mode --verify-update-ready, pas de simulation.
            backup=lambda: None,
        )
        if len(scan_calls) != 1 or not installed.is_file():
            raise AssertionError("L'archive n'a pas été installée et contrôlée.")
        if active_executable("0.0.1", program_root=root / "programmes", marker=marker) != installed:
            raise AssertionError("Activation de la nouvelle version non enregistrée.")
        if original.read_bytes() != b"MZ-original-preserve":
            raise AssertionError("Ancien EXE modifié.")
        if data.read_bytes() != b"PROGRESSION A CONSERVER":
            raise AssertionError("Historique du joueur modifié.")
        assert json.loads(marker.read_text(encoding="utf-8"))["version"] == version
        print("Installation versionnée du vrai EXE, activation et ancien état préservé : OK")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python tools/verify_windows_install.py chemin.zip version")
    main(Path(sys.argv[1]), sys.argv[2])
