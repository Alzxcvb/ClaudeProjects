"""Subprocess wrapper around the `holehe` OSINT CLI.

Same pattern as our Sherlock wrapper: we invoke the binary, parse stdout,
validate input before shelling out, and persist results as a manifest so
the dashboard can render them. We never import holehe in process — keeps
its dependency graph out of Erasure's env.

holehe's stdout prefixes:
  [+] site.com  → account exists
  [-] site.com  → account does not exist
  [x] site.com  → rate-limited / error
We keep only the [+] hits.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from erasure.emails.schema import EmailHit, EmailsManifest

EMAILS_DIR = Path("state/emails")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HIT_RE = re.compile(r"^\s*\[\+\]\s+(?P<site>\S+)\s*$")


class HoleheNotInstalled(RuntimeError):
    """Raised when the `holehe` binary is not on PATH."""


class HoleheFailed(RuntimeError):
    """Raised when holehe exits non-zero with no parseable output."""


def parse_found(stdout: str) -> List[EmailHit]:
    """Extract `[+] site` lines from holehe stdout."""
    hits: list[EmailHit] = []
    seen: set[str] = set()
    for line in stdout.splitlines():
        m = _HIT_RE.match(line)
        if not m:
            continue
        site = m.group("site").strip()
        if site in seen:
            continue
        seen.add(site)
        hits.append(EmailHit(site=site))
    return hits


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email address: {email!r}")


def run_holehe(
    email: str,
    *,
    overall_timeout: int = 900,
    extra_args: Optional[list[str]] = None,
    _runner=subprocess.run,
) -> tuple[str, int]:
    """Invoke holehe and return (stdout, return_code).

    Raises HoleheNotInstalled if the binary isn't on PATH.
    """
    _validate_email(email)
    cmd = ["holehe", "--only-used", "--no-color", email]
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
        raise HoleheNotInstalled(
            "holehe binary not found on PATH. Install with: `pipx install holehe`"
        ) from exc
    return proc.stdout, proc.returncode


def save_manifest(
    email: str,
    hits: List[EmailHit],
    *,
    scan_dir: Path = EMAILS_DIR,
    parse_source: Optional[str] = None,
) -> Path:
    scan_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_id = f"emails_{stamp}"
    manifest = EmailsManifest(
        scan_id=scan_id,
        email=email,
        found_count=len(hits),
        hits=hits,
        parse_source=parse_source,
    )
    path = scan_dir / f"{scan_id}.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def scan_email(email: str, **kwargs) -> Path:
    """High-level entrypoint: run holehe, parse, persist manifest."""
    stdout, rc = run_holehe(email, **kwargs)
    hits = parse_found(stdout)
    if rc != 0 and not hits:
        raise HoleheFailed(
            f"holehe exited with code {rc} and no hits were parsed.\n"
            f"stdout (truncated):\n{stdout[:800]}"
        )
    return save_manifest(email, hits, parse_source="stdout" if hits else None)
