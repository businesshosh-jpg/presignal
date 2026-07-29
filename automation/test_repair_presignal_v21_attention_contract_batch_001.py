from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_provider_adapters_v1 as provider_adapters
from automation import repair_presignal_v21_attention_contract_batch_001 as repair


class AttentionContractRepairBatch001Test(unittest.TestCase):
    def test_exact_valid_identity_passes_unchanged(self) -> None:
        raw = json.dumps(
            {
                "object": "session_attention_map",
                "session_id": "S",
                "provider": "OpenAI",
                "status": "ok",
                "attention_items": [],
            }
        )
        parsed = binding.attention_parser("OpenAI", raw, binding.load_manifest()["contract"])
        self.assertEqual(parsed["provider"], "OpenAI")
        self.assertNotIn("_provider_identity_normalization", parsed)

    def test_only_proven_equivalent_aliases_are_normalized(self) -> None:
        raw = json.dumps(
            {
                "object": "session_attention_map",
                "session_id": "S",
                "provider": "market_research_model",
                "status": "ok",
                "attention_items": [],
            }
        )
        parsed = binding.attention_parser("OpenAI", raw, binding.load_manifest()["contract"])
        self.assertEqual(parsed["provider"], "OpenAI")
        self.assertEqual(
            parsed["_provider_identity_normalization"]["normalization_type"],
            "attention_provider_identity_alias",
        )

    def test_arbitrary_identity_remains_rejected(self) -> None:
        raw = json.dumps(
            {
                "object": "session_attention_map",
                "session_id": "S",
                "provider": "unexpected_alias",
                "status": "ok",
                "attention_items": [],
            }
        )
        parsed = binding.attention_parser("OpenAI", raw, binding.load_manifest()["contract"])
        self.assertEqual(parsed["provider"], "unexpected_alias")

    def test_missing_identity_remains_rejected(self) -> None:
        payload = {"object": "session_attention_map", "session_id": "S", "status": "ok", "attention_items": []}
        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Gemini",
            requested_model="gemini-2.5-flash-lite",
            transport_result={"raw_output": json.dumps(payload)},
            contract_version=binding.load_manifest()["contract"]["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], provider_adapters.ParseStatus.PARSED)
        self.assertIsNone(normalized["canonical_payload"].get("provider"))

    def test_wrapper_identity_does_not_replace_payload_identity(self) -> None:
        payload = {"object": "session_attention_map", "session_id": "S", "provider": "bad_alias", "status": "ok", "attention_items": []}
        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result={
                "raw_output": json.dumps(payload),
                "actual_provider": "Anthropic",
                "actual_model": "claude-haiku-4-5",
            },
            contract_version=binding.load_manifest()["contract"]["contract_version"],
        )
        self.assertEqual(normalized["canonical_payload"]["provider"], "bad_alias")

    def test_allowed_json_cleanup_remains_narrow(self) -> None:
        fenced = "```json\n" + json.dumps({"object": "session_attention_map", "session_id": "S", "provider": "Gemini", "status": "ok", "attention_items": []}) + "\n```"
        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Gemini",
            requested_model="gemini-2.5-flash-lite",
            transport_result={"raw_output": fenced},
            contract_version=binding.load_manifest()["contract"]["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], provider_adapters.ParseStatus.PARSED)

        trailing = '{"object":"session_attention_map",}'
        normalized_bad = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Gemini",
            requested_model="gemini-2.5-flash-lite",
            transport_result={"raw_output": trailing},
            contract_version=binding.load_manifest()["contract"]["contract_version"],
        )
        self.assertEqual(normalized_bad["parse_status"], provider_adapters.ParseStatus.PARSE_FAILED)

    def test_repair_run_inventories_all_12_and_recovers_11(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.run_repair(output_root=Path(tmp), fixed_timestamp="20260729T020000Z")
            run_dir = result["run_dir"]
            inventory = repair.read_jsonl(run_dir / "live_response_inventory.jsonl")
            recovered = repair.read_jsonl(run_dir / "recovered_attention_results.jsonl")
            remaining = repair.read_jsonl(run_dir / "remaining_failed_calls.jsonl")
            reparsed = repair.read_jsonl(run_dir / "reprocessed_parse_results.jsonl")
            self.assertEqual(len(inventory), 12)
            self.assertEqual(len(recovered), 11)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(sum(row["result"] == repair.PARSED_VALID for row in reparsed), 11)
            self.assertEqual(sum(row["result"] == repair.FAILED_PARSE for row in reparsed), 1)

    def test_recovered_results_pass_strict_validation_and_failed_stays_retry_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.run_repair(output_root=Path(tmp), fixed_timestamp="20260729T020001Z")
            run_dir = result["run_dir"]
            recovered = repair.read_jsonl(run_dir / "recovered_attention_results.jsonl")
            remaining = repair.read_jsonl(run_dir / "remaining_failed_calls.jsonl")
            self.assertTrue(all(row["attention_result"]["provider"] in {"Anthropic", "Gemini", "OpenAI"} for row in recovered))
            self.assertEqual(remaining[0]["call_id"], "ATN_d7c95516e95938578834")
            self.assertTrue(remaining[0]["retry_required"])

    def test_reruns_produce_deterministic_scientific_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = repair.run_repair(output_root=Path(tmp), fixed_timestamp="20260729T020002Z")
            second = repair.run_repair(output_root=Path(tmp), fixed_timestamp="20260729T020003Z")
            self.assertEqual(first["summary"], second["summary"])
            self.assertEqual(first["decisions"], second["decisions"])


if __name__ == "__main__":
    unittest.main()
