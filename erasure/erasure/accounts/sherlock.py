"""Subprocess wrapper around the `sherlock` OSINT CLI.

Design: Sherlock runs in its own environment (install via `pipx install
sherlock-project`). We invoke the binary, parse stdout, and discard the text
file Sherlock writes to the working directory. We never import Sherlock in
process — keeps its dependency graph (pandas, numpy, openpyxl, stem) out of
Erasure's env.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from erasure.accounts.schema import AccountHit, AccountsManifest

ACCOUNTS_DIR = Path("state/accounts")

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_HIT_RE = re.compile(r"^\[\+\]\s+(?P<site>[^:]+):\s+(?P<url>https?://\S+)\s*$")


class SherlockNotInstalled(RuntimeError):
    """Raised when the `sherlock` binary is not on PATH."""


class SherlockFailed(RuntimeError):
    """Raised when sherlock exits with a non-zero status and no parseable output."""


def parse_found(stdout: str) -> List[AccountHit]:
    """Extract `[+] Site: URL` lines from Sherlock stdout."""
    hits: list[AccountHit] = []
    for line in stdout.splitlines():
        m = _HIT_RE.match(line)
        if m:
            hits.append(AccountHit(site=m.group("site").strip(), url=m.group("url").strip()))
    return hits


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 1–64 chars of letters, digits, dot, underscore, or hyphen."
        )


def run_sherlock(
    username: str,
    *,
    timeout_per_site: int = 15,
    overall_timeout: int = 900,
    extra_args: Optional[list[str]] = None,
    _runner=subprocess.run,
) -> tuple[str, int]:
    """Invoke `sherlock <username> --print-found --no-color ...`.

    Returns (stdout, return_code). Writes Sherlock's incidental text file into
    a temp dir so it doesn't pollute CWD. Raises SherlockNotInstalled if the
    binary is not on PATH.
    """
    _validate_username(username)
    with tempfile.TemporaryDirectory() as td:
        out_file = Path(td) / f"{username}.txt"
        cmd = [
            "sherlock",
            username,
            "--print-found",
            "--no-color",
            "--timeout",
            str(timeout_per_site),
            "--output",
            str(out_file),
        ]
        if extra_args:
            cmd.extend(extra_args)
        try:
            proc = _runner(
                cmd,
                capture_output=True,
                text=True,
                timeout=overall_timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise SherlockNotInstalled(
                "sherlock binary not found on PATH. Install with: `pipx install sherlock-project`"
            ) from exc
        return proc.stdout, proc.returncode


def save_manifest(username: str, hits: List[AccountHit], *, scan_dir: Path = ACCOUNTS_DIR) -> Path:
    scan_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_id = f"accounts_{stamp}"
    manifest = AccountsManifest(
        scan_id=scan_id,
        username=username,
        found_count=len(hits),
        hits=hits,
    )
    path = scan_dir / f"{scan_id}.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def scan_username(username: str, **kwargs) -> Path:
    """High-level entrypoint: run Sherlock, parse, persist manifest. Returns manifest path."""
    stdout, rc = run_sherlock(username, **kwargs)
    hits = parse_found(stdout)
    if rc != 0 and not hits:
        raise SherlockFailed(
            f"sherlock exited with code {rc} and no hits were parsed. stdout (truncated):\n"
            f"{stdout[:800]}"
        )
    return save_manifest(username, hits)
