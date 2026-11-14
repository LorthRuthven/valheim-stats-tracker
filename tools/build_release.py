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



def embedded_reader():
    """Intègre les traductions dans le lecteur, sans fichier additionnel dans le ZIP."""
    reader = (ROOT / 'valheim_reader.py').read_text(encoding='utf-8')
    marker = 'from localization_fr import localized_name'
    if reader.count(marker) != 1:
        raise ValueError('Import de localisation introuvable dans le lecteur')
    dictionary = (ROOT / 'fr_names.json').read_bytes()
    payload = base64.b64encode(zlib.compress(dictionary, level=9)).decode('ascii')
    replacement = (
        'import base64 as _fr_b64\n'
        'import zlib as _fr_zlib\n'
        'import json as _fr_json\n'
        'import re as _fr_re\n'
        'import html as _fr_html\n'
        'from functools import lru_cache as _fr_cache\n'
        f'_FR_PAYLOAD = {payload!r}\n'
        '@_fr_cache(maxsize=1)\n'
        'def french_names():\n'
        '    raw = _fr_zlib.decompress(_fr_b64.b64decode(_FR_PAYLOAD))\n'
        '    data = _fr_json.loads(raw.decode("utf-8"))\n'
        '    result = {}\n'
        '    for key, value in data.items():\n'
        '        if isinstance(key, str) and key.startswith(chr(36)) and isinstance(value, str):\n'
        '            clean = _fr_html.unescape(_fr_re.sub(r"</?(?:color|b|i|size)(?:=[^>]*)?>", "", value, flags=_fr_re.I)).replace(chr(160), " ").strip()\n'
        '            if clean and not clean.startswith(chr(36)) and len(clean) <= 140:\n'
        '                result[key.casefold()] = clean\n'
        '    return result\n'
        'def localized_name(token, fallback=None):\n'
        '    if not isinstance(token, str):\n'
        '        return fallback or str(token)\n'
        '    return french_names().get(token.casefold(), fallback if fallback is not None else token)\n'
    )
    return reader.replace(marker, replacement).encode('utf-8')



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
            if name_in == 'valheim_reader.py':
                z.writestr('Valheim_Stats_Tracker/' + name_in, embedded_reader())
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
