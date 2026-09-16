"""Tests for the AcademicEvidenceReceipt schema and its example.

The schema lives in schemas/evidence-receipt.schema.json; the example in
examples/evidence-receipt.example.json. Validation here is minimal and
dependency-free: it checks the schema is parseable JSON Schema and that the
example satisfies the schema's structural requirements.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "evidence-receipt.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "evidence-receipt.example.json"


class EvidenceReceiptTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def test_schema_is_parseable_json_schema(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["type"], "object")
        self.assertIn("properties", self.schema)

    def test_example_has_all_required_fields(self):
        for field in self.schema["required"]:
            self.assertIn(field, self.example, f"example missing required field {field}")

    def test_example_matches_schema_version_constraint(self):
        self.assertEqual(self.example["schema_version"], self.schema["properties"]["schema_version"]["const"])

    def test_example_identifiers_are_string_or_null(self):
        for key, value in self.example["identifiers"].items():
            self.assertTrue(value is None or isinstance(value, str), f"identifier {key} has invalid type")

    def test_example_sources_use_known_status_values(self):
        allowed = set(self.schema["properties"]["sources"]["items"]["properties"]["status"]["enum"])
        for source in self.example["sources"]:
            self.assertIn(source["status"], allowed)

    def test_example_claims_use_known_enum_values(self):
        evidence_types = set(self.schema["properties"]["claims"]["items"]["properties"]["evidence_type"]["enum"])
        support = set(self.schema["properties"]["claims"]["items"]["properties"]["support_status"]["enum"])
        for claim in self.example["claims"]:
            self.assertIn(claim["evidence_type"], evidence_types)
            self.assertIn(claim["support_status"], support)

    def test_example_conflicts_and_failures_are_string_lists(self):
        for field in ("conflicts", "failures", "artifacts"):
            self.assertIsInstance(self.example[field], list)
            for item in self.example[field]:
                self.assertIsInstance(item, str)


if __name__ == "__main__":
    unittest.main()
