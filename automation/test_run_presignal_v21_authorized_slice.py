import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from automation.run_presignal_v21_authorized_slice import simulate_end_to_end_route


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121500Z-9c7adf4c2f2e"
MANIFEST = RUN / "slice_002_manifest.json"
AUTH = RUN / "controller_validation_authorization.json"
ACTIVE_AUTH = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-20260803T140000Z-e8e69ad49e46" / "authorization.json"
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

    def test_end_to_end_clean_route_progresses_without_intermediate_authorization(self):
        result = simulate_end_to_end_route()
        self.assertEqual(result["decision"], "AUTHORIZED_SLICE_COMPLETE")
        self.assertEqual(result["progression"], [
            "COLLECTION_COMPLETE", "ATTACHMENT_RECONCILED",
            "MINIMAL_EVALUATION_COMPLETE", "AUTHORIZED_SLICE_COMPLETE",
        ])
        self.assertFalse(result["requires_new_authorization"])

    def test_end_to_end_stops_on_partial_or_ambiguous_stage(self):
        for stage, state in (("collection", "PARTIAL"), ("attachment", "DUPLICATE_OUTCOME"), ("evaluation", "UNRESOLVED_POPULATION"), ("final", "REMOTE_STATE_UNKNOWN")):
            result = simulate_end_to_end_route({"collection": "COMPLETE", "attachment": "RECONCILED", "evaluation": "COMPLETE", "final": "COMPLETE", stage: state})
            self.assertEqual(result["decision"], "END_TO_END_ROUTE_STOPPED")
            self.assertEqual(result["failed_stage"], stage)
            self.assertTrue(result["requires_new_authorization"])

    def test_end_to_end_inactive_fixture_stops_before_external_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.json"
            inactive = json.loads(ACTIVE_AUTH.read_text())
            inactive["authorization_status"] = "PROPOSED"
            inactive["authorization_fingerprint"] = auth_fingerprint(inactive)
            auth_path = Path(tmp) / "inactive_authorization.json"
            auth_path.write_text(json.dumps(inactive))
            result = subprocess.run([
                sys.executable, str(ROOT / "automation" / "run_presignal_v21_authorized_slice.py"),
                "--authorization", str(auth_path),
                "--manifest", str(MANIFEST), "--expected-manifest-sha", EXPECTED,
                "--end-to-end", "--mock-clean-route", "--offline-validation", "--output", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(output.read_text())
            self.assertEqual(evidence["decision"], "MANIFEST_ACCEPTED_END_TO_END_AUTHORIZATION_REQUIRED")
            self.assertEqual(evidence["external_access"]["total_external_requests"], 0)

    def test_active_authorization_is_ready_but_not_started(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.json"
            subprocess.run([
                sys.executable, str(ROOT / "automation" / "run_presignal_v21_authorized_slice.py"),
                "--authorization", str(ACTIVE_AUTH), "--manifest", str(MANIFEST),
                "--expected-manifest-sha", EXPECTED, "--end-to-end", "--offline-validation", "--output", str(output),
            ], check=True)
            evidence = json.loads(output.read_text())
            self.assertEqual(evidence["decision"], "SLICE_002_END_TO_END_EXECUTION_AUTHORIZED_NOT_STARTED")
            self.assertEqual(evidence["recognized_ceilings"]["max_attachment_records"], 12)
            self.assertEqual(evidence["external_access"]["total_external_requests"], 0)

    def test_active_authorization_tampering_fails_closed(self):
        original = json.loads(ACTIVE_AUTH.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            tampered = dict(original)
            tampered["permitted_metrics"] = list(original["permitted_metrics"]) + ["unsupported metric"]
            tampered["authorization_fingerprint"] = auth_fingerprint(tampered)
            path.write_text(json.dumps(tampered))
            result = subprocess.run([
                sys.executable, str(ROOT / "automation" / "run_presignal_v21_authorized_slice.py"),
                "--authorization", str(path), "--manifest", str(MANIFEST),
                "--expected-manifest-sha", EXPECTED, "--end-to-end", "--offline-validation",
            ], capture_output=True, text=True)
            self.assertIn("PERMITTED_METRICS_CONFLICT", result.stderr)


if __name__ == "__main__":
    unittest.main()
