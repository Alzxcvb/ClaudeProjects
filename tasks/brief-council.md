# Brief: Council

## Definition of done
Alex types `/council <question>` in Claude Code, and within a few minutes gets a judged answer: Codex argues one position, Claude argues the opposing one, each gets one rebuttal, a blind judge rules, and the whole exchange is saved as one row in a local track record log. The log's win rates are shown to the judge on later questions.

## Audience and distribution
Audience of one (Alex). No distribution needed.

## Scope
In:
- `Dev/council/`, a small new folder. It reuses Command's existing runners (`command/agents/runtimes/claude_code.py`, `codex.py`) by import or copy. Command itself is not edited.
- Persona files (`council/personas/*.md`), one worldview per file. Ships with one neutral starter pair (Bull, Bear). Alex writes his own later. v1 invents no political or other beliefs for him.
- Flow per question: two personas are picked (by flag, or the default pair) → persona A on Codex, persona B on Claude, provider assignment rotates per amendment A1 → each makes one case, capped at about 300 words → each gives one rebuttal to the other → the judge sees both with persona and provider names removed, plus each persona's past record → the judge returns structured JSON (winner, confidence 0 to 1, the key reason, what would change its mind).
- Judge provider and side assignment vary independently (see plan amendment A1), so the judge's provider matches side A half the time and side B half the time. With only two providers the judge ALWAYS shares a provider with one side; that is a known limitation, reduced by blinding and measured in `/council history` (how often the judge picks its own provider's side).
- SQLite log (`council/ledger.db`): question, personas, providers, arguments, verdict, confidence, and a resolved outcome that starts empty.
- `/council resolve <id> A|B|neither` lets Alex mark real outcomes by hand. Only resolved rows count toward a persona's track record. Unresolved rows are judged on argument quality alone.
- `/council history` shows each persona's resolved win rate and how well the judge's confidence matched outcomes.
- A Claude Code skill wraps the CLI so `/council` works in any session.
- A router hook (a function that returns "council" today) where a Jev gate can plug in later.

Out (v1 explicitly does not do this):
- No multi round debates (one case, one rebuttal, one ruling).
- No automatic web research per side.
- No phone, web, or Telegram interface.
- No marketing specialist agent (planned for v2; sources would be `hi-im-alex/marketing/`, `linkedin-content-engine/`, `content-strategy/`).
- No Jev, no Laya, and no API keys of any kind.

## Constraints
Budget: strictly zero API spend. Subscription usage only (Claude plan, ChatGPT plan with Codex). The code must refuse to run if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set, or if `codex login status` does not say "Logged in using ChatGPT", or if `claude auth status` does not report `"authMethod": "claude.ai"` (both confirmed live 2026-09-21). Residual risk the code can't see: if Alex has turned on pay as you go extra usage on either plan, going past the plan cap could bill. Alex should confirm extra usage is off (human only step 2).
Deadline or time box: none stated.
Stack: Python 3 and stdlib `sqlite3`; `claude -p --output-format json` and `codex exec --json --skip-git-repo-check`, both tested live on 2026-09-21 and returning "ok" with no API key set. Calls must run from a clean working directory (not `Dev/`), because a `claude -p` run from `Dev/` loaded about 36K tokens of CLAUDE.md and memory. Also required (live measured): scrub `CLAUDE*` env vars and pass `--strict-mcp-config --disable-slash-commands --tools "" --system-prompt`, which cut one call from about 248K to about 6K tokens. Judge and advocates default to mid tier models (Sonnet, Codex default). Each question costs 5 model calls: 2 cases, 2 rebuttals, 1 judge.

## Jev and Laya analysis (why they are out of v1)
- Neither can be the judge. Both take a structured input plus a fixed set of labels and return probabilities. They do not read two arguments and reason about which is better supported, and they write no explanation.
- Jev (TypeSafe AI): cloud API only, early access (sources disagree on whether a free trial exists, so it's unverified), $0.042 per million input tokens with output free (stated on jevai.net and in search results citing TypeSafe; docs.typesafe.ai/concepts/system-one did not list a price when fetched 2026-09-21). It would be a good cheap router ("does this question need the council?"), but any spend breaks the zero spend rule. jevai.org describes itself as a community site, and it's unclear whether jevai.net is official. The official docs are at docs.typesafe.ai.
- Laya (Convai, Apache 2.0, 421M params, source huggingface.co/convaiinnovations/laya fetched 2026-09-21): runs locally for free, but has a 512 (English) or 1024 (multilingual) token limit and scores 0.362 zero shot against a 0.318 chance baseline. Its own model card says it is "a fast base to specialise, not a zero-shot decision engine." A possible v3: once the log holds a few hundred resolved rows, train Laya on them as a local confidence scorer.
- Having a third provider judge would remove any bias from sharing a provider with one advocate. The only free local option is Ollama `qwen2.5:3b`, which is too weak to judge. v1 reduces that bias by blinding the judge and rotating which side shares the judge's provider, and measures what bias remains.

## Human only steps queue
1. BLOCKS `/council` in Claude Code (not the build or tests): agents can't write to `~/.claude/skills`, so Alex runs `! ln -s /Users/alexandercoffman/Dev/council/skill ~/.claude/skills/council` once. Until then the CLI works (`python3 -m council ask ...`).
2. Each `/council` ask triggers one permission prompt, because `codex exec` can't run inside the Claude Code sandbox (tested 2026-09-21). Optional: Alex can add the council command to the sandbox's excluded commands via `/sandbox` to skip the prompt.
3. Non blocking: confirm pay as you go / extra usage is off on the Claude and ChatGPT plans, so the zero spend rule holds past plan caps.
4. After v1 ships: write real persona files, and mark outcomes with `/council resolve` as they happen. The track record only means something once Alex does this.

## Autonomy mandate
"Build straight through." Stop only for things that truly need Alex.

## Acceptance checks
- Run `/council "<test question>"` from a fresh Claude Code session (the exact skill path, not the Python file directly), and confirm a ruling is printed and one new row is in `ledger.db`.
- Confirm the judge prompt contains no persona or provider names (a test asserts this on the built prompt).
- Confirm rotation per A1 over 4 fake runs: judge alternates every run; side A's provider flips every 2 runs; the judge's provider matches side A exactly twice and side B exactly twice.
- With `ANTHROPIC_API_KEY=x` set, the run refuses to start.
- `/council resolve <id> A` updates that row, and `/council history` reflects it (both directions: write, then read back).
- Check that no call ran with `Dev/` as its working directory (look at the process cwd in a test or log).
- Worst case timing fits: per call timeout 120 s; cases in parallel, rebuttals in parallel, judge, one judge retry = 4 serial steps = 480 s max, under the 600 s Bash ceiling. A test checks the configured numbers add up to under 600.
- The judge prompt contains both the track record sentence and the instruction to weigh record and argument together (asserted on the built prompt). `/council history` shows how often the judge sided with the side that had the better record, so Alex can see whether the record matters.
- Unit tests pass when run on their own (not piped), with a nonzero exit on failure.
