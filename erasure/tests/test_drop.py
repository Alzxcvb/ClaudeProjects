"""Tests for DROP schema helpers and the form-fill selector mapping."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from erasure.drop.client import DropClient, RESIDENCY_REVIEW_URL
from erasure.drop.schema import DropIdentity, DropReceipt
from erasure.profile import UserProfile


def _identity(**overrides) -> DropIdentity:
    base = dict(
        legal_name="Alex Coffman",
        current_address="123 Main St, Oakland, CA 94607",
        emails=["alex@example.com"],
        phones=["+14155551234"],
        dob=date(1990, 7, 4),
        zip_code="94607",
    )
    base.update(overrides)
    return DropIdentity(**base)


class _FakeLocator:
    """Minimal async stand-in for Playwright's Locator."""

    def __init__(self, page: "_FakePage", key: str):
        self._page = page
        self._key = key

    async def fill(self, value: str, timeout: int | None = None) -> None:
        self._page.fills.append((self._key, value))

    async def click(self, timeout: int | None = None) -> None:
        self._page.clicks.append(self._key)

    async def check(self, timeout: int | None = None) -> None:
        self._page.checks.append(self._key)


class _FakePage:
    """Records accessibility-selector calls instead of driving a browser."""

    def __init__(self) -> None:
        self.fills: list[tuple[str, str]] = []
        self.clicks: list[str] = []
        self.checks: list[str] = []
        self.navigations: list[str] = []

    def get_by_label(self, name: str, exact: bool = False) -> _FakeLocator:
        key = f"label:{name}" + (":exact" if exact else "")
        return _FakeLocator(self, key)

    def get_by_role(self, role: str, name: str) -> _FakeLocator:
        return _FakeLocator(self, f"role:{role}:{name}")

    async def wait_for_url(self, url: str, timeout: int | None = None) -> None:
        self.navigations.append(url)

    async def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        return None

    async def goto(self, url: str, wait_until: str | None = None) -> None:
        self.navigations.append(url)

    async def screenshot(self, path: str, full_page: bool = False) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"")

    async def content(self) -> str:
        return "<html></html>"


# -----------------------------------------------------------------------------
# DropIdentity helpers
# -----------------------------------------------------------------------------


def test_first_last_name_splits_legal_name():
    ident = _identity(legal_name="Alex Q Coffman")
    assert ident.first_name == "Alex"
    assert ident.last_name == "Coffman"


def test_first_last_name_single_token_last_name_empty():
    ident = _identity(legal_name="Cher")
    assert ident.first_name == "Cher"
    assert ident.last_name == ""


def test_dob_parts_returns_month_day_year_strings():
    ident = _identity(dob=date(1990, 7, 4))
    assert ident.dob_parts() == ("7", "4", "1990")


def test_dob_parts_none_when_unset():
    ident = _identity(dob=None)
    assert ident.dob_parts() is None


def test_address_parts_splits_street_city_zip():
    ident = _identity(
        current_address="123 Main St, Oakland, CA 94607",
        zip_code="94607",
    )
    parts = ident.address_parts()
    assert parts["street"] == "123 Main St"
    assert parts["city"] == "Oakland"
    assert parts["zip"] == "94607"


def test_address_parts_falls_back_to_trailing_zip_token():
    ident = _identity(
        current_address="99 Market St, San Francisco, CA 94103",
        zip_code=None,
    )
    parts = ident.address_parts()
    assert parts["zip"] == "94103"


def test_address_parts_empty_when_address_blank():
    ident = _identity(current_address="")
    parts = ident.address_parts()
    assert parts == {"street": "", "apt": "", "city": "", "zip": ""}


def test_primary_email_and_phone():
    ident = _identity(emails=["a@b.com", "c@d.com"], phones=["+15551111", "+15552222"])
    assert ident.primary_email() == "a@b.com"
    assert ident.primary_phone() == "+15551111"

    empty = _identity(emails=[], phones=[])
    assert empty.primary_email() is None
    assert empty.primary_phone() is None


# -----------------------------------------------------------------------------
# _fill_form — Identity Gateway selector mapping
# -----------------------------------------------------------------------------


def test_fill_form_clicks_entry_point_and_fills_gateway():
    client = DropClient()
    page = _FakePage()
    ident = _identity()

    asyncio.run(client._fill_form(page, ident))

    # Entry-point click followed by redirect wait.
    assert "role:button:Use personal information" in page.clicks
    assert any("authentication/identify" in n for n in page.navigations)

    fills = dict(page.fills)
    assert fills["label:First name"] == "Alex"
    assert fills["label:Last name"] == "Coffman"
    assert fills["label:Month"] == "7"
    assert fills["label:Day"] == "4"
    assert fills["label:Year"] == "1990"
    assert fills["label:Street address"] == "123 Main St"
    assert fills["label:City"] == "Oakland"
    assert fills["label:ZIP Code"] == "94607"
    assert fills["label:Phone or email"] == "alex@example.com"

    # OTP request is triggered but not consumed — human does the 6-digit entry.
    assert "role:button:Send code" in page.clicks


def test_fill_form_falls_back_to_phone_when_no_email():
    client = DropClient()
    page = _FakePage()
    ident = _identity(emails=[], phones=["+14155551234"])

    asyncio.run(client._fill_form(page, ident))
    fills = dict(page.fills)
    assert fills["label:Phone or email"] == "+14155551234"


def test_fill_form_skips_dob_when_unset():
    client = DropClient()
    page = _FakePage()
    ident = _identity(dob=None)

    asyncio.run(client._fill_form(page, ident))
    keys = [k for k, _ in page.fills]
    assert "label:Month" not in keys
    assert "label:Day" not in keys
    assert "label:Year" not in keys


def test_click_submit_still_stubbed_pending_post_otp_recon():
    client = DropClient()
    with pytest.raises(NotImplementedError, match="post-OTP|Post-OTP"):
        asyncio.run(client._click_submit(_FakePage()))


# -----------------------------------------------------------------------------
# Residency-review fallback form
# -----------------------------------------------------------------------------


def test_fill_residency_review_populates_all_required_fields():
    client = DropClient()
    page = _FakePage()
    ident = _identity()

    asyncio.run(client._fill_residency_review(page, ident, reason="Please review."))

    fills = dict(page.fills)
    assert fills["label:Name:exact"] == "Alex Coffman"
    assert fills["label:Email address"] == "alex@example.com"
    assert fills["label:Phone number"] == "+14155551234"
    assert fills["label:How can we help?"] == "Please review."


def test_file_residency_review_writes_receipt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    page = _FakePage()

    # Stub BrowserSession so we don't actually launch Chrome.
    class _FakeCtx:
        async def new_page(self):
            return page

    class _FakeSession:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return _FakeCtx()

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr("erasure.drop.client.BrowserSession", _FakeSession)

    profile = UserProfile(
        name="Alex Coffman",
        addresses=["123 Main St, Oakland, CA 94607"],
        emails=["alex@example.com"],
        phones=["+14155551234"],
        dob=date(1990, 7, 4),
        zip_code="94607",
    )

    receipt = asyncio.run(DropClient().file_residency_review(profile, reason="test"))

    assert isinstance(receipt, DropReceipt)
    assert receipt.submission_id.startswith("drop_rr_")
    assert receipt.status == "submitted"
    assert receipt.portal_url == RESIDENCY_REVIEW_URL
    assert "Residency review" in (receipt.notes or "")

    # Receipt JSON persisted.
    receipt_path = tmp_path / "state" / "drop" / "receipts" / f"{receipt.submission_id}.json"
    assert receipt_path.exists()
    data = json.loads(receipt_path.read_text())
    assert data["submission_id"] == receipt.submission_id

    # Form was filled and submitted.
    assert any(url.endswith("/residencyreview") for url in page.navigations)
    assert "role:button:Submit" in page.clicks
