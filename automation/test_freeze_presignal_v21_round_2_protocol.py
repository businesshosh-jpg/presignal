import copy
import unittest

from automation import freeze_presignal_v21_round_2_protocol as round2


class Round2ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.protocol = round2.build_protocol()
        self.protocol["protocol_fingerprint"] = round2.digest(self.protocol)

    def test_protocol_is_deterministic_and_local_only(self):
        validation = round2.validate_protocol(self.protocol)
        self.assertEqual(validation["protocol_fingerprint"], self.protocol["protocol_fingerprint"])
        self.assertTrue(all(value == 0 for value in self.protocol["this_move_limits"].values()))
        self.assertEqual(self.protocol["protocol_status"], "FROZEN_EXECUTION_NOT_AUTHORIZED")

    def test_primary_endpoint_and_coverage_are_prespecified(self):
        primary = self.protocol["primary_endpoint"]
        self.assertEqual(primary["name"], "T+15 directional accuracy")
        self.assertIn("NO_SIGNAL", primary["forecast_labels"])
        self.assertIn("matching same-Episode/provider/model", primary["common_paired_scoreable_population"])
        coverage = self.protocol["coverage_and_no_signal_plan"]
        self.assertIn("NO_SIGNAL", coverage["no_signal_definition"])
        self.assertIn("coverage-adjusted composite scoring", coverage["prohibitions"])

    def test_paired_inference_is_exact_and_frozen(self):
        plan = self.protocol["inferential_plan"]
        self.assertEqual(plan["test"], "Exact two-sided McNemar binomial test")
        self.assertEqual(plan["alpha"], 0.05)
        self.assertEqual(plan["confidence_interval"], "Not reported: no canonical paired risk-difference interval method and confidence level are governed.")
        self.assertIn("Prohibited", plan["interim_analysis"])

    def test_provider_models_and_paired_allocation_are_frozen(self):
        control = self.protocol["provider_model_control"]
        self.assertEqual(tuple(control["permitted_provider_models"]), round2.PROVIDER_MODELS)
        self.assertIn("one Pack A and one Pack E call", control["allocation_rule"])
        self.assertIn("outcome-informed reallocation", control["prohibitions"])

    def test_leakage_and_metric_boundaries_are_frozen(self):
        boundary = self.protocol["prospective_boundary"]
        self.assertIn("prompt_freeze_ts < forecast_freeze_deadline_ts < release_ts", boundary["release_and_cutoff_rule"])
        self.assertIn("Outcome is available", boundary["historical_leakage_prevention"])
        secondary = self.protocol["secondary_metric_boundary"]
        self.assertEqual(tuple(secondary["authorized_descriptive_metrics"]), round2.SIX_METRICS[1:])
        self.assertIn("composite score", secondary["not_authorized"])

    def test_sample_and_slice_boundaries_are_bounded(self):
        sample = self.protocol["sample_size_and_stopping_design"]
        self.assertEqual(sample["target_eligible_episodes"], 120)
        self.assertEqual(sample["maximum_eligible_episodes"], 144)
        self.assertEqual(sample["target_common_paired_scoreable_observations"], 240)
        self.assertEqual(sample["minimum_common_paired_scoreable_observations_for_confirmatory_test"], 200)
        self.assertEqual(self.protocol["execution_cadence"]["maximum_episodes_per_slice"], 48)

    def test_tampering_fails_closed(self):
        tampered = copy.deepcopy(self.protocol)
        tampered["inferential_plan"]["test"] = "One-sided test"
        tampered["protocol_fingerprint"] = round2.digest({key: value for key, value in tampered.items() if key != "protocol_fingerprint"})
        with self.assertRaisesRegex(ValueError, "INFERENCE_SPECIFICATION"):
            round2.validate_protocol(tampered)

        tampered = copy.deepcopy(self.protocol)
        tampered["this_move_limits"]["provider_calls"] = 1
        tampered["protocol_fingerprint"] = round2.digest({key: value for key, value in tampered.items() if key != "protocol_fingerprint"})
        with self.assertRaisesRegex(ValueError, "LOCAL_ONLY_LIMIT"):
            round2.validate_protocol(tampered)

        tampered = copy.deepcopy(self.protocol)
        tampered["inferential_plan"]["alpha"] = 0.01
        with self.assertRaisesRegex(ValueError, "FINGERPRINT_CONFLICT"):
            round2.validate_protocol(tampered)

        tampered = copy.deepcopy(self.protocol)
        tampered["accepted_round_1_bindings"]["aggregate_result"]["sha256"] = "sha256:tampered"
        tampered["protocol_fingerprint"] = round2.digest({key: value for key, value in tampered.items() if key != "protocol_fingerprint"})
        with self.assertRaisesRegex(ValueError, "ACCEPTED_ARTIFACT_BINDING"):
            round2.validate_protocol(tampered)


if __name__ == "__main__":
    unittest.main()
