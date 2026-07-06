# Domain: Data Pipelines / ETL

Applies when: ingesting, transforming, moving, or batch-processing data — ETL jobs, importers, exporters, scheduled processing. Load with `CLAUDE-FABEL.md`.

## 1. Failure modes

- **Non-idempotent runs.** A pipeline that double-inserts when run twice. Pipelines WILL be re-run — after crashes, for backfills, by accident.
- **Silent row loss.** Rows dropped by a bad join, a strict parse, or a swallowed exception, with no count telling anyone. The output "looks fine"; it's just missing 12% of the data.
- **Schema drift blindness.** Upstream adds/renames a column; the pipeline keeps running and produces subtly wrong output instead of failing.
- **In-memory everything.** Loading the full dataset into memory because the sample file was small. Production isn't the sample.
- **Timezone-naive timestamps.** Mixing naive and aware datetimes, or assuming local time; every downstream aggregate by day is then wrong at the edges.
- **Mutating the source.** "Cleaning" raw data in place, destroying the ability to reprocess when the cleaning logic turns out wrong.

## 2. Standards

- **Idempotent and re-runnable.** Running the pipeline twice on the same input yields the same final state (upserts, delete-then-write partitions, or dedupe keys — pick one deliberately).
- **Counts reconcile at every stage.** Log rows in, rows out, rows rejected per stage. In = out + rejected, or the run fails. Unexplained loss is a failed run, not a warning.
- **Raw data is immutable.** Land it, never edit it. All cleaning produces new artifacts, so reprocessing is always possible.
- **Fail loudly on surprise shape.** Validate expected columns/types at ingestion; an unexpected schema stops the run rather than coercing quietly.
- **Rejects are captured, not dropped.** Bad rows go to a rejects output with a reason, so data quality is observable.
- **Timestamps are UTC and timezone-aware end to end**; conversion to local time happens only at presentation.
- Long runs checkpoint and resume; a crash at hour 3 doesn't restart hour 0.

## 3. Defaults

- Batch before streaming. Plain files + SQL before frameworks. A cron job before an orchestrator. Adopt heavier machinery only when a concrete requirement (volume, latency, dependencies) forces it, with the reason written down.
- Process in chunks/streams by default; whole-file loads only with a stated size bound.
- Deterministic ordering where output order matters; explicit `ORDER BY`, never incidental order.
- One directory/table naming convention for raw → interim → final, matching the project's existing layout.

## 4. Verification

- **Run it twice.** Identical final output/state both times is the idempotency proof. This is the single most valuable pipeline test.
- **Reconcile counts** for the verification run and quote them: input rows, output rows, rejects per stage.
- **Spot-check 5 real records end to end by hand** — trace input values to output values and confirm each transform did what the spec says. Aggregates hide per-row wrongness.
- Check the edges of the data, not the middle: first/last rows, min/max dates, the null-heavy columns.
- Feed it an empty input and a malformed row; confirm the designed behavior (clean no-op; reject with reason) rather than a crash or silence.

## 5. Edge cases that always matter

- Duplicates: exact dupes and same-key-different-values dupes — which wins, and is it deliberate?
- Nulls vs. empty strings vs. missing columns — three different things; each transform decides explicitly.
- Encodings: UTF-8 with BOM, Latin-1 escapees, emoji in names. Dates: mixed formats, two-digit years, DST boundaries, month/day ambiguity (03/07 vs 07/03).
- Joins: keys missing on one side (how many rows did the join drop? count it), type-mismatched keys ("123" vs 123).
- Scale: the 10× file. Does memory/runtime degrade linearly or explode?

## 6. Stop signals

- "It mostly works" — with data, mostly means broken; the missing rows are someone's revenue.
- You're hand-fixing individual records in the output → the transform is wrong; fix it and re-run instead.
- The same cleaning logic is being written a second time for another consumer → it belongs once, at ingestion.
- Counts don't reconcile and you're tempted to proceed anyway → that discrepancy IS the bug you were hired to catch.
