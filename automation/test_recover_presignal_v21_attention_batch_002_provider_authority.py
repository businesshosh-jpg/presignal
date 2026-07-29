from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import recover_presignal_v21_attention_batch_002_provider_authority as recovery


class RecoverAttentionBatch002ProviderAuthorityTest(unittest.TestCase):
    def test_exactly_four_unresolved_responses_are_reprocessed(self) -> None:
        state = recovery.load_governing_state()
        self.assertEqual(sorted(row["call_id"] for row in state["failed_rows"]), sorted(recovery.UNRESOLVED_CALL_IDS))
        self.assertEqual(len(state["original_valid_rows"]), 6)
        self.assertEqual(len(state["prior_recovered_rows"]), 2)

    def test_manifest_transport_agreement_is_required(self) -> None:
        state = recovery.load_governing_state()
        call_id = recovery.UNRESOLVED_CALL_IDS[0]
        call = state["calls"][call_id]
        raw = state["raw_rows"][call_id]["raw_output"]
        result = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider=call["provider"],
            requested_model=call["model"],
            transport_result={
                "raw_output": raw,
                "actual_provider": "Anthropic",
                "actual_model": "claude-haiku-4-5",
            },
            contract_version=state["runtime_contract"]["contract_version"],
            authoritative_attention_provider_binding=True,
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSE_FAILED)
        self.assertEqual(result["normalization_notes"][-1]["reason"], "ATTENTION_PROVIDER_AUTHORITY_CONFLICT")

    def test_no_provider_calls_and_full_recovery_close_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_audit, tempfile.TemporaryDirectory() as tmp_exec:
            result = recovery.run_recovery(
                audit_output_root=Path(tmp_audit),
                exec_output_root=Path(tmp_exec),
                fixed_timestamp="20260729T050900Z",
            )
            manifest = recovery.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(len(result["recovered_rows"]), 4)
            self.assertEqual(len(result["remaining_rows"]), 0)
            self.assertIsNotNone(result["closure_dir"])
            final_rows = recovery.read_jsonl(result["closure_dir"] / "final_normalized_attention_results.jsonl")
            self.assertEqual(len(final_rows), 12)
            remaining = recovery.read_jsonl(result["closure_dir"] / "remaining_failed_calls.jsonl")
            self.assertEqual(remaining, [])

    def test_raw_claimed_provider_is_preserved_and_scientific_fields_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_audit:
            result = recovery.run_recovery(
                audit_output_root=Path(tmp_audit),
                exec_output_root=Path(tmp_audit) / "exec",
                fixed_timestamp="20260729T050901Z",
                create_closure=False,
            )
            contract = recovery.read_json(result["audit_dir"] / "provider_identity_authority_contract.json")
            self.assertTrue(contract["raw_claimed_provider_preservation"])
            ledger = recovery.read_jsonl(result["audit_dir"] / "normalization_application_ledger.jsonl")
            self.assertEqual(len(ledger), 4)
            self.assertTrue(all(row["scientific_fields_changed"] is False for row in ledger))

    def test_forecast_and_outcome_contracts_are_not_touched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_audit:
            result = recovery.run_recovery(
                audit_output_root=Path(tmp_audit),
                exec_output_root=Path(tmp_audit) / "exec",
                fixed_timestamp="20260729T050902Z",
                create_closure=False,
            )
            contract = recovery.read_json(result["audit_dir"] / "provider_identity_authority_contract.json")
            limits = contract["applicability_limits"]
            self.assertIn("does not apply to forecast outputs", limits)
            self.assertIn("does not apply to outcome outputs", limits)


if __name__ == "__main__":
    unittest.main()
