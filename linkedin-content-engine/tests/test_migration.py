"""The named migration test: 11 posts.jsonl rows become 10 ideas, 11 variants,
11 runs; post-001 and post-002 end up siblings under ONE idea."""
import unittest

from contentcrm import ROOT
from contentcrm.importers import migrate_posts_jsonl
from contentcrm.util import dow_bucket

from .helpers import CrmTestCase

JSONL = ROOT / "posts.jsonl"


class TestMigration(CrmTestCase):
    def setUp(self):
        super().setUp()
        self.summary = migrate_posts_jsonl(self.conn, JSONL, self.cfg)

    def test_counts(self):
        self.assertEqual(self.summary["ideas"], 10)
        self.assertEqual(self.summary["variants"], 11)
        self.assertEqual(self.summary["runs"], 11)
        self.assertEqual(self.summary["metrics"], 11)
        self.assertEqual(self.count("ideas"), 10)
        self.assertEqual(self.count("variants"), 11)
        self.assertEqual(self.count("runs"), 11)
        self.assertEqual(self.count("metrics"), 11)

    def test_post_001_and_002_are_siblings_under_one_idea(self):
        v1 = self.one("SELECT * FROM variants WHERE legacy_post_id = 'post-001'")
        v2 = self.one("SELECT * FROM variants WHERE legacy_post_id = 'post-002'")
        self.assertEqual(v1["idea_id"], v2["idea_id"])
        idea = self.one("SELECT * FROM ideas WHERE id = ?", v1["idea_id"])
        self.assertEqual(idea["slug"], "ai-jobs-divide")
        # siblings, not parent and child: neither derives from the other
        self.assertIsNone(v1["derived_from_variant_id"])
        self.assertIsNone(v2["derived_from_variant_id"])
        # and nothing else was pulled into that idea
        self.assertEqual(self.count("variants", "idea_id = ?", v1["idea_id"]), 2)

    def test_other_posts_get_their_own_ideas(self):
        v3 = self.one("SELECT * FROM variants WHERE legacy_post_id = 'post-003'")
        v1 = self.one("SELECT * FROM variants WHERE legacy_post_id = 'post-001'")
        self.assertNotEqual(v3["idea_id"], v1["idea_id"])

    def test_dated_runs_know_dow_but_not_slot(self):
        r1 = self.one("SELECT * FROM runs WHERE legacy_post_id = 'post-001'")
        self.assertEqual(r1["posted_at"], "2026-05-27")
        self.assertEqual(r1["posted_at_precision"], "date")
        self.assertEqual(r1["dow_bucket"], dow_bucket("2026-05-27", "date"))
        self.assertIsNone(r1["slot_bucket"])
        self.assertIsNone(r1["followers_at_post"])

    def test_approx_runs_know_neither(self):
        r13 = self.one("SELECT * FROM runs WHERE legacy_post_id = 'post-013'")
        self.assertEqual(r13["posted_at"], "2026-06-04")
        self.assertEqual(r13["posted_at_precision"], "approx")
        self.assertIsNone(r13["dow_bucket"])
        self.assertIsNone(r13["slot_bucket"])
        self.assertIn("approximate", r13["notes"])

    def test_bodies_preserved_where_present_and_not_faked_where_absent(self):
        v16 = self.one("SELECT * FROM variants WHERE legacy_post_id = 'post-016'")
        self.assertIn("3 hours every Monday", v16["body"])
        self.assertEqual(v16["word_count"], len(v16["body"].split()))
        for legacy in ("post-013", "post-014", "post-015"):
            v = self.one("SELECT * FROM variants WHERE legacy_post_id = ?", legacy)
            self.assertIsNone(v["body"], legacy)
            self.assertIn("not recorded", v["notes"])

    def test_legacy_snapshot_is_adhoc_with_real_capture_date(self):
        r1 = self.one("SELECT * FROM runs WHERE legacy_post_id = 'post-001'")
        m = self.one("SELECT * FROM metrics WHERE run_id = ?", r1["id"])
        self.assertIsNone(m["checkpoint"])
        self.assertEqual(m["captured_at"], "2026-06-03")
        self.assertEqual(m["impressions"], 202)
        self.assertEqual(m["reactions"], 3)
        self.assertEqual(m["comments"], 2)

    def test_migration_refuses_to_run_twice(self):
        with self.assertRaises(ValueError):
            migrate_posts_jsonl(self.conn, JSONL, self.cfg)

    def test_cli_migrate_reports_the_sibling_check(self):
        code, out, err = self.crm("show", "post-001")
        self.assertEqual(code, 0, err)
        self.assertIn("ai-jobs-divide", out)


if __name__ == "__main__":
    unittest.main()
