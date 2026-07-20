from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import validate_presignal_v21_return_only_wrappers_v1 as wrappers


class ReturnOnlyLineageWrapperValidationTests(unittest.TestCase):
    def test_archived_builders_are_write_capable_and_no_active_capability_exists(self) -> None:
        result = wrappers.validate()
        self.assertEqual(result["decision"], "V2_1_POST_STEP9_R2_WRITE_ISOLATION_VALIDATION_FAILED")
        self.assertTrue(all(row["reachable_write_capable_tokens"] for row in result["call_graph"]))
        self.assertFalse(result["deployed_interface"]["safe_lineage_entrypoints_available"])
        self.assertEqual(result["external_calls"]["provider"], 0)

    def test_validation_is_call_free_and_preserves_p12_evidence_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p12 = root / "P12-COLLECT-ffd55626bc1a886c2e19"
            p12.mkdir()
            (p12 / "live_lineage_capability.json").write_text('{"status":"BLOCKED_WRITE_ISOLATION"}\n')
            out, result = wrappers.run(output_dir=root / "repair", p12_dir=p12)
            self.assertEqual(result["external_calls"]["google_sheets_writes"], 0)
            self.assertTrue((out / "static_write_isolation_validation.json").exists())
            self.assertTrue((p12 / "live_lineage_capability_r1.json").exists())
            self.assertIn("BLOCKED_WRITE_ISOLATION", (p12 / "live_lineage_capability_r1.json").read_text())


if __name__ == "__main__":
    unittest.main()
