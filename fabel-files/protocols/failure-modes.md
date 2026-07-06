# Failure Modes — the anti-pattern catalog

Read this once at session start. These are the predictable ways capable-but-smaller models fail, each with a **Signature** (how to catch yourself doing it) and a **Countermeasure** (the mechanical fix). Every rule in CLAUDE-FABEL.md exists to counter one of these; this file is the map between them.

The meta-rule: you will not notice these failures by introspection, because each one feels like competence from the inside. You notice them by their signatures — observable behaviors you can check for.

---

## 1. Premature action
**Signature:** You are editing a file or running a mutating command within the first minute, before writing "done means."
**Countermeasure:** ORIENT gate (§2). No mutation before a one-sentence restatement and done-criteria exist. Reading, grepping, and listing are always allowed.

## 2. Hallucinated APIs
**Signature:** You are calling a function, method, flag, or config key you haven't seen defined in this session. It "feels standard."
**Countermeasure:** Grep for the definition or run `--help` before first use. Not found = does not exist. This is the single most common weak-model failure; the confidence feeling is not evidence.

## 3. Editing unread code
**Signature:** An Edit targets a file you never opened, based on what the file "probably contains."
**Countermeasure:** Hard gate — read the region first, every time. Your memory of a file from 30 turns ago counts as unread.

## 4. Shotgun debugging
**Signature:** One "fix" changes 3 things at once; or you re-run the failing command after each micro-edit hoping something sticks.
**Countermeasure:** Debug ledger, one variable per experiment, prediction line before each run. If you can't say which change fixed it, you haven't fixed it — you've hidden it.

## 5. Premature victory
**Signature:** The words "should work," "this fixes it," or "done" appear before the behavior was actually exercised.
**Countermeasure:** Verification hierarchy (§5). Quote observed output in the report. For bug fixes, red-before-green is mandatory.

## 6. Trusting the premise
**Signature:** The user said "X is broken because of Y" and your first action targets Y without confirming X or Y.
**Countermeasure:** Verify the premise in ORIENT. Reproduce the symptom before accepting the diagnosis. Users are a source of symptoms, not root causes.

## 7. Losing the thread
**Signature:** Mid-task, you re-derive something you already established, or your recent actions don't map to any step in a plan.
**Countermeasure:** Task file with checkboxes, updated at every milestone. When confused, re-read the task file BEFORE re-reading the code.

## 8. Scope creep / drive-by refactoring
**Signature:** The diff contains changes with no path back to "done means" — renames, reformats, cleanups of adjacent code.
**Countermeasure:** "Noticed" list in the task file. Every changed line must trace to the task; the self-review pass checks this explicitly.

## 9. Cosmetic retries
**Signature:** Attempt 4 is attempt 2 with different variable names. You are rephrasing an approach, not changing it.
**Countermeasure:** The 3-attempt tripwire. At 3 failures, the next move is never another fix — it's writing down assumptions and testing the most confident one.

## 10. Speculative generality
**Signature:** You are building an abstraction, option, or config flag for a future need the task never mentioned.
**Countermeasure:** Rule of 3 — no abstraction until the pattern exists 3 times. Deletion pass in self-review.

## 11. Misread errors
**Signature:** Your fix targets what the error "usually means" rather than what this error text says; or you only read the last line of a long traceback.
**Countermeasure:** Read the full error, quote it verbatim in the ledger, start from the FIRST error in the output. Later errors are usually cascade.

## 12. Blaming the outside world
**Signature:** "Must be the API / the network / a platform bug" appears before your own request, parsing, and error handling were traced.
**Countermeasure:** Blame order (own code → own usage → config/env/cache → external), and external blame requires external evidence: a status page, a changelog, an error class documented as service-side.

## 13. Blind destruction
**Signature:** Deleting or overwriting a file, branch, or record based only on how it was described, without looking at it.
**Countermeasure:** Look at the target first. Content contradicts description → stop and surface, don't proceed.

## 14. Confidence inflation
**Signature:** A report states as fact something you inferred but never ran; tiers drift upward between the work and the summary.
**Countermeasure:** Label every claim Verified / Expected / Guess at the moment you learn it, and copy the labels into the report unchanged.

## 15. Question extremes
**Signature:** Either you ask the user things you could answer with 2 minutes of grepping, or you silently guess on a genuine fork that changes the deliverable.
**Countermeasure:** The (A)/(B)/(C) unknown triage. (A) always self-serve; (B) always ask, batched; never invert them.

## 16. Checklist blindness
**Signature:** You are following a procedure step whose purpose no longer applies to the current situation, because the list said so.
**Countermeasure:** Every step of every protocol has a purpose; if you can state why a step is moot HERE in one sentence, skip it and note the skip. If you can't state it, do the step. (This is the only sanctioned way around any gate in the manual.)
