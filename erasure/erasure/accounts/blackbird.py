"""Subprocess wrapper around the `blackbird` OSINT CLI.

Alternative backend to sherlock.py. Activate via:
    ERASURE_ACCOUNTS_BACKEND=blackbird erasure accounts find <username>

Why Blackbird exists here:
  Sherlock (current default) scans ~400 platforms via username only, using HTTP-presence
  checks that produce false positives when a page loads but no account exists. Blackbird
  (github.com/p1ngul1n0/blackbird) scans 600+ platforms, supports BOTH username (-u)
  and email (-e) in a single tool, and uses response-body parsing to reduce false hits.
  The email path is natively supported (no holehe needed), which would let us unify the
  'erasure accounts find' and 'erasure emails find' commands under one binary.

Install (verify exact package name at github.com/p1ngul1n0/blackbird):
    pipx install blackbird-osint
    OR: pip install git+https://github.com/p1ngul1n0/blackbird

Implementation guide for the next session that picks this up:
  1. run_blackbird(username, ...) -> tuple[str, int, Optional[bytes]]
       Mirror run_sherlock() in sherlock.py.
       CLI: blackbird -u <username> --json --output <file>
       Capture stdout + parse the JSON output file (more structured than Sherlock's CSV).
  2. parse_blackbird_json(output_path: Path) -> List[AccountHit]
       Read the JSON Blackbird writes. Map its site/url fields to AccountHit.
       Check the current repo output schema — it has evolved across versions.
  3. scan_username(username: str, **kwargs) -> Path
       Call run_blackbird, parse, call save_manifest() from sherlock.py (schema is shared).
  4. scan_email(email: str, **kwargs) -> Path  [bonus, no Sherlock equivalent]
       CLI: blackbird -e <email> --json --output <file>
       Same parse + manifest pattern.

Shell-injection defense: apply the same _USERNAME_RE validation from sherlock.py before
building the subprocess command. For email, validate with a simple RFC-5321 regex.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class BlackbirdNotInstalled(RuntimeError):
    """Raised when the `blackbird` binary is not on PATH."""


class BlackbirdFailed(RuntimeError):
    """Raised when blackbird exits with a non-zero status and no parseable output."""


def scan_username(username: str, **kwargs) -> Path:
    raise NotImplementedError(
        "Blackbird backend is not yet implemented. "
        "See erasure/accounts/blackbird.py for the implementation guide. "
        "To fall back to Sherlock, unset ERASURE_ACCOUNTS_BACKEND."
    )


def scan_email(email: str, **kwargs) -> Path:
    raise NotImplementedError(
        "Blackbird email scan is not yet implemented. "
        "See erasure/accounts/blackbird.py for the implementation guide."
    )
