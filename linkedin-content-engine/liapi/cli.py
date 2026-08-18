"""li: the LinkedIn side of the content engine.

    ./li setup     what to create in the LinkedIn developer portal
    ./li auth      connect the account, store the token
    ./li status    is the token still alive, and for how long
    ./li probe     which posting endpoint is this app entitled to call
    ./li preview   exactly what would be sent, without sending it
    ./li post      publish a variant and record the run in one step

Design rule for this whole surface: nothing publishes without a human reading
the copy first and typing the word publish. This account has already produced
three duplicate reposts; the cost of an accidental post here is real and public.
"""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from contentcrm.config import db_path, load_config
from contentcrm.db import connect
from contentcrm.refs import RefError, resolve_idea, resolve_variant

from . import oauth, probe, tokens
from .littletext import escape, escaped_chars, find_reserved
from .publish import (MAX_COMMENTARY_CHARS, PublishAmbiguous, PublishBlocked,
                      PublishFailed, RecordingFailed, build_payload,
                      check_cooldown, check_hard, check_media, publish)

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / ".li-app.json"
PROBE_REPORT = ROOT / "liapi" / "endpoint-probe-report.json"


# ------------------------------------------------------------------ helpers --

def load_app():
    """Client id and secret. File first, environment second."""
    if APP_PATH.exists():
        data = json.loads(APP_PATH.read_text())
    else:
        data = {}
    cid = os.environ.get("LINKEDIN_CLIENT_ID") or data.get("client_id")
    secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or data.get("client_secret")
    redirect = data.get("redirect_uri") or oauth.DEFAULT_REDIRECT_URI
    return cid, secret, redirect


def require_token():
    rec = tokens.load()
    if not rec:
        sys.exit("No token stored. Run: ./li auth")
    if tokens.is_expired(rec):
        sys.exit("Token expired on %s. Run: ./li auth" % rec.get("expires_at"))
    return rec


def mask(value, keep=4):
    """Never reveal the tail. A client secret is short enough that showing the
    last characters as well as the first gives away a third of it."""
    if not value:
        return "(not set)"
    value = str(value)
    if keep <= 0 or len(value) <= keep:
        return "set (%d chars)" % len(value)
    return "%s... (%d chars)" % (value[:keep], len(value))


def open_conn(db_override=None):
    cfg = load_config()
    return connect(db_override or db_path(cfg)), cfg


# -------------------------------------------------------------------- setup --

def cmd_setup(args):
    cid, secret, redirect = load_app()
    print("""
LinkedIn app setup. Do this once, in a browser, signed in as yourself.

1. Confirm you are a SUPER ADMIN of the company page
   https://www.linkedin.com/company/hiimalex-llc/
   A page is required to create an app, and a super admin has to verify it.

2. Create the app
   https://www.linkedin.com/developers/apps/new
     App name        Hi I'm Alex Content Engine
     LinkedIn Page   hiimalex-llc
     App logo        any square image
   Then click Verify on the Settings tab and complete the page verification.
   The verification link expires after 30 days.

3. Products tab, request BOTH. Both are self serve, neither needs a review.
     Share on LinkedIn
     Sign In with LinkedIn using OpenID Connect
   The second one is not optional: it is the only self serve way to learn your
   own member id, and the id is required as the post author.

4. Auth tab, add this exact redirect URL:
     %s
   LinkedIn requires HTTPS here, it must match exactly, and it cannot contain a #.

5. Copy the Client ID and Client Secret from the Auth tab into %s:
     {"client_id": "...", "client_secret": "...", "redirect_uri": "%s"}
   That file is gitignored. Do not paste the secret into a chat window.

6. Run:  ./li auth

Current state
  client_id      %s
  client_secret  %s
  redirect_uri   %s
  token          %s
""" % (redirect, APP_PATH.name, redirect, mask(cid, 6), mask(secret, 3), redirect,
       tokens.summary(tokens.load())))


# --------------------------------------------------------------------- auth --

def cmd_auth(args):
    cid, secret, redirect = load_app()
    if not cid or not secret:
        sys.exit("Missing client id or secret. Run ./li setup and create %s" % APP_PATH.name)

    scopes = list(oauth.DEFAULT_SCOPES)
    if args.with_analytics:
        scopes.append(oauth.ANALYTICS_SCOPE)
        print("Requesting the analytics scope too. Note: changing the scope set\n"
              "invalidates every token previously granted under the old set.\n")

    url, state = oauth.authorize_url(cid, redirect, scopes=scopes)
    print("Opening LinkedIn to authorise these scopes:\n  %s\n" % " ".join(scopes))
    print(url + "\n")
    oauth.open_browser(url)
    print("Sign in, click Allow, then copy the code from the callback page.")
    # Deliberately visible, unlike the access token in `./li token`. This is the
    # authorization code, not the token: it is single use, expires in 30 minutes,
    # is useless without the client secret, and is already on screen in the
    # browser. Showing it lets you see whether a long callback URL pasted whole
    # or got truncated, which is the common failure here. Do not "harden" this
    # into getpass without weighing that.
    pasted = input("Paste the code (or the whole callback URL): ").strip()

    try:
        code = oauth.parse_redirect(pasted, expected_state=state)
    except Exception as exc:
        sys.exit("Could not read that: %s" % exc)

    payload = oauth.exchange_code(code, cid, secret, redirect)
    record = tokens.record_grant(payload, " ".join(scopes), cid)
    print("\nToken stored in %s (owner read/write only)" % tokens.TOKEN_PATH.name)
    print("  %s" % tokens.summary(record))
    print("  scopes granted: %s" % (record.get("scope_granted") or "(not reported)"))

    try:
        urn, info = oauth.fetch_person_urn(record["access_token"])
        tokens.set_person_urn(urn)
        print("  author URN: %s  (%s)" % (urn, info.get("name", "")))
    except Exception as exc:
        print("  could not read the member id: %s" % exc)
        print("  posting needs this. Check that Sign In with LinkedIn using")
        print("  OpenID Connect is added on the Products tab, then run ./li auth again.")

    print("\nNext: ./li probe")


def cmd_token(args):
    """Store a token generated by hand in LinkedIn's Developer Portal.

    LinkedIn ships a token generator at
    linkedin.com/developers/tools/oauth/token-generator which needs no redirect
    URL and no callback page. That makes it the fastest way to the first token,
    and it means the OAuth callback page does not have to be deployed before
    anything can be tested. `./li auth` remains the better path for renewals,
    because it is scripted.
    """
    print("Open: https://www.linkedin.com/developers/tools/oauth/token-generator")
    print("Pick your app, tick openid, profile and w_member_social, generate,")
    print("then copy the access token.\n")
    # Read without echoing, and deliberately offer no --token flag: a token on
    # the command line lands in shell history and in `ps` output, and Alex's
    # standing rule is that a printed secret has to be rotated.
    if args.token_file:
        token = Path(args.token_file).read_text().strip()
    else:
        token = getpass.getpass("Paste the access token (input hidden): ").strip()
    if not token:
        sys.exit("nothing pasted")

    cid, _secret, _redirect = load_app()
    # LinkedIn documents a 60 day lifespan for every access token. The generator
    # does not hand back expires_in, so this is derived from that documented
    # figure rather than measured, and status labels it as such.
    payload = {"access_token": token, "expires_in": args.expires_in_days * 86400,
               "scope": args.scope}
    record = tokens.record_grant(payload, args.scope, cid)
    record["expiry_source"] = ("assumed %s day lifespan, not reported by the generator"
                               % args.expires_in_days)
    # The generator does not tell us what was actually granted, so this scope
    # string is Alex's claim, not LinkedIn's. Say so, or status would present it
    # identically to the auth path where LinkedIn reports it.
    record["scope_source"] = "self-declared, not confirmed by LinkedIn"
    tokens.save(record)
    print("\nStored. %s" % tokens.summary(record))

    try:
        urn, info = oauth.fetch_person_urn(token)
        tokens.set_person_urn(urn)
        print("author URN: %s  (%s)" % (urn, info.get("name", "")))
    except Exception as exc:
        print("could not read the member id: %s" % exc)
        print("Add 'Sign In with LinkedIn using OpenID Connect' on the Products")
        print("tab, regenerate the token with openid and profile ticked, retry.")
    print("\nNext: ./li probe")


def cmd_status(args):
    rec = tokens.load()
    cid, secret, redirect = load_app()

    # --check is what cron runs. Silent while the token is healthy, one line
    # when it is not, so a weekly job stays quiet until it actually matters.
    if getattr(args, "check", False):
        if rec is None:
            return 0  # not connected yet; nagging about that is not this job
        if tokens.needs_attention(rec):
            print(tokens.summary(rec))
            return 1
        return 0

    print("app")
    print("  client_id      %s" % mask(cid, 6))
    print("  client_secret  %s" % mask(secret, 3))
    print("  redirect_uri   %s" % redirect)
    warn = tokens.permission_warning(APP_PATH)
    if warn:
        print("  WARNING: %s" % warn)
    print("token")
    print("  %s" % tokens.summary(rec))
    if rec:
        print("  issued         %s" % rec.get("issued_at"))
        if rec.get("expiry_source"):
            print("  expiry basis   %s" % rec["expiry_source"])
        print("  scopes         %s" % (rec.get("scope_granted") or rec.get("scope_requested")))
        if rec.get("scope_source"):
            print("  scope basis    %s" % rec["scope_source"])
        print("  author URN     %s" % (rec.get("person_urn") or "(not resolved, run ./li auth)"))
    if rec and tokens.needs_attention(rec):
        print("\n  Renew soon. LinkedIn skips the consent screen only while you are")
        print("  still signed in AND the current token has not yet expired.")


def cmd_whoami(args):
    rec = require_token()
    urn, info = oauth.fetch_person_urn(rec["access_token"])
    print("%s\n%s" % (urn, json.dumps(info, indent=2)))


# -------------------------------------------------------------------- probe --

def cmd_probe(args):
    rec = require_token()
    report = probe.run(rec["access_token"], out_path=str(PROBE_REPORT))
    print(probe.render(report))
    print("\n  full report written to %s" % PROBE_REPORT.name)
    if report["recommended"]:
        print("  use this endpoint:  ./li post <variant> --endpoint %s" % report["recommended"])


# ------------------------------------------------------------------ preview --

def _show_copy(variant, endpoint_key):
    """Print the copy for approval, and be exact about what changes on the wire."""
    body = variant["body"] or ""
    print("-" * 66)
    print(body)
    print("-" * 66)

    outgoing = escape(body) if endpoint_key == "rest_posts" else body
    over = len(outgoing) > MAX_COMMENTARY_CHARS
    print("\nlength: %s characters going out (%s written)%s"
          % (len(outgoing), len(body),
             "   OVER THE %s LIMIT" % MAX_COMMENTARY_CHARS if over else ""))

    if endpoint_key == "rest_posts":
        changed = escaped_chars(body)
        if changed:
            print("\nescaped for LinkedIn's little format (they still render as written):")
            print("  %s" % " ".join(changed))
            kept = [c for c in find_reserved(body) if c not in changed]
            if kept:
                # Almost always the hashtag case. Say it plainly rather than
                # let the operator assume everything got escaped.
                print("  left as-is (read as LinkedIn markup, not literal text): %s"
                      % " ".join(kept))
            print("\nwhat actually goes on the wire:")
            print("  %s" % (outgoing[:400] + ("..." if len(outgoing) > 400 else "")))
        else:
            print("\nnothing needed escaping")
    return body


def cmd_preview(args):
    conn, cfg = open_conn(args.db)
    variant = resolve_variant(conn, args.variant)
    idea = resolve_idea(conn, str(variant["idea_id"]))
    rec = tokens.load()
    author = (rec or {}).get("person_urn") or "urn:li:person:UNKNOWN"

    print("V%s of I%s (%s), platform %s, stage %s"
          % (variant["id"], idea["id"], idea["slug"], variant["platform"], variant["stage"]))
    _show_copy(variant, args.endpoint)

    blockers = (check_hard(variant, args.endpoint) + check_cooldown(conn, variant, cfg)
                + check_media(variant))
    print("\npre-flight gate: %s" % ("BLOCKED" if blockers else "clear"))
    for b in blockers:
        print("  - %s" % b)

    text = escape(variant["body"] or "") if args.endpoint == "rest_posts" else (variant["body"] or "")
    payload = build_payload(args.endpoint, author, text)
    print("\npayload that would be POSTed to %s:" % args.endpoint)
    print(json.dumps(payload, indent=2)[:1400])
    print("\nnothing was sent")


# --------------------------------------------------------------------- post --

def cmd_post(args):
    conn, cfg = open_conn(args.db)
    rec = require_token()
    author = rec.get("person_urn")
    if not author:
        sys.exit("No author URN stored. Run ./li auth (needs the openid and profile scopes).")

    variant = resolve_variant(conn, args.variant)
    idea = resolve_idea(conn, str(variant["idea_id"]))

    hard_blockers = check_hard(variant, args.endpoint)
    cooldown_blockers = check_cooldown(conn, variant, cfg, force=args.force)
    media_blockers = check_media(variant, text_only_ack=args.text_only)
    blockers = hard_blockers + cooldown_blockers + media_blockers
    if blockers:
        print("REFUSING to publish V%s:" % variant["id"])
        for b in blockers:
            print("  - %s" % b)
        if hard_blockers:
            # Deliberately not overridable. These are broken input, not a
            # scheduling judgement, and no flag should paper over them.
            print("\nNo flag overrides the first of those. Fix the variant.")
            sys.exit(1)
        fixes = []
        if cooldown_blockers:
            fixes.append("--force to override the cooldown gate")
        if media_blockers:
            fixes.append("--text-only to publish an image post as words alone")
        print("\nTo proceed anyway you would need: %s" % ", and ".join(fixes))
        sys.exit(1)

    print("\nAbout to publish to LinkedIn as %s" % author)
    print("V%s of I%s (%s), stage %s\n" % (variant["id"], idea["id"], idea["slug"], variant["stage"]))
    _show_copy(variant, args.endpoint)
    if tokens.needs_attention(rec):
        print("\n  note: %s" % tokens.summary(rec))

    if not args.yes:
        print("\nThis goes live on your real feed, under your real name.")
        answer = input('Type "publish" to send, anything else cancels: ').strip()
        if answer != "publish":
            sys.exit("cancelled, nothing was sent")

    # Escaping is applied here, once, at the boundary. The variant in the
    # database always keeps the copy exactly as written.
    text = escape(variant["body"] or "") if args.endpoint == "rest_posts" else (variant["body"] or "")
    outgoing = dict(variant)
    outgoing["body"] = text

    try:
        result = publish(conn, cfg, outgoing, rec["access_token"], author,
                         args.endpoint, followers=args.followers,
                         note=args.note or "published via LinkedIn API",
                         force=True,  # already gated above
                         dry_run=args.dry_run)
    except PublishBlocked as exc:
        sys.exit("blocked: %s" % exc)
    except PublishFailed as exc:
        sys.exit("NOT published, nothing went live. %s" % exc)
    except PublishAmbiguous as exc:
        print("\n" + "!" * 66)
        print("UNCLEAR whether this published.")
        print("  %s" % exc)
        print("\nDo NOT just retry. Open your feed first:")
        print("  https://www.linkedin.com/in/me/recent-activity/all/")
        print("If it IS there, record it so the tracker matches reality:")
        print('  ./crm ran V%s --url "<paste the post URL>"' % variant["id"])
        print("If it is NOT there, re-run the same ./li post command.")
        print("!" * 66)
        sys.exit(3)
    except RecordingFailed as exc:
        print("\n" + "!" * 66)
        print("THE POST IS LIVE but the run was not recorded.")
        if exc.urn:
            print("  URN: %s" % exc.urn)
            print("  URL: %s" % exc.url)
            print("Record it by hand NOW or analytics can never read this post:")
            print('  ./crm ran V%s --url "%s" --urn "%s"'
                  % (variant["id"], exc.url, exc.urn))
        else:
            # No URN came back at all. Printing the recovery command with the
            # word None in it would pollute the CRM with a literal "None", so
            # say what is actually true instead.
            print("  LinkedIn returned no post id, so the URN could not be captured.")
            print("  This post can never be read by the analytics API.")
            print("  Find the post on your feed, then record it with its URL:")
            print('    ./crm ran V%s --url "<paste the post URL>"' % variant["id"])
        print("!" * 66)
        sys.exit(2)

    if result.get("dry_run"):
        print("\ndry run, nothing sent. payload:")
        print(json.dumps(result["payload"], indent=2)[:1200])
        return

    print("\npublished and recorded together")
    print("  run   R%s" % result["run_id"])
    print("  urn   %s" % result["urn"])
    print("  url   %s" % result["url"])
    print("\nnext: ./crm status  (the 24h checkpoint is now on the clock)")


# --------------------------------------------------------------------- main --

def main(argv=None):
    p = argparse.ArgumentParser(prog="li", description="Publish to LinkedIn from the content CRM.")
    p.add_argument("--db", help="override the database path (default: config db_path)")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("setup", help="what to create in the LinkedIn developer portal")

    a = sub.add_parser("auth", help="connect the account and store a token")
    a.add_argument("--with-analytics", action="store_true",
                   help="also request r_member_postAnalytics (only after approval)")

    st = sub.add_parser("status", help="token health and stored identity")
    st.add_argument("--check", action="store_true",
                    help="silent unless the token needs renewing; exit 1 when it does")
    tk = sub.add_parser("token", help="store a token made in the portal token generator")
    tk.add_argument("--token-file", help="read the token from a file instead of prompting")
    tk.add_argument("--scope", default="openid profile w_member_social",
                    help="scopes you ticked in the generator")
    tk.add_argument("--expires-in-days", type=int, default=60,
                    help="LinkedIn's documented lifespan; override if you know better")

    sub.add_parser("whoami", help="call userinfo and show the member id")
    sub.add_parser("probe", help="which posting endpoint this app may call")

    pv = sub.add_parser("preview", help="show exactly what would be sent")
    pv.add_argument("variant")
    pv.add_argument("--endpoint", default="rest_posts", choices=["rest_posts", "ugc_posts"])

    po = sub.add_parser("post", help="publish a variant and record the run")
    po.add_argument("variant")
    po.add_argument("--endpoint", default="rest_posts", choices=["rest_posts", "ugc_posts"])
    po.add_argument("--followers", type=int, help="your follower count right now")
    po.add_argument("--note", default="")
    po.add_argument("--force", action="store_true", help="override the cooldown gate")
    po.add_argument("--text-only", action="store_true",
                    help="acknowledge that an image-tagged variant goes out as text")
    po.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    po.add_argument("--dry-run", action="store_true", help="build the payload, send nothing")

    args = p.parse_args(argv)
    if not args.command:
        p.print_help()
        return 0

    handlers = {
        "setup": cmd_setup, "auth": cmd_auth, "status": cmd_status, "token": cmd_token,
        "whoami": cmd_whoami, "probe": cmd_probe, "preview": cmd_preview,
        "post": cmd_post,
    }
    try:
        return handlers[args.command](args) or 0
    except RefError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    sys.exit(main())
