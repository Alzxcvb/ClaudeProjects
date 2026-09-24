"""Blocking subprocess runner for `claude -p` and `codex exec`.

Parsing logic (claude result/is_error, codex item.completed -> agent_message,
turn.failed/error) is copied from Command's runtimes
(command/agents/runtimes/claude_code.py, codex.py) per the Fable plan's
"Import vs copy: copy" decision. This module is a blocking
subprocess.run(timeout=) wrapper returning one string, NOT Command's
Popen/event-file streaming design, because Council needs one call per
phase, not a live event stream.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Protocol

# A2/D1: per-call and guard-call timeouts, and the serial-step count used to
# prove worst-case timing fits under the 600s Bash ceiling.
PER_CALL_TIMEOUT = 120
GUARD_TIMEOUT = 20
SERIAL_STEPS = 4  # cases (parallel) -> rebuttals (parallel) -> judge -> judge retry

RUN_DIR = Path(tempfile.gettempdir()) / "council-run"

DEV_ROOT = Path("/Users/alexandercoffman/Dev")

_ENV_SPEND_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


class CouncilError(Exception):
    """Raised when a model or guard subprocess call fails. Carries a
    trimmed stderr tail (E1) so a sandbox denial or auth failure is visible
    to the caller instead of silently swallowed."""

    def __init__(self, message: str, stderr_tail: str = ""):
        self.stderr_tail = stderr_tail
        full = message if not stderr_tail else f"{message}\nstderr: {stderr_tail}"
        super().__init__(full)


def check_env_keys(env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """A3, first check, before any model call, for every subcommand. Reads
    the real environment when `env` is None; tests pass an explicit dict so
    they don't have to mutate process env to exercise this."""
    source = os.environ if env is None else env
    found = [k for k in _ENV_SPEND_KEYS if source.get(k)]
    if found:
        return (
            "refusing to run: "
            + " and ".join(found)
            + " set in the environment (Council is a zero API spend tool)"
        )
    return None


def _scrub_env() -> Dict[str, str]:
    """Drop every var starting CLAUDE plus the API keys, so a call made from
    inside a Claude Code session doesn't inherit ~190K tokens of context or
    any credential (brief-council.md constraints)."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CLAUDE") or key in _ENV_SPEND_KEYS:
            env.pop(key, None)
    return env


def _guard_cwd(run_dir: Path) -> Optional[str]:
    """Refuse a run_dir under Dev/, or one that contains CLAUDE.md/.claude/
    AGENTS.md, so a nested claude call never picks up this repo's memory
    (measured live: ~36K extra tokens from Dev's CLAUDE.md alone)."""
    resolved = run_dir.resolve()
    resolved_str = str(resolved).lower()
    dev_str = str(DEV_ROOT.resolve() if DEV_ROOT.exists() else DEV_ROOT).lower()
    if resolved_str == dev_str or resolved_str.startswith(dev_str + os.sep):
        return f"refusing to run with cwd under Dev: {resolved}"
    for marker in ("CLAUDE.md", ".claude", "AGENTS.md"):
        if (resolved / marker).exists():
            return f"refusing to run: cwd contains {marker}: {resolved}"
    return None


def _log_call(provider: str, cwd: Path) -> None:
    # Emitted before subprocess.run so a hang or timeout still leaves a
    # trace of what was attempted.
    print(f"[council] provider={provider} cwd={cwd}", file=sys.stderr)


def _claude_argv(prompt: str, system: str, model: str = "sonnet") -> list:
    # Live-tested amendment (plan-council.md): the "--" before the prompt is
    # required, or --tools (variadic) swallows the prompt.
    return [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--no-session-persistence",
        "--tools", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--system-prompt", system,
        "--", prompt,
    ]


def _codex_argv(prompt: str, system: str, run_dir: Path) -> list:
    # B2: codex also needs "--" before the prompt. Codex has no
    # system-prompt flag, so fold system + prompt into one positional
    # (matches command/agents/runtimes/codex.py:35).
    folded = prompt if not system else f"{system}\n\n---\n\n{prompt}"
    return [
        "codex", "exec", "--json", "--skip-git-repo-check",
        "-s", "read-only",
        "-C", str(run_dir),
        "-c", "model_reasoning_effort=medium",
        "-c", "web_search=\"disabled\"",  # v1: no auto research, keep both sides on equal footing
        "--", folded,
    ]


def _extract_claude_text(stdout: str, stderr: str) -> str:
    # Copied parsing logic from claude_code.py:156-169 (result/is_error),
    # adapted from streamed events to one JSON blob.
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CouncilError(
            f"claude: could not parse JSON stdout ({exc})", (stderr or stdout)[-500:]
        ) from exc
    if isinstance(data, list):
        result = next((item for item in data if item.get("type") == "result"), None)
        if result is None:
            raise CouncilError("claude: no type==result item in JSON list output", stderr[-500:])
        data = result
    if data.get("is_error"):
        raise CouncilError(f"claude: is_error set: {data.get('error')}", stderr[-500:])
    text = data.get("result", "")
    if not text:
        raise CouncilError("claude: empty result text", stderr[-500:])
    return text


def _extract_codex_text(stdout: str, stderr: str) -> str:
    # Copied parsing logic from codex.py:64-85 (item.completed/agent_message,
    # turn.failed, error). Plan says "last" agent_message, not the joined
    # text codex.py's streaming design accumulates.
    last_message = None
    failed_msg = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type", "")
        if etype == "item.completed":
            item = evt.get("item") or {}
            if item.get("type") == "agent_message":
                text = item.get("text", "")
                if text:
                    last_message = text
        elif etype == "turn.failed":
            err = evt.get("error") or {}
            failed_msg = err.get("message", "turn.failed")
        elif etype == "error":
            failed_msg = evt.get("message", "error")
    if failed_msg:
        raise CouncilError(f"codex: {failed_msg}", stderr[-500:])
    if last_message is None:
        raise CouncilError("codex: no agent_message found in output", stderr[-500:])
    return last_message


def run_claude(
    prompt: str,
    system: str,
    *,
    run_dir: Path = RUN_DIR,
    timeout: int = PER_CALL_TIMEOUT,
    model: str = "sonnet",
) -> str:
    guard_reason = _guard_cwd(run_dir)
    if guard_reason:
        raise CouncilError(guard_reason)
    run_dir.mkdir(parents=True, exist_ok=True)
    argv = _claude_argv(prompt, system, model=model)
    env = _scrub_env()
    _log_call("claude", run_dir)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(run_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stderr or "")[-500:] if isinstance(exc.stderr, str) else ""
        raise CouncilError(f"claude: timed out after {timeout}s", tail) from exc
    if proc.returncode != 0:
        raise CouncilError(f"claude: exit {proc.returncode}", (proc.stderr or "")[-500:])
    return _extract_claude_text(proc.stdout, proc.stderr)


def run_codex(
    prompt: str,
    system: str,
    *,
    run_dir: Path = RUN_DIR,
    timeout: int = PER_CALL_TIMEOUT,
) -> str:
    guard_reason = _guard_cwd(run_dir)
    if guard_reason:
        raise CouncilError(guard_reason)
    run_dir.mkdir(parents=True, exist_ok=True)
    argv = _codex_argv(prompt, system, run_dir)
    env = _scrub_env()
    _log_call("codex", run_dir)
    try:
        proc = subprocess.run(
            argv,
            cwd=str(run_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stderr or "")[-500:] if isinstance(exc.stderr, str) else ""
        raise CouncilError(f"codex: timed out after {timeout}s", tail) from exc
    if proc.returncode != 0:
        raise CouncilError(f"codex: exit {proc.returncode}", (proc.stderr or "")[-500:])
    return _extract_codex_text(proc.stdout, proc.stderr)


def check_codex_login(*, run_dir: Path = RUN_DIR, timeout: int = GUARD_TIMEOUT) -> Optional[str]:
    """A3/C2/E2: `codex login status` must report "Logged in using ChatGPT".
    E2: that text is on stderr, stdout is empty -- check both, combined."""
    run_dir.mkdir(parents=True, exist_ok=True)
    env = _scrub_env()
    try:
        proc = subprocess.run(
            ["codex", "login", "status"],
            cwd=str(run_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "codex login status timed out"
    except FileNotFoundError:
        return "codex binary not found on PATH"
    combined = (proc.stdout or "") + (proc.stderr or "")
    if "Logged in using ChatGPT" not in combined:
        return f"codex not logged in via ChatGPT: {combined[-300:]!r}"
    return None


def check_claude_auth(*, run_dir: Path = RUN_DIR, timeout: int = GUARD_TIMEOUT) -> Optional[str]:
    """A3/C2: `claude auth status` JSON must have authMethod == "claude.ai"."""
    run_dir.mkdir(parents=True, exist_ok=True)
    env = _scrub_env()
    try:
        proc = subprocess.run(
            ["claude", "auth", "status"],
            cwd=str(run_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "claude auth status timed out"
    except FileNotFoundError:
        return "claude binary not found on PATH"
    combined = (proc.stdout or "") + (proc.stderr or "")
    ok = False
    try:
        data = json.loads(proc.stdout)
        ok = isinstance(data, dict) and data.get("authMethod") == "claude.ai"
    except json.JSONDecodeError:
        ok = '"authMethod": "claude.ai"' in combined or '"authMethod":"claude.ai"' in combined
    if not ok:
        return f"claude not authenticated via claude.ai: {combined[-300:]!r}"
    return None


class RunnerProtocol(Protocol):
    """Shape debate.py (task 6, out of this scope) needs so it can accept a
    FakeRunner in tests instead of the real SubprocessRunner."""

    def call(self, provider: str, prompt: str, system: str) -> str:
        ...

    def check_auth(self) -> Optional[str]:
        ...


class SubprocessRunner:
    """Default Runner: talks to the real `claude` and `codex` CLIs."""

    def __init__(self, run_dir: Path = RUN_DIR):
        self.run_dir = run_dir

    def call(self, provider: str, prompt: str, system: str) -> str:
        if provider == "claude":
            return run_claude(prompt, system, run_dir=self.run_dir)
        if provider == "codex":
            return run_codex(prompt, system, run_dir=self.run_dir)
        raise ValueError(f"unknown provider: {provider!r}")

    def check_auth(self) -> Optional[str]:
        """A3: codex login status, then claude auth status (C2: same
        RUN_DIR cwd, scrubbed env, stdin DEVNULL, GUARD_TIMEOUT)."""
        reason = check_codex_login(run_dir=self.run_dir)
        if reason:
            return reason
        return check_claude_auth(run_dir=self.run_dir)
