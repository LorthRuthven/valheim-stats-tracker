"""Tests V2.3.0 : encyclopédie bâtie sur les compteurs existants, sans statut fictif."""
import unittest

from collection_catalog import CATEGORIES, catalogue


class CollectionCatalogTests(unittest.TestCase):
    def test_catalogue_is_available_without_character(self):
        entries=catalogue()
        self.assertGreater(len(entries),250)
        self.assertIn("Créatures",{r["category"] for r in entries})
        self.assertIn("Trophées",{r["category"] for r in entries})
        self.assertIn("Armes",{r["category"] for r in entries})
        self.assertIn("Constructions",{r["category"] for r in entries})
        self.assertTrue(all(not row["observed"] and row["status"]=="Statut inconnu"
                            for row in entries))
        self.assertEqual(len(entries),len({x["token"] for x in entries}))

    def test_counters_are_evidence_only_not_steam_discoveries(self):
        character={"groups":{"Any":{
            "enemies":[{"$enemy_boar":3}],
            "crafted":{"$item_sword_iron":2},
            "picked_up":{"$item_wood":19},
            "pickables":{},
            "pieces_built":{"$piece_woodwall":4},
            "foods_eaten":{"$item_honey":1},
        }}}
        result={row["token"]:row for row in catalogue(character)}
        self.assertTrue(result["$enemy_boar"]["observed"])
        self.assertEqual(result["$enemy_boar"]["amount"],3)
        self.assertIn("Éliminations",result["$enemy_boar"]["evidence"][0])
        self.assertTrue(result["$item_wood"]["observed"])
        self.assertEqual(result["$item_wood"]["category"],"Ressources")
        self.assertTrue(result["$item_sword_iron"]["observed"])
        self.assertTrue(result["$piece_woodwall"]["observed"])
        self.assertEqual(result["$piece_woodwall"]["category"],"Constructions")
        self.assertEqual(result["$item_honey"]["category"],"Nourritures")
        # Les trophées sans compteur individuel ne sont pas classés "manquants".
        trophy=next(x for x in result.values() if x["category"]=="Trophées"
                    and not x["observed"])
        self.assertEqual(trophy["status"],"Statut inconnu")

    def test_unlisted_activity_is_added_without_rewriting_source(self):
        character={"groups":{"Any":{"picked_up":{"$item_new_valheim_resource":9}}}}
        rows={row["token"]:row for row in catalogue(character)}
        self.assertEqual(rows["$item_new_valheim_resource"]["amount"],9)
        self.assertEqual(rows["$item_new_valheim_resource"]["status"],"Activité enregistrée")


if __name__=="__main__":
    unittest.main()
