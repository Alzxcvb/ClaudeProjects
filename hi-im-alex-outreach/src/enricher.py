"""Email enrichment — Hunter.io stub for POC.

For Reddit POC, we capture the handle + post URL. Most Reddit users don't expose
email anywhere. Real enrichment happens later when Alex decides to chase a specific
prospect — at that point use the Reddit handle to find LinkedIn → company → Hunter.

This module is a stub for future build-out.
"""
import os
import requests
from typing import Optional


def find_email_by_domain_and_name(
    domain: str, first_name: str, last_name: Optional[str] = None
) -> Optional[str]:
    """Hunter.io email-finder. Free tier: 25 searches/mo. Not called yet."""
    api_key = os.environ.get("HUNTER_API_KEY")
    if not api_key:
        return None
    params = {"domain": domain, "first_name": first_name, "api_key": api_key}
    if last_name:
        params["last_name"] = last_name
    r = requests.get("https://api.hunter.io/v2/email-finder", params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("data", {}).get("email")
