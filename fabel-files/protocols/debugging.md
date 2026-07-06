# Debugging — fault isolation as procedure

Read when: anything behaves unexpectedly — a failing test, a wrong output, an error, a surprise during the prediction check.

Debugging is where weaker models burn the most time, because it punishes exactly their weaknesses: guessing, changing many things at once, and re-trying the same idea in new clothes. The countermeasure is to make every move an experiment with a written prediction.

---

## 1. Open a ledger

Before the first fix attempt, start `templates/debug-log.md` (or an inline version of it) with three sections:

- **Observed** — what actually happened, verbatim: the exact error text, the actual value, the log line. Paste, don't paraphrase. Paraphrased errors lose the detail that matters.
- **Expected** — what should have happened, per spec, docs, or previous behavior. If you can't state this precisely, that's your first task, not the fix.
- **Hypotheses** — numbered guesses, each with the cheapest experiment that would discriminate it from the others, and (as you go) the result.

The ledger is not bureaucracy. It is what prevents attempt 4 from being attempt 2 with different variable names.

## 2. Reproduce first

No reproduction → no conclusions. Find the smallest, fastest command that shows the failure; this becomes your red/green check for the eventual fix. If reproduction is infeasible (prod-only, timing, missing access), write down that it's infeasible and why, and downgrade all conclusions to hypotheses.

## 3. Read the error literally

- Read the WHOLE error, from the FIRST error in the output. Later errors are usually cascade from the first.
- Act on what it says, not what errors like it usually mean. "Connection refused" ≠ "connection timed out" ≠ "reset" — each implicates a different layer.
- If the message names a file and line, go read that file and line before anything else.

## 4. Bisect the pipeline

Locate before you explain. Pick the midpoint of the data's journey (input → parse → transform → call → response → handle → output), log the ACTUAL value there, and determine which half holds the fault. Repeat. Four good bisections corner almost anything.

Instrument first, guess never: when you don't know a value, print it. Reasoning about what a value "must be" is how bugs survive. Remove the instrumentation after.

## 5. One variable per experiment

Every experiment changes exactly one thing and starts with a one-line prediction. After: match / surprise / partial (per the prediction discipline). Two changes at once means an uninterpretable result even when it "works."

Prefer the cheapest experiment that discriminates your top two hypotheses — not the experiment that would confirm your favorite.

## 6. Tripwires (these override momentum)

- **Same error after your fix** → your model of the system is wrong. The next action is data-gathering, not another patch.
- **3 failed fix attempts** → stop. List every assumption in play ("the config I edited is the one being loaded," "this function is actually called," "the deploy picked up my change," "the test runs the code I think it runs"). Test the assumption you are MOST confident in — the bug statistically lives in the one you never checked.
- **A "small" bug needs edits in many places** → re-diagnose; the diagnosis is wrong, not the codebase.
- **You catch yourself thinking "just one more try"** → that is the tripwire feeling. Ledger, assumptions, step back.

Reverting to last-known-good is always on the table and is often the fastest path: get back to green, then re-approach with the diff in hand.

## 7. Blame order

Exhaust inner rings before outer ones:

1. **My new code** — the diff is the prime suspect, always.
2. **My usage of the library/API** — wrong endpoint, method, headers, auth, body shape, encoding; response parsed as the wrong shape; errors silently swallowed. Log the raw request and raw response when in doubt.
3. **Config / environment / cache / artifact** — run the checklist:
   - [ ] Env vars: set, correctly named, actually visible to the process at runtime?
   - [ ] Config: is the file being loaded the one you edited? (Print its path from inside the process.)
   - [ ] Cache: stale build, stale layer, stale response ruled out? (Hard-rebuild once and compare.)
   - [ ] Artifact: does the running/deployed code contain your change? (Fingerprint it.)
   - [ ] Versions: do runtime dependency versions match what you tested against?
4. **The external service** — LAST, and only when: your code path is traced end to end, inputs/outputs at the boundary are validated, the issue reproduces (or non-repro is documented), AND external evidence agrees — a status page, a changelog, an error class documented as service-side. Absent all four, keep looking inward.

## 8. Close it out

A fix is done when: the original red check is green, you can state the root cause in one sentence, and the sentence explains the original symptom (not just "the change made the error stop"). If the error stopped and you don't know why, the bug is still there — mark it as such.

Hygiene: while debugging, touch nothing unrelated — no refactors, no cleanups, no reformatting. Note tangents in the task file and move on.
