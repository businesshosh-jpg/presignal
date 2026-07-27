from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import validate_presignal_v21_immediate_impulse_minute_enrichment_r1 as validation


def eval_row(**overrides):
    row = {
        "episode_id": "EP1",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "information_arm": "BASELINE",
        "pack_arm": "PACK_A",
        "prediction_id": "PRD1",
        "evaluation_status": "COMPLETED_DIRECTIONAL_FORECAST",
        "no_signal_flag": False,
        "close_direction_evaluable": True,
        "sequence_unambiguous": True,
        "first_minute_direction_result": "CORRECT",
        "two_minute_direction_result": "INCORRECT",
        "one_minute_approximation_direction_result": "CORRECT",
        "sequence_unambiguous_direction_result": "CORRECT",
        "predicted_minute_path_class": "CONTINUATION",
        "observed_minute_path_class": "CONTINUATION",
        "minute_path_result": "CORRECT",
    }
    row.update(overrides)
    return row


class ValidationTests(unittest.TestCase):
    def test_independent_aggregate_recomputation(self):
        row = validation.metric_row([eval_row(), eval_row(prediction_id="PRD2", first_minute_direction_result="INCORRECT", one_minute_approximation_direction_result="INCORRECT", sequence_unambiguous_direction_result="INCORRECT")])
        self.assertEqual(row["directional_predictions"], 2)
        self.assertEqual(row["first_minute_correct"], 1)
        self.assertEqual(row["first_minute_incorrect"], 1)
        self.assertEqual(row["sequence_unambiguous_correct"], 1)
        self.assertEqual(row["sequence_unambiguous_incorrect"], 1)
        self.assertEqual(row["sequence_unambiguous_accuracy"], 0.5)

    def test_zero_denominator_metric_handling(self):
        self.assertIsNone(validation.ratio(0, 0))

    def test_correction_and_degradation_definitions(self):
        self.assertEqual(validation.pair_classification("INCORRECT", "CORRECT"), "correction")
        self.assertEqual(validation.pair_classification("CORRECT", "INCORRECT"), "degradation")

    def test_transition_category_totals(self):
        a = eval_row(no_signal_flag=False, evaluation_status="COMPLETED_DIRECTIONAL_FORECAST")
        e = eval_row(information_arm="FULL_CONTEXT", pack_arm="PACK_E", prediction_id="PRD2", no_signal_flag=True, evaluation_status="VALID_NO_SIGNAL", close_direction_evaluable=False, sequence_unambiguous=None, first_minute_direction_result="NOT_EVALUABLE", two_minute_direction_result="NOT_EVALUABLE", one_minute_approximation_direction_result="NOT_EVALUABLE", sequence_unambiguous_direction_result="NOT_EVALUABLE")
        self.assertEqual(validation.pair_transition(a, e), "A_DIRECTIONAL_TO_E_NO_SIGNAL")

    def test_continuation_metric_labeling(self):
        audit = validation.continuation_reversal_audit(
            [eval_row(), eval_row(observed_minute_path_class="REVERSAL", minute_path_result="INCORRECT")],
            {
                "PRD1": {"immediate_impulse_direction": "UP", "early_reaction_5m_direction": "UP"},
            },
        )
        self.assertEqual(audit["treatment"]["continuation"], "RELABEL_AS_CONDITIONAL_PATH_RATE")
        self.assertFalse(audit["self_comparison_detected"])

    def test_reversal_metric_labeling(self):
        audit = validation.continuation_reversal_audit(
            [eval_row(observed_minute_path_class="REVERSAL", minute_path_result="INCORRECT")],
            {"PRD1": {"immediate_impulse_direction": "UP", "early_reaction_5m_direction": "UP"}},
        )
        self.assertEqual(audit["treatment"]["reversal"], "RELABEL_AS_CONDITIONAL_PATH_RATE")

    def test_corrected_summary_uses_sequence_unambiguous_accuracy(self):
        denominator = {
            "overall": {
                "total_rows": 10,
                "directional_predictions": 8,
                "valid_no_signal": 1,
                "schema_invalid": 1,
                "approximation_evaluable": 8,
                "ambiguous_bars": 2,
                "sequence_unambiguous": 6,
                "sequence_unambiguous_correct": 2,
                "sequence_unambiguous_incorrect": 4,
                "sequence_unambiguous_accuracy": 0.333333,
                "first_minute_correct": 3,
                "first_minute_incorrect": 5,
                "first_minute_accuracy": 0.375,
                "two_minute_correct": 4,
                "two_minute_incorrect": 4,
                "two_minute_accuracy": 0.5,
            },
            "Gemini": {},
            "OpenAI": {},
            "Pack A": {},
            "Pack E": {},
        }
        summary = validation.corrected_summary(
            denominator,
            {"pair_row_count": 5},
            {
                "reported_continuation_value": 1.0,
                "reported_reversal_value": 0.0,
                "treatment": {"continuation": "RELABEL_AS_CONDITIONAL_PATH_RATE", "reversal": "RELABEL_AS_CONDITIONAL_PATH_RATE"},
                "structural_issue": "x",
            },
        )
        self.assertEqual(summary["overall_sequence_unambiguous_approximation_directional_accuracy"], 0.333333)

    def test_no_self_comparison_of_outcome_derived_fields(self):
        audit = validation.continuation_reversal_audit(
            [eval_row()],
            {"PRD1": {"immediate_impulse_direction": "UP", "early_reaction_5m_direction": "UP"}},
        )
        self.assertFalse(audit["self_comparison_detected"])
        self.assertIn("immediate_impulse_direction", audit["forecast_fields_used"])

    def test_deterministic_validation_fingerprint_material(self):
        payload = {"a": 1}
        self.assertEqual(validation.sha256_value(payload), validation.sha256_value(payload))

    def test_write_json_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            validation.write_json(path, {"b": 2, "a": 1})
            self.assertIn('"a": 1', path.read_text())


if __name__ == "__main__":
    unittest.main()
