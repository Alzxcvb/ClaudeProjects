"""Tests for the dashboard and evidence-report renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from erasure.report.html import (
    DASHBOARD_TEMPLATE,
    _EVIDENCE_MARKER,
    latest_receipt_path,
    latest_scan_path,
    latest_verify_path,
    render_dashboard,
)


def _scan_payload(scan_id: str, rows: list[dict]) -> dict:
    return {
        "scan_id": scan_id,
        "started_at": "2026-04-21T00:00:00Z",
        "broker_count": len(rows),
        "name_match_count": sum(1 for r in rows if r["name_match"]),
        "error_count": sum(1 for r in rows if r.get("error")),
        "results": rows,
    }


def _row(name: str, match: bool, error: Optional[str] = None) -> dict:
    return {
        "broker_name": name,
        "opt_out_url": f"https://{name.lower()}.test/opt-out",
        "name_match": match,
        "matched_variants": ["Test User"] if match else [],
        "html_path": f"state/scans/artifacts/{name}.html",
        "screenshot_path": f"state/scans/artifacts/{name}.png",
        "fetched_at": "20260421T000000Z",
        "error": error,
    }


def test_dashboard_template_has_marker():
    """The committed template must carry the marker the renderer expects."""
    assert DASHBOARD_TEMPLATE.exists(), f"Template missing at {DASHBOARD_TEMPLATE}"
    assert _EVIDENCE_MARKER in DASHBOARD_TEMPLATE.read_text(encoding="utf-8")


def test_render_dashboard_scan_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(json.dumps(_scan_payload("scan_abc", [_row("Spokeo", True), _row("WhitePages", False)])), encoding="utf-8")

    out = render_dashboard(
        profile_name="Test User",
        scan_path=scan_path,
    )

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # Original checklist survives
    assert "Cyber Hygiene Score" in content
    assert 'id="progressCircle"' in content
    # Evidence injected, marker replaced
    assert _EVIDENCE_MARKER not in content
    assert "Your live Erasure evidence" in content
    assert "scan_abc" in content
    assert "Spokeo" in content
    assert "WhitePages" in content
    # No DROP / verify when not provided
    assert "DROP submission" not in content
    assert "Verification diff" not in content


def test_render_dashboard_full(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(json.dumps(_scan_payload("scan_xyz", [_row("Spokeo", True)])), encoding="utf-8")

    receipt_path = tmp_path / "drop.json"
    receipt_path.write_text(json.dumps({
        "submission_id": "drop_2026042100",
        "confirmation_code": "CA-DROP-12345",
        "status": "submitted",
        "submitted_at": "2026-04-21T12:00:00Z",
        "portal_url": "https://consumer.drop.privacy.ca.gov",
    }), encoding="utf-8")

    verify_path = tmp_path / "verify.json"
    verify_path.write_text(json.dumps({
        "baseline_id": "scan_base",
        "verify_id": "scan_xyz",
        "resolved": 3,
        "persistent": 1,
        "new": 0,
        "errored": 0,
        "verifications": [],
    }), encoding="utf-8")

    out = render_dashboard(
        profile_name="Test User",
        scan_path=scan_path,
        drop_receipt_path=receipt_path,
        verify_path=verify_path,
    )

    content = out.read_text(encoding="utf-8")
    assert "DROP submission" in content
    assert "CA-DROP-12345" in content
    assert "Verification diff" in content
    assert "3 resolved" in content
    assert "1 persistent" in content


def test_render_dashboard_escapes_html(tmp_path, monkeypatch):
    """Broker names and profile names must be HTML-escaped."""
    monkeypatch.chdir(tmp_path)
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(json.dumps(_scan_payload("scan_1", [_row("<script>alert(1)</script>", True)])), encoding="utf-8")

    out = render_dashboard(
        profile_name="<b>Test</b>",
        scan_path=scan_path,
    )
    content = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    # The literal <b>Test</b> must not appear as raw HTML in profile name
    assert "&lt;b&gt;Test&lt;/b&gt;" in content


def test_render_dashboard_missing_template(tmp_path):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(json.dumps(_scan_payload("scan_1", [_row("A", False)])), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        render_dashboard(
            profile_name="Test",
            scan_path=scan_path,
            template_path=tmp_path / "does_not_exist.html",
        )


def test_render_dashboard_template_missing_marker(tmp_path):
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(json.dumps(_scan_payload("scan_1", [_row("A", False)])), encoding="utf-8")
    bad_template = tmp_path / "bad.html"
    bad_template.write_text("<html><body>no marker here</body></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="MARKER"):
        render_dashboard(
            profile_name="Test",
            scan_path=scan_path,
            template_path=bad_template,
        )


def test_latest_helpers_return_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert latest_scan_path() is None
    assert latest_receipt_path() is None
    assert latest_verify_path() is None


def test_latest_scan_picks_most_recent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scans_dir = tmp_path / "state" / "scans"
    scans_dir.mkdir(parents=True)
    older = scans_dir / "scan_old.json"
    newer = scans_dir / "scan_new.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    import os
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))

    latest = latest_scan_path()
    assert latest is not None
    assert latest.name == "scan_new.json"
