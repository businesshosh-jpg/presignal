"""Focused offline tests for the prospective Information-Request temporal guard."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_information_request_temporal_scope_alignment_v1 as temporal


class TemporalScopeAlignmentTests(unittest.TestCase):
    def test_prompt_contains_explicit_temporal_contract_and_categories(self):
        prompt = lineage.REQUEST_INSTRUCTION
        for text in ("before the forecast cutoff", "actual value of the upcoming Event", "beat, matched, or missed consensus", "post-release market reaction", "realized price path", "Outcome data", "evaluation results"):
            self.assertIn(text, prompt)
        self.assertEqual(sum(1 for category in lineage.VALID_CATEGORIES if category in prompt), 16)

    def test_temporal_guard_preserves_historical_context_and_rejects_outcomes(self):
        cases = {
            "What are the current consensus estimate and forecast range?": None,
            "What were the actual values of the previous six Manufacturing PMI releases?": None,
            "How did USD/JPY historically react to prior PMI surprises?": None,
            "What is the actual value of the upcoming Manufacturing PMI release?": "REJECTED_PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE",
            "Did the Manufacturing PMI beat expectations?": "REJECTED_PROMPT_PROHIBITED_OUTCOME_REFERENCE",
            "How did USD/JPY react after this PMI release?": "REJECTED_PROMPT_PROHIBITED_POST_RELEASE_REFERENCE",
            "What was the realized 15-minute price path?": "REJECTED_PROMPT_PROHIBITED_REALIZED_PATH_REFERENCE",
            "Was the forecast direction correct?": "REJECTED_PROMPT_PROHIBITED_EVALUATION_REFERENCE",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(lineage.validate_request_temporal_scope(text), expected)

    def test_complete_alignment_output_is_deterministic_and_closes_pmi(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            temporal.run(output=output)
            fixtures = json.loads((output / "information_request_temporal_fixture_results.json").read_text())
            closure = json.loads((output / "r6_pmi_attempt_closure_manifest.json").read_text())
            alignment = json.loads((output / "information_request_temporal_scope_alignment_manifest.json").read_text())
            determinism = json.loads((output / "information_request_temporal_determinism_report.json").read_text())
        self.assertTrue(fixtures["all_expected_results"])
        self.assertFalse(closure["episode_resumable"])
        self.assertFalse(closure["attention_reusable_for_another_episode"])
        self.assertTrue(alignment["complete_contract_parity_result"])
        self.assertTrue(determinism["identical_outputs"])

    def test_no_external_access(self):
        self.assertTrue(all(value == 0 for value in temporal.audit().values()))


if __name__ == "__main__":
    unittest.main()
