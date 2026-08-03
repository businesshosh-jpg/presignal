import json
import unittest
from pathlib import Path


ARTIFACT = Path(__file__).resolve().parents[1] / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-PROSPECTIVE-OUTCOME-EVALUATION-STAGE-COMPLETION-20260804T040000Z"


class ProspectiveStageCompletionTest(unittest.TestCase):
    def setUp(self):
        self.reconciliation = json.loads((ARTIFACT / "stage_completion_reconciliation.json").read_text())
        self.aggregate = json.loads((ARTIFACT / "aggregate_evaluation_authorization_boundary.json").read_text())

    def test_episode_partition_is_complete_and_disjoint(self):
        status = self.reconciliation["episode_status_partition"]
        sets = [set(value) for value in status.values()]
        self.assertEqual(sum(map(len, sets)), 151)
        self.assertEqual(len(set.union(*sets)), 151)
        self.assertTrue(all(not (left & right) for i, left in enumerate(sets) for right in sets[i + 1:]))
        self.assertEqual(len(status["eligible_not_processed"]), 0)
        self.assertEqual(len(status["unresolved"]), 0)

    def test_forecast_and_slice_reconciliation(self):
        self.assertEqual(self.reconciliation["total_frozen_forecast_identities"], 564)
        self.assertEqual(self.reconciliation["authoritative_valid_forecasts"], 561)
        self.assertEqual(len(self.reconciliation["terminal_invalid_forecast_calls"]), 3)
        self.assertEqual(self.reconciliation["available_outcomes_attached"], 138)
        self.assertEqual(self.reconciliation["forecast_records_evaluated"], 518)
        self.assertEqual(self.reconciliation["remaining_eligible_episodes"], 0)
        self.assertEqual(self.reconciliation["duplicate_outcome_attachment"], 0)
        self.assertEqual(self.reconciliation["duplicate_evaluation"], 0)

    def test_aggregate_evaluation_remains_unauthorized(self):
        self.assertEqual(self.aggregate["decision"], "AGGREGATE_EVALUATION_REMAINS_UNAUTHORIZED")
        self.assertFalse(self.aggregate["aggregate_metrics_calculated"])


if __name__ == "__main__":
    unittest.main()
