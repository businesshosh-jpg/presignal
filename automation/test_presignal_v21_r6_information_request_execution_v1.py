"""Focused offline validation for the one-call R6 Information-Request runner."""
from __future__ import annotations

from copy import deepcopy
import unittest

from automation import run_presignal_v21_r6_information_request_execution_v1 as runner


def valid_raw(episode_id: str) -> dict:
    return {"object": "session_information_requirements", "session_id": episode_id, "provider": "Gemini", "status": "ok", "information_items": [
        {"request_rank": 2, "requested_information": "Current DXY state", "information_category": "dxy", "priority": "must_have", "reason": "USD context", "affected_channel": "usd_direction", "event_family_relevance": "PMI", "linked_event_ids": [], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "yes", "suggested_source": "authorized source", "expected_forecast_use": "context", "is_market_state_candidate": True},
        {"request_rank": 1, "requested_information": "US two-year yield state", "information_category": "treasury_yields", "priority": "must_have", "reason": "rates context", "affected_channel": "treasury_yields", "event_family_relevance": "PMI", "linked_event_ids": [], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "yes", "suggested_source": "authorized source", "expected_forecast_use": "context", "is_market_state_candidate": True},
        {"request_rank": 3, "requested_information": "Current DXY state", "information_category": "dxy", "priority": "must_have", "reason": "duplicate", "affected_channel": "usd_direction", "event_family_relevance": "PMI", "linked_event_ids": [], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "yes", "suggested_source": "authorized source", "expected_forecast_use": "context", "is_market_state_candidate": True},
    ]}


class InformationRequestExecutionTests(unittest.TestCase):
    def setUp(self):
        self.episode, self.members, self.attention, self.raw_attention = runner.load_inputs()
        self.transport = {"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"}

    def test_authorization_and_pre_call_are_deterministic(self):
        manifest = runner.request_authorization_manifest(episode=self.episode, attention=self.attention)
        self.assertEqual(manifest["information_request_call_budget"], 1)
        self.assertEqual(manifest["retry_count"], 0)
        pre = runner.build_pre_call(episode=self.episode, members=self.members, attention=self.attention, raw_attention=self.raw_attention, at_utc="2026-07-23T17:35:00Z")
        self.assertEqual(pre["bridge_request"]["provider"], "Gemini")
        self.assertEqual(pre["bridge_request"]["model"], "gemini-2.5-flash-lite")

    def test_valid_response_is_deduplicated_and_deterministic(self):
        raw = valid_raw(self.episode["episode_id"])
        rows, report = runner.validate_and_compute(episode=self.episode, attention=self.attention, raw_response=raw, transport=self.transport)
        second, second_report = runner.validate_and_compute(episode=self.episode, attention=self.attention, raw_response=raw, transport=self.transport)
        self.assertEqual(len(rows), 2); self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["request_set_checksum"], second_report["request_set_checksum"])
        self.assertEqual([row["request_identity"] for row in rows], [row["request_identity"] for row in second])

    def test_invalid_response_variants_fail_closed(self):
        raw = valid_raw(self.episode["episode_id"])
        variants = [
            ({**raw, "information_items": []}, "REQUEST_RESPONSE_EMPTY"),
            ({**raw, "provider": "macro-research-model"}, "REQUEST_RESPONSE_PROVIDER_MISMATCH"),
            ({**raw, "session_id": "wrong"}, "REQUEST_RESPONSE_EPISODE_MISMATCH"),
            ({**raw, "information_items": [{**raw["information_items"][0], "information_category": "not-a-category"}]}, "REQUEST_CATEGORY_INVALID"),
        ]
        for value, expected in variants:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(runner.InformationRequestExecutionError, expected):
                    runner.validate_and_compute(episode=self.episode, attention=self.attention, raw_response=value, transport=self.transport)
        with self.assertRaisesRegex(runner.InformationRequestExecutionError, "REQUEST_TRANSPORT_PROVIDER_MODEL_MISMATCH"):
            runner.validate_and_compute(episode=self.episode, attention=self.attention, raw_response=raw, transport={"actual_provider": "Other", "actual_model": "m"})


if __name__ == "__main__":
    unittest.main()
