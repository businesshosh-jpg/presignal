from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import recover_presignal_v21_attention_batch_002_preserved_identities as recovery


class RecoverAttentionBatch002PreservedIdentitiesTest(unittest.TestCase):
    def test_exactly_six_failed_responses_are_audited(self) -> None:
        state = recovery.load_governing_state()
        self.assertEqual(len(state["failed_rows"]), 6)
        self.assertEqual(len(state["valid_rows"]), 6)

    def test_no_provider_calls_and_raw_responses_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = recovery.run_recovery(audit_output_root=Path(tmp), fixed_timestamp="20260729T050500Z")
            manifest = recovery.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            inventory = recovery.read_jsonl(result["audit_dir"] / "failed_response_inventory.jsonl")
            self.assertEqual(len(inventory), 6)

    def test_anthropic_alias_requires_manifest_and_transport_confirmation(self) -> None:
        state = recovery.load_governing_state()
        failed = next(row for row in state["failed_rows"] if row["call_id"] == "ATN_13cab543ced6509afc8d")
        raw = dict(state["raw_rows"][failed["call_id"]])
        transport = dict(state["transport_rows"][failed["call_id"]])
        transport["raw_output"] = raw["raw_output"]
        normalized = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(normalized["canonical_payload"]["provider"], "Anthropic")

        transport["actual_provider"] = "OpenAI"
        normalized_bad = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
        )
        self.assertEqual(normalized_bad["parse_status"], adapters.ParseStatus.PARSE_FAILED)

    def test_aliases_remain_provider_scoped(self) -> None:
        state = recovery.load_governing_state()
        checks = [
            ("Gemini", "gemini-2.5-flash-lite", "presignal_v2_shadow_research"),
            ("OpenAI", "gpt-4o-mini-2024-07-18", "presignal_v2_shadow_research"),
            ("Anthropic", "claude-haiku-4-5", "macro_model"),
            ("OpenAI", "gpt-4o-mini-2024-07-18", "MacroResearchModel"),
            ("Gemini", "gemini-2.5-flash-lite", "macro_research"),
        ]
        for provider, model, alias in checks:
            normalized = adapters.normalize_provider_response(
                stage="ATTENTION",
                requested_provider=provider,
                requested_model=model,
                transport_result={
                    "raw_output": (
                        '{"object":"session_attention_map","session_id":"S","provider":"%s",'
                        '"attention_items":[],"session_attention_summary":"x","status":"ok"}'
                    ) % alias,
                    "actual_provider": provider,
                    "actual_model": model,
                },
                contract_version=state["runtime_contract"]["contract_version"],
            )
            self.assertEqual(normalized["parse_status"], adapters.ParseStatus.PARSED)
            self.assertEqual(normalized["canonical_payload"]["provider"], alias)

    def test_unknown_and_missing_aliases_remain_rejected_for_recovery(self) -> None:
        state = recovery.load_governing_state()
        occurrence = recovery.provider_label_occurrences(["UnknownAlias", ""])
        self.assertEqual(occurrence["UnknownAlias"], {})
        inventory = recovery.inventory_failed_responses(state)
        audits, accepted = recovery.classify_identity_rows(inventory, recovery.provider_label_occurrences(sorted({row["returned_provider_identity"] for row in inventory})))
        self.assertTrue(accepted)
        self.assertTrue(any(row["classification"] == "IDENTITY_AMBIGUOUS" for row in audits))

    def test_canonical_contract_unchanged_and_no_scientific_fields_altered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = recovery.run_recovery(audit_output_root=Path(tmp), fixed_timestamp="20260729T050501Z")
            contract = recovery.read_json(result["audit_dir"] / "alias_normalization_contract.json")
            self.assertEqual(contract["canonical_attention_contract_identity"], "session_attention_map")
            accepted = contract["accepted_aliases"]
            self.assertTrue(all(not row["scientific_fields_changed"] for row in accepted))

    def test_only_strictly_validated_results_enter_recovered_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = recovery.run_recovery(audit_output_root=Path(tmp), fixed_timestamp="20260729T050502Z")
            recovered = recovery.read_jsonl(result["audit_dir"] / "recovered_attention_results.jsonl")
            remaining = recovery.read_jsonl(result["audit_dir"] / "remaining_failed_calls.jsonl")
            self.assertEqual(len(recovered), 2)
            self.assertEqual(len(remaining), 4)
            self.assertIsNone(result["closure_dir"])

    def test_no_pack_no_forecast_no_batch_003_and_prior_evidence_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = recovery.run_recovery(audit_output_root=Path(tmp), fixed_timestamp="20260729T050503Z")
            manifest = recovery.read_json(result["audit_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(manifest["google_writes"], 0)
            self.assertEqual(result["scaling_decision"], "RETRY_FAILED_BATCH_002_CALLS_REQUIRES_AUTHORIZATION")


if __name__ == "__main__":
    unittest.main()
