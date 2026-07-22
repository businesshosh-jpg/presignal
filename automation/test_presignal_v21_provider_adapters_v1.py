import unittest

from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat_r4


class ProviderAdapterTests(unittest.TestCase):
    def normalize(self, provider, raw, stage="FORECAST", **extra):
        return adapters.normalize_provider_response(
            stage=stage, requested_provider=provider, requested_model="requested",
            transport_result={"status": "ok", "actual_provider": provider, "actual_model": "returned", "raw_output": raw}, **extra,
        )

    def test_anthropic_fenced_attention_identity_normalization(self):
        rule = compat_r4.NORMALIZATION["anthropic_runtime_identity"]
        raw = {"provider": rule["accepted_emitted_provider_identities"][0], "model": rule["accepted_emitted_model_identities"][0]}
        result = self.normalize("Anthropic", "```json\n" + __import__("json").dumps(raw) + "\n```", "ATTENTION", contract_version=compat_r4.CONTRACT_VERSION)
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(result["canonical_payload"]["provider"], rule["runtime_provider"])

    def test_gemini_envelope_and_openai_raw_are_neutral_payloads(self):
        forecast = {"no_signal_flag": True}
        gemini = self.normalize("Gemini", {"forecast": forecast, "response_contract": {"version": "x"}})
        openai = self.normalize("OpenAI", forecast)
        self.assertEqual(gemini["canonical_payload"], forecast)
        self.assertEqual(openai["canonical_payload"], forecast)
        self.assertEqual(gemini["actual_model"], "returned")

    def test_existing_request_aliases_and_unknown_value(self):
        item, provenance = adapters.normalize_information_request_item({"affected_channel": "other", "information_category": "housing_market_trend"}, compat_r4.CONTRACT_VERSION)
        self.assertEqual(item, {"affected_channel": "unknown", "information_category": "other"})
        self.assertEqual(len(provenance["normalizations"]), 2)
        unchanged, provenance = adapters.normalize_information_request_item({"information_category": "housing_signal"}, compat_r4.CONTRACT_VERSION)
        self.assertEqual(unchanged["information_category"], "housing_signal")
        self.assertIsNone(provenance)

    def test_empty_and_malformed_are_parse_failures_not_abstentions(self):
        for raw in ("", "not json"):
            result = self.normalize("OpenAI", raw)
            self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSE_FAILED)
            self.assertIsNone(result["canonical_payload"])

    def test_validation_is_explicit_and_never_evaluation(self):
        invalid = self.normalize("OpenAI", {"bad": True}, validator=lambda value: "no_signal_flag" in value)
        valid_no_signal = self.normalize("OpenAI", {"no_signal_flag": True}, validator=lambda value: "no_signal_flag" in value)
        self.assertEqual(invalid["validation_status"], adapters.ValidationStatus.INVALID)
        self.assertEqual(valid_no_signal["validation_status"], adapters.ValidationStatus.VALID)
        self.assertFalse(any(key in valid_no_signal for key in ("evaluation_state", "correctness", "CORRECT", "INCORRECT")))

    def test_no_response_is_not_attempted(self):
        result = adapters.normalize_provider_response(stage="FORECAST", requested_provider="Gemini", requested_model="m", transport_result={"status": "failed"})
        self.assertEqual(result["parse_status"], adapters.ParseStatus.NOT_ATTEMPTED)


if __name__ == "__main__":
    unittest.main()
