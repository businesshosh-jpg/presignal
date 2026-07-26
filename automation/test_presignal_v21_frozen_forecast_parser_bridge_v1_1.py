import hashlib
import unittest
from pathlib import Path

from automation import presignal_v21_frozen_forecast_parser_bridge_v1 as bridge
from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import run_presignal_v21_single_event_path_pair_v1_1 as frozen
from automation.test_run_presignal_v21_single_event_path_pair_v1_1 import response


PARSER = Path(frozen.__file__)
PARSER_SHA256 = "991ab91033f13f2586860a5ae75155b882f2d1e32af2d9dbddba2d5a57a9f2f7"


class FrozenForecastParserBridgeTests(unittest.TestCase):
    def adapt(self, parsed=None, error=None):
        return bridge.adapt_frozen_forecast_parse_result(
            requested_provider="Gemini", requested_model="requested",
            actual_provider="Gemini", actual_model="returned", raw_response="raw",
            frozen_parse_result=parsed, frozen_parse_error=error, provider_metadata={"latency_ms": 1},
        )

    def test_parser_source_and_manifest_binding_remain_valid(self):
        self.assertEqual(hashlib.sha256(PARSER.read_bytes()).hexdigest(), PARSER_SHA256)

    def test_directional_and_no_signal_payloads_are_preserved(self):
        directional = frozen.parse_provider_output(response())
        no_signal = dict(response(), no_signal_flag=True, immediate_impulse_direction=None, immediate_impulse_peak_pips_min=None, immediate_impulse_peak_pips_max=None, immediate_impulse_confidence=None, immediate_impulse_window_seconds=None, early_reaction_5m_direction="UNCERTAIN", path=[])
        no_signal = frozen.parse_provider_output(no_signal)
        for payload in (directional, no_signal):
            result = self.adapt(payload)
            self.assertIs(result["canonical_payload"], payload)
            self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
            self.assertEqual(result["validation_status"], adapters.ValidationStatus.VALID)
            self.assertEqual(result["actual_model"], "returned")

    def test_frozen_rejection_is_invalid_without_reparse(self):
        rejected = self.adapt(error=ValueError("PROVIDER_OUTPUT_PATH_COUNT"))
        self.assertEqual(rejected["parse_status"], adapters.ParseStatus.PARSE_FAILED)
        self.assertEqual(rejected["validation_status"], adapters.ValidationStatus.INVALID)
        self.assertIsNone(rejected["canonical_payload"])


if __name__ == "__main__":
    unittest.main()
