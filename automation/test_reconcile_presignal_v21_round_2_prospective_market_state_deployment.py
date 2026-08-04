from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import reconcile_presignal_v21_round_2_prospective_market_state_deployment as reconciliation


class ProspectiveMarketStateDeploymentTests(unittest.TestCase):
    def test_historical_field_universe_cannot_be_promoted_to_live_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = reconciliation.reconcile(Path(directory) / "evidence")
        self.assertEqual(evidence["decisions"]["field_contract"], "ROUND_2_SHARED_MARKET_STATE_FIELD_CONTRACT_BLOCKED")
        self.assertEqual(evidence["decisions"]["adapter"], "ROUND_2_PROSPECTIVE_SHARED_MARKET_STATE_ADAPTER_BLOCKED")
        self.assertEqual(len(evidence["historical_evidence"]["base_field_universe"]), 18)
        self.assertFalse(evidence["deployment"]["attempted"])
        self.assertEqual(evidence["deployment"]["google_writes"], 0)


if __name__ == "__main__":
    unittest.main()
