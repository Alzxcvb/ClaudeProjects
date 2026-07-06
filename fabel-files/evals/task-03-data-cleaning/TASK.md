# Task: Clean the orders file

`orders_raw.csv` is a raw export of orders (UTF-8, header row: `order_id,customer,date,quantity,amount`). Write a Python script `clean_orders.py` that reads it and produces two files:

## `orders_clean.csv`

Header: `order_id,customer,date,quantity,amount_usd`. One row per ACCEPTED order, in original file order, with:

- All fields trimmed of leading/trailing whitespace.
- `date` normalized to ISO `YYYY-MM-DD`. Input dates appear in three formats: `2026-03-05` (ISO), `03/07/2026` (US month/day/year), and `Mar 9, 2026` (textual).
- `amount_usd`: the `amount` with `$` and thousands commas removed, formatted with exactly two decimal places (e.g., `1205.00`).
- Non-ASCII characters in names preserved as-is.

## `rejects.csv`

Header: `order_id,customer,date,quantity,amount,reason` — the original (raw) field values plus a reason. A row is rejected by the FIRST matching rule, checked in this order:

1. `missing field` — any of the five fields empty after trimming.
2. `invalid quantity` — quantity is not a positive integer (rejects 0, negatives, non-numbers).
3. `duplicate order_id` — an earlier row (accepted or rejected) already used this `order_id`; keep the first, reject later ones.

Completely blank lines in the input are skipped silently (they are not rejects).

## Done means

- Both output files produced with the exact headers above.
- Every input data row is accounted for: accepted + rejected = input rows (excluding blank lines). Print this reconciliation (counts of input/accepted/rejected) when the script runs.
- Running the script twice produces identical outputs.
