from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class UserProfile(BaseModel):
    name: str
    addresses: list[str] = []
    phones: list[str] = []
    emails: list[str] = []
    dob: Optional[date] = None
    prior_addresses: list[str] = []
    aliases: list[str] = []
    # IDFA (iOS) and GAID (Android). Brokers match device-linked records
    # against these — including them increases DROP's deletion surface.
    mobile_ad_ids: list[str] = []
    zip_code: Optional[str] = None

    def to_search_variants(self) -> list[str]:
        parts = self.name.strip().split()
        variants: list[str] = []

        # Full name as-is
        variants.append(self.name.strip())

        if len(parts) >= 2:
            first, last = parts[0], parts[-1]

            # Reversed: Last, First
            variants.append(f"{last}, {first}")
            # Last First (no comma)
            variants.append(f"{last} {first}")

            if len(parts) == 3:
                middle = parts[1]
                # Without middle name
                variants.append(f"{first} {last}")
                variants.append(f"{last}, {first}")
                # With middle initial only
                variants.append(f"{first} {middle[0]}. {last}")
                # Reversed with middle
                variants.append(f"{last}, {first} {middle}")

        # Include aliases as-is
        for alias in self.aliases:
            alias = alias.strip()
            if alias and alias not in variants:
                variants.append(alias)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)

        return unique
