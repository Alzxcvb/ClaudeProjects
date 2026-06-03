"""Bridge discovered accounts to their deletion paths.

Sherlock (``accounts find``) and holehe (``emails find``) tell you *where* you
have accounts. This module answers the next question: *how do I delete each
one, and how painful is it?* It cross-references a hit against a curated
directory of deletion paths (difficulty + direct link) and flags the ones you
should scrub before deleting (hard/impossible, or content that lingers).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel

# Co-located with the module (the erasure/data/ dir is gitignored, so reference
# data that must ship with the package lives next to the code that loads it).
DIRECTORY_PATH = Path(__file__).resolve().parent / "deletion_directory.json"

# Thread Step 6: for these, deleting does not reliably remove your data, so
# overwrite (junk name, alias email, blanked profile) before you delete.
SCRUB_FIRST_DIFFICULTIES = {"hard", "impossible"}


class DeletionEntry(BaseModel):
    name: str
    domain: str
    difficulty: str  # easy | medium | hard | impossible
    url: Optional[str] = None
    notes: Optional[str] = None


class EnrichedHit(BaseModel):
    site: str
    url: Optional[str] = None
    matched: Optional[DeletionEntry] = None
    scrub_first: bool = False

    @property
    def difficulty(self) -> Optional[str]:
        return self.matched.difficulty if self.matched else None


def load_directory(path: Path = DIRECTORY_PATH) -> list[DeletionEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DeletionEntry.model_validate(s) for s in data.get("services", [])]


def _norm(value: str) -> str:
    return value.strip().lower()


def match_entry(
    site: str,
    url: Optional[str],
    directory: list[DeletionEntry],
) -> Optional[DeletionEntry]:
    """Match a hit to a directory entry by service name or domain.

    Tries, in order: exact name match, the entry's domain appearing in the hit
    URL, and the entry's bare brand (domain without TLD) matching the site name.
    Returns the most specific match (longest matched token wins) or None.
    """
    site_n = _norm(site)
    url_n = _norm(url or "")
    best: Optional[DeletionEntry] = None
    best_score = 0
    for entry in directory:
        name_n = _norm(entry.name)
        domain_n = _norm(entry.domain)
        brand = domain_n.split(".")[0]
        score = 0
        if site_n == name_n:
            score = max(score, 100)
        if domain_n and domain_n in url_n:
            score = max(score, 90 + len(domain_n))
        if brand and (brand == site_n or brand in site_n):
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
    deletion difficulty, a direct link, and a scrub-first flag."""
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
        out.append(EnrichedHit(site=site, url=url, matched=matched, scrub_first=scrub))
    return out
