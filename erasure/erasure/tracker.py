"""Opt-out tracking ledger.

The unglamorous part of a footprint wipe that actually works: a sheet of
site / opt-out URL / date requested / status / follow-up date. This module is
the structured version of that sheet. It seeds from the broker registry, lets
you mark requests as you submit them, computes follow-up dates, and exports to
CSV so the data is portable (and web-consumable later).
"""

from __future__ import annotations

import csv as _csv
import io
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

TRACKER_DIR = Path("state/tracker")
LEDGER_PATH = TRACKER_DIR / "ledger.json"
DEFAULT_FOLLOW_UP_DAYS = 45  # CCPA response window; brokers relist within 6-12 months.

Status = Literal["pending", "requested", "confirmed", "denied", "relisted"]

CSV_COLUMNS = [
    "site",
    "opt_out_url",
    "method",
    "date_requested",
    "status",
    "follow_up_date",
    "notes",
]


class TrackerEntry(BaseModel):
    site: str
    opt_out_url: Optional[str] = None
    method: str = "unknown"
    status: Status = "pending"
    date_requested: Optional[date] = None
    follow_up_date: Optional[date] = None
    notes: Optional[str] = None


class Ledger(BaseModel):
    entries: list[TrackerEntry] = Field(default_factory=list)
    updated_at: Optional[datetime] = None

    def find(self, site: str) -> Optional[TrackerEntry]:
        for e in self.entries:
            if e.site.lower() == site.lower():
                return e
        return None


def load_ledger(path: Path = LEDGER_PATH) -> Ledger:
    """Load the ledger, or return an empty one if the file does not exist."""
    if not path.exists():
        return Ledger()
    return Ledger.model_validate_json(path.read_text(encoding="utf-8"))


def save_ledger(ledger: Ledger, path: Path = LEDGER_PATH) -> Path:
    ledger.updated_at = datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
    return path


def add_entry(
    ledger: Ledger,
    site: str,
    *,
    opt_out_url: Optional[str] = None,
    method: str = "unknown",
    notes: Optional[str] = None,
) -> TrackerEntry:
    """Add a site if absent; otherwise backfill any missing URL/method/notes."""
    existing = ledger.find(site)
    if existing is not None:
        if opt_out_url and not existing.opt_out_url:
            existing.opt_out_url = opt_out_url
        if method != "unknown" and existing.method == "unknown":
            existing.method = method
        if notes and not existing.notes:
            existing.notes = notes
        return existing
    entry = TrackerEntry(site=site, opt_out_url=opt_out_url, method=method, notes=notes)
    ledger.entries.append(entry)
    return entry


def seed_from_brokers(brokers, ledger: Optional[Ledger] = None) -> Ledger:
    """Add a pending row for each broker not already in the ledger.

    Accepts any iterable of objects with ``name``, ``opt_out_url``, ``method``
    attributes (e.g. BrokerEntry). Existing entries are never downgraded.
    """
    ledger = ledger or Ledger()
    for b in brokers:
        add_entry(
            ledger,
            getattr(b, "name"),
            opt_out_url=getattr(b, "opt_out_url", None),
            method=getattr(b, "method", "unknown") or "unknown",
        )
    return ledger


def mark_requested(
    ledger: Ledger,
    site: str,
    *,
    today: Optional[date] = None,
    follow_up_days: int = DEFAULT_FOLLOW_UP_DAYS,
    notes: Optional[str] = None,
) -> TrackerEntry:
    """Mark a site as requested today and compute its follow-up date.

    Creates the entry if the site is not yet in the ledger.
    """
    entry = ledger.find(site) or add_entry(ledger, site)
    day = today or date.today()
    entry.status = "requested"
    entry.date_requested = day
    entry.follow_up_date = day + timedelta(days=follow_up_days)
    if notes:
        entry.notes = notes
    return entry


def update_status(
    ledger: Ledger,
    site: str,
    status: Status,
    *,
    today: Optional[date] = None,
    notes: Optional[str] = None,
) -> TrackerEntry:
    """Set a site's status. 'requested' routes through mark_requested so the
    follow-up clock is always set. Raises KeyError if the site is unknown."""
    if status == "requested":
        return mark_requested(ledger, site, today=today, notes=notes)
    entry = ledger.find(site)
    if entry is None:
        raise KeyError(f"No tracker entry for site '{site}'. Add it first.")
    entry.status = status
    if notes:
        entry.notes = notes
    return entry


def due_followups(ledger: Ledger, *, today: Optional[date] = None) -> list[TrackerEntry]:
    """Requested entries whose follow-up date has arrived and that are not yet
    resolved (confirmed/denied)."""
    day = today or date.today()
    out = []
    for e in ledger.entries:
        if e.status == "requested" and e.follow_up_date and e.follow_up_date <= day:
            out.append(e)
    return out


def to_csv(ledger: Ledger) -> str:
    """Render the ledger as CSV with the canonical tracking-sheet columns."""
    buf = io.StringIO()
    writer = _csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for e in ledger.entries:
        writer.writerow(
            {
                "site": e.site,
                "opt_out_url": e.opt_out_url or "",
                "method": e.method,
                "date_requested": e.date_requested.isoformat() if e.date_requested else "",
                "status": e.status,
                "follow_up_date": e.follow_up_date.isoformat() if e.follow_up_date else "",
                "notes": e.notes or "",
            }
        )
    return buf.getvalue()


def export_csv(ledger: Ledger, path: Optional[Path] = None) -> Path:
    out = path or (TRACKER_DIR / "ledger.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_csv(ledger), encoding="utf-8")
    return out
