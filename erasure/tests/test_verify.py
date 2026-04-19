"""Tests for the verify diff logic."""

import json
from pathlib import Path
from typing import Optional

from erasure.verify.diff import diff_scans


def _write_scan(scans_dir: Path, scan_id: str, rows: list[dict]) -> None:
    scans_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "scan_id": scan_id,
        "started_at": "2026-04-19T00:00:00Z",
        "broker_count": len(rows),
        "name_match_count": sum(1 for r in rows if r["name_match"]),
        "error_count": sum(1 for r in rows if r.get("error")),
        "results": rows,
    }
    (scans_dir / f"{scan_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _row(name: str, match: bool, error: Optional[str] = None) -> dict:
    return {
        "broker_name": name,
        "opt_out_url": f"https://{name.lower()}.test/opt-out",
        "name_match": match,
        "matched_variants": ["Test User"] if match else [],
        "html_path": f"state/scans/artifacts/{name}.html",
        "screenshot_path": f"state/scans/artifacts/{name}.png",
        "fetched_at": "20260419T000000Z",
        "error": error,
    }


def test_diff_resolved_and_persistent(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    scans_dir = tmp_path / "state" / "scans"
    _write_scan(scans_dir, "scan_base", [_row("A", True), _row("B", True)])
    _write_scan(scans_dir, "scan_verify", [_row("A", False), _row("B", True)])

    summary = diff_scans("scan_base", "scan_verify")
    assert summary["resolved"] == 1
    assert summary["persistent"] == 1
    assert summary["new"] == 0


def test_diff_new_regression(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    scans_dir = tmp_path / "state" / "scans"
    _write_scan(scans_dir, "scan_base", [_row("A", False)])
    _write_scan(scans_dir, "scan_verify", [_row("A", True)])

    summary = diff_scans("scan_base", "scan_verify")
    assert summary["new"] == 1
    assert summary["resolved"] == 0


def test_diff_errors_are_flagged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    scans_dir = tmp_path / "state" / "scans"
    _write_scan(scans_dir, "scan_base", [_row("A", True)])
    _write_scan(scans_dir, "scan_verify", [_row("A", False, error="TimeoutError")])

    summary = diff_scans("scan_base", "scan_verify")
    assert summary["errored"] == 1
