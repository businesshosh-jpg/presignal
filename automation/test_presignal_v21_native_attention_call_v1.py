"""Focused offline tests for the one-call R6 native Attention boundary."""
from __future__ import annotations

import unittest
import inspect

from automation import presignal_v21_native_attention_call_v1 as call
from automation import run_presignal_v21_native_attention_call_v1 as reports


EPISODE = {"episode_identity": "EP_EVENT_TEST", "primary_event_identity": "EV_TEST", "release_ts": "2030-01-01T12:05:00Z", "forecast_cutoff": "2030-01-01T12:00:00Z", "schema_version": "2.1.0", "market_session_context": "STANDALONE_EVENT", "status": "ELIGIBLE", "event_name": "Fixture Event"}


class NativeAttentionCallTests(unittest.TestCase):
    def test_authorization_is_exact_and_reproducible(self):
        auth = call.authorization_manifest()
        self.assertEqual(auth["attention_scope"], {"provider": "Gemini", "model": "gemini-2.5-flash-lite", "call_budget": 1, "retry_count": 0, "prompt_version": call.PROMPT_VERSION, "response_schema_version": call.RESPONSE_SCHEMA_VERSION})
        self.assertEqual(call.checksum(auth), call.checksum(call.authorization_manifest()))
        self.assertEqual(auth["prohibitions"]["forecast_calls"], 0)
        self.assertEqual(auth["prohibitions"]["acquisition_calls"], 0)
        self.assertEqual(auth["prohibitions"]["google_scientific_writes"], 0)

    def test_candidate_selection_is_fail_closed(self):
        no_candidate = call.select_single_eligible_episode([], as_of_utc="2030-01-01T11:00:00Z")
        self.assertEqual(no_candidate["decision"], "R6_NATIVE_ATTENTION_NO_ELIGIBLE_EPISODE")
        ambiguous = call.select_single_eligible_episode([EPISODE, {**EPISODE, "episode_identity": "EP_EVENT_OTHER", "primary_event_identity": "EV_OTHER"}], as_of_utc="2030-01-01T11:00:00Z")
        self.assertEqual(ambiguous["decision"], "R6_NATIVE_ATTENTION_EPISODE_SELECTION_AMBIGUOUS")
        chosen = call.select_single_eligible_episode([EPISODE], as_of_utc="2030-01-01T11:00:00Z")
        self.assertEqual(chosen["selected_episode"]["episode_identity"], "EP_EVENT_TEST")

    def test_attention_response_validation_and_selection_mapping(self):
        raw = {"object": "session_attention_map", "session_id": "EP_EVENT_TEST", "provider": "Gemini", "status": "ok", "attention_items": [{"event_id": "EV_TEST", "attention_label": "PRIMARY_DRIVER", "attention_reason": "high impact"}]}
        selected = call.normalize_attention_response(episode=EPISODE, raw_response=raw, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="gemini-2.5-flash-lite")
        self.assertEqual(selected["selection_state"], "SELECTED_FOR_INFORMATION_REQUESTS")
        not_selected = call.normalize_attention_response(episode=EPISODE, raw_response={**raw, "attention_items": [{"event_id": "EV_TEST", "attention_label": "WATCHLIST", "attention_reason": "context"}]}, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="gemini-2.5-flash-lite")
        self.assertEqual(not_selected["selection_state"], "NOT_SELECTED")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "MODEL_MISMATCH"):
            call.normalize_attention_response(episode=EPISODE, raw_response=raw, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="other")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "STATE_INVALID"):
            call.normalize_attention_response(episode=EPISODE, raw_response={**raw, "attention_items": [{"event_id": "EV_TEST", "attention_label": "WATCH", "attention_reason": "bad"}]}, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="gemini-2.5-flash-lite")
        with self.assertRaisesRegex(call.NativeAttentionCallError, "PROVIDER_FIELD_MISMATCH"):
            call.normalize_attention_response(episode=EPISODE, raw_response={**raw, "provider": "macro-research-model"}, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="gemini-2.5-flash-lite")

    def test_identical_duplicate_member_references_collapse_before_lineage_validation(self):
        raw = {"object": "session_attention_map", "session_id": "EP_EVENT_TEST", "provider": "Gemini", "status": "ok", "attention_items": [{"event_id": "EV_TEST", "attention_label": "PRIMARY_DRIVER", "attention_reason": "fixture"}]}
        result = call.normalize_attention_response(episode=EPISODE, raw_response={**raw, "attention_items": raw["attention_items"] * 2}, effective_timestamp="2030-01-01T11:00:00Z", returned_provider="Gemini", returned_model="gemini-2.5-flash-lite", member_event_ids=["EV_TEST"])
        self.assertEqual(result["selection_state"], "SELECTED_FOR_INFORMATION_REQUESTS")

    def test_injected_runner_dispatches_once_without_retry(self):
        calls = []
        def dispatcher(request):
            calls.append(request)
            return {"status": "ok", "actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite", "completed_timestamp": "2030-01-01T11:00:00Z", "raw_output": {"object": "session_attention_map", "session_id": "EP_EVENT_TEST", "provider": "Gemini", "status": "ok", "attention_items": [{"event_id": "EV_TEST", "attention_label": "PRIMARY_DRIVER", "attention_reason": "fixture"}]}}
        result = call.execute_one_attention(episode=EPISODE, effective_timestamp="2030-01-01T11:00:00Z", collection_run_id="R6_TEST", dispatcher=dispatcher)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["provider_calls"], 1)
        self.assertEqual(result["retry_count"], 0)

    def test_malformed_response_stops_after_the_single_dispatch(self):
        calls = []
        def dispatcher(request):
            calls.append(request)
            return {"status": "ok", "raw_output": "not json"}
        with self.assertRaisesRegex(call.NativeAttentionCallError, "RAW_RESPONSE_INVALID"):
            call.execute_one_attention(episode=EPISODE, effective_timestamp="2030-01-01T11:00:00Z", collection_run_id="R6_TEST", dispatcher=dispatcher)
        self.assertEqual(len(calls), 1)

    def test_prompt_and_pack_a_trace_are_deterministic(self):
        first = call.attention_call_input(episode=EPISODE, effective_timestamp="2030-01-01T11:00:00Z", collection_run_id="R6_TEST")
        second = call.attention_call_input(episode=EPISODE, effective_timestamp="2030-01-01T11:00:00Z", collection_run_id="R6_TEST")
        self.assertEqual(first["resolved_prompt_checksum"], second["resolved_prompt_checksum"])
        trace = reports.pack_a_contract_verification()
        self.assertEqual(trace["classification"], "PACK_A_CONTRACT_CONFIRMED")
        self.assertEqual(trace, reports.pack_a_contract_verification())
        self.assertFalse(trace["scientific_mismatch_found"])

    def test_blocked_reports_are_isolated(self):
        reports_map = reports.blocked_reports(candidate_read={"spreadsheet_id": "id", "range": "Event!A1:V60", "read_timestamp_utc": "2030-01-01T11:00:00Z", "candidate_count": 1, "eligible_count": 0, "candidates": [], "token_checksum_before": "a", "token_checksum_after": "a"})
        self.assertEqual(reports_map["final_native_attention_decision.json"]["decision"], "R6_NATIVE_ATTENTION_NO_ELIGIBLE_EPISODE")
        self.assertEqual(reports_map["external_access_audit.json"]["gemini_attention_calls"], 0)
        self.assertEqual(reports_map["external_access_audit.json"]["google_scientific_writes"], 0)
        source = inspect.getsource(call)
        self.assertNotIn("google_clients", source)
        self.assertNotIn("requests.post", source)


if __name__ == "__main__":
    unittest.main()
