# Domain: CLI Tools

Applies when: building or changing command-line tools — argument parsing, terminal output, scripts meant to be invoked by humans or other programs. Load with `CLAUDE-FABEL.md`.

## 1. Failure modes

- **Exit code always 0.** The tool prints an error and exits 0, so every script, CI job, and `&&` chain built on it silently proceeds on failure.
- **Streams confused.** Human chatter on stdout mixed into data output, so `tool | jq` breaks; or errors printed to stdout where pipelines can't see them.
- **Help text drift.** `--help` describing flags that don't exist or missing ones that do. For a CLI, help IS the spec surface.
- **Destructive by default.** A bare invocation that deletes, overwrites, or mutates without a flag or confirmation.
- **Interactive assumptions.** Prompts that hang forever in cron/CI where there's no TTY; color codes garbling piped output.
- **Argument parsing by hand.** Homegrown `sys.argv` slicing that breaks on `=`, quotes, or reordering, instead of the language's standard parser.

## 2. Standards

- Exit 0 on success, nonzero on failure — distinct codes for distinct failure classes if callers need to branch (document them in help).
- **stdout is for output, stderr is for everything else** (progress, warnings, errors). The data output must survive `| grep` and `> file` untouched.
- `--help` is accurate, includes one realistic example, and is regenerated/re-checked whenever flags change. A flag change without a help change is an incomplete diff.
- Destructive operations require an explicit flag (`--force`, `--yes`) or interactive confirmation, and say what they did afterward ("deleted 3 files"), not just nothing.
- Non-interactive use always works: every prompt has a flag equivalent; detect no-TTY and fail with instructions rather than hanging.
- Errors name the problem and the fix: `error: config not found at ~/.foo/config.toml (run 'foo init' to create one)` — not a bare traceback.
- Support `-` and stdin where input files are accepted, if the codebase's tools already follow that convention.

## 3. Defaults

- The language's standard/blessed parser (argparse, clap, cobra, commander) — never hand-rolled parsing.
- Subcommand structure (`tool verb [args]`) once a tool has more than ~2 operations.
- Machine-readable output behind a flag (`--json`) rather than making humans parse tables, when other programs will consume it.
- Config precedence, explicitly: flags > environment variables > config file > defaults. Document it in help.
- No color/spinner output when stdout is not a TTY.

## 4. Verification

- Run the actual binary/script, not just its functions: happy path, bad flag, missing required arg, nonexistent input file. Quote the exit codes (`echo $?`) — don't assume them.
- Pipe it: `tool ... | cat` (TTY detection), `tool ... > out.txt` (streams clean), and feed it via stdin if supported.
- Run `--help` and read it against the actual flags — every flag present, example still correct.
- Trigger one destructive path and confirm the guard (flag required, confirmation shown) and the after-report.

## 5. Edge cases that always matter

- Paths: spaces, unicode, `~`, relative vs. absolute, nonexistent parent directories, no write permission.
- Input: empty file, huge file (streams or slurps?), binary garbage where text was expected.
- Arguments: repeated flags, empty string values, `--` separating flags from positionals, args that look like flags.
- Environment: missing env vars the tool assumes; running from a different working directory than the project root.
- Signals: Ctrl-C mid-run — does it leave partial output/temp files, and does it exit nonzero?

## 6. Stop signals

- The flag list needs its own pager → the tool wants subcommands or a config file.
- You're parsing your own human-formatted output in tests → add `--json` and test that.
- A "small script" has grown a second responsibility and a config format → restructure before it becomes an app by accident.
- You need the user to run it twice in a special order for correct state → encode the order in the tool (one command, or an explicit check with a clear error).
