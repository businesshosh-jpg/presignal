import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation.freeze_presignal_v21_slice_003_replacement_authorization import (
    MANIFEST_DIR,
    build_authorization,
)
from automation.run_presignal_v21_authorized_slice import fingerprint, validate


class Slice003ReplacementAuthorizationTests(unittest.TestCase):
    @staticmethod
    def test_authorization():
        auth, proof = build_authorization("controller-test-commit")
        auth["authorization_id"] = "PPHB-R1-TEST-SLICE-003-REPLACEMENT-AUTHORIZATION"
        auth["authorization_fingerprint"] = fingerprint(auth)
        return auth, proof

    def test_day_bound_replacement_is_accepted(self):
        auth, proof = self.test_authorization()
        manifest = MANIFEST_DIR / "slice_003_manifest.json"
        self.assertEqual(proof["distinct_release_day_count"], 10)
        self.assertEqual(auth["ceilings"]["max_apps_script_reads"], 10)
        self.assertEqual(auth["ceilings"]["max_total_external_requests"], 22)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            path.write_text(json.dumps(auth))
            checked = validate(path, manifest, auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(len(checked["episode_ids"]), 12)
        self.assertEqual(checked["manifest"]["authorized_forecast_population"]["complete_pack_a_e_pairs"], 20)

    def test_ceiling_tampering_fails_closed(self):
        auth, _ = self.test_authorization()
        auth["ceilings"]["max_apps_script_reads"] = 9
        auth["authorization_fingerprint"] = fingerprint(auth)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            path.write_text(json.dumps(auth))
            with self.assertRaises(SystemExit) as error:
                validate(path, MANIFEST_DIR / "slice_003_manifest.json", auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(str(error.exception), "AUTHORIZATION_CEILING_CONFLICT")

    def test_day_set_tampering_fails_closed(self):
        auth, _ = self.test_authorization()
        auth["release_days_utc"][0] = "2024-05-05"
        auth["authorization_fingerprint"] = fingerprint(auth)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            path.write_text(json.dumps(auth))
            with self.assertRaises(SystemExit) as error:
                validate(path, MANIFEST_DIR / "slice_003_manifest.json", auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(str(error.exception), "RELEASE_DAY_SET_CONFLICT")

    def test_blocked_authorization_is_not_reusable(self):
        old = next(Path("outputs/presignal_v21_full_round_1_forecast_execution").glob("PPHB-R1-OUTCOME-SLICE-003-END-TO-END-AUTHORIZATION-20260803T160000Z-*/authorization.json"))
        auth = json.loads(old.read_text())
        with self.assertRaises(SystemExit) as error:
            validate(old, MANIFEST_DIR / "slice_003_manifest.json", auth["manifest_fingerprint"], "manifest", end_to_end=True)
        self.assertEqual(str(error.exception), "AUTHORIZATION_NON_REUSABLE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
