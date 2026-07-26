#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from automation import presignal_v21_event_path_contract_v1 as contract_v1
from automation import presignal_v21_event_path_contract_v1_1 as contract_v1_1
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6_v1_1


EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "presignal_v21_event_path" / "examples"


def load(name: str):
    return json.loads((EXAMPLES / name).read_text())


class ImmediateImpulseContractVersioningRepairTests(unittest.TestCase):
    def test_v1_examples_remain_legacy_and_valid(self):
        baseline = load("valid_baseline_prediction.json")
        outcome = load("valid_outcome.json")
        evaluation = load("valid_evaluation.json")
        paths = load("valid_prediction_path.json")
        self.assertIn("expected_initial_direction", baseline)
        self.assertNotIn("early_reaction_5m_direction", baseline)
        self.assertNotIn("immediate_impulse_direction", baseline)
        contract_v1.validate_prediction_path_transaction(baseline, paths)
        contract_v1.validate_outcome(outcome)
        contract_v1.validate_evaluation(evaluation, baseline, outcome, paths)

    def test_v1_1_examples_use_explicit_early_reaction_and_validate(self):
        baseline = load("valid_baseline_prediction_v1_1.json")
        full = load("valid_full_context_prediction_v1_1.json")
        no_signal = load("valid_no_signal_prediction_v1_1.json")
        outcome = load("valid_outcome_v1_1.json")
        evaluation = load("valid_evaluation_v1_1.json")
        paths = load("valid_prediction_path_v1_1.json")
        self.assertNotIn("expected_initial_direction", baseline)
        self.assertIn("early_reaction_5m_direction", baseline)
        self.assertEqual(baseline["schema_version"], "2.1.1")
        contract_v1_1.validate_prediction_path_transaction(baseline, paths)
        contract_v1_1.validate_prediction(no_signal)
        contract_v1_1.validate_outcome(outcome)
        contract_v1_1.validate_evaluation(evaluation, baseline, outcome, paths)
        contract_v1_1.validate_ae_pair(baseline, full)

    def test_versions_cannot_be_confused(self):
        legacy = load("valid_baseline_prediction.json")
        modern = load("valid_baseline_prediction_v1_1.json")
        with self.assertRaises(contract_v1.ContractValidationError):
            contract_v1.validate_prediction(modern)
        with self.assertRaises(contract_v1_1.ContractValidationError):
            contract_v1_1.validate_prediction(legacy)

    def test_approximation_only_does_not_invalidate_t15(self):
        outcome = load("valid_outcome_v1_1.json")
        self.assertEqual(outcome["immediate_impulse_outcome_state"], "APPROXIMATION_ONLY")
        prediction = load("valid_baseline_prediction_v1_1.json")
        paths = load("valid_prediction_path_v1_1.json")
        evaluation = step6_v1_1.evaluate(prediction, paths, outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertEqual(evaluation["immediate_impulse_direction_result"], "NOT_APPLICABLE")
        self.assertTrue(evaluation["direction_15m_ok"])


if __name__ == "__main__":
    unittest.main()
