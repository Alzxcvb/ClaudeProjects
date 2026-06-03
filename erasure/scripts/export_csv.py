#!/usr/bin/env python3
"""Export broker and DROP records from state/ to CSV.

Reads all .json files from state/brokers/ and state/drop/ directories,
extracts broker_name, status, submitted_at, and url columns, and writes
to state/export.csv.
"""

import csv
import json
from pathlib import Path


def extract_record(data: dict) -> dict:
    """Extract relevant fields from a JSON record.

    Handles both broker and DROP receipt formats.
    Returns: {broker_name, status, submitted_at, url}
    """
    return {
        "broker_name": data.get("broker_name") or data.get("name") or "",
        "status": data.get("status") or "",
        "submitted_at": data.get("submitted_at") or "",
        "url": data.get("opt_out_url") or data.get("portal_url") or "",
    }


def export_to_csv(output_path: Path) -> int:
    """Read all JSON files and export to CSV.

    Args:
        output_path: Path where CSV will be written

    Returns:
        Number of rows written (excluding header)
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    brokers_dir = project_root / "state" / "brokers"
    drop_dir = project_root / "state" / "drop"

    records = []

    # Read broker JSON files
    if brokers_dir.exists():
        for json_file in brokers_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                records.append(extract_record(data))
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {json_file}: {e}")

    # Read drop JSON files
    if drop_dir.exists():
        for json_file in drop_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                records.append(extract_record(data))
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read {json_file}: {e}")

    # Write CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["broker_name", "status", "submitted_at", "url"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    return len(records)


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output = project_root / "state" / "export.csv"
    row_count = export_to_csv(output)
    print(f"Wrote {row_count} rows to {output}")
