# Domain: Testing Strategy

Applies when: writing tests, deciding what to test, fixing flaky tests, or judging whether a test suite means anything. Load with `CLAUDE-FABEL.md`.

The purpose of a test is to FAIL — informatively, when the behavior it guards breaks. A test that cannot fail, fails for the wrong reasons, or fails uninformatively is negative-value: it costs maintenance and buys false confidence.

## 1. Failure modes

- **Testing the implementation, not the behavior.** Asserting that a method was called with certain arguments instead of asserting the observable outcome. Refactors break these tests while real bugs sail through.
- **Mock everything, prove nothing.** So many layers mocked that the test verifies the mocks agree with each other. The classic tell: the bug was real, the suite was green.
- **The oracle loop.** Computing the expected value using the same logic under test (or copying the actual output into the assertion). The test now asserts the code does what the code does.
- **Coverage worship.** Chasing a percentage by writing assertion-free or trivial tests. Coverage measures execution, not verification.
- **Flake tolerance.** Retrying flaky tests until green. A flaky test is a real bug — in the test or the code (a race, an order dependency, a clock) — being actively ignored.
- **Happy-path suites.** Twelve tests for valid input, zero for invalid, empty, or failure-injected input — where the actual bugs live.

## 2. Standards

- Test names state the behavior and condition: `rejects_expired_token`, not `test_auth_3`. A failure should be diagnosable from the name plus the assertion message alone.
- **Every bug fix ships with a test that failed before the fix** (red-before-green, core manual §5). No exceptions — it's the only proof the test guards anything.
- Tests are deterministic: no real network, no real clock (inject/freeze time), no dependence on execution order or leftover state. Each test builds what it needs.
- Mock only what you don't own (external services, time, randomness). Your own code gets tested for real; if it's too entangled to test unmocked, that's a design finding, not a mocking opportunity.
- Assert on outcomes visible to the caller/user: return values, state changes, emitted effects. Internal call sequences are fair game only when the interaction IS the contract (e.g., "sends exactly one email").
- Expected values come from outside the implementation: the spec, hand computation, known-good fixtures.
- One behavior per test; shared setup via fixtures/helpers, not copy-paste and not a 40-line mega-test.

## 3. Defaults

- Shape: a modest number of integration-level tests exercising real component seams, a broad base of unit tests for logic-dense code, a handful of end-to-end for the money paths. Skew toward the highest level that runs fast enough.
- Table-driven tests for edge matrices (empty/one/many/huge/unicode — the self-review list) instead of near-duplicate test functions.
- Match the project's existing test framework, layout, and naming exactly; a parallel test style is scope creep.
- Speed budget: the suite a developer runs per-change should be seconds, not minutes; slow suites stop being run, and unrun tests guard nothing.

## 4. Verification (testing the tests)

- **Watch the new test fail.** Revert the fix (or comment the behavior) and run it: red? Restore: green? If it never went red, it tests nothing — rewrite it.
- Mutation spot-check for load-bearing logic: flip an operator or boundary in the code; at least one test should scream. Silence = a coverage hole where it matters.
- Read the failure output of your new test once: does the message say what broke and what was expected, without a debugger?
- Run the suite twice, and once in a different order if the runner supports it — flush out order dependence and leftover state now.

## 5. Edge cases that always matter

- The standard matrix per input: empty / zero / null / one / many / huge / unicode / malformed.
- Failure injection: the dependency throws, times out, returns garbage — what does the unit under test DO (not just "doesn't crash": the designed behavior)?
- Boundaries, exactly: the value AT the limit, one below, one above. Most off-by-ones live in tests that only checked "well inside" and "well outside."
- Time: DST transitions, end of month, epoch edges, timezone-naive vs aware — freeze the clock and test the boundary dates by name.
- Concurrency where it exists: run the operation twice in parallel in a test if the code claims idempotency or locking.

## 6. Stop signals

- The test needs to reach into private internals to assert → the code's design is hiding its observable behavior, or you're testing the wrong thing. Fix one of those.
- Setup is 30 lines for a 2-line assertion → the unit under test has too many dependencies; the test is reporting a design smell — listen to it.
- You're weakening an assertion to make CI pass → you are deleting the alarm because it rang. Understand the failure first (core manual §6).
- A test broke and you can't tell whether the code or the test is wrong → the test's expected values weren't independently sourced; re-derive them from the spec before touching either.
