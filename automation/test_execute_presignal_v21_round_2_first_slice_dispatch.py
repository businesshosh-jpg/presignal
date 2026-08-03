from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import execute_presignal_v21_round_2_first_slice_dispatch as dispatch


class FirstSliceDispatchPreflightTests(unittest.TestCase):
    def test_exact_authority_and_shared_pack_input_block(self):
        authorization, manifest, calls = dispatch.validate_frozen_authority()
        self.assertEqual(authorization["maximum_provider_calls"], 186)
        self.assertEqual(manifest["manifest_fingerprint"], dispatch.MANIFEST_FINGERPRINT)
        self.assertEqual(len(calls), 186)
        self.assertEqual(sum("pack_input_payload" not in call for call in calls), 186)

    def test_preflight_creates_no_lease_or_reservations(self):
        with tempfile.TemporaryDirectory() as directory:
            result = dispatch.preflight(Path(directory) / "evidence")
            self.assertEqual(result["decision"], "ROUND_2_FIRST_SLICE_FORECAST_EXECUTION_GOVERNANCE_BLOCKED")
            self.assertEqual(result["actuals"]["provider_calls"], 0)
            self.assertFalse(result["lease"]["acquired"])
            self.assertEqual(result["reservations"]["created"], 0)
            self.assertEqual(len(result["identity_partition"]["GOVERNANCE_BLOCKED_PACK_INPUT_AUTHORITY"]), 186)


if __name__ == "__main__":
    unittest.main()
