"""Pack complémentaire Jötunn des vrais visuels d'objets, créatures et monde.

Source figée par commit GitHub + SHA Git blob de chaque image. Les captures
Valheim restent © Iron Gate AB / Coffee Stain Publishing. Pas de téléchargement
dans l'application, pas d'accès aux fichiers .fch.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("catalogue_image_manifest.json")
ASSETS = ROOT / "assets"
KINDS = ("items", "characters", "prefabs", "world")
SOURCES = {"items": "items", "characters": "characters",
           "prefabs": "prefabs", "world": "pieces"}
MAX_SIZE = 90_000
WORKERS = 24


def slug(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def pack_filename(name, hash_):
    return "j_" + slug(name.removesuffix(".png")) + "_" + hash_[:10] + ".png"


def git_blob_hash(payload):
    return hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") +
                        b"\0" + payload).hexdigest()


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("source_repo") != "Valheim-Modding/Jotunn" or not re.fullmatch(
            r"[a-f0-9]{40}", data.get("source_commit", "")):
        raise RuntimeError("Source Jötunn non reconnue ou commit non verrouillé")
    for kind in KINDS:
        files = data.get("images", {}).get(kind, {})
        if not isinstance(files, dict) or len(files) < (3 if kind == "world" else 100):
            raise RuntimeError("Manifeste incomplet : " + kind)
        for name, meta in files.items():
            if not re.fullmatch(r"[a-zA-Z0-9_. -]+\.png", name):
                raise RuntimeError("Nom de fichier image invalide : " + name)
            if (not re.fullmatch(r"[a-f0-9]{40}", meta.get("sha", ""))
                    or not 100 <= int(meta.get("size", 0)) <= MAX_SIZE):
                raise RuntimeError("Empreinte ou taille de fichier invalide : " + name)
    for kind in ("item_token_aliases", "creature_token_aliases", "world_token_aliases"):
        aliases = data.get(kind, {})
        source = {"item_token_aliases": "items",
                  "creature_token_aliases": "characters",
                  "world_token_aliases": "world"}[kind]
        for token, file in aliases.items():
            if (not token.startswith("$") or file not in data["images"][source]):
                raise RuntimeError("Alias non vérifié : " + token)
    return data


def _download(revision, kind, filename, meta):
    from PIL import Image, UnidentifiedImageError

    url = ("https://raw.githubusercontent.com/Valheim-Modding/Jotunn/" +
           revision + "/Documentation/images/" + SOURCES[kind] + "/" +
           urllib.parse.quote(filename, safe=""))
    previous = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url, headers={
                    "User-Agent": "ValheimStatsTracker/2.7.2 (Jotunn image cache builder)",
                    "Accept": "image/png"})
            with urllib.request.urlopen(request, timeout=30) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "raw.githubusercontent.com":
                    raise RuntimeError("Redirection image non autorisée")
                data = response.read(MAX_SIZE + 1)
            if len(data) != meta["size"] or git_blob_hash(data) != meta["sha"]:
                raise RuntimeError("Empreinte Git invalide : " + filename)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Format PNG inattendu : " + filename)
            try:
                with Image.open(io.BytesIO(data)) as image:
                    image.verify()
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != "PNG" or not (12 <= min(image.size) and max(image.size) <= 512):
                        raise RuntimeError("Dimensions ou format invalides : " + filename)
            except (UnidentifiedImageError, ValueError, OSError) as error:
                raise RuntimeError("Image illisible : " + filename) from error
            return kind, filename, data
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            previous = error
            if attempt < 3:
                time.sleep((attempt + 1) * 0.6)
    raise RuntimeError("Échec de téléchargement : " + filename + " : " + str(previous))


def build_catalogue_images(*, downloader=_download):
    source = load_manifest()
    index_path = ASSETS / "index.json"
    if not index_path.is_file():
        raise RuntimeError("assets/index.json manque. Lancer fetch_game_assets d'abord.")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    revision = source["source_commit"]
    pending_files = []
    for kind in KINDS:
        folder = ASSETS / ("jotunn_" + kind)
        folder.mkdir(parents=True, exist_ok=True)
        for filename, meta in source["images"][kind].items():
            pending_files.append((kind, filename, meta))
    unique = sum(len(source["images"][kind]) for kind in KINDS)
    if len(pending_files) != unique or unique < 1500:
        raise RuntimeError("Le catalogue d'images Jötunn est incomplet")
    fulfilled = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        tasks = {pool.submit(downloader, revision, kind, filename, meta):
                 (kind, filename, meta) for kind, filename, meta in pending_files}
        for done in as_completed(tasks):
            kind, filename, meta = tasks[done]
            try:
                returned_kind, returned_name, data = done.result()
                if (returned_kind, returned_name) != (kind, filename):
                    raise RuntimeError("Échange non autorisé d'image")
                output_name = pack_filename(filename, meta["sha"])
                path = ASSETS / ("jotunn_" + kind) / output_name
                path.write_bytes(data)
                fulfilled[(kind, filename)] = output_name
            except (RuntimeError, ValueError, OSError) as error:
                errors[kind + ":" + filename] = str(error)[:220]
    if errors or len(fulfilled) != unique:
        raise RuntimeError(
            "Pack Jötunn incomplet : " + str(len(fulfilled)) + "/" +
            str(unique) + " ; erreurs : " + repr(list(errors.items())[:12])
        )
    for kind in KINDS:
        keys = Counter(slug(filename.removesuffix(".png"))
                       for filename in source["images"][kind])
        result = {}
        for filename in source["images"][kind]:
            key = slug(filename.removesuffix(".png"))
            if keys[key] == 1:
                result[key] = fulfilled[(kind, filename)]
        aliases = {"items": "item_token_aliases",
                   "characters": "creature_token_aliases",
                   "world": "world_token_aliases"}.get(kind)
        if aliases:
            for token, filename in source[aliases].items():
                result[slug(token)] = fulfilled[(kind, filename)]
        index["jotunn_" + kind] = result
    stage = index_path.with_suffix(".pending")
    try:
        stage.write_text(json.dumps(index, ensure_ascii=False, indent=2)+"\n",
                         encoding="utf-8")
        stage.replace(index_path)
    finally:
        stage.unlink(missing_ok=True)
    audit = {"source_commit":revision, "counts":{k:len(source["images"][k]) for k in KINDS},
             "total":len(fulfilled), "aliases":{
                 "items":len(source["item_token_aliases"]),
                 "characters":len(source["creature_token_aliases"]),
                 "world":len(source["world_token_aliases"])},
             "errors":errors,
             "source":"https://github.com/Valheim-Modding/Jotunn"}
    (ASSETS/"CATALOGUE_ATLAS_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    with (ASSETS/"ATTRIBUTIONS.txt").open("a", encoding="utf-8") as notes:
        notes.write(
            "\nCatalogue de visuels Valheim : © Iron Gate AB / Coffee Stain "
            "Publishing. Documentation Jötunn © ses contributeurs "
            "(Valheim-Modding/Jotunn) au commit " + revision +
            ". Images authentiques des objets, créatures et prefabs, sans "
            "imagerie synthétique. Usage non officiel ; droits réservés.\n")
    print(f"ATLAS JÖTUNN : {len(fulfilled)}/{unique} images authentiques ; "
          f"objets={audit['counts']['items']} ; "
          f"créatures={audit['counts']['characters']} ; "
          f"monde={audit['counts']['prefabs']} ; "
          f"outils={audit['counts']['world']}",flush=True)
    return audit


if __name__ == "__main__":
    build_catalogue_images()
