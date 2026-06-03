"""Tests for the account-deletion directory bridge."""

from __future__ import annotations

from types import SimpleNamespace

from erasure.accounts.justdelete import (
    DeletionEntry,
    SCRUB_FIRST_DIFFICULTIES,
    enrich_hits,
    load_directory,
    match_entry,
)


def _dir():
    return [
        DeletionEntry(name="Facebook", domain="facebook.com", difficulty="hard", url="https://fb/delete"),
        DeletionEntry(name="GitHub", domain="github.com", difficulty="easy", url="https://gh/settings"),
        DeletionEntry(name="Spotify", domain="spotify.com", difficulty="easy", url="https://spotify/close"),
    ]


def test_bundled_directory_loads_and_is_nonempty():
    entries = load_directory()
    assert len(entries) >= 30
    assert all(e.difficulty in {"easy", "medium", "hard", "impossible"} for e in entries)
    # Every entry has a name and a domain
    assert all(e.name and e.domain for e in entries)


def test_match_by_exact_name():
    m = match_entry("GitHub", None, _dir())
    assert m is not None and m.name == "GitHub"


def test_match_is_case_insensitive():
    m = match_entry("github", None, _dir())
    assert m is not None and m.name == "GitHub"


def test_match_by_domain_in_url():
    m = match_entry("Some Profile", "https://www.facebook.com/alex", _dir())
    assert m is not None and m.name == "Facebook"


def test_no_match_returns_none():
    assert match_entry("ObscureForum", "https://obscure.example/x", _dir()) is None


def test_enrich_flags_scrub_first_for_hard():
    hits = [SimpleNamespace(site="Facebook", url="https://facebook.com/alex")]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].scrub_first is True
    assert enriched[0].difficulty == "hard"


def test_enrich_does_not_flag_easy():
    hits = [SimpleNamespace(site="GitHub", url=None)]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].scrub_first is False
    assert enriched[0].matched.url == "https://gh/settings"


def test_enrich_accepts_dict_hits():
    hits = [{"site": "Spotify", "url": "https://spotify.com/x"}]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].matched.name == "Spotify"


def test_enrich_unmatched_hit_kept_with_no_match():
    hits = [{"site": "WeirdSite", "url": "https://weird.example"}]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].matched is None
    assert enriched[0].scrub_first is False
    assert enriched[0].difficulty is None


def test_scrub_difficulties_constant():
    assert "hard" in SCRUB_FIRST_DIFFICULTIES
    assert "impossible" in SCRUB_FIRST_DIFFICULTIES
    assert "easy" not in SCRUB_FIRST_DIFFICULTIES
