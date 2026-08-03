import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
AGGREGATE = BASE / "PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z"
REPORT = BASE / "PPHB-R1-ROUND-1-FINAL-REPORT-20260804T060000Z"


class RoundOneFinalReportTest(unittest.TestCase):
    def setUp(self):
        self.metrics = json.loads((AGGREGATE / "aggregate_metrics.json").read_text())
        self.interpretation = json.loads((REPORT / "scientific_interpretation.json").read_text())
        self.recommendation = json.loads((REPORT / "next_move_recommendation.json").read_text())
        self.report = (REPORT / "final_round_1_report.md").read_text()

    def test_metric_transcription_and_population_are_exact(self):
        self.assertIn("518 evaluated forecast records", self.report)
        self.assertIn("259 Pack A records", self.report)
        self.assertIn("259 Pack E records", self.report)
        self.assertIn("| Pack A | 87 | 208 | 0.418269 |", self.report)
        self.assertIn("| Pack E | 113 | 252 | 0.448413 |", self.report)
        self.assertIn("86/206 (0.417476)", self.report)
        self.assertIn("100/206 (0.485437)", self.report)
        for value in ("8.052163 pips", "7.186706 pips", "88/208 (0.423077)", "112/252 (0.444444)", "68/208 (0.326923)", "84/252 (0.333333)", "72/208 (0.346154)", "91/252 (0.361111)", "0.378606", "0.396825", "104/208 (0.500000)", "118/252 (0.468254)"):
            self.assertIn(value, self.report)
        self.assertEqual(self.metrics["PACK_A"]["no_signal_excluded_from_directional_metrics"], 51)
        self.assertEqual(self.metrics["PACK_E"]["no_signal_excluded_from_directional_metrics"], 7)

    def test_primary_secondary_and_pack_boundaries_are_preserved(self):
        self.assertIn("T+15 directional accuracy", self.report)
        self.assertIn("Immediate Impulse directional accuracy", self.report)
        self.assertIn("NOT_APPLICABLE_STRICT", self.report)
        self.assertIn("Pack A", self.report)
        self.assertIn("Pack E", self.report)

    def test_no_unsupported_inference_or_metric_extension(self):
        lower = self.report.lower()
        self.assertIn("does not establish statistical significance", lower)
        self.assertIn("do not describe pack e as established as superior", lower)
        self.assertNotIn("composite score:", lower)
        self.assertTrue(self.interpretation["metric_recalculation"] is False)
        self.assertEqual(self.interpretation["new_inference_tests"], 0)
        self.assertIsNone(self.recommendation["drifting_warning"])

    def test_recommendation_is_separately_authorized_and_local_only(self):
        required = self.recommendation["required_future_authorization"]
        self.assertEqual(required["external_access"], 0)
        self.assertEqual(required["forecast_or_outcome_modification"], 0)
        self.assertIn("exact test and assumptions", required["exact_test_and_assumptions"].lower())


if __name__ == "__main__":
    unittest.main()
