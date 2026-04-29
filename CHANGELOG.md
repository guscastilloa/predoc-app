# Changelog

All notable changes to this project will be documented here.

The project follows semantic versioning while it is small: `0.x` releases may still change internal schemas, but each change should be documented.

## [Unreleased]

### Added

- Added `preview-matches` for checking current active opportunities against a private config without sending notifications.
- Added `test-telegram` for verifying Telegram credentials and chat routing.
- Added `.env.example` for local Telegram environment variables.

### Changed

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

## Planned

## [0.0.2] - Alert Quality

- Add a daily digest mode separate from immediate alerts.
- Add stronger alert deduplication across notification channels.
- Add clearer alert severity levels such as `high`, `medium`, and `watch`.
- Add richer Telegram formatting.
- Add email notification support through SMTP.

## [0.0.3] - Scheduling

- Add a GitHub Actions workflow for scheduled scraping.
- Document required repository secrets for Telegram or email.
- Add a local launchd or cron example for macOS.
- Add safer behavior for failed network runs so the system reports failures without corrupting the database.

## [0.0.4] - Data Quality

- Improve field extraction for postings with irregular formatting.
- Add normalized deadline parsing while keeping original deadline text.
- Add normalized institution names while preserving raw institution text.
- Add observation-window fields for estimated posting intervals.
- Add parser confidence flags for records that need manual review.

## [0.0.5] - Research Exports

- Add Parquet export for Python/R analysis workflows.
- Add export of full observation history, not only latest records.
- Add event-level exports for entry, update, and disappearance analysis.
- Add a data dictionary describing every exported variable.

## [0.1.0] - Stable Personal Monitor

- Stabilize the SQLite schema for routine use.
- Add migration support for future schema changes.
- Add installation and scheduling documentation tested end to end.
- Add a sample analysis notebook.
- Treat the tool as reliable enough for daily personal monitoring.
