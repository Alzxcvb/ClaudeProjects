"""Playwright session manager.

Uses a persistent context against the real installed Chrome so the session
looks like a returning human user — not a fresh headless browser. Session
state lives under state/browser/<profile_name>/ so cookies and local storage
survive across runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, async_playwright


DEFAULT_STATE_DIR = Path("state/browser")


class BrowserSession:
    def __init__(
        self,
        profile_name: str = "default",
        headless: bool = False,
        state_dir: Optional[Path] = None,
    ) -> None:
        self.profile_name = profile_name
        self.headless = headless
        self.state_dir = (state_dir or DEFAULT_STATE_DIR) / profile_name
        self._pw = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> BrowserContext:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self.state_dir),
            channel="chrome",
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
        )
        return self._context

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            await self._context.close()
        if self._pw:
            await self._pw.stop()
