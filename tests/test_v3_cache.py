import tempfile
import unittest
from unittest.mock import patch

from v2_core import TrackerStore
from restored_pages import search_normalize


class V3CacheTests(unittest.TestCase):
    def test_unicode_search(self):
        self.assertEqual(search_normalize("ÉPÉE Noire"),"epee noire")
        self.assertTrue(all(word in search_normalize("Épée en sombracier")
                            for word in search_normalize("EPEE sombracier").split()))

    def test_snapshot_cache_and_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TrackerStore(tmp)
            store.profile={"name":"VikingTest"}
            with patch("v2_core.sample_rows", return_value=[(1,1,"x",{})]) as reader:
                first=store.rows(5000)
                second=store.rows(5000)
                self.assertEqual(first,second)
                self.assertEqual(reader.call_count,1)
                self.assertEqual(store.diagnostics()["cache_hits"],1)
                self.assertEqual(store.diagnostics()["cache_misses"],1)
                store._rows_cache.clear()
                store.rows(5000)
                self.assertEqual(reader.call_count,2)
            store.close()


if __name__=="__main__":
    unittest.main()
