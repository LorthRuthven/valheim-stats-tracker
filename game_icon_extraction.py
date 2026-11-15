"""Extraction facultative des véritables sprites du Valheim installé (sans mod).

Par rapport à la V2.2.2 :
- vérification du dossier et du fichier valheim.exe ;
- lecture des Sprite ET Texture2D éligibles, ainsi que des archives *.assets ;
- compatibilité UnityPy.parse_as_object et UnityPy.read ;
- journal JSON explicite et aucune fausse réussite "0 icône" ;
- association des variantes icon_*, item_* aux noms demandés par l'interface.

Ne modifie jamais le jeu ni les sauvegardes .fch.
"""
from __future__ import annotations

import gc
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

MAX_FILES = 5000
MAX_ERRORS = 35
MAX_IMAGE_SIDE = 4096
MAX_IMAGES = 8000


class IconExtractionError(RuntimeError):
    """L'extraction n'a rien pu produire. Un journal détaillé reste disponible."""


def icon_key(text):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', str(text)).casefold())


def icon_aliases(name):
    """Ne créer que des alias déductibles du nom réel du sprite."""
    raw = str(name)
    variants = {icon_key(raw)}
    stripped = raw
    for _ in range(3):
        old = stripped
        stripped = re.sub(r'^(?:icon|icons|inventory|sprite|sprites|texture|tex|item|ui)[_\s.-]+', '', stripped, flags=re.I)
        if stripped == old:
            break
        variants.add(icon_key(stripped))
    return {item for item in variants if len(item) >= 3}


def bundle_paths(directory):
    root = Path(directory).expanduser()
    if not (root / 'valheim.exe').is_file():
        raise ValueError(
            'Sélectionne le dossier contenant valheim.exe, et non valheim_Data ni steamapps.'
        )
    data = root / 'valheim_Data'
    if not data.is_dir():
        raise ValueError('valheim_Data est absent du dossier sélectionné.')
    folder = data / 'StreamingAssets' / 'SoftRef' / 'Bundles'
    paths = []
    if folder.is_dir():
        paths.extend(path for path in folder.iterdir() if path.is_file())
    # Les installations Unity peuvent aussi conserver des textures ici.
    paths.extend(p for p in data.glob('*.assets') if p.is_file())
    paths.extend(p for p in (data / 'Resources').glob('*.assets') if p.is_file()
                 ) if (data / 'Resources').is_dir() else None
    result = sorted(set(paths), key=lambda p: str(p).casefold())
    if not result:
        raise ValueError(
            'Aucun bundle Unity ou fichier .assets trouvé dans valheim_Data. '
            'Vérifie les fichiers du jeu via Steam.'
        )
    if len(result) > MAX_FILES:
        raise ValueError('Trop de fichiers Unity détectés ; extraction interrompue.')
    return result


def _read_unity_object(obj):
    # Les éditions récentes de UnityPy privilégient parse_as_object().
    method = getattr(obj, 'parse_as_object', None)
    if callable(method):
        return method()
    return obj.read()


def _is_icon_texture(name):
    # Texture2D est un recours : ne pas confondre paysages et icônes.
    name = str(name).casefold()
    if icon_key(name) in ('icon', 'sprite', 'texture', 'default', 'white'):
        return False
    return bool(re.search(
        r'(^|[_\s.-])(icon|icons|inventory|item|items|ui|trophy|food|skill)([_\s.-]|$)',
        name
    ))


def verify_fmod_runtime(root=None):
    """Controle la DLL native requise par UnityPy dans l'application Windows.

    root explicite permet les tests hors Windows. En usage Python non compile,
    fmod_toolkit gere lui-meme sa bibliotheque native.
    """
    if root is None:
        if os.name != 'nt' or not getattr(sys, 'frozen', False):
            return None
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    dll = Path(root) / 'fmod_toolkit' / 'libfmod' / 'Windows' / 'x64' / 'fmod.dll'
    if not dll.is_file():
        raise IconExtractionError(
            'Bibliotheque native fmod.dll introuvable dans le programme Windows : '
            f'{dll}. Reinstalle la version Windows complete du tracker, '
            'sans copier uniquement ValheimStatsTracker.exe.'
        )
    return dll


def extract_owned_icons(game_directory, target_directory,
                        notify=lambda n, total, name: None,
                        maximum=MAX_IMAGES, unity_loader=None):
    """Retourne le nombre de sprites locaux exploitables (nouveaux + existants).

    En cas de zéro résultat, lève IconExtractionError APRÈS avoir écrit le rapport.
    unity_loader permet de tester sans aucun fichier du jeu ni réseau.
    """
    if unity_loader is None:
        try:
            import UnityPy
        except (ImportError, ModuleNotFoundError) as exc:
            raise IconExtractionError('UnityPy n’est pas disponible : ' + str(exc)) from exc
        unity_loader = UnityPy.load
    # Evite de relire 802 bundles en cas de paquet Windows incomplet.
    verify_fmod_runtime()
    from PIL import Image

    paths = bundle_paths(game_directory)
    dest = Path(target_directory)
    dest.mkdir(parents=True, exist_ok=True)
    report_path = dest / 'extraction-report.json'
    counts = Counter()
    counts['files_found'] = len(paths)
    errors = []
    examples = []
    aliases = {}
    used = set()
    started = datetime.now().astimezone().isoformat(timespec='seconds')

    def failure(reason, where):
        counts['errors'] += 1
        if len(errors) < MAX_ERRORS:
            errors.append({'source': str(where), 'reason': str(reason)[:400]})

    def persist():
        data = {
            'started': started,
            'game_directory': str(Path(game_directory).resolve()),
            'files_found': counts['files_found'],
            'files_read': counts['files_read'],
            'sprites_found': counts['sprites_found'],
            'textures_found': counts['textures_found'],
            'images_decoded': counts['images_decoded'],
            'images_written': counts['images_written'],
            'images_existing': counts['images_existing'],
            'images_rejected': counts['images_rejected'],
            'errors_total': counts['errors'],
            'examples': examples,
            'errors': errors,
        }
        temporary = report_path.with_suffix('.pending')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, report_path)
        (dest / 'index.json').write_text(json.dumps({'aliases': aliases}, ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
        return data

    limit = max(1, min(MAX_IMAGES, int(maximum or MAX_IMAGES)))
    total = len(paths)
    for index, path in enumerate(paths):
        counts['files_read'] += 1
        try:
            environment = unity_loader(str(path))
            for obj in environment.objects:
                kind = getattr(getattr(obj, 'type', None), 'name', '')
                if kind not in ('Sprite', 'Texture2D'):
                    continue
                counts['sprites_found' if kind == 'Sprite' else 'textures_found'] += 1
                if len(used) >= limit:
                    break
                try:
                    resource = _read_unity_object(obj)
                    name = getattr(resource, 'm_Name', None) or getattr(resource, 'name', '')
                    canonical = icon_key(name)
                    if not canonical or len(canonical) > 110 or canonical in ('icon', 'sprite', 'texture'):
                        counts['images_rejected'] += 1
                        continue
                    if kind == 'Texture2D' and not _is_icon_texture(name):
                        counts['images_rejected'] += 1
                        continue
                    picture = getattr(resource, 'image', None)
                    if picture is None or not hasattr(picture, 'size'):
                        counts['images_rejected'] += 1
                        continue
                    if min(picture.size) < 12 or max(picture.size) > MAX_IMAGE_SIDE:
                        counts['images_rejected'] += 1
                        continue
                    counts['images_decoded'] += 1
                    if canonical in used:
                        continue
                    filename = canonical + '.png'
                    final = dest / filename
                    if not final.is_file():
                        temporary = dest / (canonical + '.pending')
                        try:
                            picture = picture.copy()
                            picture.thumbnail((256, 256), Image.Resampling.LANCZOS)
                            picture.convert('RGBA').save(temporary, format='PNG', optimize=True)
                            os.replace(temporary, final)
                        finally:
                            temporary.unlink(missing_ok=True)
                        counts['images_written'] += 1
                    else:
                        counts['images_existing'] += 1
                    used.add(canonical)
                    if len(examples) < 16:
                        examples.append({'name': str(name), 'kind': kind, 'file': filename})
                    for key in icon_aliases(name):
                        aliases.setdefault(key, filename)
                except Exception as exc:
                    failure(type(exc).__name__ + ': ' + str(exc), path.name + ':' + kind)
            del environment
        except Exception as exc:
            failure(type(exc).__name__ + ': ' + str(exc), path.name)
        if index % 8 == 0 or index == total - 1:
            notify(index + 1, total, path.name)
        if index % 40 == 0:
            gc.collect()
    state = persist()
    found = counts['images_written'] + counts['images_existing']
    if found == 0:
        raise IconExtractionError(
            f"0 icône exploitable après {counts['files_read']} fichiers analysés "
            f"({counts['sprites_found']} sprites, {counts['textures_found']} textures ; "
            f"{counts['errors']} erreurs). Rapport : {report_path}"
        )
    return found
