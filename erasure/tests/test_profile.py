from datetime import date

import pytest
from pydantic import ValidationError

from erasure.profile import UserProfile


def test_minimal_profile():
    p = UserProfile(name="Jane Doe")
    assert p.name == "Jane Doe"
    assert p.addresses == []
    assert p.dob is None


def test_full_profile():
    p = UserProfile(
        name="John Michael Smith",
        addresses=["123 Main St"],
        phones=["555-1234"],
        emails=["john@example.com"],
        dob=date(1985, 6, 15),
        prior_addresses=["456 Oak Ave"],
        aliases=["J. Smith"],
    )
    assert p.dob == date(1985, 6, 15)
    assert len(p.emails) == 1


def test_name_required():
    with pytest.raises(ValidationError):
        UserProfile()  # type: ignore[call-arg]


def test_search_variants_two_part_name():
    p = UserProfile(name="Jane Doe")
    variants = p.to_search_variants()
    assert "Jane Doe" in variants
    assert "Doe, Jane" in variants
    assert "Doe Jane" in variants


def test_search_variants_three_part_name():
    p = UserProfile(name="John Michael Smith")
    variants = p.to_search_variants()
    assert "John Michael Smith" in variants
    assert "John Smith" in variants
    assert "John M. Smith" in variants
    assert "Smith, John Michael" in variants


def test_search_variants_includes_aliases():
    p = UserProfile(name="Jane Doe", aliases=["JD", "Jenny Doe"])
    variants = p.to_search_variants()
    assert "JD" in variants
    assert "Jenny Doe" in variants


def test_search_variants_no_duplicates():
    p = UserProfile(name="Jane Doe", aliases=["Jane Doe"])
    variants = p.to_search_variants()
    assert variants.count("Jane Doe") == 1


def test_dob_string_coercion():
    p = UserProfile(name="Jane Doe", dob="1990-01-01")  # type: ignore[arg-type]
    assert p.dob == date(1990, 1, 1)
