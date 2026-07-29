from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_attention_batch_003_row_status as audit


class AuditAttentionBatch003RowStatusTest(unittest.TestCase):
    def test_exactly_two_failed_batch_003_responses_are_audited(self) -> None:
        state = audit.load_governing_state()
        self.assertEqual(sorted(row["call_id"] for row in state["failed_rows"]), sorted(audit.FAILED_CALL_IDS))
        self.assertEqual(len(state["valid_rows"]), 10)

    def test_no_provider_calls_and_ten_existing_valid_results_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051500Z",
                create_closure=False,
            )
            manifest = audit.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(len(result["recovered_rows"]), 0)
            self.assertEqual(len(result["remaining_rows"]), 2)

    def test_original_row_statuses_and_missing_rows_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051501Z",
                create_closure=False,
            )
            inventory = audit.read_jsonl(result["audit_dir"] / "failed_row_status_inventory.jsonl")
            self.assertEqual(inventory[0]["exact_invalid_status_values"], ["provider_omitted_event"])
            self.assertEqual(inventory[1]["exact_invalid_status_values"], ["provider_omitted_event"])
            self.assertEqual(inventory[0]["invalid_row_count"], 5)
            self.assertEqual(inventory[1]["invalid_row_count"], 1)

    def test_only_exact_proven_status_mappings_are_accepted(self) -> None:
        self.assertEqual(audit.classify_status_value("provider_omitted_event"), "SCIENTIFICALLY_DIFFERENT_STATUS")
        self.assertEqual(audit.classify_status_value("provider_contract_error"), "SCIENTIFICALLY_DIFFERENT_STATUS")
        self.assertEqual(audit.classify_status_value(""), "MISSING_STATUS")
        self.assertEqual(audit.classify_status_value("provider-omitted-event"), "AMBIGUOUS_STATUS")

    def test_status_normalization_scope_is_historical_attention_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051502Z",
                create_closure=False,
            )
            contract = audit.read_json(result["audit_dir"] / "status_normalization_contract.json")
            self.assertEqual(contract["allowed_object"], "session_attention_map")
            self.assertIn("historical session_attention_map", contract["allowed_route"])

    def test_provider_authority_binding_remains_unchanged(self) -> None:
        state = audit.load_governing_state()
        for call_id in audit.FAILED_CALL_IDS:
            authority = state["authority_rows"][call_id]
            self.assertTrue(authority["authority_agreement"])
            self.assertEqual(authority["authority_decision"], "MANIFEST_TRANSPORT_MATCH")

    def test_no_scientific_field_changes_and_strict_validation_still_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051503Z",
                create_closure=False,
            )
            local_validation = audit.read_jsonl(result["audit_dir"] / "local_validation_results.jsonl")
            self.assertTrue(all(row["scientific_fields_changed"] is False for row in local_validation))
            self.assertTrue(all(row["validation_result"] == "FAILED_VALIDATION" for row in local_validation))

    def test_only_validated_results_enter_recovered_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051504Z",
                create_closure=False,
            )
            recovered = audit.read_jsonl(result["audit_dir"] / "recovered_attention_results.jsonl")
            remaining = audit.read_jsonl(result["audit_dir"] / "remaining_failed_calls.jsonl")
            self.assertEqual(recovered, [])
            self.assertEqual(len(remaining), 2)
            self.assertIsNone(result["closure_dir"])

    def test_no_pack_no_forecast_no_batch_004_and_prior_evidence_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(
                audit_output_root=Path(tmp),
                exec_output_root=Path(tmp) / "exec",
                fixed_timestamp="20260729T051505Z",
                create_closure=False,
            )
            manifest = audit.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(manifest["google_writes"], 0)
            self.assertEqual(result["scaling_decision"], "RETRY_FAILED_BATCH_003_CALLS_REQUIRES_AUTHORIZATION")


if __name__ == "__main__":
    unittest.main()
