#!/bin/bash
# install-reminders.sh — install LinkedIn posting + logging cron reminders on macOS.
# Idempotent. Run once. Re-run safely.
#
# What it installs:
#   1. Mon-Thu 9am local: macOS notification reminding you to post the next LinkedIn post.
#   2. Tue-Fri 6pm local: macOS notification reminding you to log yesterday's post metrics.
#
# How to remove later:
#   crontab -e   (delete the lines under '# linkedin-content-engine reminders')

set -euo pipefail

MARKER="# linkedin-content-engine reminders"
MARKETING_DIR="/Users/alexandercoffman/Dev/hi-im-alex/marketing"
ENGINE_DIR="/Users/alexandercoffman/Dev/linkedin-content-engine"

# Pre-flight: confirm osascript exists (built into macOS — should always pass)
if ! command -v osascript >/dev/null 2>&1; then
    echo "ERROR: osascript not found. Are you on macOS?" >&2
    exit 1
fi

# Idempotency check
if crontab -l 2>/dev/null | grep -q "$MARKER"; then
    echo "Reminders already installed."
    echo "To view: crontab -l"
    echo "To edit: crontab -e"
    exit 0
fi

# Build the new crontab (existing + new entries)
{
    crontab -l 2>/dev/null || true
    echo ""
    echo "$MARKER (installed $(date +%Y-%m-%d))"
    echo "# Mon-Thu 9am local: post-next-LinkedIn-post reminder"
    echo "0 9 * * 1-4 /usr/bin/osascript -e 'display notification \"Time to post. Folder: $MARKETING_DIR\" with title \"LinkedIn Post Time\" sound name \"Glass\"'"
    echo ""
    echo "# Tue-Fri 6pm local: log-yesterdays-post-metrics reminder"
    echo "0 18 * * 2-5 /usr/bin/osascript -e 'display notification \"Log yesterday post metrics. cd $ENGINE_DIR && python log.py post-NNN --impressions N --reactions N --comments N\" with title \"LinkedIn Log Time\" sound name \"Submarine\"'"
    echo ""
} | crontab -

echo "Installed two reminders:"
echo "  Mon-Thu 9:00 — Post the next LinkedIn post"
echo "  Tue-Fri 18:00 — Log yesterday post metrics"
echo ""
echo "Verify with: crontab -l"
echo ""
echo "Firing a test notification now (if you don't see it, grant notification permission to 'cron' or use System Settings > Notifications)..."
/usr/bin/osascript -e 'display notification "LinkedIn reminders installed. You will see this daily for posts + logging." with title "Reminders Live" sound name "Glass"'
echo "Done."
