from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import finalize_presignal_v21_attention_batch_001 as finalizer


class FinalizeAttentionBatch001CorrectedTest(unittest.TestCase):
    def test_only_unresolved_call_can_be_dispatched(self) -> None:
        checked = finalizer.verify_governing_artifacts()
        self.assertEqual(checked["retry_call"]["call_id"], finalizer.AUTHORIZED_CALL_ID)
        self.assertEqual(len(checked["prior_results"]), 11)
        self.assertEqual(len(checked["remaining"]), 1)

    def test_11_valid_calls_cannot_be_repeated(self) -> None:
        checked = finalizer.verify_governing_artifacts()
        imported_ids = {row["call_id"] for row in checked["prior_results"]}
        self.assertNotIn(finalizer.AUTHORIZED_CALL_ID, imported_ids)
        self.assertEqual(len(imported_ids), 11)

    def test_runtime_correction_is_frozen(self) -> None:
        checked = finalizer.verify_governing_artifacts()
        exact = checked["correction"]["exact_correction"]
        self.assertEqual((exact["generation_settings"] or {}).get("max_output_tokens"), 8192)
        self.assertTrue((exact["generation_settings"] or {}).get("preserve_raw_before_parse"))
        self.assertEqual(checked["retry_call"]["provider"], "Anthropic")
        self.assertEqual(checked["retry_call"]["model"], "claude-haiku-4-5")

    def test_finalize_success_imports_11_and_dispatches_one(self) -> None:
        calls = []

        def preflight():
            return {
                "token_path_resolution_method": "test",
                "resolved_token_path": str(finalizer.TOKEN_PATH),
                "token_reused": True,
                "spreadsheet_id": "sheet",
                "spreadsheet_title": "title",
                "script_id": "script",
                "script_file_count": 1,
                "google_writes": 0,
            }

        def dispatcher(request):
            calls.append(request)
            payload = json.loads(request["prompt"]["user"])
            events = payload["events"]
            raw = {
                "object": "session_attention_map",
                "session_id": request["session_id"],
                "provider": "macroeconomic_research_model",
                "status": "ok",
                "attention_items": [
                    {
                        "event_id": row["event_id"],
                        "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST",
                        "attention_rank": index + 1,
                        "attention_reason": "compact reason",
                        "expected_market_channel": "treasury_yields",
                        "driver_role": "primary" if index == 0 else "watch",
                        "confidence": 0.7,
                    }
                    for index, row in enumerate(events)
                ],
            }
            return {
                "status": "ok",
                "actual_provider": request["provider"],
                "actual_model": request["model"],
                "raw_output_original": "```json\n" + json.dumps(raw) + "\n```",
                "raw_output": "```json\n" + json.dumps(raw) + "\n```",
                "stop_reason": "end_turn",
                "prompt_tokens": 123,
                "completion_tokens": 456,
                "configured_max_output_tokens": request.get("max_output_tokens"),
                "completed_timestamp": "2026-07-29T04:00:00Z",
                "usage_metadata": {"input_tokens": 123, "output_tokens": 456},
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T040000Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
            )
            self.assertEqual(result["decision"]["finalization_status"], "ATTENTION_BATCH_001_FINALIZED")
            self.assertEqual(result["decision"]["retry_decision"], "FINAL_CORRECTED_RETRY_SUCCEEDED_VALID")
            self.assertEqual(len(result["imported_rows"]), 11)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["provider"], "Anthropic")
            self.assertEqual(calls[0]["model"], "claude-haiku-4-5")
            self.assertEqual(calls[0]["max_output_tokens"], 8192)
            self.assertTrue(calls[0]["preserve_raw_before_parse"])
            self.assertEqual(len(result["final_results"]), 12)
            self.assertEqual(len(result["remaining_failed"]), 0)
            raw = finalizer.read_json(result["run_dir"] / "retry_raw_provider_output.json")
            self.assertTrue(raw["raw_output_returned"])
            self.assertIn("session_attention_map", raw["raw_output"])

    def test_retry_failure_preserves_raw_and_does_not_retry_again(self) -> None:
        calls = []

        def preflight():
            return {
                "token_path_resolution_method": "test",
                "resolved_token_path": str(finalizer.TOKEN_PATH),
                "token_reused": True,
                "spreadsheet_id": "sheet",
                "spreadsheet_title": "title",
                "script_id": "script",
                "script_file_count": 1,
                "google_writes": 0,
            }

        def dispatcher(request):
            calls.append(request)
            return {
                "status": "ok",
                "actual_provider": request["provider"],
                "actual_model": request["model"],
                "raw_output_original": "{\"broken\": ",
                "raw_output": "{\"broken\": ",
                "stop_reason": "max_tokens",
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "configured_max_output_tokens": request.get("max_output_tokens"),
                "completed_timestamp": "2026-07-29T04:01:00Z",
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T040100Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
            )
            self.assertEqual(result["decision"]["finalization_status"], "ATTENTION_BATCH_001_TERMINAL_PARTIAL")
            self.assertEqual(result["decision"]["retry_decision"], "FINAL_CORRECTED_RETRY_FAILED")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(result["remaining_failed"]), 1)
            raw = finalizer.read_json(result["run_dir"] / "retry_raw_provider_output.json")
            self.assertEqual(raw["raw_output"], "{\"broken\": ")
            self.assertTrue(raw["raw_output_returned"])
            journal = finalizer.operation_transcript(result["run_dir"] / "operation_journal.jsonl")
            self.assertEqual(sum(row["event"] == "FINAL_CORRECTED_RETRY_STARTED" for row in journal), 1)

    def test_no_second_retry_and_final_count_is_bounded(self) -> None:
        calls = []

        def preflight():
            return {
                "token_path_resolution_method": "test",
                "resolved_token_path": str(finalizer.TOKEN_PATH),
                "token_reused": True,
                "spreadsheet_id": "sheet",
                "spreadsheet_title": "title",
                "script_id": "script",
                "script_file_count": 1,
                "google_writes": 0,
            }

        def dispatcher(request):
            calls.append(request["forecast_identity"])
            return {
                "status": "ok",
                "actual_provider": request["provider"],
                "actual_model": request["model"],
                "raw_output_original": "",
                "raw_output": "",
                "completed_timestamp": "2026-07-29T04:02:00Z",
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T040200Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
            )
            self.assertEqual(len(calls), 1)
            self.assertIn(len(result["final_results"]), {11, 12})
            self.assertEqual(result["decision"]["scaling_decision"], "BATCH_001_EXCEPTION_REQUIRES_GOVERNANCE_DECISION")


if __name__ == "__main__":
    unittest.main()
