# PREDOC Tracker

A small personal Python app that checks [PREDOC.org](https://www.predoc.org/opportunities) for pre-doctoral research opportunities and sends relevant new or changed postings to Telegram, based on configurable research interests.

GitHub Actions runs the app twice a week and keeps only a small record of delivered alerts to prevent duplicates. Telegram serves as the readable archive. The original local `check` command also supports SQLite history and saved source pages.

PREDOC.org does not provide reliable posting dates, so the app records when it first observes each listing.

## Setup

Use Python 3.11 or newer. From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
predoc-tracker init-db
```

Activate the virtual environment again whenever you open a new terminal to work on the app.

## Configuration

On a fresh checkout, copy the example and edit your interests:

```bash
cp config/interests.example.yaml config/interests.yaml
```

In `config/interests.yaml`, keywords and matching region, research-area, and employer-type tags add points. `priority_keywords` carry more weight; `exclude_keywords` reject a posting outright. A posting qualifies when its score reaches `min_score`. The example file documents the scoring and available settings.

### Telegram

1. Create a bot with Telegram's **@BotFather** and save its token.
2. Add the bot to your private group and send a message in the group. For a channel, add the bot as an administrator and publish a message.
3. Load the token in your terminal and request recent updates:

   ```bash
   export PREDOC_TELEGRAM_BOT_TOKEN="your-token-from-BotFather"
   curl "https://api.telegram.org/bot$PREDOC_TELEGRAM_BOT_TOKEN/getUpdates"
   ```

4. Find your group or channel's `chat.id` in the response and set it:

   ```bash
   export PREDOC_TELEGRAM_CHAT_ID="your-chat-id"
   ```

5. Add `telegram` to `notifications.channels` in `config/interests.yaml`, keeping `console` if you also want terminal output. Test delivery:

   ```bash
   predoc-tracker test-telegram
   ```

To reuse your credentials, copy `.env.example` to `.env` and fill in the values. Load it before running the app:

```bash
source .env
```

The app does not load `.env` automatically. Credentials, personal interest rules, and generated runtime data are ignored by Git and stay local.

## Running the app

```bash
predoc-tracker check             # Fetch listings, save changes, and send matching alerts
predoc-tracker preview-matches   # Show matches from stored active listings without sending
predoc-tracker export-csv        # Export the latest known listings
```

`preview-matches` uses the last saved data; it does not fetch the website. To fetch and store listings without sending alerts, use `predoc-tracker check --no-notify`. This still records changes, so a later check will not automatically alert for those same changes.

Default output locations:

- `data/predoc.sqlite`: listings, observations, changes, and notification records.
- `data/raw/`: compressed copies of fetched pages.
- `data/exports/opportunities_latest.csv`: latest CSV export.

## How it works

Each check fetches the opportunities page, saves its HTML, and parses the listing cards. It compares them with the database to identify new, updated, reactivated, and disappeared listings. New, updated, or reactivated listings that match your rules become alerts; notification records help prevent repeat messages.

The database keeps each scrape and its observations alongside the latest state of each listing. This preserves the evidence behind detected changes.

## Development

The code lives in `src/predoc_tracker/`:

| File | Responsibility |
| --- | --- |
| `cli.py` | Commands and arguments |
| `pipeline.py` | Local checks with scrape history |
| `monitor.py` | Scheduled checks with only a notification ledger |
| `fetch.py`, `parse.py` | Downloads the page and extracts listings |
| `storage.py` | SQLite schema, change detection, and CSV export |
| `match.py`, `settings.py` | Interest scoring and configuration |
| `notify.py` | Console and Telegram messages |
| `utils.py` | Small shared helpers |

Run the existing tests after changing the code:

```bash
python -m unittest discover -s tests
```

The tests cover parsing, matching, duplicate prevention, and Telegram failure recovery. To run the app directly from source without installing the package:

```bash
PYTHONPATH=src python -m predoc_tracker check --no-notify
```

## Scheduled checks on GitHub Actions

The workflow in `.github/workflows/monitor.yml` runs **Mondays and Thursdays at 8 a.m. Bogotá time** (13:00 UTC). GitHub may delay scheduled runs. You can also start a check under **Actions → Check PREDOC postings → Run workflow**.

Scheduled checks use `predoc-tracker monitor`: no SQLite database or page archives. Only IDs and fingerprints of successfully notified, currently listed postings are retained in `notification_state.json` on the separate `codex/notification-state` branch. Do not delete that branch: losing the record can cause repeat alerts. A listing disappearing and later returning can alert again.

Three repository secrets supply the private configuration:

- `PREDOC_TELEGRAM_BOT_TOKEN`
- `PREDOC_TELEGRAM_CHAT_ID`
- `PREDOC_INTERESTS_YAML`: the contents of your interest configuration, with `telegram` as the notification channel.

Telegram messages are paced and rate-limit responses retried. Each confirmed delivery is recorded; the workflow saves partial progress even when a later delivery fails. A crash or failure while saving that record can still cause repeats. Check failed runs in the Actions tab.

Runs have a 10-minute limit and cannot overlap. About 8–10 scheduled runs per month would use at most 80–100 execution minutes if each hit that limit, plus any manual runs. GitHub's private-repository allowance is shared across your account; standard runners for public repositories are free.
