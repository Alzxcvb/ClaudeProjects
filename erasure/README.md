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
erasure legal request --recipient "Spokeo" --jurisdiction ccpa

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
Turn account-discovery hits into action. Matches the sites found by `accounts find` / `emails find` against a bundled directory of 2,600+ services from [JustDeleteMe](https://justdeleteme.xyz) (MIT), attaching each one's deletion difficulty, a direct delete URL, and the deletion email template where a service only accepts requests that way. Two flags come out of the difficulty rating:

- `hard` and `impossible` are flagged **scrub first**: overwrite the profile with a junk name, an alias email, and blank fields before you delete, since some companies retain "deleted" data.
- `limited` is flagged **legal request**: the service deletes only for people covered by a privacy law and will ask for proof. Generate that letter with `erasure legal request`.

Of the 2,612 services in the bundled snapshot, 479 give a deletion email address and 109 of those also ship the exact wording the service wants to receive. Rows that carry wording are marked **Email template available** and print the command that fills it in.

**Usage:**
```bash
erasure accounts deletion-links [--manifest PATH] [--no-emails] [--scrub-only] [--directory PATH]
```

The directory ships as a committed snapshot so the command works offline. Refresh it from upstream with `python3 scripts/refresh_deletion_directory.py`; local additions live in `erasure/accounts/deletion_directory_overrides.json` and are layered on top.

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
erasure legal list                          # list what each regime cites
erasure legal request --recipient "Spokeo" --jurisdiction ccpa [--save] [--output letter.txt]
erasure legal request --service "123RF" --username yourhandle   # use that service's own email template
```

#### Deletion emails for services that only accept email

Some services will not delete an account from a settings page at all. They act only on an email, and the JustDeleteMe directory ships the wording they ask people to send. Pass `--service NAME` and Erasure looks the service up, merges your profile into that wording, and prints a message with `To`, `From` and `Subject` already set.

The dataset does not use named tokens. Each contributor wrote the blanks by hand, so they appear as `XXXXXX` runs, `<YOUR_EMAIL>`, an all caps note such as `[NUMBER OR 0]`, or an instruction such as `(put your name here)`. Erasure reads the words just before each blank to work out what it stands for, and fills it only when that reading is unambiguous and you actually supplied the value.

Your full name, email address and phone number come from your profile. A username is not part of a profile, so pass `--username`. Use `--from-email` to send from an address other than the first one in your profile.

Anything that cannot be filled safely is left in the text as a visible `<<FILL IN: ...>>` marker and listed underneath, so you can see exactly what to type. A reason for leaving, an account or customer number, and a passport number are never filled in automatically even when your profile holds something similar. Nothing is ever guessed.

`--service` also works for the other two cases. When the directory has an address but no wording, you get your jurisdiction letter addressed to that address. When it has no address at all, you get the letter plus a pointer to the service's own delete page.

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
  accounts/     # Sherlock username scan + JustDeleteMe deletion directory
  emails/       # holehe email-exposure scan
  breaches/     # HaveIBeenPwned breach checks
  report/       # Standalone HTML report + Cyber Hygiene Dashboard injection
  scheduler/    # Recurring scans (planned)
  data/         # Broker registry data (gitignored runtime state in state/)
```

## License

MIT License — see [LICENSE](LICENSE) for details.
