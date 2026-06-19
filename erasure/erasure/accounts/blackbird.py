"""Subprocess wrapper around the `blackbird` OSINT CLI.

Alternative backend to sherlock.py. Activate via:
    ERASURE_ACCOUNTS_BACKEND=blackbird erasure accounts find <username>

Email scanning (no Sherlock equivalent):
    ERASURE_ACCOUNTS_BACKEND=blackbird erasure emails find <email>
    (once the emails CLI command is wired up)

Install:
    pip install git+https://github.com/p1ngul1n0/blackbird
    or: pipx install blackbird-osint
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from erasure.accounts.schema import AccountHit
from erasure.accounts.sherlock import ACCOUNTS_DIR, save_manifest

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
# Simplified RFC-5321: local-part@domain with at least one dot in domain
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class BlackbirdNotInstalled(RuntimeError):
    """Raised when the `blackbird` binary is not on PATH."""


class BlackbirdFailed(RuntimeError):
    """Raised when blackbird exits non-zero and no parseable output was found."""


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 1-64 chars of letters, digits, dot, underscore, or hyphen."
        )


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise ValueError("Email address did not pass basic RFC-5321 format check.")


def parse_blackbird_json(data: dict) -> List[AccountHit]:
    """Parse Blackbird's JSON export into AccountHit objects.

    Handles known schema variants across Blackbird versions. Blackbird's schema
    has evolved; this tries the most common shapes before giving up gracefully.
    """
    hits: list[AccountHit] = []

    # Locate the list of site results under any known top-level key
    sites: list = []
    for key in ("sites", "results", "data", "accounts"):
        val = data.get(key)
        if isinstance(val, list):
            sites = val
            break

    for site in sites:
        if not isinstance(site, dict):
            continue

        # Determine whether this site reported a found account
        status = site.get("status")
        found = False
        if isinstance(status, dict):
            sid = status.get("id")
            msg = str(status.get("message", "")).lower()
            desc = str(status.get("description", "")).lower()
            found = sid == 1 or "found" in msg or "found" in desc
        elif isinstance(status, str):
            found = status.lower() in {"found", "claimed", "yes", "1"}
        elif isinstance(status, bool):
            found = status

        if not found:
            continue

        name = (
            site.get("name") or site.get("site") or site.get("site_name") or ""
        ).strip()
        url = (
            site.get("uri_check")
            or site.get("url")
            or site.get("profile_url")
            or site.get("uri")
            or ""
        ).strip()

        if name and url:
            hits.append(AccountHit(site=name, url=url))

    return hits


def run_blackbird(
    target: str,
    flag: str,
    *,
    timeout: int = 900,
    extra_args: Optional[list[str]] = None,
    _runner=subprocess.run,
) -> tuple[str, int, Optional[bytes]]:
    """Invoke Blackbird and return (stdout, return_code, json_bytes).

    flag must be "-u" (username) or "-e" (email).
    Runs inside a temp dir so incidental output files never pollute CWD.
    json_bytes is the raw content of the first .json file Blackbird writes,
    or None if no JSON file was created.
    Raises BlackbirdNotInstalled if the binary is not on PATH.
    """
    cmd = ["blackbird", flag, target, "--json"]
    if extra_args:
        cmd.extend(extra_args)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        try:
            proc = _runner(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                cwd=str(td_path),
            )
        except FileNotFoundError as exc:
            raise BlackbirdNotInstalled(
                "blackbird binary not found on PATH. "
                "Install with: pip install git+https://github.com/p1ngul1n0/blackbird"
            ) from exc

        # Blackbird writes results to its own subdirectory inside CWD
        json_bytes: Optional[bytes] = None
        json_candidates = sorted(td_path.rglob("*.json"))
        if json_candidates:
            json_bytes = json_candidates[0].read_bytes()

        return proc.stdout, proc.returncode, json_bytes


def _parse_output(stdout: str, json_bytes: Optional[bytes]) -> List[AccountHit]:
    """Try JSON file first, fall back to stdout if it looks like JSON."""
    if json_bytes:
        try:
            data = json.loads(json_bytes.decode("utf-8", errors="replace"))
            hits = parse_blackbird_json(data)
            if hits:
                return hits
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # Blackbird may print JSON directly to stdout in some versions
    stripped = stdout.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                data = {"sites": data}
            return parse_blackbird_json(data)
        except (json.JSONDecodeError, KeyError):
            pass

    return []


def scan_username(username: str, **kwargs) -> Path:
    """Run Blackbird username scan, persist manifest, return manifest path."""
    _validate_username(username)
    stdout, rc, json_bytes = run_blackbird(username, "-u", **kwargs)
    hits = _parse_output(stdout, json_bytes)

    if rc != 0 and not hits:
        raise BlackbirdFailed(
            f"blackbird exited with code {rc} and no hits were parsed. "
            f"stdout (truncated):\n{stdout[:800]}"
        )

    return save_manifest(username, hits)


def scan_email(email: str, **kwargs) -> Path:
    """Run Blackbird email scan, persist manifest, return manifest path.

    No Sherlock equivalent — this path requires the Blackbird backend.
    The email is stored in the manifest's 'username' field as a
    practical shortcut until AccountsManifest gains an email-specific schema.
    """
    _validate_email(email)
    stdout, rc, json_bytes = run_blackbird(email, "-e", **kwargs)
    hits = _parse_output(stdout, json_bytes)

    if rc != 0 and not hits:
        raise BlackbirdFailed(
            f"blackbird exited with code {rc} and no hits were parsed. "
            f"stdout (truncated):\n{stdout[:800]}"
        )

    return save_manifest(email, hits)
