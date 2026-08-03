import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
COLLECTION = BASE / "PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8"


class OutcomeSliceAttachmentTest(unittest.TestCase):
    def test_candidate_scope_and_immutable_hashes(self):
        rows = [json.loads(line) for line in (COLLECTION / "candidate_outcomes_final.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({row["episode_id"] for row in rows}), 12)
        self.assertEqual(len({row["outcome_fingerprint"] for row in rows}), 12)
        self.assertTrue(all(row["candidate_outcome"]["schema_version"] == "2.1.1" for row in rows))

    def test_attachment_is_append_only_and_external_free(self):
        out_dir = BASE / "PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320"
        manifest = json.loads((out_dir / "run_manifest.json").read_text())
        self.assertEqual(manifest["external_requests"], 0)
        self.assertEqual(manifest["google_writes"], 0)
        self.assertEqual(manifest["evaluation_calculations"], 0)
        self.assertEqual(json.loads((out_dir / "attachment_decision.json").read_text())["attached_count"], 12)
        duplicate = subprocess.run([
            sys.executable, str(ROOT / "automation" / "attach_presignal_v21_outcome_slice_001.py"),
            "--run-id", "PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-DUPLICATE-TEST",
        ], capture_output=True, text=True)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("PRIOR_OUTCOME_ATTACHMENT_REQUIRES_RECONCILIATION", duplicate.stderr)


if __name__ == "__main__":
    unittest.main()
