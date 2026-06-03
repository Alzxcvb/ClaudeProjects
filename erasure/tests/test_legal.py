"""Tests for the deletion-request letter generator."""

from __future__ import annotations

from datetime import date

import pytest

from erasure.legal.generator import (
    build_identifiers_block,
    render_request,
    save_request,
)
from erasure.legal.templates import JURISDICTIONS
from erasure.profile import UserProfile


def _profile() -> UserProfile:
    return UserProfile(
        name="Jane Q Public",
        emails=["jane@example.com", "jq@example.org"],
        phones=["+1-555-0100"],
        addresses=["1 Main St, Sacramento, CA 95814"],
        prior_addresses=["9 Old Rd, Reno, NV 89501"],
        aliases=["Janie Public"],
        dob=date(1990, 5, 1),
    )


FIXED_DAY = date(2026, 6, 3)


def test_ccpa_cites_statutes_and_default_deadline():
    text = render_request(profile=_profile(), jurisdiction="ccpa", today=FIXED_DAY)
    assert "1798.105" in text
    assert "1798.120" in text
    assert "California Delete Act" in text or "SB 362" in text
    # CCPA default deadline is 45 days
    assert "within 45 days" in text


def test_gdpr_cites_articles_and_30_day_clock():
    text = render_request(profile=_profile(), jurisdiction="gdpr", today=FIXED_DAY)
    assert "Article 17" in text
    assert "Article 21" in text
    assert "within 30 days" in text


def test_generic_mentions_all_regimes():
    text = render_request(profile=_profile(), jurisdiction="generic", today=FIXED_DAY)
    assert "California Consumer Privacy Act" in text
    assert "General Data Protection Regulation" in text


def test_recipient_and_requester_substituted():
    text = render_request(
        profile=_profile(), jurisdiction="ccpa", recipient="Spokeo, Inc.", today=FIXED_DAY
    )
    assert "Spokeo, Inc." in text
    assert "Jane Q Public" in text


def test_default_recipient_when_none():
    text = render_request(profile=_profile(), jurisdiction="ccpa", today=FIXED_DAY)
    assert "Data Privacy Officer" in text


def test_deadline_override():
    text = render_request(
        profile=_profile(), jurisdiction="gdpr", deadline_days=14, today=FIXED_DAY
    )
    assert "within 14 days" in text


def test_date_is_formatted_human_readable():
    text = render_request(profile=_profile(), jurisdiction="ccpa", today=FIXED_DAY)
    assert "June 03, 2026" in text


def test_dob_excluded_by_default_included_on_flag():
    without = render_request(profile=_profile(), jurisdiction="ccpa", today=FIXED_DAY)
    assert "1990-05-01" not in without
    with_dob = render_request(
        profile=_profile(), jurisdiction="ccpa", include_dob=True, today=FIXED_DAY
    )
    assert "1990-05-01" in with_dob


def test_identifiers_block_lists_contact_details():
    block = build_identifiers_block(_profile())
    assert "Jane Q Public" in block
    assert "jane@example.com" in block
    assert "+1-555-0100" in block
    assert "Sacramento" in block
    assert "Janie Public" in block


def test_unknown_jurisdiction_raises():
    with pytest.raises(ValueError, match="Unknown jurisdiction"):
        render_request(profile=_profile(), jurisdiction="ukgdpr", today=FIXED_DAY)


def test_no_em_dashes_in_any_template():
    # Em dash / en dash are an AI tell and break the "human letter" feel.
    for key in JURISDICTIONS:
        text = render_request(profile=_profile(), jurisdiction=key, today=FIXED_DAY)
        assert "—" not in text, f"em dash in {key}"
        assert "–" not in text, f"en dash in {key}"


def test_save_request_writes_file(tmp_path):
    text = render_request(profile=_profile(), jurisdiction="ccpa", recipient="Spokeo", today=FIXED_DAY)
    path = save_request(text, jurisdiction="ccpa", recipient="Spokeo", out_dir=tmp_path)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == text
    assert path.suffix == ".txt"
    assert "spokeo" in path.name.lower()
