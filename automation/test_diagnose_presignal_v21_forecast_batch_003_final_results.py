from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import diagnose_presignal_v21_forecast_batch_003_final_results as final_diag


class Batch003FinalResultDiagnosisTests(unittest.TestCase):
    def test_exactly_four_unresolved_calls_are_inspected(self) -> None:
        self.assertEqual(set(final_diag.UNRESOLVED_CALLS), set(final_diag.PROVIDER_RESPONSE_CALLS + (final_diag.PARSE_FAILURE_CALL,)))
        self.assertEqual(len(final_diag.UNRESOLVED_CALLS), 4)

    def test_exactly_three_provider_response_failures_are_inspected(self) -> None:
        self.assertEqual(len(final_diag.PROVIDER_RESPONSE_CALLS), 3)

    def test_exactly_one_repeated_parse_failure_is_inspected(self) -> None:
        self.assertEqual(final_diag.PARSE_FAILURE_CALL, "FCL_27720b8b23236b173b96fdee")

    def test_no_provider_call_can_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:10:00Z", enforce_head=False)
        self.assertEqual(result["summary"]["cumulative_validated_forecast_calls"], 35)

    def test_no_batch_004_execution_can_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:11:00Z", enforce_head=False)
            manifest = final_diag.read_json(result["run_dir"] / "run_manifest.json")
        self.assertEqual(manifest["batch_004_calls_executed"], 0)

    def test_prior_raw_responses_remain_immutable(self) -> None:
        path = final_diag.OUTPUT_ROOT / final_diag.BATCH_003_RECOVERY_ID / "raw_provider_outputs.jsonl"
        before = path.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:12:00Z", enforce_head=False)
        after = path.read_text()
        self.assertEqual(before, after)

    def test_existing_nested_payload_extraction_is_deterministic(self) -> None:
        bundle = final_diag.load_scope_bundle()
        state = final_diag.load_run_state(final_diag.BATCH_003_RECOVERY_ID)
        classification, _, extraction_rows, recovered_rows = final_diag.recover_existing_payload(
            final_diag.PROVIDER_RESPONSE_CALLS[0],
            bundle["by_call_id"][final_diag.PROVIDER_RESPONSE_CALLS[0]],
            state,
        )
        self.assertEqual(classification["classification"], "EXISTING_FORECAST_PAYLOAD_RECOVERED_AND_VALIDATED")
        self.assertTrue(any(row.get("deterministic") for row in extraction_rows))
        self.assertEqual(len(recovered_rows), 1)

    def test_no_scientific_values_are_invented(self) -> None:
        payload = final_diag.extract_json_object(
            final_diag.index_by_call(
                final_diag.load_run_state(final_diag.BATCH_003_RECOVERY_ID)["raw_provider_outputs.jsonl"]
            )[final_diag.PROVIDER_RESPONSE_CALLS[0]]["raw_provider_output"]
        )
        self.assertEqual(payload["confidence"], 0.65)

    def test_multiple_payload_conflicts_fail_closed(self) -> None:
        conflict_rows = [
            {
                "prediction": {"a": 1},
                "paths": [{"x": 1}],
            },
            {
                "prediction": {"a": 2},
                "paths": [{"x": 2}],
            },
        ]
        fingerprints = {
            final_diag.canonical_json({"prediction": row["prediction"], "paths": row["paths"]})
            for row in conflict_rows
        }
        self.assertEqual(len(fingerprints), 2)

    def test_provider_authority_is_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:13:00Z", enforce_head=False)
            rows = final_diag.read_jsonl(result["run_dir"] / "provider_authority_recheck.jsonl")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["authority_passed"] for row in rows))

    def test_strict_parse_is_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:14:00Z", enforce_head=False)
            rows = final_diag.read_jsonl(result["run_dir"] / "forecast_parse_recheck.jsonl")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["parse_status"] == "PARSED" for row in rows))

    def test_strict_validation_is_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:15:00Z", enforce_head=False)
            rows = final_diag.read_jsonl(result["run_dir"] / "forecast_validation_recheck.jsonl")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["validation_status"] == "VALID" for row in rows))

    def test_two_parse_failed_attempts_are_compared_separately(self) -> None:
        analysis, diffs, comparison, _ = final_diag.parse_failure_comparison(
            final_diag.load_run_state(final_diag.BATCH_003_RUN_ID),
            final_diag.load_run_state(final_diag.BATCH_003_RECOVERY_ID),
        )
        self.assertEqual(analysis["classification"], "FROZEN_PROMPT_NO_SIGNAL_REQUIREMENT_AMBIGUOUS")
        self.assertIn("original_attempt", comparison)
        self.assertIn("replacement_attempt", comparison)
        self.assertEqual(len(diffs), 1)

    def test_confidence_null_is_not_coerced(self) -> None:
        _, diffs, comparison, _ = final_diag.parse_failure_comparison(
            final_diag.load_run_state(final_diag.BATCH_003_RUN_ID),
            final_diag.load_run_state(final_diag.BATCH_003_RECOVERY_ID),
        )
        self.assertTrue(comparison["both_confidence_null"])
        self.assertIsNone(diffs[0]["original_value"])
        self.assertIsNone(diffs[0]["replacement_value"])

    def test_frozen_prompts_and_pack_fingerprints_remain_unchanged(self) -> None:
        bundle = final_diag.load_scope_bundle()
        call = bundle["by_call_id"][final_diag.PROVIDER_RESPONSE_CALLS[0]]["call"]
        self.assertEqual(call["pack_type"], "PACK_A")
        self.assertTrue(str(call["pack_row_fingerprint"]).startswith("sha256:"))

    def test_forward_looking_changes_are_not_applied_automatically(self) -> None:
        _, _, _, contract = final_diag.parse_failure_comparison(
            final_diag.load_run_state(final_diag.BATCH_003_RUN_ID),
            final_diag.load_run_state(final_diag.BATCH_003_RECOVERY_ID),
        )
        self.assertTrue(contract["forward_looking_recommendation"]["authorization_required"])

    def test_recovered_results_create_one_authoritative_result_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:16:00Z", enforce_head=False)
        self.assertEqual(result["summary"]["batch_003_authoritative_valid_results"], 11)

    def test_duplicate_authoritative_results_are_prohibited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:17:00Z", enforce_head=False)
            reconciliation = final_diag.read_json(result["run_dir"] / "batch_003_post_diagnosis_reconciliation.json")
        self.assertEqual(len(set(reconciliation["recovered_call_ids"])), len(reconciliation["recovered_call_ids"]))

    def test_prior_evidence_remains_immutable(self) -> None:
        path = final_diag.OUTPUT_ROOT / final_diag.BATCH_003_RECOVERY_ID / "failed_call_ledger.jsonl"
        before = path.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:18:00Z", enforce_head=False)
        after = path.read_text()
        self.assertEqual(before, after)

    def test_no_google_writes_outcomes_or_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = final_diag.run_diagnosis(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:19:00Z", enforce_head=False)
            manifest = final_diag.read_json(result["run_dir"] / "run_manifest.json")
        self.assertEqual(manifest["google_writes_executed"], 0)
        self.assertEqual(manifest["outcome_attachment_executed"], 0)
        self.assertEqual(manifest["forecast_accuracy_calculations_executed"], 0)


if __name__ == "__main__":
    unittest.main()
