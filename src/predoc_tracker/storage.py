from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .parse import OpportunityRecord, PARSER_VERSION
from .utils import ensure_parent, utc_now_iso


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class IngestEvent:
    opportunity_id: str
    event_type: str
    title: str
    apply_url: str
    content_hash: str
    details: dict[str, str]


@dataclass(frozen=True)
class IngestResult:
    run_id: str
    fetched_at: str
    observed_count: int
    events: list[IngestEvent]


def connect(database_path: Path) -> sqlite3.Connection:
    ensure_parent(database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scrape_runs (
            run_id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            http_status INTEGER NOT NULL,
            parser_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS raw_pages (
            run_id TEXT PRIMARY KEY REFERENCES scrape_runs(run_id),
            source_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            raw_path TEXT NOT NULL,
            html_hash TEXT NOT NULL,
            byte_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            opportunity_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL UNIQUE,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            first_run_id TEXT NOT NULL,
            last_run_id TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            latest_content_hash TEXT NOT NULL,
            title TEXT NOT NULL,
            apply_url TEXT NOT NULL,
            institution TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS opportunity_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL REFERENCES scrape_runs(run_id),
            opportunity_id TEXT NOT NULL REFERENCES opportunities(opportunity_id),
            observed_at TEXT NOT NULL,
            title TEXT NOT NULL,
            apply_url TEXT NOT NULL,
            researchers TEXT NOT NULL,
            institution TEXT NOT NULL,
            fields_text TEXT NOT NULL,
            deadline_text TEXT NOT NULL,
            visa_text TEXT NOT NULL,
            note_text TEXT NOT NULL,
            body_text TEXT NOT NULL,
            region_tags_json TEXT NOT NULL,
            research_area_tags_json TEXT NOT NULL,
            employer_type_tags_json TEXT NOT NULL,
            other_tags_json TEXT NOT NULL,
            class_list_json TEXT NOT NULL,
            card_html TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            UNIQUE(run_id, opportunity_id)
        );

        CREATE TABLE IF NOT EXISTS opportunity_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL REFERENCES opportunities(opportunity_id),
            run_id TEXT NOT NULL REFERENCES scrape_runs(run_id),
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            details_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts_sent (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id TEXT NOT NULL REFERENCES opportunities(opportunity_id),
            content_hash TEXT NOT NULL,
            alert_key TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            channel TEXT NOT NULL,
            match_score INTEGER NOT NULL,
            match_reasons_json TEXT NOT NULL,
            UNIQUE(opportunity_id, content_hash, alert_key, channel)
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    connection.commit()


def ingest_run(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    source_url: str,
    fetched_at: str,
    http_status: int,
    raw_path: Path,
    html_hash: str,
    byte_count: int,
    records: list[OpportunityRecord],
) -> IngestResult:
    initialize_database(connection)
    events: list[IngestEvent] = []
    seen_ids = {record.opportunity_id for record in records}

    with connection:
        connection.execute(
            """
            INSERT INTO scrape_runs(
                run_id, source_url, fetched_at, http_status, parser_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, source_url, fetched_at, http_status, PARSER_VERSION, utc_now_iso()),
        )
        connection.execute(
            """
            INSERT INTO raw_pages(
                run_id, source_url, fetched_at, raw_path, html_hash, byte_count
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, source_url, fetched_at, str(raw_path), html_hash, byte_count),
        )

        for record in records:
            existing = connection.execute(
                """
                SELECT opportunity_id, latest_content_hash, is_active
                FROM opportunities
                WHERE opportunity_id = ?
                """,
                (record.opportunity_id,),
            ).fetchone()

            event_type = None
            details: dict[str, str] = {}
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO opportunities(
                        opportunity_id, fingerprint, first_seen_at, last_seen_at,
                        first_run_id, last_run_id, is_active, latest_content_hash,
                        title, apply_url, institution
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        record.opportunity_id,
                        record.fingerprint,
                        fetched_at,
                        fetched_at,
                        run_id,
                        run_id,
                        record.content_hash,
                        record.title,
                        record.apply_url,
                        record.institution,
                    ),
                )
                event_type = "new"
            else:
                if not existing["is_active"]:
                    event_type = "reactivated"
                elif existing["latest_content_hash"] != record.content_hash:
                    event_type = "updated"
                    details["previous_content_hash"] = existing["latest_content_hash"]

                connection.execute(
                    """
                    UPDATE opportunities
                    SET last_seen_at = ?,
                        last_run_id = ?,
                        is_active = 1,
                        latest_content_hash = ?,
                        title = ?,
                        apply_url = ?,
                        institution = ?
                    WHERE opportunity_id = ?
                    """,
                    (
                        fetched_at,
                        run_id,
                        record.content_hash,
                        record.title,
                        record.apply_url,
                        record.institution,
                        record.opportunity_id,
                    ),
                )

            connection.execute(
                """
                INSERT INTO opportunity_observations(
                    run_id, opportunity_id, observed_at, title, apply_url, researchers,
                    institution, fields_text, deadline_text, visa_text, note_text, body_text,
                    region_tags_json, research_area_tags_json, employer_type_tags_json,
                    other_tags_json, class_list_json, card_html, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    record.opportunity_id,
                    fetched_at,
                    record.title,
                    record.apply_url,
                    record.researchers,
                    record.institution,
                    record.fields_text,
                    record.deadline_text,
                    record.visa_text,
                    record.note_text,
                    record.body_text,
                    json.dumps(record.region_tags, sort_keys=True),
                    json.dumps(record.research_area_tags, sort_keys=True),
                    json.dumps(record.employer_type_tags, sort_keys=True),
                    json.dumps(record.other_tags, sort_keys=True),
                    json.dumps(record.class_list, sort_keys=True),
                    record.card_html,
                    record.content_hash,
                ),
            )

            if event_type:
                _insert_event(
                    connection,
                    opportunity_id=record.opportunity_id,
                    run_id=run_id,
                    event_type=event_type,
                    event_at=fetched_at,
                    details=details,
                )
                events.append(
                    IngestEvent(
                        opportunity_id=record.opportunity_id,
                        event_type=event_type,
                        title=record.title,
                        apply_url=record.apply_url,
                        content_hash=record.content_hash,
                        details=details,
                    )
                )

        active_rows = [
            row
            for row in connection.execute(
                """
                SELECT opportunity_id, title, apply_url, latest_content_hash
                FROM opportunities
                WHERE is_active = 1
                """
            ).fetchall()
        ]
        for active_row in active_rows:
            opportunity_id = active_row["opportunity_id"]
            if opportunity_id in seen_ids:
                continue
            connection.execute(
                """
                UPDATE opportunities
                SET is_active = 0, last_run_id = ?, last_seen_at = ?
                WHERE opportunity_id = ?
                """,
                (run_id, fetched_at, opportunity_id),
            )
            _insert_event(
                connection,
                opportunity_id=opportunity_id,
                run_id=run_id,
                event_type="disappeared",
                event_at=fetched_at,
                details={},
            )
            events.append(
                IngestEvent(
                    opportunity_id=opportunity_id,
                    event_type="disappeared",
                    title=active_row["title"],
                    apply_url=active_row["apply_url"],
                    content_hash=active_row["latest_content_hash"],
                    details={},
                )
            )

    return IngestResult(
        run_id=run_id,
        fetched_at=fetched_at,
        observed_count=len(records),
        events=events,
    )


def fetch_record(connection: sqlite3.Connection, opportunity_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM opportunity_observations
        WHERE opportunity_id = ?
        ORDER BY observed_at DESC, observation_id DESC
        LIMIT 1
        """,
        (opportunity_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"Opportunity not found: {opportunity_id}")
    return row


def mark_alert_sent(
    connection: sqlite3.Connection,
    *,
    opportunity_id: str,
    content_hash: str,
    alert_key: str,
    channel: str,
    match_score: int,
    match_reasons: list[str],
) -> bool:
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO alerts_sent(
                    opportunity_id, content_hash, alert_key, sent_at, channel,
                    match_score, match_reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opportunity_id,
                    content_hash,
                    alert_key,
                    utc_now_iso(),
                    channel,
                    match_score,
                    json.dumps(match_reasons, sort_keys=True),
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def export_latest_csv(connection: sqlite3.Connection, output_path: Path) -> int:
    ensure_parent(output_path)
    rows = connection.execute(
        """
        SELECT
            o.opportunity_id,
            o.first_seen_at,
            o.last_seen_at,
            o.is_active,
            obs.title,
            obs.apply_url,
            obs.researchers,
            obs.institution,
            obs.fields_text,
            obs.deadline_text,
            obs.visa_text,
            obs.note_text,
            obs.region_tags_json,
            obs.research_area_tags_json,
            obs.employer_type_tags_json,
            obs.body_text
        FROM opportunities o
        JOIN opportunity_observations obs
          ON obs.observation_id = (
            SELECT observation_id
            FROM opportunity_observations latest
            WHERE latest.opportunity_id = o.opportunity_id
            ORDER BY observed_at DESC, observation_id DESC
            LIMIT 1
          )
        ORDER BY o.first_seen_at DESC, obs.title
        """
    ).fetchall()

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(rows[0].keys() if rows else ["opportunity_id"])
        for row in rows:
            writer.writerow([row[key] for key in row.keys()])
    return len(rows)


def _insert_event(
    connection: sqlite3.Connection,
    *,
    opportunity_id: str,
    run_id: str,
    event_type: str,
    event_at: str,
    details: dict[str, str],
) -> None:
    connection.execute(
        """
        INSERT INTO opportunity_events(
            opportunity_id, run_id, event_type, event_at, details_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (opportunity_id, run_id, event_type, event_at, json.dumps(details, sort_keys=True)),
    )
