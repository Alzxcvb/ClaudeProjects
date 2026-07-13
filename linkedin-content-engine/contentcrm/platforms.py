"""Platform adapters.

v1: every platform gets the same interface and manual metric entry. An
adapter contributes only naming hints (what the platform's analytics screen
calls each canonical metric) so the log prompt reads naturally. No scrapers,
no APIs, no posting, by design.
"""

PLATFORMS = {
    "linkedin": {
        "label": "LinkedIn",
        "hints": {
            "impressions": "impressions",
            "reactions": "reactions",
            "comments": "comments",
            "reposts": "reposts",
            "link_clicks": "clicks on your tracked link, not shown by LinkedIn",
            "profile_visits": "weekly aggregate only, treat as soft signal",
            "bookings": "from the Calendly 'where did you find me' answer",
        },
    },
    "x": {
        "label": "X",
        "hints": {
            "impressions": "impressions",
            "reactions": "likes",
            "comments": "replies",
            "reposts": "reposts plus quotes",
            "saves": "bookmarks",
            "link_clicks": "link clicks in post analytics",
        },
    },
    "instagram": {
        "label": "Instagram",
        "hints": {
            "impressions": "reach",
            "reactions": "likes",
            "comments": "comments",
            "reposts": "shares",
            "saves": "saves",
            "profile_visits": "profile visits in insights",
        },
    },
}


def normalise(name):
    key = (name or "").strip().lower()
    if key not in PLATFORMS:
        known = ", ".join(sorted(PLATFORMS))
        raise ValueError(f"unknown platform {name!r} (known: {known})")
    return key


def entry_hints(platform):
    return PLATFORMS[normalise(platform)]["hints"]
