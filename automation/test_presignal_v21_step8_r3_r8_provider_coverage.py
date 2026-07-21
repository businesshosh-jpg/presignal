import json
import unittest

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat
from automation import repair_presignal_v21_step8_r3_r8_provider_coverage_v1 as r8


class R8ProviderCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = r8.prepare()

    def test_anthropic_runtime_identity_owns_exact_workflow_labels(self):
        for emitted in (None, "presignal_v2", "presignal_v2_shadow_research", "Anthropic"):
            raw = {"object": "session_attention_map", "session_id": "S", "provider": emitted, "attention_items": [], "status": "ok"}
            parsed = binding.attention_parser("Anthropic", json.dumps(raw), compat.spec())
            self.assertEqual(parsed["provider"], "Anthropic")
            self.assertEqual(parsed["_provider_identity_normalization"]["model_emitted_provider_identity"], emitted)
        with self.assertRaisesRegex(binding.BindingError, "IDENTITY_CONTRADICTION"):
            binding.attention_parser("Anthropic", json.dumps({"object": "session_attention_map", "session_id": "S", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "attention_items": [], "status": "ok"}), compat.spec())

    def test_housing_category_is_the_one_exact_new_alias(self):
        normalized, provenance = binding.normalize_request_item({"information_category": "housing_market_trend"}, compat.spec())
        self.assertEqual(normalized["information_category"], "other")
        self.assertEqual(provenance["normalizations"][0]["original_value"], "housing_market_trend")
        for value in ("other", "growth_context", "labor_market_trend"):
            self.assertEqual(binding.normalize_request_item({"information_category": value}, compat.spec())[0]["information_category"], value)
        self.assertIsNone(binding.normalize_request_item({"information_category": "housing_signal"}, compat.spec())[1])

    def test_r4_request_prompt_is_symmetric_and_explicit(self):
        prompt = binding.request_instruction(compat.spec(), "Gemini")
        self.assertIn("housing-market information use information_category=other", prompt)
        self.assertIn("information_category=(treasury_yields", prompt)
        self.assertIn("information_category=unknown", prompt)


if __name__ == "__main__":
    unittest.main()
