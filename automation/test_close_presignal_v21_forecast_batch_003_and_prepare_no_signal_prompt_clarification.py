#!/usr/bin/env python3
from __future__ import annotations

import unittest

from automation import close_presignal_v21_forecast_batch_003_and_prepare_no_signal_prompt_clarification as closure
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


def make_attempts() -> dict:
    return {
        "original_output": {"provider": "Anthropic", "model": "claude-haiku-4-5"},
        "replacement_output": {
            "provider": "Anthropic",
            "model": "claude-haiku-4-5",
            "attempt_category": "GOVERNANCE_AUTHORIZED_PROVIDER_SCHEMA_REPLACEMENT",
        },
        "original_authority": {"authority_passed": True},
        "replacement_authority": {"authority_passed": True},
        "original_parse": {"parse_status": "FAILED_PARSE"},
        "replacement_parse": {"parse_status": "FAILED_PARSE"},
        "original_payload": {
            "no_signal_flag": True,
            "confidence": None,
            "early_reaction_5m_direction": "UNCERTAIN",
            "path": [],
        },
        "replacement_payload": {
            "no_signal_flag": True,
            "confidence": None,
            "early_reaction_5m_direction": "UNCERTAIN",
            "path": [],
        },
    }


class ClosureLogicTests(unittest.TestCase):
    def test_only_target_call_is_in_closure_scope(self) -> None:
        self.assertEqual(
            closure.TARGET_CALL_ID,
            "FCL_27720b8b23236b173b96fdee",
        )

    def test_terminal_schema_failure_record_preserves_repeated_failure(self) -> None:
        record = closure.build_terminal_schema_failure_record(make_attempts())
        self.assertEqual(record["terminal_classification"], closure.TERMINAL_CLASSIFICATION)
        self.assertEqual(record["reason"], closure.TERMINAL_REASON)
        self.assertEqual(record["supporting_facts"]["provider_executions_completed"], 2)
        self.assertFalse(record["supporting_facts"]["contract_valid_result_exists"])
        self.assertFalse(record["supporting_facts"]["additional_unchanged_retry_recommended"])

    def test_attempt_comparison_keeps_attempts_separate(self) -> None:
        comparison = closure.build_attempt_comparison(make_attempts())
        self.assertEqual(comparison["original_attempt"]["parse_status"], "FAILED_PARSE")
        self.assertEqual(comparison["replacement_attempt"]["parse_status"], "FAILED_PARSE")
        self.assertIsNone(comparison["repeated_type_failure"]["original_value"])
        self.assertIsNone(comparison["repeated_type_failure"]["replacement_value"])

    def test_stop_retry_rationale_disallows_further_retry(self) -> None:
        rationale = closure.build_stop_retry_rationale()
        self.assertEqual(
            rationale["decision"],
            "NO_FURTHER_RETRY_FOR_TERMINAL_SCHEMA_FAILURE",
        )
        self.assertEqual(len(rationale["scientific_rationale"]), 5)

    def test_batch_accounting_distinguishes_executed_and_authoritative_valid(self) -> None:
        accounting = closure.build_batch_003_final_accounting()
        self.assertEqual(accounting["frozen_calls"], 12)
        self.assertEqual(accounting["executed_call_identities"], 12)
        self.assertEqual(accounting["authoritative_valid_results"], 11)
        self.assertEqual(accounting["terminal_provider_schema_failures"], 1)

    def test_future_prompt_adds_exactly_one_sentence(self) -> None:
        prior = step6.prompt_instruction_text()
        future = step6.prompt_instruction_text(
            include_future_no_signal_confidence_clarification=True,
        )
        self.assertNotIn(closure.ADDED_PROMPT_SENTENCE, prior)
        self.assertEqual(future.count(closure.ADDED_PROMPT_SENTENCE), 1)

    def test_completed_prompt_fingerprint_remains_unchanged(self) -> None:
        prior = step6.prompt_instruction_fingerprint()
        future = step6.prompt_instruction_fingerprint(
            include_future_no_signal_confidence_clarification=True,
        )
        self.assertNotEqual(prior, future)

    def test_no_signal_prompt_contract_accepts_numeric_boundaries(self) -> None:
        results = closure.build_prompt_contract_test_results(step6)
        permitted = {row["name"] for row in results["results"] if row["result"] == "PERMITTED"}
        self.assertEqual(
            permitted,
            {
                "NO_SIGNAL confidence=0.0",
                "NO_SIGNAL confidence=0.5",
                "NO_SIGNAL confidence=1.0",
            },
        )

    def test_no_signal_prompt_contract_rejects_null_and_missing_confidence(self) -> None:
        results = closure.build_prompt_contract_test_results(step6)
        rejected = {row["name"]: row["expected_error"] for row in results["results"] if row["result"] == "REJECTED"}
        self.assertEqual(
            rejected,
            {
                "NO_SIGNAL confidence=null": "PROVIDER_OUTPUT_TYPES",
                "NO_SIGNAL confidence omitted": "PROVIDER_OUTPUT_FIELDS",
            },
        )

    def test_drifting_warning_requires_authorization(self) -> None:
        warning = closure.build_drifting_warning()
        self.assertEqual(warning["warning"], "DRIFTING WARNING")
        self.assertIn("authorization is required", warning["authorization"].lower())

    def test_future_batches_start_after_batch_003(self) -> None:
        lineage, impact, migration = closure.build_prompt_lineage_and_impact(step6)
        self.assertEqual(lineage["first_eligible_future_batch"], "FCB_PACK_A_004")
        self.assertEqual(impact["affected_future_batch_count"], 45)
        self.assertEqual(impact["affected_future_call_count"], 528)
        self.assertFalse(impact["manifests_changed"])
        self.assertTrue(
            migration["authorization_required"],
        )
        self.assertIn(
            "Preserve forecast_call_id only where governance explicitly deems the forward-looking prompt-version amendment scientifically compatible; otherwise mint new future-only call identities.",
            migration["smallest_plan_aligned_migration"],
        )


if __name__ == "__main__":
    unittest.main()
