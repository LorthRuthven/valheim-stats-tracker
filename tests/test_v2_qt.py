"""UI Qt : tests exécutés sur Windows, ignorés sur Linux sans Qt."""
import os
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from desktop_v2 import TrackerWindow, TrendChart
    from v2_core import TrackerStore
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'Qt n’est pas installé dans cet environnement')
class QtWindowTests(unittest.TestCase):
    def test_navigation_and_interactive_chart(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            window = TrackerWindow(TrackerStore(tmp))
            self.assertEqual(window.stack.count(), 5)
            for i in range(5):
                window.show_page(i)
                self.assertEqual(window.stack.currentIndex(), i)
                self.assertTrue(window.nav_buttons[i].isChecked())
            window.history_chart.set_data([(100, 1), (200, 3), (300, 2)], 'Test')
            self.assertEqual(len(window.history_chart.points), 3)
            window.history_chart.resize(700, 350)
            image = window.history_chart.grab()
            self.assertFalse(image.isNull())
            app.processEvents()
            window.close()


if __name__=='__main__':unittest.main()
