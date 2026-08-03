from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import prepare_presignal_v21_round_2_pre_cutoff_acquisition as preparation


class PreCutoffAcquisitionPreparationTests(unittest.TestCase):
    def test_missing_prospective_shared_market_state_source_blocks_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            result = preparation.prepare(Path(directory) / "evidence")
        self.assertEqual(result["route"]["decision"], "ROUND_2_PRE_CUTOFF_PACK_ACQUISITION_ROUTE_CONFLICT")
        self.assertEqual(result["controller"]["state"], "PREREQUISITE_GOVERNANCE_BLOCKED")
        self.assertEqual(result["route"]["external_activity"]["provider_calls"], 0)
        self.assertEqual(result["controller"]["forecast_dispatch_authorization"], "NOT_PREPARED")


if __name__ == "__main__":
    unittest.main()
