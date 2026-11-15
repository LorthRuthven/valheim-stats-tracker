"""Mises à jour Windows : installeur standard visible, aucun PowerShell caché.

La provenance GitHub et le SHA-256 sont vérifiés AVANT de proposer l'installation.
Le clic utilisateur déclenche l'installateur Windows normal (assistant visible).
Jamais de modification directe de l'EXE en cours d'exécution, de suppression de
dossiers ou de modification de l'antivirus.

Une archive Windows portable est proposée si aucun installateur n'est publié.
Les contrôles de fichiers ne remplacent pas une analyse de sécurité indépendante.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "LorthRuthven/valheim-stats-tracker"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
MAX_ZIP = 250 * 1024 * 1024
MAX_TOTAL = 850 * 1024 * 1024
MAX_FILES = 25_000
MAX_INSTALLER = 250 * 1024 * 1024


class UpdateError(Exception):
    pass


def version_tuple(text):
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(text)):
        raise UpdateError("Version invalide : " + str(text))
    return tuple(map(int, text.split(".")))


def asset_filename(version, kind):
    version_tuple(version)
    if kind == "installer":
        return f"Valheim_Stats_Tracker_v{version}_Setup_Windows.exe"
    if kind == "zip":
        return f"Valheim_Stats_Tracker_v{version}_Windows.zip"
    raise UpdateError("Type de téléchargement invalide.")


def check_release(current, opener=None):
    """Privilégie l'installateur standard ; ZIP portable en repli."""
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(
        API, headers={"User-Agent": "Valheim-Stats-Tracker-Windows"}
    )
    with opener(request, timeout=20) as response:
        data = json.loads(response.read(128_000))
    version = str(data.get("tag_name", "")).removeprefix("v")
    version_tuple(version)
    for kind in ("installer", "zip"):
        filename = asset_filename(version, kind)
        matching = next((a for a in data.get("assets", [])
                         if a.get("name") == filename), None)
        if matching is None:
            continue
        url = matching.get("browser_download_url", "")
        expected = f"https://github.com/{REPO}/releases/download/v{version}/{filename}"
        if url != expected:
            raise UpdateError("Adresse de mise à jour non officielle.")
        digest = matching.get("digest") or ""
        if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
            raise UpdateError("Empreinte SHA-256 absente de la version officielle.")
        return {
            "version": version,
            "available": version_tuple(version) > version_tuple(current),
            "kind": kind,
            "url": url,
            "sha256": digest.split(":", 1)[1].lower(),
        }
    raise UpdateError("Aucun installateur ou ZIP Windows officiel dans la release.")


def validate_archive(path):
    """Vérification statique du ZIP, sans lancer ni extraire de fichier."""
    archive = Path(path)
    if archive.stat().st_size > MAX_ZIP:
        raise UpdateError("Archive trop volumineuse.")
    try:
        with zipfile.ZipFile(archive) as package:
            items = package.infolist()
            if not items or len(items) > MAX_FILES:
                raise UpdateError("Contenu ZIP invalide.")
            if sum(item.file_size for item in items) > MAX_TOTAL:
                raise UpdateError("ZIP décompressé trop volumineux.")
            seen = set()
            exe = False
            for item in items:
                # Contrôle sans extraction ; refuser les chemins ambigus,
                # doubles chemins, liens symboliques et traversées.
                name = item.filename
                normalized = PurePosixPath(name)
                parts = normalized.parts
                if ("\\" in name or name.startswith("/")
                        or ".." in parts or "." in parts
                        or not parts or parts[0] != "ValheimStatsTracker"):
                    raise UpdateError("Chemin interdit dans le ZIP.")
                key = name.casefold().rstrip("/")
                if key in seen:
                    raise UpdateError("Entrées en double dans le ZIP.")
                seen.add(key)
                mode = (item.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise UpdateError("Lien symbolique interdit dans le ZIP.")
                if name == "ValheimStatsTracker/ValheimStatsTracker.exe":
                    exe = True
            if not exe:
                raise UpdateError("Exécutable Windows manquant dans l'archive.")
    except (zipfile.BadZipFile, OSError) as exc:
        raise UpdateError("Archive Windows corrompue ou inaccessible.") from exc


def validate_installer(path):
    """Contrôle statique PE ; ne conclut PAS à l'innocuité du programme."""
    path = Path(path)
    size = path.stat().st_size
    if size < 1024 or size > MAX_INSTALLER:
        raise UpdateError("Installateur Windows trop petit ou trop volumineux.")
    with path.open("rb") as executable:
        if executable.read(2) != b"MZ":
            raise UpdateError("En-tête exécutable Windows absent.")
        executable.seek(0x3C)
        offset_data = executable.read(4)
        if len(offset_data) != 4:
            raise UpdateError("En-tête PE incomplet.")
        offset = struct.unpack("<I", offset_data)[0]
        if offset > min(size - 4, 4 * 1024 * 1024):
            raise UpdateError("Offset PE invalide.")
        executable.seek(offset)
        if executable.read(4) != b"PE\x00\x00":
            raise UpdateError("Signature PE invalide.")


def stage_release(info, directory, progress=lambda amount, total: None, opener=None):
    """Télécharge un installateur ou ZIP officiel en vérifiant son SHA-256."""
    opener = opener or urllib.request.urlopen
    version = str(info.get("version", ""))
    version_tuple(version)
    kind = info.get("kind", "zip")
    filename = asset_filename(version, kind)
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    partial = target / f"Valheim_{version}_{kind}.download"
    archive = target / filename
    expected_url = f"https://github.com/{REPO}/releases/download/v{version}/{filename}"
    if info.get("url") != expected_url:
        raise UpdateError("Lien de téléchargement non officiel.")
    digest_expected = info.get("sha256")
    if not isinstance(digest_expected, str) or not re.fullmatch(r"[0-9a-f]{64}", digest_expected):
        raise UpdateError("Empreinte SHA-256 invalide.")
    digest = hashlib.sha256()
    size = 0
    try:
        req = urllib.request.Request(
            expected_url, headers={"User-Agent": "Valheim-Stats-Tracker-Windows"}
        )
        with opener(req, timeout=90) as response, partial.open("wb") as output:
            if not str(response.geturl()).startswith("https://"):
                raise UpdateError("Redirection non HTTPS refusée.")
            announced = int(response.headers.get("Content-Length", "0") or 0)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > (MAX_INSTALLER if kind == "installer" else MAX_ZIP):
                    raise UpdateError("Téléchargement trop volumineux.")
                digest.update(chunk)
                output.write(chunk)
                progress(size, announced)
        if digest.hexdigest() != digest_expected:
            raise UpdateError("SHA-256 incorrect : téléchargement annulé.")
        if kind == "installer":
            validate_installer(partial)
        else:
            validate_archive(partial)
        partial.replace(archive)
        return archive
    finally:
        partial.unlink(missing_ok=True)


def launch_verified_installer(info, installer):
    """Ouvre l'assistant normal de Windows après une demande utilisateur.

    Pas de processus masqué, de privilèges forcés ni de contournement Defender.
    """
    if info.get("kind") != "installer":
        raise UpdateError("Ce fichier n'est pas un installateur officiel.")
    installer = Path(installer)
    expected_name = asset_filename(str(info.get("version", "")), "installer")
    if installer.name != expected_name or not installer.is_file():
        raise UpdateError("Installateur téléchargé introuvable.")
    digest_expected = info.get("sha256")
    if not isinstance(digest_expected, str) or not re.fullmatch(r"[0-9a-f]{64}", digest_expected):
        raise UpdateError("Empreinte SHA-256 de l'installateur invalide.")
    with installer.open("rb") as stream:
        digest_observed = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest_observed != digest_expected:
        raise UpdateError("L'installateur a changé depuis le téléchargement : exécution refusée.")
    validate_installer(installer)
    if os.name != "nt":
        raise UpdateError("Installateur utilisable uniquement sur Windows.")
    # Lance le programme d'installation normal, avec sa fenêtre visible.
    # Il peut demander une confirmation Windows ; ne jamais la contourner.
    os.startfile(str(installer))


def open_download_folder(archive):
    """Ouvre l'Explorateur Windows ; aucune installation automatique."""
    archive = Path(archive)
    if not archive.is_file():
        raise UpdateError("Archive vérifiée introuvable.")
    if os.name != "nt":
        raise UpdateError("Ouverture automatique réservée à Windows.")
    os.startfile(str(archive.parent))
