import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation.freeze_presignal_v21_slice_003_paired_exclusion_attachment_authorization import build_authorization, fingerprint, MANIFEST_DIR
from automation.run_presignal_v21_authorized_slice import validate_paired_exclusion_attachment


class Slice003PairedExclusionAttachmentAuthorizationTests(unittest.TestCase):
    def authorization(self):
        auth, proof = build_authorization("controller-test-commit")
        auth["authorization_id"] = "PPHB-R1-TEST-SLICE-003-PAIRED-EXCLUSION-ATTACHMENT"
        auth["authorization_fingerprint"] = fingerprint(auth)
        return auth, proof

    def test_exact_revised_population_and_no_call_boundary(self):
        auth, proof = self.authorization()
        self.assertEqual(proof["excluded_episodes"], 2)
        self.assertEqual(proof["eligible_episodes"], 10)
        self.assertEqual(proof["valid_candidates"], 10)
        self.assertEqual(proof["eligible_forecasts"], 32)
        self.assertEqual(proof["pack_a"], 16)
        self.assertEqual(proof["pack_e"], 16)
        self.assertEqual(proof["complete_pairs"], 16)
        self.assertEqual(auth["ceilings"], {"max_apps_script_reads": 0, "max_market_data_attempts": 0, "max_total_external_requests": 0, "google_write_ceiling": 0, "max_attachment_records": 10})
        self.assertFalse(auth["evaluation_authorized"])

    def test_controller_accepts_and_rejects_tampering(self):
        auth, _ = self.authorization()
        manifest = MANIFEST_DIR / "slice_003_manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authorization.json"
            path.write_text(json.dumps(auth))
            checked = validate_paired_exclusion_attachment(auth, json.loads(manifest.read_text()), auth["manifest_fingerprint"])
        self.assertEqual(checked["valid_candidate_count"], 10)
        tampered = copy.deepcopy(auth)
        tampered["ceilings"]["max_attachment_records"] = 11
        tampered["authorization_fingerprint"] = fingerprint(tampered)
        with self.assertRaises(SystemExit) as error:
            validate_paired_exclusion_attachment(tampered, json.loads(manifest.read_text()), tampered["manifest_fingerprint"])
        self.assertEqual(str(error.exception), "PAIRED_EXCLUSION_CEILING_CONFLICT")

    def test_blocked_authorizations_and_evaluation_are_not_reused(self):
        auth, _ = self.authorization()
        self.assertFalse(auth["evaluation_authorized"])
        self.assertEqual(auth["post_attachment_stop_state"], "SLICE_003_ATTACHMENT_RECONCILED_EVALUATION_AUTHORIZATION_REQUIRED")
        self.assertEqual(auth["exclusion_rule"].count("PACK_A"), 1)
        self.assertEqual(auth["exclusion_rule"].count("PACK_E"), 1)


if __name__ == "__main__":
    unittest.main()
