"""Updater du programme Windows autonome. L'updater Python de V1 n'est pas utilisé."""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime
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

INSTALL_PS1 = r"""
param(
 [Parameter(Mandatory=$true)][int]$ParentPid,
 [Parameter(Mandatory=$true)][string]$Source,
 [Parameter(Mandatory=$true)][string]$Target,
 [Parameter(Mandatory=$true)][string]$Backup,
 [Parameter(Mandatory=$true)][string]$Log,
 [switch]$SmokeTest
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$backupReady = $false
$updateApplied = $false

function Write-Journal([string]$Message) {
  $timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss.fff'
  try {
    $logFolder = Split-Path -Parent $Log
    if ($logFolder -and !(Test-Path -LiteralPath $logFolder)) {
      New-Item -ItemType Directory -Force -Path $logFolder | Out-Null
    }
    Add-Content -LiteralPath $Log -Encoding UTF8 -Value "$timestamp $Message"
  } catch {}
}
Write-Journal "START parent=$ParentPid smoke=$SmokeTest target=$Target source=$Source"
try {
  if (!(Test-Path -LiteralPath (Join-Path $Source 'ValheimStatsTracker.exe') -PathType Leaf)) {
    throw "Le nouvel exécutable Windows est absent du dossier préparé."
  }
  if (!(Test-Path -LiteralPath (Join-Path $Target 'ValheimStatsTracker.exe') -PathType Leaf)) {
    throw "L'ancien exécutable Windows est introuvable."
  }
  if (([IO.Path]::GetFullPath($Source).TrimEnd('\')) -eq ([IO.Path]::GetFullPath($Target).TrimEnd('\'))) {
    throw 'Le dossier source et le dossier cible sont identiques.'
  }
  if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
    Write-Journal 'WAIT_PARENT'
    try { Wait-Process -Id $ParentPid -Timeout 65 -ErrorAction Stop } catch {
      if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        throw 'Le tracker ne se ferme pas : installation annulée sans modification.'
      }
    }
  }
  Start-Sleep -Milliseconds 450
  New-Item -ItemType Directory -Force -Path $Backup | Out-Null
  Write-Journal 'BACKUP_START'
  Get-ChildItem -LiteralPath $Target -Force | Copy-Item -Destination $Backup -Recurse -Force -ErrorAction Stop
  $backupReady = $true
  Write-Journal 'BACKUP_OK'
  Write-Journal 'COPY_START'
  $copied = $false
  for ($attempt=1; $attempt -le 15; $attempt++) {
    try {
      Get-ChildItem -LiteralPath $Source -Force | Copy-Item -Destination $Target -Recurse -Force -ErrorAction Stop
      $copied = $true
      break
    } catch {
      Write-Journal "COPY_RETRY $attempt $($_.Exception.Message)"
      Start-Sleep -Seconds 1
    }
  }
  if (!$copied) { throw 'Fichiers Windows verrouillés : remplacement impossible.' }
  $updateApplied = $true
  Write-Journal 'COPY_OK'
  $exe = Join-Path $Target 'ValheimStatsTracker.exe'
  Write-Journal 'RELAUNCH_START'
  if ($SmokeTest) {
    $process = Start-Process -FilePath $exe -ArgumentList '--verify-unitypy-bundle' -WorkingDirectory $Target -Wait -PassThru -ErrorAction Stop
    if ($process.ExitCode -ne 0) {
      throw "L'exécutable de vérification a échoué (code $($process.ExitCode))."
    }
    Write-Journal 'RELAUNCH_TEST_OK'
  } else {
    $process = Start-Process -FilePath $exe -WorkingDirectory $Target -PassThru -ErrorAction Stop
    Start-Sleep -Seconds 4
    $process.Refresh()
    if ($process.HasExited) {
      throw "Le nouveau tracker se ferme immédiatement (code $($process.ExitCode))."
    }
    Write-Journal "RELAUNCH_OK pid=$($process.Id)"
  }
  Write-Journal 'INSTALL_OK'
  exit 0
} catch {
  Write-Journal "INSTALL_ERROR $($_.Exception.Message)"
  if ($backupReady) {
    Write-Journal 'ROLLBACK_START'
    try {
      Get-ChildItem -LiteralPath $Backup -Force | Copy-Item -Destination $Target -Recurse -Force -ErrorAction Stop
      Write-Journal 'ROLLBACK_OK'
    } catch { Write-Journal "ROLLBACK_ERROR $($_.Exception.Message)" }
  }
  if (!$SmokeTest) {
    try {
      $fallback = Join-Path $Target 'ValheimStatsTracker.exe'
      if (Test-Path -LiteralPath $fallback -PathType Leaf) {
        Start-Process -FilePath $fallback -WorkingDirectory $Target -ErrorAction Stop
        Write-Journal 'OLD_VERSION_RELAUNCH_ATTEMPTED'
      }
    } catch { Write-Journal "OLD_VERSION_RELAUNCH_ERROR $($_.Exception.Message)" }
  }
  exit 1
}
"""

def install_and_restart(staged, directory):
    if os.name!='nt' or not getattr(sys,'frozen',False):
        raise UpdateError('Installe la version Windows autonome pour utiliser cette fonction.')
    exe=Path(sys.executable).resolve()
    if exe.name.casefold()!='valheimstatstracker.exe':
        raise UpdateError('Exécutable de destination invalide.')
    folder=exe.parent
    staged=Path(staged).resolve()
    if not (staged/'ValheimStatsTracker.exe').is_file():
        raise UpdateError('Nouvelle version non préparée.')
    data=Path(directory)
    data.mkdir(parents=True,exist_ok=True)
    script=data/'updates'/'install.ps1'
    script.parent.mkdir(parents=True,exist_ok=True)
    script.write_text(INSTALL_PS1,encoding='utf-8-sig')
    backup=data/'update_backups'/datetime.now().strftime('%Y%m%d_%H%M%S')
    log=data/'updates'/'install.log'
    subprocess.Popen(
       ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),
        '-ParentPid',str(os.getpid()),'-Source',str(staged),'-Target',str(folder),
        '-Backup',str(backup),'-Log',str(log)],
       cwd=str(data),creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS,
       close_fds=True)
