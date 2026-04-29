from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SOURCE_URL = "https://www.predoc.org/opportunities"
DEFAULT_DATABASE_PATH = Path("data/predoc.sqlite")
DEFAULT_RAW_ARCHIVE_DIR = Path("data/raw")


@dataclass(frozen=True)
class NotificationConfig:
    channels: list[str] = field(default_factory=lambda: ["console"])
    telegram_bot_token_env: str = "PREDOC_TELEGRAM_BOT_TOKEN"
    telegram_chat_id_env: str = "PREDOC_TELEGRAM_CHAT_ID"


@dataclass(frozen=True)
class InterestRules:
    include_keywords: list[str] = field(default_factory=list)
    priority_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    research_areas: list[str] = field(default_factory=list)
    employer_types: list[str] = field(default_factory=list)
    min_score: int = 1


@dataclass(frozen=True)
class AppConfig:
    source_url: str = DEFAULT_SOURCE_URL
    database_path: Path = DEFAULT_DATABASE_PATH
    raw_archive_dir: Path = DEFAULT_RAW_ARCHIVE_DIR
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    interests: InterestRules = field(default_factory=InterestRules)


def load_config(path: Path | None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    notifications = raw.get("notifications") or {}
    interests = raw.get("interests") or {}

    return AppConfig(
        source_url=raw.get("source_url", DEFAULT_SOURCE_URL),
        database_path=Path(raw.get("database_path", DEFAULT_DATABASE_PATH)),
        raw_archive_dir=Path(raw.get("raw_archive_dir", DEFAULT_RAW_ARCHIVE_DIR)),
        notifications=NotificationConfig(
            channels=_string_list(notifications.get("channels"), ["console"]),
            telegram_bot_token_env=notifications.get(
                "telegram_bot_token_env", "PREDOC_TELEGRAM_BOT_TOKEN"
            ),
            telegram_chat_id_env=notifications.get(
                "telegram_chat_id_env", "PREDOC_TELEGRAM_CHAT_ID"
            ),
        ),
        interests=InterestRules(
            include_keywords=_string_list(interests.get("include_keywords")),
            priority_keywords=_string_list(interests.get("priority_keywords")),
            exclude_keywords=_string_list(interests.get("exclude_keywords")),
            regions=_string_list(interests.get("regions")),
            research_areas=_string_list(interests.get("research_areas")),
            employer_types=_string_list(interests.get("employer_types")),
            min_score=int(interests.get("min_score", 1)),
        ),
    )


def _string_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]
