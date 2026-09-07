"""Bridge discovered accounts to their deletion paths.

Sherlock (``accounts find``) and holehe (``emails find``) tell you *where* you
have accounts. This module answers the next question: *how do I delete each
one, and how painful is it?* It cross-references a hit against the bundled
directory of deletion paths (difficulty + direct link + email template) and
flags the ones you should scrub before deleting (hard/impossible, or content
that lingers) and the ones that need a legal request (``limited``).

The directory is the JustDeleteMe dataset (https://justdeleteme.xyz, MIT),
refreshed by ``scripts/refresh_deletion_directory.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel

# Co-located with the module (the erasure/data/ dir is gitignored, so reference
# data that must ship with the package lives next to the code that loads it).
DIRECTORY_PATH = Path(__file__).resolve().parent / "deletion_directory.json"

# Thread Step 6: for these, deleting does not reliably remove your data, so
# overwrite (junk name, alias email, blanked profile) before you delete.
SCRUB_FIRST_DIFFICULTIES = {"hard", "impossible"}

# "limited" means the service deletes only for people covered by a privacy law
# and verifies the claim. That is not a scrub-first case, it is a legal-request
# case: `erasure legal request` writes the CCPA/GDPR letter these sites want.
LEGAL_REQUEST_DIFFICULTIES = {"limited"}

# Below this length a brand name ("x", "hi", "ok") produces false matches
# against unrelated site names, so substring matching is restricted to
# distinctive brands and everything shorter must match exactly.
_MIN_SUBSTRING_BRAND = 5


class DeletionEntry(BaseModel):
    name: str
    domains: list[str] = []
    difficulty: str  # easy | medium | hard | limited | impossible
    url: Optional[str] = None
    notes: Optional[str] = None
    # Some services only accept deletion by email; upstream ships the template.
    email: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None

    @property
    def domain(self) -> Optional[str]:
        """The primary domain, for display and for callers wanting just one."""
        return self.domains[0] if self.domains else None


class EnrichedHit(BaseModel):
    site: str
    url: Optional[str] = None
    matched: Optional[DeletionEntry] = None
    scrub_first: bool = False
    legal_request: bool = False

    @property
    def difficulty(self) -> Optional[str]:
        return self.matched.difficulty if self.matched else None


def load_directory(path: Path = DIRECTORY_PATH) -> list[DeletionEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DeletionEntry.model_validate(s) for s in data.get("services", [])]


def _norm(value: str) -> str:
    return value.strip().lower()


def _host(url: str) -> str:
    """The bare hostname of a URL, with any www. prefix and port removed."""
    if not url:
        return ""
    if "//" not in url:
        url = "//" + url
    host = urlsplit(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _host_matches(host: str, domain: str) -> bool:
    """True when host is the domain itself or a subdomain of it."""
    return bool(host) and bool(domain) and (host == domain or host.endswith("." + domain))


def match_entry(
    site: str,
    url: Optional[str],
    directory: list[DeletionEntry],
) -> Optional[DeletionEntry]:
    """Match a hit to a directory entry by service name or domain.

    Tries, in order: exact name match, any of the entry's domains matching the
    hit URL's host, and the entry's bare brand (domain without TLD) matching
    the site name. Returns the most specific match (longest matched token wins)
    or None. With thousands of entries a loose substring rule mismatches often,
    so host comparison is exact and brand substrings need a distinctive brand.
    """
    site_n = _norm(site)
    host = _host(_norm(url or ""))
    best: Optional[DeletionEntry] = None
    best_score = 0
    for entry in directory:
        score = 0
        if site_n and site_n == _norm(entry.name):
            score = max(score, 100)
        for domain in entry.domains:
            domain_n = _norm(domain)
            if _host_matches(host, domain_n):
                score = max(score, 90 + len(domain_n))
            brand = domain_n.split(".")[0]
            if not brand or not site_n:
                continue
            if brand == site_n:
                score = max(score, 60 + len(brand))
            elif len(brand) >= _MIN_SUBSTRING_BRAND and re.search(
                rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", site_n
            ):
                score = max(score, 50 + len(brand))
        if score > best_score:
            best_score = score
            best = entry
    return best


def enrich_hits(
    hits: Iterable,
    directory: Optional[list[DeletionEntry]] = None,
) -> list[EnrichedHit]:
    """Enrich an iterable of hits (objects or dicts with site + url) with
    deletion difficulty, a direct link, a scrub-first flag, and a
    legal-request flag."""
    directory = directory if directory is not None else load_directory()
    out: list[EnrichedHit] = []
    for h in hits:
        if isinstance(h, dict):
            site = h.get("site") or h.get("name") or ""
            url = h.get("url")
        else:
            site = getattr(h, "site", "") or getattr(h, "name", "")
            url = getattr(h, "url", None)
        matched = match_entry(site, url, directory)
        scrub = bool(matched and matched.difficulty in SCRUB_FIRST_DIFFICULTIES)
        legal = bool(matched and matched.difficulty in LEGAL_REQUEST_DIFFICULTIES)
        out.append(
            EnrichedHit(
                site=site, url=url, matched=matched, scrub_first=scrub, legal_request=legal
            )
        )
    return out
