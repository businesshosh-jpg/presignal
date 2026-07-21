import json
import shutil
import unittest

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as r2
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import repair_presignal_v21_step8_r3_r6_compatibility_v1 as r6
from automation import run_presignal_v21_step8_r3_fresh_historical_verification_v1 as runner


class R6CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = r6.prepare()

    def test_contract_and_anthropic_settings_are_manifest_bound(self):
        gate = binding.gate(self.manifest)
        self.assertEqual(gate["contract"]["contract_version"], r2.CONTRACT_VERSION)
        self.assertEqual(binding.generation_settings(gate["contract"], "Anthropic", "ATTENTION"), {"max_output_tokens": 8192, "preserve_raw_before_parse": True})
        self.assertEqual(binding.generation_settings(gate["contract"], "Anthropic", "REQUEST"), {})
        self.assertEqual(binding.generation_settings(gate["contract"], "Gemini", "ATTENTION"), {})

    def test_request_priority_is_strict_and_other_is_exactly_normalized(self):
        spec = r2.spec()
        changed, provenance = binding.normalize_request_item({"affected_channel": "other"}, spec)
        self.assertEqual(changed["affected_channel"], "unknown")
        self.assertEqual(provenance["original_value"], "other")
        same, none = binding.normalize_request_item({"affected_channel": "Other"}, spec)
        self.assertEqual(same["affected_channel"], "Other")
        self.assertIsNone(none)
        self.assertNotIn("primary_driver", lineage.VALID_PRIORITIES)
        self.assertNotIn("secondary_driver", lineage.VALID_PRIORITIES)

    def test_raw_response_is_persisted_before_anthropic_parser_rejection(self):
        loop = runner.ExecutionLoop("TEST-R3-R6-RAW", dispatcher=lambda _: {"status": "ok"}, manifest_path=self.manifest)
        shutil.rmtree(loop.run, ignore_errors=True)
        identity = {"run_id": loop.run.name, "session_id": "S", "episode_id": "E", "provider": "Anthropic", "model": "claude-haiku-4-5", "stage": "ATTENTION", "information_arm": None, "contract_fingerprint": r2.spec()["contract_fingerprint"], "attempt_number": 1}
        response = {"status": "ok", "raw_output": "{\"unterminated\"", "stop_reason": "max_tokens", "configured_max_output_tokens": 8192}
        loop._persist_raw_bridge_response(identity, response)
        path = next((loop.run / "raw_provider_responses").glob("*.json"))
        saved = json.loads(path.read_text())
        self.assertEqual(saved["raw_output"], response["raw_output"])
        self.assertEqual(saved["stop_reason"], "max_tokens")

    def test_apps_script_route_is_explicitly_bounded_and_deferred(self):
        bridge = (runner.ROOT / "apps_script/authoritative_provider_bridge.js").read_text()
        provider = (runner.ROOT / "apps_script/prediction_runner.js").read_text()
        self.assertIn("configured_max_output_tokens", bridge)
        self.assertIn("defer_json_parsing", bridge)
        self.assertIn("max_tokens: maxTokens", provider)
        self.assertIn("maxTokens > 64000", provider)


if __name__ == "__main__":
    unittest.main()
