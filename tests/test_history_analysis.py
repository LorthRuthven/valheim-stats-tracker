"""Tests de la logique d'historique avancé, sans dépendance graphique."""
import unittest
from history_analysis import filter_sessions, session_comparison, session_summary


def session(end, gains, **extra):
    return dict(start=end-100, end=end, span_minutes=2, samples=2,
                gains=gains, resets=extra.get("resets", []))


class HistoryAnalysisTests(unittest.TestCase):
    def test_period_keeps_only_recent_sessions(self):
        data=[session(10,{"kills":1}),session(20,{"kills":2}),
              session(80,{"kills":3})]
        self.assertEqual(len(filter_sessions(data)),3)
        self.assertEqual([s["end"] for s in filter_sessions(data,60)],[20,80])
        self.assertEqual([s["end"] for s in filter_sessions(data,30)],[80])
        with self.assertRaises(ValueError):
            filter_sessions(data,-1)

    def test_comparison_requires_two_measured_values(self):
        newer=session(90,{"kills":8,"builds":7})
        older=session(80,{"kills":3},resets=["builds"])
        result=session_comparison(newer,older)
        self.assertEqual(result["kills"]["change"],5)
        self.assertIsNone(result["builds"]["change"])
        self.assertNotIn("deaths",result)

    def test_summary_never_invents_playtime(self):
        text=session_summary(session(90,{"kills":4},resets=["crafts"]))
        self.assertIn("pas du temps réellement joué",text)
        self.assertIn("crafts",text)
        self.assertIn("Intervalle observé",text)


if __name__ == "__main__":
    unittest.main()
