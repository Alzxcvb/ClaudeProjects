# Plan: Council (see brief-council.md)
Lineage: the architecture is Codex's Aug 18 design (Codex session ~/.codex/sessions/2026/08/18/rollout-2026-08-18T08-09-24-*.jsonl): one side via `codex exec`, the other via `claude -p`, a blind judge, a local SQLite accuracy ledger, council invoked explicitly (`/council`), one case plus at most one rebuttal, word caps, no API billing. Fable (2026-09-21) turned that design into the file level plan below; adversarial loops amended it.

## Live-tested amendments (2026-09-21, override the plan text below where they conflict)
- claude argv (tested, returns "ok", ~6K context tokens instead of ~248K):
  `claude -p --output-format json --model sonnet --no-session-persistence --tools "" --strict-mcp-config --disable-slash-commands --system-prompt "<role text>" -- "<prompt>"`
  The `--` before the prompt is REQUIRED: `--tools` is variadic and swallows the prompt otherwise (observed: empty stdout).
  Child env must drop every var starting `CLAUDE` plus ANTHROPIC_API_KEY/OPENAI_API_KEY (without the scrub, a call from inside a Claude session loaded ~190K tokens).
  stdin must be DEVNULL (without it, a call hung waiting on stdin / returned nothing).
- codex argv (tested, returns "ok"): `codex exec --json --skip-git-repo-check -s read-only -C <run_dir> -c model_reasoning_effort=medium "<prompt>"`, stdin DEVNULL, parse stdout only.
- Neither call needs an API key; `total_cost_usd` in claude's JSON is an estimate display, not a charge (no ANTHROPIC_API_KEY set).

## Adversarial loop 1 amendments (override plan text below)
- A1 Alternation (replaces §5): n = row count. judge = "claude" if n % 2 == 0 else "codex". Side assignment flips on n // 2: if (n // 2) % 2 == 0, A->codex, B->claude, else A->claude, B->codex. Over any 4 questions the judge's provider matches side A twice and side B twice. Do NOT store it: compute judge_same_side at read time in history() as 'A' if provider_a == judge_provider else 'B' (no schema column). `history` reports "judge picked its own provider's side X of Y times".
- A2 Timeouts: per call 120 s (not 180). Constant PER_CALL_TIMEOUT=120, SERIAL_STEPS=4; test asserts product < 600.
- A3 Spend guard in main(), before any model call (ask only; resolve/history just check env keys): env keys present -> exit 2; `codex login status` must contain "Logged in using ChatGPT"; `claude auth status` JSON must have authMethod == "claude.ai" (run both with the scrubbed env, stdin DEVNULL, 20 s timeout). Otherwise exit 2 with the reason.
- A4 SQLite: connect with timeout=10, `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=10000`.
- A5 Judge prompt adds: "Weigh two things: which case is better argued, and each author's track record on resolved questions. Say in key_reason how much the record mattered." history adds: of resolved-record questions where one side had the better record, how often the judge picked that side.
- A6 SKILL.md install is a human-only step (symlink); CLI works without it.

## Adversarial loop 2 amendments (override plan text below)
- B1 Blinding (replaces blind() rule in §3): do NOT whole-word scrub persona names (they collide with normal words like "bull market"). Scrub only (a) provider tokens, case-insensitive, as substrings of a word: chatgpt, gpt-?\d*, claude, codex, anthropic, openai, sonnet, opus, haiku -> [redacted]; (b) self-reference patterns: (I am|I'm|as|speaking as)\s+(the\s+)?<PersonaName>\b, case-insensitive -> "as [redacted]". Test: "the bull market is strong" survives unchanged under persona Bull; "As the Bull, I think" is redacted; "ChatGPT" and "GPT-5" are redacted.
- B2 Codex argv also takes "--" before the prompt (live tested 2026-09-21, returns ok): `codex exec --json --skip-git-repo-check -s read-only -C <run_dir> -c model_reasoning_effort=medium -- "<prompt>"`.
- B3 Named tests: history() on an empty DB prints "no questions yet" and exits 0; a persona with 0 resolved rows shows "no resolved record" (no division); judge prompt branch "no resolved record yet" asserted; a row resolved 'neither' is excluded from persona record, judge accuracy, and Brier (asserted), but counts in the total resolved-row count.

## Adversarial loop 3 amendments (override plan text below)
- C1 Record snapshot: add four columns to the §4 CREATE TABLE: rec_a_wins INTEGER NOT NULL, rec_a_resolved INTEGER NOT NULL, rec_b_wins INTEGER NOT NULL, rec_b_resolved INTEGER NOT NULL, filled at insert time with exactly the record numbers shown to the judge. The A5 "did the judge follow the better record" stat uses ONLY these snapshot columns (better record = higher wins/resolved with resolved >= 1 on both sides; ties and empty records excluded), never current ledger state. Test: resolve an earlier row after a later row was judged; the later row's stat does not change.
- C2 The A3 guard calls (`codex login status`, `claude auth status`) use the same RUN_DIR cwd, scrubbed env, stdin DEVNULL as the model calls.

## Loop 4 note
- D1 The A2 timing test includes the two 20 s guard calls: 4*120 + 2*20 = 520 < 600.

## Advisor amendments (sandbox test, 2026-09-21; override plan text below)
- E1 Sandbox reality (live tested inside the Claude Code Bash sandbox): `claude auth status`, `codex login status` and the full `claude -p` argv all WORK sandboxed. `codex exec` FAILS sandboxed: "Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)". So SKILL.md must instruct the executing Claude to run the `ask` command with the Bash tool's sandbox disabled (dangerouslyDisableSandbox: true) from the start, not as a retry, which means one permission prompt per /council ask. `resolve` and `history` need no model and run sandboxed. The runner must surface codex's stderr text in CouncilError so a sandbox failure is obvious.
- E2 `codex login status` prints "Logged in using ChatGPT" on STDERR (stdout empty). The A3 guard must check stdout + stderr combined.
- E3 Quoting: `__main__ ask` accepts `--question-file PATH` as an alternative to the positional question. SKILL.md tells the executing Claude to write $ARGUMENTS to a temp file under $TMPDIR and pass --question-file, so quotes in a question can't break the shell.
- E4 Task 8 includes one live CLI E2E (`python3 -m council ask --question-file ...`, sandbox disabled) run by the builder, before Alex's symlink; the symlink wrapper is then the only untested piece.
- E5 Git: add `council/ledger.db` to Dev/.gitignore; stage by path only; no commit or push without Alex's go.

## Build log (2026-09-21)
- Tasks 1-4 and 5-7 built by Sonnet agents; task 8 (SKILL.md, README, .gitignore) by the main session.
- F1 Self reference regex tightened: a bare "as the <Name>" followed by an ordinary lowercase word ("as the bull market shows") is not redacted; "I am the Bear and ..." still is. Tests added.
- F2 Live E2E #1 showed Codex running web searches (its default). Added `-c web_search="disabled"` to the codex argv (live tested: no web tool, 0 web__run calls in run #2). Keeps v1's "no auto research" and equal footing between sides.
- F3 Live E2E #2 (Codex as judge) exposed a display gap: the judge's reason says "Position 2" but the output never said which side that was. Added a line "(Judge saw Position 1 = Side X ..., Position 2 = Side Y ...)". The mapping itself was correct.
- Live rows #1 and #2 in council/ledger.db are real test questions (S&P 500 on 31 Dec 2026; Dec 2026 CPI above 3%), left for Alex to resolve.

## Fable plan (verbatim)
**Import vs copy: copy.** base.py is stdlib-only, but importing needs a sys.path hack into a sibling project whose top-level package is the generic name `agents`, and Command's runtimes are Popen/event-file streaming designs with no timeout. Council needs a blocking `subprocess.run(timeout=)` returning one string. Copy only the parsing logic: claude `result`/`is_error` (claude_code.py:156-169), codex `item.completed`->`agent_message`, `turn.failed`/`error` (codex.py:64-85).

### 1. File tree (Dev/council/)
- `__init__.py` package marker
- `__main__.py` argparse ask/resolve/history; API-key guard first; `main(argv, runner=None, ledger_path=None, rng=None)` for injection
- `runner.py` minimal run_claude/run_codex, RUN_DIR, clean-cwd guard, env scrub, JSON extraction, CouncilError
- `personas.py` load personas/*.md (name = `# ` heading or stem), default pair, --pair parsing
- `prompts.py` case/rebuttal/judge builders, blind(), parse_verdict()
- `debate.py` one question: assignment, 3 phases, de-blinding, ledger write
- `ledger.py` schema, insert, resolve, record(persona), history stats
- `router.py` route(question) -> "council" (Jev hook)
- `personas/bull.md`, `bear.md` neutral starter worldviews
- `skill/SKILL.md` Claude Code skill
- `tests/test_*.py` stdlib unittest + FakeRunner
- `README.md` run and install lines
- `ledger.db` runtime; add `council/ledger.db` to Dev/.gitignore

### 2. CLI and subprocess
- `cd /Users/alexandercoffman/Dev && python3 -m council ask "<q>" [--pair bull,bear]` prints id, both sides (persona+provider revealed post-judging), winner, confidence, key reason, would-change-mind, resolve hint.
- `python3 -m council resolve <id> A|B|neither` sets outcome, resolved_at; overwrites (prints previous); exit 1 on bad id/value.
- `python3 -m council history`: per persona wins/resolved/rate + unresolved count; judge accuracy and Brier over resolved non-neither rows; last 10 rows.
- Guard, first line of main(): if ANTHROPIC_API_KEY or OPENAI_API_KEY present in os.environ -> stderr, exit 2, all subcommands.
- Extraction: claude json.loads(stdout); if list, take type=="result"; raise on is_error; text = ["result"]. codex: last JSONL item.completed with item.type=="agent_message" -> item.text; raise on turn.failed/error.
- cwd: RUN_DIR = Path(tempfile.gettempdir())/"council-run", mkdir'd, passed as cwd= and -C. Not under Dev (Claude Code loads ancestor CLAUDE.md). Guard refuses if run_dir is under Dev or contains CLAUDE.md/.claude/AGENTS.md; log `[council] provider=... cwd=...` to stderr per call.
- Timeouts: 180 s per call; both cases concurrently, then both rebuttals (ThreadPoolExecutor(2)), then judge. Timeout/nonzero exit -> CouncilError, exit 1, no row.

### 3. Prompts
- Case: worldview body + question + "Argue the position your worldview implies, at most 300 words. Do not name your persona, model, or provider; first person."
- Rebuttal: worldview + question + own case + "An opposing analyst wrote: ... Rebut in at most 200 words." Same no-naming rule.
- Judge: "Two anonymous analysts, Position 1 and Position 2, debated: <q>." Four labelled blocks. "Track record (weak prior, resolved questions only): Position 1's author has a resolved record of X wins in Y resolved questions" or "no resolved record yet". "Judge on argument quality and likely correctness. Return only JSON."
- Schema: {"winner":"1"|"2","confidence":0..1,"key_reason":str,"would_change_mind":str}. parse_verdict: first { to last }, validate; one retry with "Return only JSON, no prose"; then fail.
- Blinding: position1_side = rng.choice("AB") stored; scaffolding never contains names; blind() whole-word scrubs provider tokens (claude, codex, anthropic, openai, gpt, sonnet, opus) and both persona names from argument bodies -> [redacted]. Winner mapped back to A/B via position1_side.

### 4. SQLite schema
CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, question TEXT NOT NULL, persona_a TEXT NOT NULL, persona_b TEXT NOT NULL, provider_a TEXT NOT NULL, provider_b TEXT NOT NULL, judge_provider TEXT NOT NULL, case_a TEXT NOT NULL, case_b TEXT NOT NULL, rebuttal_a TEXT NOT NULL, rebuttal_b TEXT NOT NULL, position1_side TEXT NOT NULL, winner TEXT NOT NULL, confidence REAL NOT NULL, key_reason TEXT NOT NULL, would_change_mind TEXT NOT NULL, judge_raw TEXT NOT NULL, outcome TEXT, resolved_at TEXT);
Record for persona P: rows with outcome in ('A','B') where P is a side; win if its side == outcome. Brier: p = confidence if winner=='A' else 1-confidence; y = (outcome=='A').

### 5. Alternation
n = SELECT COUNT(*). Even n: A->codex, B->claude, judge=claude. Odd: A->claude, B->codex, judge=codex. Row inserted only after judge returns.

### 6. Skill
Dev/council/skill/SKILL.md, frontmatter name: council / description:. ~/.claude/skills and Dev/.claude/skills are write-denied for agents. Install (Alex): `ln -s /Users/alexandercoffman/Dev/council/skill ~/.claude/skills/council`. Body: if $ARGUMENTS starts with resolve/history run that subcommand, else `cd /Users/alexandercoffman/Dev && python3 -m council ask "$ARGUMENTS"`, Bash timeout 600000, echo stdout verbatim. If sandbox blocks nested claude ("Operation not permitted"/auth failure), rerun that one command with sandbox disabled.

### 7. Build tasks
1. Scaffold __init__, __main__ stubs, guard, router.py, tests/. Pass: `python3 -m council --help` exit 0; guard exits 2 per key; route()=="council".
2. ledger.py. Pass: tempfile DB insert/count/resolve/record/history incl. Brier.
3. personas.py + md files. Pass: default (bull,bear); --pair bear,bull order kept; unknown -> error.
4. runner.py. Pass: monkeypatched subprocess.run asserts exact argv, cwd==RUN_DIR and not under Dev, env lacks keys/CLAUDE*; canned stdout -> text; is_error/turn.failed/timeout -> CouncilError.
5. prompts.py. Pass: fake args "I am the Bull, running on Claude via codex" -> judge prompt has no forbidden tokens, has "Position 1/2" and record sentence; parse_verdict fenced/bare/garbage.
6. debate.py + FakeRunner. Pass: two runs -> (codex,claude,judge claude) then (claude,codex,judge codex); seeded rng position1_side='B' and fake winner "1" stored as 'B'; every call cwd==RUN_DIR.
7. Wire __main__. Pass: main(["ask","q"],runner=fake) prints id; resolve 1 A then history shows 1/1; `python3 -m unittest discover -s council/tests -t /Users/alexandercoffman/Dev; echo $?` -> 0.
8. SKILL.md, README, .gitignore line. Pass: Alex symlinks, then the one live E2E.

### 8. Acceptance -> tests
- Skill E2E prints ruling, sqlite3 row count +1: LIVE (only live call).
- Judge prompt name-free: fake (task 5). Swap + judge alternation: fake (task 6).
- `ANTHROPIC_API_KEY=x python3 -m council history; echo $?` -> 2.
- resolve -> history: fake (task 7) + manual on the live row.
- No Dev cwd: fake (task 4) + runtime guard + stderr log in live run.
- Tests standalone, nonzero on failure: unittest exit code.
