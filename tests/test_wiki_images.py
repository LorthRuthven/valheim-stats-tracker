"""Wiki Valheim V2.3.1 : tests deterministes sans connexion reseau."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from wiki_images import (
    WikiImageCache, _allowed_https, _lookup_page, _same_title, wiki_title,
)

try:
    from PIL import Image
except ImportError:
    Image = None


class _Response:
    def __init__(self, url, body):
        self.url = url
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


class _MediaWikiOpener:
    def __init__(self, image_data, *, has_image=True):
        self.calls = []
        self.image_data = image_data
        self.has_image = has_image

    def open(self, request, timeout):
        url = request.full_url
        self.calls.append(url)
        if "/api.php?" in url:
            params = parse_qs(urlsplit(url).query)
            name = params["titles"][0]
            page = {"ns": 0, "pageid": 42, "title": name,
                    "fullurl": "https://valheim.wiki/w/" + name}
            if self.has_image:
                page["thumbnail"] = {
                    "source": "https://valheim.wiki/images/Greyling.png"}
            data = {"query": {"pages": [page]}}
            return _Response(url, json.dumps(data).encode("utf-8"))
        if url == "https://valheim.wiki/images/Greyling.png":
            return _Response(url, self.image_data)
        raise AssertionError("Untrusted request: " + url)


class WikiImageTests(unittest.TestCase):
    def test_names_remain_english_and_exact(self):
        self.assertEqual(wiki_title("$enemy_greyling"), "Greyling")
        self.assertEqual(wiki_title("$enemy_greydwarfbrute"), "Greydwarf Brute")
        self.assertEqual(wiki_title("$item_sword_iron"), "Iron sword")
        self.assertEqual(wiki_title("$enemy_abomination"), "Abomination")
        self.assertIsNone(wiki_title("$piece_woodwall"))
        self.assertEqual(wiki_title("$piece_workbench"), "Workbench")
        self.assertEqual(wiki_title("$piece_portal_stone"), "Stone portal")
        self.assertEqual(wiki_title("$ship_karve"), "Karve")
        self.assertEqual(wiki_title("$ship_longship"), "Longship")
        self.assertEqual(wiki_title("$ship_longship_ashlands"), "Drakkar")
        self.assertEqual(wiki_title("$ship_raft"), "Raft")
        self.assertIsNone(wiki_title("Bourgeon naingris"))
        self.assertTrue(_same_title("Greyling", "Greyling"))
        self.assertFalse(_same_title("Greydwarf", "Greyling"))
        self.assertTrue(_allowed_https("https://valheim.wiki/images/Greyling.png"))
        self.assertFalse(_allowed_https("http://valheim.wiki/images/Greyling.png"))
        self.assertFalse(_allowed_https("https://evil.org/images/Greyling.png"))
        self.assertFalse(_allowed_https("https://valheim.wiki.evil.org/Greyling.png"))

    @unittest.skipIf(Image is None, "Pillow necessaire pour verifier un PNG")
    def test_cache_image_and_attribution_without_second_network_call(self):
        picture=Image.new("RGB", (96, 96), (89, 105, 80))
        buffer=io.BytesIO()
        picture.save(buffer, format="PNG")
        with tempfile.TemporaryDirectory() as temp:
            cache=WikiImageCache(Path(temp)/"wiki_cache")
            opener=_MediaWikiOpener(buffer.getvalue())
            cache._client=opener
            image=cache.fetch("$enemy_greyling")
            self.assertIsNotNone(image)
            self.assertTrue(image.exists())
            self.assertEqual(cache.count(), 1)
            self.assertEqual(cache.fetch("$enemy_greyling"), image)
            self.assertEqual(len(opener.calls), 2)
            source=cache.source("$enemy_greyling")
            self.assertEqual(source["wiki_title"], "Greyling")
            self.assertEqual(source["page_url"], "https://valheim.wiki/w/Greyling")
            self.assertEqual(source["token"], "$enemy_greyling")
            self.assertEqual(cache.clear(), 2)
            self.assertIsNone(cache.cached_image("$enemy_greyling"))

    def test_wiki_without_page_image_fails_closed_and_caches_miss(self):
        with tempfile.TemporaryDirectory() as temp:
            cache=WikiImageCache(Path(temp)/"wiki_cache")
            opener=_MediaWikiOpener(b"", has_image=False)
            cache._client=opener
            self.assertIsNone(cache.fetch("$enemy_greyling"))
            calls=len(opener.calls)
            self.assertGreater(calls,0)
            self.assertIsNone(cache.fetch("$enemy_greyling"))
            self.assertEqual(len(opener.calls),calls)
            self.assertIsNone(cache.source("$enemy_greyling"))
            self.assertIsNone(cache.fetch("$piece_unknown"))
            self.assertEqual(len(opener.calls),calls)

    def test_wrong_image_page_is_not_accepted(self):
        class WrongPage:
            def open(self, request, timeout):
                body=json.dumps({"query":{"pages":[{"ns":0,"title":"Greydwarf",
                   "thumbnail":{"source":"https://valheim.wiki/images/Greyling.png"}}]}})
                return _Response(request.full_url, body.encode())
        self.assertIsNone(_lookup_page("Greyling", WrongPage()))


if __name__=="__main__":
    unittest.main()
