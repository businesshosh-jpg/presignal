from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation import run_presignal_v21_r6_prospective_runtime_sync_v1 as subject


def fake_selected() -> dict:
    return {
        "content_checksum": "sha256:episode-content",
        "provenance_checksum": "sha256:episode-provenance",
        "lineage_checksum": "sha256:episode-lineage",
    }


class ProspectiveRuntimeSyncTests(unittest.TestCase):
    def test_visibility_request_is_metadata_only(self) -> None:
        request = subject.visibility_request("2026-07-24T07:45:00Z")
        self.assertTrue(request["validation_only"])
        self.assertEqual(request["adapter_identity"], subject.ADAPTER)
        self.assertEqual(request["source_id"], "KSRC_FRED")

    def test_visibility_ok_requires_zero_fetch_zero_writer_metadata(self) -> None:
        self.assertTrue(subject.visibility_ok({
            "object": "PROSPECTIVE_PACK_E_CAPABILITY_METADATA",
            "validation_only": True,
            "external_source_dispatch_count": 0,
            "writer_count": 0,
            "function_identity": subject.FUNCTION,
        }))
        self.assertFalse(subject.visibility_ok({
            "object": "PROSPECTIVE_PACK_E_CAPABILITY_METADATA",
            "validation_only": True,
            "external_source_dispatch_count": 1,
            "writer_count": 0,
            "function_identity": subject.FUNCTION,
        }))

    def test_deployment_authorization_is_deterministic_and_single_use(self) -> None:
        local_manifest = {
            "dependency_files": [{"path": "apps_script/prospective_pack_e_acquisition.js", "sha256": "sha256:file"}],
            "dependency_set_checksum": "sha256:deps",
        }
        runtime_trace = {
            "project_identity_classification": "CLASP_PROJECT_ID_EXECUTION_API_HEAD",
            "deployment_identity_classification": "HEAD_SYMBOLIC_DEPLOYMENT_PRESENT",
        }
        first = subject.deployment_authorization(target_commit="abc", local_manifest=local_manifest, runtime_trace=runtime_trace)
        second = subject.deployment_authorization(target_commit="abc", local_manifest=local_manifest, runtime_trace=runtime_trace)
        self.assertEqual(first, second)
        self.assertFalse(first["authorization_activated"])
        self.assertEqual(first["deployment_count"], 1)
        self.assertEqual(first["retry_budget"], 0)

    def test_fred_v2_authorization_is_inactive_and_binds_v1_failure(self) -> None:
        with patch.object(subject, "read_json", side_effect=lambda path: fake_selected()):
            auth = subject.fred_probe_v2_authorization(
                deployment_fingerprint="sha256:deps",
                deployment_identity="PUSHED_PROJECT_HEAD",
                target_commit="abc",
                previous_failure_checksum="sha256:prior",
            )
        self.assertEqual(auth["consumed_v1_authorization_fingerprint"], subject.FRED_V1_AUTH)
        self.assertFalse(auth["authorization_activated"])
        self.assertEqual(auth["call_budget"], 1)
        self.assertEqual(auth["retry_budget"], 0)
        self.assertEqual(auth["fred_calls"], 0)

    def test_cutoff_closed_blocks_live_operations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            with patch.object(subject, "local_dependency_manifest", return_value={"entry_point_present": True, "dependency_files": [], "dependency_set_checksum": "sha256:deps"}), \
                 patch.object(subject, "git_head", return_value="commit"), \
                 patch.object(subject, "read_json", return_value={"status": "old"}):
                decision = subject.run(out, now_utc="2026-07-29T18:00:00Z", execute_deploy=False, execute_visibility=False)
            self.assertEqual(decision, "NEW_R6_PACK_E_RUNTIME_SYNC_BLOCKED_CUTOFF_CLOSED")
            final = json.loads((out / "final_prospective_runtime_sync_decision.json").read_text())
            self.assertFalse(final["cutoff_open"])

    def test_successful_run_syncs_head_and_prepares_v2_without_source_calls(self) -> None:
        remote_before = {
            "file_count": 44,
            "project_fingerprint": "sha256:before",
            "has_prospective_file": False,
            "has_entry_point": False,
            "prospective_file_sha256": None,
            "files": [],
        }
        remote_after = {
            "file_count": 45,
            "project_fingerprint": "sha256:after",
            "has_prospective_file": True,
            "has_entry_point": True,
            "prospective_file_sha256": "sha256:file",
            "files": [],
        }
        visibility = {
            "ok": True,
            "classification": {"category": "READY"},
            "result": {
                "object": "PROSPECTIVE_PACK_E_CAPABILITY_METADATA",
                "validation_only": True,
                "external_source_dispatch_count": 0,
                "writer_count": 0,
                "function_identity": subject.FUNCTION,
            },
        }
        deploy = MagicMock(returncode=0, stdout="pushed\n", stderr="")
        read_values = [
            {"status": "prior failure"},
            fake_selected(),
        ]
        def read_side_effect(_path: Path):
            return read_values.pop(0)

        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            with patch.object(subject, "local_dependency_manifest", return_value={
                "entry_point_present": True,
                "dependency_files": [{"path": "apps_script/prospective_pack_e_acquisition.js", "sha256": "sha256:file"}],
                "dependency_set_checksum": "sha256:deps",
            }), \
                 patch.object(subject, "git_head", return_value="commit"), \
                 patch.object(subject, "read_json", side_effect=read_side_effect), \
                 patch.object(subject.google_clients, "load_credentials", return_value="creds"), \
                 patch.object(subject.google_clients, "build_script_service", return_value="service"), \
                 patch.object(subject.google_clients, "default_script_id", return_value="project"), \
                 patch.object(subject, "remote_head_content", side_effect=[remote_before, remote_after]), \
                 patch.object(subject.google_clients, "run_script_function_with_metadata", return_value=visibility), \
                 patch.object(subject.subprocess, "run", side_effect=[
                     MagicMock(stdout="head deployment\n", returncode=0, stderr=""),
                     deploy,
                 ]):
                decision = subject.run(out, now_utc="2026-07-24T08:00:00Z")
                self.assertEqual(decision, "NEW_R6_PACK_E_PROSPECTIVE_RUNTIME_SYNCHRONIZED_FRED_PROBE_V2_PREPARED")
                audit = json.loads((out / "external_access_audit.json").read_text())
                self.assertEqual(audit["apps_script_deployments"], 1)
                self.assertEqual(audit["apps_script_visibility_executions"], 1)
                self.assertEqual(audit["fred_calls"], 0)
                probe = json.loads((out / "fred_probe_v2_authorization_preparation.json").read_text())
                self.assertFalse(probe["authorization_activated"])


if __name__ == "__main__":
    unittest.main()
