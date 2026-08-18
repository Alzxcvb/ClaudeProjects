"""Answer one question: which posting endpoint is this app actually allowed to call?

LinkedIn documents the answer inconsistently. The "Share on LinkedIn" product
page says every share is a POST to /v2/ugcPosts with no version header, and has
not been updated since 2023. The newer /rest/posts page lists w_member_social in
its own permissions table and says the Posts API replaces ugcPosts. Nothing
states which one a Share-on-LinkedIn-only app is entitled to. So we ask the API.

The trick is separating "you may not call this" from "your payload is wrong".
An empty JSON body cannot possibly create a post, but it still has to clear
authentication and authorization before it reaches payload validation. So:

    403  -> not entitled. The app lacks the permission for this endpoint.
    400  -> ENTITLED. It got past auth and is now complaining about the body.
    401  -> the token itself is bad, and the probe tells us nothing.

That distinction is what lets us find the right endpoint without putting a
single throwaway post on Alex's real feed under his real name.
"""
import json
from datetime import datetime

from . import http

# Pinned deliberately. Version 202508 sunset on 2026-08-17, the day before this
# was written. Anything at or after 202606 is current.
LINKEDIN_VERSION = "202606"

REST_POSTS = "https://api.linkedin.com/rest/posts"
UGC_POSTS = "https://api.linkedin.com/v2/ugcPosts"

CANDIDATES = [
    {
        "key": "rest_posts",
        "name": "Posts API",
        "url": REST_POSTS,
        "headers": {
            "Linkedin-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        },
    },
    {
        "key": "ugc_posts",
        "name": "ugcPosts API (legacy)",
        "url": UGC_POSTS,
        "headers": {"X-Restli-Protocol-Version": "2.0.0"},
    },
]


def classify(status, body):
    """Map an HTTP status to an entitlement verdict.

    Kept deliberately blunt. The raw status and body are always reported
    alongside this, so a wrong guess here is visible rather than load-bearing.
    """
    if status == 0:
        return "NETWORK_ERROR", "could not reach LinkedIn"
    if status == 401:
        return "BAD_TOKEN", "token missing, expired or malformed - probe inconclusive"
    if status == 403:
        return "NOT_ENTITLED", "app is not permitted to call this endpoint"
    if status in (400, 422):
        return "ENTITLED", "reached payload validation, so the permission is there"
    if status == 426:
        return "VERSION_PROBLEM", "Linkedin-Version header rejected"
    if status == 404:
        return "NOT_FOUND", "endpoint not exposed to this app"
    if status == 429:
        return "RATE_LIMITED", "too many requests; entitlement is unknown from this"
    if 500 <= status < 600:
        return "SERVER_ERROR", "LinkedIn side failure; entitlement is unknown from this"
    if 200 <= status < 300:
        # Should be unreachable with an empty body. Flag loudly if it happens.
        return "UNEXPECTED_SUCCESS", "empty body was accepted - CHECK THE FEED"
    return "UNKNOWN", "unmapped status"


def probe_one(token, candidate):
    headers = dict(candidate["headers"])
    headers["Authorization"] = "Bearer %s" % token
    resp = http.post(candidate["url"], headers=headers, body={})
    verdict, reason = classify(resp.status, resp.body)
    return {
        "key": candidate["key"],
        "name": candidate["name"],
        "url": candidate["url"],
        "request_headers": [k for k in sorted(headers) if k != "Authorization"],
        "status": resp.status,
        "verdict": verdict,
        "reason": reason,
        "body": (resp.body or "")[:800],
    }


def run(token, out_path=None):
    results = [probe_one(token, c) for c in CANDIDATES]
    report = {
        "probed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "linkedin_version_header": LINKEDIN_VERSION,
        "method": "POST with an empty JSON body; 403 = not entitled, 400 = entitled",
        "results": results,
        "recommended": recommend(results),
    }
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(report, fh, indent=2)
    return report


def recommend(results):
    """Prefer the modern Posts API when both are entitled; it is the one
    LinkedIn says replaces the other, and it is the versioned surface the
    analytics endpoints already live on."""
    entitled = [r for r in results if r["verdict"] == "ENTITLED"]
    if not entitled:
        return None
    for key in ("rest_posts", "ugc_posts"):
        for r in entitled:
            if r["key"] == key:
                return r["key"]
    return entitled[0]["key"]


def render(report):
    lines = ["Endpoint entitlement probe - %s" % report["probed_at"], ""]
    for r in report["results"]:
        lines.append("  %-22s %-14s HTTP %s" % (r["name"], r["verdict"], r["status"]))
        lines.append("      %s" % r["reason"])
        if r["body"]:
            lines.append("      %s" % r["body"][:200].replace("\n", " "))
        lines.append("")
    rec = report.get("recommended")
    lines.append("  VERDICT: %s" % (rec if rec else "inconclusive - see statuses above"))
    return "\n".join(lines)
