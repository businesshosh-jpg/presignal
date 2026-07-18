import json
import tempfile
import unittest
from pathlib import Path

from automation.freeze_pack_ae_evaluation_contract_v1 import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CONTRACT_ID,
    PLAN_ID,
    SPLIT_ID,
    canonical_json,
    freeze,
    sha256_value,
)


class PackAeEvaluationContractFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.result = freeze(self.output)

    def tearDown(self):
        self.temp.cleanup()

    def read(self, filename):
        return json.loads((self.output / filename).read_text())

    def assert_artifact_fingerprint(self, artifact):
        fingerprint = artifact.pop("artifact_fingerprint")
        self.assertEqual(fingerprint, sha256_value(artifact))

    def test_all_artifact_fingerprints_reproduce(self):
        for filename in (
            "evaluation_contract.json",
            "historical_split_manifest.json",
            "value_blindness_audit.json",
            "implementation_validation_plan.json",
            "binding_manifest.json",
        ):
            self.assert_artifact_fingerprint(self.read(filename))

    def test_split_is_session_level_and_matches_frozen_counts(self):
        split = self.read("historical_split_manifest.json")
        self.assertEqual(split["artifact_id"], SPLIT_ID)
        rows = split["session_records"]
        self.assertEqual(len(rows), 195)
        self.assertEqual(len({row["session_id"] for row in rows}), 195)
        self.assertEqual(
            [row["partition"] for row in rows[:130]],
            ["HISTORICAL_DEVELOPMENT"] * 130,
        )
        self.assertEqual(
            [row["partition"] for row in rows[130:]],
            ["HISTORICAL_CONFIRMATORY_HOLDOUT"] * 65,
        )
        ordering = [(row["evaluation_start_timestamp"], row["session_id"]) for row in rows]
        self.assertEqual(ordering, sorted(ordering))
        summary = split["partition_summary"]
        self.assertEqual(summary["HISTORICAL_DEVELOPMENT"]["complete_pairs"], 376)
        self.assertEqual(
            summary["HISTORICAL_DEVELOPMENT"]["complete_pairs_by_provider"],
            {"Anthropic": 125, "Gemini": 129, "OpenAI": 122},
        )
        self.assertEqual(summary["HISTORICAL_CONFIRMATORY_HOLDOUT"]["complete_pairs"], 186)
        self.assertEqual(
            summary["HISTORICAL_CONFIRMATORY_HOLDOUT"]["complete_pairs_by_provider"],
            {"Anthropic": 65, "Gemini": 62, "OpenAI": 59},
        )
        self.assertEqual(split["governed_exclusions"]["sessions"], 44)
        self.assertEqual(split["governed_exclusions"]["predictions"], 261)

    def test_contract_freezes_requested_primary_endpoint_and_decision_rule(self):
        contract = self.read("evaluation_contract.json")
        self.assertEqual(contract["artifact_id"], CONTRACT_ID)
        primary = contract["primary_endpoint"]
        self.assertEqual(primary["name"], "PAIRED_ACTION_VALUE_DIFFERENCE")
        self.assertEqual(primary["allowed_pair_differences"], [-2, -1, 0, 1, 2])
        self.assertEqual(primary["forecast_action_value"]["NO_CLEAR_DIRECTION"], 0)
        self.assertIn("lower bound > 0", contract["decision_rule"]["PACK_E_IMPROVES_FORECASTING"])
        self.assertIn("upper bound < 0", contract["decision_rule"]["PACK_E_UNDERPERFORMS_PACK_A"])
        self.assertFalse(contract["overall_accuracy"]["new_composite_created"])

    def test_strength_normalization_and_bootstrap_are_exhaustive(self):
        contract = self.read("evaluation_contract.json")
        self.assertEqual(
            contract["strength_normalization"]["mapping"],
            {"WEAK": "WEAK", "MODERATE": "MEDIUM", "STRONG": "STRONG"},
        )
        uncertainty = contract["uncertainty"]
        self.assertEqual(uncertainty["seed"], BOOTSTRAP_SEED)
        self.assertEqual(uncertainty["resamples"], BOOTSTRAP_RESAMPLES)
        self.assertEqual(uncertainty["resampling_unit"], "MARKET_SESSION")
        self.assertIn("Type 7", uncertainty["quantile_algorithm"])

    def test_value_blindness_and_holdout_guards_are_explicit(self):
        audit = self.read("value_blindness_audit.json")
        self.assertEqual(audit["result"], "PASS_VALUE_BLIND")
        self.assertFalse(audit["performance_scoring_accessed"])
        self.assertFalse(audit["pair_score_differences_accessed"])
        plan = self.read("implementation_validation_plan.json")
        self.assertEqual(plan["artifact_id"], PLAN_ID)
        self.assertTrue(plan["holdout_protection"]["holdout_values_must_not_be_loaded_during_development_validation"])
        self.assertEqual(plan["holdout_protection"]["holdout_partition_open_count"], 1)

    def test_split_artifact_contains_no_performance_fields(self):
        text = canonical_json(self.read("historical_split_manifest.json")).lower()
        forbidden = (
            "action_value",
            "accuracy",
            "correctness",
            "pair_difference",
            "win_rate",
            "realized_direction",
            "realized_reaction_strength",
        )
        for field in forbidden:
            self.assertNotIn(field, text)


if __name__ == "__main__":
    unittest.main()
