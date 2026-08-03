"""Call-free OAuth-route checks for Outcome Slice 001."""

import json
import unittest
from pathlib import Path

from automation.google_clients import CREDENTIALS_PATH, TOKEN_PATH


ROOT = Path(__file__).resolve().parents[1]
RUNS = sorted(ROOT.glob("outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-OUTCOME-OAUTH-RESTORATION-SLICE-001-*"))


class OutcomeOAuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = RUNS[-1]
        cls.oauth = json.loads((cls.run_dir / "oauth_route_evidence.json").read_text())
        cls.preflight = json.loads((cls.run_dir / "preflight_decision.json").read_text())
        cls.reconciliation = json.loads((cls.run_dir / "collection_reconciliation.json").read_text())

    def test_accepted_route_and_manifest_are_fixed(self):
        self.assertEqual(self.oauth["resolved_token_path"], str(TOKEN_PATH))
        self.assertEqual(self.oauth["resolved_client_secret_path"], str(CREDENTIALS_PATH))
        self.assertEqual(self.preflight["manifest_sha256"], "sha256:90765146ec192c58fe841b61b49d239fae321a99b2a73d3f8529ceeaad9f41c8")
        self.assertEqual(self.preflight["episode_count"], 12)

    def test_missing_route_fails_closed_without_side_effects(self):
        self.assertEqual(self.oauth["decision"], "GOOGLE_OAUTH_ROUTE_NOT_RESTORED")
        self.assertEqual(self.oauth["credential_error_code"], "GOOGLE_OAUTH_TOKEN_MISSING")
        self.assertFalse(self.oauth["parallel_route_created"])
        self.assertEqual(self.reconciliation["total_external_requests"], 0)
        self.assertEqual(self.reconciliation["google_writes"], 0)
        self.assertEqual(self.reconciliation["outcome_attachment"], 0)
        self.assertEqual(self.reconciliation["evaluation_calculations"], 0)


if __name__ == "__main__":
    unittest.main()
