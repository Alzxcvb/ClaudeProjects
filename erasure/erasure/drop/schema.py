"""DROP submission and receipt schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

from erasure.profile import UserProfile


class DropIdentity(BaseModel):
    """Identity fields DROP requires to fan out a deletion request.

    Mapping derived from CCPA §1798.105 + the CPPA-published intake schema.
    Refine after first recon pass against the live portal.
    """

    legal_name: str
    name_variants: list[str] = []
    current_address: str
    prior_addresses: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    dob: Optional[date] = None
    mobile_ad_ids: list[str] = []
    zip_code: Optional[str] = None

    @classmethod
    def from_profile(cls, p: UserProfile) -> "DropIdentity":
        return cls(
            legal_name=p.name,
            name_variants=p.aliases,
            current_address=p.addresses[0] if p.addresses else "",
            prior_addresses=p.addresses[1:] + p.prior_addresses,
            emails=p.emails,
            phones=p.phones,
            dob=p.dob,
            mobile_ad_ids=p.mobile_ad_ids,
            zip_code=p.zip_code,
        )


SubmissionStatus = Literal["draft", "submitted", "acknowledged", "rejected", "completed"]


class DropReceipt(BaseModel):
    submission_id: str
    confirmation_code: Optional[str] = None
    submitted_at: datetime
    status: SubmissionStatus = "submitted"
    portal_url: str = "https://consumer.drop.privacy.ca.gov/"
    notes: Optional[str] = None
    screenshot_path: Optional[str] = None
