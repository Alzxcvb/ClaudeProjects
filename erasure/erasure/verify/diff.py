"""Compare two scans to verify broker compliance post-DROP.

The CA Delete Act requires registered brokers to process deletion requests
within 90 days. This module diffs a baseline scan (pre-DROP) against a
verification scan (45–90 days post-DROP) and flags:

  - resolved: name present in baseline, absent in verify → broker complied
  - persistent: name present in both → broker non-compliant (evidence for CPPA)
  - new: name absent in baseline, present in verify → regression
  - unchanged_absent: name absent in both (nothing to remove)
  - errored: scan failure at either end

Output is JSON + human-readable summary; the persistent set feeds complaint
artifacts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from erasure.brokers.scan import SCANS_DIR, load_scan

VerifyStatus = Literal["resolved", "persistent", "new", "unchanged_absent", "errored"]
VERIFY_DIR = Path("state/verify")


@dataclass
class BrokerVerification:
    broker_name: str
    status: VerifyStatus
    baseline_match: bool
    verify_match: bool
    baseline_variants: list[str]
    verify_variants: list[str]
    baseline_screenshot: str
    verify_screenshot: str


def diff_scans(baseline_id: str, verify_id: str) -> dict:
    baseline = load_scan(baseline_id)
    verify = load_scan(verify_id)

    baseline_by_name = {r["broker_name"]: r for r in baseline["results"]}
    verify_by_name = {r["broker_name"]: r for r in verify["results"]}

    names = sorted(set(baseline_by_name) | set(verify_by_name))
    verifications: list[BrokerVerification] = []

    for name in names:
        b = baseline_by_name.get(name)
        v = verify_by_name.get(name)
        if b is None or v is None:
            continue
        if b.get("error") or v.get("error"):
            status: VerifyStatus = "errored"
        elif b["name_match"] and not v["name_match"]:
            status = "resolved"
        elif b["name_match"] and v["name_match"]:
            status = "persistent"
        elif not b["name_match"] and v["name_match"]:
            status = "new"
        else:
            status = "unchanged_absent"

        verifications.append(BrokerVerification(
            broker_name=name,
            status=status,
            baseline_match=b["name_match"],
            verify_match=v["name_match"],
            baseline_variants=b["matched_variants"],
            verify_variants=v["matched_variants"],
            baseline_screenshot=b["screenshot_path"],
            verify_screenshot=v["screenshot_path"],
        ))

    summary = {
        "baseline_id": baseline_id,
        "verify_id": verify_id,
        "resolved": sum(1 for x in verifications if x.status == "resolved"),
        "persistent": sum(1 for x in verifications if x.status == "persistent"),
        "new": sum(1 for x in verifications if x.status == "new"),
        "unchanged_absent": sum(1 for x in verifications if x.status == "unchanged_absent"),
        "errored": sum(1 for x in verifications if x.status == "errored"),
        "verifications": [v.__dict__ for v in verifications],
    }

    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VERIFY_DIR / f"verify_{baseline_id}_vs_{verify_id}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
