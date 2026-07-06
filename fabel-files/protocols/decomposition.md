# Decomposition — breaking work down so it can't silently fail

Read when: a task has 3+ steps, feels fuzzy, or you notice you can't predict what "step 4" will be.

The purpose of decomposition is not organization. It is to convert one large, unverifiable gamble into a chain of small, individually checkable bets — so that failure shows up at step 2 out of 8, not after everything is "done."

---

## 1. Write "done means" first

1–3 criteria, each one demonstrable: a command that passes, a behavior you can trigger and observe, a file with specific content. Test each criterion by asking: *could I show this to someone in under a minute?* If a criterion is "the code is cleaner" or "it handles errors better," it is not a criterion yet — convert it ("`lint` passes with zero new warnings"; "calling X with a bad token returns 401, not 500").

## 2. Triage unknowns

List everything you don't currently know that the task touches. Classify:

- **(A) Self-serve** — answerable by reading code, running a command, or checking docs. Resolve ALL of these before planning; they're cheap and they change the plan.
- **(B) User-only, plan-changing** — genuinely a preference or fact only the user holds, AND different answers produce different work. Batch and ask once.
- **(C) Deferrable** — doesn't affect the next two steps. Write down, move on.

The common failure is misfiling: asking the user (A)s (annoying, slow) or guessing on (B)s (wrong deliverable). When in doubt, spend 5 minutes trying to make it an (A) first.

## 3. Order by risk, not by build order

For each candidate step ask: **if this step fails, does it invalidate the others?** Those steps go first, in the smallest form that answers the question — a spike.

Spike rules:
- Timebox it. Its only job is to answer "is this approach viable?"
- Throwaway by default: write it expecting to delete it. If it happens to be keepable, fine, but don't gold-plate a probe.
- A spike ends with a written one-line answer, not a feeling.

## 4. Walking skeleton

For anything with multiple components, build the thinnest possible end-to-end path FIRST — hardcoded values, one happy path, ugly — and verify it works across every boundary. Then thicken each part. Reason: cross-boundary problems (auth, serialization, versions, permissions, CORS, env) are the expensive surprises, and they only appear at integration. Meeting them on day one with 50 lines beats meeting them on day three with 500.

## 5. Size and shape of steps

- Verb-object names: "Add retry to the fetch wrapper," not "Networking improvements."
- Each step ends with its own check, written down BEFORE the step is executed. If you can't name the check, the step is really two steps or it's not understood yet.
- A step that can't fail informatively (nothing observable at its end) should be merged into one that can.

## 6. Decisions inside the plan

When a fork appears (library A vs B, schema shape, API design):
- Enumerate at most 3 options. More than 3 means you haven't understood the constraints; go find the constraint that kills the extras.
- One line of tradeoff each. Pick. One line of why.
- Prefer the reversible option when it's close — reversible decisions deserve minutes, irreversible ones deserve the analysis.
- Record consequential ones in `templates/decision-log.md`. Then STOP revisiting; new evidence is the only reopening key.

## 7. The plan is a file

3+ steps → `tasks/todo.md` (or the template at `templates/task-plan.md`). Checkboxes. Update at every milestone. Write for a cold reader: a fresh model instance with zero session memory should be able to read the file and continue. That means: current state, next action, open questions, and the "Noticed" list of tangents you refused to chase.

---

## Worked example

Task: "Add CSV export to the reports page."

**Naive decomposition (build-order, integration-last — don't do this):**
1. Write a CSV serialization utility ✗ (easiest part first)
2. Add an export service with all options ✗ (speculative generality)
3. Build the UI button and menu ✗
4. Wire it all together ✗ (all risk deferred to the last step)

**Risk-first decomposition:**
1. *Spike:* can the reports data source return the full dataset in one request, or is it paginated/truncated? (This invalidates everything if wrong.) → Check: log the row count vs. what the DB says.
2. *Skeleton:* one hardcoded report → serialized to CSV with the stdlib → downloaded via a new endpoint → opens in a spreadsheet. Ugly but end-to-end. → Check: file opens, columns correct.
3. Real data wiring: parameterize report ID, respect existing auth on the endpoint. → Check: wrong-user request rejected; right-user gets their data.
4. Edge cases: empty report, commas/quotes/newlines in fields, non-ASCII. → Check: each produces a valid file (test with actual fixtures).
5. UI affordance matching existing page idiom. → Check: click in the real app, file lands.
6. Self-review pass + report.

Note what moved: the scary unknown (step 1) is first, the integration (step 2) is second, and the polish is last — the exact reverse of instinct.
