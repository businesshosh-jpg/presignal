import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
MANIFEST = BASE / "PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477" / "next_authorization_draft.json"
MANIFEST_SHA = "sha256:90765146ec192c58fe841b61b49d239fae321a99b2a73d3f8529ceeaad9f41c8"
RUNNER = ROOT / "automation" / "run_presignal_v21_outcome_slice.py"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def auth_file(path, permitted=None, ceilings=None):
    value = {
        "slice_id": "SLICE-001",
        "manifest_path": str(MANIFEST),
        "manifest_sha256": MANIFEST_SHA,
        "permitted_stages": permitted or ["collect", "attach", "evaluate"],
        "ceilings": ceilings or {"max_apps_script_reads": 3, "max_market_data_attempts": 12, "max_total_external_requests": 15, "google_write_ceiling": 0},
        "retry_policy": "none",
        "contract": "presignal_event_path_contract_v1_1",
        "schema": "2.1.1",
        "google_token_env": "PRESIGNAL_GOOGLE_TOKEN_PATH",
        "prohibited_operations": ["next_slice", "google_writes", "evaluation_outside_slice"],
    }
    value["authorization_fingerprint"] = "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()
    path.write_text(json.dumps(value, indent=2) + "\n")


class OutcomeSliceRunnerTest(unittest.TestCase):
    def run_runner(self, auth, *flags, run_id=None):
        command = [sys.executable, str(RUNNER), "--authorization", str(auth), "--manifest", str(MANIFEST), "--expected-manifest-sha", MANIFEST_SHA, "--slice-id", "SLICE-001", *flags]
        if run_id:
            shutil.rmtree(BASE / ".outcome_slice_runner" / "runs" / run_id, ignore_errors=True)
            command += ["--run-id", run_id]
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    def test_default_is_preflight_only(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth_file(auth)
            run_id = "PPHB-R1-OUTCOME-SLICE-RUN-TEST-PREFLIGHT"
            result = self.run_runner(auth, run_id=run_id)
            self.assertEqual(result.returncode, 0, result.stderr)
            decision = json.loads((BASE / ".outcome_slice_runner" / "runs" / run_id / "stage_decisions.json").read_text())
            self.assertEqual(decision["requested_stages"], [])
            self.assertEqual(decision["preflight"], "OUTCOME_SLICE_PREFLIGHT_PASSED")

    def test_authorization_and_limit_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth_file(auth, permitted=["attach"])
            result = self.run_runner(auth, "--collect", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-AUTH")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("STAGE_NOT_AUTHORIZED", result.stderr)
            auth_file(auth)
            result = self.run_runner(auth, "--max-apps-script-reads", "4", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-LIMIT")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AUTHORIZATION_CEILING_CONFLICT", result.stderr)
            result = self.run_runner(auth, "--expected-manifest-sha", "sha256:bad", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-HASH")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("MANIFEST_HASH_CONFLICT", result.stderr)

    def test_full_explicit_offline_fixture_and_stage_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth_file(auth)
            flags = ("--collect", "--attach", "--evaluate", "--offline-fixture")
            result = self.run_runner(auth, *flags, run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-FULL")
            self.assertEqual(result.returncode, 0, result.stderr)
            decision = json.loads((BASE / ".outcome_slice_runner" / "runs" / "PPHB-R1-OUTCOME-SLICE-RUN-TEST-FULL" / "stage_decisions.json").read_text())
            self.assertEqual(decision["collect"], "OUTCOME_SLICE_COLLECTION_COMPLETE")
            self.assertEqual(decision["attach"], "OUTCOME_SLICE_ATTACHMENT_COMPLETE")
            self.assertEqual(decision["evaluate"], "OUTCOME_SLICE_EVALUATION_COMPLETE")
            reservations = (BASE / ".outcome_slice_runner" / "runs" / "PPHB-R1-OUTCOME-SLICE-RUN-TEST-FULL" / "stage_episode_reservations.jsonl").read_text().splitlines()
            self.assertEqual(len(reservations), 36)
            self.assertEqual(json.loads((BASE / ".outcome_slice_runner" / "runs" / "PPHB-R1-OUTCOME-SLICE-RUN-TEST-FULL" / "dispatch_state.json").read_text()), {"collect": "FIXTURE_VALIDATED", "attach": "FIXTURE_VALIDATED", "evaluate": "FIXTURE_VALIDATED"})
            result = self.run_runner(auth, "--attach", "--offline-fixture", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-ATTACH")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_stage_prevention_and_lease_contention(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth_file(auth)
            result = self.run_runner(auth, "--collect", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-DUPCOLLECT")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COLLECTION_ALREADY_ACCEPTED", result.stderr)
            lease = BASE / ".outcome_slice_runner" / "leases" / "SLICE-001.json"
            lease.parent.mkdir(parents=True, exist_ok=True)
            lease.write_text(json.dumps({"slice_id": "SLICE-001", "pid": os.getpid(), "status": "ACTIVE"}))
            result = self.run_runner(auth, run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-CONTENTION")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SLICE_LEASE_CONTENTION", result.stderr)
            lease.unlink()

    def test_no_next_slice_created_and_no_external_access(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth_file(auth)
            result = self.run_runner(auth, "--offline-fixture", "--collect", run_id="PPHB-R1-OUTCOME-SLICE-RUN-TEST-NEXT")
            self.assertEqual(result.returncode, 0, result.stderr)
            run_manifest = json.loads((BASE / ".outcome_slice_runner" / "runs" / "PPHB-R1-OUTCOME-SLICE-RUN-TEST-NEXT" / "runner_manifest.json").read_text())
            self.assertEqual(run_manifest["external_requests"], 0)
            self.assertEqual(run_manifest["google_writes"], 0)
            self.assertFalse(any("SLICE-002" in path.name for path in (BASE / ".outcome_slice_runner" / "runs").glob("*")))


if __name__ == "__main__":
    unittest.main()
