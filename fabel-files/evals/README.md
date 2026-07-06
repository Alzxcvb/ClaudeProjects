# Evals — fixed, repeatable benchmark tasks

Five self-contained tasks with planted, known ground truth, for measuring whether the manual (and coaching) actually moves a weaker model. Every task runs offline with stock Python 3 — no network, no accounts, no external services — so runs are repeatable anywhere.

## The tasks

| Task | Domain exercised | Ground truth |
|---|---|---|
| `task-01-planted-bug` | Debugging, red-before-green | 2 planted bugs, failing tests included |
| `task-02-feature-spec` | Build-to-spec, edge cases, scope | Explicit done-means checklist |
| `task-03-data-cleaning` | Data pipeline, rejects, reconciliation | Expected output files to diff against |
| `task-04-config-debug` | Blame order, config/env checklist | 2 planted config faults, staged failure |
| `task-05-hostile-review` | Security/code review | Answer key of 6 planted defects |

Each task folder contains:
- `TASK.md` — the prompt the model gets. **This is ALL it gets.**
- `RUBRIC.md` — scoring key and answer key. **Never show this to the model under test.**
- `fixtures/` — the code/data the task operates on.

## Run protocol (keep runs comparable)

1. **Copy fixtures out** — never run in this folder (the rubric sits next to it, and runs must not contaminate the originals):
   ```bash
   RUN=~/fabel-runs/$(date +%Y%m%d-%H%M)-<model>-<task>
   mkdir -p "$RUN" && cp -r fabel-files/evals/task-01-planted-bug/fixtures/* "$RUN/"
   ```
2. **Fixed wrapper prompt** — give the model this, verbatim, every run:
   > Work in the current directory. Your task is described in TASK.md. Complete it, then report what you did and how you verified it.
   (Copy the task's `TASK.md` into `$RUN/` alongside the fixtures.)
3. **Condition under test** — the only thing that varies:
   - Control: bare model.
   - Manual: `CLAUDE-FABEL.md` (+ the matching domain file) loaded via `--append-system-prompt` or a CLAUDE.md in `$RUN`.
   - Coached: manual + the specialist's accumulated `learned-rules.md`.
4. Same model ID and settings across compared runs; fresh session each run; save the full transcript and `git diff`/final files.
5. Score with `RUBRIC.md` (below), and optionally have the coach (`../agents/coach.md`) grade process from the transcript.

## Scoring

Each rubric yields two numbers:

- **Outcome /10** — did the work succeed? Task-specific checklist in each `RUBRIC.md`. Mechanical: a checker command or an answer key, minimal judgment.
- **Process /10** — did it work the way the manual demands? Generic across tasks, graded from the transcript:

| Points | Criterion |
|---|---|
| 2 | "Done means" stated before any mutation |
| 2 | Read/reproduced before editing (for bugs: watched it fail first) |
| 2 | Verification run and output QUOTED, not asserted |
| 2 | Scope held — no changes untraceable to the task |
| 2 | Report honest — claims match transcript evidence; failures/skips stated plainly |

Log every run as a row in `results-log.md` (template provided). Deltas between conditions on the same task+model are the experiment's actual output.

## Integrity rules

- The model under test never sees `RUBRIC.md`, other tasks, or this README.
- Don't reuse a `$RUN` directory; state leaks.
- If a model has plausibly memorized a fixture (they're original here, but models train on everything eventually), perturb surface details (names, values) without touching the planted ground truth, and note the perturbation in the log.
- Fixtures verified working (bugs fail as designed, clean code runs) at build time — re-verify with the commands in each `RUBRIC.md` if you ever edit a fixture.
