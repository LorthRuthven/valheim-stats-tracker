"""Construit un ZIP d'application compatible updater.py + update.json GitHub."""
import argparse
import base64
import zlib
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('app.py', 'updater.py', 'update_worker.py', 'valheim_reader.py',
         'Lancer_Tracker.bat', 'README.txt', 'version.json', 'manifest.example.json')



def embedded_reader(allow_test_fixture=False):
    """Embarque la même localisation qu'en développement dans le ZIP historique."""
    reader = (ROOT / 'valheim_reader.py').read_text(encoding='utf-8')
    marker = 'from localization_fr import localized_name'
    if reader.count(marker) != 1:
        raise ValueError('Import de localisation introuvable ou dupliqué')
    localization = (ROOT / 'localization_fr.py').read_text(encoding='utf-8')
    localization = localization.replace('from __future__ import annotations\n', '')
    if localization.count('_FR_PACKED_NAMES = None') != 1:
        raise ValueError('Variable de données françaises introuvable')
    dictionary = (ROOT / 'fr_names.json').read_bytes()
    data = json.loads(dictionary.decode('utf-8'))
    if not isinstance(data, dict) or (len(data) < 100 and not allow_test_fixture):
        raise ValueError('Dictionnaire français incomplet : construction refusée')
    payload = base64.b64encode(zlib.compress(dictionary, level=9)).decode('ascii')
    localization = localization.replace('_FR_PACKED_NAMES = None', f'_FR_PACKED_NAMES = {payload!r}')
    return reader.replace(marker, localization).encode('utf-8')


def build(tag, repo, output, allow_test_fixture=False):
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
            if name_in == 'valheim_reader.py':
                z.writestr('Valheim_Stats_Tracker/' + name_in, embedded_reader(allow_test_fixture))
            else:
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
