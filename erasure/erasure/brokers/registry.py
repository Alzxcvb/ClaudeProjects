"""Broker registry loader.

Reads erasure/data/brokers.yaml and exposes filtered broker lists.
Per-broker automation modules subclass erasure.brokers.base.Broker;
this module is the lightweight YAML-driven view used by scan / verify
to enumerate targets without requiring a Python class for every broker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

BROKERS_YAML = Path(__file__).resolve().parent.parent / "data" / "brokers.yaml"

Priority = Literal["crucial", "high", "normal", "important", "optional", "unknown"]


class BrokerEntry(BaseModel):
    """One row from brokers.yaml. Not an automation class — just metadata."""

    name: str
    category: Optional[str] = None
    priority: Priority = "unknown"
    opt_out_url: Optional[str] = None
    people_search_url: Optional[str] = None
    contact_emails: list[str] = Field(default_factory=list)
    method: str = "unknown"
    ca_registered: bool = False
    coverage: Optional[str] = None  # "drop" if DROP handles it
    notes: Optional[str] = None


def load_brokers(path: Path = BROKERS_YAML) -> list[BrokerEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("brokers", [])
    out: list[BrokerEntry] = []
    for r in rows:
        # Tolerate unknown keys — brokers.yaml has fields we don't model yet.
        out.append(BrokerEntry.model_validate({k: r[k] for k in r if k in BrokerEntry.model_fields}))
    return out


def filter_brokers(
    brokers: list[BrokerEntry],
    *,
    priority: Optional[Priority] = None,
    ca_registered: Optional[bool] = None,
    has_opt_out_url: bool = True,
    limit: Optional[int] = None,
) -> list[BrokerEntry]:
    out = list(brokers)
    if priority is not None:
        out = [b for b in out if b.priority == priority]
    if ca_registered is not None:
        out = [b for b in out if b.ca_registered is ca_registered]
    if has_opt_out_url:
        out = [b for b in out if b.opt_out_url]
    if limit is not None:
        out = out[:limit]
    return out
