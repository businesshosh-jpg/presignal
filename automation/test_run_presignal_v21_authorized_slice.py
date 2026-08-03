import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121500Z-9c7adf4c2f2e"
MANIFEST = RUN / "slice_002_manifest.json"
AUTH = RUN / "controller_validation_authorization.json"
EXPECTED = "sha256:16e231a854572c72e1869ff04d3c6dcb038021af7bfe9bb059a05b2104c5270c"


def auth_fingerprint(value):
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


class AuthorizedSliceControllerTest(unittest.TestCase):
    def run_controller(self, auth=AUTH, manifest=MANIFEST, expected=EXPECTED, stage="manifest"):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.json"
            return subprocess.run([
                sys.executable, str(ROOT / "automation" / "run_presignal_v21_authorized_slice.py"),
                "--authorization", str(auth), "--manifest", str(manifest),
                "--expected-manifest-sha", expected, "--stage", stage,
                "--offline-validation", "--output", str(output),
            ], capture_output=True, text=True)

    def test_slice_002_manifest_stops_before_collection(self):
        result = self.run_controller()
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(result.stdout) if result.stdout.strip() else None
        self.assertIsNone(evidence)

    def test_fingerprint_mismatch_fails_closed(self):
        result = self.run_controller(expected="sha256:" + "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MANIFEST_FINGERPRINT_CONFLICT", result.stderr)

    def test_missing_fields_and_excessive_limits_fail_closed(self):
        original = json.loads(AUTH.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            missing = dict(original)
            missing.pop("destination")
            missing["authorization_fingerprint"] = auth_fingerprint(missing)
            path.write_text(json.dumps(missing))
            result = self.run_controller(auth=path)
            self.assertIn("AUTHORIZATION_FIELDS_MISSING:destination", result.stderr)

            excessive = dict(original)
            excessive["ceilings"] = dict(excessive["ceilings"], max_total_external_requests=16)
            excessive["authorization_fingerprint"] = auth_fingerprint(excessive)
            path.write_text(json.dumps(excessive))
            result = self.run_controller(auth=path)
            self.assertIn("AUTHORIZATION_CEILING_CONFLICT", result.stderr)

    def test_inactive_collection_cannot_execute_offline(self):
        result = self.run_controller(stage="collect")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("STAGE_AUTHORIZATION_NOT_ACTIVE", result.stderr)

    def test_fixture_proves_zero_access_and_stage_reuse(self):
        evidence = json.loads((RUN / "controller_validation_evidence.json").read_text())
        self.assertEqual(evidence["decision"], "MANIFEST_ACCEPTED_COLLECTION_AUTHORIZATION_REQUIRED")
        self.assertEqual(evidence["external_access"], {"google_reads": 0, "google_writes": 0, "market_data_attempts": 0, "total_external_requests": 0})
        source = (ROOT / "automation" / "run_presignal_v21_authorized_slice.py").read_text()
        for name in ("collect_presignal_v21_outcome_slice_001.py", "attach_presignal_v21_outcome_slice_001.py", "evaluate_presignal_v21_outcome_slice_001.py"):
            self.assertIn(name, source)


if __name__ == "__main__":
    unittest.main()
