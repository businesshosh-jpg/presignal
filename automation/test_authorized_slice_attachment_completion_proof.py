import json
import tempfile
import unittest
from pathlib import Path

import automation.run_presignal_v21_authorized_slice as controller


EXPECTED = "sha256:16e231a854572c72e1869ff04d3c6dcb038021af7bfe9bb059a05b2104c5270c"
AUTH = {
    "authorization_mode": "END_TO_END",
    "authorization_id": "AUTH-002",
    "authorization_fingerprint": "sha256:auth",
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class AttachmentCompletionProofTest(unittest.TestCase):
    def artifact(self, base, name, prefix="PPHB-R1-OUTCOME-ATTACH"):
        path = base / f"{prefix}-SLICE-002-{name}"
        write_json(path / "run_manifest.json", {
            "run_id": path.name, "manifest_sha256": EXPECTED,
            "candidate_count": 12, "attachment_count": 12, "google_writes": 0,
        })
        write_json(path / "attachment_reconciliation.json", {
            "attached_outcome_count": 12, "unattached_candidate_count": 0,
            "duplicate_or_conflicting_attachments": 0, "unresolved_identities": [],
        })
        write_json(path / "attachment_decision.json", {
            "decision": "OUTCOME_SLICE_002_ATTACHED_AND_RECONCILED",
        })
        return path

    def test_canonical_attachment_identity_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = self.artifact(base, "20260803T044538Z-x")
            proof_dir = base / "PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-x"
            write_json(proof_dir / "attachment_execution_stop.json", {
                "authorization_id": "AUTH-002", "authorization_fingerprint": "sha256:auth",
                "attachment_run_id": path.name,
                "attachment_result": {"attached_records": 12, "duplicates": 0, "unattached_records": 0},
            })
            old = controller.BASE
            controller.BASE = base
            try:
                self.assertEqual(controller.accepted_stage_artifact("attach", "SLICE-002", EXPECTED, AUTH), path)
            finally:
                controller.BASE = old

    def test_legacy_attachment_identity_remains_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = self.artifact(base, "20260803T000000Z-legacy", "PPHB-R1-OUTCOME-ATTACHMENT")
            old = controller.BASE
            controller.BASE = base
            try:
                self.assertEqual(controller.accepted_stage_artifact("attach", "SLICE-002", EXPECTED), path)
            finally:
                controller.BASE = old

    def test_multiple_eligible_attachment_runs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first = self.artifact(base, "20260803T044538Z-a")
            second = self.artifact(base, "20260803T044539Z-b")
            for path in (first, second):
                proof_dir = base / ("PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-" + path.name[-1])
                write_json(proof_dir / "attachment_execution_stop.json", {
                    "authorization_id": "AUTH-002", "authorization_fingerprint": "sha256:auth",
                    "attachment_run_id": path.name,
                    "attachment_result": {"attached_records": 12, "duplicates": 0, "unattached_records": 0},
                })
            old = controller.BASE
            controller.BASE = base
            try:
                with self.assertRaises(SystemExit):
                    controller.accepted_stage_artifact("attach", "SLICE-002", EXPECTED, AUTH)
            finally:
                controller.BASE = old


if __name__ == "__main__":
    unittest.main()
