"""Render data-deletion request letters from a user profile.

Pulls identifiers from ``UserProfile`` and fills the jurisdiction template. Date
of birth is excluded by default: a broker rarely needs it to locate a record,
and the letter is a document the user forwards onward, so we keep the minimum
identifying surface unless the caller opts in.
"""

from __future__ import annotations

import re
from datetime import date as _date, datetime, timezone
from pathlib import Path
from typing import Optional

from erasure.legal.templates import JURISDICTIONS, Jurisdiction
from erasure.profile import UserProfile

LEGAL_DIR = Path("state/legal")


def build_identifiers_block(profile: UserProfile, *, include_dob: bool = False) -> str:
    """Render the profile's locating identifiers as an indented bullet list."""
    lines: list[str] = [f"Full name: {profile.name}"]
    if profile.aliases:
        lines.append(f"Also known as: {', '.join(profile.aliases)}")
    if profile.emails:
        lines.append(f"Email: {', '.join(profile.emails)}")
    if profile.phones:
        lines.append(f"Phone: {', '.join(profile.phones)}")
    if profile.addresses:
        lines.append(f"Address: {'; '.join(profile.addresses)}")
    if profile.prior_addresses:
        lines.append(f"Prior address: {'; '.join(profile.prior_addresses)}")
    if include_dob and profile.dob:
        lines.append(f"Date of birth: {profile.dob.isoformat()}")
    return "\n".join(f"  - {line}" for line in lines)


def render_request(
    *,
    profile: UserProfile,
    jurisdiction: str,
    recipient: Optional[str] = None,
    deadline_days: Optional[int] = None,
    today: Optional[_date] = None,
    include_dob: bool = False,
) -> str:
    """Render a deletion-request letter as plain text.

    Raises ValueError if the jurisdiction key is unknown.
    """
    key = jurisdiction.lower()
    j: Optional[Jurisdiction] = JURISDICTIONS.get(key)
    if j is None:
        raise ValueError(
            f"Unknown jurisdiction '{jurisdiction}'. Choose from: {', '.join(JURISDICTIONS)}"
        )
    block = build_identifiers_block(profile, include_dob=include_dob)
    return j.body.format(
        date=(today or _date.today()).strftime("%B %d, %Y"),
        recipient_name=recipient or "Data Privacy Officer",
        identifiers_block=block,
        deadline_days=deadline_days if deadline_days is not None else j.default_deadline_days,
        requester_name=profile.name,
    )


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return s or "request"


def save_request(
    text: str,
    *,
    jurisdiction: str,
    recipient: Optional[str] = None,
    out_dir: Path = LEGAL_DIR,
) -> Path:
    """Persist a rendered letter to state/legal/ and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{jurisdiction.lower()}_{_slug(recipient or 'request')}_{stamp}.txt"
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return path
