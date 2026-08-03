import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation.freeze_presignal_v21_slice_003_authorization import MANIFEST_DIR, build_authorization
from automation.run_presignal_v21_authorized_slice import validate


class Slice003AuthorizationTests(unittest.TestCase):
    def test_blocked_authorization_is_not_reusable(self):
        auth = build_authorization("controller-test-commit")
        manifest_path = MANIFEST_DIR / "slice_003_manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            auth_path = Path(directory) / "authorization.json"
            auth_path.write_text(json.dumps(auth))
            with self.assertRaises(SystemExit) as error:
                validate(auth_path, manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(str(error.exception), "AUTHORIZATION_NON_REUSABLE_BLOCKED")

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
            self.assertEqual(str(error.exception), "AUTHORIZATION_NON_REUSABLE_BLOCKED")

            cross_slice = copy.deepcopy(auth)
            cross_slice["slice_id"] = "SLICE-002"
            cross_slice["authorization_fingerprint"] = __import__("automation.run_presignal_v21_authorized_slice", fromlist=["fingerprint"]).fingerprint(cross_slice)
            auth_path.write_text(json.dumps(cross_slice))
            with self.assertRaises(SystemExit) as error:
                validate(auth_path, manifest_path, auth["manifest_fingerprint"], "manifest", end_to_end=True)
            self.assertEqual(str(error.exception), "AUTHORIZATION_NON_REUSABLE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
