"""Tests for the Sherlock subprocess wrapper and account scan manifests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from erasure.accounts.schema import AccountHit, AccountsManifest
from erasure.accounts.sherlock import (
    ACCOUNTS_DIR,
    SherlockFailed,
    SherlockNotInstalled,
    parse_found,
    run_sherlock,
    save_manifest,
    scan_username,
)


SAMPLE_STDOUT = """\
[*] Checking username alex on:

[+] GitHub: https://github.com/alex
[+] Twitter: https://twitter.com/alex
[-] Reddit: Not Found.
[+] Gravatar: http://en.gravatar.com/alex
[*] Search completed with 3 results
"""


def test_parse_found_extracts_hits():
    hits = parse_found(SAMPLE_STDOUT)
    assert len(hits) == 3
    assert hits[0].site == "GitHub"
    assert hits[0].url == "https://github.com/alex"
    assert hits[2].site == "Gravatar"
    # The [-] line is not found and must not be included
    assert all("Reddit" not in h.site for h in hits)


def test_parse_found_empty_when_no_hits():
    assert parse_found("[*] Checking username foo on:\n[*] Search completed with 0 results\n") == []


def test_run_sherlock_rejects_shell_metacharacters():
    with pytest.raises(ValueError):
        run_sherlock("alex; rm -rf /")
    with pytest.raises(ValueError):
        run_sherlock("`whoami`")
    with pytest.raises(ValueError):
        run_sherlock("alex with spaces")
    with pytest.raises(ValueError):
        run_sherlock("")


def test_run_sherlock_accepts_reasonable_usernames():
    # Should not raise for valid usernames — subprocess call is mocked via FileNotFoundError path below
    for good in ("alex", "alex_1", "alex.coffman", "A-B_c.0"):
        def _raise(*a, **kw):
            raise FileNotFoundError("stub")
        with pytest.raises(SherlockNotInstalled):
            run_sherlock(good, _runner=_raise)


def test_run_sherlock_missing_binary_raises_typed_error():
    def _raise(*a, **kw):
        raise FileNotFoundError("sherlock not found")

    with pytest.raises(SherlockNotInstalled, match="pipx install"):
        run_sherlock("alex", _runner=_raise)


def test_run_sherlock_passes_expected_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    captured: dict = {}

    def _runner(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout=SAMPLE_STDOUT, returncode=0)

    stdout, rc = run_sherlock("alex", timeout_per_site=7, overall_timeout=60, _runner=_runner)
    assert rc == 0
    assert "alex" in captured["cmd"]
    assert "--print-found" in captured["cmd"]
    assert "--no-color" in captured["cmd"]
    assert "--timeout" in captured["cmd"]
    assert "7" in captured["cmd"]
    # --output should point inside a temp dir (not CWD) so we don't litter the workdir
    i = captured["cmd"].index("--output")
    assert str(tmp_path) not in captured["cmd"][i + 1]


def test_save_manifest_writes_json(tmp_path):
    hits = [AccountHit(site="GitHub", url="https://github.com/alex")]
    path = save_manifest("alex", hits, scan_dir=tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["username"] == "alex"
    assert data["found_count"] == 1
    assert data["hits"][0]["site"] == "GitHub"
    AccountsManifest.model_validate(data)


def test_scan_username_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout=SAMPLE_STDOUT, returncode=0)

    path = scan_username("alex", _runner=_runner)
    assert path.parent == ACCOUNTS_DIR
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["found_count"] == 3


def test_scan_username_raises_when_no_hits_and_nonzero_exit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout="[*] something went wrong\n", returncode=2)

    with pytest.raises(SherlockFailed, match="code 2"):
        scan_username("alex", _runner=_runner)


def test_scan_username_empty_hits_with_zero_exit_is_fine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        return SimpleNamespace(stdout="[*] Search completed with 0 results\n", returncode=0)

    path = scan_username("alex", _runner=_runner)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["found_count"] == 0
