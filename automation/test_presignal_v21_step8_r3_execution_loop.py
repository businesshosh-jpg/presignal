import json
import shutil
import unittest

from automation import run_presignal_v21_step8_r3_fresh_historical_verification_v1 as runner
from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat
from automation import repair_presignal_v21_step8_r3_r6_compatibility_v1 as r6


def forecast(direction="UP"):
    return {
        "no_signal_flag": False, "no_signal_reason": None, "confidence": 0.6,
        "expected_initial_direction": direction, "expected_reversal_flag": False,
        "expected_reversal_horizon_min": None, "expected_path_summary": "fixture",
        "information_used": "frozen", "missing_information": "none", "invalidation_condition": "fixture",
        "path": [{"horizon_min": horizon, "expected_direction": direction, "expected_pips_min": 1.0,
                  "expected_pips_max": 2.0, "stage_confidence": 0.6,
                  "continuation_probability": 0.6, "reversal_probability": 0.1,
                  "stage_reason": "fixture", "invalidation_condition": "fixture"}
                 for horizon in (5, 15, 30, 60)],
    }


class MockBridge:
    def __init__(self, malformed_anthropic=False):
        self.calls = []
        self.malformed_anthropic = malformed_anthropic

    def __call__(self, request):
        self.calls.append(dict(request))
        provider, arm = request["provider"], request["arm"]
        if arm == "LINEAGE_ATTENTION":
            if provider == "Anthropic" and self.malformed_anthropic:
                raw = "not json"
            else:
                events = json.loads(request["prompt"]["user"])["events"]
                raw = {"object": "session_attention_map", "session_id": request["session_id"], "provider": provider,
                       "status": "ok", "attention_items": [
                           {"event_id": item["event_id"], "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST",
                            "attention_rank": index + 1, "attention_reason": "fixture",
                            "expected_market_channel": "treasury_yields", "driver_role": "primary", "confidence": 0.7}
                           for index, item in enumerate(events)]}
                raw = "```json\n" + json.dumps(raw) + "\n```" if provider == "Anthropic" else json.dumps(raw)
        elif arm == "LINEAGE_REQUESTS":
            raw = json.dumps({"object": "session_information_requirements", "session_id": request["session_id"],
                              "provider": provider, "status": "ok", "information_items": [{
                                  "request_rank": 1, "requested_information": "US 2Y yield",
                                  "information_category": "treasury_yields", "priority": "must_have",
                                  "reason": "fixture", "affected_channel": "treasury_yields",
                                  "event_family_relevance": "session", "linked_event_ids": [],
                                  "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "unknown",
                                  "suggested_source": "fixture", "expected_forecast_use": "context",
                                  "is_market_state_candidate": True}]})
        else:
            raw = json.dumps(forecast())
        return {"status": "ok", "actual_provider": provider, "actual_model": request["model"],
                "raw_output": raw, "completed_timestamp": "2024-07-03T05:00:00Z"}


class LoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r6.prepare()

    def setUp(self):
        self.bridge = MockBridge()
        self.loop = runner.ExecutionLoop("TEST-R3-ADAPTER-DISPATCH", dispatcher=self.bridge)
        shutil.rmtree(self.loop.run, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.loop.run, ignore_errors=True)

    def test_concrete_adapter_backed_end_to_end_and_resume(self):
        result = self.loop.process_episode(self.loop.first_episode())
        self.assertEqual(set(result["results"]), {"Anthropic", "Gemini", "OpenAI"})
        self.assertEqual(self.loop.status()["unique_complete_episodes"], 1)
        self.assertEqual(len(self.bridge.calls), 12)  # three Attention, Requests, and paired forecasts.
        result_files = list((self.loop.run / "stage_results").glob("*.json"))
        self.assertTrue(any(json.loads(path.read_text())["raw_response"] for path in result_files))
        before = len(self.bridge.calls)
        self.assertEqual(self.loop.process_episode(self.loop.first_episode())["status"], "ALREADY_PROCESSED")
        self.assertEqual(len(self.bridge.calls), before)
        self.assertTrue(any("For UP use" in json.loads(path.read_text())["payload"].get("payload", {}).get("prompt", {}).get("user", "") for path in (self.loop.run / "stage_payloads").glob("*.json") if "payload" in json.loads(path.read_text())["payload"]))

    def test_anthropic_r3_parser_rejection_is_terminal_and_not_retried(self):
        self.bridge = MockBridge(malformed_anthropic=True)
        self.loop = runner.ExecutionLoop("TEST-R3-ANTHROPIC-REJECTION", dispatcher=self.bridge)
        shutil.rmtree(self.loop.run, ignore_errors=True)
        result = self.loop.process_episode(self.loop.first_episode())
        self.assertEqual(result["terminal"]["Anthropic"], "ATTENTION_REJECTED")
        anth_calls = [call for call in self.bridge.calls if call["provider"] == "Anthropic"]
        self.assertEqual(len(anth_calls), 1)
        self.assertEqual(anth_calls[0]["arm"], "LINEAGE_ATTENTION")
        raw_records = [json.loads(path.read_text()) for path in (self.loop.run / "raw_provider_responses").glob("*.json")]
        self.assertTrue(any(record["identity"]["provider"] == "Anthropic" and record["raw_output"] == "not json" for record in raw_records))

    def test_payload_conflict_fails_closed(self):
        episode = self.loop._load_source()[1][self.loop.first_episode()]
        identity = self.loop._identity(episode, "Gemini", "gemini-2.5-flash-lite", "ATTENTION")
        self.loop._persist_payload(identity, {"one": 1})
        with self.assertRaisesRegex(runner.DispatchError, "RECONCILIATION_CONFLICT"):
            self.loop._persist_payload(identity, {"one": 2})

    def test_r6_contract_is_bound_and_previous_manifest_is_rejected(self):
        self.assertEqual(self.loop.gate["contract"]["contract_version"], compat.CONTRACT_VERSION)
        self.assertIn("attention_reason must contain at most six words", binding.attention_instruction(self.loop.gate["contract"], "Anthropic"))
        self.assertIn("information_category=(treasury_yields", binding.request_instruction(self.loop.gate["contract"], "Gemini"))
        with self.assertRaisesRegex(runner.DispatchError, "PREVIOUS_CONTRACT_REJECTED"):
            runner.ExecutionLoop("TEST-R3-OLD-CONTRACT", dispatcher=self.bridge, manifest_path=binding.PREP)

    def test_child_request_instruction_drives_canonical_enum_fixture(self):
        result = self.loop.process_episode(self.loop.first_episode())
        request_calls = [call for call in self.bridge.calls if call["arm"] == "LINEAGE_REQUESTS"]
        self.assertTrue(request_calls)
        for call in request_calls:
            self.assertIn("priority=(must_have|useful|optional|low_value)", call["prompt"]["instruction"])
            self.assertIn("Request priority is separate from Attention classification", call["prompt"]["instruction"])
            self.assertIn("information_category=(treasury_yields", call["prompt"]["instruction"])
        self.assertTrue(all(payload["forecasts"]["PACK_A"]["accepted"] for payload in result["results"].values()))


if __name__ == "__main__":
    unittest.main()
