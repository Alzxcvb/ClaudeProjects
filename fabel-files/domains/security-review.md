# Domain: Security Review (defensive)

Applies when: reviewing code for vulnerabilities, hardening a feature, or writing code that handles untrusted input, auth, or secrets. Scope is defensive: finding and fixing weaknesses in systems you're authorized to work on.

## 1. Failure modes

- **Style review wearing a security hat.** Commenting on naming and structure while missing that user input reaches a query. Security review is about DATA FLOW, not code aesthetics.
- **"Validated elsewhere" assumption.** Trusting that some other layer sanitized the input. If you can't point to the line that validates it, it isn't validated.
- **Authn/authz conflation.** Verifying the user is logged in, never verifying the resource is theirs. Most real-world access bugs are authz, not authn.
- **Vague findings.** "This could be insecure" — unfalsifiable and unactionable. A finding without an attack path is a feeling.
- **Crying wolf.** Flooding a review with theoretical non-issues, training everyone to ignore the review that matters.
- **Secrets "temporarily" in code.** There is no temporarily; there is only committed and not-yet-committed.

## 2. Standards

- **Every finding states a concrete attack scenario**: the input, the path it travels, and the impact. "A username containing `'; DROP TABLE` reaches `db.execute` unparameterized at handler.py:42 → arbitrary SQL." No scenario, no finding.
- Findings are ranked by exploitability × impact, worst first, and separated from hardening suggestions.
- Trust boundaries are enumerated explicitly at the start of a review: every place external data enters (requests, files, env, webhooks, model output, subprocess output) and every place data exits to an interpreter (SQL, shell, HTML, path, eval, deserializer).
- Secrets: never in code, logs, error messages, or client-delivered payloads. Anything already committed is treated as burned — rotate, don't just delete.
- Fixes prefer the structural control over the patch: parameterized queries over escaping, allowlists over blocklists, framework auto-escaping over manual, deny-by-default authz over per-route remembering.

## 3. Method (the review procedure)

1. **Map entry points.** List every route/handler/consumer of external input in scope.
2. **Trace each input to its sinks.** For each entry point, follow the data until it dies or exits into an interpreter. The question at each sink: is it parameterized/escaped/validated FOR THIS SINK's language?
3. **Walk the authz matrix.** For each resource × operation: where is the ownership/role check? In the query itself, middleware, or (finding) nowhere / only the UI?
4. **Sweep the classics** against the checklist: injection per sink type (SQL, shell, path traversal, XSS, template), insecure deserialization, SSRF on any URL the server fetches, missing rate limits on auth endpoints, weak or unsalted password hashing (bcrypt/scrypt/argon2 only), permissive CORS, secrets in code/logs, dependency CVEs (`npm audit` / `pip-audit`).
5. **Check the failure behavior.** What do errors leak (stack traces, paths, versions)? Does auth fail closed?

## 4. Verification

- Every claimed vulnerability gets a **proof**: a working PoC input where safe to run, or a precise line-by-line trace where not. A finding you can't demonstrate or trace gets labeled as a hypothesis, per core-manual calibration.
- Every fix is verified by re-running the attack that motivated it and watching it fail — red-before-green applies to exploits too.
- After fixing, sweep for siblings: the same bug pattern usually exists everywhere the same author/pattern touched. Grep for the pattern, don't fix one instance and declare victory.

## 5. Edge cases that always matter

- Second-order injection: data stored safely now, interpolated dangerously later (in a report, an email template, an admin page).
- IDs in URLs/payloads: enumerable? signed? checked against the session's owner?
- File uploads: extension vs. content-type vs. actual bytes; where files land (web root?); path traversal via filename.
- Timing and enumeration: login/reset endpoints revealing whether an account exists.
- The machine-facing surface: webhooks, cron endpoints, internal APIs — often authenticated by nothing but obscurity.

## 6. Stop signals

- You're about to approve because "it's internal" → internal is one phished laptop away from external; review it at half severity, not zero.
- The fix requires every future developer to remember something → it will be forgotten; make the safe path the default path instead.
- You've found nothing at all in nontrivial code handling untrusted input → suspect your review before their code; re-run the method on the top three entry points.
- The task drifts toward building attack capability for use against systems the user doesn't own → out of scope; stop and say so.
