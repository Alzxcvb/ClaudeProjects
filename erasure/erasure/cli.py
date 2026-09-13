"""CLI entrypoint for Erasure."""

import json
import sys
from datetime import date
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

console = Console()

DEFAULT_PROFILE_PATH = Path.home() / ".erasure" / "profile.json"


def get_version():
    """Get package version."""
    try:
        return version("erasure")
    except PackageNotFoundError:
        return "0.1.0"


def show_not_implemented(command_name: str):
    """Display a not-implemented panel."""
    panel = Panel(
        f"[yellow]Not yet implemented[/yellow]\n\n[dim]TODO: Implement {command_name} command[/dim]",
        title=f"[bold]{command_name}[/bold]",
        expand=False,
    )
    console.print(panel)


@click.group()
@click.version_option(version=get_version(), prog_name="erasure")
def cli():
    """Erasure: open-source data-broker opt-out tool."""
    pass


@cli.command()
@click.option("--profile-path", type=click.Path(), help="Path to user profile file")
@click.option("--force", is_flag=True, help="Overwrite existing profile without prompting")
def init(profile_path, force):
    """Initialize user profile via prompts. Writes ~/.erasure/profile.json by default."""
    from erasure.profile import UserProfile

    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if target.exists() and not force:
        if not Confirm.ask(f"Profile already exists at {target}. Overwrite?", default=False):
            console.print("[yellow]Aborted.[/yellow]")
            sys.exit(0)

    console.print(Panel(
        "Let's build your Erasure profile.\n\n"
        "[dim]This stays on your machine. Only the fields you choose are sent to DROP "
        "or broker opt-out forms.[/dim]",
        title="erasure init",
        expand=False,
    ))

    name = Prompt.ask("Legal name (as on ID)")
    addresses: list[str] = []
    first_addr = Prompt.ask("Current address (street, city, state, ZIP)")
    addresses.append(first_addr)
    while Confirm.ask("Add another current address?", default=False):
        addresses.append(Prompt.ask("Address"))

    prior_addresses: list[str] = []
    while Confirm.ask("Add a prior address (improves broker match)?", default=False):
        prior_addresses.append(Prompt.ask("Prior address"))

    emails: list[str] = []
    emails.append(Prompt.ask("Primary email"))
    while Confirm.ask("Add another email?", default=False):
        emails.append(Prompt.ask("Email"))

    phones: list[str] = []
    phones.append(Prompt.ask("Primary phone (E.164 preferred, e.g. +14155551234)"))
    while Confirm.ask("Add another phone?", default=False):
        phones.append(Prompt.ask("Phone"))

    dob_str = Prompt.ask("Date of birth (YYYY-MM-DD, or blank to skip)", default="")
    dob = date.fromisoformat(dob_str) if dob_str else None

    aliases: list[str] = []
    while Confirm.ask("Add a name alias / maiden name / variant?", default=False):
        aliases.append(Prompt.ask("Alias"))

    mobile_ad_ids: list[str] = []
    if Confirm.ask("Add mobile advertising IDs (IDFA/GAID)? Deepens DROP match rate.", default=True):
        console.print(
            "[dim]iOS: Settings → Privacy & Security → Tracking. "
            "Android: Settings → Google → Ads → Your advertising ID.[/dim]"
        )
        while True:
            mid = Prompt.ask("Advertising ID (blank to finish)", default="")
            if not mid:
                break
            mobile_ad_ids.append(mid)

    zip_code = Prompt.ask("ZIP (required by DROP)", default=addresses[0].split()[-1] if addresses else "")

    profile = UserProfile(
        name=name,
        addresses=addresses,
        prior_addresses=prior_addresses,
        emails=emails,
        phones=phones,
        dob=dob,
        aliases=aliases,
        mobile_ad_ids=mobile_ad_ids,
        zip_code=zip_code,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    target.chmod(0o600)

    console.print(Panel(
        f"[green]Profile saved to {target}[/green]\n\n"
        f"Name variants Erasure will search: {len(profile.to_search_variants())}\n"
        f"Emails: {len(emails)} | Phones: {len(phones)} | Addresses: {len(addresses)+len(prior_addresses)}\n"
        f"Mobile ad IDs: {len(mobile_ad_ids)}\n\n"
        f"[bold]Next:[/bold] `erasure drop submit --profile {target}` to queue a CA DROP request.",
        title="Ready",
        expand=False,
    ))


@cli.command("opt-out")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
def opt_out(dry_run):
    """Per-broker opt-out automation. Stub — CA users should use `erasure drop submit` instead."""
    show_not_implemented("opt-out")
    sys.exit(0)


@cli.command()
@click.option("--profile", "profile_path", type=click.Path(exists=True), help="Profile JSON (default: ~/.erasure/profile.json)")
@click.option("--output", "output_path", type=click.Path(), help="Write the playbook as Markdown to this path")
def playbook(profile_path, output_path):
    """Your personalized 9-step privacy playbook: what Erasure has done, what's left."""
    from erasure.playbook import STEPS, checkbox, gather_status, render_markdown

    name = None
    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if target.exists():
        from erasure.profile import UserProfile

        try:
            name = UserProfile.model_validate_json(target.read_text()).name
        except Exception:
            name = None

    if output_path:
        Path(output_path).write_text(render_markdown(name), encoding="utf-8")
        console.print(f"[green]Playbook written:[/green] {output_path}")
        return

    status = gather_status()
    console.print(Panel(
        f"[bold]Your privacy playbook[/bold]{(' for ' + name) if name else ''}\n"
        f"[dim][x] done   [ ] not started   [~] ongoing / manual[/dim]",
        title="erasure playbook",
        expand=False,
    ))
    for s in STEPS:
        st = status.get(s.probe_key) if s.probe_key else None
        mark = checkbox(st.done if st else None)
        color = "green" if (st and st.done is True) else ("yellow" if (st and st.done is None) else "white")
        body = s.summary
        if st and st.detail:
            body += f"\n\n[dim]Status: {st.detail}[/dim]"
        if s.commands:
            body += "\n\n[cyan]Erasure automates this:[/cyan]"
            for c in s.commands:
                body += f"\n  • {c}"
        if s.manual:
            body += "\n\n[magenta]Do by hand:[/magenta]"
            for m in s.manual:
                body += f"\n  • {m}"
        console.print(Panel(body, title=f"[{color}]{mark} Step {s.number}. {s.title}[/{color}]", expand=False))


@cli.command()
@click.option("--profile", "profile_path", type=click.Path(exists=True), help="Profile JSON (default: ~/.erasure/profile.json)")
@click.option("--priority", type=click.Choice(["crucial", "high", "normal"]), default="crucial", help="Priority filter")
@click.option("--ca-registered/--all", default=True, help="Limit to CA-registered brokers (DROP-covered)")
@click.option("--limit", type=int, default=10, help="Max brokers to scan")
@click.option("--concurrency", type=int, default=3, help="Concurrent Playwright sessions")
def scan(profile_path, priority, ca_registered, limit, concurrency):
    """Capture evidence screenshots of broker opt-out pages. Baseline for verify."""
    import asyncio
    from erasure.brokers.registry import load_brokers, filter_brokers
    from erasure.brokers.scan import scan_brokers
    from erasure.profile import UserProfile

    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if not target.exists():
        console.print(f"[red]No profile at {target}. Run `erasure init` first.[/red]")
        sys.exit(1)

    profile = UserProfile.model_validate_json(target.read_text())
    brokers = filter_brokers(
        load_brokers(),
        priority=priority,
        ca_registered=ca_registered if ca_registered else None,
        limit=limit,
    )

    console.print(f"Scanning {len(brokers)} brokers (priority={priority}, ca_registered={ca_registered}, limit={limit})...")
    scan_id, results = asyncio.run(scan_brokers(brokers, profile, concurrency=concurrency))

    matches = sum(1 for r in results if r.name_match)
    errors = sum(1 for r in results if r.error)
    console.print(Panel(
        f"[bold]Scan complete[/bold]\n\n"
        f"ID: [cyan]{scan_id}[/cyan]\n"
        f"Brokers: {len(results)}  |  Name matches: {matches}  |  Errors: {errors}\n\n"
        f"Artifacts: state/scans/artifacts/\n"
        f"Manifest:  state/scans/{scan_id}.json",
        title="erasure scan",
        expand=False,
    ))


@cli.command()
@click.option("--baseline", required=True, help="Baseline scan ID")
@click.option("--verify", "verify_id", required=True, help="Verify scan ID")
def verify(baseline, verify_id):
    """Diff two scans to flag non-compliant brokers after DROP."""
    from erasure.verify.diff import diff_scans

    summary = diff_scans(baseline, verify_id)
    console.print(Panel(
        f"[green]{summary['resolved']} resolved[/green]  |  "
        f"[red]{summary['persistent']} persistent[/red]  |  "
        f"[yellow]{summary['new']} new[/yellow]  |  "
        f"[dim]{summary['errored']} errored[/dim]\n\n"
        f"State written to state/verify/verify_{baseline}_vs_{verify_id}.json",
        title="erasure verify",
        expand=False,
    ))


@cli.command()
@click.option("--profile", "profile_path", type=click.Path(exists=True))
@click.option("--scan", "scan_id", default=None, help="Scan ID to include (default: latest for --dashboard)")
@click.option("--drop-receipt", type=click.Path(exists=True), help="Path to DROP receipt JSON")
@click.option("--verify-file", type=click.Path(exists=True), help="Path to verify JSON")
@click.option("--output", "output_path", type=click.Path(), help="Output HTML path")
@click.option("--dashboard", is_flag=True, help="Render the Cyber Hygiene Dashboard (checklist + live evidence) instead of the standalone evidence report")
def report(profile_path, scan_id, drop_receipt, verify_file, output_path, dashboard):
    """Generate HTML evidence report (DROP receipt + scan + verify)."""
    from erasure.brokers.scan import SCANS_DIR
    from erasure.profile import UserProfile
    from erasure.report.html import (
        render_report,
        render_dashboard,
        latest_scan_path,
        latest_receipt_path,
        latest_verify_path,
        latest_accounts_path,
        latest_breaches_path,
        latest_emails_path,
    )

    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    profile = UserProfile.model_validate_json(target.read_text()) if target.exists() else None
    profile_name = profile.name if profile else "unknown"

    if dashboard:
        scan_path = (SCANS_DIR / f"{scan_id}.json") if scan_id else latest_scan_path()
        if scan_path is None or not scan_path.exists():
            console.print("[red]No scan found. Run `erasure scan` first.[/red]")
            sys.exit(1)
        receipt_path = Path(drop_receipt) if drop_receipt else latest_receipt_path()
        verify_path_resolved = Path(verify_file) if verify_file else latest_verify_path()
        accounts_path_resolved = latest_accounts_path()
        breaches_path_resolved = latest_breaches_path()
        emails_path_resolved = latest_emails_path()
        out = render_dashboard(
            profile_name=profile_name,
            scan_path=scan_path,
            drop_receipt_path=receipt_path,
            verify_path=verify_path_resolved,
            accounts_path=accounts_path_resolved,
            breaches_path=breaches_path_resolved,
            emails_path=emails_path_resolved,
            out_path=Path(output_path) if output_path else None,
        )
        console.print(Panel(
            f"[green]Dashboard written:[/green] {out}\n\n"
            f"Scan:     {scan_path}\n"
            f"Receipt:  {receipt_path or '—'}\n"
            f"Verify:   {verify_path_resolved or '—'}\n"
            f"Accounts: {accounts_path_resolved or '—'}\n"
            f"Breaches: {breaches_path_resolved or '—'}\n"
            f"Emails:   {emails_path_resolved or '—'}\n\n"
            f"[dim]Open in a browser: file://{out.resolve()}[/dim]",
            title="erasure report --dashboard",
            expand=False,
        ))
        return

    if not scan_id:
        console.print("[red]--scan is required (or pass --dashboard for the live-dashboard view).[/red]")
        sys.exit(1)

    scan_path = SCANS_DIR / f"{scan_id}.json"
    if not scan_path.exists():
        console.print(f"[red]Scan manifest not found: {scan_path}[/red]")
        sys.exit(1)

    out = render_report(
        profile_name=profile_name,
        scan_path=scan_path,
        drop_receipt_path=Path(drop_receipt) if drop_receipt else None,
        verify_path=Path(verify_file) if verify_file else None,
        out_path=Path(output_path) if output_path else None,
    )
    console.print(f"[green]Report written:[/green] {out}")


@cli.command()
@click.option("--interval", type=str, help="Interval for scheduling")
def schedule(interval):
    """Schedule recurring opt-out checks."""
    show_not_implemented("schedule")
    sys.exit(0)


@cli.command()
@click.option("--output-dir", type=click.Path(), help="Directory to save evidence")
def evidence(output_dir):
    """Collect evidence of opt-outs."""
    show_not_implemented("evidence")
    sys.exit(0)


@cli.group()
def drop():
    """California DROP universal opt-out portal."""
    pass


@drop.command("recon")
def drop_recon():
    """Open DROP in real Chrome and snapshot the form (no submission)."""
    import asyncio
    from erasure.drop.client import DropClient

    path = asyncio.run(DropClient().recon())
    console.print(f"[green]Snapshot saved:[/green] {path}")


@drop.command("submit")
@click.option("--profile", "profile_path", required=True, type=click.Path(exists=True))
@click.option("--confirm", is_flag=True, help="Actually submit. Default is dry-run.")
def drop_submit(profile_path, confirm):
    """Submit a DROP deletion request for the given profile."""
    import asyncio
    from erasure.drop.client import DropClient
    from erasure.profile import UserProfile

    profile = UserProfile.model_validate_json(open(profile_path).read())
    receipt = asyncio.run(DropClient().submit(profile, confirm=confirm))
    mode = "SUBMITTED" if confirm else "DRY RUN"
    console.print(Panel(
        f"[bold]{mode}[/bold]\n\nID: {receipt.submission_id}\n"
        f"Status: {receipt.status}\n"
        f"Confirmation: {receipt.confirmation_code or '—'}\n"
        f"Screenshot: {receipt.screenshot_path}",
        title="DROP submission",
    ))


@cli.group()
def accounts():
    """Account-exposure scanning via Sherlock (install: `pipx install sherlock-project`)."""
    pass


@accounts.command("find")
@click.argument("username")
@click.option("--timeout-per-site", type=int, default=15, help="Per-site request timeout in seconds (default: 15)")
@click.option("--overall-timeout", type=int, default=900, help="Overall timeout for the Sherlock run in seconds (default: 900)")
def accounts_find(username, timeout_per_site, overall_timeout):
    """Scan 400+ social networks for USERNAME and save results to state/accounts/."""
    from erasure.accounts.sherlock import (
        SherlockFailed,
        SherlockNotInstalled,
        scan_username,
    )

    try:
        path = scan_username(
            username,
            timeout_per_site=timeout_per_site,
            overall_timeout=overall_timeout,
        )
    except SherlockNotInstalled as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    except SherlockFailed as exc:
        console.print(f"[red]Sherlock failed:[/red]\n{exc}")
        sys.exit(1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    import json as _json

    data = _json.loads(path.read_text(encoding="utf-8"))
    console.print(Panel(
        f"[bold]Account scan complete[/bold]\n\n"
        f"Username: [cyan]{data['username']}[/cyan]\n"
        f"Hits: [bold]{data['found_count']}[/bold]\n"
        f"Manifest: {path}",
        title="erasure accounts find",
        expand=False,
    ))


def _domain_candidate(value):
    """Return VALUE when it can be read as a domain or URL, else None.

    The service argument is matched against entry names and entry domains, but
    a person can type anything. A stray bracket makes the URL parser raise, so
    anything that will not parse is matched by name only.
    """
    from urllib.parse import urlsplit

    if not value:
        return None
    probe = value if "//" in value else "//" + value
    try:
        host = urlsplit(probe).hostname
    except ValueError:
        return None
    return value if host else None


def _contact_path(entry):
    """Where a deletion request for this entry would actually go.

    Used when two entries tie on a domain, so the user can tell which of them
    is the company they hold an account with before any letter is written.
    """
    if entry.email and entry.email_body:
        return f"email to {entry.email}, with wording the service supplies"
    if entry.email:
        return f"email to {entry.email}"
    if entry.url:
        return f"web form at {entry.url}"
    return "no contact path listed"


def _latest_manifest(dir_path):
    if not dir_path.exists():
        return None
    candidates = sorted(dir_path.glob("*.json"))
    return candidates[-1] if candidates else None


@accounts.command("deletion-links")
@click.option("--manifest", "manifest_path", type=click.Path(exists=True), help="Accounts/emails manifest JSON (default: latest in state/)")
@click.option("--include-emails/--no-emails", default=True, help="Also fold in the latest holehe emails manifest")
@click.option("--scrub-only", is_flag=True, help="Only show sites you should scrub before deleting")
@click.option("--directory", "directory_path", type=click.Path(exists=True), default=None, help="Deletion directory JSON to match against (default: the bundled snapshot).")
def accounts_deletion_links(manifest_path, include_emails, scrub_only, directory_path):
    """Map discovered accounts to deletion difficulty + direct delete links."""
    from rich.table import Table
    from erasure.accounts.justdelete import DIRECTORY_PATH, enrich_hits, load_directory
    from erasure.legal.email_templates import DEFAULT_SUBJECT, has_email_template

    hits: list[dict] = []
    if manifest_path:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        hits.extend(data.get("hits", []))
    else:
        acc = _latest_manifest(Path("state/accounts"))
        if acc:
            hits.extend(json.loads(acc.read_text(encoding="utf-8")).get("hits", []))
        if include_emails:
            eml = _latest_manifest(Path("state/emails"))
            if eml:
                hits.extend(json.loads(eml.read_text(encoding="utf-8")).get("hits", []))

    if not hits:
        console.print(
            "[yellow]No account hits found.[/yellow] Run `erasure accounts find <username>` "
            "or `erasure emails find <email>` first, or pass --manifest."
        )
        sys.exit(0)

    directory = load_directory(Path(directory_path) if directory_path else DIRECTORY_PATH)
    enriched = enrich_hits(hits, directory)
    if scrub_only:
        enriched = [e for e in enriched if e.scrub_first]

    diff_color = {
        "easy": "green",
        "medium": "yellow",
        "hard": "red",
        "limited": "cyan",
        "impossible": "magenta",
    }
    table = Table(title="erasure accounts deletion-links")
    for col in ("Site", "Difficulty", "Do first", "Delete link / notes"):
        table.add_column(col, overflow="fold")
    matched_n = 0
    legal_n = 0
    # Counted by service, not by hit: one service can show up twice in a
    # manifest and the summary should not count it twice.
    template_services: set = set()
    for e in enriched:
        if e.matched:
            matched_n += 1
            d = e.matched.difficulty
            color = diff_color.get(d, "white")
            link = e.matched.url or "-"
            note = f"\n[dim]{e.matched.notes}[/dim]" if e.matched.notes else ""
            if e.matched.email:
                subject = e.matched.email_subject or DEFAULT_SUBJECT
                note += f"\n[dim]Email {e.matched.email} (subject: {subject})[/dim]"
                if has_email_template(e.matched):
                    template_services.add(e.matched.name)
                    extra = f" --directory {directory_path}" if directory_path else ""
                    note += (
                        "\n[green]Email template available.[/green] [dim]Fill it with "
                        f"`erasure legal request --service \"{e.matched.name}\"{extra}`[/dim]"
                    )
            if e.scrub_first:
                action = "[red]scrub[/red]"
            elif e.legal_request:
                legal_n += 1
                action = "[cyan]legal request[/cyan]"
            else:
                action = "no"
            table.add_row(e.site, f"[{color}]{d}[/{color}]", action, f"{link}{note}")
        elif not scrub_only:
            table.add_row(
                e.site,
                "[dim]unknown[/dim]",
                "no",
                f"[dim]Not in directory. Try: {e.site} delete account / justdeleteme.xyz[/dim]",
            )

    console.print(table)
    console.print(
        f"[dim]{matched_n}/{len(enriched)} hits mapped to a known deletion path. "
        "Scrub-first sites: overwrite name/email/profile with junk before deleting (deleted != erased).[/dim]"
    )
    if legal_n:
        console.print(
            f"[dim]{legal_n} site(s) delete only for people covered by a privacy law and will ask you "
            "to prove it. Generate the letter with `erasure legal request`.[/dim]"
        )
    if template_services:
        console.print(
            f"[dim]{len(template_services)} site(s) ship the exact wording they want you to email. "
            "`erasure legal request --service NAME` merges your details into it and marks "
            "anything you still have to fill in yourself.[/dim]"
        )


@cli.group()
def breaches():
    """Data-breach exposure checks via HaveIBeenPwned (requires HIBP_API_KEY)."""
    pass


@breaches.command("check")
@click.argument("email")
def breaches_check(email):
    """Check EMAIL against HaveIBeenPwned. Saves manifest to state/breaches/."""
    from erasure.breaches.hibp import (
        HIBPFailed,
        HIBPNotConfigured,
        HIBPRateLimited,
        check_and_save,
    )

    try:
        path = check_and_save(email)
    except HIBPNotConfigured as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    except HIBPRateLimited as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        sys.exit(2)
    except HIBPFailed as exc:
        console.print(f"[red]HIBP failed:[/red] {exc}")
        sys.exit(1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    console.print(Panel(
        f"[bold]Breach check complete[/bold]\n\n"
        f"Email: [cyan]{data['email']}[/cyan]\n"
        f"Breaches: [bold]{data['found_count']}[/bold]\n"
        f"Manifest: {path}",
        title="erasure breaches check",
        expand=False,
    ))


@cli.group()
def emails():
    """Email-registration scanning via holehe (install: `pipx install holehe`)."""
    pass


@emails.command("find")
@click.argument("email")
@click.option("--overall-timeout", type=int, default=900, help="Overall timeout in seconds (default: 900)")
def emails_find(email, overall_timeout):
    """Scan sites for EMAIL registrations and save results to state/emails/."""
    from erasure.emails.holehe import (
        HoleheFailed,
        HoleheNotInstalled,
        scan_email,
    )

    try:
        path = scan_email(email, overall_timeout=overall_timeout)
    except HoleheNotInstalled as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    except HoleheFailed as exc:
        console.print(f"[red]holehe failed:[/red]\n{exc}")
        sys.exit(1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    console.print(Panel(
        f"[bold]Email scan complete[/bold]\n\n"
        f"Email: [cyan]{data['email']}[/cyan]\n"
        f"Hits: [bold]{data['found_count']}[/bold]\n"
        f"Manifest: {path}",
        title="erasure emails find",
        expand=False,
    ))


@cli.group()
def legal():
    """Generate CCPA/GDPR/generic data-deletion request letters."""
    pass


@legal.command("list")
def legal_list():
    """List the deletion-request jurisdictions and what each one cites."""
    from erasure.legal.templates import JURISDICTIONS

    lines = []
    for key, j in JURISDICTIONS.items():
        lines.append(
            f"[cyan]{key}[/cyan] — {j.label}\n"
            f"  Cites: {', '.join(j.statutes)}\n"
            f"  Default deadline: {j.default_deadline_days} days"
        )
    console.print(Panel("\n\n".join(lines), title="erasure legal — jurisdictions", expand=False))


@legal.command("request")
@click.option(
    "--jurisdiction",
    type=click.Choice(["ccpa", "gdpr", "generic"]),
    default="ccpa",
    help="Which law to cite (default: ccpa).",
)
@click.option("--recipient", default=None, help="Broker/company name addressed in the letter.")
@click.option("--service", default=None, help="Service name or domain to look up in the deletion directory. Uses that service's own email template when it has one.")
@click.option("--username", default=None, help="Your username on that service. The profile does not hold one, so pass it here.")
@click.option("--from-email", "from_email", default=None, help="Which of your addresses to send from (default: the first in your profile).")
@click.option("--directory", "directory_path", type=click.Path(exists=True), default=None, help="Deletion directory JSON to look up (default: the bundled snapshot).")
@click.option("--profile", "profile_path", type=click.Path(exists=True), help="Profile JSON (default: ~/.erasure/profile.json)")
@click.option("--deadline-days", type=int, default=None, help="Override the statutory response deadline.")
@click.option("--include-dob", is_flag=True, help="Include date of birth as an identifier (off by default).")
@click.option("--output", "output_path", type=click.Path(), default=None, help="Save the letter to this path.")
@click.option("--save", "save_to_state", is_flag=True, help="Save the letter under state/legal/.")
def legal_request(
    jurisdiction,
    recipient,
    service,
    username,
    from_email,
    directory_path,
    profile_path,
    deadline_days,
    include_dob,
    output_path,
    save_to_state,
):
    """Render a deletion request for the active profile.

    With --service, look the service up in the bundled deletion directory. Some
    services only delete on request by email and ship their own wording, and for
    those this prints a ready to send message with your details merged in.
    Anything the tool cannot fill safely is marked in the text and listed below
    it, so nothing is ever guessed on your behalf. Measured on the 2026-09-07
    snapshot, 84 of the 109 bundled templates come out with every blank filled
    when you pass --username, and 74 without one.

    When two directory entries claim the same domain and would be contacted in
    different places, nothing is written and both are listed, so you choose
    which company receives your details.
    """
    from rich.text import Text

    from erasure.legal.email_templates import has_email_template
    from erasure.legal.generator import render_request, save_request
    from erasure.profile import UserProfile

    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if not target.exists():
        console.print(f"[red]No profile at {target}. Run `erasure init` first.[/red]")
        sys.exit(1)

    profile = UserProfile.model_validate_json(target.read_text())

    entry = None
    if service:
        from erasure.accounts.justdelete import (
            DIRECTORY_PATH,
            load_directory,
            match_candidates,
            match_entry,
        )

        directory = load_directory(Path(directory_path) if directory_path else DIRECTORY_PATH)
        # Passed as both the name and the URL so that a domain works too, since
        # an emails manifest gives you domains rather than display names.
        candidates = match_candidates(service, _domain_candidate(service), directory)
        if not candidates:
            console.print(
                f"[red]No directory entry matches '{service}'.[/red] "
                "Check the name with `erasure accounts deletion-links`, or drop "
                "--service to write a plain jurisdiction letter."
            )
            sys.exit(1)
        # Two entries can claim one domain and belong to different companies.
        # The letter carries the user's name, address and phone number, so when
        # the tied entries would be contacted in different places, nothing is
        # rendered and the user picks. Entries that share one address, or that
        # both offer only a web form, are still broken automatically: there the
        # choice sends the details nowhere different.
        if len(candidates) > 1 and len({c.email for c in candidates}) > 1:
            console.print(
                f"[red]'{service}' matches {len(candidates)} directory entries "
                "that are contacted in different places, so no letter was "
                "written.[/red]"
            )
            for candidate in candidates:
                console.print(f"  {candidate.name}: {_contact_path(candidate)}")
            console.print(
                "[yellow]Run it again with the exact name, for example "
                f"--service \"{candidates[0].name}\".[/yellow]"
            )
            sys.exit(1)
        entry = match_entry(service, _domain_candidate(service), directory)
        console.print(f"[dim]Matched directory entry: {entry.name}[/dim]")
        # Two entries can claim one domain, so say so rather than letting the
        # user assume the one they meant is the one they got.
        mine = {d.lower() for d in entry.domains}
        shared = [
            other.name
            for other in directory
            if other.name != entry.name and mine & {d.lower() for d in other.domains}
        ]
        if shared:
            console.print(
                f"[dim]Also listing a domain of {entry.name}: {', '.join(shared)}. "
                "Pass the exact name if you meant one of those.[/dim]"
            )

    save_key = jurisdiction
    footer = (
        "[dim]Paste this into the broker's contact form or privacy email. "
        "Share only the identifiers needed to locate your record.[/dim]"
    )

    if entry is not None and has_email_template(entry):
        from erasure.legal.email_templates import missing_field_lines, render_email_request

        rendered = render_email_request(
            entry, profile=profile, username=username, from_email=from_email
        )
        text = rendered.as_text()
        title = f"erasure legal request (email template, {entry.name})"
        save_key = "email"
        if not recipient:
            recipient = entry.name
        footer_lines = [
            "[dim]This wording comes from the JustDeleteMe directory, which is what "
            "this service asks people to send.[/dim]"
        ]
        if rendered.from_email:
            footer_lines.append(
                f"[dim]Send it from {rendered.from_email}. Most services match the "
                "request against the address on the account.[/dim]"
            )
        else:
            footer_lines.append(
                "[yellow]Your profile has no email address. Send this from the "
                "address the account is registered under.[/yellow]"
            )
        if rendered.blanks:
            count = len(rendered.blanks)
            word = "spot" if count == 1 else "spots"
            footer_lines.append(f"[yellow]Still to fill in yourself, {count} {word}:[/yellow]")
            for line in missing_field_lines(rendered):
                footer_lines.append(f"[yellow]  {line}[/yellow]")
            if "username" in rendered.missing:
                footer_lines.append("[dim]Pass --username to fill the username.[/dim]")
        else:
            footer_lines.append("[green]Every placeholder was filled.[/green]")
        footer = "\n".join(footer_lines)
    else:
        letter = render_request(
            profile=profile,
            jurisdiction=jurisdiction,
            recipient=recipient or (entry.name if entry else None),
            deadline_days=deadline_days,
            include_dob=include_dob,
        )
        title = f"erasure legal request ({jurisdiction})"
        if entry is not None and entry.email:
            from erasure.legal.email_templates import DEFAULT_SUBJECT

            sender = from_email or (profile.emails[0] if profile.emails else None)
            header = [f"To: {entry.email}"]
            if sender:
                header.append(f"From: {sender}")
            header.append(f"Subject: {entry.email_subject or DEFAULT_SUBJECT}")
            text = "\n".join(header) + "\n\n" + letter
            save_key = "email"
            footer = (
                f"[dim]{entry.name} accepts deletion requests by email but ships no "
                "wording of its own, so this is your jurisdiction letter addressed to "
                "them. Send it from the address on the account.[/dim]"
            )
        else:
            text = letter
            if entry is not None:
                where = entry.url or "the service's own settings page"
                footer = (
                    f"[dim]{entry.name} has no deletion email in the directory. "
                    f"Delete the account at {where}, and use this letter only if that "
                    "route fails.[/dim]"
                )

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        console.print(f"[green]Letter written:[/green] {output_path}")
    if save_to_state:
        saved = save_request(text, jurisdiction=save_key, recipient=recipient)
        console.print(f"[green]Saved to state:[/green] {saved}")

    # Rendered as Text, not markup: a template can contain square brackets such
    # as [NUMBER OR 0] that Rich would otherwise read as a style tag.
    console.print(Panel(Text(text), title=title, expand=False))
    console.print(footer)


@cli.group()
def tracker():
    """Opt-out tracking ledger: site / URL / date / status / follow-up."""
    pass


def _render_tracker_table(ledger, title="erasure tracker"):
    from rich.table import Table

    table = Table(title=title)
    for col in ("Site", "Status", "Requested", "Follow-up", "Method", "Opt-out URL"):
        table.add_column(col, overflow="fold")
    status_color = {
        "pending": "dim",
        "requested": "yellow",
        "confirmed": "green",
        "denied": "red",
        "relisted": "magenta",
    }
    for e in ledger.entries:
        color = status_color.get(e.status, "white")
        table.add_row(
            e.site,
            f"[{color}]{e.status}[/{color}]",
            e.date_requested.isoformat() if e.date_requested else "-",
            e.follow_up_date.isoformat() if e.follow_up_date else "-",
            e.method,
            e.opt_out_url or "-",
        )
    console.print(table)


@tracker.command("init")
@click.option("--priority", type=click.Choice(["crucial", "high", "normal"]), default="crucial")
@click.option("--ca-registered/--all", default=True, help="Limit to CA-registered (DROP-covered) brokers")
@click.option("--limit", type=int, default=25, help="Max brokers to seed")
def tracker_init(priority, ca_registered, limit):
    """Seed the ledger with pending rows from the broker registry."""
    from erasure.brokers.registry import load_brokers, filter_brokers
    from erasure.tracker import load_ledger, save_ledger, seed_from_brokers

    brokers = filter_brokers(
        load_brokers(),
        priority=priority,
        ca_registered=ca_registered if ca_registered else None,
        limit=limit,
    )
    ledger = load_ledger()
    before = len(ledger.entries)
    seed_from_brokers(brokers, ledger)
    path = save_ledger(ledger)
    console.print(f"[green]Seeded {len(ledger.entries) - before} new rows[/green] ({len(ledger.entries)} total). Ledger: {path}")


@tracker.command("add")
@click.argument("site")
@click.option("--url", "opt_out_url", default=None, help="Opt-out URL")
@click.option("--method", default="unknown", help="form | email | portal | unknown")
@click.option("--notes", default=None)
def tracker_add(site, opt_out_url, method, notes):
    """Add a site to the ledger."""
    from erasure.tracker import add_entry, load_ledger, save_ledger

    ledger = load_ledger()
    add_entry(ledger, site, opt_out_url=opt_out_url, method=method, notes=notes)
    save_ledger(ledger)
    console.print(f"[green]Tracked:[/green] {site}")


@tracker.command("update")
@click.argument("site")
@click.option(
    "--status",
    required=True,
    type=click.Choice(["pending", "requested", "confirmed", "denied", "relisted"]),
)
@click.option("--notes", default=None)
def tracker_update(site, status, notes):
    """Update a site's status. 'requested' stamps today + a follow-up date."""
    from erasure.tracker import load_ledger, save_ledger, update_status

    ledger = load_ledger()
    try:
        entry = update_status(ledger, site, status, notes=notes)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    save_ledger(ledger)
    follow = f" (follow up {entry.follow_up_date.isoformat()})" if entry.follow_up_date else ""
    console.print(f"[green]{site} -> {status}[/green]{follow}")


@tracker.command("show")
@click.option("--due", is_flag=True, help="Only show entries whose follow-up date has arrived")
def tracker_show(due):
    """Show the tracking ledger as a table."""
    from erasure.tracker import due_followups, load_ledger, Ledger

    ledger = load_ledger()
    if not ledger.entries:
        console.print("[dim]Ledger is empty. Run `erasure tracker init` to seed it.[/dim]")
        return
    if due:
        items = due_followups(ledger)
        if not items:
            console.print("[green]Nothing due for follow-up.[/green]")
            return
        _render_tracker_table(Ledger(entries=items), title="erasure tracker — due for follow-up")
    else:
        _render_tracker_table(ledger)


@tracker.command("export")
@click.option("--output", "output_path", type=click.Path(), default=None, help="CSV path (default: state/tracker/ledger.csv)")
def tracker_export(output_path):
    """Export the ledger to CSV."""
    from erasure.tracker import export_csv, load_ledger

    ledger = load_ledger()
    path = export_csv(ledger, Path(output_path) if output_path else None)
    console.print(f"[green]Exported {len(ledger.entries)} rows:[/green] {path}")


@drop.command("residency-review")
@click.option("--profile", "profile_path", required=True, type=click.Path(exists=True))
@click.option(
    "--reason",
    default=(
        "I am a California resident. The Identity Gateway could not verify "
        "my identity automatically. Please review my residency and process "
        "my deletion request under CCPA §1798.105."
    ),
    help="Text to enter into the 'How can we help?' field.",
)
def drop_residency_review(profile_path, reason):
    """File the CA DROP residency-review fallback form."""
    import asyncio
    from erasure.drop.client import DropClient
    from erasure.profile import UserProfile

    profile = UserProfile.model_validate_json(open(profile_path).read())
    receipt = asyncio.run(DropClient().file_residency_review(profile, reason=reason))
    console.print(Panel(
        f"[bold]Residency review submitted[/bold]\n\n"
        f"ID: {receipt.submission_id}\n"
        f"Status: {receipt.status}\n"
        f"Screenshot: {receipt.screenshot_path}\n"
        f"Notes: {receipt.notes}",
        title="DROP residency review",
    ))


@drop.command("status")
def drop_status():
    """List DROP submission receipts."""
    from erasure.drop.client import DropClient

    receipts = DropClient.list_receipts()
    if not receipts:
        console.print("[dim]No DROP submissions yet.[/dim]")
        return
    for r in receipts:
        console.print(f"{r.submission_id}  {r.status:13}  {r.submitted_at.isoformat()}  {r.confirmation_code or '—'}")


if __name__ == "__main__":
    cli()
