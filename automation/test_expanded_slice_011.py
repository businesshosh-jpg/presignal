import glob
import json
import unittest
from pathlib import Path

import automation.run_presignal_v21_authorized_slice as controller


BASE = Path(__file__).resolve().parents[1] / "outputs/presignal_v21_full_round_1_forecast_execution"


class ExpandedSlice011Test(unittest.TestCase):
    def setUp(self):
        self.manifest_path = next(BASE.glob("PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-011-*/slice_011_manifest.json"))
        self.auth_path = next(BASE.glob("PPHB-R1-OUTCOME-SLICE-011-END-TO-END-AUTHORIZATION-20260803T230000Z-*/authorization.json"))
        self.continuation_path = BASE / "PPHB-R1-OUTCOME-SLICE-011-PAIRED-EXCLUSION-END-TO-END-AUTHORIZATION-20260803T111500Z-eef0a8b7d52eb568f106/authorization.json"

    def test_expanded_population_and_ceiling(self):
        manifest = json.loads(self.manifest_path.read_text())
        auth = json.loads(self.auth_path.read_text())
        self.assertEqual(len(manifest["episode_manifest"]), 36)
        self.assertEqual(manifest["authorized_forecast_population"]["valid_forecasts"], 130)
        self.assertEqual(manifest["authorized_forecast_population"]["pack_a"], 65)
        self.assertEqual(manifest["authorized_forecast_population"]["pack_e"], 65)
        self.assertEqual(len(manifest["release_days_utc"]), 14)
        self.assertEqual(auth["ceilings"], {"max_apps_script_reads": 14, "max_market_data_attempts": 36, "max_total_external_requests": 50, "google_write_ceiling": 0, "max_attachment_records": 36, "max_evaluation_artifacts": 1})

    def test_zero_call_continuation_and_completion(self):
        auth = json.loads(self.continuation_path.read_text())
        self.assertEqual(auth["ceilings"]["max_total_external_requests"], 0)
        self.assertEqual(len(auth["authorized_identity_ids"]), 35)
        self.assertEqual(auth["evaluation_population"]["valid_forecasts"], 124)
        self.assertEqual(auth["evaluation_population"]["complete_pack_a_e_pairs"], 62)
        completion = json.loads(next(BASE.glob("PPHB-R1-OUTCOME-SLICE-011-COMPLETION-*/slice_completion.json")).read_text())
        self.assertEqual(completion["decision"], "AUTHORIZED_EXPANDED_SLICE_END_TO_END_COMPLETE")
        self.assertEqual(completion["external_operations"]["new_continuation_external_requests"], 0)

    def test_controller_offline_acceptance(self):
        auth = json.loads(self.auth_path.read_text())
        checked = controller.validate(self.auth_path, self.manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(len(checked["episode_ids"]), 36)


if __name__ == "__main__":
    unittest.main()
