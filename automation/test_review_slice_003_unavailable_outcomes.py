import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-SLICE-003-UNAVAILABLE-OUTCOME-GOVERNANCE-REVIEW-20260803T073000Z"


class Slice003UnavailableOutcomeReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads((REVIEW_DIR / "governance_review.json").read_text())
        self.run = json.loads((REVIEW_DIR / "run_manifest.json").read_text())

    def test_exact_two_episode_scope_and_preserved_collection_counts(self):
        self.assertEqual(
            [item["episode_id"] for item in self.review["episodes"]],
            ["EP_EVENT_4b80366594480b554889", "EP_EVENT_aa41226bcb8107901555"],
        )
        self.assertEqual(
            self.review["preserved_collection_facts"],
            {"apps_script_reads": 10, "market_data_attempts": 12, "total_external_requests": 22,
             "google_writes": 0, "retries": 0, "candidate_outcome_records": 12,
             "attachment_records": 0, "evaluation_started": False, "remote_state": "CERTAIN"},
        )

    def test_classification_and_paired_population_are_deterministic(self):
        first, second = self.review["episodes"]
        self.assertEqual(first["classification"], "OUTCOME_TERMINALLY_UNAVAILABLE_UNDER_CURRENT_SOURCE")
        self.assertEqual(second["classification"], "OUTCOME_REQUIRES_SEPARATE_EXTERNAL_RECOVERY_AUTHORIZATION")
        self.assertFalse(first["deterministic_recovery_from_preserved_evidence"])
        self.assertFalse(second["deterministic_recovery_from_preserved_evidence"])
        population = self.review["treatment_options"]["A_paired_exclusion"]["population_after_exclusion"]
        self.assertEqual(population, {"episodes": 10, "valid_forecasts": 32, "pack_a": 16, "pack_e": 16, "complete_pairs": 16, "excluded_forecasts": 8})
        excluded = self.review["proposed_next_authorization"]["exact_forecast_exclusions"]
        self.assertEqual(len(excluded), 8)
        self.assertEqual(len(set(excluded)), 8)

    def test_review_performed_no_external_or_scientific_operation(self):
        self.assertEqual(self.review["recommended_decision"], "AUTHORIZE_PAIRED_EXCLUSION_OF_TWO_UNAVAILABLE_EPISODES")
        self.assertEqual(self.review["readiness_decision"], "SLICE_003_RESUME_AUTHORIZATION_READY")
        self.assertEqual(self.run["external_requests"], 0)
        self.assertEqual(self.run["google_writes"], 0)
        self.assertEqual(self.run["outcome_attachments"], 0)
        self.assertEqual(self.run["evaluation_calculations"], 0)
        self.assertFalse(self.run["preserved_evidence_modified"])


if __name__ == "__main__":
    unittest.main()
