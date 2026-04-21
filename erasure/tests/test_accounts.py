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
    parse_csv_found,
    parse_found,
    run_sherlock,
    save_manifest,
    scan_username,
)


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    stdout, rc, csv_bytes = run_sherlock("alex", timeout_per_site=7, overall_timeout=60, _runner=_runner)
    assert rc == 0
    assert "alex" in captured["cmd"]
    assert "--print-found" in captured["cmd"]
    assert "--no-color" in captured["cmd"]
    assert "--csv" in captured["cmd"]
    assert "--timeout" in captured["cmd"]
    assert "7" in captured["cmd"]
    # cwd is set so Sherlock's incidental files don't pollute the user's working dir
    assert "cwd" in captured["kwargs"]
    assert captured["kwargs"]["cwd"] != str(tmp_path)
    # --output should point inside a temp dir (not CWD) so we don't litter the workdir
    i = captured["cmd"].index("--output")
    assert str(tmp_path) not in captured["cmd"][i + 1]
    # No CSV file was created in the mocked runner, so csv_bytes is None
    assert csv_bytes is None


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


# ---- CSV parser tests -----------------------------------------------------


def test_parse_csv_found_happy_path(tmp_path):
    csv_path = tmp_path / "alex.csv"
    _write_csv(
        csv_path,
        ["name", "url_user", "exists"],
        [
            ["GitHub", "https://github.com/alex", "Claimed"],
            ["Twitter", "https://twitter.com/alex", "Claimed"],
            ["Reddit", "https://reddit.com/u/alex", "Available"],
        ],
    )
    hits = parse_csv_found(csv_path)
    assert len(hits) == 2
    assert hits[0].site == "GitHub"
    assert hits[0].url == "https://github.com/alex"
    assert all("Reddit" not in h.site for h in hits)


def test_parse_csv_found_alias_fallback(tmp_path):
    # Sherlock renames url_user → profile_url; we should still pick it up
    csv_path = tmp_path / "alex.csv"
    _write_csv(
        csv_path,
        ["site_name", "profile_url", "status"],
        [["GitHub", "https://github.com/alex", "found"]],
    )
    hits = parse_csv_found(csv_path)
    assert len(hits) == 1
    assert hits[0].site == "GitHub"


def test_parse_csv_found_no_filter_column_keeps_all(tmp_path):
    # --print-found means the file only holds hits; no found/exists column present
    csv_path = tmp_path / "alex.csv"
    _write_csv(
        csv_path,
        ["name", "url"],
        [["GitHub", "https://github.com/alex"], ["Twitter", "https://twitter.com/alex"]],
    )
    hits = parse_csv_found(csv_path)
    assert len(hits) == 2


def test_parse_csv_found_raises_on_missing_site_column(tmp_path):
    csv_path = tmp_path / "alex.csv"
    _write_csv(
        csv_path,
        ["platform", "url_user"],
        [["GitHub", "https://github.com/alex"]],
    )
    with pytest.raises(ValueError, match="site column"):
        parse_csv_found(csv_path)


def test_parse_csv_found_raises_on_missing_url_column(tmp_path):
    csv_path = tmp_path / "alex.csv"
    _write_csv(
        csv_path,
        ["name", "link"],
        [["GitHub", "https://github.com/alex"]],
    )
    with pytest.raises(ValueError, match="URL column"):
        parse_csv_found(csv_path)


def test_scan_username_prefers_csv_when_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        # Simulate sherlock writing a CSV into its cwd (the temp dir it was given)
        cwd = Path(kwargs["cwd"])
        csv_file = cwd / "alex.csv"
        csv_file.write_text(
            "name,url_user,exists\n"
            "Mastodon,https://mastodon.social/@alex,Claimed\n",
            encoding="utf-8",
        )
        # Stdout deliberately reports a different site to prove CSV wins
        return SimpleNamespace(stdout="[+] GitHub: https://github.com/alex\n", returncode=0)

    path = scan_username("alex", _runner=_runner)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["parse_source"] == "csv"
    assert data["found_count"] == 1
    assert data["hits"][0]["site"] == "Mastodon"


def test_scan_username_falls_back_to_stdout_on_bad_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def _runner(cmd, **kwargs):
        # Unrecognized headers → parse_csv_found raises, stdout parser takes over
        cwd = Path(kwargs["cwd"])
        (cwd / "alex.csv").write_text("platform,link\nFoo,http://x\n", encoding="utf-8")
        return SimpleNamespace(stdout=SAMPLE_STDOUT, returncode=0)

    path = scan_username("alex", _runner=_runner)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["parse_source"] == "stdout"
    assert data["found_count"] == 3
