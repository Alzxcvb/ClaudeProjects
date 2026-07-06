# Self-Review — the hostile pass before "done"

Read when: the work verifies and you are about to report completion.

Verification proved the happy path works. This pass hunts for what verification didn't cover. Do it as a SEPARATE pass over the full diff — not while writing, not from memory. Actually re-read every changed hunk (`git diff`, or re-open the files). Read as a reviewer whose job is to find a reason to reject.

If anything below turns something up: fix it, re-verify, and only then report. Findings here are cheap; the same findings in the user's hands are expensive.

---

## Pass 1 — Correctness edges

For each changed hunk, walk the standard edge set against the inputs it handles:

- **Empty / zero / null / missing** — empty string, empty list, 0, null, absent key, absent file.
- **One vs. many** — exactly one element (off-by-one heaven), and the maximum plausible size.
- **Boundaries** — first and last iteration, inclusive/exclusive ends, midnight/EOM dates, page boundaries.
- **Ugly values** — unicode, emoji, quotes, commas and newlines in data, very long strings, negative numbers, NaN.
- **Concurrency / reentry** — what happens if this runs twice, or twice at once? Is it idempotent where it needs to be?

You don't need a test for every cell of this matrix — you need to have ASKED each question and either shown it's handled, shown it's impossible here, or added the handling.

## Pass 2 — Error paths

- Every new call that can fail: what happens when it does? Swallowed exceptions and empty catch blocks are findings.
- Do error messages carry enough context to debug from a log line alone?
- Resources opened (files, connections, subprocesses, locks, temp files): released on ALL paths, including the error paths?
- Partial failure: if step 2 of 3 fails, what state is left behind? Is it re-runnable?

## Pass 3 — Trust boundaries

For any input that crosses a boundary (user input, network, file contents, env vars, subprocess output):

- Validated / sanitized before use?
- Can it reach a shell, a query, a path, an eval, HTML? (Injection in each flavor.)
- Secrets: nothing sensitive logged, committed, or echoed into error messages?
- New surface area: does this change expose anything (endpoint, file, permission) that wasn't exposed before? Intentionally?

## Pass 4 — Diff honesty

- **Trace every changed line to the task.** A line you can't justify from "done means" gets reverted — that's the scope-creep filter running in reverse.
- Leftover debug code: prints, commented-out blocks, temporary logs, TODO-with-no-owner, hardcoded test values.
- Names tell the truth? (A function named `validate` that also saves is a finding.)
- Comments only where the code can't speak; none of them narrating the diff to a reviewer.
- Style matches the surrounding file — idiom, naming, formatting — not your habits.

## Pass 5 — Deletion

The pass models most often skip. Ask of the finished work:

- What can be REMOVED with the checks still passing? Dead branches, unused params, imports, flags nobody set, an abstraction with one caller.
- Could a smaller diff have done this? If a hunk exists only to support another hunk that could be simpler, both go.
- Any speculative generality — options, hooks, or layers for futures nobody asked for? Delete; the future can pay for its own code.

## The gate

Final question, answered honestly: **"Would a staff engineer approve this diff as-is?"**

Hesitation is an answer. Whatever caused the hesitation is the finding — go fix it. Then report, with the self-review's notable findings ("found and fixed unreleased file handle on the error path") included, because they're evidence the pass actually ran.
