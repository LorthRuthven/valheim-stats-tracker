"""Extraction locale, facultative, des véritables icônes Valheim (sans mod).

Ne télécharge rien et n'écrit jamais dans le dossier du jeu. Les sprites sont
copiés depuis une installation légalement présente sur l'ordinateur de l'utilisateur
vers %LOCALAPPDATA%/ValheimStatsTracker/game_icons.
"""
from __future__ import annotations

import gc
import os
import re
import tempfile
import unicodedata
from pathlib import Path

def icon_key(text):
    return re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',str(text)).casefold())

def bundle_paths(directory):
    root=Path(directory)
    base=root/'valheim_Data'/'StreamingAssets'/'SoftRef'/'Bundles'
    if not base.is_dir():
        raise ValueError('Dossier de Valheim introuvable : sélectionne le dossier contenant valheim.exe.')
    return sorted(path for path in base.iterdir() if path.is_file())

def extract_owned_icons(game_directory, target_directory, notify=lambda n,total,name:None,
                        maximum=5000):
    try:
        import UnityPy
    except ImportError as exc:
        raise RuntimeError('Le composant UnityPy n’est pas disponible dans cette édition.') from exc
    from PIL import Image
    paths=bundle_paths(game_directory)
    dest=Path(target_directory)
    dest.mkdir(parents=True,exist_ok=True)
    added=set()
    total=len(paths)
    if not total:
        raise ValueError('Aucun asset bundle trouvé dans cette installation.')
    for index,path in enumerate(paths):
        try:
            env=UnityPy.load(str(path))
            for obj in env.objects:
                if obj.type.name!='Sprite':continue
                try:
                    sprite=obj.read()
                    name=getattr(sprite,'m_Name','')
                    code=icon_key(name)
                    if not code or len(code)>95 or code in added:continue
                    if maximum and len(added)>=maximum:break
                    image=sprite.image
                    if image is None:continue
                    if image.width<8 or image.height<8:continue
                    image.thumbnail((196,196),Image.Resampling.LANCZOS)
                    # Destination uniquement locale, pas de redistribution des ressources du jeu.
                    target=dest/(code+'.png')
                    if target.exists():
                        added.add(code)
                        continue
                    temporary=dest/(code+'.pending')
                    image.convert('RGBA').save(temporary,format='PNG',optimize=True)
                    os.replace(temporary,target)
                    added.add(code)
                except (ValueError,RuntimeError,OSError,AttributeError):
                    continue
            del env
        except (OSError,ValueError,RuntimeError):
            pass
        if index%8==0 or index==total-1:
            notify(index+1,total,path.name)
        if index%48==0:
            gc.collect()
    return len(added)
