from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_attention_batch_001_anthropic_failure as audit
from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r1_contract_v1 as compat_r1
from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
from automation import repair_presignal_v21_attention_contract_batch_001 as repair


class AnthropicFailureAuditTest(unittest.TestCase):
    def test_only_unresolved_call_is_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030000Z")
            run_dir = result["run_dir"]
            inventory = audit.read_json(run_dir / "failed_call_inventory.json")
            self.assertEqual(inventory["call_id"], audit.CALL_ID)
            self.assertEqual(inventory["provider"], "Anthropic")
            self.assertEqual(inventory["model"], "claude-haiku-4-5")

    def test_all_11_validated_results_remain_untouched(self) -> None:
        recovered = repair.read_jsonl(audit.REPAIR_ROOT / "recovered_attention_results.jsonl")
        self.assertEqual(len(recovered), 11)
        self.assertEqual(len({row["call_id"] for row in recovered}), 11)
        self.assertNotIn(audit.CALL_ID, {row["call_id"] for row in recovered})

    def test_no_provider_calls_occur_and_prior_runs_remain_inputs_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030001Z")
            run_dir = result["run_dir"]
            manifest = audit.read_json(run_dir / "run_manifest.json")
            self.assertEqual(manifest["provider_calls"], 0)
            self.assertEqual(manifest["google_writes"], 0)
            self.assertEqual(manifest["forecast_calls"], 0)
            self.assertEqual(manifest["pack_construction"], 0)

    def test_both_failed_attempt_records_are_referenced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030002Z")
            run_dir = result["run_dir"]
            comparison = audit.read_json(run_dir / "attempt_comparison.json")
            self.assertEqual(comparison["first_attempt"]["run_identity"], audit.RUN1_ID)
            self.assertEqual(comparison["second_attempt"]["run_identity"], audit.RUN2_ID)

    def test_second_raw_response_remains_unchanged(self) -> None:
        second_raw = audit.read_json(audit.RUN2_ROOT / "retry_raw_provider_output.json")
        self.assertEqual(second_raw["call_id"], audit.CALL_ID)
        self.assertEqual(second_raw["raw_output"], "")

    def test_malformed_content_is_not_completed_by_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030003Z")
            run_dir = result["run_dir"]
            boundary = audit.read_json(run_dir / "retry_response_boundary_audit.json")
            self.assertEqual(boundary["field_being_generated_at_failure"], "UNINSPECTABLE_RAW_OUTPUT_MISSING")
            self.assertEqual(boundary["last_complete_json_object"], "UNINSPECTABLE_RAW_OUTPUT_MISSING")
            self.assertEqual(boundary["scientific_content_before_truncation_structurally_valid"], "UNINSPECTABLE_RAW_OUTPUT_MISSING")

    def test_required_canonical_fields_remain_in_corrected_prompt(self) -> None:
        contract = binding.load_manifest()["contract"]
        instruction = binding.attention_instruction(contract, "Anthropic")
        self.assertIn("object, session_id, provider, attention_items, session_attention_summary, status", instruction)
        self.assertIn("event_id, attention_label, attention_rank, attention_reason, expected_market_channel, driver_role, confidence", instruction)

    def test_selected_request_semantics_and_session_input_are_unchanged(self) -> None:
        calls = {row["call_id"]: row for row in audit.read_jsonl(audit.RUN1_ROOT / "batch_call_manifest.jsonl")}
        sessions, members_by_session = audit.batch.read_source_sessions()
        contract = binding.load_manifest()["contract"]
        corrected = audit.build_corrected_request(calls[audit.CALL_ID], sessions[calls[audit.CALL_ID]["source_session_id"]], members_by_session[calls[audit.CALL_ID]["source_session_id"]], contract)
        payload = audit.json.loads(corrected["prompt"]["user"])
        self.assertEqual(corrected["request"]["session_id"], calls[audit.CALL_ID]["source_session_id"])
        self.assertEqual([row["event_id"] for row in payload["events"]], [row["event_id"] for row in members_by_session[calls[audit.CALL_ID]["source_session_id"]]])

    def test_provider_and_model_remain_unchanged(self) -> None:
        calls = {row["call_id"]: row for row in audit.read_jsonl(audit.RUN1_ROOT / "batch_call_manifest.jsonl")}
        sessions, members_by_session = audit.batch.read_source_sessions()
        contract = binding.load_manifest()["contract"]
        corrected = audit.build_corrected_request(calls[audit.CALL_ID], sessions[calls[audit.CALL_ID]["source_session_id"]], members_by_session[calls[audit.CALL_ID]["source_session_id"]], contract)
        self.assertEqual(corrected["request"]["provider"], "Anthropic")
        self.assertEqual(corrected["request"]["model"], "claude-haiku-4-5")

    def test_output_only_compacting_does_not_weaken_validation(self) -> None:
        contract = binding.load_manifest()["contract"]
        settings = binding.generation_settings(contract, "Anthropic", "ATTENTION")
        self.assertEqual(settings, {"max_output_tokens": compat_r2.ANTHROPIC_ATTENTION_MAX_TOKENS, "preserve_raw_before_parse": True})

    def test_rationale_limit_applies_only_to_non_scientific_prose(self) -> None:
        contract = binding.load_manifest()["contract"]
        instruction = binding.attention_instruction(contract, "Anthropic")
        self.assertIn(compat_r1.ANTHROPIC_ATTENTION_RULE, instruction)
        self.assertIn("attention_reason must contain at most six words", instruction)

    def test_recommended_additional_retry_count_is_at_most_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030004Z")
            run_dir = result["run_dir"]
            recommendation = audit.read_json(run_dir / "retry_authorization_recommendation.json")
            self.assertLessEqual(recommendation["maximum_additional_calls"], 1)

    def test_prior_evidence_is_input_only_for_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030005Z")
            run_dir = result["run_dir"]
            manifest = audit.read_json(run_dir / "governing_artifact_manifest.json")
            self.assertEqual(manifest["first_attempt_root"], audit.path_ref(audit.RUN1_ROOT))
            self.assertEqual(manifest["repair_root"], audit.path_ref(audit.REPAIR_ROOT))
            self.assertEqual(manifest["second_attempt_root"], audit.path_ref(audit.RUN2_ROOT))

    def test_reruns_produce_deterministic_scientific_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030006Z")
            second = audit.run_audit(output_root=Path(tmp), fixed_timestamp="20260729T030007Z")
            self.assertEqual(first["decision"], second["decision"])
            self.assertEqual(first["summary"]["audit_status"], second["summary"]["audit_status"])


if __name__ == "__main__":
    unittest.main()
