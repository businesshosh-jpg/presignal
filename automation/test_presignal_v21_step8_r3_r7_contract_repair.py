import json
import shutil
import unittest

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_event_path_contract_v1 as event_contract
from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat
from automation import repair_presignal_v21_step8_r3_r9_provider_isolation_v1 as r9
from automation import run_presignal_v21_step8_r3_fresh_historical_verification_v1 as runner


class R7ContractRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = r9.prepare()

    def test_contract_and_all_provider_prompts_use_absolute_pip_representation(self):
        gate = binding.gate(self.manifest)
        self.assertEqual(gate["contract"]["contract_version"], compat.CONTRACT_VERSION)
        row = {
            "information_arm": "PACK_A", "pack_fingerprint": "fixture", "shared_market_state_pack": None,
            "episode_id": "E", "source_session_id": "S", "country": "US", "release_ts": "2024-01-01T00:00:00Z",
            "forecast_cutoff_ts": "2024-01-01T00:00:00Z", "episode_members": [{"event_id": "EV", "indicator_name": "Fixture"}],
            "structural_component_roles": [], "provider_attention_map": [{"event_id": "EV", "attention_label": "PRIMARY_DRIVER"}],
            "information_requests": [],
        }
        for provider in ("Anthropic", "Gemini", "OpenAI"):
            prompt = binding.forecast_prompt(row, provider, gate["contract"])
            self.assertIn("nonnegative absolute pip magnitudes", prompt)
            self.assertIn('"direction":"DOWN","expected_pips_min":5,"expected_pips_max":15', prompt)

    def test_only_the_exact_anthropic_identity_is_normalized(self):
        raw = "```json\n" + json.dumps({"object": "session_attention_map", "session_id": "S", "provider": "presignal_v2", "attention_items": [], "status": "ok"}) + "\n```"
        parsed = binding.attention_parser("Anthropic", raw, compat.spec())
        self.assertEqual(parsed["provider"], "Anthropic")
        self.assertEqual(parsed["_provider_identity_normalization"]["model_emitted_provider_identity"], "presignal_v2")
        contradictory = json.dumps({"object": "session_attention_map", "session_id": "S", "provider": "unexpected", "attention_items": [], "status": "ok"})
        with self.assertRaisesRegex(binding.BindingError, "IDENTITY_CONTRADICTION"):
            binding.attention_parser("Anthropic", contradictory, compat.spec())

    def test_only_unknown_information_category_maps_to_other(self):
        normalized, provenance = binding.normalize_request_item({"information_category": "unknown", "affected_channel": "other"}, compat.spec())
        self.assertEqual(normalized["information_category"], "other")
        self.assertEqual(normalized["affected_channel"], "unknown")
        self.assertEqual(len(provenance["normalizations"]), 2)
        unchanged, none = binding.normalize_request_item({"information_category": "invalid"}, compat.spec())
        self.assertEqual(unchanged["information_category"], "invalid")
        self.assertIsNone(none)

    def test_existing_validator_accepts_absolute_down_and_rejects_negative_down(self):
        from automation.test_presignal_v21_step8_r3_execution_loop import MockBridge

        loop = runner.ExecutionLoop("TEST-R3-R7-DOWN", dispatcher=MockBridge(), manifest_path=self.manifest)
        shutil.rmtree(loop.run, ignore_errors=True)
        loop.process_episode(loop.first_episode())
        result = next(json.loads(path.read_text()) for path in (loop.run / "stage_results").glob("*.json") if json.loads(path.read_text())["identity"]["stage"] == "FORECAST" and json.loads(path.read_text())["accepted"])
        prediction, paths = result["output"]["prediction"], result["output"]["paths"]

        def refresh() -> None:
            prediction["prediction_id"] = event_contract.prediction_id_for(prediction)
            prediction["prediction_fingerprint"] = event_contract._fingerprint(prediction, "prediction_fingerprint", ("run_id", "forecast_created_ts", "prompt_tokens", "completion_tokens", "latency_ms", "status", "error_message"))
            for path in paths:
                path["prediction_id"] = prediction["prediction_id"]
                path["path_id"] = event_contract.path_id_for(path)
                path["stage_fingerprint"] = event_contract._fingerprint(path, "stage_fingerprint", ("run_id", "created_ts", "status", "error_message"))

        prediction["expected_initial_direction"] = "DOWN"
        for path in paths:
            path["expected_direction"] = "DOWN"; path["expected_pips_min"] = 5; path["expected_pips_max"] = 15
        refresh()
        event_contract.validate_prediction_path_transaction(prediction, paths)
        paths[0]["expected_pips_min"] = -5
        refresh()
        with self.assertRaisesRegex(event_contract.ContractValidationError, "PATH_PIPS_MIN"):
            event_contract.validate_prediction_path_transaction(prediction, paths)
        paths[0]["expected_pips_min"] = 0; paths[0]["expected_pips_max"] = 0; paths[0]["expected_direction"] = "FLAT"
        refresh()
        event_contract.validate_prediction_path_transaction(prediction, paths)
        paths[0]["expected_pips_min"] = 15; paths[0]["expected_pips_max"] = 5
        refresh()
        with self.assertRaisesRegex(event_contract.ContractValidationError, "PATH_PIP_RANGE"):
            event_contract.validate_prediction_path_transaction(prediction, paths)
        shutil.rmtree(loop.run, ignore_errors=True)

    def test_runner_rejects_r3_manifest_and_keeps_validator_unchanged(self):
        loop = runner.ExecutionLoop("TEST-R3-R7-CONTRACT", dispatcher=lambda _: {"status": "ok"}, manifest_path=self.manifest)
        shutil.rmtree(loop.run, ignore_errors=True)
        self.assertEqual(loop.gate["contract"]["validator_fingerprint"], compat.spec()["validator_fingerprint"])
        with self.assertRaisesRegex(runner.DispatchError, "PREVIOUS_CONTRACT_REJECTED"):
            runner.ExecutionLoop("TEST-R3-R9-R4", dispatcher=lambda _: {"status": "ok"}, manifest_path=r9.R8 / "verification_manifest.json")


if __name__ == "__main__":
    unittest.main()
