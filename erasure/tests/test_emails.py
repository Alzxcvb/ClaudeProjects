"""Tests for the holehe subprocess wrapper and email scan manifests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from erasure.emails.holehe import (
    EMAILS_DIR,
    HoleheFailed,
    HoleheNotInstalled,
    parse_found,
    run_holehe,
    save_manifest,
    scan_email,
)
from erasure.emails.schema import EmailHit, EmailsManifest


SAMPLE_STDOUT = """\
************************
     alex@example.com
************************
[+] github.com
[+] twitter.com
[-] pinterest.com
[x] rate-limited.com
"""


def test_parse_found_extracts_hits():
    hits = parse_found(SAMPLE_STDOUT)
    assert len(hits) == 2
    assert hits[0].site == "github.com"
    assert hits[1].site == "twitter.com"


def test_parse_found_empty_when_no_hits():
    assert parse_found("[-] foo.com\n[x] bar.com\n") == []


def test_parse_found_deduplicates():
    hits = parse_found("[+] github.com\n[+] github.com\n")
    assert len(hits) == 1


def test_run_holehe_rejects_invalid_email():
    with pytest.raises(ValueError):
        run_holehe("not-an-email")
    with pytest.raises(ValueError):
        run_holehe("")


def test_run_holehe_missing_binary_raises_typed_error():
    def _raise(*a, **kw):
        raise FileNotFoundError("holehe not found")

    with pytest.raises(HoleheNotInstalled, match="pipx install"):
        run_holehe("alex@example.com", _runner=_raise)


def test_run_holehe_passes_expected_flags():
    captured: dict = {}

    def _runner(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout=SAMPLE_STDOUT, returncode=0)

    stdout, rc = run_holehe("alex@example.com", _runner=_runner)
    assert rc == 0
    assert "holehe" in captured["cmd"]
    assert "alex@example.com" in captured["cmd"]
    assert "--only-used" in captured["cmd"]
    assert "--no-color" in captured["cmd"]


def test_save_manifest_writes_json(tmp_path):
    hits = [EmailHit(site="github.com")]
    path = save_manifest("alex@example.com", hits, scan_dir=tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["email"] == "alex@example.com"
    assert data["found_count"] == 1
    EmailsManifest.model_validate(data)


def test_scan_email_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout=SAMPLE_STDOUT, returncode=0)

    path = scan_email("alex@example.com", _runner=_runner)
    assert path.parent == EMAILS_DIR
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["found_count"] == 2


def test_scan_email_raises_on_nonzero_exit_with_no_hits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout="[x] all rate limited\n", returncode=1)

    with pytest.raises(HoleheFailed, match="code 1"):
        scan_email("alex@example.com", _runner=_runner)


def test_scan_email_empty_hits_zero_exit_is_fine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout="************************\n", returncode=0)

    path = scan_email("alex@example.com", _runner=_runner)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["found_count"] == 0
