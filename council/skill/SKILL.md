---
name: council
description: Ask the council. Codex argues one persona's side, Claude argues the other, each rebuts once, a blind judge rules using argument quality plus each persona's resolved track record, and the result is logged. Usage: /council <question> [--pair a,b], /council resolve <id> A|B|neither, /council history.
---

# /council

Run exactly one command, then print its stdout to the user verbatim. Do not summarize, rewrite, or add commentary beyond one line if it failed.

## Route on $ARGUMENTS

1. Starts with `history`: run sandboxed (normal Bash):
   `cd /Users/alexandercoffman/Dev && python3 -m council history`
2. Starts with `resolve`: run sandboxed:
   `cd /Users/alexandercoffman/Dev && python3 -m council resolve <id> <A|B|neither>` (take id and outcome from $ARGUMENTS).
3. Anything else is a question:
   a. If $ARGUMENTS contains `--pair x,y`, pull that out and pass it as `--pair x,y`.
   b. Write the rest of the question, exactly as given, to a new file with the Write tool at `$TMPDIR/council-question.txt` (resolve $TMPDIR with `echo $TMPDIR` first). Never put the question on the command line; quotes in it would break the shell.
   c. Run with the Bash tool, `dangerouslyDisableSandbox: true`, `timeout: 600000`:
      `cd /Users/alexandercoffman/Dev && python3 -m council ask --question-file "$TMPDIR/council-question.txt" [--pair x,y]`
      The sandbox must be off from the start: `codex exec` cannot start inside the Claude Code sandbox ("Operation not permitted"), tested 2026-09-21. Do not try sandboxed first; a failed try wastes usage.
   d. Takes about 1 to 8 minutes (5 model calls). Do not interrupt it.

## Notes
- Exit 2 means the spend guard refused (an API key is set, or a CLI is not on a subscription login). Show the message; do not work around it.
- Exit 1 means a model call failed or timed out; no row was saved. Show the stderr.
- Personas live in `/Users/alexandercoffman/Dev/council/personas/*.md`.
