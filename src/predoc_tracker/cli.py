from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_check
from .settings import load_config
from .match import MatchResult, match_record
from .notify import Alert, send_telegram
from .storage import (
    connect,
    export_latest_csv,
    fetch_latest_observations,
    initialize_database,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="predoc-tracker",
        description="Monitor PREDOC opportunities and preserve scrape provenance.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Fetch, parse, store, and alert.")
    check_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/interests.yaml"),
        help="Path to YAML config. Defaults to config/interests.yaml.",
    )
    check_parser.add_argument("--no-notify", action="store_true", help="Skip notifications.")

    init_db_parser = subparsers.add_parser("init-db", help="Create the SQLite schema.")
    init_db_parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/predoc.sqlite"),
        help="SQLite database path.",
    )

    export_parser = subparsers.add_parser(
        "export-csv", help="Export the latest known opportunities to CSV."
    )
    export_parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/predoc.sqlite"),
        help="SQLite database path.",
    )
    export_parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/exports/opportunities_latest.csv"),
        help="CSV output path.",
    )

    preview_parser = subparsers.add_parser(
        "preview-matches",
        help="Preview current active opportunities matched by a config without notifying.",
    )
    preview_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/interests.yaml"),
        help="Path to YAML config. Defaults to config/interests.yaml.",
    )
    preview_parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of matched records to print.",
    )

    test_telegram_parser = subparsers.add_parser(
        "test-telegram",
        help="Send one Telegram test message using the configured env vars.",
    )
    test_telegram_parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/interests.yaml"),
        help="Path to YAML config. Defaults to config/interests.yaml.",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        config = load_config(args.config)
        summary = run_check(config, notify=not args.no_notify)
        print()
        print(f"Run: {summary.run_id}")
        print(f"Observed opportunities: {summary.observed_count}")
        print(f"New/updated/reactivated events: {summary.event_count}")
        print(f"Matching alerts: {summary.alert_count}")
        print(f"Database: {summary.database_path}")
        return 0

    if args.command == "init-db":
        connection = connect(args.db)
        try:
            initialize_database(connection)
        finally:
            connection.close()
        print(f"Initialized database: {args.db}")
        return 0

    if args.command == "export-csv":
        connection = connect(args.db)
        try:
            count = export_latest_csv(connection, args.out)
        finally:
            connection.close()
        print(f"Exported {count} opportunities to {args.out}")
        return 0

    if args.command == "preview-matches":
        config = load_config(args.config)
        connection = connect(config.database_path)
        try:
            rows = fetch_latest_observations(connection)
        finally:
            connection.close()

        matched = []
        for row in rows:
            result = match_record(row, config.interests)
            if result.matched:
                matched.append((result.score, row, result))
        matched.sort(key=lambda item: (-item[0], item[1]["title"]))

        print(f"Active opportunities: {len(rows)}")
        print(f"Matched opportunities: {len(matched)}")
        for index, (score, row, result) in enumerate(matched[: args.limit], start=1):
            reasons = ", ".join(result.reasons) if result.reasons else "no reasons"
            print()
            print(f"{index}. [{score}] {row['title']}")
            print(f"   Institution: {row['institution'] or 'Unknown'}")
            print(f"   Deadline: {row['deadline_text'] or 'Unknown'}")
            print(f"   Reasons: {reasons}")
            if row["apply_url"]:
                print(f"   Apply: {row['apply_url']}")
        return 0

    if args.command == "test-telegram":
        config = load_config(args.config)
        send_telegram(
            [
                Alert(
                    event_type="test",
                    title="PREDOC Tracker Telegram test",
                    apply_url="https://www.predoc.org/opportunities",
                    institution="PREDOC Tracker",
                    deadline_text="Not applicable",
                    fields_text="Notification setup",
                    match=MatchResult(
                        matched=True,
                        score=999,
                        reasons=["telegram setup test"],
                    ),
                )
            ],
            bot_token_env=config.notifications.telegram_bot_token_env,
            chat_id_env=config.notifications.telegram_chat_id_env,
        )
        print("Telegram test message sent.")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
