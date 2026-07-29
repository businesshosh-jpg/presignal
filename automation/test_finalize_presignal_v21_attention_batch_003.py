from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import finalize_presignal_v21_attention_batch_003 as finalizer


class FinalizeAttentionBatch003Test(unittest.TestCase):
    def test_only_two_failed_calls_may_be_dispatched(self) -> None:
        checked = finalizer.verify_governing_artifacts(enforce_head=False)
        self.assertEqual([row["call"]["call_id"] for row in checked["retries"]], finalizer.RETRY_CALL_IDS)
        self.assertEqual(len(checked["valid_rows"]), 10)

    def test_ten_valid_calls_cannot_be_repeated(self) -> None:
        checked = finalizer.verify_governing_artifacts(enforce_head=False)
        self.assertEqual(len(checked["valid_call_ids"]), 10)
        self.assertTrue(all(call_id not in checked["valid_call_ids"] for call_id in finalizer.RETRY_CALL_IDS))

    def test_provider_model_and_expected_event_sets_are_frozen(self) -> None:
        checked = finalizer.verify_governing_artifacts(enforce_head=False)
        for retry in checked["retries"]:
            self.assertEqual(retry["call"]["provider"], "OpenAI")
            self.assertEqual(retry["call"]["model"], "gpt-4o-mini-2024-07-18")
            self.assertTrue(retry["expected_event_ids"])
            self.assertTrue(set(retry["prior_omitted_event_ids"]).issubset(set(retry["expected_event_ids"])))

    def test_completeness_instruction_explicitly_lists_event_ids(self) -> None:
        instruction = finalizer.build_completeness_instruction("base", ["E1", "E2"])
        self.assertIn("Return exactly one Attention row for every expected event ID", instruction)
        self.assertIn("E1, E2", instruction)

    def test_completeness_check_fails_missing_duplicate_unexpected(self) -> None:
        checked = finalizer.verify_governing_artifacts(enforce_head=False)
        retry = checked["retries"][0]
        call = retry["call"]
        contract = checked["runtime_contract"]
        transport = {"actual_provider": call["provider"], "actual_model": call["model"]}
        raw_missing = json.dumps(
            {
                "object": "session_attention_map",
                "session_id": call["source_session_id"],
                "provider": "OpenAI",
                "status": "ok",
                "attention_items": [],
                "session_attention_summary": "x",
            }
        )
        completeness, _ = finalizer.determine_event_completeness(
            raw_output=raw_missing,
            call=call,
            contract=contract,
            expected_event_ids=["E1"],
            transport=transport,
        )
        self.assertEqual(completeness["completeness_decision"], "FAILED")
        self.assertEqual(completeness["missing_event_ids"], ["E1"])

        raw_duplicate = json.dumps(
            {
                "object": "session_attention_map",
                "session_id": call["source_session_id"],
                "provider": "OpenAI",
                "status": "ok",
                "attention_items": [
                    {
                        "event_id": "E1",
                        "attention_label": "WATCHLIST",
                        "attention_rank": 1,
                        "attention_reason": "a",
                        "expected_market_channel": "unknown",
                        "driver_role": "watch",
                        "confidence": 0.5,
                    },
                    {
                        "event_id": "E1",
                        "attention_label": "WATCHLIST",
                        "attention_rank": 2,
                        "attention_reason": "b",
                        "expected_market_channel": "unknown",
                        "driver_role": "watch",
                        "confidence": 0.5,
                    },
                ],
                "session_attention_summary": "x",
            }
        )
        completeness_dup, _ = finalizer.determine_event_completeness(
            raw_output=raw_duplicate,
            call=call,
            contract=contract,
            expected_event_ids=["E1"],
            transport=transport,
        )
        self.assertEqual(completeness_dup["duplicate_event_ids"], ["E1"])

    def test_success_path_imports_ten_and_dispatches_only_two(self) -> None:
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
                "provider": "OpenAI",
                "status": "ok",
                "attention_items": [
                    {
                        "event_id": row["event_id"],
                        "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST",
                        "attention_rank": index + 1,
                        "attention_reason": "complete reason",
                        "expected_market_channel": "unknown",
                        "driver_role": "primary" if index == 0 else "watch",
                        "confidence": 0.7,
                    }
                    for index, row in enumerate(events)
                ],
                "session_attention_summary": "complete",
            }
            return {
                "status": "ok",
                "actual_provider": request["provider"],
                "actual_model": request["model"],
                "raw_output_original": json.dumps(raw),
                "raw_output": json.dumps(raw),
                "stop_reason": "stop",
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "configured_max_output_tokens": request.get("max_output_tokens"),
                "completed_timestamp": "2026-07-29T06:00:00Z",
                "usage_metadata": {"input_tokens": 100, "output_tokens": 200},
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T060000Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
                enforce_head=False,
            )
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_003_CLOSED")
            self.assertEqual(result["decision"]["retry_decision"], "BOTH_COMPLETENESS_RETRIES_SUCCEEDED_VALID")
            self.assertEqual(len(result["imported_rows"]), 10)
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(result["final_results"]), 12)
            self.assertEqual(len(result["remaining_failed"]), 0)
            self.assertTrue(all(call["provider"] == "OpenAI" for call in calls))
            self.assertTrue(all(call["model"] == "gpt-4o-mini-2024-07-18" for call in calls))

    def test_failure_preserves_raw_output_and_no_additional_retry(self) -> None:
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
            payload = json.loads(request["prompt"]["user"])
            events = payload["events"][:-1]
            raw = {
                "object": "session_attention_map",
                "session_id": request["session_id"],
                "provider": "OpenAI",
                "status": "ok",
                "attention_items": [
                    {
                        "event_id": row["event_id"],
                        "attention_label": "WATCHLIST",
                        "attention_rank": index + 1,
                        "attention_reason": "incomplete reason",
                        "expected_market_channel": "unknown",
                        "driver_role": "watch",
                        "confidence": 0.7,
                    }
                    for index, row in enumerate(events)
                ],
                "session_attention_summary": "incomplete",
            }
            return {
                "status": "ok",
                "actual_provider": request["provider"],
                "actual_model": request["model"],
                "raw_output_original": json.dumps(raw),
                "raw_output": json.dumps(raw),
                "stop_reason": "stop",
                "prompt_tokens": 101,
                "completion_tokens": 201,
                "configured_max_output_tokens": request.get("max_output_tokens"),
                "completed_timestamp": "2026-07-29T06:01:00Z",
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T060100Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
                enforce_head=False,
            )
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_003_REMAINS_PARTIALLY_COMPLETE")
            self.assertEqual(result["decision"]["completeness_decision"], "EVENT_OMISSIONS_REMAIN")
            self.assertEqual(len(calls), 2)
            raw_rows = finalizer.read_jsonl(result["run_dir"] / "raw_provider_outputs.jsonl")
            self.assertEqual(len(raw_rows), 2)
            self.assertTrue(all(row["raw_output_returned"] for row in raw_rows))
            remaining = finalizer.read_jsonl(result["run_dir"] / "remaining_failed_calls.jsonl")
            self.assertTrue(remaining)


if __name__ == "__main__":
    unittest.main()
