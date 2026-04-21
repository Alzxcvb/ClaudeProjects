"""Pydantic models for Sherlock scan results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class AccountHit(BaseModel):
    site: str
    url: str


class AccountsManifest(BaseModel):
    scan_id: str
    username: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    found_count: int
    hits: List[AccountHit]
    sherlock_version: Optional[str] = None
