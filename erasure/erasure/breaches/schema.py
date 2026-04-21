"""Pydantic models for HIBP breach-check results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class BreachHit(BaseModel):
    name: str
    title: str
    domain: Optional[str] = None
    breach_date: Optional[str] = None
    pwn_count: Optional[int] = None
    data_classes: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class BreachesManifest(BaseModel):
    scan_id: str
    email: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    found_count: int
    breaches: List[BreachHit]
    source: str = "hibp"
