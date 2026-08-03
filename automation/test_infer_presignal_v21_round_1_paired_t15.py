import json
import tempfile
import unittest
from pathlib import Path

from automation import infer_presignal_v21_round_1_paired_t15 as inference


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
AUTH = BASE / "PPHB-R1-PAIRED-T15-INFERENCE-20260804T070000Z/inference_authorization.json"
RESULT = BASE / "PPHB-R1-PAIRED-T15-INFERENCE-RESULT-20260804T070000Z"


class PairedT15InferenceTest(unittest.TestCase):
    def setUp(self):
        self.authorization, self.pairs = inference.load_authorization(AUTH)
        self.result = json.loads((RESULT / "paired_t15_inference.json").read_text())
        self.decision = json.loads((RESULT / "inference_decision.json").read_text())

    def test_exact_common_pair_population_and_identity_bindings(self):
        self.assertEqual(len(self.pairs), 206)
        self.assertEqual(len({pair["pack_a_forecast_call_id"] for pair in self.pairs}), 206)
        self.assertEqual(len({pair["pack_e_forecast_call_id"] for pair in self.pairs}), 206)
        self.assertEqual(self.authorization["exact_pair_population"]["pairs"], 206)
        correction = json.loads((RESULT / "pair_population_proof_correction.json").read_text())
        self.assertEqual(correction["corrected_value"], 106)
        self.assertEqual(correction["source_aggregate_record_count"] - correction["common_paired_scoreable_record_count"], 106)

    def test_four_cell_table_reconciles_to_accepted_correctness_totals(self):
        table = self.result["four_cell_table"]
        self.assertEqual(table, {"both_correct": 46, "pack_a_correct_pack_e_incorrect": 40, "pack_a_incorrect_pack_e_correct": 54, "both_incorrect": 66})
        self.assertEqual(sum(table.values()), 206)
        self.assertEqual(table["both_correct"] + table["pack_a_correct_pack_e_incorrect"], 86)
        self.assertEqual(table["both_correct"] + table["pack_a_incorrect_pack_e_correct"], 100)

    def test_exact_two_sided_mcnemar_is_reproducible(self):
        self.assertAlmostEqual(inference.exact_two_sided_mcnemar(40, 54), 0.17966501480803043)
        self.assertEqual(self.result["discordant_pairs"], {"pack_a_only_correct": 40, "pack_e_only_correct": 54, "total": 94})
        self.assertFalse(self.result["null_rejected_at_pre_specified_alpha"])

    def test_authorization_tampering_fails_closed(self):
        tampered = dict(self.authorization)
        tampered["test_specification"] = dict(tampered["test_specification"])
        tampered["test_specification"]["direction"] = "one-sided"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "TAMPER_CONFLICT"):
                inference.load_authorization(path)

    def test_no_external_or_unauthorized_analysis(self):
        self.assertTrue(all(value == 0 for value in self.authorization["external_limits"].values()))
        self.assertEqual(self.decision["confidence_interval"], "NOT_CALCULATED_METHOD_NOT_AUTHORIZED")
        self.assertEqual(self.decision["external_operations"], 0)
        self.assertEqual(self.decision["new_metrics"], 0)

    def test_interpretation_is_restrained(self):
        interpretation = self.decision["interpretation"]
        self.assertIn("not rejected", interpretation["conclusion"].lower())
        boundary = interpretation["boundary"].lower()
        self.assertIn("causality", boundary)
        self.assertIn("provider selection", boundary)
        self.assertIn("pack a replacement", boundary)


if __name__ == "__main__":
    unittest.main()
