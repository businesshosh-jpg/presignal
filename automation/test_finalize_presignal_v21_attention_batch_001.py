from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import finalize_presignal_v21_attention_batch_001 as finalizer


class FinalizeAttentionBatch001Test(unittest.TestCase):
    def test_preconditions_require_exact_11_plus_one(self) -> None:
        checked = finalizer.verify_preconditions()
        self.assertEqual(len(checked["recovered"]), 11)
        self.assertEqual(len({row["call_id"] for row in checked["recovered"]}), 11)
        self.assertEqual(checked["remaining"][0]["call_id"], "ATN_d7c95516e95938578834")

    def test_only_authorized_retry_call_is_present(self) -> None:
        checked = finalizer.verify_preconditions()
        self.assertEqual(checked["retry_call"]["call_id"], finalizer.AUTHORIZED_RETRY_CALL_ID)
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
            calls.append(
                {
                    "provider": request["provider"],
                    "model": request["model"],
                    "session_id": request["session_id"],
                    "forecast_identity": request["forecast_identity"],
                }
            )
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
                        "attention_reason": "fixture",
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
                "raw_output": "```json\n" + json.dumps(raw) + "\n```",
                "completed_timestamp": "2026-07-29T03:00:00Z",
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "latency_ms": 1000,
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T030000Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
            )
            self.assertEqual(result["decision"]["finalization_status"], "ATTENTION_BATCH_001_FINALIZED")
            self.assertEqual(len(result["imported_rows"]), 11)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["retry_call"]["call_id"], "ATN_d7c95516e95938578834")
            self.assertEqual(len(result["final_results"]), 12)
            self.assertEqual(len(result["remaining_failed"]), 0)

    def test_retry_failure_does_not_trigger_second_retry(self) -> None:
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
                "raw_output": "",
                "completed_timestamp": "2026-07-29T03:00:00Z",
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = finalizer.finalize(
                output_root=Path(tmp),
                fixed_timestamp="20260729T030100Z",
                dispatcher=dispatcher,
                preflight_override=preflight,
            )
            self.assertEqual(result["decision"]["finalization_status"], "ATTENTION_BATCH_001_REMAINS_PARTIALLY_COMPLETE")
            self.assertEqual(result["decision"]["retry_decision"], "AUTHORIZED_RETRY_FAILED")
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(result["remaining_failed"]), 1)


if __name__ == "__main__":
    unittest.main()
