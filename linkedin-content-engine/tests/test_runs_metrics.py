"""Logging a run and its three checkpoints through the real CLI surface."""
import unittest
from datetime import datetime, timedelta

from .helpers import CrmTestCase


class TestRunsAndMetrics(CrmTestCase):
    def setUp(self):
        super().setUp()
        self.crm("idea", "Copy paste tax", "--thesis", "4 hrs/week pasting = a vacation")
        code, out, err = self.crm(
            "draft", "copy-paste-tax", "--body", "Four hours a week.\n\nThat adds up.",
            "--hook", "stat-shock", "--format", "short-punchy",
        )
        self.assertEqual(code, 0, err)
        self.vid = self.one("SELECT id FROM variants")["id"]

    def test_ran_records_buckets_and_followers(self):
        code, out, err = self.crm(
            "ran", f"V{self.vid}", "--at", "2026-07-01 09:00", "--followers", "500",
        )
        self.assertEqual(code, 0, err)
        run = self.one("SELECT * FROM runs")
        self.assertEqual(run["posted_at"], "2026-07-01 09:00")
        self.assertEqual(run["posted_at_precision"], "minute")
        self.assertEqual(run["dow_bucket"], "Wed")
        self.assertEqual(run["slot_bucket"], "mid-am")
        self.assertEqual(run["followers_at_post"], 500)

    def test_ran_without_followers_warns(self):
        code, out, err = self.crm("ran", f"V{self.vid}", "--at", "2026-07-01 09:00")
        self.assertEqual(code, 0, err)
        self.assertIn("normalised reach will be unavailable", out)

    def test_three_checkpoints_and_latest_snapshot_scoring(self):
        self.crm("ran", f"V{self.vid}", "--at", "2026-07-01 09:00", "--followers", "500")
        for cp, at, imp in (("24h", "2026-07-02 09:10", 120),
                            ("72h", "2026-07-04 10:00", 180),
                            ("7d", "2026-07-08 09:00", 200)):
            code, out, err = self.crm(
                "log", "-i", imp, "-r", "4", "-c", "2", "--cp", cp, "--at", at)
            self.assertEqual(code, 0, err)

        self.assertEqual(self.count("metrics"), 3)
        labels = [m["checkpoint"] for m in
                  self.conn.execute("SELECT checkpoint FROM metrics ORDER BY id")]
        self.assertEqual(labels, ["24h", "72h", "7d"])

        # score = 0.01*200 + 1*4 + 3*2 = 12; eff = 12/200; reach = 200/500
        code, out, err = self.crm("show", "R1")
        self.assertEqual(code, 0, err)
        self.assertIn("score 12.00", out)
        self.assertIn("eff 0.060", out)
        self.assertIn("reach 0.40", out)

    def test_auto_checkpoint_label_from_elapsed_time(self):
        posted = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M")
        self.crm("ran", f"V{self.vid}", "--at", posted, "--followers", "500")
        code, out, err = self.crm("log", "-i", "90", "-r", "1", "-c", "0")
        self.assertEqual(code, 0, err)
        m = self.one("SELECT * FROM metrics")
        self.assertEqual(m["checkpoint"], "24h")
        self.assertIn("Logged 24h metrics", out)

    def test_log_with_no_metric_flags_is_refused_with_platform_hints(self):
        self.crm("ran", f"V{self.vid}", "--at", "2026-07-01 09:00")
        code, out, err = self.crm("log")
        self.assertEqual(code, 2)
        self.assertIn("no metrics given", err)

    def test_status_shows_due_checkpoints(self):
        posted = (datetime.now() - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M")
        self.crm("ran", f"V{self.vid}", "--at", posted, "--followers", "500")
        code, out, err = self.crm("status")
        self.assertEqual(code, 0, err)
        self.assertIn("24h DUE", out)
        self.assertIn("7d in", out)

    def test_status_marks_long_past_checkpoints_missed_not_due(self):
        posted = (datetime.now() - timedelta(hours=96)).strftime("%Y-%m-%d %H:%M")
        self.crm("ran", f"V{self.vid}", "--at", posted, "--followers", "500")
        code, out, err = self.crm("status")
        self.assertEqual(code, 0, err)
        self.assertIn("24h missed", out)   # 96h > 1.5 x 24h: that moment passed
        self.assertIn("72h DUE", out)      # still inside its window
        self.assertIn("no data at all", out)

    def test_status_hides_settled_runs_but_keeps_dataless_ones(self):
        # 12 days old with an ad hoc snapshot: everything settled, no nagging
        posted = (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d %H:%M")
        self.crm("ran", f"V{self.vid}", "--at", posted, "--followers", "500")
        self.crm("log", "-i", "100", "--cp", "adhoc")
        code, out, err = self.crm("status")
        self.assertEqual(code, 0, err)
        self.assertNotIn(f"V{self.vid}", out)

        # same age but zero data: still shown, still worth a snapshot
        self.crm("draft", "copy-paste-tax", "--body", "second variant body")
        v2 = self.one("SELECT id FROM variants ORDER BY id DESC")["id"]
        self.crm("ran", f"V{v2}", "--at", posted, "--followers", "500")
        code, out, err = self.crm("status")
        self.assertIn(f"V{v2}", out)
        self.assertIn("no data at all", out)


if __name__ == "__main__":
    unittest.main()
