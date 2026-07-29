from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import diagnose_presignal_v21_forecast_batch_003_failures as diag


class Batch003DiagnosisTests(unittest.TestCase):
    def test_exactly_nine_failed_calls_are_inspected(self) -> None:
        state = diag.load_batch_003_state()
        self.assertEqual(len(state["failed"]), 9)
        self.assertEqual(set(state["failed"]), set(diag.TRANSPORT_FAILURES + diag.PROVIDER_FAILURES + [diag.PARSE_FAILURE]))

    def test_three_successful_calls_remain_immutable(self) -> None:
        state = diag.load_batch_003_state()
        self.assertEqual(len(state["normalized"]), 3)
        self.assertEqual(set(state["normalized"]), {"FCL_d591677837ba5b1b0fcd39ff", "FCL_99c46a5f924cf6617c74370b", "FCL_d576400379b9741913d6ec6f"})

    def test_all_four_transport_failures_are_inventoried(self) -> None:
        state = diag.load_batch_003_state()
        rows = [diag.classify_transport_failure(call_id, state) for call_id in diag.TRANSPORT_FAILURES]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["classification"] == "REMOTE_EXECUTION_STATE_UNKNOWN" for row in rows))

    def test_all_four_provider_failures_are_inventoried(self) -> None:
        state = diag.load_batch_003_state()
        rows = [diag.classify_provider_failure(call_id, state)[0] for call_id in diag.PROVIDER_FAILURES]
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["classification"] == "RECOVERABLE_PROVIDER_RESULT_FOUND" for row in rows))

    def test_parse_failure_is_separately_inspected(self) -> None:
        state = diag.load_batch_003_state()
        analysis, diffs, _ = diag.analyze_parse_failure(state)
        self.assertEqual(analysis["forecast_call_id"], diag.PARSE_FAILURE)
        self.assertEqual(len(diffs), 1)

    def test_no_provider_call_can_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T17:10:00Z")
        self.assertEqual(result["summary"]["cumulative_validated_forecast_calls"], 31)

    def test_no_batch_004_execution_can_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T17:11:00Z")
            manifest = diag.read_json(result["run_dir"] / "run_manifest.json")
        self.assertEqual(manifest["batch_004_calls_executed"], 0)

    def test_remote_state_unknown_calls_cannot_be_marked_retry_safe(self) -> None:
        state = diag.load_batch_003_state()
        row = diag.classify_transport_failure(diag.TRANSPORT_FAILURES[0], state)
        self.assertEqual(row["retry_classification"], "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN")

    def test_terminal_provider_errors_with_no_payload_are_separate_from_recoverable_existing_results(self) -> None:
        state = diag.load_batch_003_state()
        row, recovered = diag.classify_provider_failure(diag.PROVIDER_FAILURES[0], state)
        self.assertEqual(row["classification"], "RECOVERABLE_PROVIDER_RESULT_FOUND")
        self.assertEqual(recovered["validation_status"], "VALID")

    def test_provider_error_wrappers_cannot_enter_parsing(self) -> None:
        payload = {"status": "error", "response_status": "error", "provider_response_body": "", "raw_output": ""}
        self.assertTrue(diag.batch_exec.provider_error_without_forecast_payload(payload))

    def test_exact_raw_parse_failed_payload_remains_unchanged(self) -> None:
        state = diag.load_batch_003_state()
        raw_before = state["raw_transport"][diag.PARSE_FAILURE]["raw_transport_result"]["raw_output"]
        diag.analyze_parse_failure(state)
        raw_after = state["raw_transport"][diag.PARSE_FAILURE]["raw_transport_result"]["raw_output"]
        self.assertEqual(raw_before, raw_after)

    def test_mechanical_parse_recovery_cannot_alter_scientific_content(self) -> None:
        state = diag.load_batch_003_state()
        analysis, diffs, _ = diag.analyze_parse_failure(state)
        self.assertFalse(analysis["mechanical_repair_allowed"])
        self.assertEqual(diffs[0]["field"], "confidence")

    def test_ambiguous_content_cannot_be_coerced(self) -> None:
        state = diag.load_batch_003_state()
        analysis, _, _ = diag.analyze_parse_failure(state)
        self.assertEqual(analysis["classification"], "EXISTING_RESULT_NOT_RECOVERABLE_PROVIDER_SCHEMA_FAILURE")

    def test_recovered_results_require_provider_authority(self) -> None:
        state = diag.load_batch_003_state()
        _, recovered = diag.classify_provider_failure(diag.PROVIDER_FAILURES[0], state)
        self.assertTrue(recovered["provider_authority_result"]["authority_passed"])

    def test_recovered_results_require_strict_contract_validation(self) -> None:
        state = diag.load_batch_003_state()
        _, recovered = diag.classify_provider_failure(diag.PROVIDER_FAILURES[0], state)
        self.assertEqual(recovered["validation_status"], "VALID")

    def test_repository_history_discrepancy_is_explicitly_checked(self) -> None:
        history = diag.verify_repository_history()
        self.assertFalse(history["expected_prompt_hash_exists_locally"])
        self.assertTrue(history["actual_start_exists_locally"])

    def test_prior_evidence_remains_immutable(self) -> None:
        before = (diag.OUTPUT_ROOT / diag.BATCH_003_RUN_ID / "failed_call_ledger.jsonl").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T17:12:00Z")
        after = (diag.OUTPUT_ROOT / diag.BATCH_003_RUN_ID / "failed_call_ledger.jsonl").read_text()
        self.assertEqual(before, after)

    def test_no_google_writes_outcome_attachment_or_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T17:13:00Z")
            manifest = diag.read_json(result["run_dir"] / "run_manifest.json")
        self.assertEqual(manifest["google_writes_executed"], 0)
        self.assertEqual(manifest["outcome_attachment_executed"], 0)
        self.assertEqual(manifest["forecast_accuracy_calculations_executed"], 0)


if __name__ == "__main__":
    unittest.main()
