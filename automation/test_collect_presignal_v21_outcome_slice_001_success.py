"""Call-free reconciliation checks for the successful Outcome Slice 001 run."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8"


class SuccessfulOutcomeCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.final = json.loads((RUN / "collection_finalization.json").read_text())
        cls.ledger = json.loads((RUN / "external_request_ledger.jsonl").read_text())
        cls.candidates = json.loads((RUN / "candidate_outcomes.jsonl").read_text())

    def test_limits_identity_and_schema(self):
        self.assertEqual(self.final["manifest_episode_count"], 12)
        self.assertEqual(self.final["apps_script_reads"], 3)
        self.assertEqual(self.final["market_data_provider_attempts"], 3)
        self.assertEqual(self.final["total_external_requests"], 6)
        self.assertEqual(self.final["candidate_outcomes"], 12)
        self.assertEqual(self.final["schema_validated_candidates"], 12)
        self.assertEqual(self.final["unresolved_identities"], [])

    def test_provider_lineage_and_teardown(self):
        self.assertEqual({row["selected_provider"] for row in self.ledger}, {"tiingo"})
        self.assertTrue(all(row["provider_attempt_count"] == 1 for row in self.ledger))
        self.assertTrue(self.final["transport_teardown_passed"])
        self.assertTrue(all(row["status"] == "VALID" for row in self.candidates))

    def test_no_attachment_or_evaluation(self):
        self.assertEqual(self.final["google_writes"], 0)
        self.assertEqual(self.final["outcome_attachment"], 0)
        self.assertEqual(self.final["evaluation_calculations"], 0)


if __name__ == "__main__":
    unittest.main()
