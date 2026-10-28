# Changelog

All notable changes to this project will be documented here.

The project follows semantic versioning while it is small: `0.x` releases may still change internal schemas, but each change should be documented.

## [Unreleased]

## [0.0.2] - 2026-10-27

### Added

- Telegram receipts after every successful scheduled check, including checks with no new alerts. Receipts show posting and alert counts, Bogotá time, and app version; they are sent only after the notification record is saved to GitHub.
- Twice-weekly GitHub Actions checks with private configuration supplied through repository secrets.
- Lightweight `monitor` mode that retains only notified posting IDs and fingerprints, without SQLite history or source archives.
- Tests for duplicate prevention, partial delivery recovery, rate limits, and successful check receipts.

### Added

- Added `preview-matches` for checking current active opportunities against a private config without sending notifications.
- Added `test-telegram` for verifying Telegram credentials and chat routing.
- Added `.env.example` for local Telegram environment variables.

### Changed

- Paced Telegram delivery and retry rate-limit responses, recording lightweight notifications only after successful delivery.
- Reorganized the README for contributors and documented scheduled operation.

- Improved parser handling for postings that use short `Field:` or `Fields:` labels.
- Expanded the example config with visa-related exclusion examples.

## [0.0.1] - 2026-04-29

### Added

- Initialized the repository as a Python CLI project.
- Added PREDOC opportunities scraping from `https://www.predoc.org/opportunities`.
- Added raw HTML archival with gzip compression.
- Added HTML parsing for opportunity cards, links, institutions, researchers, fields, deadlines, visa notes, and site filter tags.
- Added SQLite schema for scrape runs, raw pages, canonical opportunities, observations, events, and sent-alert records.
- Added event detection for new, updated, reactivated, and disappeared postings.
- Added YAML-based interest rules.
- Added console notifications.
- Added optional Telegram notifications using environment variables.
- Added CSV export for latest opportunity records.
- Added initial unit tests for parsing and matching.

### Notes

- The site does not expose a posting date, so v0.0.1 records `first_seen_at` and `last_seen_at` as provenance-backed observation timestamps.
- The opportunities list appears to be server-rendered HTML, so v0.0.1 intentionally scrapes and archives HTML rather than depending on a private API.

## Future ideas

- Notifications for failed or missing scheduled checks.
- More reliable deadline and institution extraction.
- Optional digest formatting for job alerts.
