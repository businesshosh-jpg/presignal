from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import reconcile_presignal_v21_round_2_first_slice_pack_inputs as reconciliation


class FirstSlicePackInputReconciliationTests(unittest.TestCase):
    def test_canonical_route_and_missing_input_partition_are_exact(self):
        validation = reconciliation.validate_missing_lineage()
        self.assertEqual(len(validation["missing_by_pack"]["A"]), 93)
        self.assertEqual(len(validation["missing_by_pack"]["E"]), 93)
        self.assertEqual(validation["required_fields"]["A"], ("provider_attention_map", "information_requests"))
        self.assertIn("shared_market_state_pack", validation["required_fields"]["E"])

    def test_reconciliation_does_not_create_dispatch_authority_or_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = reconciliation.reconcile(Path(directory) / "evidence")
        self.assertEqual(evidence["decisions"]["canonical_pack_construction"], "ROUND_2_CANONICAL_PACK_CONSTRUCTION_CONFIRMED")
        self.assertEqual(evidence["materialization"]["pack_a_input_artifacts"], 0)
        self.assertFalse(evidence["authority_boundary"]["replacement_authorization_created"])
        self.assertEqual(evidence["actuals"]["provider_calls"], 0)
        self.assertEqual(len(evidence["identity_partition"]["GOVERNANCE_BLOCKED_PACK_INPUT_AUTHORITY"]), 186)


if __name__ == "__main__":
    unittest.main()
