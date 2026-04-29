import unittest

from predoc_tracker.parse import parse_opportunities


SAMPLE_HTML = """
<section class="component isotope">
  <select data-filter-group="region">
    <option value=".all">Region</option>
    <option value=".remote">Remote</option>
  </select>
  <select data-filter-group="researchAreas">
    <option value=".all">Research Areas</option>
    <option value=".labor">Labor</option>
  </select>
  <select data-filter-group="emploerType">
    <option value=".all">Employer Type</option>
    <option value=".academia">Academia</option>
  </select>
  <div class="grid-container">
    <article class="all sorted remote labor academia">
      <h2><a href="https://example.org/job">Research Assistant</a></h2>
      <div class="swiss-text">
        <p>
          <strong>Sponsoring Researcher(s):</strong> Jane Doe<br />
          <strong>Sponsoring Institution:</strong> Example University<br />
          <strong>Fields of Research:</strong> Labor economics<br />
          <strong>Deadline:</strong> Rolling
        </p>
      </div>
    </article>
  </div>
</section>
"""


class ParserTests(unittest.TestCase):
    def test_parse_opportunities_extracts_core_fields(self):
        records = parse_opportunities(SAMPLE_HTML)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.title, "Research Assistant")
        self.assertEqual(record.apply_url, "https://example.org/job")
        self.assertEqual(record.researchers, "Jane Doe")
        self.assertEqual(record.institution, "Example University")
        self.assertEqual(record.fields_text, "Labor economics")
        self.assertEqual(record.deadline_text, "Rolling")
        self.assertEqual(record.region_tags, ["Remote"])
        self.assertEqual(record.research_area_tags, ["Labor"])
        self.assertEqual(record.employer_type_tags, ["Academia"])


if __name__ == "__main__":
    unittest.main()
