"""V2.2.3 : cas de référence pour l'extraction des sprites Valheim.

Les tests créent de petits bundles fictifs, sans redistribuer les fichiers du jeu.
Le test avec de vraies données du jeu doit encore être effectué sur le PC utilisateur.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from game_icon_extraction import (
    IconExtractionError, bundle_paths, extract_owned_icons, icon_aliases
)

try:
    from PIL import Image
except ImportError:
    Image = None


def game_folder(parent):
    root=Path(parent)/'Valheim'
    (root/'valheim_Data'/'StreamingAssets'/'SoftRef'/'Bundles').mkdir(parents=True)
    (root/'valheim.exe').write_bytes(b'MZ')
    (root/'valheim_Data'/'StreamingAssets'/'SoftRef'/'Bundles'/'example_bundle').write_bytes(b'UnityFS')
    return root


def object_of(kind, name, image=None, fail=False):
    def parse():
        if fail:
            raise RuntimeError('Sprite compressé : échec factice pour test')
        return NS(m_Name=name, image=image)
    return NS(type=NS(name=kind), parse_as_object=parse)


class IconExtractionTests(unittest.TestCase):
    def test_invalid_directory_explains_valheim_exe(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'valheim.exe'):
                bundle_paths(temp)

    def test_aliases_match_names_used_by_tracker(self):
        self.assertIn('wood',icon_aliases('Icon_Wood'))
        self.assertIn('raspberries',icon_aliases('Sprite_Raspberries'))

    @unittest.skipIf(Image is None,'Pillow nécessaire pour encoder les sprites')
    def test_sprite_texture_and_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root=game_folder(temp)
            dest=Path(temp)/'icons'
            picture=Image.new('RGBA',(64,64),(25,70,120,255))
            objects=[
                object_of('Sprite','Icon_Wood',picture),
                object_of('Texture2D','Inventory_Honey',picture),
                object_of('Texture2D','HugeMountainLandscape',picture),
                object_of('Sprite','broken_sprite',fail=True),
            ]
            calls=[]
            count=extract_owned_icons(root,dest,unity_loader=lambda path:NS(objects=objects),
                                      notify=lambda index,total,name:calls.append((index,total,name)))
            self.assertEqual(count,2)
            self.assertTrue((dest/'iconwood.png').is_file())
            self.assertTrue((dest/'inventoryhoney.png').is_file())
            report=json.loads((dest/'extraction-report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['files_read'],1)
            self.assertEqual(report['sprites_found'],2)
            self.assertEqual(report['textures_found'],2)
            self.assertEqual(report['images_written'],2)
            self.assertEqual(report['errors_total'],1)
            self.assertEqual(report['images_rejected'],1)
            self.assertEqual(calls[-1][0],1)
            index=json.loads((dest/'index.json').read_text(encoding='utf-8'))
            self.assertEqual(index['aliases']['wood'],'iconwood.png')
            self.assertEqual(index['aliases']['honey'],'inventoryhoney.png')
            repeat=extract_owned_icons(root,dest,unity_loader=lambda path:NS(objects=objects))
            self.assertEqual(repeat,2)
            second=json.loads((dest/'extraction-report.json').read_text(encoding='utf-8'))
            self.assertEqual(second['images_existing'],2)

    @unittest.skipIf(Image is None,"Pillow nécessaire pour contrôler l’extraction à zéro")
    def test_empty_extraction_is_error_and_report_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            root=game_folder(temp)
            dest=Path(temp)/'icons'
            with self.assertRaisesRegex(IconExtractionError,'0 icône exploitable'):
                extract_owned_icons(root,dest,unity_loader=lambda path:NS(objects=[]))
            report=json.loads((dest/'extraction-report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['files_read'],1)
            self.assertEqual(report['sprites_found'],0)
            self.assertEqual(report['textures_found'],0)
            self.assertEqual(report['images_written'],0)

    @unittest.skipIf(Image is None,"Pillow nécessaire pour contrôler le journal des erreurs")
    def test_loader_errors_preserved_in_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root=game_folder(temp)
            dest=Path(temp)/'icons'
            def fail(_):
                raise RuntimeError('Bundle Unity incompatible pour ce test')
            with self.assertRaises(IconExtractionError):
                extract_owned_icons(root,dest,unity_loader=fail)
            report=json.loads((dest/'extraction-report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['errors_total'],1)
            self.assertIn('Bundle Unity incompatible',report['errors'][0]['reason'])


if __name__=='__main__':
    unittest.main()
