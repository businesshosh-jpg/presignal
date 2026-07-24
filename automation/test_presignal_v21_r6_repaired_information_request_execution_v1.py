"""Focused no-dispatch checks for the repaired R6 Information-Request boundary."""
from __future__ import annotations

import copy
import json
import unittest

from automation import run_presignal_v21_r6_repaired_information_request_execution_v1 as repaired
from automation import run_presignal_v21_r6_information_request_execution_v1 as legacy


class RepairedInformationRequestExecutionTests(unittest.TestCase):
    def setUp(self):
        self.episode, self.members, self.attention, self.raw_attention = legacy.load_inputs()
        self.pre = legacy.build_pre_call(episode=self.episode, members=self.members, attention=self.attention, raw_attention=self.raw_attention, at_utc=self.attention["effective_timestamp"])

    def test_authorization_is_reproducible_and_bindings_pass(self):
        manifest = repaired.authorization_manifest(episode=self.episode, attention=self.attention)
        self.assertEqual(repaired.checksum(manifest), repaired.checksum(manifest))
        report = repaired.validate_bindings(episode=self.episode, attention=self.attention, pre=self.pre)
        self.assertTrue(report["prompt_template_checksum_valid"])
        self.assertTrue(report["category_enum_checksum_valid"])

    def test_exact_categories_accept_and_invalid_categories_reject(self):
        for category in ("event_consensus_detail", "growth_context", "risk_sentiment", "other"):
            accepted, _ = __import__("automation.run_presignal_v21_information_request_prompt_schema_alignment_v1", fromlist=["validate_fixture"]).validate_fixture(category=category)
            self.assertTrue(accepted)
        for category in ("Economic Indicator", "macro_data", "", "growth_context,risk_sentiment"):
            accepted, _ = __import__("automation.run_presignal_v21_information_request_prompt_schema_alignment_v1", fromlist=["validate_fixture"]).validate_fixture(category=category)
            self.assertFalse(accepted)

    def test_wrong_identity_and_empty_response_fail_closed(self):
        raw = {"object": "session_information_requirements", "session_id": "wrong", "provider": "Gemini", "status": "ok", "information_items": []}
        with self.assertRaisesRegex(Exception, "EPISODE"):
            repaired.normalize_and_validate(episode=self.episode, attention=self.attention, raw_response=raw, transport={"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"})
        invalid_attention = copy.deepcopy(self.attention); invalid_attention["selection_state"] = "NOT_SELECTED"
        with self.assertRaisesRegex(Exception, "SELECTED_ATTENTION_STATE"):
            repaired.normalize_and_validate(episode=self.episode, attention=invalid_attention, raw_response={**raw, "session_id": self.episode["episode_id"], "information_items": [{"requested_information": "x", "information_category": "other"}]}, transport={"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"})

    def test_no_external_access_is_recorded(self):
        self.assertTrue(all(value == 0 for value in repaired.audit().values()))


if __name__ == "__main__":
    unittest.main()
