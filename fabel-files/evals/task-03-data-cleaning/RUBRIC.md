# Rubric — task-03-data-cleaning (never show the model this file)

## Ground truth

Input: 11 data rows + 1 blank line. Expected: 6 accepted, 5 rejected. The `expected/` folder (which lives OUTSIDE `fixtures/` — never copy it into the run directory) holds the exact answer files.

Planted nasties the spec forces the model through: quoted fields containing commas (textual dates, `$1,205.00`), three date formats, unicode names (José, Müller), apostrophe (O'Neil), whitespace padding, an empty line, a missing amount, a missing customer, quantity 0 and negative, and a duplicate `order_id` appearing after the original.

Rejection-order subtlety: row `1002,Bob Smith,03/12/2026,...` is a duplicate; row `1008` (quantity 0) must be `invalid quantity` not anything else; blank line is neither accepted nor rejected (counts: 11 = 6 + 5).

## Outcome score /10

Compare semantically (parse both CSVs; quoting style may legitimately differ):

```bash
python3 - <<'EOF'
import csv
def rows(p): return list(csv.reader(open(p, encoding="utf-8")))
for name in ["orders_clean.csv", "rejects.csv"]:
    got, want = rows(name), rows(f"<path-to>/expected/{name}")
    print(name, "MATCH" if got == want else f"MISMATCH\n got={got}\n want={want}")
EOF
```

| Pts | Check |
|---|---|
| 4 | `orders_clean.csv` matches expected exactly (parsed rows, incl. order, headers, `1205.00` formatting, ISO dates, unicode intact) |
| 3 | `rejects.csv` matches expected exactly (raw values, correct reasons, correct precedence order) |
| 1 | Reconciliation printed and correct (input 11 / accepted 6 / rejected 5) |
| 1 | Second run produces identical files (idempotency; run it twice, diff) |
| 1 | Script uses the `csv` module (or equivalent proper parser) — hand-split on commas breaks the quoted fields and forfeits this point even if outputs luck out |

Partial credit within the 4/3: one point off per wrong/missing/misplaced row, floor 0.

## Process notes for this task

Watch for: profiling the input before writing code (did it LOOK at the file and notice the quoted commas and blank line, or discover them by crash?); spot-checking output rows against input by hand; the reconciliation being computed from actual counters rather than hardcoded.
