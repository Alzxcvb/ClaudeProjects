"""Publish one variant to LinkedIn and record the run in the same breath.

Design note, and the reason this module exists at all. This account has produced
three separate duplicate reposts inside the 90-day cooldown. Every one had the
same root cause: a real posting event that was never logged, which left the CRM
saying "never run", which made the next session recommend the same copy again.

`./crm ran` already prints a warning when a variant has run before, but a
warning printed after the fact cannot stop anything. So this module inverts it:

  1. the cooldown check runs BEFORE the network call and HARD BLOCKS
  2. publishing and recording the run are one operation, not two steps
  3. if the database write somehow fails after a successful publish, the URN is
     printed with an exact recovery command, because a live post whose URN is
     lost can never be read by the analytics API

The post URN is the durable handle. Per-post analytics only work for posts the
app created; enumerating a member's own posts needs r_member_social, which is
restricted and unavailable. A URN not captured at creation is gone for good.
"""
import json
from datetime import datetime

from . import http
from .probe import LINKEDIN_VERSION, REST_POSTS, UGC_POSTS


# LinkedIn documents a 3,000 character limit on ugcPosts text. The Posts API
# documents only a FIELD_LENGTH_TOO_LONG error with no number, so the same
# figure is applied to both: it is the published limit and it matches the UI.
MAX_COMMENTARY_CHARS = 3000


class PublishBlocked(Exception):
    """Raised before anything reaches the network."""


class PublishFailed(Exception):
    """The API rejected the post, or it never left this machine. Nothing went live."""


class PublishAmbiguous(Exception):
    """The request went out and the reply was lost.

    LinkedIn may or may not have created the post. This is deliberately NOT a
    PublishFailed: telling someone "nothing went live" when it might have is
    how a retry turns into a duplicate, which is the exact failure this module
    exists to prevent.
    """


class RecordingFailed(Exception):
    """The post IS LIVE but the database write failed. Carries the URN."""

    def __init__(self, message, urn, url):
        Exception.__init__(self, message)
        self.urn = urn
        self.url = url


def build_payload(endpoint_key, author_urn, text, visibility="PUBLIC"):
    """The two endpoints want genuinely different shapes for the same post."""
    if endpoint_key == "rest_posts":
        return {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
    if endpoint_key == "ugc_posts":
        return {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }
    raise ValueError("unknown endpoint key: %s" % endpoint_key)


def _endpoint(endpoint_key):
    if endpoint_key == "rest_posts":
        return REST_POSTS, {
            "Linkedin-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
        }
    return UGC_POSTS, {"X-Restli-Protocol-Version": "2.0.0"}


def extract_urn(resp):
    """The created post's URN.

    LinkedIn returns it in the x-restli-id header on both endpoints; the body
    also carries it on ugcPosts. Header first, body as the fallback, because a
    missing URN is not a cosmetic problem here.
    """
    urn = resp.header("x-restli-id")
    if urn:
        return urn.strip()
    parsed = resp.json() or {}
    return (parsed.get("id") or "").strip() or None


def urn_to_url(urn):
    """A human-clickable permalink. LinkedIn has no documented endpoint that
    converts a URN to a URL, but the activity feed path is stable and this is
    only ever used for Alex to eyeball the post, never for an API call."""
    if not urn:
        return None
    return "https://www.linkedin.com/feed/update/%s/" % urn


def check_hard(variant, endpoint_key="rest_posts", expected_platform="linkedin"):
    """Defects that --force must never wave through.

    These are not scheduling judgements, they are broken input. Overriding a
    cooldown is a decision a human can reasonably make; publishing an empty
    body, or copy that LinkedIn will reject for length, or a variant written
    for another platform, is never a decision, it is a mistake.
    """
    from .littletext import escape

    reasons = []
    body = variant["body"]
    if body is None or not body.strip():
        reasons.append("this variant has no body recorded, so there is nothing to post")
    else:
        # Measure what actually goes on the wire. Escaping only ever grows the
        # text, so copy that reads as safely under the limit can cross it.
        outgoing = escape(body) if endpoint_key == "rest_posts" else body
        if len(outgoing) > MAX_COMMENTARY_CHARS:
            reasons.append(
                "the copy is %s characters after escaping (%s raw), over LinkedIn's "
                "%s character limit" % (len(outgoing), len(body), MAX_COMMENTARY_CHARS)
            )

    actual = (variant["platform"] or "").lower()
    if expected_platform and actual != expected_platform:
        # Publishing another platform's copy is bad; recording the run under
        # that platform is worse, because check_cooldown filters by platform
        # and the run would vanish from the LinkedIn cooldown check.
        reasons.append(
            "V%s is a %s variant, not %s, so it must not be published here"
            % (variant["id"], variant["platform"] or "unknown", expected_platform)
        )
    return reasons


def check_cooldown(conn, variant, cfg, force=False):
    """Repost protection. These reasons are the ones --force may override."""
    platform = variant["platform"]
    cooldown = (cfg.get("cooldown_days") or {}).get(platform)
    reasons = []

    same_variant = conn.execute(
        "SELECT id, posted_at FROM runs WHERE variant_id = ?"
        " ORDER BY posted_at DESC LIMIT 1", (variant["id"],)
    ).fetchone()
    if same_variant is not None:
        reasons.append(
            "this exact variant V%s already ran as R%s on %s"
            % (variant["id"], same_variant["id"], same_variant["posted_at"][:10])
        )

    same_idea = conn.execute(
        """SELECT r.id, r.posted_at, r.variant_id FROM runs r
           JOIN variants v ON v.id = r.variant_id
           WHERE v.idea_id = ? AND r.platform = ?
           ORDER BY r.posted_at DESC LIMIT 1""",
        (variant["idea_id"], platform),
    ).fetchone()
    if same_idea is not None:
        days = _days_since(same_idea["posted_at"])
        if days is None:
            # Fail closed. Several runs on record carry approximate timestamps,
            # so an unreadable date is a real possibility, and a gate that
            # exists to stop duplicate posts must not wave one through simply
            # because it could not do the arithmetic.
            reasons.append(
                "the same idea ran as R%s (V%s) but its date %r cannot be read, "
                "so the cooldown cannot be checked"
                % (same_idea["id"], same_idea["variant_id"], same_idea["posted_at"])
            )
        elif not cooldown:
            # No cooldown configured for this platform. Unknown is not the same
            # as zero, so surface the prior run instead of ignoring it.
            reasons.append(
                "the same idea ran %s days ago as R%s (V%s) and no cooldown is "
                "configured for %s, so this needs a human decision"
                % (days, same_idea["id"], same_idea["variant_id"], platform)
            )
        elif days < cooldown:
            reasons.append(
                "the same idea ran %s days ago as R%s (V%s), inside the %s-day cooldown"
                % (days, same_idea["id"], same_idea["variant_id"], cooldown)
            )

    if reasons and force:
        return []
    return reasons


def check_media(variant, text_only_ack=False):
    """Refuse to quietly publish an image post as text.

    Roughly half the variants on record are tagged `image`, and adding a visual
    to every post is a standing policy on this account precisely so the CRM can
    later prove whether images move the numbers. Version one of this publisher
    cannot attach media: that needs the Images API to obtain a urn:li:image
    first. Publishing an image-tagged variant anyway would silently drop the
    visual and quietly corrupt the media_type comparison the policy exists to
    produce. So it blocks, and the override has to be deliberate.
    """
    if text_only_ack:
        return []
    if (variant["media_type"] or "").lower() in ("image", "video", "document"):
        return ["V%s is tagged media_type=%s, but this publisher only sends text. "
                "Attaching media needs the Images API. Post it by hand with the "
                "visual, or re-run with --text-only to publish the words alone."
                % (variant["id"], variant["media_type"])]
    return []


def _days_since(posted_at):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return (datetime.now() - datetime.strptime(posted_at, fmt)).days
        except ValueError:
            continue
    return None


def publish(conn, cfg, variant, token, author_urn, endpoint_key,
            followers=None, note="", visibility="PUBLIC", force=False,
            dry_run=False):
    """Publish, then record. Never one without the other."""
    # Hard checks first and always. force does not reach them.
    hard = check_hard(variant, endpoint_key)
    if hard:
        raise PublishBlocked("; ".join(hard))
    blockers = check_cooldown(conn, variant, cfg, force=force)
    if blockers:
        raise PublishBlocked("; ".join(blockers))

    text = variant["body"]
    url, headers = _endpoint(endpoint_key)
    headers = dict(headers)
    headers["Authorization"] = "Bearer %s" % token
    payload = build_payload(endpoint_key, author_urn, text, visibility)

    if dry_run:
        return {
            "dry_run": True, "endpoint": url, "payload": payload,
            "headers": [k for k in sorted(headers) if k != "Authorization"],
        }

    resp = http.post(url, headers=headers, body=payload)

    if getattr(resp, "ambiguous", False):
        raise PublishAmbiguous(
            "the request reached LinkedIn but the reply was lost (%s). The post MAY "
            "be live. Open your feed and check before retrying, because retrying a "
            "post that already went out creates a duplicate." % (resp.body or "")
        )
    if not resp.ok:
        detail = ""
        if resp.status == 429:
            retry = resp.header("retry-after")
            detail = " Rate limited%s." % (" retry after %ss." % retry if retry else "")
        raise PublishFailed("HTTP %s from %s: %s%s"
                            % (resp.status, url, (resp.body or "")[:500], detail))

    urn = extract_urn(resp)
    permalink = urn_to_url(urn)

    if not urn:
        raise RecordingFailed(
            "post published but LinkedIn returned no URN; analytics can never read it",
            None, None,
        )

    try:
        run_id = _record_run(conn, cfg, variant, urn, permalink, followers, note)
    except Exception as exc:
        raise RecordingFailed(
            "post is LIVE but the run could not be recorded: %s" % (exc,),
            urn, permalink,
        )

    return {
        "dry_run": False, "run_id": run_id, "urn": urn, "url": permalink,
        "status": resp.status, "endpoint": url,
    }


def _record_run(conn, cfg, variant, urn, permalink, followers, note):
    from contentcrm.util import dow_bucket, now_iso, parse_when, slot_bucket

    posted_at, precision = parse_when(None)
    dow = dow_bucket(posted_at, precision)
    slot = slot_bucket(posted_at, precision, cfg["slots"])
    cur = conn.execute(
        "INSERT INTO runs (variant_id, platform, posted_at, posted_at_precision,"
        " dow_bucket, slot_bucket, followers_at_post, post_url, post_urn,"
        " created_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (variant["id"], variant["platform"], posted_at, precision, dow, slot,
         followers, permalink, urn, now_iso(), note or "published via LinkedIn API"),
    )
    conn.commit()
    return cur.lastrowid
