"""Tests for council.debate. FakeRunner never touches a subprocess; it is
keyed by (provider, phase), where phase is inferred from prompt content
since RunnerProtocol.call() is (provider, prompt, system) with no phase
argument. Also covers the A1 4-run rotation invariant."""
import tempfile
import unittest
from pathlib import Path

from council import debate, ledger, personas
from council.runner import CouncilError


class FixedChoiceRng:
    """Minimal double satisfying the only rng method debate.py calls:
    .choice(seq). Lets a test pin position1_side deterministically without
    seed-hunting a real random.Random."""

    def __init__(self, value):
        self._value = value

    def choice(self, seq):
        return self._value


class FakeRunner:
    def __init__(self, judge_responses=None, fail_for=None, case_text=None, rebuttal_text=None):
        self.judge_responses = list(judge_responses) if judge_responses else [
            '{"winner":"1","confidence":0.7,"key_reason":"the clearer case",'
            '"would_change_mind":"new data"}'
        ]
        self.fail_for = fail_for or {}
        self.case_text = case_text or {}
        self.rebuttal_text = rebuttal_text or {}
        self.calls = []  # list of (provider, phase, prompt, system)
        self._judge_call_count = 0

    def _phase(self, prompt):
        if "Return only JSON" in prompt:
            return "judge"
        if "An opposing analyst wrote" in prompt:
            return "rebuttal"
        return "case"

    def call(self, provider, prompt, system):
        phase = self._phase(prompt)
        self.calls.append((provider, phase, prompt, system))
        key = (provider, phase)
        if key in self.fail_for:
            raise self.fail_for[key]
        if phase == "case":
            return self.case_text.get(provider, f"{provider} case: my worldview implies X.")
        if phase == "rebuttal":
            return self.rebuttal_text.get(provider, f"{provider} rebuttal: not so fast.")
        idx = min(self._judge_call_count, len(self.judge_responses) - 1)
        self._judge_call_count += 1
        return self.judge_responses[idx]


class AssignProvidersTest(unittest.TestCase):
    def test_4_run_rotation_invariant(self):
        rows = [debate.assign_providers(n) for n in range(4)]
        judges = [r[2] for r in rows]
        sides_a = [r[0] for r in rows]

        # judge alternates every run
        for i in range(3):
            self.assertNotEqual(judges[i], judges[i + 1])

        # side A's provider flips every 2 runs
        self.assertEqual(sides_a[0], sides_a[1])
        self.assertEqual(sides_a[2], sides_a[3])
        self.assertNotEqual(sides_a[0], sides_a[2])

        # over the 4 runs, judge's provider matches side A twice and side B
        # (which is always the opposite of side A within a row) twice
        matches_a = sum(1 for a, _b, j in rows if a == j)
        matches_b = sum(1 for _a, b, j in rows if b == j)
        self.assertEqual(matches_a, 2)
        self.assertEqual(matches_b, 2)

    def test_exact_expected_sequence(self):
        self.assertEqual(debate.assign_providers(0), ("codex", "claude", "claude"))
        self.assertEqual(debate.assign_providers(1), ("codex", "claude", "codex"))
        self.assertEqual(debate.assign_providers(2), ("claude", "codex", "claude"))
        self.assertEqual(debate.assign_providers(3), ("claude", "codex", "codex"))


class RunDebateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "ledger.db"
        pair = personas.parse_pair(None)
        self.bull, self.bear = pair

    def tearDown(self):
        self._tmp.cleanup()

    def test_end_to_end_inserts_one_row_and_returns_expected_fields(self):
        runner = FakeRunner()
        result = debate.run_debate(
            "will it work?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A")
        )
        self.assertEqual(ledger.count(self.path), 1)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["provider_a"], "codex")
        self.assertEqual(result["provider_b"], "claude")
        self.assertEqual(result["judge_provider"], "claude")
        self.assertEqual(result["winner"], "A")  # position1_side="A", winner "1" -> A
        self.assertAlmostEqual(result["confidence"], 0.7)
        self.assertEqual(result["key_reason"], "the clearer case")

    def test_position1_side_b_maps_verdict_winner_1_to_side_b(self):
        runner = FakeRunner(judge_responses=['{"winner":"1","confidence":0.6,'
                                              '"key_reason":"r","would_change_mind":"c"}'])
        result = debate.run_debate(
            "q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("B")
        )
        self.assertEqual(result["winner"], "B")

    def test_position1_side_b_maps_verdict_winner_2_to_side_a(self):
        runner = FakeRunner(judge_responses=['{"winner":"2","confidence":0.6,'
                                              '"key_reason":"r","would_change_mind":"c"}'])
        result = debate.run_debate(
            "q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("B")
        )
        self.assertEqual(result["winner"], "A")

    def test_no_persona_or_provider_names_reach_the_judge_prompt(self):
        runner = FakeRunner(
            case_text={
                "codex": "I am the Bull, running on Claude via codex. Growth continues.",
                "claude": "I am the Bear and I use GPT-5. Risks are unpriced.",
            },
            rebuttal_text={
                "codex": "As the Bull, I still push back.",
                "claude": "Speaking as Bear, the risk stands.",
            },
        )
        debate.run_debate("q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A"))

        judge_calls = [c for c in runner.calls if c[1] == "judge"]
        self.assertEqual(len(judge_calls), 1)
        judge_prompt = judge_calls[0][2]
        lowered = judge_prompt.lower()
        for forbidden in ("bull", "bear", "claude", "codex", "gpt-5", "gpt5", "anthropic", "openai"):
            self.assertNotIn(forbidden, lowered)

    def test_c1_snapshot_matches_record_shown_to_judge_and_is_frozen(self):
        runner = FakeRunner()
        r1 = debate.run_debate(
            "q1?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A")
        )
        # bull (side A) wins row 1, but it is not yet *resolved* -- record()
        # only counts resolved rows, so the snapshot for row 2 should still
        # be 0/0 for both sides.
        r2 = debate.run_debate(
            "q2?", self.bull, self.bear, FakeRunner(), self.path, FixedChoiceRng("A")
        )
        stats = ledger.history(self.path)
        row2 = next(r for r in stats["last_rows"] if r["id"] == r2["id"])
        self.assertEqual(row2["rec_a_wins"], 0)
        self.assertEqual(row2["rec_a_resolved"], 0)

        # Now resolve row 1 for real, then run a third debate: its snapshot
        # must reflect bull's now-1/1 record, and that record must match
        # what ledger.record() reports right before insert.
        ledger.resolve(self.path, r1["id"], "A")
        pre_record = ledger.record(self.path, self.bull.key)
        r3 = debate.run_debate(
            "q3?", self.bull, self.bear, FakeRunner(), self.path, FixedChoiceRng("A")
        )
        stats2 = ledger.history(self.path)
        row3 = next(r for r in stats2["last_rows"] if r["id"] == r3["id"])
        self.assertEqual(row3["rec_a_wins"], pre_record["wins"])
        self.assertEqual(row3["rec_a_resolved"], pre_record["resolved"])

        # And resolving row1 again afterwards must not retroactively change
        # row3's already-stored snapshot (C1).
        ledger.resolve(self.path, r1["id"], "B")
        stats3 = ledger.history(self.path)
        row3_after = next(r for r in stats3["last_rows"] if r["id"] == r3["id"])
        self.assertEqual(row3_after["rec_a_wins"], row3["rec_a_wins"])
        self.assertEqual(row3_after["rec_a_resolved"], row3["rec_a_resolved"])

    def test_retries_judge_once_on_bad_json_then_succeeds(self):
        runner = FakeRunner(
            judge_responses=[
                "not json at all, sorry",
                '{"winner":"2","confidence":0.55,"key_reason":"r","would_change_mind":"c"}',
            ]
        )
        result = debate.run_debate(
            "q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A")
        )
        judge_calls = [c for c in runner.calls if c[1] == "judge"]
        self.assertEqual(len(judge_calls), 2)
        self.assertIn("Return only JSON, no prose.", judge_calls[1][2])
        self.assertEqual(result["winner"], "B")  # winner "2", position1_side="A" -> B
        self.assertEqual(ledger.count(self.path), 1)

    def test_judge_fails_twice_raises_and_inserts_no_row(self):
        runner = FakeRunner(judge_responses=["garbage one", "garbage two"])
        with self.assertRaises(CouncilError):
            debate.run_debate("q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A"))
        self.assertEqual(ledger.count(self.path), 0)

    def test_case_call_failure_propagates_and_inserts_no_row(self):
        runner = FakeRunner(fail_for={("codex", "case"): CouncilError("codex down")})
        with self.assertRaises(CouncilError):
            debate.run_debate("q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A"))
        self.assertEqual(ledger.count(self.path), 0)

    def test_rebuttal_call_failure_propagates_and_inserts_no_row(self):
        runner = FakeRunner(fail_for={("claude", "rebuttal"): CouncilError("claude down")})
        with self.assertRaises(CouncilError):
            debate.run_debate("q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A"))
        self.assertEqual(ledger.count(self.path), 0)

    def test_persona_a_b_stored_as_keys_not_display_names(self):
        runner = FakeRunner()
        debate.run_debate("q?", self.bull, self.bear, runner, self.path, FixedChoiceRng("A"))
        stats = ledger.history(self.path)
        self.assertIn(self.bull.key, stats["personas"])
        self.assertIn(self.bear.key, stats["personas"])


if __name__ == "__main__":
    unittest.main()
