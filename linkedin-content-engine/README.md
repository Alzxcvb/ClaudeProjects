# linkedin-content-engine

Content CRM + generator + predictor for Alex's posts. Library, lineage and recycling in SQLite; you publish by hand, the tool tracks everything else. See [`PLAN.md`](PLAN.md) for the measurement methodology (read §0 before trusting any number).

**Status:** Phase 1.5 shipped (2026-07-10) — `./crm` CLI + `content.db` (ideas / variants / runs / metrics), posts.jsonl migrated, generator + predictor rewired to the database.

## The model

A post is not one thing:

- **idea** — the durable claim or angle. Ideas don't expire.
- **variant** — one written expression of an idea, for one platform. Variants have parents (`rewrite`).
- **run** — one publication of one variant at one moment. Metrics attach to runs, as snapshots at 24h / 72h / 7d.

The same variant can run twice, months apart (that's recycling). A rewrite beating its parent is a different question (that's lineage). The schema keeps them separate so both are queries instead of memory.

## Daily use

```bash
cd linkedin-content-engine

# morning: what should I post?
./crm due                          # past-cooldown ideas ranked by last efficiency, plus never-run backlog
./crm show V12 --body | pbcopy     # copy the text, paste into LinkedIn yourself
./crm ran V12 --followers 520      # record that it went out (grab follower count while you're there)

# evening: what needs numbers?
./crm status                       # which runs have a checkpoint due
./crm log -i 210 -r 5 -c 2         # metrics for the latest run; auto-labels 24h/72h/7d by elapsed time
```

Library work:

```bash
./crm import ~/Notes/swipe-file    # markdown dir -> ideas + variants (idempotent, safe to re-run)
./crm ideas --search email         # find things
./crm rewrite V12 --body-file f.md # child variant of V12, same idea
./crm compare V18                  # did the rewrite beat its parent? real answer or honest refusal
./crm due -p x                     # same queue for X/Instagram (manual entry, same interface)
```

## Honesty rules (enforced, not suggested)

- Raw impressions are never compared across time; runs store `followers_at_post` and compare on **efficiency** (score/impressions) and **normalised reach** (impressions/followers).
- Two runs are only comparable on the same **platform + day-of-week + time slot**; otherwise `compare` says INCONCLUSIVE and why.
- Gaps under **40%** (config) on the decision metric are NOISE, do not act.
- Comparisons prefer **same-checkpoint snapshots** (24h vs 24h); mixed-age snapshots get a warning because impressions accumulate.
- Scoring weights and cooldowns (LinkedIn 90d / X 30d / Instagram 120d) live in `config.json`, not in code.

## Generator + predictor

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python generate.py "topic" --notes "raw observations"   # 3 variants varying one axis
python predict.py --body-file draft.txt                  # BEAT/MATCH/UNDERPERFORM + forecast
```

Both read the database now (last runs as few-shot / labeled history). Prompts in `prompts/*.md` are unchanged and still the thing to edit for voice or calibration. `--dry-run` on either prints the assembled prompt without calling the API. The predictor keeps its `LOW-N` honesty tag until n ≥ 10.

## Files

| File | Purpose |
|---|---|
| `crm` + `contentcrm/` | The CLI and its modules (schema, migration, import, queue, compare) |
| `content.db` | SQLite source of truth (gitignored) |
| `config.json` | Score weights, cooldowns, slots, checkpoints, noise threshold |
| `PLAN.md` | Architecture + experimentation methodology (§0 is the point) |
| `prompts/*.md` | Tuned prompts for generator/predictor — edit these, not the scripts |
| `posts.jsonl` | Legacy post log, migrated 2026-07-10; kept as archive, nothing reads it |
| `log.py` | Legacy jsonl logger; prints a warning, use `./crm log` instead |
| `tests/` | `.venv/bin/python -m unittest discover` (39 tests, no extra deps) |
