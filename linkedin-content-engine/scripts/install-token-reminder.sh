#!/bin/bash
# install-token-reminder.sh: warn before the LinkedIn access token expires.
# Idempotent. Run once. Re-run safely.
#
# Why this exists: LinkedIn access tokens last 60 days, and this app is not an
# approved Marketing Developer Platform partner, so there is no programmatic
# refresh. Renewing means running ./li auth again. LinkedIn skips the consent
# screen ONLY while you are still signed in to linkedin.com AND the current
# token has not yet expired. So renewing late costs an extra click, and
# forgetting entirely makes posting stop silently, which is the failure this
# guards against.
#
# What it installs:
#   Mondays 9am local: check the token. Silent unless it expires within 14
#   days, in which case a macOS notification fires.
#
# How to remove later:
#   crontab -e   (delete the lines under '# linkedin-content-engine token check')

set -euo pipefail

MARKER="# linkedin-content-engine token check"
ENGINE_DIR="/Users/alexandercoffman/Dev/linkedin-content-engine"

if ! command -v osascript >/dev/null 2>&1; then
    echo "ERROR: osascript not found. Are you on macOS?" >&2
    exit 1
fi

if [ ! -x "$ENGINE_DIR/li" ]; then
    echo "ERROR: $ENGINE_DIR/li not found or not executable." >&2
    exit 1
fi

# Read the existing crontab carefully.
#
# The usual idiom is `crontab -l 2>/dev/null || true`, and it is genuinely
# dangerous here. It cannot tell "you have no crontab yet" from "I was not
# allowed to read it", and in the second case it hands back an empty base and
# silently wipes every entry the user already had. That is a real scenario:
# reading the crontab from inside a restricted shell returns nothing while a
# populated crontab exists. So capture stderr, and accept an empty base only
# when crontab actually says there is no crontab.
set +e
EXISTING="$(crontab -l 2>/dev/null)"
STATUS=$?
ERRTEXT="$(crontab -l 2>&1 >/dev/null)"
set -e

if [ $STATUS -ne 0 ]; then
    case "$ERRTEXT" in
        *"no crontab for"*)
            EXISTING=""   # genuinely nothing installed yet
            ;;
        *)
            echo "ERROR: could not read the existing crontab, so refusing to write one." >&2
            echo "       crontab said: ${ERRTEXT:-(no message)}" >&2
            echo "       Writing now could remove entries you already have." >&2
            exit 1
            ;;
    esac
fi

# Re-running must converge on the current definition rather than refuse, or the
# installed cron line silently drifts away from what this script says. Strip any
# previously installed block of ours (the marker line plus the two lines under
# it) and write a fresh one. Only OUR block is touched; every other entry is
# copied through untouched.
ALREADY=no
if printf '%s\n' "$EXISTING" | grep -q "$MARKER"; then
    ALREADY=yes
    EXISTING="$(printf '%s\n' "$EXISTING" | awk -v marker="$MARKER" '
        index($0, marker) == 1 { skip = 3 }
        skip > 0 { skip--; next }
        { print }
    ')"
fi

{
    [ -n "$EXISTING" ] && printf '%s\n' "$EXISTING"
    echo ""
    echo "$MARKER (installed $(date +%Y-%m-%d))"
    echo "# Mondays 9am: quiet unless the LinkedIn token expires within 14 days"
    # Exit 1 means "renewal due". Any other nonzero exit is a broken script or a
    # missing venv, which is a different problem and gets a different message,
    # so a crash never masquerades as a token warning.
    echo "0 9 * * 1 cd $ENGINE_DIR && { ./li status --check >/dev/null 2>&1; s=\$?; [ \$s -eq 0 ] || { [ \$s -eq 1 ] && /usr/bin/osascript -e 'display notification \"LinkedIn token expires soon. Run ./li auth\" with title \"LinkedIn token\" sound name \"Glass\"' || /usr/bin/osascript -e 'display notification \"LinkedIn token check failed to run\" with title \"LinkedIn token\" sound name \"Basso\"'; }; }"
} | crontab -

if [ "$ALREADY" = yes ]; then
    echo "Updated the existing token check."
else
    echo "Installed."
fi
echo "Weekly token check every Monday at 9am."
echo "It stays silent until the token is within 14 days of expiry."
echo "To view: crontab -l"
