"""Subprocess wrapper around the `sherlock` OSINT CLI.

Design: Sherlock runs in its own environment (install via `pipx install
sherlock-project`). We invoke the binary, parse stdout, and discard the text
file Sherlock writes to the working directory. We never import Sherlock in
process — keeps its dependency graph (pandas, numpy, openpyxl, stem) out of
Erasure's env.
"""

from __future__ import annotations

import csv
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

# Column aliases we'll accept in Sherlock's CSV output.
# Sherlock can evolve headers across versions; this list captures the sane options
# we've seen or reasonably expect. If none match, we fall back to stdout regex.
_CSV_SITE_COLS = ("name", "site", "site_name")
_CSV_URL_COLS = ("url_user", "user_url", "url", "profile_url")
_CSV_FOUND_COLS = ("exists", "found", "status")
_CSV_FOUND_TRUE_VALUES = {"claimed", "found", "true", "yes", "1"}


class SherlockNotInstalled(RuntimeError):
    """Raised when the `sherlock` binary is not on PATH."""


class SherlockFailed(RuntimeError):
    """Raised when sherlock exits with a non-zero status and no parseable output."""


def parse_found(stdout: str) -> List[AccountHit]:
    """Fallback parser: extract `[+] Site: URL` lines from Sherlock stdout.

    Used when CSV parsing fails or the CSV file is missing. Stdout format is the
    least stable contract (meant for humans) — prefer parse_csv_found when a CSV
    file is available.
    """
    hits: list[AccountHit] = []
    for line in stdout.splitlines():
        m = _HIT_RE.match(line)
        if m:
            hits.append(AccountHit(site=m.group("site").strip(), url=m.group("url").strip()))
    return hits


def _first_present(row: dict, candidates: tuple[str, ...]) -> Optional[str]:
    """Return row[k] for the first k in candidates that exists (case-insensitive)."""
    lowered = {k.lower(): k for k in row.keys()}
    for cand in candidates:
        actual = lowered.get(cand.lower())
        if actual is not None:
            val = row[actual]
            if val is not None and val != "":
                return val
    return None


def parse_csv_found(csv_path: Path) -> List[AccountHit]:
    """Preferred parser: read Sherlock's --csv output by column headers.

    Resilient to column additions and reorderings. We look up site and URL
    across a list of known column-name aliases, so a rename from e.g.
    `url_user` to `profile_url` doesn't immediately break us. If a hit-filter
    column exists (exists/found/status), we respect it; otherwise, we assume
    the file only contains found rows (we pass --print-found).

    Raises FileNotFoundError if the CSV doesn't exist, ValueError if no
    recognized site/URL columns are present.
    """
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV at {csv_path} has no header row")
        headers_lower = {h.lower() for h in reader.fieldnames}
        if not (headers_lower & {c.lower() for c in _CSV_SITE_COLS}):
            raise ValueError(
                f"CSV at {csv_path} has no recognized site column. Headers: {reader.fieldnames}"
            )
        if not (headers_lower & {c.lower() for c in _CSV_URL_COLS}):
            raise ValueError(
                f"CSV at {csv_path} has no recognized URL column. Headers: {reader.fieldnames}"
            )

        has_found_col = bool(headers_lower & {c.lower() for c in _CSV_FOUND_COLS})
        hits: list[AccountHit] = []
        for row in reader:
            if has_found_col:
                found_val = _first_present(row, _CSV_FOUND_COLS)
                if found_val is None or str(found_val).strip().lower() not in _CSV_FOUND_TRUE_VALUES:
                    continue
            site = _first_present(row, _CSV_SITE_COLS)
            url = _first_present(row, _CSV_URL_COLS)
            if site and url:
                hits.append(AccountHit(site=site.strip(), url=url.strip()))
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
) -> tuple[str, int, Optional[bytes]]:
    """Invoke Sherlock with CSV output and return (stdout, return_code, csv_bytes).

    We pass --csv so the structured file is the primary parse source; stdout
    remains the fallback. Runs inside a temp dir so incidental files never
    pollute CWD. csv_bytes is None if Sherlock didn't write the expected CSV.
    Raises SherlockNotInstalled if the binary isn't on PATH.
    """
    _validate_username(username)
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        out_file = td_path / f"{username}.txt"
        cmd = [
            "sherlock",
            username,
            "--print-found",
            "--no-color",
            "--csv",
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
                cwd=str(td_path),
            )
        except FileNotFoundError as exc:
            raise SherlockNotInstalled(
                "sherlock binary not found on PATH. Install with: `pipx install sherlock-project`"
            ) from exc

        # Sherlock writes its CSV to CWD with a version-dependent name
        # (historically `<username>.csv`). Glob broadly so we're robust to
        # that filename drifting.
        csv_bytes: Optional[bytes] = None
        csv_candidates = sorted(td_path.glob("*.csv"))
        if csv_candidates:
            csv_bytes = csv_candidates[0].read_bytes()

        return proc.stdout, proc.returncode, csv_bytes


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
    """High-level entrypoint: run Sherlock, parse, persist manifest.

    Parser preference: CSV (structured, stable) → stdout regex (fallback).
    Returns the manifest path.
    """
    stdout, rc, csv_bytes = run_sherlock(username, **kwargs)

    hits: List[AccountHit] = []
    parse_source = "unknown"
    if csv_bytes:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_bytes)
            tmp_path = Path(tmp.name)
        try:
            hits = parse_csv_found(tmp_path)
            parse_source = "csv"
        except (ValueError, FileNotFoundError):
            # Header set we don't recognize (Sherlock schema drift) or bad file.
            # Fall through to stdout regex.
            hits = []
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    if not hits:
        hits = parse_found(stdout)
        if hits:
            parse_source = "stdout"

    if rc != 0 and not hits:
        raise SherlockFailed(
            f"sherlock exited with code {rc} and no hits were parsed (CSV + stdout both empty). "
            f"stdout (truncated):\n{stdout[:800]}"
        )

    manifest_path = save_manifest(username, hits)
    # Record which parser won for forensics; harmless if the field is unused.
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        data["parse_source"] = parse_source
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (OSError, ValueError):
        pass
    return manifest_path
