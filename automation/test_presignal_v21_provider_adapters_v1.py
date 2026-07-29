import unittest
from pathlib import Path
import json

from automation import presignal_v21_provider_adapters_v1 as adapters
from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat_r4
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


ROOT = Path(__file__).resolve().parents[1]
TARGETED_VALIDATION_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-TARGETED-PROVIDER-VALIDATION-20260726T133327Z-5ed8eeda82cc"
)
EXPANDED_VALIDATION_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_pure_prediction_historical_baseline"
    / "PPHB-R1-EXPANDED-VALIDATION-20260726T123833Z-c6afc7952cca"
)


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

    def test_historical_attention_provider_authority_binding_uses_manifest_and_transport(self):
        raw = {
            "object": "session_attention_map",
            "session_id": "S",
            "provider": "macro_model",
            "attention_items": [],
            "session_attention_summary": "x",
            "status": "ok",
        }
        result = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="OpenAI",
            requested_model="gpt-4o-mini-2024-07-18",
            transport_result={
                "status": "ok",
                "actual_provider": "OpenAI",
                "actual_model": "gpt-4o-mini-2024-07-18",
                "raw_output": raw,
            },
            authoritative_attention_provider_binding=True,
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(result["canonical_payload"]["provider"], "OpenAI")
        self.assertEqual(result["canonical_payload"]["_raw_claimed_provider"], "macro_model")
        self.assertEqual(
            result["canonical_payload"]["_provider_identity_normalization"]["normalization_type"],
            "attention_provider_authority_binding",
        )

    def test_historical_attention_provider_authority_binding_fails_closed_on_conflict(self):
        raw = {
            "object": "session_attention_map",
            "session_id": "S",
            "provider": "macro_research",
            "attention_items": [],
            "session_attention_summary": "x",
            "status": "ok",
        }
        result = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="OpenAI",
            requested_model="gpt-4o-mini-2024-07-18",
            transport_result={
                "status": "ok",
                "actual_provider": "Gemini",
                "actual_model": "gemini-2.5-flash-lite",
                "raw_output": raw,
            },
            authoritative_attention_provider_binding=True,
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSE_FAILED)
        self.assertEqual(result["normalization_notes"][-1]["reason"], "ATTENTION_PROVIDER_AUTHORITY_CONFLICT")

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

    def test_prospective_forecast_validation_stays_outside_adapter_semantics(self):
        result = adapters.normalize_prospective_forecast_response(
            requested_provider="Gemini", requested_model="m",
            transport_result={"raw_output": {"forecast": {"direction": "UP"}, "response_contract": {}}},
            scientific_validator=lambda payload: payload.get("direction") == "UP",
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(result["validation_status"], adapters.ValidationStatus.VALID)
        invalid = adapters.normalize_prospective_forecast_response(
            requested_provider="Anthropic", requested_model="m", transport_result={"raw_output": {"direction": "SIDEWAYS"}},
            scientific_validator=lambda _: False,
        )
        self.assertEqual(invalid["validation_status"], adapters.ValidationStatus.INVALID)

    def test_nested_apps_script_transport_result_unwraps_for_anthropic(self):
        raw = json.loads(
            (
                TARGETED_VALIDATION_ROOT
                / "raw_provider_responses"
                / "02_EP_EVENT_f2862037fd8c6ab5315a_Anthropic_PACK_E.json"
            ).read_text()
        )["transport_result"]
        result = adapters.normalize_prospective_forecast_response(
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=raw,
            scientific_validator=lambda payload: bool(step6.normalize_provider_output(payload)),
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(result["validation_status"], adapters.ValidationStatus.VALID)
        self.assertEqual(result["actual_provider"], "Anthropic")
        self.assertEqual(result["actual_model"], "claude-haiku-4-5")

    def test_nested_apps_script_transport_result_unwraps_for_gemini_and_openai(self):
        fixtures = [
            (
                "Gemini",
                "gemini-2.5-flash-lite",
                EXPANDED_VALIDATION_ROOT / "raw_provider_responses" / "03_EP_EVENT_2d777c70a07c631e5f03_Gemini_PACK_A.json",
            ),
            (
                "OpenAI",
                "gpt-4o-mini-2024-07-18",
                EXPANDED_VALIDATION_ROOT / "raw_provider_responses" / "09_EP_BATCH_80bbf91b9afbc592880f_OpenAI_PACK_A.json",
            ),
        ]
        for provider, model, path in fixtures:
            with self.subTest(provider=provider):
                raw = json.loads(path.read_text())["transport_result"]
                result = adapters.normalize_prospective_forecast_response(
                    requested_provider=provider,
                    requested_model=model,
                    transport_result=raw,
                    scientific_validator=lambda payload: bool(step6.normalize_provider_output(payload)),
                )
                self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
                self.assertEqual(result["validation_status"], adapters.ValidationStatus.VALID)
                self.assertEqual(result["actual_provider"], provider)
                self.assertEqual(result["actual_model"], model)

    def test_scientific_fields_still_fail_closed_after_wrapper_unwrap(self):
        transport = {
            "result": {
                "actual_provider": "Anthropic",
                "actual_model": "claude-haiku-4-5",
                "raw_output": {"confidence": 0.5},
            }
        }
        result = adapters.normalize_prospective_forecast_response(
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result=transport,
            scientific_validator=lambda payload: bool(step6.normalize_provider_output(payload)),
        )
        self.assertEqual(result["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(result["validation_status"], adapters.ValidationStatus.INVALID)


if __name__ == "__main__":
    unittest.main()
