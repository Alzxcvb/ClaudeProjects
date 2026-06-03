#!/usr/bin/env python3
"""Statistics collector for erasure project state directory.

Recursively walks state/ directory, collects all .json files, and computes:
- Total scan files (accounts + breaches manifests)
- Total brokers found (sum of found_count from manifests)
- Total opted-out (DropReceipt with status in ['submitted', 'complete', 'completed'])
- Accuracy rate (opted_out / brokers_found)
"""

from __future__ import annotations

import json
from pathlib import Path


def collect_stats(state_dir: Path) -> dict:
    """Walk state_dir recursively and collect statistics from all .json files."""
    stats = {
        "scan_files": 0,
        "brokers_found": 0,
        "opted_out": 0,
    }

    if not state_dir.exists():
        return stats

    for json_file in state_dir.rglob("*.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to read {json_file}: {e}")
            continue

        # Count scan files (AccountsManifest and BreachesManifest have scan_id and found_count)
        if isinstance(data, dict):
            # Check for AccountsManifest or BreachesManifest (both have scan_id and found_count)
            if "scan_id" in data and "found_count" in data:
                stats["scan_files"] += 1
                stats["brokers_found"] += data.get("found_count", 0)

            # Count opted-out (DropReceipt with status in submitted/complete/completed)
            if "status" in data and data["status"] in ("submitted", "complete", "completed"):
                stats["opted_out"] += 1

    return stats


def compute_accuracy_rate(brokers_found: int, opted_out: int) -> float:
    """Compute accuracy rate with division by zero handling."""
    if brokers_found == 0:
        return 0.0
    return opted_out / brokers_found


def print_summary(stats: dict) -> None:
    """Print a formatted summary table."""
    scan_files = stats["scan_files"]
    brokers_found = stats["brokers_found"]
    opted_out = stats["opted_out"]
    accuracy_rate = compute_accuracy_rate(brokers_found, opted_out)

    print("\n" + "=" * 60)
    print("Erasure Project Statistics")
    print("=" * 60)
    print(f"{'Scan Files':<30} {scan_files:>10}")
    print(f"{'Total Brokers Found':<30} {brokers_found:>10}")
    print(f"{'Total Opted-Out':<30} {opted_out:>10}")
    print("-" * 60)
    print(f"{'Accuracy Rate':<30} {accuracy_rate:>10.1%}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    state_dir = Path(__file__).parent.parent / "state"
    stats = collect_stats(state_dir)
    print_summary(stats)
