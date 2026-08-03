import json
import tempfile
import unittest
from pathlib import Path

from automation import evaluate_presignal_v21_round_1_aggregate as aggregate


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
RUN = BASE / "PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z"
AUTH = BASE / "PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-20260804T050000Z/aggregate_authorization.json"


class RoundOneAggregateEvaluationTest(unittest.TestCase):
    def setUp(self):
        self.authorization, self.rows, self.sources = aggregate.load_and_validate(AUTH)
        self.metrics = json.loads((RUN / "aggregate_metrics.json").read_text())

    def test_authorization_is_bound_to_the_accepted_eleven_slice_artifacts(self):
        self.assertEqual(len(self.authorization["accepted_slice_artifacts"]), 11)
        self.assertEqual(len(self.sources), 11)
        self.assertEqual(self.authorization["population"]["evaluation_records"], 518)

    def test_identity_population_is_unique_and_pack_separated(self):
        self.assertEqual(len(self.rows), 518)
        self.assertEqual(len({row["forecast_call_id"] for row in self.rows}), 518)
        self.assertEqual(sum(row["pack"] == "PACK_A" for row in self.rows), 259)
        self.assertEqual(sum(row["pack"] == "PACK_E" for row in self.rows), 259)
        self.assertEqual(aggregate.pair_summary(self.rows)["complete_pairs"], 259)

    def test_pooled_denominators_and_no_signal_treatment_are_deterministic(self):
        recomputed = {pack: aggregate.metric_summary([row for row in self.rows if row["pack"] == pack], pack) for pack in ("PACK_A", "PACK_E")}
        self.assertEqual(recomputed["PACK_A"], self.metrics["PACK_A"])
        self.assertEqual(recomputed["PACK_E"], self.metrics["PACK_E"])
        self.assertEqual(self.metrics["PACK_A"]["T+15 directional accuracy"]["denominator"], 208)
        self.assertEqual(self.metrics["PACK_E"]["T+15 directional accuracy"]["denominator"], 252)
        self.assertEqual(self.metrics["PACK_A"]["no_signal_excluded_from_directional_metrics"], 51)
        self.assertEqual(self.metrics["PACK_E"]["no_signal_excluded_from_directional_metrics"], 7)
        self.assertEqual(self.metrics["paired_comparison"]["common_paired_t15_scoreable"], 206)

    def test_immediate_impulse_remains_strictly_not_applicable(self):
        for pack in ("PACK_A", "PACK_E"):
            metric = self.metrics[pack]["Immediate Impulse directional accuracy"]
            self.assertEqual(metric["denominator"], 0)
            self.assertEqual(metric["status"], "NOT_APPLICABLE_STRICT")

    def test_no_external_access_or_composite_score_is_authorized(self):
        self.assertTrue(all(value == 0 for value in self.authorization["external_limits"].values()))
        decision = json.loads((RUN / "aggregate_decision.json").read_text())
        self.assertEqual(decision["composite_score"], "NOT_CALCULATED_NOT_AUTHORIZED")
        self.assertEqual(decision["external_operations"], 0)

    def test_authorization_tampering_fails_closed(self):
        tampered = dict(self.authorization)
        tampered["population"] = dict(tampered["population"])
        tampered["population"]["evaluation_records"] = 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.json"
            path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError, "TAMPER_OR_FINGERPRINT_CONFLICT"):
                aggregate.load_and_validate(path)


if __name__ == "__main__":
    unittest.main()
