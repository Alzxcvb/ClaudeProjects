# Verification — proving work is done

Read when: you are about to claim anything works, is fixed, or is complete.

The core rule: **a claim's strength may never exceed its evidence.** "Should work" is a plan, not a result. The gap between "I wrote code that looks right" and "I watched the behavior happen" is where most false completions live.

---

## 1. Define the check before the change

For every step, write the verification BEFORE doing the work: the exact command, the expected output, the behavior to trigger. Two reasons: (a) if you can't define the check, you don't understand the step; (b) a check defined afterward gets unconsciously bent to fit whatever you built.

## 2. The hierarchy

Always verify at the highest feasible level:

1. **Real behavior, end to end** — run the app/CLI/pipeline the way a user would, observe the result.
2. **Integration test** — real components, automated.
3. **Unit test** — one component, automated.
4. **Typecheck / lint / build** — proves shape, not behavior.
5. **Re-reading the code** — the weakest. Never sufficient alone for a behavior change.

Level 4 passing while you claim a behavior works is the classic false completion. Compiles ≠ works.

## 3. Red before green (bug fixes)

Reproduce the failure and WATCH IT FAIL before you fix it. Then apply the fix and watch the same check pass.

- A test that never failed proves nothing about your fix — it may pass for unrelated reasons, or test the wrong thing.
- If you cannot reproduce, you may not conclude. Document what you attempted, say reproduction failed, and treat any fix as a **Guess**-tier change.

## 4. The oracle problem

Never verify output against your own implementation's opinion of itself (e.g., asserting the function returns what the function returns, or eyeballing output and deciding it "looks right" against your mental model — the same mental model that wrote the bug). Verify against something external: the spec, known-good sample data, the old system's output, a hand-computed example, a different tool.

## 5. Read output, don't just check exit codes

Exit code 0 with an error printed to stdout is common (test runners that "pass" 0 tests, scripts that swallow exceptions, `|| true` in the chain). Read the actual output: how many tests ran? Does the log contain the line you predicted? Are there warnings that are really failures?

Also: an empty result is a result that needs explaining. "Grep found nothing" means either it's clean or you grepped the wrong thing — decide which, with evidence.

## 6. Per-artifact checklists

**Code (behavior change):** trigger the changed behavior itself, not just the suite. Run the narrowest relevant tests, then the broader suite if it's cheap. Confirm you exercised YOUR path (add a temporary log line if unsure — then remove it).

**Config / infra:** boot the thing with the new config and probe it. Config errors are load-time or first-use-time; a file that "looks valid" verifies nothing.

**Deploys:** verify the deployed artifact is YOUR artifact — fingerprint it (a version string, a sentinel change, response shape) rather than trusting the deploy pipeline's green checkmark. Auto-deploy hooks lie; caches serve stale builds.

**Data work:** row counts in vs. out at every stage; spot-check ~5 real records end to end by hand; check the edges (nulls, duplicates, encoding) not just the middle. An aggregate that "seems plausible" is not a check.

**Docs / prose:** re-read against the source of truth line by line — every claim, number, path, and command in the doc gets checked against reality, not memory. Run every command you tell the reader to run.

**UI:** drive the actual flow (click it, don't just render it). Check the console for errors even when the screen looks right.

## 7. When you truly can't verify

Sometimes the environment makes real verification impossible (no credentials, no device, prod-only behavior). Then:
1. Say so explicitly — first sentence of the report, not a footnote.
2. List what you attempted.
3. Verify at the highest level you CAN, and label the overall claim **Expected**, never Verified.
4. Hand the user the exact command/steps to complete the verification themselves.
