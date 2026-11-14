"""Qt V2.1 : tests exécutés sur Windows, ignorés sur Linux sans Qt."""
import os
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from nordic_ui import NordicWindow, rune_icon
    from desktop_v2 import TrendChart
    from v2_core import TrackerStore
except ImportError:
    QApplication=None


@unittest.skipIf(QApplication is None,'Qt non installé dans cet environnement')
class QtWindowTests(unittest.TestCase):
    def test_navigation_graphics_and_motion(self):
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            w=NordicWindow(TrackerStore(tmp))
            w.show()
            app.processEvents()
            self.assertEqual(w.stack.count(),5)
            self.assertTrue(w.hero.renderer.isValid())
            self.assertFalse(rune_icon('trophy').pixmap(28,28).isNull())
            self.assertFalse(w.grab().isNull())
            w.hero.ring.move_to(48,animated=False)
            self.assertAlmostEqual(w.hero.ring.get_value(),48)
            for i in range(5):
                w.show_page(i)
                self.assertEqual(w.stack.currentIndex(),i)
                self.assertTrue(w.nav_buttons[i].isChecked())
            w.set_motion(False)
            self.assertFalse(w.motion)
            self.assertFalse(w.motion_checkbox.isChecked()==True and w.motion)
            w.history_chart.set_data([(100,1),(200,3),(300,2)],'Test')
            self.assertEqual(len(w.history_chart.points),3)
            self.assertFalse(w.history_chart.grab().isNull())
            w.close()
            newer=NordicWindow(TrackerStore(tmp))
            self.assertFalse(newer.motion)
            newer.close()


if __name__=='__main__':
    unittest.main()
