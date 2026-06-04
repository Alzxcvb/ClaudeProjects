"""The master privacy playbook (thread steps 1-9).

The data-broker thread's real value was not any single trick. It was turning
"vague dread" into an ordered checklist. This module is that checklist, made
stateful: it lays out the nine-step footprint wipe, marks which steps Erasure
automates (with the exact command to run), reports how far you have gotten by
reading ``state/``, and gives concrete instructions + links for the steps that
stay manual (clean search results, suppression, lock-the-doors).

Copy is deliberately plain (no em dashes) so a generated checklist reads like a
human wrote it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel


@dataclass(frozen=True)
class StepSpec:
    number: int
    title: str
    summary: str  # what the thread tells you to do
    commands: tuple[str, ...]  # erasure commands that automate this step
    manual: tuple[str, ...]  # manual actions + links for the non-automated part
    probe_key: Optional[str]  # which state probe drives the status line, if any


STEPS: tuple[StepSpec, ...] = (
    StepSpec(
        1,
        "Map your exposure",
        "Find everywhere you appear: data brokers, social accounts, breached "
        "sites, and email-linked signups. Brokers are the source, so they come "
        "first.",
        (
            "erasure scan",
            "erasure accounts find <username>",
            "erasure emails find <email>",
            "erasure breaches check <email>",
        ),
        (
            "Google your own name plus your city in an incognito window and log "
            "every site that shows you.",
        ),
        "exposure",
    ),
    StepSpec(
        2,
        "Build the tracking sheet",
        "For every broker, record site, opt-out URL, date requested, status, and "
        "follow-up date. This is the unglamorous part that actually works.",
        ("erasure tracker init", "erasure tracker show", "erasure tracker export"),
        (),
        "tracker",
    ),
    StepSpec(
        3,
        "Submit removals",
        "Send the opt-out and deletion requests. In California, DROP fans a single "
        "request out to every registered broker. Elsewhere, submit per broker.",
        ("erasure drop submit --profile ~/.erasure/profile.json",),
        (
            "Per-broker forms ask you to confirm the listing and verify by email. "
            "If one demands a photo ID, cover everything but your name and photo.",
        ),
        "drop",
    ),
    StepSpec(
        4,
        "Use your legal leverage",
        "Cite the law. A request that names CCPA section 1798.105 or GDPR Article "
        "17 and sets a response clock moves far faster than a polite ask.",
        ("erasure legal request --recipient '<Broker>' --jurisdiction ccpa",),
        (),
        "legal",
    ),
    StepSpec(
        5,
        "Kill the dead accounts",
        "Find old logins and delete them, not just deactivate. Erasure turns your "
        "account-discovery hits into direct deletion links and difficulty ratings.",
        ("erasure accounts deletion-links",),
        (
            "Search your inbox for 'welcome', 'verify your account', and 'your "
            "receipt' to surface forgotten signups.",
        ),
        "deletion_links",
    ),
    StepSpec(
        6,
        "Scrub before you delete",
        "Some companies keep 'deleted' data. Before deleting a hard-to-remove "
        "account, overwrite it first: junk name, alias email, blanked profile.",
        ("erasure accounts deletion-links --scrub-only",),
        (
            "For each flagged site: change the name to junk, swap the email to an "
            "alias, blank the profile, and only then delete.",
        ),
        "scrub",
    ),
    StepSpec(
        7,
        "Clean your search results",
        "Broker removals slowly clean Google, but stubborn cached results remain. "
        "Request removal of pages exposing your phone, address, or email.",
        (),
        (
            "Use Google's 'Results about you' tool: "
            "https://myactivity.google.com/results-about-you",
        ),
        None,
    ),
    StepSpec(
        8,
        "Suppress what you cannot remove",
        "For results you do not control, such as old forum posts and mentions, "
        "fight visibility rather than existence. Pages you own rank higher.",
        (),
        (
            "Build and maintain pages you control (LinkedIn, a personal site) so "
            "they outrank the junk. Nobody checks page 2.",
        ),
        None,
    ),
    StepSpec(
        9,
        "Lock the doors behind you",
        "A wipe is pointless if you re-leak. Privacy is maintenance: brokers "
        "relist you within 6 to 12 months, so re-check on a schedule.",
        ("erasure tracker show --due", "erasure scan"),
        (
            "Use email aliases for new signups (SimpleLogin, iCloud Hide My Email). "
            "Stop posting your real-time location. Audit app permissions. Set a "
            "quarterly reminder to re-check the brokers.",
        ),
        "followups",
    ),
)


class StepStatus(BaseModel):
    # True = done, False = not started, None = ongoing/manual (no binary state)
    done: Optional[bool] = None
    detail: str = ""


def _safe(fn, default):
    """Run a probe, swallowing any import/IO error so the playbook never crashes
    just because one subsystem's state dir is missing."""
    try:
        return fn()
    except Exception:
        return default


def gather_status() -> dict[str, StepStatus]:
    """Inspect ``state/`` (relative to the current directory) and report how far
    each step has progressed. Resilient: a missing subsystem yields 'not started'
    rather than an error."""
    from erasure.report import html as _h

    status: dict[str, StepStatus] = {}

    # 1. exposure: a baseline scan + any OSINT surface
    scan = _safe(_h.latest_scan_path, None)
    accounts = _safe(_h.latest_accounts_path, None)
    emails = _safe(_h.latest_emails_path, None)
    breaches = _safe(_h.latest_breaches_path, None)
    surfaces = [
        ("broker scan", scan),
        ("accounts", accounts),
        ("emails", emails),
        ("breaches", breaches),
    ]
    have = [name for name, p in surfaces if p]
    status["exposure"] = StepStatus(
        done=bool(scan),
        detail=("mapped: " + ", ".join(have)) if have else "no scans yet",
    )

    # 2. tracker ledger
    def _tracker():
        from erasure import tracker

        led = tracker.load_ledger()
        n = len(led.entries)
        requested = sum(1 for e in led.entries if e.status == "requested")
        confirmed = sum(1 for e in led.entries if e.status == "confirmed")
        return StepStatus(
            done=n > 0,
            detail=(
                f"{n} sites tracked ({requested} requested, {confirmed} confirmed)"
                if n
                else "ledger empty"
            ),
        )

    status["tracker"] = _safe(_tracker, StepStatus(done=False, detail="ledger empty"))

    # 3. DROP submission
    receipt = _safe(_h.latest_receipt_path, None)
    status["drop"] = StepStatus(
        done=bool(receipt),
        detail="DROP receipt on file" if receipt else "no DROP submission yet",
    )

    # 4. legal letters
    def _legal():
        from erasure.legal.generator import LEGAL_DIR

        letters = list(LEGAL_DIR.glob("*.txt")) if LEGAL_DIR.exists() else []
        return StepStatus(
            done=bool(letters),
            detail=f"{len(letters)} letters generated" if letters else "no letters yet",
        )

    status["legal"] = _safe(_legal, StepStatus(done=False, detail="no letters yet"))

    # 5 + 6. deletion links / scrub-first (driven by account discovery)
    status["deletion_links"] = StepStatus(
        done=bool(accounts or emails),
        detail=(
            "account hits available to enrich"
            if (accounts or emails)
            else "run accounts/emails discovery first"
        ),
    )

    def _scrub():
        from erasure.accounts.justdelete import load_directory, SCRUB_FIRST_DIFFICULTIES

        entries = load_directory()
        n = sum(1 for e in entries if e.difficulty in SCRUB_FIRST_DIFFICULTIES)
        return StepStatus(
            done=None,
            detail=f"{n} services in the directory need scrubbing before deletion",
        )

    status["scrub"] = _safe(_scrub, StepStatus(done=None, detail="directory unavailable"))

    # 9. quarterly follow-ups due
    def _followups():
        from erasure import tracker

        led = tracker.load_ledger()
        due = tracker.due_followups(led)
        return StepStatus(
            done=None,
            detail=(f"{len(due)} follow-ups due now" if due else "no follow-ups due"),
        )

    status["followups"] = _safe(_followups, StepStatus(done=None, detail="no follow-ups due"))

    return status


def checkbox(done: Optional[bool]) -> str:
    if done is True:
        return "[x]"
    if done is False:
        return "[ ]"
    return "[~]"  # ongoing / manual


def render_markdown(requester_name: Optional[str] = None) -> str:
    """Render the full personalized playbook as Markdown."""
    status = gather_status()
    who = f" for {requester_name}" if requester_name else ""
    lines = [
        f"# Your privacy playbook{who}",
        "",
        "Legend: [x] done  [ ] not started  [~] ongoing or manual",
        "",
    ]
    for s in STEPS:
        st = status.get(s.probe_key) if s.probe_key else None
        mark = checkbox(st.done if st else None)
        lines.append(f"## {mark} Step {s.number}. {s.title}")
        lines.append("")
        lines.append(s.summary)
        if st and st.detail:
            lines.append("")
            lines.append(f"Status: {st.detail}")
        if s.commands:
            lines.append("")
            lines.append("Erasure automates this:")
            for c in s.commands:
                lines.append(f"  - `{c}`")
        if s.manual:
            lines.append("")
            lines.append("Do by hand:")
            for m in s.manual:
                lines.append(f"  - {m}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
