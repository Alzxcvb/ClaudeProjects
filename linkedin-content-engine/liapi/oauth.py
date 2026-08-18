"""The three legged OAuth flow, run from a terminal.

The design follows LinkedIn's documented constraints rather than the usual
CLI-app shortcut, because two of them rule that shortcut out.

The redirect URL must be HTTPS. LinkedIn's 3-legged OAuth page says plainly
"Add the redirect (callback) URL via HTTPS to your server", and documents no
loopback exemption, so the customary http://localhost callback server is a
gamble. It also documents that the URL must be absolute, must not contain a #,
that query parameters are stripped, and that a mismatch is a 401. Alex already
owns hiimalex.ai on Vercel, so the callback lives there: a static page that
does nothing but show the code for copying. Documented, exact match, no local
server, and nothing to keep running.

There is also no programmatic refresh. LinkedIn: "Programmatic refresh tokens
are available for a limited set of partners." Renewal is running this same flow
again, and LinkedIn bypasses the consent screen only while the member is still
signed in AND the current token has not yet expired. Renewing late costs a
consent click; forgetting entirely stops posting silently. Hence the warnings.

One trap worth knowing: "If you request a different scope than the previously
granted scope, all the previous access tokens are invalidated." Adding the
analytics scope later will therefore kill the posting token, and both must be
re-granted together.
"""
import secrets
import urllib.parse
import webbrowser

from . import http as lihttp

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# The redirect target. Static page on Alex's own domain, so it satisfies the
# HTTPS requirement using infrastructure that already exists.
DEFAULT_REDIRECT_URI = "https://hiimalex.ai/li/callback"

# w_member_social  -> publish to the member's own feed   (Share on LinkedIn)
# openid, profile  -> identify the member, giving the id needed to build
#                     urn:li:person:{id}  (Sign In with LinkedIn using OpenID
#                     Connect). Both products are self serve; neither needs
#                     LinkedIn review. `email` is deliberately not requested:
#                     nothing here needs it, and LinkedIn asks for the least
#                     number of scopes.
DEFAULT_SCOPES = ["openid", "profile", "w_member_social"]

# Requested only once the Community Management API is approved. Adding it
# invalidates every token granted under the smaller scope set.
ANALYTICS_SCOPE = "r_member_postAnalytics"


def new_state():
    """CSRF token. LinkedIn's docs require checking this on the way back."""
    return secrets.token_urlsafe(16)


def authorize_url(client_id, redirect_uri, scopes=None, state=None):
    scopes = scopes or DEFAULT_SCOPES
    state = state or new_state()
    params = [
        ("response_type", "code"),
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("state", state),
        ("scope", " ".join(scopes)),
    ]
    # quote_via=quote gives %20 for spaces. urlencode's default would emit '+',
    # and LinkedIn's own samples use %20, so match the documented form exactly
    # rather than rely on the server treating them alike.
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return AUTH_URL + "?" + query, state


def exchange_code(code, client_id, client_secret, redirect_uri):
    """Swap the one time code for an access token.

    redirect_uri must match the authorization request exactly; LinkedIn returns
    invalid_redirect_uri otherwise. The code expires 30 minutes after issue.
    """
    resp = lihttp.form_post(TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    })
    payload = resp.json()
    if not resp.ok or not payload or not payload.get("access_token"):
        raise RuntimeError("token exchange failed (HTTP %s): %s"
                           % (resp.status, (resp.body or "")[:400]))
    return payload


def parse_redirect(url_or_code, expected_state=None):
    """Accept a bare code or the whole pasted redirect URL; return the code.

    Alex will paste whatever the browser gave him. Handle both, surface
    LinkedIn's own error text, and check state when it is available, because
    the docs call an unvalidated state a CSRF hole.
    """
    text = (url_or_code or "").strip()
    if not text:
        raise ValueError("nothing pasted")

    # Decide URL vs bare code by shape, not by whether "code=" happens to appear.
    # Checking for the substring first meant a redirect URL that carried no code
    # was returned whole, as though the URL itself were the authorization code.
    looks_like_url = text.lower().startswith(("http://", "https://")) or "?" in text
    if not looks_like_url:
        return text  # a bare authorization code

    parsed = urllib.parse.urlparse(text)
    qs = urllib.parse.parse_qs(parsed.query or "")
    if "error" in qs:
        raise RuntimeError("LinkedIn returned an error: %s (%s)" % (
            qs.get("error", [""])[0], qs.get("error_description", [""])[0]))

    codes = qs.get("code")
    if not codes:
        raise ValueError("no ?code= found in that URL")

    if expected_state:
        got = (qs.get("state") or [None])[0]
        if got != expected_state:
            raise RuntimeError(
                "state mismatch: expected %r, got %r. Do not use this code; "
                "start the flow again." % (expected_state, got))
    return codes[0]


def fetch_person_urn(access_token):
    """Return (urn, payload).

    The id comes from the OpenID Connect userinfo endpoint's `sub` claim, which
    LinkedIn documents as a bare identifier (sample: "sub": "782bbtaQ"), so the
    URN is assembled here. This endpoint is unversioned and takes no
    Linkedin-Version header.

    One honest caveat: LinkedIn documents that `sub` is the member id, and it
    documents author values of the form urn:li:person:{id}, but no page states
    the concatenation rule outright. Joining them is an inference from two
    documented facts rather than a quoted instruction, so if posting fails with
    INVALID_URN_ID this line is the first place to look.
    """
    resp = lihttp.get(USERINFO_URL, headers={"Authorization": "Bearer %s" % access_token})
    payload = resp.json() or {}
    if not resp.ok:
        raise RuntimeError("userinfo failed (HTTP %s): %s" % (resp.status, (resp.body or "")[:300]))
    sub = payload.get("sub")
    if not sub:
        raise RuntimeError("userinfo returned no 'sub' claim: %s" % (resp.body or "")[:300])
    sub = str(sub)
    urn = sub if sub.startswith("urn:li:") else "urn:li:person:%s" % sub
    return urn, payload


def open_browser(url):
    try:
        return webbrowser.open(url)
    except Exception:
        return False
