from __future__ import annotations

import json
from dataclasses import dataclass
from sqlite3 import Row

from .settings import InterestRules


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    score: int
    reasons: list[str]


def match_record(row: Row, rules: InterestRules) -> MatchResult:
    searchable = " ".join(
        [
            row["title"],
            row["institution"],
            row["researchers"],
            row["fields_text"],
            row["deadline_text"],
            row["note_text"],
            row["body_text"],
        ]
    ).lower()
    reasons: list[str] = []
    score = 0

    for keyword in rules.exclude_keywords:
        if keyword.lower() in searchable:
            return MatchResult(False, 0, [f"excluded keyword: {keyword}"])

    for keyword in rules.priority_keywords:
        if keyword.lower() in searchable:
            score += 4
            reasons.append(f"priority keyword: {keyword}")

    for keyword in rules.include_keywords:
        if keyword.lower() in searchable:
            score += 3
            reasons.append(f"keyword: {keyword}")

    score += _score_tag_group(
        row["region_tags_json"], rules.regions, 2, "region", reasons
    )
    score += _score_tag_group(
        row["research_area_tags_json"], rules.research_areas, 2, "research area", reasons
    )
    score += _score_tag_group(
        row["employer_type_tags_json"], rules.employer_types, 2, "employer type", reasons
    )

    no_rules = not any(
        [
            rules.include_keywords,
            rules.priority_keywords,
            rules.regions,
            rules.research_areas,
            rules.employer_types,
        ]
    )
    if no_rules:
        return MatchResult(True, 1, ["no interest rules configured"])

    return MatchResult(score >= rules.min_score, score, reasons)


def _score_tag_group(
    stored_json: str,
    wanted: list[str],
    points: int,
    label: str,
    reasons: list[str],
) -> int:
    if not wanted:
        return 0
    tags = {tag.lower() for tag in json.loads(stored_json)}
    matched = [item for item in wanted if item.lower() in tags]
    for item in matched:
        reasons.append(f"{label}: {item}")
    return points * len(matched)
