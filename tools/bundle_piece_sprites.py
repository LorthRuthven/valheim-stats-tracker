"""Images Valheim de constructions issues de la documentation Jötunn figée.

Télécharge seulement les PNG référencés par des prefabs EXACTS du catalogue.
Les sources sont verrouillées sur un commit GitHub et chaque PNG est vérifié
par le SHA-1 Git blob enregistré au manifeste, puis décodé avec Pillow.
Aucune donnée de jeu utilisateur n'est transmise et aucun .fch n'est modifié.
Les images restent © Iron Gate AB / Coffee Stain Publishing.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("piece_image_manifest.json")
BASE = ROOT / "assets"
MAX_IMAGE_BYTES = 180_000
MAX_WORKERS = 12


def load_piece_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("source_repo") != "Valheim-Modding/Jotunn":
        raise RuntimeError("Source de constructions inconnue.")
    revision = data.get("source_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise RuntimeError("Révision de la source non verrouillée.")
    pieces = data.get("pieces", {})
    if not isinstance(pieces, dict) or len(pieces) < 380:
        raise RuntimeError("Manifeste de pièces incomplet.")
    for token, entry in pieces.items():
        if not re.fullmatch(r"\$piece_[A-Za-z0-9_]+", token):
            raise RuntimeError("Identifiant de construction invalide : " + token)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.png", entry.get("file", "")):
            raise RuntimeError("Nom de PNG construction non autorisé : " + token)
        if not re.fullmatch(r"[a-f0-9]{40}", entry.get("git_blob_sha", "")):
            raise RuntimeError("Empreinte Git de l'image absente : " + token)
        if not 100 <= int(entry.get("bytes", 0)) <= MAX_IMAGE_BYTES:
            raise RuntimeError("Taille d'image hors limites : " + token)
    return data


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def sprite_name(token):
    return re.sub(r"[^a-z0-9]", "", token.casefold()) + ".png"


def download_piece(revision, token, entry):
    from PIL import Image, UnidentifiedImageError

    address = (
        "https://raw.githubusercontent.com/Valheim-Modding/Jotunn/"
        + revision + "/Documentation/images/pieces/"
        + urllib.parse.quote(entry["file"], safe="")
    )
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                address,
                headers={"User-Agent": "ValheimStatsTracker/2.7.1 (noncommercial companion; Jotunn docs)",
                         "Accept": "image/png"},
            )
            with urllib.request.urlopen(request, timeout=25) as response:
                # urllib suit les redirections ; ne jamais autoriser un autre hôte.
                if urllib.parse.urlsplit(response.geturl()).hostname not in (
                    "raw.githubusercontent.com",):
                    raise RuntimeError("Redirection hors du dépôt officiel")
                payload = response.read(MAX_IMAGE_BYTES + 1)
            if not 100 <= len(payload) <= MAX_IMAGE_BYTES:
                raise RuntimeError("Image trop volumineuse ou vide : " + token)
            if len(payload) != entry["bytes"] or git_blob_sha(payload) != entry["git_blob_sha"]:
                raise RuntimeError("Intégrité Git différente : " + token)
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Ce fichier n'est pas un PNG : " + token)
            try:
                with Image.open(io.BytesIO(payload)) as img:
                    img.verify()
                with Image.open(io.BytesIO(payload)) as img:
                    if img.format != "PNG" or not (12 <= min(img.size) and max(img.size) <= 512):
                        raise RuntimeError("Dimensions de pièce invalides : " + token)
            except (UnidentifiedImageError, OSError) as exc:
                raise RuntimeError("PNG de pièce illisible : " + token) from exc
            return token, payload
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
    raise RuntimeError("Image inaccessible : " + token + " : " + str(last))


def build_piece_icons(*, fetcher=download_piece):
    manifest = load_piece_manifest()
    catalog_path = BASE / "index.json"
    if not catalog_path.is_file():
        raise RuntimeError("Génère d'abord les assets officiels avec fetch_game_assets.")
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    folder = BASE / "pieces"
    folder.mkdir(parents=True, exist_ok=True)
    finished = {}
    failures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = {pool.submit(fetcher, manifest["source_commit"], token, image): token
                for token, image in manifest["pieces"].items()}
        for future in as_completed(jobs):
            token = jobs[future]
            try:
                image_token, payload = future.result()
                if image_token != token:
                    raise RuntimeError("L'identifiant reçu ne correspond pas au manifeste.")
                filename = sprite_name(token)
                (folder / filename).write_bytes(payload)
                finished[token] = filename
            except (RuntimeError, ValueError, OSError) as exc:
                failures[token] = str(exc)[:250]

    if len(finished) < 380:
        raise RuntimeError(
            f"Images de constructions insuffisantes : {len(finished)}/"
            f"{len(manifest['pieces'])} ; premières erreurs : "
            + repr(list(failures.items())[:5])
        )
    pieces = data.setdefault("pieces", {})
    pieces.update({re.sub(r"[^a-z0-9]", "", token.casefold()): name
                   for token, name in sorted(finished.items())})
    # Sauvegarde atomique : le cache images ne doit jamais invalider l'index.
    pending = catalog_path.with_suffix(".pending")
    try:
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
        pending.replace(catalog_path)
    finally:
        pending.unlink(missing_ok=True)
    audit = {
        "source": "https://github.com/Valheim-Modding/Jotunn",
        "source_commit": manifest["source_commit"],
        "catalogue": len(manifest["pieces"]),
        "included": len(finished),
        "failed": failures,
        "tokens": sorted(finished),
        "copyright": manifest["pixel_copyright"],
    }
    (BASE / "PIECE_ICONS_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (BASE / "ATTRIBUTIONS.txt").open("a", encoding="utf-8") as notes:
        notes.write(
            "\nIllustrations de constructions Valheim (captures du jeu) : "
            "© Iron Gate AB / Coffee Stain Publishing. Documentation Jötunn "
            "(Valheim-Modding/Jotunn), commit " + manifest["source_commit"]
            + ". Usage non officiel, droits des images réservés à leurs auteurs. "
            "Les identifiants sont associés strictement depuis la table des pièces ; "
            "l'image de l'Armor Stand et des plantations ambiguës a été corrigée.\n"
        )
    print(f"CONSTRUCTIONS : {len(finished)}/{len(manifest['pieces'])} "
          f"vraies images de pièces Valheim, {len(failures)} échecs", flush=True)
    return audit


if __name__ == "__main__":
    build_piece_icons()
