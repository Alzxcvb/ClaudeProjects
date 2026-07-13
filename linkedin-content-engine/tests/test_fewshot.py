"""generate.py and predict.py must keep working from the database, including
on the rows that crashed them when they read posts.jsonl directly."""
import unittest

import generate
import predict
from contentcrm import ROOT
from contentcrm.fewshot import load_posts_compat
from contentcrm.importers import migrate_posts_jsonl

from .helpers import CrmTestCase


class TestFewshot(CrmTestCase):
    def setUp(self):
        super().setUp()
        migrate_posts_jsonl(self.conn, ROOT / "posts.jsonl", self.cfg)
        self.conn.commit()

    def test_generator_examples_skip_bodiless_runs(self):
        posts = load_posts_compat(require_body=True, config=self.cfg)
        self.assertEqual(len(posts), 8)  # 013-015 have no recorded body
        ids = [p["id"] for p in posts]
        self.assertIn("post-001", ids)
        self.assertNotIn("post-013", ids)
        text = generate.format_examples(posts)  # crashed with KeyError before
        self.assertIn("post-016", text)
        self.assertIn("impressions=208", text)

    def test_predictor_history_keeps_all_labeled_runs(self):
        posts = load_posts_compat(require_body=False, config=self.cfg)
        self.assertEqual(len(posts), 11)
        by_id = {p["id"]: p for p in posts}
        self.assertEqual(by_id["post-013"]["body"], "(body not recorded)")
        self.assertEqual(by_id["post-013"]["hook_archetype"], "?")
        history, n_labeled, median = predict.format_history(posts)
        self.assertEqual(n_labeled, 11)
        self.assertIn("post-013", history)
        self.assertIsNotNone(median)

    def test_chronological_order_matches_the_old_jsonl_contract(self):
        posts = load_posts_compat(require_body=False, config=self.cfg)
        self.assertEqual(posts[0]["id"], "post-001")
        self.assertEqual(posts[-1]["id"], "post-016")


if __name__ == "__main__":
    unittest.main()
