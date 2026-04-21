"""Tests for the HIBP client and breach manifest."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from erasure.breaches.hibp import (
    HIBPFailed,
    HIBPNotConfigured,
    HIBPRateLimited,
    check_and_save,
    check_email,
    save_manifest,
)
from erasure.breaches.schema import BreachHit, BreachesManifest


SAMPLE_HIBP_RESPONSE = [
    {
        "Name": "LinkedIn",
        "Title": "LinkedIn",
        "Domain": "linkedin.com",
        "BreachDate": "2012-05-05",
        "PwnCount": 164611595,
        "DataClasses": ["Email addresses", "Passwords"],
        "Description": "In May 2012...",
    },
    {
        "Name": "Adobe",
        "Title": "Adobe",
        "Domain": "adobe.com",
        "BreachDate": "2013-10-04",
        "PwnCount": 152445165,
        "DataClasses": ["Email addresses", "Password hints", "Passwords", "Usernames"],
    },
]


def _mock_transport(status_code: int, json_body=None, text_body: str = ""):
    def handler(request: httpx.Request) -> httpx.Response:
        if json_body is not None:
            return httpx.Response(status_code, json=json_body)
        return httpx.Response(status_code, text=text_body)
    return httpx.MockTransport(handler)


def _client(transport: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=transport)


def test_check_email_requires_api_key(monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    with pytest.raises(HIBPNotConfigured, match="HIBP_API_KEY"):
        check_email("a@b.com")


def test_check_email_rejects_invalid_address():
    with pytest.raises(ValueError, match="Invalid email"):
        check_email("not-an-email", api_key="stub")


def test_check_email_returns_empty_on_404():
    transport = _mock_transport(404)
    hits = check_email("clean@example.com", api_key="k", _client=_client(transport))
    assert hits == []


def test_check_email_parses_breaches():
    transport = _mock_transport(200, json_body=SAMPLE_HIBP_RESPONSE)
    hits = check_email("pwned@example.com", api_key="k", _client=_client(transport))
    assert len(hits) == 2
    assert hits[0].title == "LinkedIn"
    assert hits[0].domain == "linkedin.com"
    assert hits[0].breach_date == "2012-05-05"
    assert hits[0].pwn_count == 164611595
    assert "Passwords" in hits[0].data_classes


def test_check_email_rate_limited():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "3"})
    transport = httpx.MockTransport(handler)
    with pytest.raises(HIBPRateLimited, match="3"):
        check_email("a@b.com", api_key="k", _client=_client(transport))


def test_check_email_401_maps_to_not_configured():
    transport = _mock_transport(401, text_body="bad key")
    with pytest.raises(HIBPNotConfigured, match="401"):
        check_email("a@b.com", api_key="k", _client=_client(transport))


def test_check_email_500_maps_to_failed():
    transport = _mock_transport(500, text_body="server error")
    with pytest.raises(HIBPFailed, match="500"):
        check_email("a@b.com", api_key="k", _client=_client(transport))


def test_save_manifest_round_trips(tmp_path):
    hits = [BreachHit(name="LinkedIn", title="LinkedIn", domain="linkedin.com")]
    path = save_manifest("a@b.com", hits, scan_dir=tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["email"] == "a@b.com"
    assert data["found_count"] == 1
    assert data["breaches"][0]["title"] == "LinkedIn"
    BreachesManifest.model_validate(data)


def test_check_and_save_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    transport = _mock_transport(200, json_body=SAMPLE_HIBP_RESPONSE)
    path = check_and_save("a@b.com", api_key="k", _client=_client(transport))
    assert path.parent.name == "breaches"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["found_count"] == 2
