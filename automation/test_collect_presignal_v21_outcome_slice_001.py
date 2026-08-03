"""Call-free checks for the bounded Outcome collection slice."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T000113Z-ceeaad9f41c8"


class OutcomeCollectionSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preflight = json.loads((RUN / "preflight_decision.json").read_text())
        cls.reconciliation = json.loads((RUN / "collection_reconciliation.json").read_text())
        cls.decision = json.loads((RUN / "collection_decision.json").read_text())
        cls.failure = json.loads((RUN / "collection_failure.json").read_text())

    def test_preflight_manifest_and_contract(self):
        self.assertEqual(self.preflight["decision"], "OUTCOME_SOURCE_PREFLIGHT_PASSED")
        self.assertEqual(self.preflight["episode_count"], 12)
        self.assertEqual(len(set(self.preflight["episode_ids"])), 12)
        self.assertEqual(self.preflight["contract"], "presignal_event_path_contract_v1_1")
        self.assertEqual(self.preflight["schema_version"], "2.1.1")

    def test_limits_and_no_side_effects(self):
        self.assertEqual(self.reconciliation["apps_script_reads"], 0)
        self.assertEqual(self.reconciliation["market_data_provider_attempts"], 0)
        self.assertEqual(self.reconciliation["total_external_requests"], 0)
        self.assertEqual(self.reconciliation["google_writes"], 0)
        self.assertEqual(self.reconciliation["outcome_attachment"], 0)
        self.assertEqual(self.reconciliation["evaluation_calculations"], 0)

    def test_missing_oauth_fails_closed(self):
        self.assertEqual(self.decision["collection_decision"], "OUTCOME_COLLECTION_SLICE_001_BLOCKED")
        self.assertEqual(self.failure["classification"], "GOOGLE_OAUTH_TOKEN_MISSING")
        self.assertEqual(self.failure["automatic_retries"], 0)


if __name__ == "__main__":
    unittest.main()
