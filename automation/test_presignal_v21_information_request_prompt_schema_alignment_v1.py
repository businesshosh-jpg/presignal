"""Focused offline checks for Information Request prompt/schema parity."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_information_request_prompt_schema_alignment_v1 as alignment


class PromptSchemaAlignmentTests(unittest.TestCase):
    def test_prompt_contains_exact_frozen_category_set(self):
        values = alignment.exact_category_set_from_prompt(lineage.REQUEST_INSTRUCTION)
        self.assertEqual(values, sorted(lineage.VALID_CATEGORIES))
        self.assertNotIn("Economic Indicator", lineage.REQUEST_INSTRUCTION)
        self.assertNotIn("macro_data", lineage.REQUEST_INSTRUCTION)

    def test_all_authoritative_category_sets_match(self):
        sets = alignment.category_sets()
        self.assertTrue(all(values == sets["schema"] for values in sets.values()))

    def test_fixture_contract_admits_only_exact_values(self):
        for category in ("event_consensus_detail", "growth_context", "risk_sentiment", "other"):
            accepted, result = alignment.validate_fixture(category=category)
            self.assertTrue(accepted, result)
        for category in ("Economic Indicator", "macro_data", "", "growth_context,risk_sentiment"):
            accepted, _result = alignment.validate_fixture(category=category)
            self.assertFalse(accepted)

    def test_alignment_output_preserves_old_response_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            alignment.run(output=output)
            old = json.loads((output / "information_request_old_response_status.json").read_text())
            parity = json.loads((output / "information_request_prompt_category_parity.json").read_text())
            determinism = json.loads((output / "information_request_prompt_determinism_report.json").read_text())
            fingerprint = json.loads((output / "information_request_prompt_schema_alignment_fingerprint.json").read_text())
        self.assertTrue(old["old_response_status"].startswith("INVALID"))
        self.assertFalse(old["new_prompt_assigned_retroactively"])
        self.assertFalse(old["canonical_requests_created_from_old_response"])
        self.assertTrue(parity["all_category_sets_identical"])
        self.assertTrue(determinism["identical_outputs"])
        self.assertTrue(fingerprint["reproducible"])

    def test_no_external_access(self):
        self.assertTrue(all(value == 0 for value in alignment.audit().values()))


if __name__ == "__main__":
    unittest.main()
