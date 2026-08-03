import glob
import json
import unittest
from pathlib import Path

import automation.run_presignal_v21_authorized_slice as controller


BASE = Path(__file__).resolve().parents[1] / "outputs/presignal_v21_full_round_1_forecast_execution"


class ExpandedSlice012Test(unittest.TestCase):
    def setUp(self):
        self.manifest = next(BASE.glob("PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-012-*/slice_012_manifest.json"))
        self.auth = next(BASE.glob("PPHB-R1-OUTCOME-SLICE-012-END-TO-END-AUTHORIZATION-*/authorization.json"))

    def test_frontier_is_bounded_below_48_and_exactly_pairable(self):
        manifest = json.loads(self.manifest.read_text())
        population = manifest["authorized_forecast_population"]
        self.assertEqual(len(manifest["episode_manifest"]), 3)
        self.assertLessEqual(len(manifest["episode_manifest"]), 48)
        self.assertEqual(population["valid_forecasts"], 14)
        self.assertEqual(population["pack_a"], population["pack_e"])
        self.assertEqual(population["complete_pack_a_e_pairs"], 7)
        self.assertEqual(population["unpaired"], 0)
        self.assertEqual(len(manifest["release_days_utc"]), 1)

    def test_dynamic_authorization_and_controller_acceptance(self):
        auth = json.loads(self.auth.read_text())
        self.assertEqual(auth["ceilings"]["max_apps_script_reads"], 1)
        self.assertEqual(auth["ceilings"]["max_market_data_attempts"], 3)
        self.assertEqual(auth["ceilings"]["max_total_external_requests"], 4)
        checked = controller.validate(self.auth, self.manifest, auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(len(checked["episode_ids"]), 3)

    def test_completion_has_no_unavailable_treatment(self):
        completion = json.loads(next(BASE.glob("PPHB-R1-OUTCOME-SLICE-012-COMPLETION-*/slice_completion.json")).read_text())
        self.assertEqual(completion["unavailable_outcomes"], [])
        self.assertEqual(completion["external_operations"]["total_external_requests"], 2)
        self.assertEqual(completion["external_operations"]["local_attachments"], 3)


if __name__ == "__main__":
    unittest.main()
