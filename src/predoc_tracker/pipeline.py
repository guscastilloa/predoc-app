from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .fetch import archive_html, fetch_page
from .match import match_record
from .notify import Alert, send_console, send_telegram
from .parse import parse_opportunities
from .settings import AppConfig
from .storage import (
    connect,
    fetch_record,
    ingest_run,
    mark_alert_sent,
)
from .utils import utc_now_iso


@dataclass(frozen=True)
class CheckSummary:
    run_id: str
    observed_count: int
    event_count: int
    alert_count: int
    database_path: Path


def run_check(config: AppConfig, *, notify: bool = True) -> CheckSummary:
    fetched_at = utc_now_iso()
    run_id = f"{fetched_at.replace(':', '').replace('+00:00', 'Z')}-{uuid.uuid4().hex[:8]}"
    fetch_result = fetch_page(config.source_url)
    raw_path = archive_html(config.raw_archive_dir, run_id, fetch_result.html)
    records = parse_opportunities(fetch_result.html)

    connection = connect(config.database_path)
    try:
        ingest_result = ingest_run(
            connection,
            run_id=run_id,
            source_url=config.source_url,
            fetched_at=fetched_at,
            http_status=fetch_result.status_code,
            raw_path=raw_path,
            html_hash=fetch_result.html_hash,
            byte_count=fetch_result.byte_count,
            records=records,
        )
        alerts = _build_alerts(connection, ingest_result.events, config)
        if notify:
            _send_alerts(connection, alerts, config)
    finally:
        connection.close()

    return CheckSummary(
        run_id=run_id,
        observed_count=len(records),
        event_count=len(ingest_result.events),
        alert_count=len(alerts),
        database_path=config.database_path,
    )


def _build_alerts(connection, events, config: AppConfig) -> list[tuple[str, str, Alert]]:
    alerts: list[tuple[str, str, Alert]] = []
    for event in events:
        if event.event_type not in {"new", "updated", "reactivated"}:
            continue
        row = fetch_record(connection, event.opportunity_id)
        match = match_record(row, config.interests)
        if not match.matched:
            continue
        alert = Alert(
            event_type=event.event_type,
            title=row["title"],
            apply_url=row["apply_url"],
            institution=row["institution"],
            deadline_text=row["deadline_text"],
            fields_text=row["fields_text"],
            match=match,
        )
        alerts.append((event.opportunity_id, row["content_hash"], alert))
    return alerts


def _send_alerts(connection, alert_entries, config: AppConfig) -> None:
    alerts_by_channel = [entry[2] for entry in alert_entries]
    channels = config.notifications.channels
    if "console" in channels:
        send_console(alerts_by_channel)

    for channel in channels:
        if channel == "console":
            continue
        unsent = []
        for opportunity_id, content_hash, alert in alert_entries:
            inserted = mark_alert_sent(
                connection,
                opportunity_id=opportunity_id,
                content_hash=content_hash,
                alert_key="default",
                channel=channel,
                match_score=alert.match.score,
                match_reasons=alert.match.reasons,
            )
            if inserted:
                unsent.append(alert)

        if channel == "telegram":
            send_telegram(
                unsent,
                bot_token_env=config.notifications.telegram_bot_token_env,
                chat_id_env=config.notifications.telegram_chat_id_env,
            )
        else:
            raise ValueError(f"Unsupported notification channel: {channel}")

    if "console" in channels:
        for opportunity_id, content_hash, alert in alert_entries:
            mark_alert_sent(
                connection,
                opportunity_id=opportunity_id,
                content_hash=content_hash,
                alert_key="default",
                channel="console",
                match_score=alert.match.score,
                match_reasons=alert.match.reasons,
            )
