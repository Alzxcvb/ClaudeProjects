"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from erasure.cli import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test that CLI help works."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Erasure" in result.output


def test_cli_version(runner):
    """Test that --version works."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "erasure" in result.output.lower()


def test_init_help(runner):
    result = runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.output.lower()


def test_scan_requires_profile(runner, tmp_path):
    missing = tmp_path / "nope.json"
    result = runner.invoke(cli, ["scan", "--profile", str(missing)])
    assert result.exit_code != 0


def test_scan_help(runner):
    result = runner.invoke(cli, ["scan", "--help"])
    assert result.exit_code == 0
    assert "broker" in result.output.lower()


def test_opt_out_command(runner):
    """opt-out is still a stub in the 1-week prototype — DROP handles deletion."""
    result = runner.invoke(cli, ["opt-out"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output


def test_opt_out_command_with_dry_run(runner):
    result = runner.invoke(cli, ["opt-out", "--dry-run"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output


def test_report_help(runner):
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.output.lower()


def test_verify_help(runner):
    result = runner.invoke(cli, ["verify", "--help"])
    assert result.exit_code == 0
    assert "baseline" in result.output.lower()


def test_schedule_command(runner):
    """Test schedule command."""
    result = runner.invoke(cli, ["schedule"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output


def test_schedule_command_with_interval(runner):
    """Test schedule command with --interval option."""
    result = runner.invoke(cli, ["schedule", "--interval", "daily"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output


def test_evidence_command(runner):
    """Test evidence command."""
    result = runner.invoke(cli, ["evidence"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output


def test_evidence_command_with_output_dir(runner):
    """Test evidence command with --output-dir option."""
    result = runner.invoke(cli, ["evidence", "--output-dir", "/tmp/evidence"])
    assert result.exit_code == 0
    assert "Not yet implemented" in result.output
