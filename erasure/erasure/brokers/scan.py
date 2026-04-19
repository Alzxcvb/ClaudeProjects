"""Lightweight broker scan.

Purpose: capture evidence artifacts (screenshot + HTML snapshot) of broker
opt-out pages so we have a before/after record around a DROP submission.
This is not per-broker automation — that's the long-tail roadmap. This is
the supplement layer: DROP fans out the deletion request, Erasure documents
whether the user's data is present before and after.

Positive-match heuristic: we grep the rendered HTML for name variants.
False positives are expected (e.g. a broker's homepage listing news articles
that happen to contain the name). The artifact itself is the point — a human
or legal team can review screenshots for a CPPA complaint if brokers ignore
the DROP request.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from erasure.brokers.registry import BrokerEntry
from erasure.browser.session import BrowserSession
from erasure.profile import UserProfile

SCANS_DIR = Path("state/scans")
ARTIFACTS_DIR = Path("state/scans/artifacts")


@dataclass
class ScanResult:
    broker_name: str
    opt_out_url: str
    name_match: bool
    matched_variants: list[str]
    html_path: str
    screenshot_path: str
    fetched_at: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "broker_name": self.broker_name,
            "opt_out_url": self.opt_out_url,
            "name_match": self.name_match,
            "matched_variants": self.matched_variants,
            "html_path": self.html_path,
            "screenshot_path": self.screenshot_path,
            "fetched_at": self.fetched_at,
            "error": self.error,
        }


async def scan_broker(
    broker: BrokerEntry,
    profile: UserProfile,
    scan_id: str,
    browser_profile: str = "scan",
    timeout_ms: int = 30_000,
) -> ScanResult:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = broker.name.lower().replace(" ", "_").replace("/", "_")
    base = ARTIFACTS_DIR / f"{scan_id}_{safe_name}_{stamp}"
    html_path = str(base) + ".html"
    png_path = str(base) + ".png"

    variants = profile.to_search_variants()
    matched: list[str] = []
    error: Optional[str] = None

    try:
        async with BrowserSession(profile_name=browser_profile, headless=True) as ctx:
            page = await ctx.new_page()
            await page.goto(broker.opt_out_url or "", wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass  # Some broker pages never reach networkidle — snapshot anyway.
            html = await page.content()
            Path(html_path).write_text(html, encoding="utf-8")
            await page.screenshot(path=png_path, full_page=True)

            lower = html.lower()
            for v in variants:
                if v.lower() in lower:
                    matched.append(v)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    return ScanResult(
        broker_name=broker.name,
        opt_out_url=broker.opt_out_url or "",
        name_match=bool(matched),
        matched_variants=matched,
        html_path=html_path,
        screenshot_path=png_path,
        fetched_at=stamp,
        error=error,
    )


async def scan_brokers(
    brokers: list[BrokerEntry],
    profile: UserProfile,
    concurrency: int = 3,
) -> tuple[str, list[ScanResult]]:
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"

    sem = asyncio.Semaphore(concurrency)

    async def _one(b: BrokerEntry) -> ScanResult:
        async with sem:
            return await scan_broker(b, profile, scan_id)

    results = await asyncio.gather(*[_one(b) for b in brokers])

    manifest = {
        "scan_id": scan_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "broker_count": len(brokers),
        "name_match_count": sum(1 for r in results if r.name_match),
        "error_count": sum(1 for r in results if r.error),
        "results": [r.to_dict() for r in results],
    }
    (SCANS_DIR / f"{scan_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return scan_id, results


def load_scan(scan_id: str) -> dict:
    path = SCANS_DIR / f"{scan_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_scans() -> list[dict]:
    if not SCANS_DIR.exists():
        return []
    out = []
    for p in sorted(SCANS_DIR.glob("scan_*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out
