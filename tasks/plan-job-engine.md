# Job Engine: implementation plan

Written 7 September 2026 against the revised `Dev/tasks/brief-job-engine.md`, which is authoritative. This plan adds nothing to the brief's scope. Where it picks a value the brief left open, it says so and marks it as an assumption. Revision 2 replaces the first plan entirely: own Chrome profile and port, the six submission controls, the corpus allowlist, the answer bank, the residency filter, hours as a scored field, three exact floors with strict greater than, the lane 1 higher education sources, verbatim quoted company notes, count based report reconciliation, and per row degradation reasons.

Repo: `/Users/alexandercoffman/Dev/job-engine/` (its own `.git`, commits made inside it, staged by path).
Runtime: Python 3.11, per the brief. JARVIS pins 3.12 in `jarvis/.python-version`, but 3.12 is not installed on this Mac and the brief resolved not to force an install, so Phase 0 runs `/opt/homebrew/bin/python3.11 -m venv .venv` and every command below is `.venv/bin/python ...`. The system `python3` is 3.9 and must not be used.
Inference, revision 3, replacing the paid API model layer entirely. Alex has ruled out all API spend, so there is no Anthropic API key anywhere in this repo and no pay per token call at any tier.

- **Tier 0, no model.** Lane keyword match, remote flag, residency eligibility and all three pay floors run as ordinary code over the structured ATS fields. Most of the 400 daily postings are cut here. Every avoided call is subscription capacity kept.
- **Tier 1, free tier provider, bulk classification.** Lane fit and first pass automation potential on whatever survives tier 0. Groq, Google Gemini Flash Lite, or a local Ollama model, behind one interface in `llm.py`. Their free tier limits are UNKNOWN and could not be verified on 2026-09-07: Groq renders its limits table client side so a fetch returns only audio model rows, and Google publishes no fixed numbers, showing per account limits inside AI Studio. Hardcode no rate assumption. After the account exists, read the real limits from the console and record them with the date in the README. `llm.py` paces requests, backs off on 429, degrades to fewer candidates rather than failing, and supports a local Ollama backend on equal footing since it is the only option whose ceiling is known in advance.
- **Tier 2, Claude Code, low volume and high judgment.** Deep scoring, company notes and the writing, roughly 25 and 8 a day. This does NOT call the Messages API. It runs as a scheduled Claude Code routine that invokes this repo's functions as tools. Subscription credentials are not API credits, and consumer terms restrict OAuth to Claude Code and claude.ai; Claude Code and its routines are explicitly permitted native use.

Standing rule: usage credits are never enabled on Alex's account. That one setting is what keeps the budget at zero if Anthropic reactivates the paused Agent SDK credit, whose documented behaviour without usage credits is a hard stop rather than a rollover into billing.

## 0. Rules for every slice agent

1. Read only your phase section plus sections 1 to 3. Sections 1 to 3 are frozen after Phase 0; later phases add columns only through the migrations block in `db.py`.
2. Never import from `Dev/jarvis`. Never add LinkedIn, Indeed, USAJOBS or Workday code paths. Never solve or bypass a CAPTCHA; a challenge routes to the approval queue.
3. Never touch port 9222 or the `CDP-Profile` directory. Job engine's browser is its own profile on `JOBENGINE_CDP_PORT` (default 9333).
4. Fail closed. A required form field with no mapping in `data/answer_bank.yaml` stops that application and queues it. Nothing about work authorization, residency, EEO, veteran or disability status is ever model generated. No filter anywhere keys on work authorization.
5. The corpus is the explicit file list in `data/corpus_allowlist.txt`. `profile.py` and `corpus.py` must not import `glob`, `os.walk`, `Path.rglob` or `Path.glob`; a test greps for them. A directory path on the allowlist is an error.
6. The four floor literals (2000, 60000, 150000, 212900) each appear exactly once outside `tests/`, in `job_engine/config.py`. Never write these numbers anywhere in `job_engine/`, `scripts/`, `bin/`, `README.md` or `.env.example` for any other purpose (token limits, years, sleeps, dates); pick another value. The check greps only those paths, so fixtures under `tests/` may hold them. Every floor comparison is strictly greater than.
7. `DRY_RUN` defaults to on. Only `JOBENGINE_DRY_RUN=false` turns it off, and only Alex sets that.
8. No dash characters in any Telegram message text, prompt file, README prose or code comment. Commas and periods instead. Hyphens in identifiers, paths and URLs are fine.
9. Tests run offline against `tests/fixtures/`. Live checks are named per phase and run with the Bash sandbox disabled or from Alex's terminal, because the sandbox blocks localhost ports.
10. Every outbound HTTP call goes through `job_engine/http.py`; every browser tab comes from `job_engine/browser.py`. Both log hosts per stage and abort the denylist. Every tier 1 model call goes through `job_engine/llm.py`, which enforces `MAX_MODEL_CALLS_PER_RUN['tier1']` and the prompt content guard. Tier 2 is not a call from this repo at all: Claude Code invokes the repo's functions. The guard therefore moves to the repo boundary. `deep.pending()` and `writer.pending()` run `corpus.probe()` over every field they are about to return and raise `PromptContentBlocked` rather than hand up a deny term, so nothing reaches the tier 2 model that could not reach the tier 1 one. `deep.record()` and `writer.record()` increment `runs.tier2_calls` and enforce `MAX_MODEL_CALLS_PER_RUN['tier2']`. The routine's working directory is the job engine repo only; it is never pointed at `Dev/` as a whole.
11. Pin versions, all nine verified against PyPI on 2026-09-07 and current as of that date. The `anthropic` SDK is NOT a dependency; there is no API key path. `python-telegram-bot[job-queue]==22.8`, `playwright==1.62.0`, `fpdf2==2.8.8`, `pypdf==6.17.0`, `python-docx==1.2.0`, `PyYAML==6.0.3`, `requests==2.34.2`, `python-dotenv==1.2.3`, `pytest==9.1.1`. No `playwright install`; the browser is a real Chrome launched by `bin/chrome.sh`.
12. A source is fetched only when its registry entry carries `terms_verdict="allowed"` with a `terms_url` and `checked_on` date. The brief requires this check for every board and it is code, not a note.

## 1. File tree

```
job-engine/
  README.md                      run instructions, human items, source terms table, the no ratings API statement, cut list, "run bin/start.sh after any restart"
  requirements.txt               pinned deps above
  .env.example                   every env var, blank values, no secrets, no floor literals
  .gitignore                     .env, .venv/, data/*.db*, data/raw/, data/screenshots/, data/resumes/, data/profile.yaml, data/answer_bank.yaml, data/corpus_allowlist.txt, data/STOP
  bin/
    run-daily.sh                 THE scheduled command: exports JOBENGINE_TRIGGER_COMMAND and runs caffeinate -i .venv/bin/python -m job_engine.daily "$@"
    chrome.sh                    launches the job engine Chrome: own user-data-dir JobEngine-Profile, --remote-debugging-port=$JOBENGINE_CDP_PORT, detached
    start.sh                     nohup .venv/bin/python -m job_engine.bot > ~/Library/Logs/job-engine.log 2>&1 & disown; writes data/bot.pid
    stop.sh                      kills the pid in data/bot.pid
  job_engine/
    __init__.py
    config.py                    env loading, every constant (floors, lanes, caps, DRY_RUN, stop file, lock paths, denylist, permitted reputation hosts, seed queries, model ids)
    db.py                        SCHEMA_SQL, connect(), init_db(), migrations block, add_column_if_missing()
    types.py                     dataclasses shared across seams (section 3)
    http.py                      requests wrapper: UA, retries, per hop host log with stage, denylist guard, raw body capture
    browser.py                   Playwright connect_over_cdp to JOBENGINE_CDP_PORT, LinkedIn cookie assertion, own tab lifecycle, request host log, denylist abort, screenshots, chrome self start
    locks.py                     shared browser lock (job engine and Prospector) plus the run lock; holder records with pid liveness
    runs.py                      runs table helpers, degradations, per tier call counters, preflight
    corpus.py                    allowlist loader: explicit files only, line indexed, content probe, no directory walking
    profile.py                   loads data/profile.yaml, fails closed on blanks
    answer_bank.py               loads data/answer_bank.yaml, maps form labels to bank keys by pattern, raises on unmapped required fields
    pay.py                       salary regex, normalization to monthly and annual, hours, effective hourly, floor check in native unit, strict greater than
    filters.py                   remote, staleness, denylist, residency requirement, duplicate; never work authorization
    dedupe.py                    company plus normalized title key, cross board, cross day, cooldown window
    sources/
      __init__.py                registry: Source(name, fetch, needs_browser, lanes, terms_url, terms_verdict, checked_on); only allowed sources run
      remotive.py                remotive.com/api/remote-jobs, seed queries
      remoteok.py                remoteok.com/api (skip element 0, the legal notice; link back rule noted)
      arbeitnow.py               arbeitnow.com/api/job-board-api
      adzuna.py                  api.adzuna.com search, needs keys, free tier limit verified from Adzuna's own docs on day 2, 3 calls a day cap regardless
      greenhouse.py              boards-api.greenhouse.io per known slug, plus ?questions=true detail
      lever.py                   api.lever.co/v0/postings/{slug}?mode=json
      ashby.py                   api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
      smartrecruiters.py         api.smartrecruiters.com/v1/companies/{id}/postings plus detail
      recruitee.py               {slug}.recruitee.com/api/offers/
      higheredjobs.py            HigherEdJobs search by seed query (lane 1); terms check first
      edjoin.py                  EDJOIN search by seed query (lane 1); terms check first
      cccregistry.py             CCC Registry listings (lane 1); terms check first; jobs page bounced to a JS lander on 7 September 2026, likely account gated
      ccc_districts.py           California community college district HR sites from a seed list of district URLs (lane 1); terms check per district
      climatebase.py             Playwright reader (Phase 7), only if terms allow; robots.txt returned 403 to a plain fetch on 7 September 2026, treat as likely forbidden
      terra.py                   Playwright reader (Phase 7), only if terms allow
      inclimate.py               Playwright reader (Phase 7), only if terms allow
      climatetechlist.py         reader (Phase 7), only if terms allow
      workonclimate.py           reader (Phase 7), only if terms allow
      ats_detect.py              apply_url to (ats_kind, slug, job_id); company name to slug probing; apply_surface classification
    ingest.py                    runs allowed sources, saves raw bodies, normalises, dedupes, upserts jobs and companies, records per source counts
    llm.py                       tier 1 provider interface (Groq, Gemini or local Ollama), structured output call, MAX_MODEL_CALLS_PER_RUN before every call, prompt content guard, call counting, prompt_log writes
    prompts/
      triage.md                  tier 1 system prompt
      triage_examples.md         12 illustrative postings with lane labels, hours and automation scores, always included
      deep.md                    tier 2 deep score prompt, used by the routine
      reputation.md              tier 2 company note prompt (verbatim quote per claim)
      writer.md                  tier 2 resume, cover letter and free text answers prompt
      reply_classify.md          tier 1 inbox classifier prompt
    ratings.py                   record(), prompt_block(limit=RATING_EXAMPLES)
    triage.py                    tier 1 pass over new jobs; CLI --dump-prompt --job-id N
    deep.py                      tier 2 shortlist scoring via Claude Code, decision rules, lane 3 dark handling, application row creation
    reputation.py                fetch permitted pages, tier 2 note, verbatim quote verification in code, 30 day cache
    writer.py                    resume_md, cover_letter_md, free text answers, claims with cited corpus lines
    trace.py                     the traceability gate: claim to line check plus vocabulary check, sentence dropping, gut threshold
    render.py                    Markdown to PDF with fpdf2; original resume file passthrough fallback
    ats/
      __init__.py                get_adapter(kind)
      base.py                    AtsAdapter interface, FormSpec, FormField, SubmitResult, captcha detection, account wall detection
      greenhouse.py              form_spec via ?questions=true, DOM fill and submit
      lever.py                   DOM fill and submit
      ashby.py                   DOM fill and submit (posting detail API is 401 without a company key, verified 7 September 2026)
      smartrecruiters.py         DOM fill and submit
      recruitee.py               careers API POST if confirmed on a real slug, else DOM
    submit.py                    ordered send: capture payload, commit, stop file, daily cap, DRY_RUN, send, evidence; CLI --application-id N
    approvals.py                 pending_approvals CRUD, message builders
    mail.py                      read only IMAP reader, tier 1 classify, match to applications, quiet past threshold flags, running reply count
    report.py                    send_message() over Bot API HTTP, compose header under 3,500 chars, top N match messages, reports and degradations rows, report_lines
    bot.py                       long running poller: callbacks, /status /run /ping /stop, JobQueue daily job, catch up on boot, chrome self start
    daily.py                     orchestrator: preflight, stages in order, per stage degradation rows, always sends a report
  data/
    .keep
    profile.example.yaml         every field, blank
    answer_bank.example.yaml     every key, blank, with the legal attestation note
    corpus_allowlist.example.txt one absolute file path per line, comments allowed, no directories, no globs
    boards.seed.txt              "kind,slug" per line, grows via detection
    districts.seed.txt           California community college district HR URLs, one per line, each with its terms verdict
    raw/                         {run_id}/{source}.{json|html}, the raw body per source per run
  tests/
    conftest.py                  temp db, fake profile, fake corpus, fake answer bank, fake LLM, fixture loader
    fixtures/                    saved API JSON, form HTML snapshots, sample emails, reputation pages
    test_floors.py               acceptance 4: boundaries, strict greater than, normalization, hours unknown, the 1,500 a month hole, single literal
    test_decision_rules.py       routing, unknown pay and hours paths, lane 3 dark, quotas
    test_filters.py              remote, staleness, denylist, duplicate
    test_residency_filter.py     acceptance 13, both directions, no work authorization keying
    test_dedupe.py               acceptance 10 dedupe half, cross board and cross day
    test_ingest_counts.py        raw body parsed count equals stored count
    test_sources_parse.py        each parser against its fixture
    test_terms_gate.py           a source with verdict forbidden is never fetched
    test_ats_detect.py           URL patterns and apply_surface classification
    test_triage_parse.py         schema validation, shortlist sort
    test_ratings_loop.py         acceptance 4b offline half
    test_corpus_allowlist.py     acceptance 12, by name and by content probe, no walking imports
    test_trace_gate.py           acceptance 9 offline half with a fake persuasive model
    test_answer_bank.py          acceptance 11
    test_reputation_quotes.py    a signal whose quote is not in the fetched page is dropped
    test_submission_controls.py  acceptance 10 and 10c: DRY_RUN, daily cap, stop file, payload before send
    test_call_cap.py            acceptance 10b
    test_lock.py                 acceptance 10d
    test_ats_formspec.py         each adapter's form_spec against fixture HTML/JSON
    test_report_roundtrip.py     acceptance 2 offline half
    test_no_linkedin_indeed.py   acceptance 6 static half plus denylist guard behaviour
  scripts/
    check_preflight.py           acceptance 1b: lock held and Chrome down scenarios, degraded report rows present
    check_report.py              acceptance 2 against a real run id, three assertions
    check_submission_proof.py    acceptance 3 against a window of runs
    check_routing.py             acceptance 5 with deferral reporting
    outbound_hosts.py            acceptance 6 host half
    check_profile_cookies.py     acceptance 6 cookie half, also run at every browser start
    verify_schedule.py           acceptance 8
    verify_window.py             definition of done: qualifying mornings and confirmed submissions over days 8 to 14
    seed_boards.py               fills data/boards.seed.txt from detected ATS slugs
```

## 2. DB schema

SQLite, file `data/job_engine.db`. `db.connect()` sets `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `busy_timeout=30000`, `row_factory=sqlite3.Row`. The bot process and the daily subprocess share the file.

Ordering rule: every index and constraint appears after the column it references exists. New columns go in the migrations block at the end, through `add_column_if_missing(table, column, ddl)` which checks `PRAGMA table_info` first because SQLite has no `ADD COLUMN IF NOT EXISTS`. Indexes on migrated columns go after their ALTER, inside the migrations block.

```sql
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- keys used: last_imap_uid, schema_version, replies_total

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    started_by TEXT NOT NULL,            -- schedule | manual | catchup
    trigger_command TEXT NOT NULL,       -- JOBENGINE_TRIGGER_COMMAND, else argv
    status TEXT NOT NULL DEFAULT 'running',  -- running | ok | partial | failed | locked
    dry_run INTEGER NOT NULL DEFAULT 1,
    stage_json TEXT,                     -- {stage: {ran: bool, ok: bool, counts: {...}, error: str|null}}
    browser_available INTEGER NOT NULL DEFAULT 0,
    tier1_calls INTEGER NOT NULL DEFAULT 0,
    tier2_calls INTEGER NOT NULL DEFAULT 0,
    report_sent_at TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
CREATE INDEX IF NOT EXISTS idx_runs_by ON runs(started_by);

-- One row per degradation per run. disqualifying=1 removes the morning from the seven day count.
CREATE TABLE IF NOT EXISTS degradations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    stage TEXT NOT NULL,                 -- preflight | ingest | triage | deep | write | submit | mail | report
    reason TEXT NOT NULL,                -- lock_refused | browser_unavailable | linkedin_cookies_present | browser_stage_error | call_cap | source_error | source_terms_unverified | lane3_dark_floor_open | stale_lock_cleared | stop_file | daily_cap | inbox_absent
    disqualifying INTEGER NOT NULL,      -- 1 for lock_refused, browser_unavailable, linkedin_cookies_present, browser_stage_error; 0 otherwise
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_degradations_run ON degradations(run_id);

CREATE TABLE IF NOT EXISTS raw_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    status_code INTEGER,
    body_path TEXT NOT NULL,             -- data/raw/{run_id}/{source}_{n}.{json|html}
    body_sha1 TEXT NOT NULL,
    parsed_count INTEGER,                -- postings the parser found in this body
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_raw_run_source ON raw_responses(run_id, source);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_norm TEXT NOT NULL,             -- lowercase, punctuation and legal suffixes stripped
    website TEXT,
    domain TEXT,
    ats_kind TEXT,                       -- greenhouse | lever | ashby | smartrecruiters | recruitee | NULL
    ats_slug TEXT,
    ats_probe_done INTEGER NOT NULL DEFAULT 0,
    apply_surface TEXT,                  -- ats | account_required | unknown
    climate_flag INTEGER,
    reputation_summary TEXT,
    reputation_json TEXT,                -- signals with verbatim quotes and source urls, sources_used, confidence
    reputation_checked_at TEXT,
    last_applied_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_companies_name_norm ON companies(name_norm);
CREATE INDEX IF NOT EXISTS idx_companies_ats ON companies(ats_kind, ats_slug);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,            -- lowercase, seniority and punctuation noise stripped
    url TEXT NOT NULL,
    apply_url TEXT,
    description TEXT NOT NULL DEFAULT '',
    location_text TEXT,
    remote_flag INTEGER,                 -- 1 | 0 | NULL unknown
    employment_type TEXT,                -- full_time | part_time | contract | NULL
    salary_text TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_period TEXT,                  -- year | month | hour | NULL
    salary_currency TEXT,
    hours_text TEXT,
    hours_per_week REAL,                 -- stated hours, NULL when silent
    hours_unknown INTEGER NOT NULL DEFAULT 1,
    pay_monthly_usd REAL,                -- normalized, unrounded
    pay_monthly_estimated INTEGER NOT NULL DEFAULT 0,   -- 1 when derived via assumed 40h/52w
    pay_annual_usd REAL,
    pay_annual_estimated INTEGER NOT NULL DEFAULT 0,
    effective_hourly_usd REAL,           -- pay divided by stated hours, or the stated hourly rate
    effective_hourly_estimated INTEGER NOT NULL DEFAULT 0,
    pay_status TEXT,                     -- pass | fail | unknown, written once lane is known
    residency_required INTEGER NOT NULL DEFAULT 0,
    residency_country TEXT,              -- ISO code when the posting names a required residence
    posted_at TEXT,
    ats_kind TEXT,
    ats_slug TEXT,
    ats_job_id TEXT,
    dedupe_key TEXT NOT NULL,            -- sha1(company name_norm | title_norm)
    duplicate_of INTEGER REFERENCES jobs(id),
    filter_status TEXT NOT NULL DEFAULT 'new',  -- new | passed | dropped
    filter_reason TEXT,
    first_seen_run_id INTEGER REFERENCES runs(id),
    last_seen_run_id INTEGER REFERENCES runs(id),
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source, source_id);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_filter ON jobs(filter_status);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_run_id);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    run_id INTEGER NOT NULL REFERENCES runs(id),
    stage TEXT NOT NULL,                 -- triage | deep
    model TEXT NOT NULL,
    lane INTEGER NOT NULL,               -- 0 none, 1 part time, 2 full time cash, 3 climate
    lane_confidence REAL,
    lane_match INTEGER,                  -- 0 to 100 (deep)
    automation_potential INTEGER NOT NULL,  -- 0 to 100
    pay_status TEXT NOT NULL,            -- pass | fail | unknown
    hours_unknown INTEGER NOT NULL,
    adjusted_hourly_usd REAL,            -- desirability only, never used against a floor
    overall INTEGER,                     -- 0 to 100 (deep, computed in code)
    decision TEXT,                       -- deep: apply | queue | report | skip | dark
    decision_reason TEXT,
    result_json TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_scores_job_stage ON scores(job_id, stage);
CREATE INDEX IF NOT EXISTS idx_scores_run_stage ON scores(run_id, stage);
CREATE INDEX IF NOT EXISTS idx_scores_decision ON scores(run_id, decision);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    company_id INTEGER NOT NULL REFERENCES companies(id),
    run_id INTEGER NOT NULL REFERENCES runs(id),
    lane INTEGER NOT NULL,
    dedupe_key TEXT NOT NULL,            -- copied from jobs at creation
    status TEXT NOT NULL,
    -- queued | approved_auto | approved_manual | skipped | drafted | captured | dry_run
    -- | submitting | submitted_unconfirmed | submitted_page | submitted_email | submitted_both
    -- | challenged | manual | halted | failed
    status_reason TEXT,
    send_mode TEXT,                      -- dry_run | live
    resume_md TEXT,
    cover_letter_md TEXT,
    answers_json TEXT,                   -- [{path, label, value, source: bank|rule|writer}]
    claims_json TEXT,                    -- [{text, source_file, source_line, verified}]
    trace_json TEXT,                     -- {sentences_total, sentences_dropped, dropped: [...]}
    payload_json TEXT,                   -- full send payload: rendered resume path, cover letter, every form value
    payload_captured_at TEXT,
    resume_pdf_path TEXT,
    ats_kind TEXT,
    submitted_at TEXT,
    confirmation_url TEXT,
    confirmation_text TEXT,
    screenshot_path TEXT,
    confirmation_reply_id INTEGER,       -- replies.id, no FK because replies is created later
    proof_kind TEXT,                     -- page | email | both | NULL
    approved_at TEXT,
    quiet_since TEXT,                    -- set at submission; the mail stage flags when older than QUIET_DAYS with no reply
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_dedupe ON applications(dedupe_key, created_at);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company_id);
CREATE INDEX IF NOT EXISTS idx_applications_submitted ON applications(submitted_at);

CREATE TABLE IF NOT EXISTS pending_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    kind TEXT NOT NULL,                  -- climate | manual_challenge | manual_unanswered | manual_account_required | manual_no_adapter | manual_trace | manual_writer
    telegram_chat_id INTEGER,
    telegram_message_id INTEGER,
    decision TEXT,                       -- NULL | approve | skip
    decided_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_app_kind ON pending_approvals(application_id, kind);
CREATE INDEX IF NOT EXISTS idx_pending_open ON pending_approvals(decision);

CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    rating INTEGER NOT NULL,             -- 1 good, 0 not good
    telegram_message_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ratings_job ON ratings(job_id);
CREATE INDEX IF NOT EXISTS idx_ratings_created ON ratings(created_at);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_uid TEXT NOT NULL,           -- "{folder}:{imap uid}"
    from_addr TEXT,
    from_domain TEXT,
    subject TEXT,
    received_at TEXT,
    snippet TEXT,
    kind TEXT,                           -- confirmation | rejection | interview | info_request | other | unmatched
    application_id INTEGER REFERENCES applications(id),
    company_id INTEGER REFERENCES companies(id),
    match_confidence REAL,
    reported_run_id INTEGER REFERENCES runs(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_replies_uid ON replies(message_uid);
CREATE INDEX IF NOT EXISTS idx_replies_app ON replies(application_id);
CREATE INDEX IF NOT EXISTS idx_replies_unreported ON replies(reported_run_id);

-- One row per morning report. qualifying is computed at send time and never edited.
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    sent_at TEXT NOT NULL,
    telegram_message_id INTEGER,
    new_matches INTEGER NOT NULL DEFAULT 0,
    submitted_count INTEGER NOT NULL DEFAULT 0,
    queued_count INTEGER NOT NULL DEFAULT 0,
    replies_count INTEGER NOT NULL DEFAULT 0,
    degraded INTEGER NOT NULL DEFAULT 0,          -- 1 if any degradation row this run
    disqualifying INTEGER NOT NULL DEFAULT 0,     -- 1 if any degradation had disqualifying=1
    qualifying INTEGER NOT NULL DEFAULT 0,        -- 1 only when new_matches > 0 AND disqualifying = 0
    header_text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_run ON reports(run_id);
CREATE INDEX IF NOT EXISTS idx_reports_sent ON reports(sent_at);

-- One row per model call. Tier 2 rows are written by deep.record and writer.record, not by llm.py.
CREATE TABLE IF NOT EXISTS prompt_log (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    stage TEXT NOT NULL,
    tier TEXT,                          -- 'tier1' or 'tier2'
    provider TEXT,                      -- tier 1 provider name, or 'claude_code' for tier 2
    prompt_sha256 TEXT NOT NULL,
    input_tokens INTEGER,               -- null for tier 2, which reports no token counts
    output_tokens INTEGER,
    ok INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompt_log_run ON prompt_log(run_id);
CREATE INDEX IF NOT EXISTS idx_prompt_log_tier ON prompt_log(run_id, tier);

-- Every outbound host touched, both halves of acceptance 6.
CREATE TABLE IF NOT EXISTS outbound_hosts (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    stage TEXT NOT NULL,
    host TEXT NOT NULL,
    via TEXT NOT NULL,                  -- 'http' or 'browser'
    hits INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outbound_unique ON outbound_hosts(run_id, stage, host, via);
CREATE INDEX IF NOT EXISTS idx_outbound_host ON outbound_hosts(host);

-- Migration pattern:
--   add_column_if_missing('jobs', 'new_col', 'TEXT')
--   CREATE INDEX IF NOT EXISTS idx_jobs_new_col ON jobs(new_col)   (only after the ALTER)
```

## 3. Seam types, signatures, constants (frozen after Phase 0)

`job_engine/types.py`:

```python
@dataclass
class RawPosting:
    source: str
    source_id: str
    title: str
    company_name: str
    url: str
    apply_url: str | None = None
    description: str = ""            # plain text, HTML stripped by the source module
    location_text: str | None = None
    remote_flag: bool | None = None
    employment_type: str | None = None   # full_time | part_time | contract
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None     # year | month | hour
    salary_currency: str | None = None
    hours_text: str | None = None
    hours_per_week: float | None = None
    posted_at: str | None = None
    ats_kind: str | None = None
    ats_slug: str | None = None
    ats_job_id: str | None = None
    company_website: str | None = None
    raw_json: dict = field(default_factory=dict)

@dataclass
class PayFigures:
    monthly_usd: float | None
    monthly_estimated: bool
    annual_usd: float | None
    annual_estimated: bool
    effective_hourly_usd: float | None
    hourly_estimated: bool
    hours_unknown: bool
    native_period: str | None        # the period the posting quoted

@dataclass
class PayGate:
    status: str                      # pass | fail | unknown
    compared_value: float | None     # unrounded, in the floor's native unit
    floor: float
    note: str

@dataclass
class FilterResult:
    passed: bool
    reason: str | None               # not_remote | stale | denylisted_host | duplicate | residency_required | None

@dataclass
class FormField:
    path: str
    label: str
    kind: str                        # text | textarea | email | phone | file | select | multiselect | boolean | eeoc | unknown
    required: bool
    options: list[str] = field(default_factory=list)

@dataclass
class FormSpec:
    ats_kind: str
    fields: list[FormField]
    has_captcha: bool
    account_required: bool
    apply_url: str

@dataclass
class SubmitResult:
    status: str                      # dry_run | submitted_page | submitted_unconfirmed | challenged | unanswered | halted | failed
    confirmation_url: str | None
    confirmation_text: str | None
    screenshot_path: str | None
    error: str | None

@dataclass
class Claim:
    text: str
    source_file: str
    source_line: int
    verified: bool = False
```

Signatures every slice must match:

```
db.connect() -> sqlite3.Connection
db.init_db() -> None
locks.acquire_browser_lock(holder="job-engine") -> context manager; raises LockHeld(holder, pid)
locks.acquire_run_lock() -> context manager; raises RunLocked
runs.start(started_by, trigger_command, dry_run) -> int
runs.finish(run_id, status, stage_json) -> None
runs.degrade(run_id, stage, reason, disqualifying: bool, detail="") -> None
runs.add_calls(run_id, tier: str, n: int = 1) -> None   # tier is 'tier1' or 'tier2'; raises CallCapReached at the per tier limit
runs.preflight(run_id) -> dict           # {browser: bool, lock: bool, inbox: bool, tier1_provider: bool, lane3_remote: bool}
http.get(url, run_id, stage, **kw) -> requests.Response     # every hop logged; raises DenylistedHost
http.post(url, run_id, stage, **kw) -> requests.Response
http.save_raw(run_id, source, url, resp) -> str             # writes data/raw and raw_responses, returns body_path
browser.ensure_chrome() -> bool          # answers on JOBENGINE_CDP_PORT, starts bin/chrome.sh if not, waits up to 20 s
browser.session(run_id, stage) -> context manager yielding Browser; takes the shared browser lock for its lifetime; raises LockHeld, BrowserUnavailable, LinkedInCookiesPresent
browser.assert_no_linkedin_cookies(context) -> None
browser.new_tab(browser, run_id, stage) -> Page
browser.close_tab(page) -> None
browser.screenshot(page, name) -> str
corpus.load() -> list[CorpusLine]        # CorpusLine(file, line_no, text); raises AllowlistError on directories, globs, missing files
corpus.text() -> str
corpus.probe(text) -> list[str]          # deny terms found, used by llm.py before every send
profile.load() -> Profile                # raises ProfileIncomplete
answer_bank.load() -> dict
answer_bank.answer(field: FormField) -> tuple[str, str] | None   # (value, source) or None when unmapped
pay.parse_salary(text) -> tuple[min, max, period, currency] | None
pay.parse_hours(text) -> float | None
pay.normalize(salary_min, salary_max, period, currency, hours_per_week, employment_type) -> PayFigures
pay.floor_check(lane, figures: PayFigures, remote_flag, in_target_city) -> PayGate   # lane 3 has exactly two branches: a remote posting is gated by CLIMATE_REMOTE_FLOOR_USD, and a posting in a target city by CLIMATE_RELOCATION_FLOOR_USD. A remote lane 3 posting returns dark while CLIMATE_REMOTE_FLOOR_USD is unset. There is no mode that applies the relocation figure to remote roles.
pay.adjusted_hourly(figures, automation_potential) -> float | None
filters.prefilter(job: Row) -> FilterResult
filters.residency(job: Row, lane, in_target_city: bool) -> FilterResult
dedupe.key(company_name, title) -> str
dedupe.blocked(dedupe_key, now) -> tuple[bool, str]          # any application with the key inside APPLICATION_COOLDOWN_DAYS
sources.<name>.fetch(run_id, browser=None) -> list[RawPosting]
sources.enabled() -> list[Source]        # only terms_verdict == "allowed"
sources.ats_detect.from_url(url) -> tuple[kind, slug, job_id] | None
sources.ats_detect.apply_surface(url) -> str                 # ats | account_required | unknown
ingest.run(run_id, browser=None) -> dict      # {source: {fetched, parsed, inserted, updated, duplicates, error}}
ingest.upsert(posting, run_id) -> tuple[int, bool]
llm.call(stage, model, system_blocks, user, schema, run_id, job_id=None, company_id=None, application_id=None, max_tokens=1024) -> dict
     # order inside: call cap check, corpus.probe on every block, send, log, increment call count; raises CallCapReached, PromptContentBlocked
ratings.record(job_id, rating, telegram_message_id) -> int
ratings.prompt_block(limit=RATING_EXAMPLES) -> str
triage.run(run_id) -> int
triage.build_prompt(job, rating_block) -> tuple[list[str], str]
deep.pending(run_id) -> list[DeepTask]        # tier 2 handoff out; runs corpus.probe on every field first
deep.record(posting_id, run_id, result: DeepResult) -> None   # tier 2 handoff in; increments runs.tier2_calls
deep.decide(lane, overall, pay: PayGate, hours_unknown, remote_flag, in_target_city, residency: FilterResult, hard_red_flag, apply_surface, lane3_mode) -> tuple[str, str]
reputation.ensure(company_id, run_id) -> str
writer.pending(run_id) -> list[WriteTask]     # tier 2 handoff out; corpus.probe'd
writer.record(application_id, run_id, result: WriteResult) -> None   # tier 2 handoff in; runs the trace gate in code before storing
trace.gate(document_md, claims: list[Claim], corpus_lines) -> tuple[str, dict]   # (document with failing sentences dropped, trace_json); raises TraceGutted
render.resume_pdf(application_id) -> str
ats.get_adapter(kind) -> AtsAdapter
AtsAdapter.form_spec(job, page=None) -> FormSpec
AtsAdapter.submit(job, application, page) -> SubmitResult
submit.one(application_id, run_id) -> SubmitResult
     # order inside: capture payload and commit, stop file, MAX_SUBMISSIONS_PER_DAY, DRY_RUN, lock, send, evidence
submit.run_pending(run_id) -> int
approvals.create(application_id, kind) -> int
approvals.decide(pending_id, decision) -> int
mail.run(run_id) -> int
report.send_message(text, buttons=None) -> int
report.send(run_id) -> int               # writes reports row with qualifying, degradation lines, report_lines
daily.main(argv) -> int                  # 0 ok, 1 failed (no report), 2 partial (report sent, includes a Prospector held browser lock), 3 another job engine run holds the run lock (one line report sent)
```

Config constants (`config.py`):

```
LANE_PART_TIME = 1; LANE_FULL_TIME_CASH = 2; LANE_CLIMATE = 3
PARTTIME_FLOOR_USD_PER_MONTH = <literal, once>      # comment: stated by Alex; compare strictly greater than
CASH_FULLTIME_FLOOR_USD = <literal, once>           # comment: from the option Alex selected, "near" resolved exactly; strictly greater than
CLIMATE_RELOCATION_FLOOR_USD = <literal, once>                 # comment: 200,000 times CPI-U Jul 2026 (333.918) over the 2024 annual average (313.689), rounded to the nearest 100; do not write the result here
# CLIMATE_FLOOR_SCOPE removed. Alex settled this on 2026-09-07: the constant gates the relocation exception ONLY, never the whole lane. There is no "whole_lane" mode and none may be reintroduced.
CLIMATE_REMOTE_FLOOR_USD = 150000                   # stated by Alex 2026-09-07; gates remote climate roles. Strictly greater than, so exactly 150000 is rejected. Third of four floor literals, same once outside tests rule as the others.
LANE3_REMOTE_MODE = "live" as of 2026-09-07, since CLIMATE_REMOTE_FLOOR_USD now has a value. The dark path stays in code as the guard for a future unset, but it must not be the shipped behaviour. The relocation branch is independently "live" once TARGET_CITIES is non empty, gated by CLIMATE_RELOCATION_FLOOR_USD.
RAW_RETENTION_DAYS = 21                             # data/raw/<run_id> older than this is deleted by the cleanup stage; assumption
PAY_COMPARE = "midpoint"                            # midpoint of a stated range; "max" is the alternative. Assumption, brief silent.
FULL_TIME_HOURS_PER_WEEK = 40; WEEKS_PER_YEAR = 52  # assumed only for full time postings with no stated hours, and marked estimated
TARGET_CITIES = env list, default empty             # human item 5
RESIDENCE_COUNTRY = read from answer_bank["country_of_residence"]; used by the residency filter
STALE_DAYS = 45
SEED_QUERIES = {1: ["instructor", "adjunct", "online instructor"], 2: ["analyst", "data analyst", "data", "reporting", "business intelligence"]}
DEEP_QUOTA = {1: 10, 2: 10, 3: 5}; MAX_TRIAGE_PER_RUN = 400; MAX_DEEP_PER_RUN = 25; MAX_REPUTATION_PER_RUN = 15
MAX_APPLICATIONS_PER_RUN = 8
MAX_SUBMISSIONS_PER_DAY = 5                         # checked before every send; assumption, brief gives the name not the number
APPLICATION_COOLDOWN_DAYS = 90                      # dedupe window on company plus normalized title; assumption
MAX_MODEL_CALLS_PER_RUN = {"tier1": 450, "tier2": 60}   # per tier, checked before every batch; assumption, sized under the 1,000 a day free tier limit
FREE_TIER_PROVIDER = env, "groq" or "gemini", required   # tier 1 only; verify its live limits in Phase 3
DRY_RUN = env JOBENGINE_DRY_RUN != "false"          # default on
STOP_FILE = data/STOP
BROWSER_LOCK_FILE = ~/.automation-locks/browser.lock   # shared with Prospector
RUN_LOCK_FILE = data/run.lock
MAX_REPORT_MATCHES = 10; HEADER_MAX_CHARS = 3500
QUIET_DAYS = 10                                     # quiet past threshold flag; assumption
APPLY_THRESHOLD = 70; QUEUE_THRESHOLD = 60; REPORT_THRESHOLD = 50
W_LANE = 0.45; W_AUTO = 0.35; W_PAY = 0.20
TRACE_DROP_RATIO = 0.30                             # more than this share of sentences dropped means the document is gutted
RATING_EXAMPLES = 20                                # arbitrary start per the brief, tune later
REPUTATION_TTL_DAYS = 30
REPUTATION_PERMITTED_HOSTS = ("<company domain>", "en.wikipedia.org", "news.google.com redirect targets that are publisher pages")
CORPUS_DENY_TERMS = ("citizenship", "naturalization", "naturalisation", "ancestry", "heritage", "temple records", "market timing", "backtest")
DENYLIST_HOSTS = ("linkedin.com", "lnkd.in", "indeed.com")   # host == x or host endswith "." + x, every hop, every stage, every via
TIER1_MODEL = env, provider specific   # no Anthropic model ids anywhere; tier 2 is Claude Code itself, not a model id
RUN_HOUR = 7; RUN_MINUTE = 0; MISFIRE_GRACE_SECONDS = 6 * 3600
DEFAULT_TIMEZONE = env, required, no default; config raises at import when blank
JOBENGINE_CDP_PORT = env, default 9333; JOBENGINE_CHROME_PROFILE_DIR = ~/Library/Application Support/Google/Chrome/JobEngine-Profile
JOBENGINE_TELEGRAM_BOT_TOKEN, JOBENGINE_TELEGRAM_CHAT_ID  (never TELEGRAM_BOT_TOKEN)
JOBENGINE_TIER1_API_KEY
ADZUNA_APP_ID, ADZUNA_APP_KEY                       (blank = source skipped)
JOBHUNT_IMAP_HOST, JOBHUNT_IMAP_USER, JOBHUNT_IMAP_PASSWORD, JOBHUNT_EMAIL   (blank = mail stage off, decommission trigger suspended)
RESUME_FILE_PATH                                    (human item 1)
```

`data/profile.yaml` (blank in the example; `profile.load()` raises on blank `first_name`, `last_name`, `email`, `phone`, `RESUME_FILE_PATH`): `first_name, last_name, email, phone, location_text, linkedin_url (a text value only, never automated), website, lane_summary_for_prompt`.

`data/answer_bank.yaml` (blank in the example; legally attested answers Alex writes himself): `work_authorization_us, work_authorization_other, country_of_residence, willing_to_relocate, salary_expectation_monthly_usd, salary_expectation_annual_usd, previous_employers (list), notice_period, references (list), eeo_gender, eeo_race, eeo_veteran, eeo_disability, how_did_you_hear, preferred_name, pronouns`. Missing key means unmapped, never a default.

`data/corpus_allowlist.txt`: absolute file paths, one per line. The loader rejects directories, globs, relative paths and any path under a name matching a deny term. `corpus.py` indexes every line as `(file, line_no, text)`.

Lock protocol (shared with Prospector): `~/.automation-locks/browser.lock` holds JSON `{"holder": "job-engine"|"prospector", "pid": N, "since": iso}`. A holder is live when its pid is alive; a dead pid is stale and cleared with a `stale_lock_cleared` degradation (not disqualifying). Job engine holds it only while a browser session is open (climate readers, DOM form introspection, submission), acquired inside `browser.session()` and released when the session closes, so API only stages never block Prospector and a Prospector session never blocks ingest, triage or the report. Exclusivity between two job engine runs is the separate `RUN_LOCK_FILE`. The brief's phrase "refuse to start" is served at the stage level: with Prospector holding the lock the morning is disqualified either way, but the API stages and the degraded report still run, which acceptance 1b requires. Prospector must write its record at session start and remove it at session end; that is a one line addition to `hi-im-alex-outreach/prospects/RESUME-prospector.md`, outside this repo, and the lead should schedule it. Per the brief, Prospector pauses through day 14 either way.

## 4. Phases

Day 0 is when the pre build gates clear (resume plus corpus allowlist, funded API key, Telegram token, the Mac awake decision). Phases 0 and 2 need none of them and can be pulled earlier; Phase 3 needs the key; Phase 5 needs the resume; live sends need the pre live gates (phone, lane 2 floor confirmation, ATS terms check, answer bank, Alex turning `DRY_RUN` off). Until those clear the system runs in dry run and every check that needs a live send is reported as deferred, never passed.

Highest risk first: the dedicated Chrome and a filled ATS form (day 1), ingestion with terms gating and count capture (day 2), scoring with the caps and guards (day 3), bot and report with degradation rows (day 4, the minimum loop is live), writer with the trace gate and answer bank plus the six controls in dry run (day 5), adapters, mail and the first live send once Alex flips the switch (day 6), climate boards, schedule and the window checks (day 7).

### Phase 0, day 1 morning: skeleton, locks, preflight, controls scaffolding

Goal: the exact scheduled command runs with stub stages, writes `runs`, `reports` and `degradations`, and a header lands on Telegram even when the lock is held or Chrome is down.
Files: `README.md`, `requirements.txt`, `.env.example`, `.gitignore`, `bin/*`, `config.py`, `db.py`, `types.py`, `http.py`, `locks.py`, `runs.py`, `daily.py` (stages as no ops), `report.py` (`send_message()` plus a header with degradation lines), `tests/conftest.py`, `tests/test_floors.py` (literal count and boundary cases against `pay.floor_check` stub), `tests/test_lock.py`, `tests/test_no_linkedin_indeed.py` (static half), `scripts/check_preflight.py`.
Needs: Telegram token and chat id; the existing `/opt/homebrew/bin/python3.11`.
Seam: `daily.py` runs in two halves, because tier 2 is Claude Code and not an in process call. Half A is `preflight -> ingest -> prefilter -> triage`, tier 0 and tier 1 only. Half B is `submit -> mail -> report -> cleanup`. Between them the Claude Code routine does the deep scoring and the writing and hands results back through `deep.record()` and `writer.record()`; see Phase 3b. `bin/run-daily.sh` takes `--stages` and `--run-id`, and the routine invokes both halves. Across the morning the full ordering is `preflight -> ingest -> prefilter -> triage -> [Claude Code: deep, write] -> submit -> mail -> report -> cleanup`, where cleanup deletes `data/raw/<run_id>` directories older than `RAW_RETENTION_DAYS` so day 14's check can still re parse day 8. Preflight first takes `RUN_LOCK_FILE`; if another job engine run holds it, it writes a `runs` row with status `locked`, sends a one line report naming it, and exits 3. It then peeks at the shared browser lock without taking it: a live Prospector holder is recorded as a `lock_refused` degradation (disqualifying), every browser stage is marked `ran=false`, the API stages run, and the degraded report goes out with exit 2. Browser stages take the shared lock inside `browser.session()` and degrade `lock_refused` if it is held by then. It then calls `browser.ensure_chrome()`; if the port never answers, the browser dependent stages are marked `ran=false` with a `browser_unavailable` degradation (disqualifying) and every API stage still runs. Each stage is wrapped; an exception becomes `ran=true, ok=false` with a `source_error` or `browser_stage_error` degradation. A stage that runs and finds zero items is `ran=true, ok=true, counts={...:0}` and never degrades. `bin/run-daily.sh` exports `JOBENGINE_TRIGGER_COMMAND="$0 $*"` and `JOBENGINE_STARTED_BY` (default `manual`).
Pass: `bin/run-daily.sh` exits 0, `sqlite3 data/job_engine.db "select status, started_by, trigger_command, dry_run from runs order by id desc limit 1"` prints `ok|manual|bin/run-daily.sh...|1`, the header appears on the phone with a `DRY RUN` banner; `.venv/bin/python scripts/check_preflight.py --scenario lock_held` (writes a prospector lock record with a live `sleep` pid, runs the command) shows exit 2, a `degradations` row `lock_refused, disqualifying=1` naming `prospector`, ingest API stubs marked ran, and a report row with `qualifying=0`; `--scenario chrome_down` shows exit 2, a `browser_unavailable` row, and ingest stubs marked ran; `pytest tests/test_floors.py tests/test_lock.py -q` passes; `grep -rnE "\b(2000|60000|150000|212900)\b|2,000|60,000|150,000|212,900|150_000|212_900" job_engine/ scripts/ bin/ README.md .env.example` prints exactly four lines, all in `job_engine/config.py`.

### Phase 1, day 1 afternoon: the dedicated browser spike

Goal: Playwright 1.62 attaches to a Chrome launched by `bin/chrome.sh` on port 9333 with a fresh profile, the cookie assertion runs, our own tab fills a live Greenhouse form up to the submit button, and a PDF renders.
Files: `browser.py`, `bin/chrome.sh`, `ats/base.py`, `ats/greenhouse.py` (form_spec via `?questions=true`, DOM fill, no submit yet), `render.py`, `profile.py`, `corpus.py`, `data/*.example.*`, `scripts/check_profile_cookies.py`, `tests/test_corpus_allowlist.py`, `tests/test_ats_formspec.py` (Greenhouse fixture).
Seam: `bin/chrome.sh` runs the Chrome binary with `--remote-debugging-port=$JOBENGINE_CDP_PORT --user-data-dir="$JOBENGINE_CHROME_PROFILE_DIR" --no-first-run --no-default-browser-check`, detached with nohup. `browser.session()` takes the shared browser lock, calls `ensure_chrome()`, `connect_over_cdp("http://127.0.0.1:{port}")`, uses `browser.contexts[0]`, then `assert_no_linkedin_cookies(context)` (`context.cookies()` filtered on domain containing `linkedin.com`; any hit raises and the stage degrades `linkedin_cookies_present`, disqualifying). Tabs we open are tracked and closed; `context.route("**/*")` aborts denylisted hosts; `page.on("request")` logs hosts with the stage. `corpus.load()` reads only the allowlist paths, refuses directories and globs, and `corpus.probe()` scans for `CORPUS_DENY_TERMS`.
Pass (sandbox disabled): `.venv/bin/python -m job_engine.browser --smoke` starts Chrome if needed, prints the cookie assertion result, screenshots a Greenhouse posting to `data/screenshots/smoke.png`, closes its tab, exits 0; `select host from outbound_hosts where via='browser'` has no denylisted host; `.venv/bin/python scripts/check_profile_cookies.py` prints `linkedin cookies: 0`; `.venv/bin/python -m job_engine.ats.greenhouse --fill <job_url>` fills name, email, phone and the resume file and stops on the submit button with a screenshot; `.venv/bin/python -m job_engine.render --smoke` writes a PDF that `pypdf` reads back containing `SMOKE`; `pytest tests/test_corpus_allowlist.py -q` passes (a directory on the allowlist raises; a file not on the allowlist next to one that is is never opened, proven with a sentinel string; `profile.py` and `corpus.py` contain no `glob`, `os.walk`, `rglob`).

### Phase 3b, day 4: the tier 2 Claude Code routine

This phase exists because tier 2 is the half of the system that does all the judgment work, and an earlier revision asserted it without designing it.

Goal: a scheduled Claude Code routine drives the morning end to end, calling half A, doing the deep scoring and the writing itself as the model, handing results back through the repo, then calling half B. A morning completes with real deep decisions and at least one written document, with no API key anywhere.

Files: `ROUTINE.md` (the routine's own instructions, checked into the repo), `job_engine/handoff.py` (`DeepTask`, `DeepResult`, `WriteTask`, `WriteResult`, the JSON encode and decode, and the schema validation both directions), `deep.py` and `writer.py` refactored from `run`/`write` to `pending`/`record`, `bin/tier2-tasks.sh` and `bin/tier2-record.sh` as the two thin CLI surfaces the routine calls, `tests/test_handoff_schema.py`, `tests/test_tier2_guard.py`.

Why a CLI surface rather than the routine importing Python: it keeps the seam narrow and inspectable, it means the routine never holds repo state between calls, and it makes the handoff testable without Claude Code in the loop by piping fixture JSON through the same two commands.

Seam: `bin/tier2-tasks.sh --kind deep --run-id N` prints a JSON array of `DeepTask` to stdout; the routine reads it, scores each posting against the Phase 3 rubric, and pipes a JSON array of `DeepResult` into `bin/tier2-record.sh --kind deep --run-id N`. Same shape for `--kind write`. Both directions validate against the schema in `handoff.py` and exit non zero on a mismatch rather than storing a partial result. `pending()` runs `corpus.probe()` over every field before printing and raises `PromptContentBlocked` on a deny term, which is the tier 2 half of acceptance 12. `record()` enforces `MAX_MODEL_CALLS_PER_RUN['tier2']`, increments `runs.tier2_calls`, and for writes runs the trace gate in code before storing, so the fabrication gate does not depend on the model having behaved.

Scheduling: the routine runs locally in Claude Code on Alex's Mac, not in the cloud, because half B's submit stage needs the local Chrome on port 9333. This is the answer to the brief's question about which stages move: none of them. The Mac awake item therefore still gates, exactly as the brief says.

Failure behaviour: if the routine never runs, half A has still stored postings and half B can still send a report, which reports zero new matches and records a `tier2_absent` degradation, disqualifying. The morning fails honestly rather than looking empty.

Pass: `.venv/bin/python -m pytest tests/test_handoff_schema.py tests/test_tier2_guard.py -q` passes; `bin/tier2-tasks.sh --kind deep --run-id N | bin/tier2-record.sh --kind deep --run-id N --echo-fixture` round trips fixture data and writes `deep_decisions` rows with `runs.tier2_calls` incremented; a task carrying a `CORPUS_DENY_TERMS` string causes `tier2-tasks.sh` to exit non zero and print nothing; a `WriteResult` whose claims fail the trace gate is refused by `record()` with nothing stored; and one real morning run driven by the routine produces at least one `deep_decisions` row and one rendered document, with `select tier1_calls, tier2_calls from runs` showing both non zero.

### Phase 2, day 2: sources with terms gating, ingest with count capture, filters, pay normalization

Goal: every allowed source lands real postings, raw bodies are saved and counted, dedupe keys and pay figures are computed, the residency and remote filters run, and no request touches the denylist.
Files: `sources/*` (all API sources plus the four lane 1 sources), `ats_detect.py`, `ingest.py`, `filters.py`, `dedupe.py`, `pay.py`, `scripts/seed_boards.py`, `data/districts.seed.txt`, tests `test_sources_parse.py`, `test_terms_gate.py`, `test_ats_detect.py`, `test_ingest_counts.py`, `test_dedupe.py`, `test_filters.py`, `test_residency_filter.py`, `test_floors.py` (full).
Terms check step, done first and written into the registry and the README table (source, terms URL, verdict, checked on, note): the builder reads each source's terms of use in the job engine Chrome and records `allowed` or `forbidden`. Findings on 7 September 2026 that shape expectations: HigherEdJobs robots allows all but click through paths; EDJOIN and CCC Registry robots allow all; CCC Registry's jobs page redirects to a JavaScript lander, so expect account gating; climatebase.org answered a plain robots request with 403, the signature of an edge gated product; ClimateTechList and Work on Climate robots allow all. A `forbidden` verdict removes the source and its listings are reached through employer ATS boards instead. Adzuna's free tier limit is read from Adzuna's own documentation and written into the README; the source is capped at 3 calls a run regardless.
Seam: `ingest.run()` iterates `sources.enabled()` in order: aggregators, lane 1 boards, climate boards (Phase 7), then ATS boards for companies with `ats_kind`. Every fetched body goes through `http.save_raw()`; the parser's count is written to `raw_responses.parsed_count`. `upsert()` keys on `(source, source_id)`, fills `title_norm` and `dedupe_key`, marks cross board duplicates with `duplicate_of` (ATS native preferred as canonical), runs `pay.parse_salary`, `pay.parse_hours`, `pay.normalize` and writes the pay and hours columns. `ats_detect.apply_surface()` sets `companies.apply_surface`: `ats` for the five adapters' hosts, `account_required` for HigherEdJobs, EDJOIN, CCC Registry, GovernmentJobs/NEOGOV, PeopleAdmin and district portals, `unknown` otherwise. `filters.prefilter()` drops `not_remote`, `stale`, `denylisted_host` (any hop), `duplicate`; it also detects residency requirements (patterns such as `must reside in`, `US based only`, `located in the United States`, `residents of`) and stores `residency_required` and `residency_country` without dropping, because the lane and the relocation exemption are decided later. It never matches on work authorization phrases.
`pay.normalize` rules, exactly as the brief states them: figures are compared unrounded in the floor's native unit (monthly for lane 1, annual for lanes 2 and 3). Monthly quoted: monthly as is, annual = monthly times 12. Annual quoted: annual as is, monthly = annual over 12. Hourly quoted with stated hours: monthly = hourly times hours times `WEEKS_PER_YEAR` over 12, annual likewise. Hourly quoted, hours unstated, full time posting: assume `FULL_TIME_HOURS_PER_WEEK`, mark `estimated`. Hourly quoted, hours unstated, part time posting: no monthly or annual figure, `hours_unknown` stays set, `effective_hourly_usd` is the stated rate. Effective hourly for monthly or annual quotes = monthly over (hours times 52 over 12) when hours are stated, else unknown. Non USD: unknown, no conversion table invented. `floor_check` compares `compared_value > floor`, never `>=`; a posting quoting pay in the floor's own unit is compared whether or not hours are stated, so `$1,500 a month, hours unspecified` in lane 1 is `fail`, never `unknown`.
Pass: `bin/run-daily.sh --stages ingest,prefilter` exits 0; `select source, count(*) from jobs where last_seen_run_id=<id> group by source` shows every allowed reachable source with at least 1 row; `.venv/bin/python -m pytest tests/test_ingest_counts.py -q` re parses each saved body and asserts parsed count equals inserted plus updated plus rows marked `duplicate_of` for that source and run, the per source stats `ingest.run()` returns, because cross board duplicates collapse into one `jobs` row; `pytest tests/test_terms_gate.py tests/test_dedupe.py tests/test_filters.py tests/test_residency_filter.py tests/test_floors.py -q` passes with these named cases: climate 50,000 fail; part time 2,001 a month pass and 2,000 fail; cash 60,001 pass and 60,000 fail; climate `CLIMATE_RELOCATION_FLOOR_USD` fail and `CLIMATE_RELOCATION_FLOOR_USD + 1` pass; part time 1,500 a month with no hours is `fail` and never `unknown`; `$30 an hour, 40 hours`, `$5,200 a month` and `$62,400 a year` all normalize to monthly 5200.0; a part time hourly posting with no hours carries `hours_unknown=1` and no monthly figure; a posting saying `must reside in the United States` is flagged and a posting saying `must be authorized to work in the US` is not; two postings for the same company and normalized title from Remotive and Greenhouse share one `dedupe_key`; `.venv/bin/python scripts/outbound_hosts.py --run-id <id>` exits 0.

### Phase 3, day 3: scoring with caps and guards, ratings loop, company notes with quotes

Goal: tier 1 triage, tier 2 deep score, hours aware desirability, deterministic decisions with lane 3 live on both branches, ratings fed back, company notes where every claim carries a verbatim quote.
Files: `llm.py`, `prompts/*.md` (except writer), `ratings.py`, `triage.py`, `deep.py`, `reputation.py`, tests `test_triage_parse.py`, `test_decision_rules.py`, `test_ratings_loop.py`, `test_call_cap.py`, `test_reputation_quotes.py`.
Seam: `llm.call()` first checks `runs.tier1_calls + 1 <= MAX_MODEL_CALLS_PER_RUN['tier1']` and raises `CallCapReached`; the calling stage catches it, records a `call_cap` degradation (not disqualifying), and continues with what it already scored. It then runs `corpus.probe()` over every system block and the user content and raises `PromptContentBlocked` on any deny term (this is the by content probe of acceptance 12). Tier 1 uses the chosen provider's own structured output or JSON mode, validated against the schema in code because free tier models honour schemas less reliably than Claude; a response that fails validation is retried once then counted as unscored rather than guessed at. There is no prompt caching to tune and no `count_tokens` step, because the paid Anthropic path is gone. Tier 2 deep scoring and writing are performed by Claude Code against `deep.py` and `writer.py` as tools rather than by an API call from this repo. Shortlist: `lane != 0 and lane_confidence >= 0.6 and pay_status != 'fail'`, filled per lane by `DEEP_QUOTA`: two thirds of each lane's slots from known pay postings ordered by `adjusted_hourly_usd desc`, one third from unknown pay postings ordered by `automation_potential desc`, unused slots rolling across lanes, so unknown pay postings (which the cash lanes may auto submit) are not starved by a null sort. The split is an assumption. `deep.run()` skips lane 3 only if `CLIMATE_REMOTE_FLOOR_USD` were ever unset, storing those postings with `decision='dark'` and recording `lane3_dark_floor_open` (not disqualifying) once per run. That path is a guard, not the shipped behaviour: the floor is set to 150000 as of 2026-09-07, so lane 3 runs normally and a dark lane 3 in a real run means a config regression. `reputation.ensure()` fetches only permitted hosts (company site root and about page, Wikipedia REST summary, publisher pages reached from Google News RSS links after following redirects), passes fetched page text and never RSS titles or snippets to the model, and after the call verifies each signal's `quote` appears verbatim (whitespace normalized) in the fetched text of its `source_url`; unverified signals are dropped in code. Application rows: `apply` with `apply_surface='ats'` becomes `approved_auto`; `apply` or `queue` with `account_required` or no adapter becomes `manual` with kind `manual_account_required` or `manual_no_adapter`; lane 3 `queue` becomes `queued` with kind `climate`. `dedupe.blocked()` and the unique job index are checked before any row is created. Lane 2 auto submission is additionally gated on `LANE2_FLOOR_CONFIRMED` being true in config, which is human item 6: the $60,000 cash lane floor overrides the rule Alex wrote in his own words, so until he confirms it, lane 2 matches are created as `queued` rather than `approved_auto`, with a `lane2_floor_unconfirmed` degradation, not disqualifying. This is a gate in `decide()`, not a string in a report.
Decision rules, pure function:

```
if lane == 0: skip
if lane == 3 and LANE3_REMOTE_MODE is dark: dark, floor_open   # guard only; not reachable now that the floor is set
if pay.status == 'fail': skip, pay_below_floor
if residency.reason == 'residency_required' and not (lane == 3 and in_target_city): skip, residency_required
if hard_red_flag: report, red_flag
lanes 1 and 2:
    if remote_flag is False: skip, not_remote
    if overall >= APPLY_THRESHOLD: apply          (pay unknown and hours unknown both allowed)
    elif overall >= REPORT_THRESHOLD: report
    else: skip
lane 3:
    if remote_flag is False and not (pay.status == 'pass' and in_target_city): skip, not_remote
    if pay.status == 'unknown' or hours_unknown: queue, climate_unknown   (regardless of overall)
    if overall >= QUEUE_THRESHOLD: queue
    elif overall >= REPORT_THRESHOLD: report
    else: skip
```

Reading of "regardless of score" for climate unknown pay or hours: any climate posting that reaches deep scoring with either unknown lands in the queue whatever its overall. Reaching deep scoring is the gate, the brief's wording is "reaches scoring". Stated as the plan's reading. `in_target_city` is True only when `remote_flag is False` and `location_text` matches `TARGET_CITIES`; a remote lane 3 posting that requires residence in a country other than Alex's is dropped exactly like the cash lanes, because the exemption is the relocation branch only.
Pass: `pytest tests/test_decision_rules.py tests/test_triage_parse.py tests/test_ratings_loop.py tests/test_call_cap.py tests/test_reputation_quotes.py -q` passes: no salary reaches scoring as `unknown`; cash lane unknown pay with overall 80 is `apply`; cash lane hours unknown with overall 80 is `apply`; climate unknown pay with overall 20 is `queue`; climate hours unknown is `queue`; climate known pay above floor is `queue` never `apply`; lane 3 with scope unset is `dark`; a fake tier 1 client against `MAX_MODEL_CALLS_PER_RUN['tier1']=2` gets exactly two calls, a `call_cap` degradation row, and the run still completes. Live: `bin/run-daily.sh --stages ingest,prefilter,triage,deep` exits 0, `select decision, count(*) from scores where run_id=<id> and stage='deep' group by decision` shows rows, `select cache_read_tokens from prompt_log where run_id=<id> and stage='triage' order by id limit 5` is nonzero from the second row. Ratings: `ratings.record(<job_id>, 0, None)` then `.venv/bin/python -m job_engine.triage --dump-prompt --job-id <other>` prints that title under `NOT GOOD (rated by Alex)`. Stop condition from the brief: if the automation potential score proves unworkable here, stop and say so rather than finishing the repo.

### Phase 4, day 4: bot, report, approvals, degradation rows

Goal: the minimum loop is live: counts plus top N matches with rating buttons, approvals stored in SQLite overnight, own token polling, JobQueue firing the exact command, every degradation named in the report.
Files: `bot.py`, `report.py` (full), `approvals.py`, `scripts/check_report.py`, `tests/test_report_roundtrip.py`.
Seam: `report.send()` composes a header under `HEADER_MAX_CHARS`: date, `DRY RUN` banner when on, counts (tier 1 and tier 2 calls used, ingested new, passed filters, new matches by lane, shown), submitted with proof breakdown, awaiting approval, replies new and running total (or `reply tracking off, decommission trigger suspended` when inbox access is absent), API spend, lane 3 status (`dark: floor decision open` when unset), one line per degradation naming the stage and reason and whether it disqualifies the morning, and the fixed line `Company notes quote public pages with a link for every claim. No Glassdoor, Blind, Comparably or Levels.fyi ratings: none offers a free legal API.` Then one message per match up to `MAX_REPORT_MATCHES`, ordered by lane then adjusted hourly, each with title link, company, lane, overall, pay in the floor's unit with `est.` when estimated, hours or `hours unknown`, effective hourly or unknown, status, and buttons `👍 good` and `👎 not good` (`callback_data="rate:{job_id}:1|0"`); one message per new pending approval with `✅ Apply` and `⏭ Skip` (`callback_data="appr:{pending_id}:a|s"`); one message for new replies and quiet applications when there are any. Every message writes `report_lines` with `telegram_message_id`; 1.1 second sleep between sends; `html.escape()` on every title and company. `reports.new_matches` is the count of deep decisions in (`apply`, `queue`, `report`) this run; `qualifying = new_matches >= 1 and no degradation with disqualifying=1`. Header shape follows `jarvis/news.py:198` and `jarvis/pandemic.py:177`.
`bot.py`: `Application.builder().token(JOBENGINE_TELEGRAM_BOT_TOKEN)`, `run_polling(drop_pending_updates=False)`; callbacks write `ratings` or `pending_approvals` at once and edit the message; `/ping` replies `pong`; `/status` prints the last run and report rows; `/run` spawns `bin/run-daily.sh` with `JOBENGINE_STARTED_BY=manual`; `/stop` creates `data/STOP`; `job_queue.run_daily(time=time(RUN_HOUR, RUN_MINUTE, tzinfo=ZoneInfo(TZ)), job_kwargs={"misfire_grace_time": MISFIRE_GRACE_SECONDS})` spawns `bin/run-daily.sh` with `JOBENGINE_STARTED_BY=schedule` via `asyncio.create_subprocess_exec`; on `post_init` it calls `browser.ensure_chrome()` and, if past the run time with no `runs` row today from `schedule` or `catchup`, spawns once with `catchup`. Approve sets `approved_manual` and `approved_at`; submission lands in Phase 5.
"Passes the filters" for acceptance 2 is this plan's reading: a job passes when it has a deep decision in (`apply`, `queue`, `report`) this run; the prefilter count is a separate header number. The forward set also includes applications with `updated_at` later than the previous run's `report_sent_at` and replies with `reported_run_id` equal to this run.
Pass: `bin/start.sh` (Alex's terminal or sandbox disabled) then `/ping` gets `pong`, a message to JARVIS still gets a reply, `grep -c Conflict ~/Library/Logs/job-engine.log` prints 0 and the Railway log search for `Conflict` on the JARVIS service shows 0 hits; `/run` produces a report; tapping `👎` inserts a `ratings` row; tapping `✅` sets `decision='approve'` and status `approved_manual`; `.venv/bin/python scripts/check_report.py --run-id <id>` prints three lines `sources: parsed N handled N`, `counts: report claims M db has M`, `lines: K/K trace to rows` and exits 0; `pytest tests/test_report_roundtrip.py -q` passes.

### Phase 5, day 5: writer, trace gate, answer bank, the six controls, submission in dry run

Goal: custom resume and cover letter from the corpus behind a code enforced trace gate, answers only from the answer bank, payload captured before send, and every control proven, all in dry run.
Files: `writer.py`, `trace.py`, `answer_bank.py`, `prompts/writer.md`, `submit.py`, `ats/greenhouse.py` (submit), `ats/lever.py`, tests `test_trace_gate.py`, `test_answer_bank.py`, `test_submission_controls.py`, `scripts/check_submission_proof.py`.
Seam: the tier 2 routine produces, per `WriteTask`, `resume_md`, `cover_letter_md`, free text answers and `claims` where each claim cites `source_file` and `source_line` from the corpus index supplied in the prompt. `trace.gate()` is code: layer one verifies each claim's employer, title, dates, degree, licence, tool or metric tokens against the cited line plus or minus two lines; layer two extracts every capitalized token, acronym, number with a unit or percent, and every item in a skills or tools list from the documents and requires it to occur in `corpus.text()` case insensitively (a small stoplist handles sentence initial capitals); any sentence failing either layer is dropped; when more than `TRACE_DROP_RATIO` of sentences drop or a required section empties, `TraceGutted` routes the application to the queue as `manual_trace`. `answer_bank.answer()` maps each `FormField` by label patterns to a bank key; booleans and selects come only from the bank; free text questions may go to the writer; any required field with no mapping raises `UnansweredRequired`, kind `manual_unanswered`. `submit.one()` runs in this order and nothing else: check the adapter's `submit_verdict` and route anything not `allowed` to the approval queue as `manual_terms_unchecked` or `manual_terms_forbidden`; write `payload_json` and `payload_captured_at` and commit; check `STOP_FILE` (present: status `halted`, reason `stop_file`, degradation `stop_file`); check `MAX_SUBMISSIONS_PER_DAY` against `count(*) where submitted_at >= today` (reached: `halted`, reason `daily_cap`); check `DRY_RUN` (on: status `dry_run`, `send_mode='dry_run'`, return without opening the apply page; the payload, the rendered PDF and the cover letter were already written and committed by the first step, so dry run rows carry every artifact); take the browser lock; send; save evidence. Confirmation markers: Greenhouse `/confirmation` in the URL or `Thank you for applying`; Lever `/thanks`; a reCAPTCHA or hCaptcha iframe means `challenged` with kind `manual_challenge`; an account wall means `manual_account_required`. `run_pending()` processes `approved_auto` and `approved_manual` rows up to `MAX_APPLICATIONS_PER_RUN`. The bot's approve handler spawns `.venv/bin/python -m job_engine.submit --application-id N` when the lock is free.
Pass: `pytest tests/test_trace_gate.py tests/test_answer_bank.py tests/test_submission_controls.py -q` passes with these named cases: a corpus without Python or Kubernetes and a fake model that writes both (and a variant told to be persuasive) yields documents containing neither; a claim citing a line that does not contain the employer is dropped; a form with a required `Do you require sponsorship` field and a bank without `work_authorization_us` raises and queues, and no value is written; DRY_RUN on produces `payload_json`, `resume_pdf_path` and status `dry_run` with zero `outbound_hosts` rows for stage `submit`; a cap of 1 halts the second send with reason `daily_cap`; creating `data/STOP` between two sends halts the second with reason `stop_file`; a fake adapter that raises `SystemExit` after capture leaves a row with full payload and no `submitted_at`; two postings from different boards with one `dedupe_key` create one application and a second attempt inside the cooldown is blocked. Live (dry run, sandbox disabled): `bin/run-daily.sh --stages write,submit` produces at least one application with status `dry_run`, a PDF on disk and `payload_json` holding every form value; Alex reads that output (human item 10).

### Phase 6, day 6: remaining adapters, inbox, first live send when Alex flips the switch

Goal: Ashby, SmartRecruiters and Recruitee adapters; read only reply tracking with quiet flags and the running reply count; the first confirmed live submission once `DRY_RUN` is off and the pre live gates have cleared.
Files: `ats/ashby.py`, `ats/smartrecruiters.py`, `ats/recruitee.py`, `mail.py`, `prompts/reply_classify.md`, fixtures, `tests/test_ats_formspec.py` (extend), `scripts/check_routing.py`.
Seam: every adapter and every lane 1 surface carries a `submit_verdict` record of `{verdict: "allowed" | "forbidden" | "unchecked", terms_url, checked_on}`, set from the human item 7 terms check and stored in `data/submit_terms.yaml`. This is deliberately separate from the `terms_verdict` that gates reading a source: reading a public job board and submitting an application through it are different acts, only the reading side is checked when sources are wired, and the submitting side is the one that gets Alex's real name blocklisted. `submit.one()` checks `submit_verdict` before the stop file, the daily cap and DRY_RUN, and anything not explicitly `allowed` routes to the approval queue as `manual_terms_unchecked` or `manual_terms_forbidden`. Note this is not the same failure as an account wall: `apply_surface` catches surfaces that need a login, while `submit_verdict` catches surfaces that permit anonymous applying but forbid doing it automatically. Beyond that, each adapter saves a fixture of its form on first contact and `form_spec()` is unit tested against it; each detects account walls and captchas. `mail.run()` reads IMAP UIDs above `meta.last_imap_uid`, stores `replies`, classifies with Haiku, matches by job title then sender domain then company name with a confidence; a `confirmation` matched at 0.8 or more sets `confirmation_reply_id` and `proof_kind` `email` or `both`; applications with `quiet_since` older than `QUIET_DAYS` and no reply are flagged in the report; `meta.replies_total` is the running count for the decommission trigger, suspended in the report while inbox access is absent. Nothing is ever sent to an employer from this module.
Pass: `pytest tests/test_ats_formspec.py -q` passes for all five adapters; with `DRY_RUN` off by Alex and the gates cleared, `bin/run-daily.sh` produces at least one `submitted_page` row with a screenshot showing the confirmation and, where inbox access exists, `bin/run-daily.sh --stages mail,report` on the following run marks it `proof_kind='both'`; `.venv/bin/python scripts/check_submission_proof.py --since <day 8>` exits 0 and prints `inbox access: present` or `inbox access: absent, page proof only`; `.venv/bin/python scripts/check_routing.py --since <day 8>` prints per lane `occurred` or `deferred: <reason>`.

### Phase 7, day 7: climate boards that passed terms, schedule, window checks, README

Goal: climate readers for boards whose terms allow it, the schedule installed and re verified after a full day, the definition of done checks scripted, README complete.
Files: `sources/climatebase.py`, `climatetechlist.py`, `terra.py`, `inclimate.py`, `workonclimate.py` (each only if `terms_verdict="allowed"`), `scripts/verify_schedule.py`, `scripts/verify_window.py`, `README.md` (final, with the source terms table).
Needs: the Mac awake decision, human item 13, settled before day 8; if `pmset` is chosen, Alex's administrator password is a second human action.
Seam: each reader takes the shared browser from `ingest.run()`, returns `RawPosting` rows, and raises nothing past its own `try`; a forbidden board is not built and its employers are reached through their ATS boards. Selectors are found on the day from a snapshot and stored as constants with a fixture; none is invented ahead.
Schedule: `bin/start.sh` from Alex's terminal, which also starts Chrome through `ensure_chrome()`; `pmset -g sched` today shows no wake event, so `sudo pmset repeat wakeorpoweron MTWRFSU 06:55:00` is offered to Alex as the only thing that opens a closed lid; `caffeinate -i` inside `bin/run-daily.sh` keeps the machine up during a run only.
Pass: `bin/run-daily.sh` full run exits 0 or 2 with the report on the phone and every degradation named; day 8 morning, at least 24 hours after `bin/start.sh`: `.venv/bin/python scripts/verify_schedule.py` exits 0 (a `runs` row dated today with `started_by='schedule'`, bot pid alive); day 14: `.venv/bin/python scripts/verify_window.py --start <day 8>` prints `qualifying mornings: q/7`, `confirmed submissions: n`, and exits 0 only when `q >= 5` and `n >= 1`.

Cut order if day 7 arrives with work left: (1) climate readers, lane 3 still fills from ATS and aggregator postings; (2) the rendered custom resume PDF, the original resume file goes in its place, the cover letter and the trace gate stay; (3) SmartRecruiters and Recruitee adapters, their jobs route to the queue as `manual_no_adapter`; (4) the mail stage, the report then says `reply tracking off`. Never cut: the six submission controls, the floors, lane routing, the approval queue, the ratings loop, the report with degradation rows, the own token, the own Chrome profile and cookie assertion, the denylist, the corpus allowlist, the trace gate, the answer bank, the residency filter.

## 5. Scoring rubrics as prompt specs

All prompts live in `job_engine/prompts/*.md`, stable text first purely for readability and diffing since there is no prompt cache to tune on either tier, every response validated against a JSON schema through structured outputs. Ratings block, newest first, `RATING_EXAMPLES` rows:

```
GOOD (rated by Alex)
* "{title}" at {company}, lane {lane}, {employment_type or 'type unknown'}, {hours_text or 'hours unknown'}, {salary_text or 'pay unknown'}: {first 200 chars of description}
NOT GOOD (rated by Alex)
* ...
```

### 5.1 Triage, tier 1, one call per posting

System: who Alex is (`lane_summary_for_prompt` or the brief's lane text with the two archetypes: an online community college astronomy instructor at about $3,000 a month for under five hours a week, and an analyst at $60,000 a year for about an hour a day), a 600 token corpus summary, the lane definitions, the automation rubric, `triage_examples.md`, the ratings block, output instructions.
User: title, company, location text, employment type, remote flag, hours text, salary text, first 3,000 chars of description.

Lane definitions:
```
LANE 1, part time remote, mostly automatable: part time or contract, fully remote, few hours a week, the listed work is mostly repeatable and tool driven so most of it could be scripted. Instructor, adjunct and online teaching roles belong here.
LANE 2, full time remote, automatable, check in only: full time, fully remote, the day to day is mostly repeatable and tool driven; one person could run it with about an hour a day of real attention. Analyst, data, reporting and business intelligence roles belong here.
LANE 3, climate full time, mission driven, high pay: full time, the company mission or the role itself is climate, energy transition, decarbonisation or sustainability.
LANE 0: none of the above.
```

Output schema:
```
{
  "lane": 0|1|2|3,
  "lane_confidence": 0.0 to 1.0,
  "automation_potential": 0 to 100,
  "remote": true|false|null,
  "hours_per_week": number|null,          only when the posting states it
  "salary": {"min": number|null, "max": number|null, "period": "year"|"month"|"hour"|null, "currency": string|null} | null,
  "residency_requirement": string|null,   verbatim phrase if the posting requires residence somewhere
  "disqualifiers": [string],
  "one_line": string (max 140 chars)
}
```
Post processing in code: `salary` and `hours_per_week` are used only when the regex parsers found nothing; `pay.floor_check()` runs in code; `lane_confidence` below 0.6 never shortlists.

### 5.2 Automation potential, used inside triage and deep

```
Split the listed responsibilities into two lists.
A, repeatable and tool driven: reporting, data entry and cleanup, scheduling, monitoring and alerts, templated content, grading with rubrics, CRM and spreadsheet upkeep, standard tickets, routine research, invoice and order processing, recurring outreach from lists, recorded or reusable lectures.
B, judgment, relationship, physical or presence bound: negotiating, managing people, on site duties, live synchronous teaching hours, novel analysis, executive stakeholder work, live sales calls, clinical or licensed work.
automation_potential is the share of a typical week that falls in A, 0 to 100. Return both lists as evidence.
```

### 5.3 Pay, hours and effective hourly, code not model

`pay.parse_salary()` and `pay.parse_hours()` are regex first (currency symbols and codes, `k` suffix, ranges, `per hour`, `/hr`, `per month`, `per year`, `annual`, and `N hours per week`, `N hrs/wk`, `N hours a week`). The model parses only when regex found nothing. Then `pay.normalize()` per the Phase 2 rules and `pay.floor_check()` per lane, strict greater than, native unit, unrounded. `pay.adjusted_hourly(figures, automation_potential) = effective_hourly_usd / max(0.2, 1 - automation_potential / 100)` is stored as `adjusted_hourly_usd`, used only to order the shortlist and the report and shown as `worth about $X an hour of real work`; it never touches a floor comparison. Floors: lane 1 `PARTTIME_FLOOR_USD_PER_MONTH` on the monthly figure; lane 2 `CASH_FULLTIME_FLOOR_USD` on the annual figure; lane 3 `CLIMATE_RELOCATION_FLOOR_USD` on the annual figure when scope is `whole_lane`, or on the relocation branch only with `CLIMATE_REMOTE_FLOOR_USD` on remote roles when scope is `relocation_only`.

### 5.4 Deep score, tier 2, one unit of work per shortlisted posting

System: full corpus, profile summary, lane definitions, automation rubric, ratings block, red flag list (pay to apply, MLM language, commission only, unpaid trial, crypto wallet requests), output instructions.
User: full description up to 10,000 chars, triage output, pay figures and floor result, hours, company note summary, form questions when known.
Output schema:
```
{
  "lane": 0|1|2|3,
  "lane_match": 0 to 100,
  "lane_reason": string,
  "automation_potential": 0 to 100,
  "automatable": [string],
  "manual": [string],
  "real_hours_estimate": number|null,      hours a week likely to stay manual, evidence in "manual"
  "fit_summary": string (2 sentences, grounded in the corpus),
  "red_flags": [{"text": string, "hard": true|false}],
  "one_line_for_report": string (max 140 chars)
}
```
Code computes `overall = round(W_LANE*lane_match + W_AUTO*automation_potential + W_PAY*pay_component)` with `pay_component` 100 pass, 60 unknown, 0 fail, then `decide()`.

### 5.5 Company reputation, tier 2, one unit of work per company per 30 days

Inputs, fetched through `http.get` from permitted hosts only: company site root and about page (first 3,000 chars of visible text each), Wikipedia REST summary (404 tolerated), and publisher article pages reached by following the links in Google News RSS results for `"{company}"` and `"{company}" layoffs OR lawsuit OR funding OR acquired OR fraud` (last 12 months). The model receives fetched page text with its URL, never RSS titles or search snippets.
Output schema:
```
{
  "summary": string (4 to 7 plain sentences; each factual sentence ends with the source url in brackets),
  "signals": [{"kind": "positive"|"negative"|"neutral", "text": string, "quote": string (verbatim from the page), "source_url": string, "date": string|null}],
  "facts": {"founded": {"value": string, "quote": string, "source_url": string}|null, "size_hint": {...}|null, "funding_hint": {...}|null, "hq": {...}|null},
  "confidence": "low"|"medium"|"high",
  "sources_used": [string]
}
```
Rules in the prompt: no numeric rating; no claim without a quote; when sources are thin say `little public information found`. Code drops any signal or fact whose quote is not found verbatim (whitespace normalized) in the fetched text of its `source_url`, and drops summary sentences whose bracketed URL was not fetched. The report prints the fixed line about Glassdoor, Blind, Comparably and Levels.fyi every day.

### 5.6 Writer, tier 2, one unit of work per application

System: the corpus as numbered lines with file names, profile, style rules (plain English, no dash characters, one page resume, claims only from the corpus, every claim cites a line).
User: job description, deep output, form questions with kinds.
Output schema:
```
{
  "resume_md": string,
  "cover_letter_md": string (max 250 words),
  "answers": [{"path": string, "value": string}],      free text questions only
  "claims": [{"text": string, "source_file": string, "source_line": number}]
}
```
`trace.gate()` then runs in code as in Phase 5. The prompt asking nicely is not the control; the gate is.

### 5.7 Reply classifier, tier 1, one call per new email

User: from, subject, first 1,000 chars. Output `{"kind": "confirmation"|"rejection"|"interview"|"info_request"|"other", "company_guess": string|null, "job_title_guess": string|null}`.

## 6. Capacity model, not a cost model

Revision 3 replaced the dollar model. There is no API spend, so the budget is measured in calls against free tier limits and in Claude Code subscription capacity that Alex also uses for everything else.

Assumed steady state day: about 1,200 postings ingested, most cut by tier 0 at zero cost, about 400 reaching tier 1, about 25 deep scored and 8 applications written at tier 2, plus 10 emails classified.

Tier 0, no model, unlimited. Every filter that can be code is code. This is the single biggest lever in the whole design, and any work moved from tier 1 down to tier 0 is free capacity.

Tier 1, roughly 410 calls a day against a ceiling that is currently UNKNOWN, because neither Groq nor Google publishes a verifiable free tier number without an account. Plan for the ceiling being low. Headroom cannot be assumed, and a heavy first day of 2,000 postings would breach it, so `MAX_MODEL_CALLS_PER_RUN["tier1"]` is set to 450 and the first run is deliberately capped lower. Rate limiting matters as much as the daily quota: at 15 requests a minute, 400 calls takes about 27 minutes of wall clock, so the stage must pace itself and not burst.

Tier 2, Claude Code, roughly 33 substantive units of work a day. These draw on the same subscription limits as Alex's own sessions, so the honest statement is that this competes with his other work rather than costing him money. Keeping tier 2 small is the entire reason tiers 0 and 1 exist.

The tier 1 ceiling is unverified and unverifiable without an account, which is why no number appears above. Read it from the provider console in Phase 3 and record it with the date. This is also why tier 0 matters more than first assumed: every posting cut by code is one that never tests an unknown limit. Free tiers change without notice, which is why tier 1 sits behind one interface.

What was removed and why it is worth remembering: the earlier revision priced this at about $2 a day and about $60 a month of Anthropic API usage, with the arithmetic verified against real rates of $1 and $5 per million for Haiku 4.5 and $2 and $10 for Sonnet 5. That is what the free tier design is saving, and it is also the fallback cost if Alex ever decides the free tiers are too constraining.

## 7. Acceptance checks as pass/fail tests

All commands run from `/Users/alexandercoffman/Dev/job-engine/`. Anything touching a local port runs with the Bash sandbox disabled or from Alex's terminal. Checks that need a live send are reported as `deferred: dry run` until Alex turns `DRY_RUN` off, never as passed.

1. Real entrypoint. `bin/run-daily.sh` (the string `bot.py` spawns). Pass: exit 0, `sqlite3 data/job_engine.db "select status, trigger_command from runs order by id desc limit 1"` prints `ok` and a command beginning `bin/run-daily.sh`, header on the phone. During the seven mornings the bar is the report arriving and the morning qualifying: exit 0, or exit 2 with only non disqualifying degradations, count; exit 1 or a disqualifying degradation is a non qualifying morning.

1b. Preflight fails loudly but partially. `.venv/bin/python scripts/check_preflight.py --scenario lock_held` and `--scenario chrome_down`. Pass: lock held by prospector gives exit 2, a `degradations` row `lock_refused, disqualifying=1` naming the holder, API stages `ran=true`, browser stages `ran=false`, a `reports` row with `qualifying=0`, and the degraded header on the phone naming the lock; chrome down gives exit 2, a `browser_unavailable` row, `stage_json` showing ingest API sources `ran=true` and browser sources `ran=false`, and the header naming the reason. A run that ends with no report row is a fail.

2. Both directions by count. `.venv/bin/python scripts/check_report.py --run-id <id>`. Pass: three lines, each equal: `sources: parsed N handled N` (each saved body under `data/raw/<run>/` re parsed by its source parser; the right hand N is inserted plus updated plus marked `duplicate_of` for that source and run, taken from `runs.stage_json`), `counts: report claims M db has M` (`reports.new_matches` equals deep decisions in apply, queue, report), `lines: K/K trace to rows` (every `report_lines` row of kind match, submitted, approval, reply, quiet resolves to an existing row); exit 0.

3. At least one confirmed submission. `.venv/bin/python scripts/check_submission_proof.py --since <day 8>`. Pass: prints `confirmed submissions: n` with `n >= 1`, each having `proof_kind` in (page, email, both) with a screenshot on disk or a matched confirmation reply; prints `inbox access: present` and reconciles every submission against a confirmation email, or `inbox access: absent, page proof only`; a `submitted_unconfirmed` row is listed as `unconfirmed, needs a look`; zero submissions is a fail, not a pass.

4. Floors. `.venv/bin/python -m pytest tests/test_floors.py tests/test_decision_rules.py -q` and `grep -rnE "\b(2000|60000|150000|212900)\b|2,000|60,000|150,000|212,900|150_000|212_900" job_engine/ scripts/ bin/ README.md .env.example`. Pass: the named cases in Phase 2 and Phase 3 are green (50,000 climate fail; 2,001 pass and 2,000 fail; 60,001 pass and 60,000 fail; `CLIMATE_RELOCATION_FLOOR_USD` fail and plus one pass; 1,500 a month no hours is fail and never auto submits; hourly, monthly and annual for the same pay give one monthly figure; part time no hours carries `hours_unknown` and no converted figure; no salary reaches scoring as unknown; cash lane unknown may apply; climate unknown queues), and the grep prints exactly four lines, all in `job_engine/config.py`.

4b. Ratings loop. `pytest tests/test_ratings_loop.py -q`; live: tap `👎`, `sqlite3 data/job_engine.db "select job_id, rating from ratings order by id desc limit 1"` shows it, `.venv/bin/python -m job_engine.triage --dump-prompt --job-id <other>` prints the title under `NOT GOOD (rated by Alex)`, and next morning `select count(*) from prompt_log where run_id=<next> and stage='triage' and prompt_text like '%<title>%'` is above 0.

4c. Own token. `bin/start.sh`; `/ping` gets `pong`; a JARVIS message still gets a reply; `grep -c Conflict ~/Library/Logs/job-engine.log` prints 0; the Railway log viewer for JARVIS shows 0 `Conflict` hits over the same hour; `grep -rn "TELEGRAM_BOT_TOKEN" job_engine/` matches only `JOBENGINE_TELEGRAM_BOT_TOKEN`.

5. Lane routing by occurrence. `.venv/bin/python scripts/check_routing.py --since <day 8>`. Pass: prints `lane 1 or 2 auto: occurred (application <id>, status submitted_*)` with no approval row of kind `climate` on it, or `deferred: <reason>` where the reason is `dry run`, `no surface permits automated submission`, or `lane 2 floor unconfirmed`; prints `lane 3: occurred (queued, sent only after approve)` with `select count(*) from applications where lane=3 and status like 'submitted%' and approved_at is null` equal to 0, or `deferred: floor decision open` while `CLIMATE_FLOOR_SCOPE` is unset. Deferred is printed, never counted as passed.

6. Zero requests to LinkedIn or Indeed, and no cookies. `pytest tests/test_no_linkedin_indeed.py -q` (the guard raises on any hop, the browser route aborts, and `grep -rnE "linkedin\.com|indeed\.com|lnkd\.in" job_engine/ scripts/` matches only `config.py`); after a complete run `.venv/bin/python scripts/outbound_hosts.py --run-id <id>` prints every distinct host across all stages and both `via` values and exits nonzero on any denylist match; `.venv/bin/python scripts/check_profile_cookies.py` prints `linkedin cookies: 0` against the job engine profile.

7. Seven mornings on the phone. Alex confirms each morning or sends one screenshot of the chat list on day 14. A log line or a `report_lines` row is not accepted and `verify_window.py` prints `phone confirmation: not machine checkable, ask Alex` rather than a pass.

8. Schedule after a day. Day 8 and again day 9, at least 24 hours after `bin/start.sh`: `.venv/bin/python scripts/verify_schedule.py` exits 0 when a `runs` row dated today has `started_by='schedule'` and `pgrep -f job_engine.bot` finds the process; a `catchup` row instead is a fail with the reason printed.

9. Fabrication gate by counterexample. `pytest tests/test_trace_gate.py -q` (fake model) and, once the key exists, `.venv/bin/python -m job_engine.writer --counterexample` which loads `tests/fixtures/corpus_no_python.md`, a job demanding Python and Kubernetes, and a system prompt told to be persuasive. Pass: neither generated document contains `Python` or `Kubernetes`, `trace_json` lists the dropped sentences, and the test asserts the gate lives in `trace.py` by running it on raw text with no model at all.

10. Submission controls individually. `pytest tests/test_submission_controls.py tests/test_dedupe.py -q`. Pass: DRY_RUN on gives artifacts and zero `outbound_hosts` rows for stage `submit`; a cap of 1 halts the second send with `daily_cap`; a stop file created mid run halts the next send with `stop_file`; two postings from different boards with one `dedupe_key` make one application and a repeat inside `APPLICATION_COOLDOWN_DAYS` is blocked.

10b. Model call cap. `pytest tests/test_call_cap.py -q` and live `JOBENGINE_MAX_TIER1_CALLS=3 bin/run-daily.sh --stages ingest,prefilter,triage,report`. Pass: the run completes, `degradations` has `call_cap, disqualifying=0`, the header says it degraded, `reports.qualifying` is unaffected by that row, and fewer candidates were scored than `MAX_TRIAGE_PER_RUN`. Separately assert that no module imports the `anthropic` package and that no code path reads an `JOBENGINE_TIER1_API_KEY`, since a zero spend budget is only as good as the absence of a billing path.

10c. Payload before send. `pytest tests/test_submission_controls.py::test_capture_precedes_send -q`. Pass: with a fake adapter that raises `SystemExit` after capture, the application row holds `payload_json`, `resume_md`, `cover_letter_md` and `payload_captured_at` and has no `submitted_at`.

10d. Lock blocks concurrency. `pytest tests/test_lock.py -q` and live: start `bin/run-daily.sh`, start it again, the second exits 3 on the run lock with a one line report; write a prospector holder record with a live pid, start the command, it exits 2 with `lock_refused` naming `prospector`, no browser stage ran, and the degraded report arrived.

11. Answer bank refusal. `pytest tests/test_answer_bank.py -q`. Pass: a required field with no mapping stops the application with status `manual`, kind `manual_unanswered`, and `answers_json` holds no value for it; `grep -rn "work_authorization" job_engine/prompts/` matches nothing.

12. Corpus allowlist. `pytest tests/test_corpus_allowlist.py -q`. Pass: a directory with an allowlisted file and a sibling file named like the second citizenship project and containing a sentinel; the loader opens only the first (proven by a patched `open`); `corpus.probe()` flags the sentinel and each deny term; `llm.call()` refuses a prompt containing one; `profile.py` and `corpus.py` contain no `glob`, `os.walk`, `rglob`.

12b. Tier 2 handoff and its guard. `pytest tests/test_handoff_schema.py tests/test_tier2_guard.py -q`, then live: `bin/tier2-tasks.sh --kind deep --run-id <today>` prints valid JSON, a deny term in any field makes it exit non zero printing nothing, and `bin/tier2-record.sh` refuses a WriteResult whose claims fail the trace gate. Pass also requires one routine driven morning where `select tier1_calls, tier2_calls from runs order by id desc limit 1` shows both non zero, proving tier 2 actually ran rather than being skipped into a zero match report.
12c. No billing path exists. `grep -rn "anthropic\|ANTHROPIC_API_KEY" job_engine/ bin/ requirements.txt` prints nothing. A zero spend budget is only as good as the absence of a way to spend.
13. Residency both directions. `pytest tests/test_residency_filter.py -q`. Pass: a remote lane 2 posting saying `must reside in the United States` is dropped with `residency_required` while `country_of_residence` is not US; a lane 3 posting in a named target city with the same phrase is kept; a posting saying `must be authorized to work in the United States` is not dropped anywhere; `grep -rniE "authori[sz]ed to work|work authori[sz]ation" job_engine/filters.py job_engine/deep.py` matches nothing.

Definition of done window: `.venv/bin/python scripts/verify_window.py --start <day 8>` on day 14 prints `qualifying mornings: q/7` and `confirmed submissions: n` and exits 0 only when `q >= 5` and `n >= 1`; a morning counts as qualifying only from its stored `reports.qualifying` value. Exit 0 is necessary, not sufficient: the done declaration also needs Alex's phone confirmation from check 7.

## 8. Risk register

1. ATS form variability. Greenhouse form questions come from `?questions=true` (verified free); the others introspect the DOM once and save a fixture. Every adapter enumerates required fields, answers only from the bank or the writer's free text, and fails closed. Ashby's detail API is 401 without a company key (verified), so Ashby is DOM. Recruitee needs a real slug to confirm its API; DOM is the fallback. The report shows adapter failures by ATS every morning.

2. A dedicated Chrome next to the ones Alex uses. Own profile directory and port, fresh and never logged into anything; the cookie assertion runs at every browser start and disqualifies the morning if LinkedIn cookies ever appear; only our own tabs are touched; the browser lock serializes job engine and Prospector; `ensure_chrome()` restarts Chrome after a reboot when the bot is running. Memory records a `playwright-core` attach failure against Chrome 151 and a clean attach against 152; the Phase 1 smoke settles it for Python Playwright 1.62, with the raw CDP driver at `Dev/tasks/cdp.py` as the fallback behind the same interface.

3. Local schedule not firing while travelling. Code: `misfire_grace_time` of 6 hours, catch up on process boot, `runs` and `reports` as heartbeat, `verify_schedule.py` on days 8 and 9. Machine: `caffeinate` keeps the machine up during a run only; nothing in code opens a closed lid on battery; only `sudo pmset repeat wakeorpoweron` (an administrator password, Alex's action) or keeping the machine awake does, and `pmset -g sched` shows no wake event today; launchd was denied before and is not proposed. A reboot kills the bot and nothing restarts it, so `run bin/start.sh after any restart` is a README human step. If seven local mornings prove impossible, the brief's fallback (ingest, score and report on Railway, submit locally from a queue) is the honest next build, not v1.

4. Model capacity. Per tier call caps checked before every batch with a named non disqualifying degradation, tier 1 and tier 2 call counts in every header, the tier 1 provider's free tier limits verified against its own page rather than assumed, and tier 2 kept small on purpose because it competes with Alex's own Claude Code use.

5. CAPTCHA or account wall on a form. Detected, never solved or bypassed; `challenged` or `manual_account_required` with the link in the queue. Lane 1 surfaces are expected to be account gated, so lane 1 may run in approval mode and check 5 reports that as deferred with the reason.

6. Fabricated or over reaching claims under Alex's name. The trace gate in code with two layers and a gut threshold; the counterexample test; payload capture before every send; DRY_RUN default on until Alex reads a dry run; dedupe with cooldown; `MAX_SUBMISSIONS_PER_DAY`; the stop file; hard red flags never auto apply.

7. The corpus pulling in material Alex marks as never to be exposed. Explicit path allowlist, no directory walking (grep tested), a by name refusal on the loader and a by content probe on every outgoing prompt.

8. Aggregator links bouncing through LinkedIn or Indeed. Every hop is logged and checked; the browser route aborts those hosts; such postings drop with `denylisted_host`.

9. Board terms. Every source carries a verdict before it runs. Climatebase and Terra.do were CHECKED on 2026-09-07 and both FAILED: their terms explicitly forbid any automated system, spider, robot or scraper accessing the site, so no adapter exists for either and neither may be added later without new written permission. Climate employers are reached through their own Greenhouse, Lever and Ashby boards instead, which is where applications get submitted anyway. inclimate.com, ClimateTechList and Work on Climate passed with permissive robots files and no prohibition found; Adzuna's real free tier limit is read from Adzuna's own page and capped regardless.

10. One bad source or stage breaking the morning streak. Every stage is wrapped, every failure is a named degradation row, and the report always goes out. A stage with zero items to do is a clean run, not a degradation.

11. SQLite contention between the bot and the daily subprocess. WAL, 30 second busy timeout, short transactions, the run lock.

12. Inbox provider. If the job hunt inbox is Proton, IMAP needs Proton Bridge, which is paid; the mail seam is provider agnostic and this is an open question. Without inbox access the report says `reply tracking off, decommission trigger suspended` and page proof is the submission proof.

13. Lane 3 live on both branches. Human item 11 was cleared on 2026-09-07. Pass: a remote climate posting at $150,001 is accepted and one at exactly $150,000 is rejected; a target city posting at $212,901 is accepted and one at $212,900 rejected; a remote climate posting is NOT judged against the relocation floor. The dark path is asserted unreachable while the floor is set.

14. Rendered resume quality. fpdf2 is plain; `page.pdf()` is headless only. The original resume file is the fallback and the first explicit cut candidate.

## 9. Items outside the brief's human list that this plan surfaces

Not in the brief's list; each absence degrades one feature, none blocks the build.

* Python 3.11 is used rather than JARVIS's pinned 3.12, because 3.12 is not installed on this Mac and the brief resolved not to force an install.
* The Prospector runbook needs one line: write `~/.automation-locks/browser.lock` with holder `prospector` at session start and remove it at session end. Outside this repo; the lead schedules it. Prospector pauses through day 14 either way.
* Provider caveat on brief human item 3 (inbox access): Gmail works with an app password over IMAP; Proton needs Bridge, which is paid.
* A real Recruitee company slug to confirm its API shape. Absent: Recruitee is DOM only.
* `DEFAULT_TIMEZONE` in `.env`, the zone the 07:00 run follows. Required; the process refuses to start without it.
* A free tier provider API key for tier 1, from Groq or Google AI Studio, or else a local Ollama install which needs no account at all. Free either way, but a signup is Alex's to do. Blocks tier 1 entirely, which means no classification at all. This belongs on the brief's human only list and is not currently on it; it replaces the void API key item.
* Values the brief names but does not number, set here as assumptions and marked as such in `config.py`: `MAX_SUBMISSIONS_PER_DAY = 5`, `APPLICATION_COOLDOWN_DAYS = 90`, `QUIET_DAYS = 10`, `MAX_MODEL_CALLS_PER_RUN = {tier1: 450, tier2: 60}`.
