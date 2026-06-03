"""Tests for the master privacy playbook (thread steps 1-9)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from erasure.cli import cli
from erasure.playbook import STEPS, checkbox, gather_status, render_markdown


@pytest.fixture
def runner():
    return CliRunner()


# --- structure -------------------------------------------------------------

def test_nine_steps_numbered_1_to_9():
    assert len(STEPS) == 9
    assert [s.number for s in STEPS] == list(range(1, 10))


def test_every_step_has_summary():
    for s in STEPS:
        assert s.summary.strip(), f"step {s.number} has no summary"


def test_checkbox_marks():
    assert checkbox(True) == "[x]"
    assert checkbox(False) == "[ ]"
    assert checkbox(None) == "[~]"


# --- markdown --------------------------------------------------------------

def test_markdown_lists_all_step_titles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # empty state
    md = render_markdown("Jane Public")
    for s in STEPS:
        assert s.title in md
    assert "Jane Public" in md


def test_markdown_includes_manual_links(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = render_markdown()
    # step 7 Google tool + step 9 alias services
    assert "myactivity.google.com/results-about-you" in md
    assert "SimpleLogin" in md or "Hide My Email" in md


def test_markdown_has_no_em_or_en_dash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = render_markdown("Jane")
    assert "—" not in md
    assert "–" not in md


# --- status probes ---------------------------------------------------------

def test_status_resilient_on_empty_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    status = gather_status()
    # every probe key referenced by a step must resolve
    for s in STEPS:
        if s.probe_key:
            assert s.probe_key in status
    assert status["exposure"].done is False
    assert status["tracker"].done is False
    assert status["legal"].done is False


def test_status_detects_seeded_tracker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from erasure import tracker

    led = tracker.Ledger()
    tracker.add_entry(led, "Spokeo", opt_out_url="https://spokeo.com/optout")
    tracker.save_ledger(led)  # writes state/tracker/ledger.json under tmp cwd
    status = gather_status()
    assert status["tracker"].done is True
    assert "1 sites tracked" in status["tracker"].detail


def test_scrub_probe_counts_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # directory ships with the package (absolute path), so this works anywhere
    status = gather_status()
    assert status["scrub"].done is None
    assert "scrub" in status["scrub"].detail.lower()


# --- CLI -------------------------------------------------------------------

def test_playbook_cmd_runs(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["playbook"])
    assert result.exit_code == 0
    assert "Map your exposure" in result.output
    assert "Lock the doors behind you" in result.output


def test_playbook_writes_markdown(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "plan.md"
    result = runner.invoke(cli, ["playbook", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "# Your privacy playbook" in out.read_text()
