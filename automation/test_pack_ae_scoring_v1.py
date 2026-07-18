import json
import tempfile
import unittest
from pathlib import Path

from automation import pack_ae_scoring_v1 as scoring


class PackAEScoringUnitTests(unittest.TestCase):
    def test_action_value_correct_and_incorrect(self):
        self.assertEqual(scoring.action_value("UP", "UP"), 1)
        self.assertEqual(scoring.action_value("DOWN", "UP"), -1)

    def test_no_clear_direction_is_zero(self):
        for realized in ("UP", "DOWN", "FLAT"):
            self.assertEqual(scoring.action_value("NO_CLEAR_DIRECTION", realized), 0)

    def test_flat_is_actionable(self):
        self.assertEqual(scoring.action_value("FLAT", "FLAT"), 1)
        self.assertEqual(scoring.action_value("FLAT", "UP"), -1)

    def test_all_possible_pair_differences(self):
        observed = {scoring.pair_difference(a, e) for a in (-1, 0, 1) for e in (-1, 0, 1)}
        self.assertEqual(observed, {-2, -1, 0, 1, 2})

    def test_provider_averaging_within_session(self):
        rows = [
            {"session_id": "s1", "pair_difference": 2},
            {"session_id": "s1", "pair_difference": -1},
            {"session_id": "s2", "pair_difference": -2},
        ]
        self.assertEqual(scoring.average_pairs_within_sessions(rows), {"s1": 0.5, "s2": -2.0})

    def test_provider_rows_are_not_independent_sessions(self):
        rows = [
            {"session_id": "s1", "pair_difference": 2},
            {"session_id": "s1", "pair_difference": 2},
            {"session_id": "s1", "pair_difference": 2},
            {"session_id": "s2", "pair_difference": -2},
        ]
        session_values = scoring.average_pairs_within_sessions(rows)
        self.assertEqual(len(session_values), 2)
        self.assertEqual(sum(session_values.values()) / len(session_values), 0.0)

    def test_bootstrap_is_deterministic(self):
        values = {"s1": -1.0, "s2": 0.0, "s3": 1.0}
        first = scoring.cluster_bootstrap_interval(values, seed=77, resamples=500)
        second = scoring.cluster_bootstrap_interval(values, seed=77, resamples=500)
        self.assertEqual(first, second)

    def test_type7_interpolation(self):
        self.assertAlmostEqual(scoring.type7_quantile([0, 10, 20, 30], 0.25), 7.5)
        self.assertAlmostEqual(scoring.type7_quantile([0, 10, 20, 30], 0.975), 29.25)

    def test_strength_normalization(self):
        self.assertEqual(scoring.normalize_strength("WEAK"), "WEAK")
        self.assertEqual(scoring.normalize_strength("MODERATE"), "MEDIUM")
        self.assertEqual(scoring.normalize_strength("STRONG"), "STRONG")

    def test_actionable_accuracy_denominator_excludes_no_clear(self):
        rows = [
            {"a_direction": "UP", "a_action_value": 1},
            {"a_direction": "DOWN", "a_action_value": -1},
            {"a_direction": "NO_CLEAR_DIRECTION", "a_action_value": 0},
        ]
        summary = scoring.summarize_arm(rows, "A")
        self.assertEqual(summary["actionable_count"], 2)
        self.assertEqual(summary["actionable_accuracy"], 0.5)
        self.assertEqual(summary["actionable_coverage"], 2 / 3)

    def test_holdout_partition_is_rejected(self):
        partitions, _ = scoring.load_partition_manifest()
        holdout_ids = [session_id for session_id, partition in partitions.items() if partition == "HISTORICAL_CONFIRMATORY_HOLDOUT"]
        self.assertEqual(len(holdout_ids), 65)
        for session_id in holdout_ids:
            with self.assertRaises(scoring.HoldoutAccessError):
                scoring.require_development_session(session_id, partitions)

    def test_fingerprint_is_deterministic(self):
        payload = {"z": [3, 2, 1], "a": {"x": True}}
        self.assertEqual(scoring.with_fingerprint(payload), scoring.with_fingerprint(payload))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            scoring.write_json(path, scoring.with_fingerprint(payload))
            loaded = json.loads(path.read_text())
            self.assertEqual(loaded["artifact_fingerprint"], scoring.with_fingerprint(payload)["artifact_fingerprint"])


class PackAEScoringDevelopmentPopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.diagnostics = scoring.load_development_inputs()

    def test_exact_development_population_reconciles(self):
        self.assertEqual(len({row["session_id"] for row in self.inputs}), 130)
        self.assertEqual(len(self.inputs), 376)
        self.assertEqual(
            self.diagnostics["provider_pair_counts"],
            {"Anthropic": 125, "Gemini": 129, "OpenAI": 122},
        )

    def test_holdout_rows_are_not_deserialized_or_opened(self):
        self.assertEqual(self.diagnostics["holdout_prediction_files_opened"], 0)
        self.assertEqual(self.diagnostics["holdout_canonical_rows_deserialized"], 0)
        self.assertEqual(self.diagnostics["holdout_attachment_rows_deserialized"], 0)

    def test_pair_scoring_reconciles_and_uses_allowed_values(self):
        rows = scoring.score_pairs(self.inputs)
        self.assertEqual(len(rows), 376)
        self.assertTrue(all(row["pair_difference"] in {-2, -1, 0, 1, 2} for row in rows))
        self.assertEqual(len(scoring.average_pairs_within_sessions(rows)), 130)


if __name__ == "__main__":
    unittest.main()
