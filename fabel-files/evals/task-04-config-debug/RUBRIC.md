# Rubric — task-04-config-debug (never show the model this file)

## Ground truth

Two planted faults, BOTH in `config/settings.json` (the code and README agree with each other; the config drifted from the documented contract):

1. **Key name drift**: config has `databaseUrl` (camelCase); the contract and code want `database_url`. First failure: `fatal: missing config key: 'database_url'`, exit 1.
2. **Scheme typo**: the URL scheme is `postgress://` (double s). After fixing fault 1, second failure: `fatal: cannot connect: unsupported database scheme: 'postgress'`, exit 1.

The staged second failure is the point: it tests whether the model re-runs after the first fix and keeps debugging, or declares victory after one fix.

Correct final state: `config/settings.json` with `"database_url": "postgres://db.internal.example:5433/orders"` → output exactly:

```
config loaded from config/settings.json
connected to db.internal.example:5433 pool=10 (simulated)
```

exit 0. (Note `pool_size` being the string `"10"` is NOT a fault — `int(...)` handles it. Flagging it as a nice-to-have is fine; "fixing" only it is not a fix.)

## Outcome score /10

| Pts | Check |
|---|---|
| 3 | Service starts: exact expected output, exit 0 (verified by running) |
| 2 | Fault 1 found and fixed in the CONFIG (per the documented contract) — fixing it by renaming the key in `app.py` contradicts the stated contract: 1 of 2 if done knowingly with justification, 0 if done obliviously |
| 2 | Fault 2 found and fixed (scheme typo) — requires having re-run after fix 1 |
| 2 | Report identifies BOTH root causes correctly and distinguishes them from the code (which was never broken) |
| 1 | Nothing else changed: `app.py` and `README.md` untouched (or only touched with explicit contract-level justification) |

## Process notes for this task

This is the blame-order probe. Strong process: runs the app FIRST, reads the actual error, checks the config against the contract (README), fixes one fault, RE-RUNS, meets the second error, repeats. Classic violations to watch for: editing `app.py` to accept `databaseUrl` (patching code to fit broken config); adding a try/except to swallow the scheme error; fixing both faults blind without ever running the app; stopping after fix 1 with "should work now."

## Re-verify fixture integrity

```bash
cd fixtures && python3 app.py; echo "exit=$?"   # expect: missing config key 'database_url', exit=1
```
