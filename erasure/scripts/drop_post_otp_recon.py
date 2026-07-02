#!/usr/bin/env python3
"""TEMPORARY recon tool — capture the CA DROP post-OTP screens.

DELETE THIS FILE once DropClient._click_submit is implemented. It exists
only because submit() has no pause point for human OTP entry, so nobody
has ever seen what the portal shows after "Send code".

What it does:
  1. Reuses BrowserSession + DropClient._fill_form to open real Chrome
     (headed), fill the CA Identity Gateway form, and click "Send code".
  2. Pauses. You type the 6-digit OTP into the browser yourself and click
     through at your own pace.
  3. Each time you press Enter in this terminal, it saves a full-page
     screenshot AND the raw page HTML to state/drop/snapshots/ as
     postotp_NN_<label>.png / .html, plus a manifest line with the URL.
  4. Type "done" to stop. Nothing here ever clicks a final submit button;
     if YOU click submit inside the browser that is a real state filing.

Preconditions:
  - Profile at ~/.erasure/profile.json (run `python3 -m erasure.cli init`).
  - Tailscale "boxy" exit node ON so you present a California IP —
    otherwise the Gateway will reject you like the 2026-04-21 attempt.

Usage (from anywhere; the script chdirs to the project root):
    python3 scripts/drop_post_otp_recon.py [--profile PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# state/ paths in the package are relative to the project root.
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from erasure.browser.session import BrowserSession  # noqa: E402
from erasure.drop.client import PORTAL_URL, SNAPSHOTS_DIR, DropClient  # noqa: E402
from erasure.drop.schema import DropIdentity  # noqa: E402
from erasure.profile import UserProfile  # noqa: E402

MANIFEST_PATH = SNAPSHOTS_DIR / "postotp_manifest.jsonl"


def _ainput(prompt: str):
    """input() without freezing the Playwright event loop."""
    return asyncio.to_thread(input, prompt)


def _slug(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


async def _auto_label(page) -> str:
    try:
        title = await page.title()
    except Exception:
        title = ""
    label = _slug(title) or _slug(Path(page.url).name)
    return label or "screen"


async def _capture(page, index: int, label: str) -> None:
    base = f"postotp_{index:02d}_{label}"
    html_path = SNAPSHOTS_DIR / f"{base}.html"
    png_path = SNAPSHOTS_DIR / f"{base}.png"
    html_path.write_text(await page.content(), encoding="utf-8")
    await page.screenshot(path=str(png_path), full_page=True)
    record = {
        "index": index,
        "label": label,
        "url": page.url,
        "title": await page.title(),
        "html": str(html_path),
        "png": str(png_path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    with MANIFEST_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print(f"  saved {png_path}")
    print(f"  saved {html_path}")
    print(f"  url:  {page.url}")


def _active_page(ctx, fallback):
    """If the flow opened a new tab, capture that one, not the original."""
    pages = [p for p in ctx.pages if not p.is_closed()]
    return pages[-1] if pages else fallback


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--profile",
        default=str(Path.home() / ".erasure" / "profile.json"),
        help="Profile JSON (default: ~/.erasure/profile.json)",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"No profile at {profile_path}.")
        print("Run `python3 -m erasure.cli init` first, then rerun this script.")
        return 1

    profile = UserProfile.model_validate_json(profile_path.read_text(encoding="utf-8"))
    identity = DropIdentity.from_profile(profile)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    client = DropClient()

    print("=" * 72)
    print("DROP POST-OTP RECON (no submission — capture only)")
    print("Reminder: you should be on the Tailscale 'boxy' exit node (CA IP).")
    print("=" * 72)

    async with BrowserSession(profile_name=client.profile_name, headless=False) as ctx:
        page = await ctx.new_page()
        await page.goto(PORTAL_URL, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=60_000)

        try:
            await client._fill_form(page, identity)
        except Exception as exc:
            # The Gateway rejected us before "Send code" — the IP/phone
            # precondition is still unsolved. Snapshot the exact rejection
            # point and stop; selectors can't be guessed from here.
            print("\n!! _fill_form failed BEFORE reaching 'Send code'.")
            print(f"!! {type(exc).__name__}: {exc}")
            page = _active_page(ctx, page)
            await _capture(page, 0, "fill-failure")
            await _ainput(
                "\nRejection state captured. Look at the browser if you want, "
                "then press Enter to close it... "
            )
            return 2

        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        # Free capture of the OTP-entry screen itself — a future automated
        # flow will need its input selector too.
        await _capture(_active_page(ctx, page), 0, "otp-entry")

        print()
        print("=" * 72)
        print("The browser is open and 'Send code' was clicked.")
        print("1. Type the 6-digit OTP into the BROWSER now.")
        print("2. When you are PAST the OTP screen and looking at the next")
        print("   screen, come back here and press Enter to capture it.")
        print("Each capture: optionally type a short label first (e.g.")
        print("'eligibility'), or just press Enter and I'll name it from the")
        print("page title. Type 'done' to finish.")
        print("=" * 72)

        answer = await _ainput("\n[past the OTP? press Enter to capture] > ")
        index = 1
        while answer.strip().lower() != "done":
            page = _active_page(ctx, page)
            label = _slug(answer) or await _auto_label(page)
            try:
                await _capture(page, index, label)
                index += 1
            except Exception as exc:
                print(f"  capture failed ({type(exc).__name__}: {exc}) — "
                      "navigate somewhere stable and try again.")
            answer = await _ainput(
                "\n[Enter = capture next screen (optional label first), "
                "'done' = stop] > "
            )

        print(f"\nCaptured {index - 1} post-OTP screen(s) + the OTP-entry screen.")
        print(f"Files + manifest: {SNAPSHOTS_DIR}/")
        print("Bring these back to Claude to implement _click_submit.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted — captures so far are already on disk.")
        raise SystemExit(130)
