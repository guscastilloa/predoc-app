from __future__ import annotations

import gzip
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests
import certifi

from .utils import ensure_parent, sha256_text


USER_AGENT = "predoc-tracker/0.0.1 (+https://www.predoc.org/opportunities monitor)"


@dataclass(frozen=True)
class FetchResult:
    source_url: str
    status_code: int
    html: str
    html_hash: str
    byte_count: int


def fetch_page(source_url: str, timeout_seconds: int = 30) -> FetchResult:
    try:
        response = requests.get(
            source_url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout_seconds,
            verify=certifi.where(),
        )
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return _result_from_html(source_url, response.status_code, response.text)
    except requests.exceptions.SSLError:
        return _fetch_page_with_curl(source_url, timeout_seconds)


def archive_html(raw_archive_dir: Path, run_id: str, html: str) -> Path:
    archive_path = raw_archive_dir / f"{run_id}.html.gz"
    ensure_parent(archive_path)
    with gzip.open(archive_path, "wt", encoding="utf-8") as handle:
        handle.write(html)
    return archive_path


def _fetch_page_with_curl(source_url: str, timeout_seconds: int) -> FetchResult:
    status_marker = "\nPREDOC_TRACKER_HTTP_STATUS:"
    command = [
        "curl",
        "--location",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout_seconds),
        "--user-agent",
        USER_AGENT,
        "--write-out",
        f"{status_marker}%{{http_code}}",
        source_url,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    body, marker, status_text = completed.stdout.rpartition(status_marker)
    if not marker:
        raise RuntimeError("curl fallback did not return an HTTP status marker.")
    return _result_from_html(source_url, int(status_text), body)


def _result_from_html(source_url: str, status_code: int, html: str) -> FetchResult:
    return FetchResult(
        source_url=source_url,
        status_code=status_code,
        html=html,
        html_hash=sha256_text(html),
        byte_count=len(html.encode("utf-8")),
    )
