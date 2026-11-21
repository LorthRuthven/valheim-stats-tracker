"""Prépare les sprites originaux d'inventaire Valheim pour le bundle Windows.

Source épinglée : dépôt chest-seer, bibliothèque publique d'icônes extraites
du jeu. Seule la sélection nécessaire aux pages est téléchargée.
© Iron Gate AB / Coffee Stain Publishing pour les éléments Valheim.
La licence MIT du code source du dépôt ne modifie pas les droits du jeu.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from game_visuals import required_inventory_items
from collection_catalog import catalogue

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "assets"
REVISION = "c7dec46462fb0a86197442142ab14e1fb943b6b2"
SOURCE = "https://raw.githubusercontent.com/djcdevelopment/chest-seer/" + REVISION
MAX_IMAGE_BYTES = 550_000


def slug(name):
    value = unicodedata.normalize("NFKD", name).casefold()
    return re.sub("[^a-z0-9]+", "", value)


def fetch_bytes(url, max_bytes=MAX_IMAGE_BYTES):
    req = urllib.request.Request(url, headers={
        "User-Agent": "ValheimStatsTracker/2.5 (nonofficial interface)",
        "Accept": "text/plain,image/png,*/*",
    })
    with urllib.request.urlopen(req, timeout=28) as handle:
        data = handle.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError("Fichier de sprites trop volumineux")
        return data


def sprite_index(csv_content):
    rows = csv.DictReader(io.StringIO(csv_content.decode("utf-8-sig")))
    index = {}
    for row in rows:
        key, value = row.get("ItemName"), row.get("SpriteName")
        if key and value and re.fullmatch(r"[A-Za-z0-9_-]{2,96}", value):
            index.setdefault(key, value)
    return index


def matching_catalogue_items(sprite_names, catalogue_rows):
    """Correspondances STRICTES entre prefabs Valheim et objets du CSV.

    Aucun rapprochement flou : un nom de créature ou de pièce construit
    ne devient jamais, par accident, le sprite d'une arme.
    """
    by_slug = {}
    for name in sorted(sprite_names):
        by_slug.setdefault(slug(name), name)
    matched = {}
    for entry in catalogue_rows:
        token = str(entry.get("token", "")).lstrip("$")
        if not (token.startswith("item_") or token.startswith("pickable_")):
            continue
        prefix, raw = token.split("_", 1)
        exact = by_slug.get(slug(raw))
        if exact:
            matched[token] = exact
    return matched


def matching_creature_trophies(sprite_names, catalogue_rows):
    """Vrais trophées correspondant exactement à une créature."""
    by_slug = {slug(name): name for name in sorted(sprite_names)}
    matched = {}
    for entry in catalogue_rows:
        token = str(entry.get("token", "")).lstrip("$")
        if not (token.startswith("enemy_") or token.startswith("animal_")):
            continue
        raw = token.split("_", 1)[-1]
        trophy = by_slug.get(slug("Trophy" + raw))
        if trophy:
            matched[entry["token"]] = trophy
    return matched


def read_icon(item, sprite):
    address = SOURCE + "/sprites/" + urllib.parse.quote(sprite) + ".png"
    payload = fetch_bytes(address)
    if not payload.startswith(bytes.fromhex("89504e470d0a1a0a")):
        raise RuntimeError(f"Le sprite {sprite} n'est pas un PNG authentique")
    try:
        with Image.open(io.BytesIO(payload)) as image:
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            if image.size[0] < 24 or image.size[1] < 24:
                raise RuntimeError(f"Sprite {sprite} trop petit")
            if image.size[0] > 512 or image.size[1] > 512:
                raise RuntimeError(f"Sprite {sprite} trop grand")
    except (UnidentifiedImageError, OSError) as exc:
        raise RuntimeError(f"Sprite corrompu {sprite}") from exc
    return item, sprite, payload


def build_inventory_icons():
    catalog_file = BASE / "index.json"
    if not catalog_file.is_file():
        raise RuntimeError("L'index Steam doit être généré avant les objets Valheim")
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    must_have = required_inventory_items()
    csv_bytes = fetch_bytes(SOURCE + "/items2sprites.csv", 300_000)
    entries = sprite_index(csv_bytes)
    missing = sorted(must_have - set(entries))
    if missing:
        raise RuntimeError(f"Correspondances absentes de la source : {missing}")
    entries_list = catalogue()
    matches = matching_catalogue_items(entries, entries_list)
    trophies = matching_creature_trophies(entries, entries_list)
    names = set(must_have) | set(matches.values()) | set(trophies.values())
    print(
        f"CATALOGUE : {len(matches)} sprites d'objets exacts, "
        f"{len(trophies)} trophées liés aux créatures, "
        f"{len(names)} images uniques à intégrer",
        flush=True,
    )

    root = BASE / "items"
    root.mkdir(parents=True, exist_ok=True)
    result = {}
    failed_optional = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        tasks = {pool.submit(read_icon, item, entries[item]): item for item in sorted(names)}
        for future in as_completed(tasks):
            item = tasks[future]
            try:
                _item, source_sprite, data = future.result()
            except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
                if item in must_have:
                    raise RuntimeError(
                        "Sprite Valheim obligatoire non disponible : " + item
                    ) from error
                failed_optional[item] = str(error)[:180]
                continue
            alias = slug(item)
            filename = "jeu_" + alias + ".png"
            (root / filename).write_bytes(data)
            result[alias] = filename
            print(f"SPRITE VALHEIM {item} -> {source_sprite}, {len(data)} octets",
                  flush=True)
    if not all(slug(item) in result for item in must_have):
        raise RuntimeError("Des icônes requises manquent dans le pack")
    # L'index Steam et les petites ressources officielles déjà présentes
    # restent utilisables ; le jeu authentique est prioritaire pour nos alias.
    catalog.setdefault("items", {}).update(result)
    catalog_file.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    attribution = BASE / "ATTRIBUTIONS.txt"
    with attribution.open("a", encoding="utf-8") as notes:
        notes.write(
            "\nIcônes d'inventaire Valheim (PNG issus du jeu) : "
            "© Iron Gate AB / Coffee Stain Publishing.\n"
            "Bibliothèque technique de référence : "
            "https://github.com/djcdevelopment/chest-seer\n"
            f"Révision épinglée : {REVISION}\n"
            "Extrait limité aux sprites réellement utilisés dans les pages ; "
            "companion non officiel. MIT (code hôte), "
            "droits des sprites réservés à leurs auteurs originaux.\n"
        )
    audit = {
        "source_repo": "djcdevelopment/chest-seer",
        "source_revision": REVISION,
        "selected_icons": len(result),
        "catalogue_exact_matches": sum(
            1 for item in matches.values() if slug(item) in result
        ),
        "catalogue_total": len(catalogue()),
        "catalogue_tokens_matched": sorted(
            token for token, item in matches.items() if slug(item) in result
        ),
        "creature_trophies": sorted(
            token for token, item in trophies.items() if slug(item) in result
        ),
        "catalogue_optional_unavailable": failed_optional,
        "sha256": {name: hashlib.sha256((root / filename).read_bytes()).hexdigest()
                   for name, filename in sorted(result.items())},
    }
    (BASE / "GAME_ICONS_AUDIT.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"BILAN : {len(result)} véritables icônes d'inventaire Valheim dans le bundle, "
        f"{audit['catalogue_exact_matches']} entrées de l'encyclopédie illustrées "
        f"({len(failed_optional)} sprites supplémentaires indisponibles)",
        flush=True,
    )
    return result


if __name__ == "__main__":
    build_inventory_icons()
