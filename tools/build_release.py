"""Construit un ZIP d'application compatible updater.py + update.json GitHub."""
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('app.py', 'updater.py', 'update_worker.py', 'valheim_reader.py',
         'Lancer_Tracker.bat', 'README.txt', 'version.json', 'manifest.example.json',
         'localization_fr.py', 'fr_names.json')


def build(tag, repo, output):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',tag):
        raise ValueError('Tag attendu : v1.2.3')
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9._-]+',repo):
        raise ValueError('Dépôt attendu : utilisateur/nom')
    expected=tag[1:]
    version=json.loads((ROOT/'version.json').read_text(encoding='utf8'))['version']
    if version!=expected:
        raise ValueError(f'Le tag {tag} ne correspond pas à version.json ({version})')
    output.mkdir(parents=True,exist_ok=True)
    name=f'Valheim_Stats_Tracker_{tag}.zip'
    target=output/name
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name_in in FILES:
            file=ROOT/name_in
            if not file.is_file(): raise FileNotFoundError(name_in)
            z.write(file,arcname='Valheim_Stats_Tracker/'+name_in)
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    notes=(ROOT/'RELEASE_NOTES.md').read_text(encoding='utf8').strip()[:3000]
    manifest={'version':version,
              'url':f'https://github.com/{repo}/releases/download/{tag}/{name}',
              'sha256':sha,'notes':notes}
    (output/'update.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Archive:',target,'SHA-256:',sha,'Manifeste:',output/'update.json')
    return target, output/'update.json'

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--tag',required=True)
    p.add_argument('--repo',required=True)
    p.add_argument('--output',default='dist')
    args=p.parse_args()
    build(args.tag,args.repo,Path(args.output).resolve())
