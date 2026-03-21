# CLAUDE.md

Behavioral rules for Claude Code when working in this repository.

---

## 1. Planning

### Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity
- **Exception: bug fixes** — see Autonomous Bug Fixing below

### Subagent Strategy
- Use subagents liberally to keep the main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

---

## 2. Task Management

For non-trivial tasks:

1. **Plan First** — Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan** — Check in before starting implementation
3. **Track Progress** — Mark items complete as you go
4. **Explain Changes** — High-level summary at each step
5. **Document Results** — Add review section to `tasks/todo.md`
6. **Capture Lessons** — Update `tasks/lessons.md` after corrections

---

## 3. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review `tasks/lessons.md` at session start for relevant context

---

## 4. Verification Before Done

- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

---

## 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: implement the elegant solution instead
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

---

## 6. Autonomous Bug Fixing

When given a bug report:
- Fix it. Don't ask for hand-holding on navigating the codebase
- Point at logs, errors, failing tests — then resolve them
- Go fix failing CI tests without being told how
- Still apply the full Debugging & Fault Isolation Policy below — autonomy means self-directed investigation, not skipping rigor

---

## Debugging & Fault Isolation Policy

### Core Principle

Exhaust code-level explanations before attributing faults to third-party services, infrastructure, or external systems.

### Required Checks Before Blaming External Systems

1. **API usage** — Verify the request is constructed correctly: endpoint, method, headers, authentication, and body format.
2. **Response parsing** — Confirm the response is being read and decoded as expected. Log raw responses when uncertain.
3. **Error handling** — Check whether errors are being caught, surfaced, or silently swallowed.
4. **Integration logic** — Trace the full call path: caller → adapter → external system → response handler.

### Deployment Issue Checklist

When a bug may be deployment-related, explicitly verify each of the following before drawing conclusions:

- [ ] Environment variables — are they set, correctly named, and accessible at runtime?
- [ ] Configuration files — is the active config the expected one for this environment?
- [ ] Caching — has a stale build, layer, or cached response been ruled out?
- [ ] Build artifacts — does the deployed artifact reflect the current source?
- [ ] Version mismatches — do runtime dependencies match what was tested?

### Behavioral Standards

- Do not assume user testing errors without direct evidence (e.g., a screenshot, log line, or reproduction step that confirms it).
- Reproduce the issue before forming a conclusion. If reproduction is not possible, state that explicitly and note what was attempted.
- Distinguish clearly between these three categories in any analysis:

  | Category | Definition |
  |---|---|
  | **Observed behavior** | What actually happened, supported by logs or evidence |
  | **Expected behavior** | What should have happened, per spec or prior behavior |
  | **Hypothesis** | An untested explanation for the discrepancy |

### Escalation to Third-Party Blame

Attribute a fault to an external system or third-party service only when all of the following conditions are met:

1. The relevant code logic has been traced end-to-end.
2. Inputs to the external system and outputs from it have been validated.
3. The issue has been reproduced (or reproduction has been documented as infeasible with reasons).
4. External evidence supports the hypothesis — e.g., provider status page, API changelog, error codes that match known service-side failures.

If these conditions are not all met, continue investigating the local codebase.

---

## Code Hygiene During Debugging

- Do not refactor unrelated code while investigating or fixing a bug.
- Do not reformat, lint, or clean up files that are not directly involved in the issue.
- Do not stage, commit, push, or alter git history as part of a debugging session unless the fix itself is ready to ship.
- Limit all changes strictly to what is required to isolate or fix the issue at hand.
- If a refactor or cleanup opportunity is noticed, note it separately — do not act on it during the debugging session.
