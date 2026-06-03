#!/usr/bin/env python3
"""Check for stale broker records in state/ directory.

Walks state/ recursively, reads all .json files, and identifies broker records
where the last_checked timestamp (or equivalent field) is more than 30 days
before today. Treats missing timestamps as stale.

Common timestamp field names checked: last_checked, checked_at, updated_at,
fetched_at, started_at.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import json


def get_timestamp_from_record(record: dict) -> Optional[datetime]:
    """Extract timestamp from broker record.

    Checks for common timestamp field names and returns the first found as a
    datetime object. Returns None if no recognized timestamp field exists.
    """
    timestamp_fields = ["last_checked", "checked_at", "updated_at", "fetched_at", "started_at"]

    for field in timestamp_fields:
        if field in record:
            value = record[field]
            if isinstance(value, str):
                try:
                    # Handle ISO format timestamps (with or without timezone)
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

    return None


def is_stale(timestamp: Optional[datetime], reference_date: datetime, days_threshold: int = 30) -> bool:
    """Check if a timestamp is more than days_threshold days old.

    Returns True if timestamp is None (missing) or older than threshold.
    """
    if timestamp is None:
        return True

    # Ensure both datetimes are timezone-aware for comparison
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)

    age = reference_date - timestamp
    return age > timedelta(days=days_threshold)


def check_staleness(state_dir: Path = None, reference_date: datetime = None) -> tuple[list[str], int]:
    """Walk state/ directory and return stale broker names and count.

    Args:
        state_dir: Path to state directory. Defaults to ./state/ or state/ relative to script.
        reference_date: Date to compare against. Defaults to today (2026-04-22).

    Returns:
        Tuple of (list of stale broker names, total stale count)
    """
    if state_dir is None:
        # Try to find state directory
        possible_paths = [
            Path("state"),
            Path(__file__).parent.parent / "state",
        ]
        for p in possible_paths:
            if p.exists():
                state_dir = p
                break
        if state_dir is None:
            state_dir = Path("state")

    if reference_date is None:
        # 2026-04-22 as specified in requirements
        reference_date = datetime(2026, 4, 22, 0, 0, 0, tzinfo=timezone.utc)

    stale_brokers: list[str] = []

    if not state_dir.exists():
        print(f"State directory not found: {state_dir}")
        return stale_brokers, 0

    # Walk state directory recursively
    for json_file in state_dir.rglob("*.json"):
        try:
            content = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading {json_file}: {e}")
            continue

        # Handle different JSON structures
        # Could be a single record or a list of records or a dict with "results" key
        records_to_check = []

        if isinstance(content, dict):
            # Check if it's a single broker record or has nested structure
            if "broker_name" in content:
                # Single record
                records_to_check = [content]
            elif "results" in content and isinstance(content["results"], list):
                # Scan manifest or similar structure
                records_to_check = content["results"]
            elif "verifications" in content and isinstance(content["verifications"], list):
                # Verification results structure
                records_to_check = content["verifications"]
        elif isinstance(content, list):
            records_to_check = content

        # Check each record
        for record in records_to_check:
            if not isinstance(record, dict):
                continue

            broker_name = record.get("broker_name")
            if not broker_name:
                continue

            timestamp = get_timestamp_from_record(record)
            if is_stale(timestamp, reference_date):
                stale_brokers.append(broker_name)

    return stale_brokers, len(stale_brokers)


if __name__ == "__main__":
    stale_brokers, total = check_staleness()

    if stale_brokers:
        print("Stale brokers (not checked in 30+ days):")
        for broker in sorted(set(stale_brokers)):  # deduplicate and sort
            print(f"  - {broker}")

    print(f"\nTotal stale: {total}")

    if total == 0:
        print("No stale brokers found.")
