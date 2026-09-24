"""Tests for council.runner. All subprocess calls are monkeypatched via
mock.patch("subprocess.run", ...); no live model calls are made."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from council import runner


class FakeCompletedProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TmpDirMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name) / "council-run"

    def tearDown(self):
        self._tmp.cleanup()


class EnvKeyGuardTest(unittest.TestCase):
    def test_no_keys_present(self):
        self.assertIsNone(runner.check_env_keys(env={}))

    def test_anthropic_key_present(self):
        reason = runner.check_env_keys(env={"ANTHROPIC_API_KEY": "x"})
        self.assertIsNotNone(reason)
        self.assertIn("ANTHROPIC_API_KEY", reason)

    def test_openai_key_present(self):
        reason = runner.check_env_keys(env={"OPENAI_API_KEY": "x"})
        self.assertIsNotNone(reason)
        self.assertIn("OPENAI_API_KEY", reason)

    def test_reads_real_environ_by_default(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}):
            self.assertIsNotNone(runner.check_env_keys())


class ScrubEnvTest(unittest.TestCase):
    def test_scrub_removes_claude_and_key_vars(self):
        fake_env = {
            "CLAUDE_FOO": "1",
            "CLAUDECODE": "1",
            "ANTHROPIC_API_KEY": "x",
            "OPENAI_API_KEY": "y",
            "PATH": "/usr/bin",
            "HOME": "/home/alex",
        }
        with mock.patch.dict(os.environ, fake_env, clear=True):
            scrubbed = runner._scrub_env()
        self.assertNotIn("CLAUDE_FOO", scrubbed)
        self.assertNotIn("CLAUDECODE", scrubbed)
        self.assertNotIn("ANTHROPIC_API_KEY", scrubbed)
        self.assertNotIn("OPENAI_API_KEY", scrubbed)
        self.assertIn("PATH", scrubbed)
        self.assertIn("HOME", scrubbed)


class CwdGuardTest(unittest.TestCase):
    def test_refuses_dir_under_dev(self):
        under_dev = Path("/Users/alexandercoffman/Dev/some-council-run-dir")
        reason = runner._guard_cwd(under_dev)
        self.assertIsNotNone(reason)

    def test_refuses_dir_containing_claude_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "CLAUDE.md").write_text("x")
            self.assertIsNotNone(runner._guard_cwd(d))

    def test_refuses_dir_containing_dot_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / ".claude").mkdir()
            self.assertIsNotNone(runner._guard_cwd(d))

    def test_refuses_dir_containing_agents_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "AGENTS.md").write_text("x")
            self.assertIsNotNone(runner._guard_cwd(d))

    def test_allows_clean_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "council-run"
            d.mkdir()
            self.assertIsNone(runner._guard_cwd(d))

    def test_run_claude_refuses_when_cwd_under_dev_without_creating_it(self):
        under_dev = Path("/Users/alexandercoffman/Dev/council-run-should-not-exist")
        self.assertFalse(under_dev.exists())
        with self.assertRaises(runner.CouncilError):
            runner.run_claude("p", "s", run_dir=under_dev)
        # The guard must fire before mkdir, so no stray directory is left
        # under Dev/.
        self.assertFalse(under_dev.exists())


class ArgvCaptureTest(TmpDirMixin, unittest.TestCase):
    def test_run_claude_exact_argv(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            claude_json = '{"type":"result","is_error":false,"result":"ok text"}'
            return FakeCompletedProcess(stdout=claude_json, stderr="", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            text = runner.run_claude("the prompt", "the system", run_dir=self.run_dir)

        self.assertEqual(text, "ok text")
        self.assertEqual(
            captured["argv"],
            [
                "claude", "-p",
                "--output-format", "json",
                "--model", "sonnet",
                "--no-session-persistence",
                "--tools", "",
                "--strict-mcp-config",
                "--disable-slash-commands",
                "--system-prompt", "the system",
                "--", "the prompt",
            ],
        )
        kwargs = captured["kwargs"]
        self.assertEqual(Path(kwargs["cwd"]), self.run_dir)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], runner.PER_CALL_TIMEOUT)
        env = kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertFalse(any(k.startswith("CLAUDE") for k in env))

    def test_run_codex_exact_argv(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            codex_json = (
                '{"type":"item.completed","item":{"type":"agent_message","text":"codex ok"}}\n'
            )
            return FakeCompletedProcess(stdout=codex_json, stderr="", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            text = runner.run_codex("the prompt", "the system", run_dir=self.run_dir)

        self.assertEqual(text, "codex ok")
        self.assertEqual(
            captured["argv"],
            [
                "codex", "exec", "--json", "--skip-git-repo-check",
                "-s", "read-only",
                "-C", str(self.run_dir),
                "-c", "model_reasoning_effort=medium",
                "-c", "web_search=\"disabled\"",
                "--", "the system\n\n---\n\nthe prompt",
            ],
        )
        kwargs = captured["kwargs"]
        self.assertEqual(Path(kwargs["cwd"]), self.run_dir)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], runner.PER_CALL_TIMEOUT)
        env = kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("OPENAI_API_KEY", env)

    def test_codex_argv_with_no_system_prompt_uses_bare_prompt(self):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            codex_json = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
            return FakeCompletedProcess(stdout=codex_json, returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            runner.run_codex("just the prompt", "", run_dir=self.run_dir)

        self.assertEqual(captured["argv"][-1], "just the prompt")


class ErrorCasesTest(TmpDirMixin, unittest.TestCase):
    def test_claude_is_error_raises_council_error(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(
                stdout='{"type":"result","is_error":true,"error":"boom","result":""}',
                stderr="some stderr detail",
                returncode=0,
            )

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_claude("p", "s", run_dir=self.run_dir)
        self.assertIn("boom", str(cm.exception))

    def test_claude_bad_json_raises_council_error_with_stderr(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(stdout="not json", stderr="parse failure detail", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_claude("p", "s", run_dir=self.run_dir)
        self.assertIn("parse failure detail", str(cm.exception))

    def test_codex_turn_failed_raises_council_error(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(
                stdout='{"type":"turn.failed","error":{"message":"exploded"}}\n',
                stderr="stderr tail here",
                returncode=0,
            )

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_codex("p", "s", run_dir=self.run_dir)
        self.assertIn("exploded", str(cm.exception))
        self.assertIn("stderr tail here", str(cm.exception))

    def test_codex_error_event_raises_council_error(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(
                stdout='{"type":"error","message":"sandbox denied: Operation not permitted"}\n',
                stderr="",
                returncode=0,
            )

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_codex("p", "s", run_dir=self.run_dir)
        self.assertIn("Operation not permitted", str(cm.exception))

    def test_nonzero_returncode_raises_council_error_with_stderr(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(stdout="", stderr="explosion on stderr", returncode=1)

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_claude("p", "s", run_dir=self.run_dir)
        self.assertIn("explosion on stderr", str(cm.exception))

    def test_timeout_raises_council_error(self):
        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout", 120))

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError) as cm:
                runner.run_codex("p", "s", run_dir=self.run_dir)
        self.assertIn("timed out", str(cm.exception))

    def test_codex_no_agent_message_raises_council_error(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(stdout='{"type":"turn.completed"}\n', returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(runner.CouncilError):
                runner.run_codex("p", "s", run_dir=self.run_dir)


class LoginGuardTest(TmpDirMixin, unittest.TestCase):
    def test_codex_login_status_checked_on_stdout_and_stderr(self):
        def fake_run(argv, **kwargs):
            self.assertEqual(argv, ["codex", "login", "status"])
            self.assertEqual(Path(kwargs["cwd"]), self.run_dir)
            self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"], runner.GUARD_TIMEOUT)
            # E2: the message is on stderr; stdout is empty.
            return FakeCompletedProcess(stdout="", stderr="Logged in using ChatGPT", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = runner.check_codex_login(run_dir=self.run_dir)
        self.assertIsNone(reason)

    def test_codex_login_status_missing_message_returns_reason(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(stdout="", stderr="not logged in", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = runner.check_codex_login(run_dir=self.run_dir)
        self.assertIsNotNone(reason)

    def test_claude_auth_status_authmethod_match(self):
        def fake_run(argv, **kwargs):
            self.assertEqual(argv, ["claude", "auth", "status"])
            self.assertEqual(kwargs["timeout"], runner.GUARD_TIMEOUT)
            return FakeCompletedProcess(stdout='{"authMethod": "claude.ai"}', stderr="", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = runner.check_claude_auth(run_dir=self.run_dir)
        self.assertIsNone(reason)

    def test_claude_auth_status_authmethod_mismatch(self):
        def fake_run(argv, **kwargs):
            return FakeCompletedProcess(stdout='{"authMethod": "api_key"}', stderr="", returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = runner.check_claude_auth(run_dir=self.run_dir)
        self.assertIsNotNone(reason)


class SubprocessRunnerTest(TmpDirMixin, unittest.TestCase):
    def test_check_auth_reports_codex_failure_first(self):
        def fake_run(argv, **kwargs):
            if argv[0] == "codex":
                return FakeCompletedProcess(stdout="", stderr="not logged in", returncode=0)
            return FakeCompletedProcess(stdout='{"authMethod":"claude.ai"}', returncode=0)

        r = runner.SubprocessRunner(run_dir=self.run_dir)
        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = r.check_auth()
        self.assertIsNotNone(reason)

    def test_check_auth_passes_when_both_ok(self):
        def fake_run(argv, **kwargs):
            if argv[0] == "codex":
                return FakeCompletedProcess(stdout="", stderr="Logged in using ChatGPT", returncode=0)
            return FakeCompletedProcess(stdout='{"authMethod":"claude.ai"}', returncode=0)

        r = runner.SubprocessRunner(run_dir=self.run_dir)
        with mock.patch("subprocess.run", side_effect=fake_run):
            reason = r.check_auth()
        self.assertIsNone(reason)

    def test_call_dispatches_to_provider(self):
        def fake_run(argv, **kwargs):
            if argv[0] == "claude":
                return FakeCompletedProcess(
                    stdout='{"type":"result","is_error":false,"result":"claude says hi"}',
                    returncode=0,
                )
            return FakeCompletedProcess(
                stdout='{"type":"item.completed","item":{"type":"agent_message","text":"codex says hi"}}\n',
                returncode=0,
            )

        r = runner.SubprocessRunner(run_dir=self.run_dir)
        with mock.patch("subprocess.run", side_effect=fake_run):
            self.assertEqual(r.call("claude", "p", "s"), "claude says hi")
            self.assertEqual(r.call("codex", "p", "s"), "codex says hi")

    def test_call_unknown_provider_raises(self):
        r = runner.SubprocessRunner(run_dir=self.run_dir)
        with self.assertRaises(ValueError):
            r.call("bogus", "p", "s")


class TimingTest(unittest.TestCase):
    def test_worst_case_timing_under_bash_ceiling(self):
        # A2/D1: 4 serial steps (cases, rebuttals, judge, judge retry) at
        # 120s each, plus the two 20s guard calls, must fit under Bash's
        # 600s ceiling.
        total = runner.PER_CALL_TIMEOUT * runner.SERIAL_STEPS + 2 * runner.GUARD_TIMEOUT
        self.assertEqual(total, 520)
        self.assertLess(total, 600)


if __name__ == "__main__":
    unittest.main()
