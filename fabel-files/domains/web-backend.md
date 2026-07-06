# Domain: Web Backend / HTTP APIs

Applies when: building or changing HTTP endpoints, services, request handling, auth, or server-side business logic. Load with `CLAUDE-FABEL.md`.

## 1. Failure modes

- **200-with-error-body.** Returning success status codes with an error in the payload, breaking every client that checks status first.
- **Trusting the client.** Validating input in the UI only; assuming the caller sends what the frontend would send. Attackers and retries don't use your frontend.
- **Authn ≠ authz confusion.** Checking that a user is logged in but not that THIS resource is theirs. The classic: `GET /orders/123` returns any order to any authenticated user.
- **Silent breaking changes.** Renaming a response field or tightening validation without knowing who consumes the endpoint.
- **Long work in the request path.** Sending emails, calling slow third parties, or processing files synchronously inside the request, then timing out.
- **Swallowed errors at the boundary.** `catch { return [] }` around external calls, converting outages into mysteriously empty data.

## 2. Standards

- Status codes tell the truth: 400 bad input, 401 unauthenticated, 403 unauthorized, 404 absent (or 403 if existence itself is private — be consistent with the codebase), 409 conflict, 5xx only for genuine server faults.
- All input validated at the boundary — types, ranges, lengths, enums — with error messages that name the offending field. Unknown fields: rejected or ignored per codebase convention, but deliberately.
- Every ownership-scoped resource access includes the ownership check in the query itself (`WHERE id = ? AND user_id = ?`), not as a separate lookup that can be forgotten.
- Mutating endpoints that clients may retry are idempotent (idempotency key, upsert, or natural idempotency) — networks retry whether you planned for it or not.
- Errors are logged with request context (route, user/request ID) and WITHOUT secrets, tokens, or passwords. No stack traces or internal paths in responses.
- List endpoints paginate; there is no "return all rows" endpoint unless the row count is provably bounded and small.

## 3. Defaults

- Boring REST matching the codebase's existing conventions (envelope shape, error format, naming). Consistency with neighbors beats abstract correctness.
- Additive API evolution: new optional fields are fine; renames/removals require finding every consumer first (grep, logs) and are their own task.
- Slow side effects go to a queue/background job; the request path does validation + persistence + response.
- Timeouts on every outbound call, always. No unbounded waits inside a request.
- Transactions around any multi-write invariant; the DB enforces what the DB can enforce (see `database.md`).

## 4. Verification

- `curl` (or the test client) the endpoint four ways minimum: happy path, invalid input, unauthenticated, wrong-user/unauthorized. Quote the actual status codes and bodies observed.
- For mutations: verify the side effect by READING IT BACK (query the row, fetch the resource), not by the absence of an error.
- Fire the same mutation twice; confirm the second behaves as designed (idempotent or clean 409).
- Check the server log output for the error paths you triggered — is there enough context to debug from the log alone?

## 5. Edge cases that always matter

- Payloads: empty body, huge body, wrong content type, duplicate keys, unicode, `null` vs. absent field.
- IDs: nonexistent, deleted, belonging to someone else, malformed (string where int expected).
- Concurrency: two requests mutating the same resource at once — who wins, and is the invariant preserved?
- Time: timezone-naive datetimes crossing midnight/DST; token expiring mid-session.
- Pagination: page beyond the end, page size 0 or 10000, data changing between pages.

## 6. Stop signals

- An endpoint needs 3+ boolean query params to control its behavior → it's multiple endpoints.
- You need the client to "just call them in the right order" for correctness → the invariant belongs server-side, in one call or a transaction.
- The auth check is copy-pasted per handler → it belongs in middleware; a missed paste is a vulnerability.
- You're about to loosen validation to make an error go away → the error is telling you about a real caller; find it first.
