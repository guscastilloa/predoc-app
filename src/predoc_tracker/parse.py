from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup

from .utils import normalize_text, normalize_url, sha256_text


PARSER_VERSION = "0.0.1"

NON_TAG_CLASSES = {"all", "sorted", "hidden", "shown", "first", "last"}
LABEL_ALIASES = {
    "sponsoring researcher": "researchers",
    "sponsoring researchers": "researchers",
    "sponsoring researcher(s)": "researchers",
    "sponsoring institution": "institution",
    "sponsoring institutions": "institution",
    "sponsoring institution(s)": "institution",
    "field of research": "fields",
    "fields of research": "fields",
    "field(s) of research": "fields",
    "deadline": "deadline",
    "visa": "visa",
    "please note": "note",
    "projects": "projects",
}
LABEL_PATTERN = re.compile(
    r"(?P<label>"
    r"Sponsoring Researcher(?:\(s\))?s?|"
    r"Sponsoring Institution(?:\(s\))?s?|"
    r"Field(?:\(s\))? of Research|"
    r"Fields of Research|"
    r"Deadline|Visa|Please Note|Projects"
    r")\s*:?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OpportunityRecord:
    opportunity_id: str
    fingerprint: str
    content_hash: str
    title: str
    apply_url: str
    researchers: str
    institution: str
    fields_text: str
    deadline_text: str
    visa_text: str
    note_text: str
    body_text: str
    region_tags: list[str]
    research_area_tags: list[str]
    employer_type_tags: list[str]
    other_tags: list[str]
    class_list: list[str]
    card_html: str


def parse_opportunities(html: str) -> list[OpportunityRecord]:
    soup = BeautifulSoup(html, "html.parser")
    filter_options = _parse_filter_options(soup)
    grid = soup.select_one(".grid-container")
    if not grid:
        return []

    records = []
    for article in grid.select("article.all"):
        class_list = sorted(article.get("class", []))
        title_link = article.select_one("h2 a")
        title = normalize_text(title_link.get_text(" ", strip=True) if title_link else "")
        apply_url = normalize_url(title_link.get("href") if title_link else "")
        swiss_text = article.select_one(".swiss-text") or article
        body_text = normalize_text(swiss_text.get_text(" ", strip=True))
        labels = _extract_labeled_fields(body_text)
        tags = _classify_tags(class_list, filter_options)

        institution = labels.get("institution", "")
        fingerprint = _build_fingerprint(title, institution, apply_url, body_text)
        content_basis = "\n".join(
            [
                title,
                apply_url,
                body_text,
                " ".join(class_list),
            ]
        )

        records.append(
            OpportunityRecord(
                opportunity_id=sha256_text(fingerprint)[:24],
                fingerprint=fingerprint,
                content_hash=sha256_text(content_basis),
                title=title,
                apply_url=apply_url,
                researchers=labels.get("researchers", ""),
                institution=institution,
                fields_text=labels.get("fields", ""),
                deadline_text=labels.get("deadline", ""),
                visa_text=labels.get("visa", ""),
                note_text=labels.get("note", ""),
                body_text=body_text,
                region_tags=tags["region"],
                research_area_tags=tags["researchAreas"],
                employer_type_tags=tags["emploerType"],
                other_tags=tags["other"],
                class_list=class_list,
                card_html=str(article),
            )
        )
    return records


def _parse_filter_options(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = {
        "region": {},
        "researchAreas": {},
        "emploerType": {},
    }
    for select in soup.select("select[data-filter-group]"):
        group = select.get("data-filter-group") or select.get("name")
        if group not in groups:
            continue
        for option in select.select("option"):
            raw_value = (option.get("value") or "").strip()
            if raw_value in {"", ".all"}:
                continue
            class_name = raw_value.removeprefix(".")
            groups[group][class_name] = normalize_text(option.get_text(" ", strip=True))
    return groups


def _classify_tags(
    class_list: Iterable[str], filter_options: dict[str, dict[str, str]]
) -> dict[str, list[str]]:
    result = {"region": [], "researchAreas": [], "emploerType": [], "other": []}
    known_classes = set()
    for group, options in filter_options.items():
        for class_name, label in options.items():
            known_classes.add(class_name)
            if class_name in class_list:
                result[group].append(label)

    for class_name in class_list:
        if class_name not in NON_TAG_CLASSES and class_name not in known_classes:
            result["other"].append(class_name)
    return result


def _extract_labeled_fields(text: str) -> dict[str, str]:
    matches = list(LABEL_PATTERN.finditer(text))
    fields: dict[str, str] = {}
    for index, match in enumerate(matches):
        label = _canonical_label(match.group("label"))
        if not label:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = normalize_text(text[start:end])
        if value:
            fields[label] = value
    return fields


def _canonical_label(label: str) -> str | None:
    label_key = normalize_text(label).lower()
    return LABEL_ALIASES.get(label_key)


def _build_fingerprint(title: str, institution: str, apply_url: str, body_text: str) -> str:
    if apply_url:
        return f"url:{apply_url}"
    fallback = "|".join([title.lower(), institution.lower(), body_text[:240].lower()])
    return f"text:{normalize_text(fallback)}"
