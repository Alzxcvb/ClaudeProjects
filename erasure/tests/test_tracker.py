"""Tests for the opt-out tracking ledger."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from erasure.tracker import (
    CSV_COLUMNS,
    DEFAULT_FOLLOW_UP_DAYS,
    Ledger,
    add_entry,
    due_followups,
    export_csv,
    load_ledger,
    mark_requested,
    save_ledger,
    seed_from_brokers,
    to_csv,
    update_status,
)


def _brokers():
    return [
        SimpleNamespace(name="Spokeo", opt_out_url="https://spokeo.com/optout", method="form"),
        SimpleNamespace(name="Whitepages", opt_out_url="https://whitepages.com/suppression", method="form"),
    ]


def test_add_entry_dedupes_case_insensitively():
    ledger = Ledger()
    add_entry(ledger, "Spokeo", opt_out_url="https://x")
    add_entry(ledger, "spokeo", method="form")
    assert len(ledger.entries) == 1
    # backfill: method filled on the second call
    assert ledger.entries[0].method == "form"
    assert ledger.entries[0].opt_out_url == "https://x"


def test_seed_from_brokers_adds_pending_rows():
    ledger = seed_from_brokers(_brokers())
    assert len(ledger.entries) == 2
    assert all(e.status == "pending" for e in ledger.entries)
    assert ledger.find("Spokeo").opt_out_url == "https://spokeo.com/optout"


def test_seed_is_idempotent():
    ledger = seed_from_brokers(_brokers())
    seed_from_brokers(_brokers(), ledger)
    assert len(ledger.entries) == 2


def test_mark_requested_sets_dates():
    ledger = seed_from_brokers(_brokers())
    today = date(2026, 6, 3)
    entry = mark_requested(ledger, "Spokeo", today=today)
    assert entry.status == "requested"
    assert entry.date_requested == today
    assert entry.follow_up_date == today + timedelta(days=DEFAULT_FOLLOW_UP_DAYS)


def test_update_status_requested_routes_through_mark_requested():
    ledger = seed_from_brokers(_brokers())
    today = date(2026, 6, 3)
    entry = update_status(ledger, "Whitepages", "requested", today=today)
    assert entry.follow_up_date == today + timedelta(days=DEFAULT_FOLLOW_UP_DAYS)


def test_update_status_confirmed_keeps_dates():
    ledger = seed_from_brokers(_brokers())
    today = date(2026, 6, 3)
    mark_requested(ledger, "Spokeo", today=today)
    entry = update_status(ledger, "Spokeo", "confirmed")
    assert entry.status == "confirmed"
    assert entry.date_requested == today  # not wiped


def test_update_unknown_site_raises():
    ledger = Ledger()
    with pytest.raises(KeyError):
        update_status(ledger, "Nope", "confirmed")


def test_due_followups_filters_by_date_and_status():
    ledger = seed_from_brokers(_brokers())
    req_day = date(2026, 1, 1)
    mark_requested(ledger, "Spokeo", today=req_day)  # follow-up 2026-02-15
    mark_requested(ledger, "Whitepages", today=date(2026, 6, 1))  # follow-up far out
    due = due_followups(ledger, today=date(2026, 3, 1))
    assert [e.site for e in due] == ["Spokeo"]
    # A confirmed entry is never "due"
    update_status(ledger, "Spokeo", "confirmed")
    assert due_followups(ledger, today=date(2026, 3, 1)) == []


def test_csv_has_canonical_columns():
    ledger = seed_from_brokers(_brokers())
    mark_requested(ledger, "Spokeo", today=date(2026, 6, 3))
    csv_text = to_csv(ledger)
    header = csv_text.splitlines()[0]
    assert header == ",".join(CSV_COLUMNS)
    assert "Spokeo" in csv_text
    assert "2026-06-03" in csv_text
    assert "2026-07-18" in csv_text  # +45 days


def test_round_trip_persistence(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = seed_from_brokers(_brokers())
    mark_requested(ledger, "Spokeo", today=date(2026, 6, 3))
    save_ledger(ledger, path)

    reloaded = load_ledger(path)
    assert len(reloaded.entries) == 2
    spokeo = reloaded.find("Spokeo")
    assert spokeo.status == "requested"
    assert spokeo.date_requested == date(2026, 6, 3)


def test_load_ledger_missing_returns_empty(tmp_path):
    assert load_ledger(tmp_path / "nope.json").entries == []


def test_export_csv_writes_file(tmp_path):
    ledger = seed_from_brokers(_brokers())
    out = export_csv(ledger, tmp_path / "out.csv")
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("site,opt_out_url")
