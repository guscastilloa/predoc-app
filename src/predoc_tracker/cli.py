from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_check
from .settings import load_config
from .storage import connect, export_latest_csv, initialize_database


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

    parser.error(f"Unknown command: {args.command}")
    return 2
