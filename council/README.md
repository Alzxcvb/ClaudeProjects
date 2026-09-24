# Council

Two personas argue a question (one on Codex, one on Claude, via your subscription CLIs, no API keys), each rebuts once, and a blind judge rules using argument quality plus each persona's resolved track record. Every ruling is logged to `council/ledger.db`.

Brief: `../tasks/brief-council.md`. Plan and review log: `../tasks/plan-council.md`.

## Use
    python3 -m council ask "Will X happen by June?" [--pair bull,bear]
    python3 -m council ask --question-file q.txt
    python3 -m council resolve 3 A        # A, B, or neither, once reality settles it
    python3 -m council history

Run from `Dev/`. `ask` must run outside the Claude Code sandbox (codex exec can't start inside it).

## Install the /council skill (one time, by hand)
    ln -s /Users/alexandercoffman/Dev/council/skill ~/.claude/skills/council

## Personas
One file per worldview in `personas/`. The first `# ` heading is the display name, the file stem is the key used with `--pair`. Bull and Bear are neutral starters; write your own.

## Guards
Refuses to run if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is set, or if `claude auth status` / `codex login status` do not show a subscription login. Model calls run from `$TMPDIR/council-run` with MCP servers, skills, and tools off (about 6K context tokens per Claude call instead of about 248K).

## Tests
    python3 -m unittest discover -s council/tests -t .
