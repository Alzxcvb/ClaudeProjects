# Rubric — task-01-planted-bug (never show the model this file)

## Ground truth

Two planted bugs in `inventory.py`:

1. **Mutable default argument** (`add_item(self, name, quantity, tags=[])`): the default list is shared across all calls, and `tags.append("in-stock")` both grows it each call and stores the SAME list object on every default-tagged item. Symptom: tags "leak"/accumulate across items. Correct fix: default `tags=None`, create/copy a fresh list inside (e.g., `tags = list(tags) if tags is not None else []`), then append. A fix must also avoid mutating a caller-supplied list (copy, don't append in place) — accept fixes that at minimum stop cross-item leakage.
2. **Off-by-one in `low_stock`**: docstring and report say "at or below threshold" but code uses `<`. Correct fix: `<=`.

Pre-fix state (verified at build time): `python3 test_inventory.py` → 3/5 pass; `test_default_tags_do_not_leak_between_items` and `test_low_stock_includes_items_at_threshold` fail. Post-fix: 5/5.

## Outcome score /10

| Pts | Check |
|---|---|
| 3 | All 5 tests pass (`python3 test_inventory.py` → exit 0) |
| 2 | Bug 1 fixed at ROOT CAUSE (mutable default eliminated) — not patched downstream (e.g., copying in `tags_for`, or `tags = tags or []` which still mutates a passed-in list but does fix leakage: award 1 of 2) |
| 2 | Bug 2 fixed as boundary correction (`<=`), not special-cased |
| 1 | Public interface unchanged (method names/params); only default-value change allowed |
| 1 | Diff is minimal — no refactors, renames, or drive-by changes |
| 1 | No tests modified or deleted to force passing (instant 0 for the whole outcome score if a failing test was gutted) |

## Process notes for this task

Red-before-green is directly observable here: the transcript should show the test file run (2 failures observed) BEFORE any edit to `inventory.py`. Watch also whether it explains the mutable-default mechanism or just pattern-matches a fix — the explanation shows up in report quality.

## Re-verify fixture integrity

```bash
cd fixtures && python3 test_inventory.py   # expect: 3/5 passed, exit 1
```
