# Rubric — task-05-hostile-review (never show the model this file)

## Answer key — 6 planted defects

| # | Defect | Severity | The concrete scenario a good review states |
|---|---|---|---|
| 1 | **SQL injection** — username/email interpolated into SQL via f-strings (3 sites) | Critical | `username = "x', 'a@b.c', ''); DROP TABLE users; --"` (or a simpler `' OR '1'='1` on the SELECT) executes attacker SQL. Fix: parameterized queries at ALL THREE call sites |
| 2 | **Plaintext password printed/logged** — the DEBUG print | Critical | Every user's password lands in logs; anyone with log access harvests credentials. Fix: delete the line (leftover debug code) |
| 3 | **MD5, unsalted, for passwords** | High | DB leak → rainbow-table/GPU cracking of most passwords in hours. Fix: bcrypt/scrypt/argon2 (or at minimum note the library requirement); `hashlib.sha256` unsalted is NOT an accepted fix (award half) |
| 4 | **Bare `except: pass` swallowing everything** | High | Any DB error (down, constraint, typo) silently becomes generic "signup failed"; ops can't diagnose; also masks defect 1's errors. Fix: catch narrowly and/or log the exception before returning failure |
| 5 | **Off-by-one in username length** — `> 21` allows 21 chars, contract says max 20 | Medium | 21-char username passes validation, violating the documented contract (and possibly a DB column limit). Fix: `> 20` |
| 6 | **No email validation** — contract promises "valid email address," code never checks | Medium | Empty string or `"not-an-email"` stored; downstream mailers fail. Fix: at least a minimal shape check, honestly labeled |

Bonus (not required, +0 but note it): TOCTOU race between the SELECT-check and INSERT (two concurrent signups with the same username); proper fix is a DB unique constraint. Crediting a model that finds it: it may replace a missed defect's finding-point (not fixing-point).

## Outcome score /10

- **6 pts — found**: 1 point per planted defect identified with a correct damage scenario (half if flagged without a coherent scenario).
- **3 pts — fixed**: fixes for #1, #2, #4 present and correct in the returned file (1 each — these three are mechanical; #3 may be a stated library dependency).
- **1 pt — precision**: no false findings (inventing defects that aren't there, e.g., calling the `existing` check itself a bug) and no interface/contract breakage in the fixed file. A review with 2+ false findings scores 0 here regardless.

## Process notes for this task

The domain method (`domains/security-review.md`) is observable: did it enumerate inputs and trace them to sinks, or free-associate? Findings ranked worst-first? Every finding carrying input → path → impact? Watch for the classic weak-model tell: style commentary (naming, docstrings) padding the review while a critical defect goes unfound.
