import sqlite3
import tempfile
import unittest
from pathlib import Path

from council import ledger


def _row_kwargs(**overrides):
    defaults = dict(
        question="will X happen?",
        persona_a="bull",
        persona_b="bear",
        provider_a="codex",
        provider_b="claude",
        judge_provider="claude",
        case_a="case a text",
        case_b="case b text",
        rebuttal_a="rebuttal a",
        rebuttal_b="rebuttal b",
        position1_side="A",
        winner="A",
        confidence=0.7,
        key_reason="reason",
        would_change_mind="new data",
        judge_raw="{}",
        rec_a_wins=0,
        rec_a_resolved=0,
        rec_b_wins=0,
        rec_b_resolved=0,
    )
    defaults.update(overrides)
    return defaults


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ledger.db"

    def tearDown(self):
        self._tmp.cleanup()

    def _insert(self, **overrides):
        return ledger.insert(self.path, **_row_kwargs(**overrides))

    # -- insert / count -----------------------------------------------

    def test_insert_and_count(self):
        self.assertEqual(ledger.count(self.path), 0)
        row_id = self._insert()
        self.assertEqual(row_id, 1)
        self.assertEqual(ledger.count(self.path), 1)
        row_id2 = self._insert()
        self.assertEqual(row_id2, 2)
        self.assertEqual(ledger.count(self.path), 2)

    def test_insert_requires_snapshot_columns(self):
        kwargs = _row_kwargs()
        for key in ("rec_a_wins", "rec_a_resolved", "rec_b_wins", "rec_b_resolved"):
            bad = dict(kwargs)
            del bad[key]
            with self.assertRaises(TypeError):
                ledger.insert(self.path, **bad)

    def test_schema_has_c1_snapshot_columns(self):
        self._insert(rec_a_wins=2, rec_a_resolved=3, rec_b_wins=1, rec_b_resolved=4)
        conn = sqlite3.connect(str(self.path))
        row = conn.execute(
            "SELECT rec_a_wins, rec_a_resolved, rec_b_wins, rec_b_resolved FROM questions"
        ).fetchone()
        conn.close()
        self.assertEqual(row, (2, 3, 1, 4))

    def test_pragmas_applied(self):
        self._insert()
        conn = sqlite3.connect(str(self.path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal")

    # -- resolve --------------------------------------------------------

    def test_resolve_updates_outcome_and_returns_previous(self):
        row_id = self._insert()
        previous = ledger.resolve(self.path, row_id, "A")
        self.assertIsNone(previous)
        previous2 = ledger.resolve(self.path, row_id, "B")
        self.assertEqual(previous2, "A")

    def test_resolve_bad_id_raises(self):
        with self.assertRaises(ledger.LedgerError):
            ledger.resolve(self.path, 999, "A")

    def test_resolve_bad_value_raises(self):
        row_id = self._insert()
        with self.assertRaises(ledger.LedgerError):
            ledger.resolve(self.path, row_id, "C")
        with self.assertRaises(ledger.LedgerError):
            ledger.resolve(self.path, row_id, "a")  # case sensitive

    # -- record -----------------------------------------------------------

    def test_record_win_rate(self):
        row_id = self._insert(persona_a="bull", persona_b="bear")
        ledger.resolve(self.path, row_id, "A")
        rec_bull = ledger.record(self.path, "bull")
        self.assertEqual(rec_bull, {"wins": 1, "resolved": 1, "rate": 1.0})
        rec_bear = ledger.record(self.path, "bear")
        self.assertEqual(rec_bear, {"wins": 0, "resolved": 1, "rate": 0.0})

    def test_record_no_resolved_rows_is_no_division(self):
        self._insert()
        rec = ledger.record(self.path, "bull")
        self.assertEqual(rec, {"wins": 0, "resolved": 0, "rate": None})

    def test_record_unknown_persona_is_empty(self):
        self._insert()
        rec = ledger.record(self.path, "nobody")
        self.assertEqual(rec, {"wins": 0, "resolved": 0, "rate": None})

    # -- B3: neither / empty behaviors -------------------------------------

    def test_neither_excluded_from_record_but_counts_in_resolved_total(self):
        row_id = self._insert()
        ledger.resolve(self.path, row_id, "neither")
        rec = ledger.record(self.path, "bull")
        self.assertEqual(rec["resolved"], 0)
        stats = ledger.history(self.path)
        self.assertEqual(stats["resolved_total"], 1)
        self.assertEqual(stats["total_rows"], 1)

    def test_neither_excluded_from_judge_accuracy_and_brier(self):
        row_id = self._insert(winner="A", confidence=0.9)
        ledger.resolve(self.path, row_id, "neither")
        stats = ledger.history(self.path)
        self.assertIsNone(stats["judge"]["accuracy"])
        self.assertEqual(stats["judge"]["accuracy_n"], 0)
        self.assertIsNone(stats["judge"]["brier"])
        self.assertEqual(stats["judge"]["brier_n"], 0)

    def test_history_on_empty_db(self):
        stats = ledger.history(self.path)
        self.assertEqual(stats["total_rows"], 0)
        self.assertEqual(stats["resolved_total"], 0)
        self.assertEqual(stats["personas"], {})
        self.assertIsNone(stats["judge"]["accuracy"])
        self.assertIsNone(stats["judge"]["brier"])
        self.assertEqual(stats["last_rows"], [])

    # -- Brier / accuracy --------------------------------------------------

    def test_brier_and_accuracy(self):
        # winner A, confidence 0.8, outcome A -> p=0.8, y=1 -> (0.2)^2 = 0.04, correct
        row1 = self._insert(winner="A", confidence=0.8)
        ledger.resolve(self.path, row1, "A")
        # winner B, confidence 0.6, outcome A -> p=1-0.6=0.4, y=1 -> (0.6)^2=0.36, wrong
        row2 = self._insert(winner="B", confidence=0.6)
        ledger.resolve(self.path, row2, "A")

        stats = ledger.history(self.path)
        judge = stats["judge"]
        self.assertEqual(judge["accuracy_n"], 2)
        self.assertAlmostEqual(judge["accuracy"], 0.5)
        self.assertEqual(judge["brier_n"], 2)
        self.assertAlmostEqual(judge["brier"], (0.04 + 0.36) / 2)

    # -- A1: judge_same_side computed at read time -------------------------

    def test_judge_same_side_computed_at_read_time(self):
        # judge shares provider with side A; winner A -> match
        self._insert(provider_a="claude", provider_b="codex", judge_provider="claude", winner="A")
        # judge shares provider with side B; winner B -> match
        self._insert(provider_a="codex", provider_b="claude", judge_provider="claude", winner="B")
        # judge shares provider with side A; winner B -> no match
        self._insert(provider_a="claude", provider_b="codex", judge_provider="claude", winner="B")

        stats = ledger.history(self.path)
        judge = stats["judge"]
        self.assertEqual(judge["same_side_total"], 3)
        self.assertEqual(judge["same_side_matches"], 2)

    # -- C1: better-record-followed stat uses snapshot columns only --------

    def test_better_record_followed_basic(self):
        # A had the better snapshot record (3/4 vs 1/4); judge picked A -> match
        self._insert(
            winner="A",
            rec_a_wins=3, rec_a_resolved=4,
            rec_b_wins=1, rec_b_resolved=4,
        )
        stats = ledger.history(self.path)
        self.assertEqual(stats["better_record_followed"], {"matches": 1, "total": 1})

    def test_better_record_followed_excludes_empty_and_tied_records(self):
        self._insert(winner="A", rec_a_wins=0, rec_a_resolved=0, rec_b_wins=0, rec_b_resolved=0)
        self._insert(winner="A", rec_a_wins=2, rec_a_resolved=4, rec_b_wins=2, rec_b_resolved=4)
        stats = ledger.history(self.path)
        self.assertEqual(stats["better_record_followed"], {"matches": 0, "total": 0})

    def test_c1_resolving_earlier_row_does_not_change_later_rows_stat(self):
        # Row 1 (earlier) has no snapshot record yet -> excluded either way.
        row1 = self._insert(
            winner="A", rec_a_wins=0, rec_a_resolved=0, rec_b_wins=0, rec_b_resolved=0
        )
        # Row 2 (later) was judged with its own snapshot: B had the better
        # record (3/4 vs 1/4) and the judge picked B -> match.
        row2 = self._insert(
            winner="B", rec_a_wins=1, rec_a_resolved=4, rec_b_wins=3, rec_b_resolved=4
        )
        stats_before = ledger.history(self.path)
        self.assertEqual(stats_before["better_record_followed"], {"matches": 1, "total": 1})

        # Resolving the EARLIER row for real must not touch row2's snapshot
        # or its contribution to the stat.
        ledger.resolve(self.path, row1, "A")
        stats_after = ledger.history(self.path)
        self.assertEqual(stats_after["better_record_followed"], {"matches": 1, "total": 1})

    def test_c1_resolving_the_row_itself_does_not_change_its_own_snapshot(self):
        row_id = self._insert(
            winner="A", rec_a_wins=3, rec_a_resolved=4, rec_b_wins=1, rec_b_resolved=4
        )
        stats_before = ledger.history(self.path)
        ledger.resolve(self.path, row_id, "B")  # real-world outcome differs from snapshot logic
        stats_after = ledger.history(self.path)
        self.assertEqual(stats_before["better_record_followed"], stats_after["better_record_followed"])


if __name__ == "__main__":
    unittest.main()
