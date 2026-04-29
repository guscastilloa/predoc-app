import json
import sqlite3
import unittest

from predoc_tracker.match import match_record
from predoc_tracker.settings import InterestRules


def _row(**values):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE records (
            title TEXT,
            institution TEXT,
            researchers TEXT,
            fields_text TEXT,
            deadline_text TEXT,
            note_text TEXT,
            body_text TEXT,
            region_tags_json TEXT,
            research_area_tags_json TEXT,
            employer_type_tags_json TEXT
        )
        """
    )
    defaults = {
        "title": "Research Assistant",
        "institution": "Example University",
        "researchers": "",
        "fields_text": "Labor economics and causal inference",
        "deadline_text": "Rolling",
        "note_text": "",
        "body_text": "",
        "region_tags_json": json.dumps(["Remote"]),
        "research_area_tags_json": json.dumps(["Labor"]),
        "employer_type_tags_json": json.dumps(["Academia"]),
    }
    defaults.update(values)
    connection.execute(
        """
        INSERT INTO records VALUES (
            :title, :institution, :researchers, :fields_text, :deadline_text,
            :note_text, :body_text, :region_tags_json, :research_area_tags_json,
            :employer_type_tags_json
        )
        """,
        defaults,
    )
    return connection.execute("SELECT * FROM records").fetchone()


class MatchingTests(unittest.TestCase):
    def test_match_record_scores_keywords_and_tags(self):
        rules = InterestRules(
            include_keywords=["causal inference"],
            research_areas=["Labor"],
            min_score=3,
        )

        result = match_record(_row(), rules)

        self.assertTrue(result.matched)
        self.assertEqual(result.score, 5)
        self.assertIn("keyword: causal inference", result.reasons)
        self.assertIn("research area: Labor", result.reasons)

    def test_match_record_honors_exclusions(self):
        rules = InterestRules(
            include_keywords=["causal inference"],
            exclude_keywords=["unpaid"],
            min_score=1,
        )

        result = match_record(_row(body_text="This is an unpaid position."), rules)

        self.assertFalse(result.matched)
        self.assertEqual(result.reasons, ["excluded keyword: unpaid"])


if __name__ == "__main__":
    unittest.main()
