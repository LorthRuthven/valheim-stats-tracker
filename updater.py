"""Mises à jour du Valheim Stats Tracker (sans mod), Python standard uniquement.

Le manifeste distant et son ZIP doivent être distribués depuis une source HTTPS de
confiance. SHA-256 protège l'intégrité du téléchargement, mais n'est pas une
signature indépendante du serveur qui publie le manifeste.
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
import urllib.request
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

VERSION = '2.2.5'
DEFAULT_MANIFEST_URL = 'https://raw.githubusercontent.com/LorthRuthven/valheim-stats-tracker/main/update.json'
MAX_ZIP_SIZE = 80 * 1024 * 1024
MAX_UNPACKED_SIZE = 120 * 1024 * 1024
MAX_MANIFEST_SIZE = 64 * 1024
MAX_ENTRIES = 100
FILES = frozenset({
    'app.py', 'valheim_reader.py', 'updater.py', 'update_worker.py',
    'Lancer_Tracker.bat', 'README.txt', 'version.json', 'manifest.example.json',
    'localization_fr.py', 'fr_names.json',
})


class UpdateError(Exception):
    """Échec réversible de validation, téléchargement ou installation."""


def data_dir():
    root = Path(os.getenv('LOCALAPPDATA') or (Path.home() / '.local' / 'share')) / 'ValheimStatsTracker'
    root.mkdir(parents=True, exist_ok=True)
    return root


def current_version():
    version_file = Path(__file__).with_name('version.json')
    try:
        version = json.loads(version_file.read_text(encoding='utf8'))['version']
        parse_version(version)
        return version
    except (OSError, ValueError, KeyError, TypeError):
        return VERSION


def parse_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}', value):
        raise UpdateError('Numéro de version invalide (attendu : 1.2.3).')
    return tuple(int(i) for i in value.split('.'))


def github_manifest_url(repo):
    """Construit l'URL publique du manifeste d'une GitHub Release.

    Seul un dépôt public fonctionne sans authentification depuis le tracker.
    """
    if not isinstance(repo, str):
        raise UpdateError('Nom de dépôt GitHub invalide.')
    repo = repo.strip().strip('/')
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}', repo):
        raise UpdateError('Saisir le dépôt au format propriétaire/nom-du-depot.')
    owner, name = repo.split('/', 1)
    if name in ('.', '..') or name.endswith('.git'):
        raise UpdateError('Nom de dépôt GitHub invalide.')
    return f'https://raw.githubusercontent.com/{owner}/{name}/main/update.json'


def repo_from_manifest_url(url):
    match = re.fullmatch(r'https://(?:github\.com/([^/]+)/([^/]+)/releases/latest/download/update\.json|raw\.githubusercontent\.com/([^/]+)/([^/]+)/main/update\.json)', url or '')
    if not match:
        return ''
    return f'{match.group(1) or match.group(3)}/{match.group(2) or match.group(4)}'


def config_path():
    return data_dir() / 'update_config.json'


def read_config():
    default = {'manifest_url': DEFAULT_MANIFEST_URL, 'check_at_startup': True}
    try:
        cfg = json.loads(config_path().read_text(encoding='utf8'))
        if isinstance(cfg, dict):
            default.update({k: cfg[k] for k in default if k in cfg})
    except (OSError, ValueError):
        pass
    if not isinstance(default['manifest_url'], str) or not default['manifest_url']:
        default['manifest_url'] = DEFAULT_MANIFEST_URL
    # Migration transparente des anciennes URLs de Releases, qui peuvent
    # renvoyer une page HTML volumineuse sur certaines configurations.
    if isinstance(default['manifest_url'], str) and re.fullmatch(
            r'https://github\.com/LorthRuthven/valheim-stats-tracker/releases/latest/download/update\.json',
            default['manifest_url']):
        default['manifest_url'] = DEFAULT_MANIFEST_URL
    default['check_at_startup'] = bool(default['check_at_startup'])
    return default


def save_config(url, check_at_startup):
    url = url.strip()
    if url:
        check_https_url(url)
    payload = {'manifest_url': url, 'check_at_startup': bool(check_at_startup)}
    target = config_path()
    tmp = target.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
    os.replace(tmp, target)
    return payload


def check_https_url(url):
    if not isinstance(url, str):
        raise UpdateError('Adresse URL invalide.')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise UpdateError('Une adresse HTTPS publique et sans identifiants est nécessaire.')
    if parsed.hostname.lower() in ('localhost', '127.0.0.1', '::1'):
        raise UpdateError('Le manifeste doit utiliser une source HTTPS publique de confiance.')


def _https_open(url, timeout=12):
    check_https_url(url)
    request = urllib.request.Request(url, headers={'User-Agent': f'ValheimStatsTracker/{VERSION}', 'Accept': 'application/json, application/zip, */*'})
    response = urllib.request.urlopen(request, timeout=timeout)
    if urlparse(response.geturl()).scheme != 'https':
        response.close()
        raise UpdateError('Redirection vers HTTP non sécurisé refusée.')
    return response


def load_manifest(url):
    with _https_open(url) as response:
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type:
            raise UpdateError('Le serveur a renvoyé une page HTML au lieu du manifeste JSON. Vérifie l’URL.')
        raw = response.read(MAX_MANIFEST_SIZE + 1)
    if raw.lstrip()[:15].lower().startswith((b'<!doctype html', b'<html')):
        raise UpdateError('Page HTML reçue à la place du manifeste JSON. Vérifie l’URL.')
    if len(raw) > MAX_MANIFEST_SIZE:
        raise UpdateError('Le fichier reçu dépasse 64 Ko : il ne semble pas être un manifeste JSON.')
    try:
        data = json.loads(raw.decode('utf8'))
    except (UnicodeError, ValueError) as exc:
        raise UpdateError('Manifeste JSON illisible.') from exc
    if not isinstance(data, dict):
        raise UpdateError('Le manifeste doit être un objet JSON.')
    version = data.get('version')
    parse_version(version)
    archive_url = data.get('url')
    check_https_url(archive_url)
    digest = data.get('sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise UpdateError('SHA-256 absent ou invalide dans le manifeste.')
    notes = data.get('notes', '')
    return {'version': version, 'url': archive_url, 'sha256': digest.lower(),
            'notes': (notes if isinstance(notes, str) else '')[:3000]}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as src:
        while chunk := src.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_zip(archive, minimum_version=None):
    """Valide un paquet officiel auto-contenu et renvoie (version, membres relatifs)."""
    archive = Path(archive)
    if archive.stat().st_size > MAX_ZIP_SIZE:
        raise UpdateError('Archive trop volumineuse.')
    try:
        with zipfile.ZipFile(archive) as z:
            files = [i for i in z.infolist() if not i.is_dir()]
            if len(files) > MAX_ENTRIES:
                raise UpdateError('Trop de fichiers dans l’archive.')
            if sum(i.file_size for i in files) > MAX_UNPACKED_SIZE:
                raise UpdateError('Archive décompressée trop volumineuse.')
            candidates = [i.filename for i in files if i.filename.rsplit('/', 1)[-1] == 'version.json']
            if len(candidates) != 1:
                raise UpdateError('Archive invalide : version.json introuvable ou multiple.')
            prefix = candidates[0][:-len('version.json')]
            # Accepte une archive plate ou un dossier racine unique.
            if prefix and (not prefix.endswith('/') or '/' in prefix.rstrip('/')):
                raise UpdateError('Structure du dossier racine non prise en charge.')
            members = {}
            for info in files:
                name = info.filename
                if '\\' in name or ':' in name or name.startswith('/') or '..' in name.split('/'):
                    raise UpdateError('Chemin potentiellement dangereux dans le ZIP.')
                if not name.startswith(prefix):
                    raise UpdateError('Fichier en dehors du dossier de l’application.')
                rel = name[len(prefix):]
                if rel not in FILES:
                    raise UpdateError(f'Fichier non autorisé dans le paquet : {rel}')
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise UpdateError('Les liens symboliques ne sont pas autorisés.')
                if rel in members:
                    raise UpdateError(f'Doublon dans le paquet : {rel}')
                members[rel] = name
            required = {'app.py', 'valheim_reader.py', 'updater.py', 'update_worker.py', 'version.json', 'Lancer_Tracker.bat'}
            if not required.issubset(members):
                raise UpdateError('Le paquet ne contient pas les composants requis.')
            if any(z.getinfo(n).file_size > 40 * 1024 * 1024 for n in members.values()):
                raise UpdateError('Un composant dépasse la taille maximale.')
            version_payload = json.loads(z.read(members['version.json']).decode('utf8'))
            version = version_payload['version']
            parse_version(version)
            if minimum_version is not None and parse_version(version) <= parse_version(minimum_version):
                raise UpdateError(f'Version {version} non supérieure à {minimum_version}.')
            bad_file = z.testzip()
            if bad_file is not None:
                raise UpdateError(f'Archive ZIP corrompue : {bad_file}')
            return version, members
    except (zipfile.BadZipFile, zipfile.LargeZipFile, KeyError, ValueError, OSError, UnicodeError) as exc:
        raise UpdateError(f'Archive non valide : {exc}') from exc


def stage_archive(source, expected_sha=None, minimum_version=None):
    source = Path(source)
    if not source.is_file():
        raise UpdateError('Fichier ZIP introuvable.')
    digest = sha256_file(source)
    if expected_sha and digest.lower() != expected_sha.lower():
        raise UpdateError('SHA-256 différent de celui du manifeste : installation annulée.')
    version, _ = verify_zip(source, minimum_version=minimum_version)
    stage = data_dir() / 'update_staging' / uuid.uuid4().hex
    stage.mkdir(parents=True)
    destination = stage / 'update.zip'
    try:
        shutil.copyfile(source, destination)
        if sha256_file(destination) != digest:
            raise UpdateError('Erreur de copie du ZIP de mise à jour.')
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {'version': version, 'sha256': digest, 'archive': str(destination)}


def download_release(manifest, minimum_version=None):
    if minimum_version is not None and parse_version(manifest['version']) <= parse_version(minimum_version):
        raise UpdateError('Aucune version plus récente.')
    stage = data_dir() / 'update_staging' / uuid.uuid4().hex
    stage.mkdir(parents=True)
    archive = stage / 'update.zip'
    digest = hashlib.sha256()
    total = 0
    try:
        with _https_open(manifest['url'], timeout=20) as response, open(archive, 'wb') as out:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_ZIP_SIZE:
                    raise UpdateError('Téléchargement trop volumineux.')
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != manifest['sha256']:
            raise UpdateError('SHA-256 non conforme au manifeste.')
        version, _ = verify_zip(archive, minimum_version=minimum_version)
        if version != manifest['version']:
            raise UpdateError('La version du ZIP ne correspond pas au manifeste.')
        return {'version': version, 'sha256': digest.hexdigest(), 'archive': str(archive)}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def launch_installer(package, target_folder, pid=None):
    """Lance l'installateur hors du dossier applicatif, puis l'UI peut se fermer."""
    here = Path(__file__).resolve().parent
    helper = data_dir() / 'updater_runtime'
    helper.mkdir(parents=True, exist_ok=True)
    for filename in ('update_worker.py', 'updater.py'):
        shutil.copy2(here / filename, helper / filename)
    flags = 0
    if os.name == 'nt':
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen(
        [sys.executable, str(helper/'update_worker.py'),
         '--archive', str(package['archive']), '--sha256', package['sha256'],
         '--target', str(Path(target_folder).resolve()),
         '--pid', str(pid or os.getpid())],
        cwd=str(helper), creationflags=flags,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
