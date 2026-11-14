"""Installateur indépendant : attend la fermeture du tracker, remplace les fichiers,
conserve les sauvegardes de l'application et tente de restaurer en cas d'échec.
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from updater import UpdateError, data_dir, sha256_file, verify_zip


def wait_for_pid(pid, seconds=45):
    if pid <= 0:
        return
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            result = kernel.WaitForSingleObject(handle, seconds * 1000)
            kernel.CloseHandle(handle)
            if result == 0x102:  # WAIT_TIMEOUT
                raise UpdateError('Le tracker ne s’est pas fermé à temps.')
    else:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.15)
        raise UpdateError('Le tracker ne s’est pas fermé à temps.')


def install(archive, expected_sha, target, relaunch=False):
    archive = Path(archive)
    target = Path(target).resolve()
    if not (target / 'app.py').is_file():
        raise UpdateError('Dossier cible non reconnu comme installation du tracker.')
    if sha256_file(archive) != expected_sha.lower():
        raise UpdateError('SHA-256 incorrect : le fichier téléchargé a changé.')
    version, members = verify_zip(archive)
    base = data_dir()
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = base / 'update_backups' / (stamp + '_' + version.replace('.', '_'))
    backup.mkdir(parents=True, exist_ok=False)
    stage = archive.parent / 'extracted'
    stage.mkdir(parents=True, exist_ok=True)
    updated = []
    originals = set()
    try:
        with zipfile.ZipFile(archive) as z:
            for rel, stored in members.items():
                with z.open(stored) as src, (stage / rel).open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        for rel in members:
            existing = target / rel
            if existing.is_file():
                shutil.copy2(existing, backup / rel)
                originals.add(rel)
        for rel in members:
            dest = target / rel
            source = stage / rel
            temporary = target / (rel + '.update.tmp')
            shutil.copy2(source, temporary)
            os.replace(temporary, dest)
            updated.append(rel)
    except Exception as exc:
        rollback_errors = []
        for rel in reversed(updated):
            try:
                if rel in originals:
                    shutil.copy2(backup / rel, target / (rel + '.rollback.tmp'))
                    os.replace(target / (rel + '.rollback.tmp'), target / rel)
                else:
                    (target / rel).unlink(missing_ok=True)
            except Exception as restore_error:
                rollback_errors.append(f'{rel}: {restore_error}')
        raise UpdateError(f'Installation interrompue : {exc}; restauration : {rollback_errors or "OK"}') from exc
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if relaunch:
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        subprocess.Popen([sys.executable, str(target / 'app.py')], cwd=target,
                         creationflags=flags, close_fds=True)
    return version, backup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--pid', type=int, default=0)
    args = parser.parse_args()
    log = data_dir() / 'updater.log'
    try:
        wait_for_pid(args.pid)
        version, backup = install(args.archive, args.sha256, args.target, relaunch=True)
        with log.open('a', encoding='utf8') as f:
            f.write(f'{datetime.datetime.now().isoformat()} OK v{version} backup={backup}\n')
    except Exception as exc:
        with log.open('a', encoding='utf8') as f:
            f.write(f'{datetime.datetime.now().isoformat()} ERROR {exc!r}\n')
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, str(exc) + '\n\nDétails : ' + str(log),
                                                 'Valheim Stats Tracker - mise à jour', 0x10)
            except Exception:
                pass
        else:
            print(f'Échec de mise à jour : {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
