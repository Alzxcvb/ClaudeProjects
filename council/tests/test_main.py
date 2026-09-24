import contextlib
import io
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from council import ledger
from council.__main__ import build_parser, main


class FakeRunner:
    """Minimal stand-in for runner.SubprocessRunner: never calls a real
    subprocess. call() intentionally raises if invoked, so it can only be
    used for paths that must fail before reaching a model call (env-key
    guard, auth guard, bad --pair)."""

    def __init__(self, auth_reason=None):
        self._auth_reason = auth_reason
        self.call_count = 0

    def call(self, provider, prompt, system):  # pragma: no cover - guard
        self.call_count += 1
        raise AssertionError("call() should not be invoked when a guard should have stopped ask")

    def check_auth(self):
        return self._auth_reason


class ScriptedRunner:
    """A FakeRunner that completes a full debate (task 7 wiring): case and
    rebuttal calls return simple canned text, and the judge call returns
    valid JSON naming Position 1 the winner (by default)."""

    def __init__(self, auth_reason=None, judge_json=None):
        self._auth_reason = auth_reason
        self._judge_json = judge_json or (
            '{"winner":"1","confidence":0.75,"key_reason":"the clearer case",'
            '"would_change_mind":"new data"}'
        )
        self.calls = []

    def check_auth(self):
        return self._auth_reason

    def call(self, provider, prompt, system):
        self.calls.append((provider, prompt, system))
        if "Return only JSON" in prompt:
            return self._judge_json
        return f"a case or rebuttal from {provider}, no names."


def _insert_row(path, **overrides):
    defaults = dict(
        question="will X happen?",
        persona_a="bull",
        persona_b="bear",
        provider_a="codex",
        provider_b="claude",
        judge_provider="claude",
        case_a="a", case_b="b", rebuttal_a="ra", rebuttal_b="rb",
        position1_side="A", winner="A", confidence=0.6,
        key_reason="r", would_change_mind="c", judge_raw="{}",
        rec_a_wins=0, rec_a_resolved=0, rec_b_wins=0, rec_b_resolved=0,
    )
    defaults.update(overrides)
    return ledger.insert(path, **defaults)


class ParserTest(unittest.TestCase):
    def test_positional_question_parses(self):
        args = build_parser().parse_args(["ask", "what is up"])
        self.assertEqual(args.question, "what is up")
        self.assertIsNone(args.question_file)

    def test_question_file_flag_parses(self):
        args = build_parser().parse_args(["ask", "--question-file", "/tmp/q.txt"])
        self.assertIsNone(args.question)
        self.assertEqual(args.question_file, "/tmp/q.txt")

    def test_ask_requires_question_or_file(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["ask"])

    def test_ask_rejects_both_question_and_file(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["ask", "q", "--question-file", "/tmp/q.txt"])

    def test_pair_flag_defaults_to_none(self):
        args = build_parser().parse_args(["ask", "q"])
        self.assertIsNone(args.pair)

    def test_pair_flag_parses(self):
        args = build_parser().parse_args(["ask", "q", "--pair", "bear,bull"])
        self.assertEqual(args.pair, "bear,bull")

    def test_resolve_parses_id_and_outcome(self):
        args = build_parser().parse_args(["resolve", "3", "A"])
        self.assertEqual(args.id, 3)
        self.assertEqual(args.outcome, "A")

    def test_history_parses(self):
        args = build_parser().parse_args(["history"])
        self.assertEqual(args.command, "history")


class MainHelpTest(unittest.TestCase):
    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_no_subcommand_prints_help_and_returns_zero(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("usage", buf.getvalue().lower())


class SpendGuardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self._tmp.name) / "ledger.db"

    def tearDown(self):
        self._tmp.cleanup()

    def test_env_guard_blocks_history_on_anthropic_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}):
            code = main(["history"], ledger_path=self.ledger_path)
        self.assertEqual(code, 2)

    def test_env_guard_blocks_resolve_on_openai_key(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}):
            code = main(["resolve", "1", "A"], ledger_path=self.ledger_path)
        self.assertEqual(code, 2)

    def test_env_guard_blocks_ask(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}):
            code = main(["ask", "q"], runner=FakeRunner(), ledger_path=self.ledger_path)
        self.assertEqual(code, 2)

    def test_env_guard_checked_before_auth_guard(self):
        # If both would fail, the env guard (checked first, per A3) is what
        # reports -- the FakeRunner's check_auth must never even run.
        fake = FakeRunner(auth_reason="should not be reached")
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}):
            code = main(["ask", "q"], runner=fake, ledger_path=self.ledger_path)
        self.assertEqual(code, 2)

    def test_no_keys_present_env_guard_passes(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            code = main(["history"], ledger_path=self.ledger_path)
        self.assertEqual(code, 0)


class AskCommandTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self._tmp.name) / "ledger.db"
        # Ensure no real spend-guard key is set for these tests.
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def tearDown(self):
        self._env_patch.stop()
        self._tmp.cleanup()

    def test_ask_blocked_by_auth_guard(self):
        fake = FakeRunner(auth_reason="codex not logged in")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = main(["ask", "question?"], runner=fake, ledger_path=self.ledger_path)
        self.assertEqual(code, 2)
        self.assertIn("codex not logged in", buf.getvalue())

    def test_ask_runs_full_debate_and_prints_ruling(self):
        fake = ScriptedRunner(auth_reason=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(
                ["ask", "question?"],
                runner=fake,
                ledger_path=self.ledger_path,
                rng=random.Random(1),
            )
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("question #1", out)
        self.assertIn("Winner:", out)
        self.assertIn("Confidence:", out)
        self.assertIn("Key reason:", out)
        self.assertIn("Would change its mind if:", out)
        self.assertIn("/council resolve 1 A|B|neither", out)
        self.assertEqual(ledger.count(self.ledger_path), 1)

    def test_ask_bad_pair_returns_1_before_any_model_call(self):
        fake = FakeRunner(auth_reason=None)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = main(
                ["ask", "q", "--pair", "bull,nonexistent"],
                runner=fake,
                ledger_path=self.ledger_path,
            )
        self.assertEqual(code, 1)
        self.assertEqual(fake.call_count, 0)

    def test_ask_reads_question_file(self):
        qfile = Path(self._tmp.name) / "q.txt"
        qfile.write_text("will it rain tomorrow?\n")
        fake = ScriptedRunner(auth_reason=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(
                ["ask", "--question-file", str(qfile)],
                runner=fake,
                ledger_path=self.ledger_path,
                rng=random.Random(2),
            )
        self.assertEqual(code, 0)
        self.assertIn("will it rain tomorrow?", buf.getvalue())

    def test_ask_missing_question_file_returns_1(self):
        fake = FakeRunner(auth_reason=None)
        code = main(
            ["ask", "--question-file", "/nonexistent/path/q.txt"],
            runner=fake,
            ledger_path=self.ledger_path,
        )
        self.assertEqual(code, 1)

    def test_ask_council_error_from_debate_prints_stderr_and_inserts_no_row(self):
        fake = ScriptedRunner(auth_reason=None, judge_json="not json at all")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = main(
                ["ask", "q"],
                runner=fake,
                ledger_path=self.ledger_path,
                rng=random.Random(3),
            )
        self.assertEqual(code, 1)
        self.assertIn("judge", buf.getvalue().lower())
        self.assertEqual(ledger.count(self.ledger_path), 0)

    def test_main_accepts_rng_param(self):
        code = main(["history"], ledger_path=self.ledger_path, rng=random.Random(42))
        self.assertEqual(code, 0)

    def test_ask_then_resolve_then_history_chain(self):
        # §7 task 7 pass criterion, run as one chain: ask prints an id,
        # resolving that id then shows up in history under the winning
        # persona's record -- proving the persona key `ask` writes is the
        # same one `history` reads back.
        fake = ScriptedRunner(auth_reason=None)
        code = main(
            ["ask", "q"], runner=fake, ledger_path=self.ledger_path, rng=random.Random(7)
        )
        self.assertEqual(code, 0)

        code = main(["resolve", "1", "A"], ledger_path=self.ledger_path)
        self.assertEqual(code, 0)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["history"], ledger_path=self.ledger_path)
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("1 questions asked, 1 resolved", output)
        self.assertIn("bull: 1/1 wins (100%)", output)


class ResolveHistoryWiringTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self._tmp.name) / "ledger.db"
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def tearDown(self):
        self._env_patch.stop()
        self._tmp.cleanup()

    def test_history_on_empty_db_prints_no_questions_yet(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["history"], ledger_path=self.ledger_path)
        self.assertEqual(code, 0)
        self.assertIn("no questions yet", buf.getvalue())

    def test_resolve_bad_id_exits_1(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = main(["resolve", "999", "A"], ledger_path=self.ledger_path)
        self.assertEqual(code, 1)

    def test_resolve_bad_outcome_value_exits_1(self):
        row_id = _insert_row(self.ledger_path)
        code = main(["resolve", str(row_id), "Z"], ledger_path=self.ledger_path)
        self.assertEqual(code, 1)

    def test_resolve_then_history_round_trip(self):
        row_id = _insert_row(self.ledger_path, persona_a="bull", persona_b="bear", winner="A")
        code = main(["resolve", str(row_id), "A"], ledger_path=self.ledger_path)
        self.assertEqual(code, 0)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["history"], ledger_path=self.ledger_path)
        output = buf.getvalue()
        self.assertIn("1 questions asked, 1 resolved", output)
        self.assertIn("bull: 1/1 wins (100%)", output)

    def test_persona_with_zero_resolved_shows_no_resolved_record(self):
        _insert_row(self.ledger_path, persona_a="bull", persona_b="bear")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["history"], ledger_path=self.ledger_path)
        output = buf.getvalue()
        self.assertIn("bull: no resolved record", output)
        self.assertIn("bear: no resolved record", output)




class PositionKeyTest(unittest.TestCase):
    def test_position_key_maps_positions_to_sides(self):
        from types import SimpleNamespace
        from council.__main__ import _format_position_key
        r = {"position1_side": "B",
             "persona_a": SimpleNamespace(name="Bull"),
             "persona_b": SimpleNamespace(name="Bear")}
        self.assertEqual(_format_position_key(r),
                         "(Judge saw Position 1 = Side B Bear, Position 2 = Side A Bull)")

if __name__ == "__main__":
    unittest.main()
