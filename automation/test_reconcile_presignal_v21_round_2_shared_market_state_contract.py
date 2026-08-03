from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import reconcile_presignal_v21_round_2_shared_market_state_contract as reconciliation


class SharedMarketStateContractTests(unittest.TestCase):
    def test_no_prospective_source_blocks_contract_without_external_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = reconciliation.reconcile(Path(directory) / "evidence")
        self.assertEqual(evidence["decisions"]["contract"], "ROUND_2_SHARED_MARKET_STATE_CONTRACT_BLOCKED")
        self.assertEqual(evidence["source_authority"]["current_deployed_equivalent"], "NONE")
        self.assertFalse(evidence["source_authority"]["deployed_return_only_entrypoint"])
        self.assertEqual(evidence["external_activity"]["provider_calls"], 0)
        self.assertIn("source_timestamp", evidence["canonical_pack_e_schema"]["item_required_fields"])


if __name__ == "__main__":
    unittest.main()
