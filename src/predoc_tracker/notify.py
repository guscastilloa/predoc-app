from __future__ import annotations

import os
from dataclasses import dataclass

import requests

from .match import MatchResult


@dataclass(frozen=True)
class Alert:
    event_type: str
    title: str
    apply_url: str
    institution: str
    deadline_text: str
    fields_text: str
    match: MatchResult


def format_alert(alert: Alert) -> str:
    lines = [
        f"[{alert.event_type.upper()}] {alert.title}",
        f"Institution: {alert.institution or 'Unknown'}",
        f"Deadline: {alert.deadline_text or 'Unknown'}",
        f"Fields: {alert.fields_text or 'Unknown'}",
        f"Match score: {alert.match.score}",
        f"Reasons: {', '.join(alert.match.reasons) if alert.match.reasons else 'None'}",
    ]
    if alert.apply_url:
        lines.append(f"Apply: {alert.apply_url}")
    return "\n".join(lines)


def send_console(alerts: list[Alert]) -> None:
    if not alerts:
        print("No matching new or updated opportunities.")
        return
    print(f"{len(alerts)} matching new or updated opportunities:")
    for index, alert in enumerate(alerts, start=1):
        print()
        print(f"--- Alert {index} ---")
        print(format_alert(alert))


def send_telegram(
    alerts: list[Alert],
    *,
    bot_token_env: str,
    chat_id_env: str,
) -> None:
    if not alerts:
        return
    bot_token = os.getenv(bot_token_env)
    chat_id = os.getenv(chat_id_env)
    if not bot_token or not chat_id:
        raise RuntimeError(
            f"Telegram requested but {bot_token_env} or {chat_id_env} is not set."
        )

    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for alert in alerts:
        response = requests.post(
            endpoint,
            json={
                "chat_id": chat_id,
                "text": format_alert(alert),
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        response.raise_for_status()
