"""Pydantic models for holehe email scan results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class EmailHit(BaseModel):
    site: str
    url: Optional[str] = None


class EmailsManifest(BaseModel):
    scan_id: str
    email: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    found_count: int
    hits: List[EmailHit]
    source: str = "holehe"
    parse_source: Optional[str] = None
