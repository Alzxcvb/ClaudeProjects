"""Refresh the bundled account-deletion directory from JustDeleteMe.

Upstream (https://justdeleteme.xyz, repo jdm-contrib/jdm, MIT) maintains the
canonical directory of per-service deletion paths. This script pulls their
``_data/sites.json``, drops the localized ``notes_xx`` / ``url_xx`` fields we do
not use (they are the bulk of the 1.2MB payload), layers our local overrides on
top, and writes the snapshot Erasure ships.

The snapshot is committed so the CLI works offline and reproducibly; run this
when the directory goes stale. Upstream takes pull requests, so a correction
belongs in ``deletion_directory_overrides.json`` only while it is in flight.

    python3 scripts/refresh_deletion_directory.py
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx

RAW_URL = "https://raw.githubusercontent.com/jdm-contrib/jdm/master/_data/sites.json"
REPO_API = "https://api.github.com/repos/jdm-contrib/jdm"

ACCOUNTS_DIR = Path(__file__).resolve().parent.parent / "erasure" / "accounts"
OUT = ACCOUNTS_DIR / "deletion_directory.json"
OVERRIDES = ACCOUNTS_DIR / "deletion_directory_overrides.json"

# The fields we keep. Everything else upstream carries is per-language copy.
KEEP = ("name", "url", "difficulty", "notes", "domains", "email", "email_subject", "email_body")

DIFFICULTY_LEGEND = {
    "easy": "Self-service delete button, completes quickly.",
    "medium": "Deletion is offered but takes extra steps, a wait, or leaves content behind.",
    "hard": "Hidden flow, a support ticket, or contacting customer service.",
    "limited": "Deletion only for people covered by a privacy law (CCPA, GDPR), and the service verifies it. Send a legal request: erasure legal request.",
    "impossible": "No deletion path; the best you can do is scrub the data.",
}


def _slim(entry: dict) -> dict:
    out = {k: entry[k] for k in KEEP if entry.get(k)}
    out.setdefault("domains", [])
    return out


def main() -> None:
    meta = httpx.get(REPO_API, timeout=30).json()
    upstream_pushed_at = meta.get("pushed_at")

    r = httpx.get(RAW_URL, follow_redirects=True, timeout=60)
    r.raise_for_status()
    services = [_slim(e) for e in r.json()]

    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")).get("services", [])
    by_name = {s["name"].strip().lower(): i for i, s in enumerate(services)}
    added = replaced = 0
    for entry in overrides:
        key = entry["name"].strip().lower()
        if key in by_name:
            services[by_name[key]] = _slim(entry)
            replaced += 1
        else:
            services.append(_slim(entry))
            added += 1

    services.sort(key=lambda s: s["name"].strip().lower())

    payload = {
        "source": "https://justdeleteme.xyz",
        "source_repo": "https://github.com/jdm-contrib/jdm",
        "license": (
            "MIT (c) 2013-2020 Robb Lewis, The JDM Contrib Team, & various contributors. "
            "Full text in LICENSE-justdeleteme, next to this file."
        ),
        "upstream_pushed_at": upstream_pushed_at,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "local_overrides": {"replaced": replaced, "added": added},
        "count": len(services),
        "difficulty_legend": DIFFICULTY_LEGEND,
        "services": services,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    size = OUT.stat().st_size
    print(f"Saved {len(services):,} services ({size:,} bytes) → {OUT}")
    print(f"  Upstream last pushed: {upstream_pushed_at}")
    print(f"  Local overrides: {replaced} replaced, {added} added")
    counts: dict[str, int] = {}
    for s in services:
        counts[s.get("difficulty", "?")] = counts.get(s.get("difficulty", "?"), 0) + 1
    print("  By difficulty: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"  With an email deletion path: {sum(1 for s in services if s.get('email')):,}")


if __name__ == "__main__":
    main()
