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

    @property
    def first_name(self) -> str:
        parts = self.legal_name.strip().split()
        return parts[0] if parts else ""

    @property
    def last_name(self) -> str:
        parts = self.legal_name.strip().split()
        return parts[-1] if len(parts) >= 2 else ""

    def dob_parts(self) -> Optional[tuple[str, str, str]]:
        """Return (month, day, year) as the Identity Gateway form expects.

        None when dob is unset — the caller should skip the fields rather
        than fill blanks.
        """
        if self.dob is None:
            return None
        return (str(self.dob.month), str(self.dob.day), str(self.dob.year))

    def primary_email(self) -> Optional[str]:
        return self.emails[0] if self.emails else None

    def primary_phone(self) -> Optional[str]:
        return self.phones[0] if self.phones else None

    def address_parts(self) -> dict[str, str]:
        """Best-effort split of current_address into street/city/zip.

        The Identity Gateway asks for street, apt/suite, city, state, zip
        separately. State/country are locked to California/US on the form,
        so we only need the remainder. Returns empty strings for parts
        that cannot be parsed — caller decides whether to prompt.
        """
        raw = self.current_address.strip()
        if not raw:
            return {"street": "", "apt": "", "city": "", "zip": ""}
        parts = [p.strip() for p in raw.split(",")]
        street = parts[0] if parts else ""
        city = parts[1] if len(parts) >= 2 else ""
        zip_code = self.zip_code or ""
        if not zip_code and len(parts) >= 3:
            tail_tokens = parts[-1].split()
            if tail_tokens:
                last_tok = tail_tokens[-1]
                if last_tok.replace("-", "").isdigit():
                    zip_code = last_tok
        return {"street": street, "apt": "", "city": city, "zip": zip_code}


SubmissionStatus = Literal["draft", "submitted", "acknowledged", "rejected", "completed"]


class DropReceipt(BaseModel):
    submission_id: str
    confirmation_code: Optional[str] = None
    submitted_at: datetime
    status: SubmissionStatus = "submitted"
    portal_url: str = "https://consumer.drop.privacy.ca.gov/"
    notes: Optional[str] = None
    screenshot_path: Optional[str] = None
