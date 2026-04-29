from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


WHITESPACE_RE = re.compile(r"\s+")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path
    return urlunsplit((scheme, netloc, path, parsed.query, ""))
