"""Tests de l’identité visuelle Qt V2.1 ; sans Qt, validation AST/SVG."""
import ast
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


class VectorArtworkTests(unittest.TestCase):
    def test_scenery_and_logo_are_valid_svg(self):
        tree=ast.parse((ROOT/'nordic_ui.py').read_text(encoding='utf8'))
        declared={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant):
                for target in node.targets:
                    if isinstance(target,ast.Name):
                        declared[target.id]=node.value.value
        for key in ('HERO','EMBLEM'):
            self.assertIn(key,declared)
            image=ET.fromstring(declared[key])
            self.assertEqual(image.tag,'{http://www.w3.org/2000/svg}svg')
            self.assertGreater(len(list(image.iter())),3 if key == 'EMBLEM' else 15)

    def test_no_opaque_label_boxes(self):
        ui=(ROOT/'nordic_ui.py').read_text(encoding='utf8')
        self.assertIn('QLabel{{background:transparent',ui)
        self.assertNotIn("QMainWindow,QWidget{{background:",ui)

    def test_no_network_in_new_theme(self):
        text=(ROOT/'nordic_ui.py').read_text(encoding='utf8')
        self.assertNotIn('urllib.request',text)
        self.assertNotIn('requests.get(',text)
        self.assertIn('QSvgRenderer',text)
        self.assertIn('QPropertyAnimation',text)
