"""Scheduled checks with only a small notification ledger, no scrape history."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from .fetch import fetch_page
from .match import match_record
from .notify import Alert, send_console, send_telegram
from .parse import parse_opportunities
from .settings import AppConfig


def save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    temporary.replace(path)


def run_monitor(config: AppConfig, state_path: Path, *, notify: bool = True) -> int:
    channels = config.notifications.channels
    if set(channels) - {'console', 'telegram'}:
        raise ValueError('Unsupported notification channel.')
    if notify and 'telegram' in channels:
        for name in (config.notifications.telegram_bot_token_env,
                     config.notifications.telegram_chat_id_env):
            if not os.getenv(name):
                raise RuntimeError(f'Missing required setting: {name}')
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if not isinstance(state, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in state.items()
    ):
        raise ValueError('Notification state must be a map of posting IDs to hashes.')

    records = parse_opportunities(fetch_page(config.source_url).html)
    if not records:
        raise RuntimeError('No listings parsed; refusing to replace notification state.')
    sent = 0
    for record in records:
        row = asdict(record)
        for group in ('region', 'research_area', 'employer_type'):
            row[f'{group}_tags_json'] = json.dumps(row[f'{group}_tags'])
        match = match_record(row, config.interests)
        if not match.matched or state.get(record.opportunity_id) == record.content_hash:
            continue
        alert = Alert(
            event_type='updated' if record.opportunity_id in state else 'new',
            title=record.title, apply_url=record.apply_url,
            institution=record.institution, deadline_text=record.deadline_text,
            fields_text=record.fields_text, match=match,
        )
        if 'console' in channels or not notify:
            send_console([alert])
        if not notify:
            continue
        if 'telegram' in channels:
            send_telegram([alert],
                          bot_token_env=config.notifications.telegram_bot_token_env,
                          chat_id_env=config.notifications.telegram_chat_id_env)
        elif 'console' not in channels:
            raise ValueError('At least one notification channel is required.')
        # Save each success so a later delivery failure can be retried safely.
        state[record.opportunity_id] = record.content_hash
        save_state(state_path, state)
        sent += 1
    if notify:
        # Keep only IDs still listed on the source page. No posting bodies or history.
        active_ids = {record.opportunity_id for record in records}
        save_state(state_path, {key: value for key, value in state.items() if key in active_ids})
    print(f'Observed {len(records)} listings; sent {sent} alerts.')
    return sent
