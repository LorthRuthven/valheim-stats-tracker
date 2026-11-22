import unittest

from session_insights import session_insights, session_records


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

    def test_intermediate_reset_cannot_generate_false_gain(self):
        from unittest.mock import patch
        with patch("session_insights._stat", side_effect=lambda p, key: p[key]):
            data = session_insights([
                row(1, 100, 100), row(2, 200, 2), row(3, 300, 120)
            ])[0]
        self.assertIn("kills", data["resets"])
        self.assertNotIn("kills", data["gains"])

    def test_no_fake_duration_for_single_snapshot(self):
        self.assertEqual(session_insights([row(1, 100, 1)]), [])
        self.assertEqual(session_insights([]), [])


    def test_records_choose_highest_positive_gain(self):
        sessions = [
            {"start": 10, "end": 20, "gains": {"kills": 7, "builds": 3}},
            {"start": 30, "end": 40, "gains": {"kills": 2, "builds": 9}},
            {"start": 50, "end": 60, "gains": {"builds": 0}, "resets": ["kills"]},
        ]
        found = {item["key"]: item for item in session_records(sessions)}
        self.assertEqual(found["kills"]["value"], 7)
        self.assertEqual(found["kills"]["start"], 10)
        self.assertEqual(found["builds"]["value"], 9)
        self.assertNotIn("crafts", found)
        self.assertNotIn("deaths", found)

    def test_invalid_gap_rejected(self):
        with self.assertRaises(ValueError):
            session_insights([], gap_seconds=0)


if __name__ == "__main__":
    unittest.main()
