# CLAUDE.md

Behavioral rules for Claude Code when working in this repository.

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
