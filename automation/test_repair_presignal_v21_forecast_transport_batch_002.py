from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import repair_presignal_v21_forecast_transport_batch_002 as repair


class ForecastTransportRepairBatch002Test(unittest.TestCase):
    def test_incomplete_call_is_kept_non_retryable(self) -> None:
        result = repair.classify_incomplete_call({"started_at": "2026-07-29T13:41:24Z"}, {})
        self.assertEqual(result["classification"], "REMOTE_EXECUTION_STATE_UNKNOWN")
        self.assertEqual(result["decision"], "INCOMPLETE_CALL_REMOTE_STATE_UNKNOWN")
        self.assertEqual(result["retry_safety_classification"], "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN")

    def test_retry_safety_respects_confirmed_not_sent_transport(self) -> None:
        call = {"forecast_call_id": "FCL_test", "provider": "Gemini", "model": "gemini-2.5-flash-lite", "episode_id": "EP_test"}
        failed = {"terminal_state": "FAILED_TRANSPORT"}
        safe = repair.classify_retry_safety(
            call=call,
            failed_row=failed,
            transport_row={"transport_classification": {"category": "GOOGLE_API_CONNECTION_ERROR", "dispatch_certainty": "CONFIRMED_NOT_SENT"}},
        )
        unsafe = repair.classify_retry_safety(
            call=call,
            failed_row=failed,
            transport_row={"transport_classification": {"category": "GOOGLE_API_TIMEOUT", "dispatch_certainty": "UNKNOWN"}},
        )
        self.assertEqual(safe["retry_safety_classification"], "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT")
        self.assertEqual(unsafe["retry_safety_classification"], "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN")

    def test_execute_repair_creates_append_only_diagnosis_without_resume(self) -> None:
        verification = {
            "status": "PASSED",
            "health_function": "presignalRuntimeHealthCheck",
            "service_rebuilt_per_attempt": True,
            "script_http_timeout_seconds": repair.SCRIPT_TIMEOUT_SECONDS,
            "attempts": [
                {"attempt": 1, "transport_ok": True, "classification": {"category": "READY"}},
                {"attempt": 2, "transport_ok": True, "classification": {"category": "READY"}},
                {"attempt": 3, "transport_ok": True, "classification": {"category": "READY"}},
            ],
            "provider_calls": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(repair, "verify_transport_repair", return_value=verification), mock.patch.object(
                repair,
                "git_branch",
                return_value="codex/immediate-impulse-outcome-recovery-r1",
            ), mock.patch.object(
                repair,
                "git_head",
                return_value="1e82c6df5d8de5327a412ccbef3de0974e4377de",
            ), mock.patch.object(repair, "is_descendant_of", return_value=True):
                result = repair.execute_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:30:00Z")
            self.assertEqual(result["decisions"]["resume_decision"], "BATCH_002_NOT_RESUMED_RETRY_SAFETY_NOT_PROVEN")
            self.assertEqual(result["decisions"]["repair_decision"], "SHARED_TRANSPORT_REPAIR_VALIDATED")
            self.assertIn("FCL_1e7b6936b48bf931a7ed5e7d", result["safe_retry_calls"])
            self.assertIn("FCL_64c262f5f677009a4ce5c45a", result["safe_retry_calls"])
            self.assertIn("FCL_befd6d6947490cc19f4754b9", result["unsafe_retry_calls"])
            self.assertIn("FCL_d72f741393a7643ea859edb8", result["unsafe_retry_calls"])
            run_dir = result["run_dir"]
            self.assertTrue((run_dir / "retry_safety_ledger.jsonl").exists())
            self.assertTrue((run_dir / "resume_authorization_decision.json").exists())
            decision = repair.read_json(run_dir / "repair_decision.json")
            self.assertEqual(decision["next_phase_decision"], "RETRY_AUTHORIZATION_REQUIRES_GOVERNANCE")


if __name__ == "__main__":
    unittest.main()
