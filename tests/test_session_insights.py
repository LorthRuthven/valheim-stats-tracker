import unittest

from session_insights import session_insights


def row(number, timestamp, kills, builds=0, crafts=0, deaths=0):
    # metrics(profile, "Any") reads its counters through the real parser schema;
    # mocking _stat keeps these tests focused on session segmentation.
    return (number, timestamp, "", {"kills": kills, "built": builds, "crafted": crafts, "deaths": deaths})


class SessionInsightsTests(unittest.TestCase):
    def test_splits_on_large_gap_and_ignores_isolated_save(self):
        from unittest.mock import patch
        with patch("session_insights._stat", side_effect=lambda p, key: p[key]):
            data = session_insights([
                row(1, 1000, 1), row(2, 1300, 4),
                row(3, 8000, 8), row(4, 8100, 9),
                row(5, 25000, 11),
            ])
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["gains"]["kills"], 1)
        self.assertEqual(data[1]["gains"]["kills"], 3)

    def test_negative_counter_is_reset_not_gain(self):
        from unittest.mock import patch
        with patch("session_insights._stat", side_effect=lambda p, key: p[key]):
            data = session_insights([row(1, 1, 50), row(2, 2, 4)])[0]
        self.assertNotIn("kills", data["gains"])
        self.assertIn("kills", data["resets"])

    def test_no_fake_duration_for_single_snapshot(self):
        self.assertEqual(session_insights([row(1, 100, 1)]), [])
        self.assertEqual(session_insights([]), [])


if __name__ == "__main__":
    unittest.main()
