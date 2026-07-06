# Domain: Databases — schema, migrations, SQL

Applies when: designing schema, writing migrations, or writing/tuning queries. Load with `CLAUDE-FABEL.md`.

## 1. Failure modes

- **Fresh-DB-only migrations.** Testing a migration against an empty database. On the live table, the `CREATE TABLE IF NOT EXISTS` is a no-op, the new column's constraint never runs, existing rows violate the new NOT NULL, and prod crashes on boot. Always rehearse against a copy WITH data.
- **Index amnesia.** Adding foreign keys and query filters with no supporting index; fine at 1k rows, a fire at 10M.
- **N+1 queries.** A loop of per-row queries hiding behind an ORM. The page works in dev with 5 rows.
- **Float money.** Storing currency in floating point. It's wrong by a cent eventually, and eventually is an audit.
- **Nullable-everything schemas.** Every column nullable "to be safe," pushing every invariant into application code that forgets.
- **App-only invariants.** Uniqueness or referential rules enforced only in code — until the second writer (a script, a retry, a race) breaks them.

## 2. Standards

- Migrations are additive-first (**expand → migrate data → contract**): add the new column/table, backfill, switch readers, then remove the old — each step separately deployable and reversible. Destructive steps ship only after the code that needed the old shape is gone.
- New columns on live tables: `ALTER TABLE ... ADD COLUMN` with its index/constraint created AFTER (and concurrently where the engine supports it) — never bundled where existing-table no-ops will skip it.
- Every migration is rehearsed on a data-bearing copy, and its rollback path is written before it runs. "Irreversible" is allowed only as an explicit, stated decision.
- The database enforces what it can: NOT NULL, UNIQUE, FK, CHECK. Application checks are a convenience layer, not the source of truth.
- Money in integer minor units or DECIMAL; timestamps as UTC `timestamptz`; IDs per codebase convention, chosen deliberately.
- Multi-write invariants live inside transactions. Queries whose cost matters get an `EXPLAIN` before shipping.

## 3. Defaults

- Postgres unless the project already chose otherwise. Boring normalized schema first; denormalize only against a measured need.
- Naming: follow the existing schema's conventions exactly (singular/plural, casing, `_id` suffixes).
- Soft delete only with a stated reason (audit, undo) — it complicates every future query. Default is hard delete with FK behavior chosen (`RESTRICT`/`CASCADE`) deliberately.
- ORM for CRUD, SQL for anything interesting (reports, bulk ops, window functions). Don't fight the ORM into generating what you could just write.

## 4. Verification

- Migration: run against a copy with realistic data → verify schema AND data; run the rollback → verify restored. Then run it a SECOND time — is it safely re-runnable/guarded?
- Query changes: `EXPLAIN (ANALYZE)` on realistic volume; quote the plan's scan type and cost. A seq scan on a big table's hot path is a finding.
- Count queries fired per request for the changed path (ORM logging on) — catch the N+1 now.
- Constraint you added: insert a violating row on the copy and watch it be rejected.

## 5. Edge cases that always matter

- Existing rows that violate the new constraint (the backfill's real job).
- Concurrent writes during a long migration; lock duration on big-table ALTERs (some ALTERs rewrite the table — know which).
- NULL semantics: `NULL != NULL`; unique indexes and NULLs; `WHERE col != 'x'` silently excluding NULLs.
- Collation/case sensitivity in text comparisons and unique constraints ('Bob' vs 'bob').
- Retention: what deletes this data eventually, and does anything reference it?

## 6. Stop signals

- A "simple" feature needs a 4+ table join on the hot path → the model may be wrong for the access pattern.
- You're adding the third nullable column to patch around a shape mismatch → redesign the shape.
- The migration can't be expressed as expand → migrate → contract → the deploy risk is real; slow down and get review.
- You're about to run a destructive statement and the table's row count surprises you → stop (core manual: blind destruction).
