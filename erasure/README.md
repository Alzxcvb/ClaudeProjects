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

# Scan major data brokers for your information
erasure scan

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

### `erasure report`
Generate a compliance report with scan results, opt-out status, and evidence artifacts.

**Usage:**
```bash
erasure report [--format json|html|pdf] [--output FILE]
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
  brokers/    # Broker definitions and metadata
  browser/    # Playwright automation and interaction
  verify/     # Verification logic for deletion confirmation
  legal/      # GDPR/CCPA compliance and evidence generation
  scheduler/  # Cron job management
  report/     # Report generation and formatting
  data/       # Local data storage (encrypted)
```

## License

MIT License — see [LICENSE](LICENSE) for details.
