# PREDOC Tracker

PREDOC Tracker monitors the public PREDOC opportunities page and stores each scrape in a way that supports both alerts and later research on the pre-doctoral research assistant market.

The project has two purposes:

- Notify a busy applicant when relevant new or changed opportunities appear.
- Build a longitudinal dataset with enough provenance to support later analysis.

The target source for v0.0.1 is:

```text
https://www.predoc.org/opportunities
```

## Why This Design

The opportunities page currently returns the listings inside the server-rendered HTML. The dropdown filters on the site only show and hide cards that are already present in the page. Because there is no separate public JSON endpoint for the opportunity list, this project fetches the HTML directly, archives the raw page, parses the cards, and stores structured observations.

This is intentionally a small command-line system rather than a web app. The main workflow is automatic monitoring, not browsing a dashboard.

## System Purposes

### Monitoring

The tracker is designed to run on a schedule, for example once or twice daily. Each run:

1. Fetches the PREDOC opportunities page.
2. Archives the raw HTML with a timestamp and hash.
3. Parses opportunity cards into structured records.
4. Deduplicates postings across runs.
5. Records new, updated, reactivated, and disappeared postings.
6. Matches new or changed postings against user interest rules.
7. Sends notification-ready alerts.

### Research Data Collection

The tracker preserves provenance rather than only keeping the latest state. It stores:

- The raw HTML fetched on every run.
- The timestamp and source URL for every scrape.
- A hash of each raw page.
- Parsed observations for every opportunity on every run.
- A canonical opportunity table with `first_seen_at`, `last_seen_at`, and active status.
- Event records for changes over time.

The website does not expose a reliable posting date. The defensible substitute is an observation window:

- `first_seen_at` is the first scrape where a posting appears.
- The previous scrape time is the lower-bound evidence that it was not yet observed.
- The first scrape time is the upper bound for when it appeared.

More frequent scheduled runs make that estimated posting window narrower.

## v0.0.1 Features

- Python CLI project.
- SQLite database for operational and research storage.
- Gzipped raw HTML archive.
- PREDOC opportunity parser.
- Canonical opportunity IDs.
- Event detection for new, updated, reactivated, and disappeared postings.
- Configurable interest rules in YAML.
- Console notifications.
- Optional Telegram notifications through environment variables.
- CSV export for analysis.

## Installation

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The fetcher uses Python `requests` first. On macOS certificate-store failures, it falls back to system `curl`, which is available by default on macOS and in GitHub Actions.

Initialize the database:

```bash
predoc-tracker init-db
```

## Configuration

Copy the example config and edit your interests:

```bash
cp config/interests.example.yaml config/interests.yaml
```

`config/interests.yaml` is ignored by git because it can reveal your personal research interests.

The config supports:

- `include_keywords`
- `priority_keywords`
- `exclude_keywords`
- `regions`
- `research_areas`
- `employer_types`
- `min_score`

For Telegram notifications, set:

```bash
export PREDOC_TELEGRAM_BOT_TOKEN="..."
export PREDOC_TELEGRAM_CHAT_ID="..."
```

Then add `telegram` to `notifications.channels` in `config/interests.yaml`.

## Usage

Run a check:

```bash
predoc-tracker check
```

Run without sending notifications:

```bash
predoc-tracker check --no-notify
```

Export the latest opportunity table:

```bash
predoc-tracker export-csv
```

The default runtime files are:

- SQLite database: `data/predoc.sqlite`
- Raw HTML archive: `data/raw/`
- CSV exports: `data/exports/`

## Scheduling

For a laptop-based setup, schedule `predoc-tracker check` with cron or launchd.

For a cloud-based setup, GitHub Actions is a good next step because it can run even when the laptop is off. That requires storing notification credentials as repository secrets.

## Database Tables

The v0.0.1 schema includes:

- `scrape_runs`: one row per run.
- `raw_pages`: source URL, raw archive path, hash, and byte count.
- `opportunities`: canonical deduplicated opportunities.
- `opportunity_observations`: parsed opportunity state on each run.
- `opportunity_events`: new, updated, reactivated, and disappeared events.
- `alerts_sent`: deduplication log for notifications.

## Development

Run the test suite with:

```bash
python -m unittest discover -s tests
```

Run the package module directly without installing:

```bash
PYTHONPATH=src python -m predoc_tracker check --no-notify
```
