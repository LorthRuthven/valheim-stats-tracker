"""Affichage français sans modification des clés de sauvegarde."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localization_fr import localized_name, french_names
from valheim_reader import prefab_label, evaluate_one, SPECS
from app import clean_name


class FrenchTranslationTests(unittest.TestCase):
    def test_names_from_valheim_french_locale(self):
        self.assertEqual(localized_name('$enemy_greydwarf'), 'Naingris')
        self.assertEqual(localized_name('$item_wood'), 'Bois')
        self.assertEqual(localized_name('$enemy_seeker'), 'Fouineur')
        self.assertEqual(prefab_label('$piece_workbench'), 'Table de fabrication')
        self.assertEqual(clean_name('$item_sword_mistwalker'), 'Marchebrume')

    def test_missing_keeps_fallback_and_token(self):
        self.assertEqual(localized_name('$enemy_unknown_999', 'Unknown 999'), 'Unknown 999')
        self.assertEqual(localized_name('$enemy_unknown_999'), '$enemy_unknown_999')

    def test_translation_does_not_change_identifier(self):
        # On doit conserver les prefabs d'origine pour lire les valeurs .fch.
        from test_achievements import synthetic
        p = synthetic()
        p['groups']['Any']['enemies'][0]['$enemy_greydwarf'] = 1
        hunter = next(x for x in SPECS if x.key == 'hunter')
        r = evaluate_one(p, hunter)
        entry = next(x for x in r['parts'] if x['key'] == '$enemy_greydwarf')
        self.assertEqual(entry['label'], 'Naingris')
        self.assertEqual(entry['current'], 1)

    def test_pickable_aliases_do_not_modify_keys(self):
        from localization_fr import _item_keys
        names = {
            '$item_wood':'Bois', '$item_raspberries':'Framboises',
            '$item_mushroomcommon':'Champignon', '$item_jotunpuffs':'Globes jötnars',
            '$item_ancientgemstone_black':'Draumyx', '$item_magecap':'Coiffe-de-mage',
        }
        with patch('localization_fr.french_names', return_value=names):
            _item_keys.cache_clear()
            for key, expected in {
                'Wood':'Bois', 'Raspberry':'Framboises',
                'Mushroom':'Champignon', 'MushroomJotunPuffs':'Globes jötnars',
                'AncientGemstoneBlack':'Draumyx', 'MushroomMagecap':'Coiffe-de-mage',
            }.items():
                self.assertEqual(localized_name(key), expected)
                self.assertEqual(clean_name(key), expected)
        _item_keys.cache_clear()

    def test_descriptive_missing_names(self):
        from localization_fr import SUPPLEMENTAL_LABELS
        self.assertEqual(len(SUPPLEMENTAL_LABELS), 7)
        self.assertEqual(localized_name('$enemy_root'), 'Racine')
        self.assertEqual(localized_name('$enemy_writhan'), 'Writhan')
        self.assertEqual(localized_name('$spiritcaller_moose'), 'Élan invoqué')
        self.assertEqual(localized_name('$piece_darkwoodbeam67'), 'Poutre en bois sombre 67°')

    def test_html_formatting_cleaned(self):
        with patch('localization_fr.Path.read_text', return_value='{"$enemy_goblin": "<color=orange>Fuling</color>"}'):
            french_names.cache_clear()
            self.assertEqual(localized_name('$enemy_goblin'), 'Fuling')
        french_names.cache_clear()


if __name__ == '__main__':
    unittest.main()
