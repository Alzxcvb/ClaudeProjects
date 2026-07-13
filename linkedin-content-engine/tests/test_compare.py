"""Compare must give a real answer or an honest refusal. Never a confident
number the data cannot support."""
import copy
import unittest

from contentcrm import ROOT
from contentcrm.compare import compare_runs
from contentcrm.importers import migrate_posts_jsonl

from .helpers import CrmTestCase


class TestCompare(CrmTestCase):
    def seed(self, slug="permission-problem"):
        self.crm("idea", slug.replace("-", " "))
        self.crm("draft", slug, "--body", "original body", "--hook", "contrarian-take")
        return self.one("SELECT id FROM variants ORDER BY id DESC")["id"]

    def run_and_log(self, vid, at, followers, imp, reactions, comments):
        self.crm("ran", f"V{vid}", "--at", at, "--followers", followers)
        rid = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        self.crm("log", f"R{rid}", "-i", imp, "-r", reactions, "-c", comments,
                 "--cp", "adhoc", "--at", at)
        return rid

    def get_run(self, rid):
        return self.one("SELECT * FROM runs WHERE id = ?", rid)

    def test_rewrite_beats_parent_when_gates_pass_and_gap_is_big(self):
        parent = self.seed()
        # same platform, both Tuesday, both mid-am; eff 0.06 vs 0.1033 = +72%
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 200, 4, 2)
        self.crm("rewrite", f"V{parent}", "--body", "sharper rewrite body")
        child = self.one("SELECT id FROM variants ORDER BY id DESC")["id"]
        r2 = self.run_and_log(child, "2026-06-09 09:30", 420, 300, 10, 6)

        result = compare_runs(self.conn, self.cfg, self.get_run(r2), self.get_run(r1))
        self.assertEqual(result["verdict"], "WINNER")
        self.assertEqual(result["winner"], "a")
        self.assertAlmostEqual(result["gap_pct"], 72.2, delta=0.5)

        # single-argument form resolves the parent by lineage
        code, out, err = self.crm("compare", f"V{child}")
        self.assertEqual(code, 0, err)
        self.assertIn("beats", out)
        self.assertIn("Directional signal, not proof", out)

    def test_small_gap_is_noise_do_not_act(self):
        parent = self.seed()
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 200, 4, 2)   # eff 0.060
        r2 = self.run_and_log(parent, "2026-06-09 09:30", 410, 200, 5, 2)   # eff 0.065 (+8%)
        code, out, err = self.crm("compare", f"R{r1}", f"R{r2}")
        self.assertEqual(code, 0, err)
        self.assertIn("NOISE", out)
        self.assertIn("Do not act", out)

    def test_different_slots_are_inconclusive(self):
        parent = self.seed()
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 200, 4, 2)   # mid-am
        r2 = self.run_and_log(parent, "2026-06-09 19:00", 400, 500, 9, 4)   # evening
        result = compare_runs(self.conn, self.cfg, self.get_run(r1), self.get_run(r2))
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("mid-am vs evening" in r for r in result["reasons"]))

    def test_different_platforms_are_inconclusive(self):
        a = self.seed("idea-a")
        self.crm("draft", "idea-a", "--body", "x version", "--platform", "x")
        x_vid = self.one("SELECT id FROM variants ORDER BY id DESC")["id"]
        r1 = self.run_and_log(a, "2026-06-02 09:00", 400, 200, 4, 2)
        r2 = self.run_and_log(x_vid, "2026-06-09 09:00", 100, 900, 40, 10)
        result = compare_runs(self.conn, self.cfg, self.get_run(r1), self.get_run(r2))
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("platform" in r for r in result["reasons"]))

    def test_missing_metrics_are_inconclusive(self):
        parent = self.seed()
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 200, 4, 2)
        self.crm("ran", f"V{parent}", "--at", "2026-06-09 09:00", "--followers", "400")
        r2 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        result = compare_runs(self.conn, self.cfg, self.get_run(r1), self.get_run(r2))
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("no usable metrics" in r for r in result["reasons"]))

    def test_reach_metric_without_followers_is_inconclusive(self):
        parent = self.seed()
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 200, 4, 2)
        self.crm("ran", f"V{parent}", "--at", "2026-06-09 09:00")  # no followers
        r2 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        self.crm("log", f"R{r2}", "-i", "300", "-r", "5", "-c", "2",
                 "--cp", "adhoc", "--at", "2026-06-09 09:00")
        result = compare_runs(self.conn, self.cfg, self.get_run(r1), self.get_run(r2),
                              metric="reach")
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertTrue(any("followers_at_post" in r for r in result["reasons"]))

    def test_zero_scoring_loser_wins_without_a_fake_percentage(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["score_weights"] = {"comments": 3}
        parent = self.seed()
        r1 = self.run_and_log(parent, "2026-06-02 09:00", 400, 50, 0, 0)  # score 0
        r2 = self.run_and_log(parent, "2026-06-09 09:00", 400, 50, 0, 5)  # score 15
        result = compare_runs(self.conn, cfg, self.get_run(r1), self.get_run(r2))
        self.assertEqual(result["verdict"], "WINNER")
        self.assertTrue(result.get("zero_loser"))
        self.assertIsNone(result["gap_pct"])

    def test_same_checkpoint_snapshots_beat_latest_snapshots(self):
        parent = self.seed()
        self.crm("ran", f"V{parent}", "--at", "2026-06-02 09:00", "--followers", "400")
        r1 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        # parent: weak at 24h, strong by 7d
        self.crm("log", f"R{r1}", "-i", "100", "-r", "0", "-c", "0",
                 "--cp", "24h", "--at", "2026-06-03 09:00")
        self.crm("log", f"R{r1}", "-i", "1000", "-r", "50", "-c", "50",
                 "--cp", "7d", "--at", "2026-06-09 09:00")
        self.crm("rewrite", f"V{parent}", "--body", "child body")
        child = self.one("SELECT id FROM variants ORDER BY id DESC")["id"]
        self.crm("ran", f"V{child}", "--at", "2026-06-09 09:30", "--followers", "400")
        r2 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        self.crm("log", f"R{r2}", "-i", "100", "-r", "5", "-c", "5",
                 "--cp", "24h", "--at", "2026-06-10 09:30")

        result = compare_runs(self.conn, self.cfg, self.get_run(r2), self.get_run(r1))
        # 24h is the only shared checkpoint, so 24h vs 24h, not 24h vs 7d
        self.assertIn("24h", result["snapshot_note"])
        self.assertAlmostEqual(result["values"]["a"], 0.21, places=3)
        self.assertAlmostEqual(result["values"]["b"], 0.01, places=3)
        self.assertEqual(result["verdict"], "WINNER")

    def test_mismatched_snapshot_ages_carry_a_warning(self):
        parent = self.seed()
        self.crm("ran", f"V{parent}", "--at", "2026-06-02 09:00", "--followers", "400")
        r1 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        self.crm("log", f"R{r1}", "-i", "200", "-r", "4", "-c", "2",
                 "--cp", "7d", "--at", "2026-06-09 09:00")
        self.crm("ran", f"V{parent}", "--at", "2026-06-09 09:30", "--followers", "400")
        r2 = self.one("SELECT id FROM runs ORDER BY id DESC")["id"]
        self.crm("log", f"R{r2}", "-i", "300", "-r", "9", "-c", "4",
                 "--cp", "adhoc", "--at", "2026-06-10 09:30")
        result = compare_runs(self.conn, self.cfg, self.get_run(r1), self.get_run(r2))
        self.assertIsNotNone(result["snapshot_warning"])
        self.assertIn("accumulate", result["snapshot_warning"])

    def test_the_plan_md_trap_post_001_vs_002_refuses_honestly(self):
        migrate_posts_jsonl(self.conn, ROOT / "posts.jsonl", self.cfg)
        code, out, err = self.crm("compare", "post-001", "post-002")
        self.assertEqual(code, 0, err)
        self.assertIn("INCONCLUSIVE", out)
        self.assertIn("slot unknown", out)
        self.assertNotIn("beats", out)


if __name__ == "__main__":
    unittest.main()
