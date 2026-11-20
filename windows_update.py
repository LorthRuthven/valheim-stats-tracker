"""Vérification et téléchargement des mises à jour Windows — sans exécution cachée.

Mécanisme de sécurité conservé depuis V2.4.1 après les alertes Defender :
- SHA-256 du ZIP vérifié contre l'empreinte GitHub Releases ;
- aucune extraction ou exécution de binaire téléchargé par l'application ;
- aucune commande PowerShell, politique d'exécution modifiée ou processus masqué ;
- l'utilisateur extrait explicitement l'archive dans un nouveau dossier.

Le verdict antivirus d'un exécutable reste indépendant du contrôle de l'archive.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPO = "LorthRuthven/valheim-stats-tracker"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
MAX_ZIP = 250 * 1024 * 1024
MAX_TOTAL = 850 * 1024 * 1024
MAX_FILES = 25_000


class UpdateError(Exception):
    pass


def version_tuple(text):
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(text)):
        raise UpdateError("Version invalide : " + str(text))
    return tuple(map(int, text.split(".")))


def check_release(current, opener=None):
    """Accepte uniquement la version officielle et son SHA-256 publié."""
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(
        API, headers={"User-Agent": "Valheim-Stats-Tracker-Windows"}
    )
    with opener(request, timeout=20) as response:
        data = json.loads(response.read(128_000))
    version = str(data.get("tag_name", "")).removeprefix("v")
    version_tuple(version)
    target = f"Valheim_Stats_Tracker_v{version}_Windows.zip"
    matching = next((a for a in data.get("assets", [])
                     if a.get("name") == target), None)
    if not matching:
        raise UpdateError("ZIP Windows absent de la dernière version.")
    url = matching.get("browser_download_url", "")
    expected = f"https://github.com/{REPO}/releases/download/v{version}/{target}"
    if url != expected:
        raise UpdateError("Adresse de mise à jour non officielle.")
    digest = matching.get("digest") or ""
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise UpdateError("Empreinte SHA-256 absente de la version officielle.")
    return {
        "version": version,
        "available": version_tuple(version) > version_tuple(current),
        "url": url,
        "sha256": digest.split(":", 1)[1].lower(),
    }


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


def stage_release(info, directory, progress=lambda amount, total: None, opener=None):
    """Télécharge le ZIP vérifié, sans installer ni exécuter l'EXE."""
    opener = opener or urllib.request.urlopen
    version = str(info.get("version", ""))
    version_tuple(version)
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    partial = target / f"Valheim_{version}.download"
    archive = target / f"Valheim_Stats_Tracker_v{version}_Windows.zip"
    expected_url = f"https://github.com/{REPO}/releases/download/v{version}/{archive.name}"
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
                if size > MAX_ZIP:
                    raise UpdateError("Téléchargement trop volumineux.")
                digest.update(chunk)
                output.write(chunk)
                progress(size, announced)
        if digest.hexdigest() != digest_expected:
            raise UpdateError("SHA-256 incorrect : téléchargement annulé.")
        validate_archive(partial)
        partial.replace(archive)
        return archive
    finally:
        partial.unlink(missing_ok=True)


def open_download_folder(archive):
    """Ouvre l'Explorateur Windows ; aucune installation automatique."""
    archive = Path(archive)
    if not archive.is_file():
        raise UpdateError("Archive vérifiée introuvable.")
    if os.name != "nt":
        raise UpdateError("Ouverture automatique réservée à Windows.")
    os.startfile(str(archive.parent))
