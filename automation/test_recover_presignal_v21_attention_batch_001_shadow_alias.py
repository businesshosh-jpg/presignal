from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import recover_presignal_v21_attention_batch_001_shadow_alias as recovery


class RecoverAnthropicShadowAliasTest(unittest.TestCase):
    def test_no_provider_call_occurs_and_only_preserved_response_is_reprocessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = recovery.run_recovery(
                audit_output_root=root / "audit",
                exec_output_root=root / "exec",
                fixed_timestamp="20260729T050000Z",
            )
            manifest = recovery.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["google_writes"], 0)

    def test_11_validated_calls_remain_unchanged(self) -> None:
        state = recovery.load_governing_state()
        self.assertEqual(len(state["imported"]), 11)
        self.assertNotIn(recovery.CALL_ID, {row["call_id"] for row in state["imported"]})

    def test_exact_alias_is_accepted_only_for_manifest_bound_anthropic_attention(self) -> None:
        state = recovery.load_governing_state()
        transport = dict(state["retry_transport"])
        transport["raw_output"] = state["retry_raw"]["raw_output"]
        normalized = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(normalized["canonical_payload"]["provider"], "Anthropic")

    def test_alias_is_rejected_for_gemini_and_openai(self) -> None:
        state = recovery.load_governing_state()
        transport = dict(state["retry_transport"])
        transport["raw_output"] = state["retry_raw"]["raw_output"]
        for provider, model in (("Gemini", "gemini-2.5-flash-lite"), ("OpenAI", "gpt-4o-mini-2024-07-18")):
            normalized = adapters.normalize_provider_response(
                stage="ATTENTION",
                requested_provider=provider,
                requested_model=model,
                transport_result=transport,
                contract_version=state["runtime_contract"]["contract_version"],
            )
            self.assertEqual(normalized["canonical_payload"]["provider"], recovery.ALIAS)

    def test_alias_is_rejected_when_transport_metadata_does_not_confirm_anthropic(self) -> None:
        state = recovery.load_governing_state()
        transport = dict(state["retry_transport"])
        transport["raw_output"] = state["retry_raw"]["raw_output"]
        transport["actual_provider"] = "Gemini"
        normalized = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], adapters.ParseStatus.PARSE_FAILED)

    def test_unknown_shadow_alias_remains_rejected(self) -> None:
        raw = '{"object":"session_attention_map","session_id":"S","provider":"PreSignal_v2.0_shadow_unknown","attention_items":[],"session_attention_summary":"x","status":"ok"}'
        normalized = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result={"raw_output": raw, "actual_provider": "Anthropic", "actual_model": "claude-haiku-4-5"},
            contract_version=recovery.batch.load_runtime_contract()["contract_version"],
        )
        self.assertEqual(normalized["canonical_payload"]["provider"], "PreSignal_v2.0_shadow_unknown")

    def test_canonical_contract_remains_unchanged_and_no_scientific_fields_change(self) -> None:
        root = Path(tempfile.mkdtemp())
        result = recovery.run_recovery(
            audit_output_root=root / "audit",
            exec_output_root=root / "exec",
            fixed_timestamp="20260729T050001Z",
        )
        contract = recovery.read_json(result["audit_dir"] / "alias_normalization_contract.json")
        self.assertEqual(contract["allowed_object"], "session_attention_map")
        self.assertFalse(contract["scientific_fields_changed"])

    def test_strict_validation_still_runs_and_successful_recovery_closes_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = recovery.run_recovery(
                audit_output_root=root / "audit",
                exec_output_root=root / "exec",
                fixed_timestamp="20260729T050002Z",
            )
            self.assertEqual(result["reparsed"]["result"], "PARSED_VALID")
            self.assertTrue(result["reparsed"]["validation_ok"])
            self.assertIsNotNone(result["closure_dir"])
            final_rows = recovery.read_jsonl(result["closure_dir"] / "final_normalized_attention_results.jsonl")
            remaining = recovery.read_jsonl(result["closure_dir"] / "remaining_failed_calls.jsonl")
            self.assertEqual(len(final_rows), 12)
            self.assertEqual(len(remaining), 0)

    def test_no_pack_construction_forecast_execution_or_batch_002(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = recovery.run_recovery(
                audit_output_root=root / "audit",
                exec_output_root=root / "exec",
                fixed_timestamp="20260729T050003Z",
            )
            closure = recovery.read_json(result["closure_dir"] / "run_manifest.json")
            self.assertEqual(closure["pack_construction_executed"], 0)
            self.assertEqual(closure["forecast_calls_executed"], 0)
            self.assertEqual(closure["provider_calls_executed"], 0)


if __name__ == "__main__":
    unittest.main()
