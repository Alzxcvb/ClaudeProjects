"""Reddit scraper using the public JSON endpoints — no auth required."""
from __future__ import annotations
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import requests
import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

# Browser-like UA — Reddit JSON is more forgiving with a real-looking agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
BASE_HOSTS = [
    "https://old.reddit.com",   # historically more permissive for unauth JSON
    "https://www.reddit.com",
]

REQ_DELAY_SEC = 3.0   # Reddit anon limit ~1/sec; pad heavily after early 429/timeout

_HOST_IDX = 0


def _get_json(path: str, params: dict, retries: int = 2) -> Optional[dict]:
    global _HOST_IDX
    last_err = None
    for attempt in range(retries + 1):
        host = BASE_HOSTS[_HOST_IDX % len(BASE_HOSTS)]
        url = host + path
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code in (429, 403):
                # Rotate host + back off harder
                _HOST_IDX += 1
                time.sleep(5 + random.random() * 3)
                last_err = f"HTTP {r.status_code}"
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = str(e)[:120]
            _HOST_IDX += 1
            time.sleep(4 + random.random() * 2)
    print(f"    ! {path} gave up after {retries+1} tries: {last_err}")
    return None


def load_subreddits() -> list:
    with open(CONFIG_DIR / "subreddits.yaml") as f:
        return yaml.safe_load(f)


def load_keywords() -> list:
    with open(CONFIG_DIR / "keywords.yaml") as f:
        return yaml.safe_load(f)


def _row_from_listing(item: dict, subreddit: str, matched_keyword: str = "") -> dict:
    d = item.get("data", {})
    return {
        "source": "reddit",
        "handle": d.get("author") or "[deleted]",
        "post_url": "https://www.reddit.com" + d.get("permalink", ""),
        "subreddit": subreddit,
        "post_title": d.get("title", "")[:500],
        "post_body": (d.get("selftext") or "")[:3000],
        "matched_keyword": matched_keyword,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def scan_new(subreddit: str, limit: int = 25) -> Iterator[dict]:
    """Scan /new — broad, no keyword filter."""
    data = _get_json(f"/r/{subreddit}/new.json", {"limit": limit})
    time.sleep(REQ_DELAY_SEC + random.random())
    if not data:
        return
    for item in data.get("data", {}).get("children", []):
        yield _row_from_listing(item, subreddit)


def scan_search(subreddit: str, keyword: str, limit: int = 10) -> Iterator[dict]:
    """Search a subreddit for a keyword."""
    data = _get_json(
        f"/r/{subreddit}/search.json",
        {"q": keyword, "restrict_sr": "on", "limit": limit, "sort": "new", "t": "month"},
    )
    time.sleep(REQ_DELAY_SEC + random.random())
    if not data:
        return
    for item in data.get("data", {}).get("children", []):
        yield _row_from_listing(item, subreddit, matched_keyword=keyword)


def scan_all(limit_per_sub: int = 15, limit_per_keyword: int = 5,
             do_search: bool = False) -> Iterator[dict]:
    """POC: skip search.json by default (Reddit blocks it harder than /new)."""
    subs = load_subreddits()
    kws = load_keywords()
    print(f"Scanning {len(subs)} subreddits (/new, no search)...")
    for sub in subs:
        print(f"  /r/{sub} /new ({limit_per_sub} posts)")
        for row in scan_new(sub, limit=limit_per_sub):
            yield row
    if do_search:
        core_subs = [s for s in subs if s in {
            "smallbusiness", "Entrepreneur", "startups", "SaaS",
            "algotrading", "SecurityAnalysis", "financialcareers",
            "automation", "ChatGPT", "ClaudeAI",
        }]
        for sub in core_subs:
            for kw in kws[:4]:
                print(f"  /r/{sub} search '{kw}' ({limit_per_keyword} posts)")
                for row in scan_search(sub, kw, limit=limit_per_keyword):
                    yield row
