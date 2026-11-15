"""Images de complément depuis le wiki communautaire Valheim (V2.3.1).

- La priorité reste aux sprites extraits localement : ce module ne les touche jamais.
- Requête MediaWiki exacte, sans recherche floue ni renommage hasardeux.
- Les images téléchargées ne sont pas redistribuées : cache utilisateur seulement.
- L'attribution conserve URL de la page et URL de l'image pour chaque entrée.
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
from datetime import datetime, timezone
from pathlib import Path

MAX_DOWNLOAD = 5_000_000
MAX_DIMENSION = 4096
MAX_API_BYTES = 512_000
RETRY_AFTER = 6 * 3600

WIKI_API = (
    "https://valheim.wiki/api.php",
    "https://valheim.wiki/w/api.php",
    "https://valheim.weirdgloop.org/api.php",
    "https://valheim.weirdgloop.org/w/api.php",
)
ALLOWED_HOSTS = frozenset((
    "valheim.wiki", "valheim.weirdgloop.org",
    "upload.wikimedia.org", "static.wikia.nocookie.net",
))
USER_AGENT = "ValheimStatsTracker/2.3.1 (personal image cache; MediaWiki API)"

# Correspondances explicitement contrôlées. Pas de supposition à partir du français.
WIKI_NAMES = {
    "greydwarfbrute": "Greydwarf Brute",
    "greydwarfshaman": "Greydwarf Shaman",
    "greydwarf": "Greydwarf",
    "greyling": "Greyling",
    "boar": "Boar",
    "abomination": "Abomination",
    "asksvin": "Asksvin",
    "skeleton": "Skeleton",
    "draugr": "Draugr",
    "troll": "Troll",
    "neck": "Neck",
    "charred_archer": "Charred Archer",
    "charred_melee": "Charred Warrior",
    "charred_mage": "Charred Warlock",
    "sword_iron": "Iron sword",
    "sword_bronze": "Bronze sword",
    "sword_silver": "Silver sword",
    "sword_mistwalker": "Mistwalker",
    "wood": "Wood",
    "stone": "Stone",
    "resin": "Resin",
    "honey": "Honey",
}


class WikiImageError(Exception):
    """Problème non critique : l'application continue sans image."""


def _allowed_https(url, *, host_list=ALLOWED_HOSTS):
    parsed = urllib.parse.urlsplit(str(url))
    return (parsed.scheme == "https" and (parsed.hostname or "").lower() in host_list
            and not parsed.username and not parsed.password and parsed.port in (None, 443))


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_https(newurl):
            raise WikiImageError("Redirection image hors domaines autorisés")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    return urllib.request.build_opener(_SafeRedirects())


def wiki_title(token):
    """Retourne un titre anglais exact ou None si le prefab est ambigu."""
    if not isinstance(token, str):
        return None
    raw = token.strip().lstrip("$")
    match = re.match(r"^(enemy|animal|item|piece|pickable)_([a-z0-9_]+)$", raw, re.I)
    if not match:
        return None
    group, name = match.groups()
    name = name.lower()
    if name in WIKI_NAMES:
        return WIKI_NAMES[name]
    # Constructions à noms internes opaques : ne jamais confondre deux pages.
    if group.lower() == "piece":
        return None
    if not re.fullmatch(r"[a-z0-9_]{3,70}", name):
        return None
    # Correspondance stricte, sans déduire de noms localisés ni inverser les mots.
    # Le wiki peut ne pas avoir de page, auquel cas on n'ajoute aucune image.
    return name.replace("_", " ").title()


def _key(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]


def _read_response(opener, url, limit):
    if not _allowed_https(url):
        raise WikiImageError("URL wiki non autorisée")
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,image/*"}
    )
    with opener.open(request, timeout=12) as response:
        final = response.geturl() if hasattr(response, "geturl") else url
        if not _allowed_https(final):
            raise WikiImageError("Réponse provenant d'un domaine non approuvé")
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise WikiImageError("Fichier wiki trop volumineux")
        return payload


def _same_title(candidate, expected):
    return str(candidate).replace("_", " ").casefold().strip() == expected.casefold().strip()


def _lookup_page(title, opener):
    """Résout uniquement le titre exact et son image principale MediaWiki."""
    last_error = None
    for endpoint in WIKI_API:
        query = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": "2",
            "prop": "pageimages|info", "inprop": "url", "titles": title,
            "piprop": "thumbnail", "pithumbsize": "420", "pilicense": "any",
        })
        try:
            raw = _read_response(opener, endpoint + "?" + query, MAX_API_BYTES)
            result = json.loads(raw.decode("utf-8"))
            pages = result.get("query", {}).get("pages", [])
            if not isinstance(pages, list) or not pages:
                continue
            page = pages[0]
            if not isinstance(page, dict) or "missing" in page:
                continue
            if int(page.get("ns", -1)) != 0:
                continue
            if not _same_title(page.get("title", ""), title):
                continue
            image = page.get("thumbnail", {}).get("source", "")
            if not _allowed_https(image):
                continue
            link = page.get("fullurl", "")
            if not _allowed_https(link):
                # La page elle-même a été confirmée par la réponse MediaWiki.
                link = "https://valheim.wiki/w/" + urllib.parse.quote(
                    page["title"].replace(" ", "_"), safe="_")
            return {"title": page["title"], "page_url": link, "image_url": image,
                    "wiki_name": "Valheim Wiki"}
        except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError,
                WikiImageError) as error:
            last_error = error
    if last_error:
        raise WikiImageError("Wiki inaccessible ou image absente : " + str(last_error)) from last_error
    return None


class WikiImageCache:
    def __init__(self, directory=None):
        if directory is None:
            from v2_core import app_dir
            directory = app_dir() / "wiki_cache"
        self.directory = Path(directory)
        self._client = _opener()

    def _paths(self, token):
        stem = _key(token)
        return (self.directory / (stem + ".png"),
                self.directory / (stem + ".json"),
                self.directory / (stem + ".miss.json"))

    def cached_image(self, token):
        image, meta, _ = self._paths(token)
        if not image.is_file() or not meta.is_file():
            return None
        try:
            contents = json.loads(meta.read_text(encoding="utf-8"))
            if contents.get("token") == token and image.stat().st_size > 100:
                return image
        except (OSError, ValueError, TypeError):
            pass
        return None

    def source(self, token):
        if self.cached_image(token) is None:
            return None
        _, meta, _ = self._paths(token)
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            if _allowed_https(data.get("page_url", "")):
                return data
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _missed_recently(self, token):
        *_, miss = self._paths(token)
        try:
            info = json.loads(miss.read_text(encoding="utf-8"))
            return (time.time() - float(info["time"])) < RETRY_AFTER
        except (OSError, KeyError, ValueError, TypeError):
            return False

    def fetch(self, token, *, force=False):
        """Télécharge une image unique. À appeler uniquement hors thread Qt UI."""
        existing = self.cached_image(token)
        if existing is not None:
            return existing
        if not force and self._missed_recently(token):
            return None
        title = wiki_title(token)
        if title is None:
            return None
        image, meta, miss = self._paths(token)
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            info = _lookup_page(title, self._client)
            if not info:
                raise WikiImageError("Aucune image principale pour la page exacte " + title)
            raw = _read_response(self._client, info["image_url"], MAX_DOWNLOAD)
            from PIL import Image, UnidentifiedImageError
            from PIL import ImageOps
            try:
                with Image.open(io.BytesIO(raw)) as picture:
                    width, height = picture.size
                    if not (12 <= width <= MAX_DIMENSION and 12 <= height <= MAX_DIMENSION):
                        raise WikiImageError("Dimensions de l'image non acceptées")
                    output = ImageOps.exif_transpose(picture).convert("RGBA")
                    output.thumbnail((420, 420), Image.Resampling.LANCZOS)
                    stage = image.with_suffix(".pending")
                    try:
                        output.save(stage, format="PNG", optimize=True)
                        stage.replace(image)
                    finally:
                        stage.unlink(missing_ok=True)
            except (UnidentifiedImageError, ValueError, OSError) as exc:
                raise WikiImageError("La réponse wiki n'est pas une image valide") from exc
            attribution = {
                "token": token, "wiki_title": info["title"], "page_url": info["page_url"],
                "image_url": info["image_url"], "source": info["wiki_name"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "note": "Image communautaire ; vérifier les droits et l'attribution sur la page source.",
            }
            temporary = meta.with_suffix(".tmp")
            try:
                temporary.write_text(json.dumps(attribution, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                temporary.replace(meta)
            finally:
                temporary.unlink(missing_ok=True)
            miss.unlink(missing_ok=True)
            return image
        except (OSError, WikiImageError, urllib.error.URLError, ValueError) as exc:
            try:
                miss.write_text(json.dumps({"token": token, "time": time.time(),
                                            "reason": str(exc)[:300]},
                                           ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            return None

    def clear(self):
        """Ne touche jamais aux sprites du jeu dans game_icons."""
        if not self.directory.is_dir():
            return 0
        deleted = 0
        for entry in self.directory.iterdir():
            if (entry.is_file() and re.fullmatch(r"[0-9a-f]{32}\.(png|json|miss\.json)", entry.name)):
                try:
                    entry.unlink()
                    deleted += 1
                except OSError:
                    pass
        return deleted

    def count(self):
        return sum(1 for entry in self.directory.glob("*.png")) if self.directory.is_dir() else 0
