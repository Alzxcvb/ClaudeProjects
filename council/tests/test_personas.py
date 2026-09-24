import unittest

from council import personas


class PersonasTest(unittest.TestCase):
    def test_default_pair_is_bull_bear(self):
        pair = personas.parse_pair(None)
        self.assertEqual([p.key for p in pair], ["bull", "bear"])

    def test_pair_order_is_kept(self):
        pair = personas.parse_pair("bear,bull")
        self.assertEqual([p.key for p in pair], ["bear", "bull"])

    def test_pair_case_insensitive(self):
        pair = personas.parse_pair("BULL,Bear")
        self.assertEqual([p.key for p in pair], ["bull", "bear"])

    def test_unknown_persona_errors(self):
        with self.assertRaises(personas.PersonaError):
            personas.parse_pair("bull,nonexistent")

    def test_duplicate_persona_errors(self):
        with self.assertRaises(personas.PersonaError):
            personas.parse_pair("bull,bull")

    def test_wrong_count_errors(self):
        with self.assertRaises(personas.PersonaError):
            personas.parse_pair("bull")
        with self.assertRaises(personas.PersonaError):
            personas.parse_pair("bull,bear,extra")

    def test_load_all_finds_starter_pair(self):
        loaded = personas.load_all()
        self.assertIn("bull", loaded)
        self.assertIn("bear", loaded)
        self.assertTrue(loaded["bull"].body)
        self.assertTrue(loaded["bear"].body)
        self.assertEqual(loaded["bull"].name, "Bull")
        self.assertEqual(loaded["bear"].name, "Bear")

    def test_persona_files_are_politics_free(self):
        # Not exhaustive, but a floor: no obvious political terms in the
        # shipped starter pair.
        banned = ("democrat", "republican", "election", "president")
        for persona in personas.load_all().values():
            lowered = persona.body.lower()
            for term in banned:
                self.assertNotIn(term, lowered)


if __name__ == "__main__":
    unittest.main()
