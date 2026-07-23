"""Focused offline checks for the exact Gemini bridge-role normalization."""
from __future__ import annotations

import copy
import unittest

from automation import presignal_v21_native_attention_call_v1 as call


EPISODE = {"episode_identity": "EP_TEST", "primary_event_identity": "EV_1", "forecast_cutoff": "2030-01-01T12:00:00Z"}
RAW = {"object": "session_attention_map", "session_id": "EP_TEST", "provider": "macro-research-model", "status": "ok", "attention_items": [{"event_id": "EV_1", "attention_label": "PRIMARY_DRIVER", "attention_reason": "fixture"}]}


class BridgeIdentityRepairTests(unittest.TestCase):
    def mapped(self, **changes):
        args = {"raw_response": RAW, "transport_provider": "Gemini", "transport_model": "gemini-2.5-flash-lite", "prompt_template_checksum": call.TRUSTED_GEMINI_PROMPT_TEMPLATE_CHECKSUM, "bridge_source_checksum": call.TRUSTED_GEMINI_BRIDGE_SOURCE_CHECKSUM}
        args.update(changes)
        return call.normalize_trusted_gemini_bridge_identity(**args)

    def test_exact_mapping_preserves_raw_role(self):
        before = copy.deepcopy(RAW); result = self.mapped()
        self.assertEqual(RAW, before); self.assertEqual(result["canonical_payload"]["provider"], "Gemini")
        self.assertEqual(result["payload_provider_role"], "macro-research-model")

    def test_wrong_transport_provider_or_model_fails_closed(self):
        with self.assertRaisesRegex(call.NativeAttentionCallError, "TRANSPORT_PROVIDER"):
            self.mapped(transport_provider="OpenAI")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "TRANSPORT_MODEL"):
            self.mapped(transport_model="other")

    def test_wrong_prompt_bridge_or_payload_role_fails_closed(self):
        with self.assertRaisesRegex(call.NativeAttentionCallError, "PROMPT_VERSION"):
            self.mapped(prompt_template_checksum="sha256:wrong")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "SOURCE_VERSION"):
            self.mapped(bridge_source_checksum="sha256:wrong")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "PAYLOAD_ROLE"):
            self.mapped(raw_response={**RAW, "provider": "other"})

    def test_full_revalidation_is_deterministic(self):
        values = [call.normalize_preserved_gemini_attention_response(episode=EPISODE, raw_response=RAW, effective_timestamp="2030-01-01T11:00:00Z", member_event_ids=["EV_1"], prompt_template_checksum=call.TRUSTED_GEMINI_PROMPT_TEMPLATE_CHECKSUM, bridge_source_checksum=call.TRUSTED_GEMINI_BRIDGE_SOURCE_CHECKSUM, preserved_raw_response_checksum="sha256:preserved") for _ in range(3)]
        self.assertEqual({call.checksum(value) for value in values}, {call.checksum(values[0])})
        self.assertEqual(values[0]["selection_state"], "SELECTED_FOR_INFORMATION_REQUESTS")
        self.assertEqual(values[0]["raw_response_checksum"], "sha256:preserved")


if __name__ == "__main__": unittest.main()
