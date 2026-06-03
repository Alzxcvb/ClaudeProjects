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
@click.option("--profile", "profile_path", type=click.Path(exists=True), help="Profile JSON (default: ~/.erasure/profile.json)")
@click.option("--deadline-days", type=int, default=None, help="Override the statutory response deadline.")
@click.option("--include-dob", is_flag=True, help="Include date of birth as an identifier (off by default).")
@click.option("--output", "output_path", type=click.Path(), default=None, help="Save the letter to this path.")
@click.option("--save", "save_to_state", is_flag=True, help="Save the letter under state/legal/.")
def legal_request(jurisdiction, recipient, profile_path, deadline_days, include_dob, output_path, save_to_state):
    """Render a deletion-request letter for the active profile."""
    from erasure.legal.generator import render_request, save_request
    from erasure.profile import UserProfile

    target = Path(profile_path) if profile_path else DEFAULT_PROFILE_PATH
    if not target.exists():
        console.print(f"[red]No profile at {target}. Run `erasure init` first.[/red]")
        sys.exit(1)

    profile = UserProfile.model_validate_json(target.read_text())
    text = render_request(
        profile=profile,
        jurisdiction=jurisdiction,
        recipient=recipient,
        deadline_days=deadline_days,
        include_dob=include_dob,
    )

    if output_path:
        Path(output_path).write_text(text, encoding="utf-8")
        console.print(f"[green]Letter written:[/green] {output_path}")
    if save_to_state:
        saved = save_request(text, jurisdiction=jurisdiction, recipient=recipient)
        console.print(f"[green]Saved to state:[/green] {saved}")

    console.print(Panel(text, title=f"erasure legal request ({jurisdiction})", expand=False))
    console.print(
        "[dim]Paste this into the broker's contact form or privacy email. "
        "Share only the identifiers needed to locate your record.[/dim]"
    )


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
