import json
import unittest
from unittest.mock import patch

from automation import run_presignal_v21_new_r6_native_attention_execution_v1 as subject


class FomcAttentionExecutionTests(unittest.TestCase):
    def test_authorization_and_cutoff_guards(self):
        self.assertEqual("NEW_R6_NATIVE_ATTENTION_BLOCKED_CUTOFF_CLOSED", subject.run(do_dispatch=False, at_utc="2026-07-29T18:00:00Z"))

    def test_one_selected_response_prepares_inactive_request_authorization(self):
        raw = {"object": "session_attention_map", "session_id": subject.EPISODE, "provider": "macro-research-model", "status": "ok", "attention_items": [{"event_id": "5ea0-ce20-ad20-fba0", "attention_label": "PRIMARY_DRIVER", "attention_rank": 1, "attention_reason": "The policy decision directly sets the near-term US rate path.", "expected_market_channel": "Rates and FX", "driver_role": "Monetary Policy", "confidence": "High"}], "session_attention_summary": "The rate decision is the sole supplied event."}
        response = {"status": "ok", "actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite", "completed_timestamp": "2026-07-24T05:09:34Z", "raw_output": raw, "requested_provider": "Gemini", "requested_model": "gemini-2.5-flash-lite"}
        with patch.object(subject, "dispatch", return_value=response) as dispatched:
            decision = subject.run(do_dispatch=True, at_utc="2026-07-24T05:09:34Z")
        self.assertEqual("NEW_R6_NATIVE_ATTENTION_ACCEPTED_REQUEST_AUTHORIZATION_PREPARED", decision); dispatched.assert_called_once()
        req = json.loads((subject.OUT / "new_r6_information_request_authorization_preparation.json").read_text())
        self.assertFalse(req["authorization_activated"]); self.assertFalse(req["request_call_executed"])
        attention = json.loads((subject.OUT / "new_r6_native_attention.json").read_text())
        self.assertNotEqual("NATTN_b85703c6c08cdfdffd27", attention["attention_identity"])


if __name__ == "__main__":
    unittest.main()
