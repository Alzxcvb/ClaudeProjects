#!/usr/bin/env bash
# Off-laptop backup for the Prospector outreach data.
# Copies the SQLite DB (+ a plain-CSV export of it), the outcome tracker,
# and the flat logs into iCloud Drive, so nothing lives only on this laptop.
# Keeps a rolling "latest" mirror plus dated snapshots.
set -euo pipefail

PROJ="/Users/alexandercoffman/ClaudeProjects/hi-im-alex-outreach"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
DEST="$ICLOUD/hi-im-alex-backups"
STAMP="$(date +%Y-%m-%d)"          # date only -> at most ONE snapshot per day
SNAP="$DEST/snapshots/$STAMP"
LATEST="$DEST/latest"

# fresh same-day folder (re-running today overwrites today's copy, never piles up)
rm -rf "$SNAP"
mkdir -p "$SNAP" "$LATEST"

# files to preserve
FILES=(
  "state/db.sqlite"
  "prospects/tracker.csv"
  "prospects/SENT_LOG.md"
  "prospects/raw_extract.jsonl"
  "prospects/linkedin_prospects.csv"
  "prospects/connection_notes.json"
  "prospects/batch2_notes.json"
  "prospects/batch3_ca_notes.json"
)

for f in "${FILES[@]}"; do
  if [ -f "$PROJ/$f" ]; then
    cp "$PROJ/$f" "$SNAP/$(basename "$f")"
    cp "$PROJ/$f" "$LATEST/$(basename "$f")"
  fi
done

# human-readable CSV export of the SQLite prospects table (so the data is
# readable even without any database tool)
if [ -f "$PROJ/state/db.sqlite" ]; then
  python3 - "$PROJ/state/db.sqlite" "$SNAP/reddit_prospects_export.csv" "$LATEST/reddit_prospects_export.csv" <<'PY'
import csv, sqlite3, sys
db, *outs = sys.argv[1:]
c = sqlite3.connect(db); c.row_factory = sqlite3.Row
rows = [dict(r) for r in c.execute("SELECT * FROM prospects")]
cols = rows[0].keys() if rows else []
for out in outs:
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cols)); w.writeheader()
        w.writerows(rows)
print(f"  exported {len(rows)} reddit prospects to CSV")
PY
fi

# keep only the last 7 daily snapshots; auto-delete anything older so it never piles up
find "$DEST/snapshots" -maxdepth 1 -type d -mtime +7 -exec rm -rf {} + 2>/dev/null || true

echo "✅ Backup done -> $SNAP"
echo "   rolling mirror -> $LATEST"
ls -1 "$LATEST"
