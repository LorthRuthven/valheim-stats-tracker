"""Updater du programme Windows autonome. L'updater Python de V1 n'est pas utilisé."""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO='LorthRuthven/valheim-stats-tracker'
API=f'https://api.github.com/repos/{REPO}/releases/latest'
MAX_ZIP=250*1024*1024
MAX_TOTAL=850*1024*1024

class UpdateError(Exception):
    pass

def version_tuple(text):
    if not re.fullmatch(r'\d+\.\d+\.\d+',str(text)):
        raise UpdateError('Version invalide : '+str(text))
    return tuple(map(int,text.split('.')))

def check_release(current,opener=None):
    opener=opener or urllib.request.urlopen
    request=urllib.request.Request(API,headers={'User-Agent':'Valheim-Stats-Tracker-Windows'})
    with opener(request,timeout=20) as response:
        data=json.loads(response.read(128_000))
    version=str(data.get('tag_name','')).removeprefix('v')
    version_tuple(version)
    target=f'Valheim_Stats_Tracker_v{version}_Windows.zip'
    match=next((asset for asset in data.get('assets',[]) if asset.get('name')==target),None)
    if match is None:raise UpdateError('ZIP Windows absent de la dernière version.')
    url=match.get('browser_download_url','')
    prefix=f'https://github.com/{REPO}/releases/download/v{version}/'
    if not url.startswith(prefix):
        raise UpdateError('Adresse de mise à jour non officielle.')
    digest=match.get('digest') or ''
    if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):
        raise UpdateError('SHA-256 absent de la version officielle.')
    return {'version':version,'available':version_tuple(version)>version_tuple(current),
            'url':url,'sha256':digest.split(':')[1].lower()}

def validate_archive(path):
    path=Path(path)
    if path.stat().st_size>MAX_ZIP:raise UpdateError('Archive trop volumineuse.')
    with zipfile.ZipFile(path) as z:
        names=z.infolist()
        if not names or len(names)>25000:raise UpdateError('Contenu ZIP invalide.')
        if sum(item.file_size for item in names)>MAX_TOTAL:
            raise UpdateError('ZIP décompressé trop volumineux.')
        exe=False
        for info in names:
            name=info.filename.replace('\\','/')
            if not name.startswith('ValheimStatsTracker/') or '/..' in name or '..\\' in name:
                raise UpdateError('Chemin interdit dans le ZIP.')
            if info.external_attr>>16 & 0o170000 == 0o120000:
                raise UpdateError('Lien symbolique interdit dans le ZIP.')
            exe|=name=='ValheimStatsTracker/ValheimStatsTracker.exe'
        if not exe:raise UpdateError('Exécutable Windows manquant.')

def stage_release(info,directory,progress=lambda amount,total:None,opener=None):
    opener=opener or urllib.request.urlopen
    target=Path(directory)
    target.mkdir(parents=True,exist_ok=True)
    partial=target/f"Valheim_{info['version']}.download"
    archive=target/f"Valheim_{info['version']}.zip"
    req=urllib.request.Request(info['url'],headers={'User-Agent':'Valheim-Stats-Tracker-Windows'})
    digest=hashlib.sha256()
    size=0
    try:
        with opener(req,timeout=90) as source,partial.open('wb') as output:
            announced=int(source.headers.get('Content-Length','0') or 0)
            while True:
                block=source.read(256*1024)
                if not block:break
                size+=len(block)
                if size>MAX_ZIP:raise UpdateError('Téléchargement trop volumineux.')
                digest.update(block);output.write(block);progress(size,announced)
        if digest.hexdigest()!=info['sha256']:
            raise UpdateError('SHA-256 incorrect : installation annulée.')
        partial.replace(archive)
        validate_archive(archive)
        staging=target/('new_'+info['version'])
        if staging.exists():shutil.rmtree(staging)
        staging.mkdir()
        with zipfile.ZipFile(archive) as z:z.extractall(staging)
        return staging/'ValheimStatsTracker'
    finally:
        partial.unlink(missing_ok=True)

def manual_update_instructions(staged, executable=None):
    """Prépare une mise à jour vérifiée, sans exécution ni modification du programme.

    Le remplacement de l'EXE en cours d'exécution requiert une action explicite
    de l'utilisateur. Aucun script PowerShell, processus caché, élévation ou
    modification de Defender n'est lancé par le tracker.
    """
    staged = Path(staged).resolve()
    if not staged.is_dir() or not (staged / 'ValheimStatsTracker.exe').is_file():
        raise UpdateError('Le dossier de mise à jour vérifié est absent.')
    if executable is None:
        executable = sys.executable
    executable = Path(executable).resolve()
    if executable.name.casefold() != 'valheimstatstracker.exe':
        raise UpdateError('Le programme Windows installé est introuvable.')
    destination = executable.parent
    if staged == destination:
        raise UpdateError('Le dossier préparé ne doit pas être le dossier installé.')
    return {
        'source': str(staged),
        'target': str(destination),
        'archive': str(staged.parent.parent / (staged.parent.name.removeprefix('new_') + '.zip')),
    }
