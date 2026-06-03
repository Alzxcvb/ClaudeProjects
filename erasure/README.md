# erasure

Open-source data-broker opt-out tool. Automate your privacy: scan which data brokers have your information, generate opt-out requests, and verify deletion across hundreds of brokers.

## Overview

Data brokers collect and sell personal information at scale. `erasure` streamlines the labor-intensive process of opting out: it identifies which brokers have your data, submits deletion requests via automated browser interactions, and generates compliance reports for GDPR, CCPA, and other regulations.

## Installation

Requires Python 3.11+.

```bash
git clone https://github.com/your-org/erasure.git
cd erasure
pip install -e .
```

## Quick Start

```bash
# Initialize your profile (name, email, phone, address)
erasure init

# See the whole footprint wipe as a personalized checklist (start here)
erasure playbook

# Scan major data brokers for your information
erasure scan

# Build a tracking sheet of every broker opt-out
erasure tracker init

# Draft a statute-citing deletion letter for one broker
erasure legal request --to "Spokeo" --jurisdiction ccpa

# Submit opt-out requests to identified brokers
erasure opt-out

# Generate a compliance report
erasure report

# Schedule recurring scans
erasure schedule --interval monthly

# Verify deletion after opt-out requests
erasure verify
```

## CLI Commands

### `erasure init`
Initialize your personal profile and storage credentials. Sets up keyring integration for secure credential storage.

**Usage:**
```bash
erasure init [--email EMAIL] [--phone PHONE] [--name NAME]
```

### `erasure scan`
Scan configured data brokers to detect if your personal information is present.

**Usage:**
```bash
erasure scan [--brokers LIST] [--parallel N]
```

### `erasure opt-out`
Submit automated opt-out requests to identified brokers using headless browser automation.

**Usage:**
```bash
erasure opt-out [--brokers LIST] [--dry-run]
```

### `erasure accounts find`
Scan 400+ social networks for a username via the [Sherlock](https://github.com/sherlock-project/sherlock) OSINT tool. Erasure runs Sherlock as an external subprocess — install it separately with `pipx install sherlock-project` to keep its dependency tree (pandas, numpy, openpyxl) out of Erasure's environment. Results are persisted as an `AccountsManifest` JSON in `state/accounts/` and show up in `erasure report --dashboard`.

**Usage:**
```bash
erasure accounts find USERNAME [--timeout-per-site SECONDS] [--overall-timeout SECONDS]
```

### `erasure accounts deletion-links`
Turn account-discovery hits into action. Matches the sites found by `accounts find` / `emails find` against a bundled directory of services (adapted from [justdelete.me](https://justdeleteme.xyz)), attaching each one's deletion difficulty and a direct delete URL. Sites rated `hard` or `impossible` are flagged to scrub first (junk name, alias email, blanked profile) before you delete, since some companies retain "deleted" data.

**Usage:**
```bash
erasure accounts deletion-links [--manifest PATH] [--no-emails] [--scrub-only]
```

### `erasure breaches check`
Check whether an email address appears in any known data breach via [HaveIBeenPwned](https://haveibeenpwned.com). Requires a HIBP API key (`$3.95/mo` minimum) — get one at [haveibeenpwned.com/API/Key](https://haveibeenpwned.com/API/Key) and export `HIBP_API_KEY`. Results persist as a `BreachesManifest` JSON in `state/breaches/` and show up in `erasure report --dashboard`.

**Usage:**
```bash
export HIBP_API_KEY=your-key-here
erasure breaches check EMAIL
```

### `erasure emails find`
Scan 120+ sites to see where an email address has been used to sign up, via the [holehe](https://github.com/megadose/holehe) OSINT tool. Install it separately with `pipx install holehe`. Results persist as an `EmailsManifest` JSON in `state/emails/` and show up in `erasure report --dashboard`.

**Usage:**
```bash
erasure emails find EMAIL [--overall-timeout SECONDS]
```

### `erasure report`
Generate a compliance report with scan results, opt-out status, and evidence artifacts.

**Usage:**
```bash
erasure report --scan SCAN_ID [--drop-receipt PATH] [--verify-file PATH] [--output FILE]

# Or render the Cyber Hygiene Dashboard with live evidence injected
# (auto-picks latest scan / receipt / verify from state/):
erasure report --dashboard [--output FILE]
```

### `erasure legal`
Draft statute-citing deletion / opt-out letters off your profile. A request that names CCPA section 1798.105 or GDPR Article 17 and sets a response clock moves far faster than a polite ask. The generator excludes your date of birth by default and tells the recipient not to use the supplied identifiers to build a new profile. Letters are plain-text, ready to paste into a broker's contact form or privacy email.

**Usage:**
```bash
erasure legal jurisdictions                 # list what each regime cites
erasure legal request --to "Spokeo" --jurisdiction ccpa --type both [--output letter.txt]
```

### `erasure tracker`
The structured version of the thread's tracking sheet: one row per site with opt-out URL, method, date requested, status, and an auto-computed follow-up date (45 days, the CCPA window). Seed it from the broker registry, mark requests as you send them, and export to CSV. Because brokers relist you within 6 to 12 months, `--due` surfaces the rows whose follow-up has come around.

**Usage:**
```bash
erasure tracker init                        # seed from the broker registry
erasure tracker add "Spokeo" --url ...      # add one site
erasure tracker update "Spokeo" --status requested
erasure tracker show [--due]                # full ledger, or only follow-ups due
erasure tracker export [--output ledger.csv]
```

### `erasure playbook`
The whole footprint wipe as one personalized, stateful checklist (thread steps 1 through 9). It marks which steps Erasure automates with the exact command to run, reads `state/` to report how far you have gotten on each, and gives concrete instructions plus links for the steps that stay manual (Google's "Results about you" tool, scrub-before-delete, search-result suppression, email aliases, quarterly re-checks). Start here.

**Usage:**
```bash
erasure playbook [--output plan.md]
```

### `erasure schedule`
Configure recurring scans and opt-outs on a schedule.

**Usage:**
```bash
erasure schedule --interval daily|weekly|monthly [--start-time HH:MM]
```

### `erasure verify`
Follow up on submitted opt-out requests and verify successful deletion.

**Usage:**
```bash
erasure verify [--brokers LIST]
```

## Architecture

```
erasure/
  brokers/      # Broker registry (586 brokers), Playwright baseline scan
  drop/         # California DROP portal client (Delete Act / SB 362)
  verify/       # Diff two scans to flag brokers that did not delete
  legal/        # CCPA / GDPR / generic deletion-letter generator
  tracker.py    # Opt-out tracking ledger + CSV export
  playbook.py   # The stateful 9-step privacy checklist
  accounts/     # Sherlock username scan + justdelete.me deletion directory
  emails/       # holehe email-exposure scan
  breaches/     # HaveIBeenPwned breach checks
  report/       # Standalone HTML report + Cyber Hygiene Dashboard injection
  scheduler/    # Recurring scans (planned)
  data/         # Broker registry data (gitignored runtime state in state/)
```

## License

MIT License — see [LICENSE](LICENSE) for details.
