"""The recycling queue: past-cooldown ranking, cooling, never-run, platform isolation."""
import unittest
from datetime import date

from contentcrm.queue import due

from .helpers import CrmTestCase

TODAY = date(2026, 7, 10)


class TestDue(CrmTestCase):
    def make(self, slug, platform, posted_at, followers, imp, reactions, comments):
        self.crm("idea", slug.replace("-", " "))
        self.crm("draft", slug, "--body", f"body for {slug}", "--platform", platform)
        vid = self.one(
            "SELECT v.id FROM variants v JOIN ideas i ON i.id = v.idea_id WHERE i.slug = ?",
            slug)["id"]
        if posted_at:
            self.crm("ran", f"V{vid}", "--at", posted_at, "--followers", followers)
            rid = self.one("SELECT id FROM runs WHERE variant_id = ?", vid)["id"]
            self.crm("log", f"R{rid}", "-i", imp, "-r", reactions, "-c", comments,
                     "--cp", "adhoc", "--at", posted_at[:10] + " 23:00")

    def setUp(self):
        super().setUp()
        # eff: high-scorer 41/100 = 0.41, low-scorer 2/200 = 0.01
        self.make("winner-long-ago", "linkedin", "2026-03-01 09:00", 400, 100, 10, 10)
        self.make("dud-long-ago", "linkedin", "2026-01-05 09:00", 300, 200, 0, 0)
        self.make("fresh-one", "linkedin", "2026-07-01 09:00", 500, 150, 3, 1)
        self.make("never-ran-drafted", "linkedin", None, 0, 0, 0, 0)
        self.crm("idea", "never ran no variant")
        self.make("x-only", "x", "2026-06-01 09:00", 90, 500, 20, 5)

    def test_past_cooldown_ranked_by_last_efficiency(self):
        q = due(self.conn, self.cfg, "linkedin", today=TODAY)
        slugs = [e["idea_slug"] for e in q["due"]]
        self.assertEqual(slugs, ["winner-long-ago", "dud-long-ago"])
        self.assertGreater(q["due"][0]["perf"]["efficiency"],
                           q["due"][1]["perf"]["efficiency"])
        self.assertEqual(q["due"][0]["days_since"], 131)

    def test_recent_run_is_cooling_with_eligible_date(self):
        q = due(self.conn, self.cfg, "linkedin", today=TODAY)
        cooling = {e["idea_slug"]: e for e in q["cooling"]}
        self.assertIn("fresh-one", cooling)
        self.assertEqual(str(cooling["fresh-one"]["eligible_on"]), "2026-09-29")

    def test_never_run_lists_backlog_and_flags_missing_variants(self):
        q = due(self.conn, self.cfg, "linkedin", today=TODAY)
        never = {r["slug"]: r for r in q["never"]}
        self.assertIn("never-ran-drafted", never)
        self.assertIn("never-ran-no-variant", never)
        self.assertIn("x-only", never)  # never ran on THIS platform
        self.assertEqual(never["never-ran-drafted"]["platform_variants"], 1)
        self.assertEqual(never["never-ran-no-variant"]["platform_variants"], 0)

    def test_platform_isolation_and_platform_cooldowns(self):
        q = due(self.conn, self.cfg, "x", today=TODAY)
        self.assertEqual([e["idea_slug"] for e in q["due"]], ["x-only"])  # 39d > 30d cooldown
        self.assertEqual(q["cooldown"], 30)
        linkedin_slugs = {e["idea_slug"] for e in
                          due(self.conn, self.cfg, "linkedin", today=TODAY)["due"]}
        self.assertNotIn("x-only", linkedin_slugs)

    def test_cli_renders_the_queue(self):
        code, out, err = self.crm("due")
        self.assertEqual(code, 0, err)
        self.assertIn("DUE FOR RETEST", out)
        self.assertIn("winner-long-ago", out)
        self.assertIn("NEVER RUN", out)


if __name__ == "__main__":
    unittest.main()
