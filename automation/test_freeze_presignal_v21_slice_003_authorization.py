import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation.freeze_presignal_v21_slice_003_authorization import MANIFEST_DIR, build_authorization
from automation.run_presignal_v21_authorized_slice import validate


class Slice003AuthorizationTests(unittest.TestCase):
    def test_exact_authorization_is_accepted_offline(self):
        auth = build_authorization("controller-test-commit")
        manifest_path = MANIFEST_DIR / "slice_003_manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            auth_path = Path(directory) / "authorization.json"
            auth_path.write_text(json.dumps(auth))
            checked = validate(auth_path, manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(checked["auth"]["slice_id"], "SLICE-003")
        self.assertEqual(len(checked["episode_ids"]), 12)
        self.assertEqual(checked["manifest"]["authorized_forecast_population"]["complete_pack_a_e_pairs"], 20)
        self.assertEqual(checked["auth"]["ceilings"]["max_total_external_requests"], 15)

    def test_tampering_and_cross_slice_reuse_fail_closed(self):
        auth = build_authorization("controller-test-commit")
        manifest_path = MANIFEST_DIR / "slice_003_manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            auth_path = Path(directory) / "authorization.json"
            tampered = copy.deepcopy(auth)
            tampered["ceilings"]["max_total_external_requests"] = 16
            auth_path.write_text(json.dumps(tampered))
            with self.assertRaises(SystemExit) as error:
                validate(auth_path, manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
            self.assertEqual(str(error.exception), "AUTHORIZATION_FINGERPRINT_MISMATCH")

            cross_slice = copy.deepcopy(auth)
            cross_slice["slice_id"] = "SLICE-002"
            cross_slice["authorization_fingerprint"] = __import__("automation.run_presignal_v21_authorized_slice", fromlist=["fingerprint"]).fingerprint(cross_slice)
            auth_path.write_text(json.dumps(cross_slice))
            with self.assertRaises(SystemExit) as error:
                validate(auth_path, manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
            self.assertEqual(str(error.exception), "MANIFEST_IDENTITY_CONFLICT")


if __name__ == "__main__":
    unittest.main()
