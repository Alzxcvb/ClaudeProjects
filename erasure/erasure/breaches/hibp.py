"""Thin client around the HaveIBeenPwned v3 API.

HIBP requires a paid API key ($3.95/mo minimum as of 2026-04). We read it
from the `HIBP_API_KEY` env var. No key → typed error so the CLI can print
a helpful install note instead of crashing with an HTTP 401.

We pass `truncateResponse=false` so we get the full breach metadata in one
request (name, title, domain, breach date, pwn count, data classes).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx

from erasure.breaches.schema import BreachesManifest, BreachHit

BREACHES_DIR = Path("state/breaches")

_HIBP_BASE = "https://haveibeenpwned.com/api/v3"
_USER_AGENT = "erasure-cli (https://github.com/Alzxcvb/ClaudeProjects)"

# Minimal RFC-5322-ish email check; HIBP itself validates, we just guard
# against obviously bogus inputs before spending a request on them.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class HIBPNotConfigured(RuntimeError):
    """Raised when HIBP_API_KEY is missing."""


class HIBPRateLimited(RuntimeError):
    """Raised when HIBP returns 429."""


class HIBPFailed(RuntimeError):
    """Raised for other non-success HIBP responses."""


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email address: {email!r}")


def check_email(
    email: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    _client: Optional[httpx.Client] = None,
) -> List[BreachHit]:
    """Return the list of breaches containing `email`, empty list if clean.

    Raises HIBPNotConfigured if no API key is set. Raises HIBPRateLimited on
    429 so callers can back off. Any other non-2xx becomes HIBPFailed.
    """
    _validate_email(email)
    api_key = api_key or os.environ.get("HIBP_API_KEY")
    if not api_key:
        raise HIBPNotConfigured(
            "HIBP_API_KEY is not set. Get a key at https://haveibeenpwned.com/API/Key "
            "and export it: `export HIBP_API_KEY=...`"
        )

    headers = {
        "hibp-api-key": api_key,
        "user-agent": _USER_AGENT,
    }
    url = f"{_HIBP_BASE}/breachedaccount/{email}"
    params = {"truncateResponse": "false"}

    client = _client or httpx.Client(timeout=timeout)
    close_client = _client is None
    try:
        resp = client.get(url, headers=headers, params=params)
    finally:
        if close_client:
            client.close()

    if resp.status_code == 404:
        return []
    if resp.status_code == 429:
        raise HIBPRateLimited(
            f"HIBP rate limit hit. Retry-After: {resp.headers.get('retry-after', '?')}s"
        )
    if resp.status_code == 401:
        raise HIBPNotConfigured("HIBP rejected the API key (401). Check HIBP_API_KEY.")
    if resp.status_code >= 400:
        raise HIBPFailed(f"HIBP returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    hits: list[BreachHit] = []
    for entry in data:
        hits.append(
            BreachHit(
                name=entry.get("Name", ""),
                title=entry.get("Title", entry.get("Name", "")),
                domain=entry.get("Domain") or None,
                breach_date=entry.get("BreachDate") or None,
                pwn_count=entry.get("PwnCount"),
                data_classes=list(entry.get("DataClasses") or []),
                description=entry.get("Description") or None,
            )
        )
    return hits


def save_manifest(
    email: str, breaches: List[BreachHit], *, scan_dir: Path = BREACHES_DIR
) -> Path:
    scan_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_id = f"breaches_{stamp}"
    manifest = BreachesManifest(
        scan_id=scan_id,
        email=email,
        found_count=len(breaches),
        breaches=breaches,
    )
    path = scan_dir / f"{scan_id}.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def check_and_save(email: str, **kwargs) -> Path:
    """High-level: check HIBP, persist manifest, return the manifest path."""
    hits = check_email(email, **kwargs)
    return save_manifest(email, hits)
