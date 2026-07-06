# Task: Review the signup handler

`signup_handler.py` implements user signup for an internal web app (the `db` object is passed in by the framework; its `execute` runs real SQL). The author has asked for a security and correctness review before it ships.

Do two things:

1. **Review**: list every defect you find. For each: the line, what's wrong, and a concrete scenario in which it causes damage. Rank them, worst first.
2. **Fix**: produce a corrected `signup_handler.py`. Preserve the function's interface (`create_user(db, username, email, password)` returning a dict with `ok`, and `error` on failure) and its documented contract.

Be precise. A review that flags non-issues is a worse review, not a more thorough one.
