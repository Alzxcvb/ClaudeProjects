"""Tests for the account-deletion directory bridge."""

from __future__ import annotations

from types import SimpleNamespace

from erasure.accounts.justdelete import (
    DeletionEntry,
    LEGAL_REQUEST_DIFFICULTIES,
    SCRUB_FIRST_DIFFICULTIES,
    enrich_hits,
    load_directory,
    match_entry,
)

VALID_DIFFICULTIES = {"easy", "medium", "hard", "limited", "impossible"}


def _dir():
    return [
        DeletionEntry(name="Facebook", domains=["facebook.com"], difficulty="hard", url="https://fb/delete"),
        DeletionEntry(name="GitHub", domains=["github.com"], difficulty="easy", url="https://gh/settings"),
        DeletionEntry(name="Spotify", domains=["spotify.com"], difficulty="easy", url="https://spotify/close"),
        DeletionEntry(name="X", domains=["x.com", "twitter.com"], difficulty="easy", url="https://x/deactivate"),
        DeletionEntry(name="Chess.com", domains=["chess.com"], difficulty="limited", url="https://chess/close"),
        DeletionEntry(
            name="123RF",
            domains=["123rf.com"],
            difficulty="hard",
            email="frsales@123rf.com",
            email_body="I want my account to be deleted.",
        ),
    ]


def test_bundled_directory_loads_and_is_nonempty():
    entries = load_directory()
    # The bundled snapshot is the full JustDeleteMe dataset, not a sample.
    assert len(entries) >= 2000
    assert all(e.difficulty in VALID_DIFFICULTIES for e in entries)
    # Every entry has a name and at least one domain
    assert all(e.name and e.domains for e in entries)


def test_bundled_directory_carries_email_deletion_paths():
    entries = load_directory()
    with_email = [e for e in entries if e.email]
    assert len(with_email) >= 100


def test_domain_property_returns_primary_domain():
    entry = DeletionEntry(name="X", domains=["x.com", "twitter.com"], difficulty="easy")
    assert entry.domain == "x.com"
    assert DeletionEntry(name="Nowhere", difficulty="easy").domain is None


def test_match_by_exact_name():
    m = match_entry("GitHub", None, _dir())
    assert m is not None and m.name == "GitHub"


def test_match_is_case_insensitive():
    m = match_entry("github", None, _dir())
    assert m is not None and m.name == "GitHub"


def test_match_by_domain_in_url():
    m = match_entry("Some Profile", "https://www.facebook.com/alex", _dir())
    assert m is not None and m.name == "Facebook"


def test_match_by_secondary_domain():
    """An entry lists several domains; a hit on any of them resolves."""
    m = match_entry("Some Profile", "https://twitter.com/alex", _dir())
    assert m is not None and m.name == "X"


def test_match_by_subdomain():
    m = match_entry("Some Profile", "https://gist.github.com/alex", _dir())
    assert m is not None and m.name == "GitHub"


def test_host_match_is_not_a_substring_match():
    """A domain appearing inside a path or query must not count as a hit."""
    assert match_entry("Some Profile", "https://evil.example/?to=facebook.com", _dir()) is None


def test_short_brand_does_not_substring_match():
    """The brand 'x' (from x.com) must not swallow unrelated site names."""
    m = match_entry("Xbox", None, _dir())
    assert m is None


def test_no_match_returns_none():
    assert match_entry("ObscureForum", "https://obscure.example/x", _dir()) is None


def test_enrich_flags_scrub_first_for_hard():
    hits = [SimpleNamespace(site="Facebook", url="https://facebook.com/alex")]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].scrub_first is True
    assert enriched[0].legal_request is False
    assert enriched[0].difficulty == "hard"


def test_enrich_flags_legal_request_for_limited():
    hits = [{"site": "Chess.com", "url": "https://chess.com/member/alex"}]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].legal_request is True
    assert enriched[0].scrub_first is False
    assert enriched[0].difficulty == "limited"


def test_enrich_surfaces_email_deletion_path():
    hits = [{"site": "123RF", "url": "https://123rf.com/profile"}]
    enriched = enrich_hits(hits, _dir())
    assert enriched[0].matched.email == "frsales@123rf.com"
    assert enriched[0].matched.email_body


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
    assert enriched[0].legal_request is False
    assert enriched[0].difficulty is None


def test_scrub_difficulties_constant():
    assert "hard" in SCRUB_FIRST_DIFFICULTIES
    assert "impossible" in SCRUB_FIRST_DIFFICULTIES
    assert "easy" not in SCRUB_FIRST_DIFFICULTIES
    # "limited" means deletable with a privacy-law request, so it is not a
    # scrub case; it routes to `erasure legal request` instead.
    assert "limited" not in SCRUB_FIRST_DIFFICULTIES
    assert "limited" in LEGAL_REQUEST_DIFFICULTIES
