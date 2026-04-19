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
        raise NotImplementedError(
            "DROP form selectors not yet mapped. Run `erasure drop recon` first, "
            "then update _fill_form with actual selectors from the snapshot."
        )

    async def _click_submit(self, page) -> Optional[str]:
        raise NotImplementedError(
            "Submit button selector not yet mapped. See _fill_form note."
        )

    @staticmethod
    def list_receipts() -> list[DropReceipt]:
        if not RECEIPTS_DIR.exists():
            return []
        out: list[DropReceipt] = []
        for p in sorted(RECEIPTS_DIR.glob("drop_*.json")):
            out.append(DropReceipt.model_validate_json(p.read_text(encoding="utf-8")))
        return out
