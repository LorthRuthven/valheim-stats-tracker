"""Mises à jour Windows intégrées, par installations versionnées.

L'EXE en cours ne se remplace jamais lui-même. Une nouvelle version vérifiée
est installée dans LocalAppData/Programs, puis lancée avec accord explicite.
Le dossier de la version précédente et les données utilisateur sont préservés.
Aucune commande PowerShell, tâche planifiée ou désactivation de l'antivirus.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from windows_update import UpdateError, validate_archive, version_tuple
from v2_core import app_dir, backup_before_update

EXE = Path("ValheimStatsTracker") / "ValheimStatsTracker.exe"
STATE_NAME = "installed_windows.json"


def program_folder() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "Programs" / "ValheimStatsTracker"


def state_path() -> Path:
    return app_dir() / STATE_NAME


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_fields(info):
    version = str(info.get("version", ""))
    version_tuple(version)
    digest = str(info.get("sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise UpdateError("Empreinte SHA-256 de la version invalide.")
    return version, digest


def _folder_name(version: str, digest: str) -> str:
    return version + "-" + digest[:12]


def _load_state(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, ValueError):
        return {}


def _write_state(path: Path, state: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".installation_", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(state, out, ensure_ascii=False, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def defender_scanner(archive: Path, folder: Path):
    """Analyse explicite avec Defender ; un outil indisponible bloque l'auto-lancement."""
    if os.name != "nt":
        raise UpdateError("L'installation automatique est réservée à Windows.")
    candidates = []
    root = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows Defender" / "Platform"
    if root.is_dir():
        candidates.extend(sorted(root.glob("*/MpCmdRun.exe"), reverse=True))
    candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe")
    scanner = next((file for file in candidates if file.is_file()), None)
    if scanner is None:
        raise UpdateError("Analyse Defender indisponible : installation automatique bloquée. Le ZIP vérifié reste accessible.")
    for path in (archive, folder):
        try:
            result = subprocess.run(
                [str(scanner), "-Scan", "-ScanType", "3", "-File", str(path)],
                timeout=240, capture_output=True, text=True, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UpdateError("Analyse antivirus interrompue : installation annulée.") from exc
        if result.returncode != 0:
            raise UpdateError("Defender n'a pas validé le nouveau programme (code "
                              + str(result.returncode) + "). Installation annulée.")


def probe_candidate(executable: Path, version: str):
    """Vérifie que la version extraite démarre sans ouvrir une deuxième fenêtre."""
    try:
        result = subprocess.run(
            [str(executable), "--verify-update-ready", version],
            cwd=str(executable.parent), timeout=120,
            capture_output=True, text=True, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError("Le nouveau programme ne démarre pas : installation annulée.") from exc
    if result.returncode != 0:
        raise UpdateError("Le nouveau programme a échoué au contrôle de démarrage "
                          f"(code {result.returncode}). Ancienne version conservée.")


def _valid_receipt(directory: Path, version: str, digest: str):
    try:
        receipt = json.loads((directory / "installation.json").read_text(encoding="utf-8"))
        executable = directory / EXE
        if not executable.is_file() or receipt.get("version") != version or receipt.get("sha256") != digest:
            return None
        if sha256_file(executable) != receipt.get("exe_sha256"):
            return None
        return executable
    except (OSError, ValueError, UnicodeError):
        return None


def install_release(info, archive, *, program_root=None, marker=None,
                    scan=None, probe=None, backup=None):
    """Installe puis active atomiquement un ZIP déjà téléchargé.

    scan/probe/backup sont injectables pour tester les échecs sans lancer d'EXE.
    """
    version, digest = _release_fields(info)
    archive = Path(archive)
    if not archive.is_file() or sha256_file(archive) != digest:
        raise UpdateError("ZIP absent ou SHA-256 incorrect : installation annulée.")
    validate_archive(archive)
    root = Path(program_root) if program_root is not None else program_folder()
    marker = Path(marker) if marker is not None else state_path()
    versions = root / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / _folder_name(version, digest)
    existing = _valid_receipt(destination, version, digest) if destination.exists() else None
    if destination.exists() and existing is None:
        raise UpdateError("Un dossier de version existe déjà mais n'est pas vérifiable. Aucun fichier remplacé.")

    stage = None
    if existing is None:
        stage = Path(tempfile.mkdtemp(prefix=".preparation_", dir=versions))
        try:
            with zipfile.ZipFile(archive, "r") as package:
                if package.testzip() is not None:
                    raise UpdateError("Une entrée du ZIP est corrompue.")
                for item in package.infolist():
                    path = stage.joinpath(*Path(item.filename).parts)
                    if item.is_dir():
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with package.open(item, "r") as source, path.open("wb") as target:
                            shutil.copyfileobj(source, target)
            executable = stage / EXE
            if not executable.is_file():
                raise UpdateError("Exécutable Windows extrait invalide.")
            with executable.open("rb") as program:
                header = program.read(2)
            if header != b"MZ":
                raise UpdateError("Exécutable Windows extrait invalide.")
            (scan or defender_scanner)(archive, stage)
            if not executable.is_file():
                raise UpdateError("L'exécutable a été retiré pendant l'analyse antivirus.")
            (probe or probe_candidate)(executable, version)
            receipt = {"version": version, "sha256": digest,
                       "exe_sha256": sha256_file(executable)}
            (stage / "installation.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            # On ne touche jamais aux données avant leur sauvegarde indépendante.
            (backup or (lambda: backup_before_update(app_dir(), version)))()
            stage.rename(destination)  # Même disque : publication atomique.
            stage = None
        finally:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
    else:
        # Une réactivation requiert la même vérification antivirus et de démarrage.
        (scan or defender_scanner)(archive, destination)
        (probe or probe_candidate)(existing, version)
        (backup or (lambda: backup_before_update(app_dir(), version)))()

    executable = _valid_receipt(destination, version, digest)
    if executable is None:
        raise UpdateError("Contrôle final de l'installation échoué : activation annulée.")
    previous = _load_state(marker)
    state = {"version": version, "sha256": digest,
             "exe_sha256": sha256_file(executable),
             "previous": {k: previous[k] for k in ("version", "sha256", "exe_sha256")
                          if k in previous}}
    _write_state(marker, state)
    return executable


def active_executable(current_version, *, program_root=None, marker=None):
    """Ne résout que le chemin canonique d'une version effectivement installée."""
    marker = Path(marker) if marker is not None else state_path()
    data = _load_state(marker)
    try:
        version, digest = _release_fields(data)
        if version_tuple(version) <= version_tuple(current_version):
            return None
        root = Path(program_root) if program_root is not None else program_folder()
        destination = root / "versions" / _folder_name(version, digest)
        exe = _valid_receipt(destination, version, digest)
        if exe is not None and sha256_file(exe) == data.get("exe_sha256"):
            return exe
    except (UpdateError, OSError, TypeError):
        pass
    return None


def launch_executable(executable):
    """Lancement normal : fenêtre visible, aucun contournement de Defender."""
    executable = Path(executable)
    if os.name != "nt":
        raise UpdateError("Le redémarrage intégré n'est disponible que sur Windows.")
    if not executable.is_file():
        raise UpdateError("Nouvel exécutable introuvable.")
    return subprocess.Popen([str(executable)], cwd=str(executable.parent))


def handoff_if_newer(current_version):
    """Un ancien raccourci reste fonctionnel après l'installation d'une version."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    executable = active_executable(current_version)
    if executable is None:
        return False
    try:
        launch_executable(executable)
        return True
    except OSError:
        return False
