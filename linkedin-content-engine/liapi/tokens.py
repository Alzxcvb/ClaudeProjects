"""Where the access token lives, and how close it is to dying.

LinkedIn issues 60-day access tokens. True refresh tokens go only to approved
Marketing Developer Platform partners, which this app is not, so the renewal
path is re-running the authorization flow before expiry. That makes the expiry
date operationally important rather than a detail: if it lapses unnoticed while
Alex is travelling, posting stops silently. Everything here exists to make that
date loud.
"""
import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Overridable so tests and dry runs never touch the real credential file.
TOKEN_PATH = Path(os.environ.get("LI_TOKEN_PATH") or (ROOT / ".li-token.json"))

# Warn from here on. Two weeks is enough to re-auth from anywhere with a laptop.
WARN_DAYS = 14


def _now():
    return datetime.now()


OWNER_ONLY = stat.S_IRUSR | stat.S_IWUSR


def save(data, path=None):
    """Write the token file so it is owner-only before the secret lands in it.

    O_CREAT does not change the mode of a file that already exists, so simply
    opening with 0600 and chmod-ing afterwards would write a fresh token into
    an existing world-readable file and only then tighten it. Tighten first
    instead, then write.
    """
    p = Path(path) if path else TOKEN_PATH
    if p.exists():
        os.chmod(str(p), OWNER_ONLY)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, OWNER_ONLY)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.chmod(str(p), OWNER_ONLY)
    return p


def permission_warning(path):
    """Warn when a credential file is readable by anyone but its owner.

    `.li-app.json` holds the client secret and is created by hand in an editor,
    so it lands 0644 by default. It is the longer lived credential of the two.
    """
    p = Path(path)
    if not p.exists():
        return None
    mode = stat.S_IMODE(p.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return ("%s is mode %o, readable beyond you. Run: chmod 600 %s"
                % (p.name, mode, p))
    return None


def load(path=None):
    p = Path(path) if path else TOKEN_PATH
    if not p.exists():
        return None
    return json.loads(p.read_text())


def record_grant(payload, scope_requested, client_id, path=None):
    """Turn a raw token response into the stored record.

    `expires_in` is seconds from now, which is useless to a human three weeks
    later, so the absolute expiry is computed once, here, and stored.
    """
    issued = _now()
    expires_in = int(payload.get("expires_in") or 0)
    record = {
        "access_token": payload.get("access_token"),
        "token_type": payload.get("token_type", "Bearer"),
        "expires_in": expires_in,
        "issued_at": issued.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": (issued + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S"),
        "scope_granted": payload.get("scope"),
        "scope_requested": scope_requested,
        "client_id": client_id,
        # Present only for approved partners. Recorded if LinkedIn ever sends one.
        "refresh_token": payload.get("refresh_token"),
        "refresh_token_expires_in": payload.get("refresh_token_expires_in"),
        # Filled in by the first successful identity call, then reused.
        "person_urn": None,
    }
    if path is not False:
        save(record, path)
    return record


def days_left(record):
    """Whole days until expiry. Negative once expired. None if unknown."""
    if not record or not record.get("expires_at"):
        return None
    expires = datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S")
    return int((expires - _now()).total_seconds() // 86400)


def is_expired(record):
    left = days_left(record)
    return left is not None and left < 0


def needs_attention(record):
    left = days_left(record)
    return left is None or left <= WARN_DAYS


def summary(record):
    """One human-readable line about token health."""
    if not record:
        return "no token stored - run: ./li auth"
    left = days_left(record)
    if left is None:
        return "token stored, expiry unknown - re-run: ./li auth"
    if left < 0:
        return "TOKEN EXPIRED %s days ago (%s) - re-run: ./li auth" % (abs(left), record["expires_at"])
    flag = "  <-- RENEW NOW" if left <= WARN_DAYS else ""
    return "token valid %s more days (expires %s)%s" % (left, record["expires_at"], flag)


def set_person_urn(urn, path=None):
    record = load(path)
    if not record:
        raise RuntimeError("no token stored")
    record["person_urn"] = urn
    save(record, path)
    return record
