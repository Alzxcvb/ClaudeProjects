"""Account-exposure scanning via configurable OSINT backend.

Default backend: Sherlock (github.com/sherlock-project/sherlock), ~400 platforms, username only.
Alternative: Blackbird (github.com/p1ngul1n0/blackbird), 600+ platforms, username + email.

Switch backends by setting the environment variable before any erasure command:
    ERASURE_ACCOUNTS_BACKEND=blackbird erasure accounts find <username>

Blackbird also exposes scan_email, which has no Sherlock equivalent (replaces holehe).
"""

import os as _os

_BACKEND = _os.environ.get("ERASURE_ACCOUNTS_BACKEND", "sherlock").lower()

if _BACKEND == "blackbird":
    from erasure.accounts.blackbird import scan_username as scan_username  # noqa: F401
    from erasure.accounts.blackbird import scan_email as scan_email  # noqa: F401
else:
    from erasure.accounts.sherlock import scan_username as scan_username  # noqa: F401
