"""DROP portal client.

Phase-1 design: browser-driven via Playwright against the real consumer
portal. The portal sits behind Cloudflare's managed challenge so a pure
HTTP client is not viable for consumer submissions today.

Submission is gated behind explicit confirm; default is recon (open the
portal, snapshot the form, close). Real submissions persist a receipt to
state/drop/receipts/<id>.json.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from erasure.browser.session import BrowserSession
from erasure.drop.schema import DropIdentity, DropReceipt
from erasure.profile import UserProfile

PORTAL_URL = "https://consumer.drop.privacy.ca.gov/"
RESIDENCY_REVIEW_URL = "https://consumer.drop.privacy.ca.gov/residencyreview"
RECEIPTS_DIR = Path("state/drop/receipts")
SNAPSHOTS_DIR = Path("state/drop/snapshots")


class DropClient:
    def __init__(self, profile_name: str = "drop") -> None:
        self.profile_name = profile_name

    async def recon(self) -> Path:
        """Open the portal, snapshot HTML + screenshot, do not submit.

        Useful for first-look mapping of the form to DropIdentity fields
        and for debugging Cloudflare-challenge / auth changes.
        """
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        async with BrowserSession(profile_name=self.profile_name, headless=False) as ctx:
            page = await ctx.new_page()
            await page.goto(PORTAL_URL, wait_until="domcontentloaded")
            # Pause for the human to clear any CF challenge / login.
            await page.wait_for_load_state("networkidle", timeout=60_000)
            html_path = SNAPSHOTS_DIR / f"recon_{stamp}.html"
            png_path = SNAPSHOTS_DIR / f"recon_{stamp}.png"
            html_path.write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(png_path), full_page=True)
        return html_path

    async def submit(
        self,
        profile: UserProfile,
        confirm: bool = False,
    ) -> DropReceipt:
        """Submit a deletion request via DROP.

        confirm=False (default) walks the flow up to the final submit
        button, captures the filled form, and aborts. confirm=True clicks
        through and persists the receipt.
        """
        identity = DropIdentity.from_profile(profile)
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        submission_id = f"drop_{uuid.uuid4().hex[:12]}"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        async with BrowserSession(profile_name=self.profile_name, headless=False) as ctx:
            page = await ctx.new_page()
            await page.goto(PORTAL_URL, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=60_000)

            # Field mapping is stubbed until recon pass identifies actual
            # selectors. _fill_form raises NotImplementedError so we never
            # silently skip required identity fields.
            await self._fill_form(page, identity)

            screenshot = SNAPSHOTS_DIR / f"{submission_id}_{stamp}_filled.png"
            await page.screenshot(path=str(screenshot), full_page=True)

            confirmation_code: Optional[str] = None
            if confirm:
                confirmation_code = await self._click_submit(page)
                await page.screenshot(
                    path=str(SNAPSHOTS_DIR / f"{submission_id}_{stamp}_submitted.png"),
                    full_page=True,
                )

        receipt = DropReceipt(
            submission_id=submission_id,
            confirmation_code=confirmation_code,
            submitted_at=datetime.now(timezone.utc),
            status="submitted" if confirm else "draft",
            screenshot_path=str(screenshot),
            notes=None if confirm else "Dry run — form filled, not submitted.",
        )
        receipt_path = RECEIPTS_DIR / f"{submission_id}.json"
        receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
        return receipt

    async def _fill_form(self, page, identity: DropIdentity) -> None:
        """Fill the CA Identity Gateway verification form.

        Flow (captured from 2026-04-21 recon):
          1. Landing page at consumer.drop.privacy.ca.gov has a
             "Use personal information" entry point that redirects to
             auth.cdt.ca.gov/authentication/identify.
          2. The Gateway form asks for first/last name, DOB (month/day/year
             separate inputs), street + apt + city + ZIP, and a contact
             channel (email or phone) to receive an OTP.
          3. After "Send code" the user types the 6-digit OTP. We do not
             automate that — the caller pauses for a human.

        State / country are locked to California / United States, so we
        skip them. Selectors use accessible labels (get_by_label /
        get_by_role) so ID churn doesn't break us.
        """
        # Step 1: click "Use personal information" on the portal landing.
        try:
            await page.get_by_role("button", name="Use personal information").click(timeout=5_000)
        except Exception:
            # The label is rendered as a link in some A/B variants.
            await page.get_by_role("link", name="Use personal information").click(timeout=5_000)
        await page.wait_for_url("**/authentication/identify**", timeout=30_000)

        # Step 2: fill the Identity Gateway form.
        await page.get_by_label("First name").fill(identity.first_name)
        await page.get_by_label("Last name").fill(identity.last_name)

        dob = identity.dob_parts()
        if dob is not None:
            month, day, year = dob
            await page.get_by_label("Month").fill(month)
            await page.get_by_label("Day").fill(day)
            await page.get_by_label("Year").fill(year)

        addr = identity.address_parts()
        if addr["street"]:
            await page.get_by_label("Street address").fill(addr["street"])
        if addr["city"]:
            await page.get_by_label("City").fill(addr["city"])
        if addr["zip"]:
            await page.get_by_label("ZIP Code").fill(addr["zip"])

        contact = identity.primary_email() or identity.primary_phone()
        if contact:
            await page.get_by_label("Phone or email").fill(contact)

        # Step 3: request the OTP. Actual code entry is human-in-the-loop.
        await page.get_by_role("button", name="Send code").click()

    async def _click_submit(self, page) -> Optional[str]:
        raise NotImplementedError(
            "Post-OTP submit flow not yet mapped. Next recon pass (on a "
            "CA IP + US phone) needs to capture the screens after 'Send "
            "code' to finish this."
        )

    async def file_residency_review(
        self,
        profile: UserProfile,
        reason: str,
    ) -> DropReceipt:
        """Fallback path when the Identity Gateway rejects the user.

        DROP routes non-CA-resident or failed-verification cases to a
        residency review form at consumer.drop.privacy.ca.gov/residencyreview.
        It's a static form with name / email / phone / reason dropdown /
        free-text textarea. We fill it, click Submit, and save a receipt.
        """
        identity = DropIdentity.from_profile(profile)
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        submission_id = f"drop_rr_{uuid.uuid4().hex[:12]}"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        async with BrowserSession(profile_name=self.profile_name, headless=False) as ctx:
            page = await ctx.new_page()
            await page.goto(RESIDENCY_REVIEW_URL, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=60_000)

            await self._fill_residency_review(page, identity, reason)

            screenshot = SNAPSHOTS_DIR / f"{submission_id}_{stamp}_filled.png"
            await page.screenshot(path=str(screenshot), full_page=True)

            await page.get_by_role("button", name="Submit").click()
            await page.wait_for_load_state("networkidle", timeout=60_000)
            await page.screenshot(
                path=str(SNAPSHOTS_DIR / f"{submission_id}_{stamp}_submitted.png"),
                full_page=True,
            )

        receipt = DropReceipt(
            submission_id=submission_id,
            confirmation_code=None,
            submitted_at=datetime.now(timezone.utc),
            status="submitted",
            portal_url=RESIDENCY_REVIEW_URL,
            screenshot_path=str(screenshot),
            notes="Residency review fallback (Identity Gateway bypass).",
        )
        receipt_path = RECEIPTS_DIR / f"{submission_id}.json"
        receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
        return receipt

    async def _fill_residency_review(
        self,
        page,
        identity: DropIdentity,
        reason: str,
    ) -> None:
        """Fill the residency-review fallback form."""
        # "Individual" radio is the default; we only click it defensively
        # so the form doesn't flip to Data Broker on a remembered session.
        try:
            await page.get_by_label("Individual").check(timeout=2_000)
        except Exception:
            pass

        await page.get_by_label("Name", exact=True).fill(identity.legal_name)
        email = identity.primary_email()
        if email:
            await page.get_by_label("Email address").fill(email)
        phone = identity.primary_phone()
        if phone:
            await page.get_by_label("Phone number").fill(phone)

        await page.get_by_label("How can we help?").fill(reason)

    @staticmethod
    def list_receipts() -> list[DropReceipt]:
        if not RECEIPTS_DIR.exists():
            return []
        out: list[DropReceipt] = []
        for p in sorted(RECEIPTS_DIR.glob("drop_*.json")):
            out.append(DropReceipt.model_validate_json(p.read_text(encoding="utf-8")))
        return out
