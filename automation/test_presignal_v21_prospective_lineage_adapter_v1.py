from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_prospective_lineage_adapter_v1 as adapter


class ProspectiveLineageAdapterTests(unittest.TestCase):
    def test_exact_v2_sources_are_identified_but_rejected_without_write_isolation(self) -> None:
        inventory = adapter.source_inventory()
        self.assertEqual({row["stage"] for row in inventory}, {"ATTENTION", "REQUESTS", "PACK"})
        self.assertTrue(all(row["entrypoint_present"] for row in inventory))
        self.assertTrue(all(not row["accepted"] for row in inventory))
        self.assertTrue(all(row["rejection_reason"] == "NO_SAFE_DEPLOYED_RETURN_ONLY_NO_WRITE_BINDING" for row in inventory))
        self.assertEqual(adapter.deployed_interface_manifest()["safe_lineage_entrypoints_available"], False)

    def test_attention_requests_and_pack_preserve_exact_lineage_or_fail_closed(self) -> None:
        self.assertTrue(adapter.fixture_validation()["passed"])
        with self.assertRaisesRegex(ValueError, "ATTENTION_LABEL_INVALID"):
            adapter.validate_attention_rows([{"attention_run_id": "A", "session_id": "S", "provider": "OpenAI", "model": "m", "event_id": "E", "attention_label": "UNKNOWN", "generated_ts": "2026-01-01T00:00:00Z", "information_cutoff_ts": "2026-01-01T00:00:00Z", "raw_output": "{}", "status": "parsed"}], session_id="S", provider="OpenAI", model="m", information_cutoff_ts="2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "REQUEST_ATTENTION_LINEAGE_MISSING"):
            adapter.validate_request_rows([{"request_run_id": "R", "attention_run_id": "other", "session_id": "S", "provider": "OpenAI", "model": "m", "request_identity": "I", "information_cutoff_ts": "2026-01-01T00:00:00Z", "raw_output": "{}", "status": "parsed"}], session_id="S", provider="OpenAI", model="m", attention_run_id="A", information_cutoff_ts="2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "PACK_FREEZE_LINEAGE_MISSING"):
            adapter.validate_pack({"session_id": "S", "information_cutoff_ts": "2026-01-01T00:00:00Z", "pack_freeze_id": "P", "source_request_run_ids": ["R"], "items": []}, session_id="S", information_cutoff_ts="2026-01-01T00:00:00Z", pack_freeze_id="P")

    def test_stage_wrappers_refuse_unsafe_execution_before_external_calls(self) -> None:
        for stage in (adapter.build_prospective_attention_map, adapter.build_prospective_information_requests, adapter.build_prospective_shared_market_state_pack):
            with self.assertRaisesRegex(adapter.ProspectiveLineageWriteIsolationRequired, "WRITE_ISOLATION_REQUIRED"):
                stage(study_id="PSS")

    def test_evidence_preserves_original_p12_blocker_before_appending_transition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p12 = root / "P12-COLLECT-ffd55626bc1a886c2e19"
            p12.mkdir()
            (p12 / "live_lineage_capability.json").write_text('{"blocker":"original"}\n')
            result = adapter.write_repair_evidence(output_dir=root / "repair", p12_dir=p12)
            self.assertEqual(result["decision"], "V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED")
            self.assertTrue((p12 / "live_lineage_capability_initial.json").exists())
            self.assertIn("original", (p12 / "live_lineage_capability_initial.json").read_text())
            self.assertIn("BLOCKED_WRITE_ISOLATION", (p12 / "resume_transition.json").read_text())


if __name__ == "__main__":
    unittest.main()
