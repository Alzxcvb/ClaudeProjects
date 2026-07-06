# Domain: Automation & Scripting

Applies when: writing scripts that act on the world — cron jobs, scrapers, browser automation, bulk operations against APIs, glue between services. Load with `CLAUDE-FABEL.md`.

The defining property of this domain: the script's environment is HOSTILE AND CHANGING. Pages restructure, APIs throttle, sessions expire, networks flake. Code that assumes cooperation is code that fails silently at 3am.

## 1. Failure modes

- **Happy-path scripts.** No handling for the service being down, the element missing, the response empty. Works in the demo, dies unattended.
- **Silent partial success.** Processes 40 of 200 items, hits an error, exits — and reports nothing about the 160. The operator believes it finished.
- **Yesterday's selectors.** Scrapers hardwired to exact DOM paths (`div:nth-child(3) > span`) that die on the next site tweak, with an error that says nothing about what changed.
- **Retry duplication.** Re-running after a crash re-performs actions already done — double emails, double orders, double posts.
- **No rate limiting.** Hammering an API/site at full speed until banned. Bans outlast the bug.
- **Hardcoded secrets and paths.** Credentials in the script; absolute paths from the author's machine.

## 2. Standards

- **Idempotent or resumable.** Track what's been processed (a state file, a done-marker, an idempotency check against the target) so re-runs skip completed work. Assume every run can die mid-way.
- **A run report is mandatory output**: attempted / succeeded / failed / skipped, with per-failure reasons. "Done" alone is a failed report.
- **Timeouts on every network call.** No unbounded waits anywhere. Retries with backoff for transient failures, with a retry BUDGET — then fail loudly.
- **Fail loudly at the end**: nonzero exit + a clear summary if anything failed, so cron/CI can alert. Never `except: continue` without counting and reporting.
- Secrets from environment or a secret store, never in the script or its logs. Paths relative to a configurable root.
- Rate limits respected by design: deliberate delay/concurrency cap, chosen from the target's documented or observed tolerance.
- Browser automation specifically: prefer stable selectors (roles, labels, data-test IDs) over positional CSS; wait on conditions, never fixed sleeps; screenshot + dump HTML on failure so the 3am break is diagnosable at 9am.

## 3. Defaults

- The dumbest tool that works: `curl`/requests before a browser; an official API before scraping; scraping only when no API exists.
- Dry-run mode (`--dry-run` printing what WOULD happen) for anything that mutates external state — build it first, it's also your test harness.
- Small-batch first run: cap at N=3 items, verify results by hand, then open the throttle.
- Logs to a file with timestamps, not just the terminal; the terminal disappears, the 3am question doesn't.

## 4. Verification

- Run once end-to-end against reality (small batch), then **verify side effects by reading them back** from the target system — the email in Sent, the row in the sheet, the post live. Absence of errors is not evidence of effect.
- Kill it mid-run, run again: completed items skipped? partial item handled?
- Force a failure (bad credential, unreachable host, missing element) and check: does the run report show it, and is the exit code nonzero?
- Read the log file after the run — could a stranger tell what happened from it alone?

## 5. Edge cases that always matter

- Empty result sets: "found 0 items" — designed outcome or silent breakage? The script must distinguish and say which.
- Auth expiry mid-run; the login page appearing where content was expected (scrapers: detect it explicitly).
- Pagination: the last page, items added/removed between pages.
- Unicode/encoding in scraped content; HTML entities; timezone math in scheduled jobs (cron runs in whose timezone?).
- The target's failure modes: 429s, CAPTCHAs, maintenance pages — each needs a designed response, not a crash.

## 6. Stop signals

- The script needs a database, a queue, or a second config format → it's becoming an app; restructure deliberately or stop.
- You're adding the third `time.sleep()` to outwait flakiness → switch to condition-based waits; sleeps are guesses.
- Scraping requires defeating anti-bot measures beyond polite-user behavior → stop and surface; that's a decision about terms and risk for the user, not an engineering problem.
- The retry loop exists to survive an error you haven't understood → understand it first (core manual §6); retrying a mystery just schedules the failure.
