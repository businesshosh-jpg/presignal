from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_001 as batch001
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation import execute_presignal_v21_attention_batch_004 as batch004
from automation.google_clients import GoogleCredentialError
from automation.test_execute_presignal_v21_attention_batch_001 import CountingDispatcher, valid_dispatcher


def fake_source_sessions_batch_004():
    calls = batch004.load_batch_calls()
    session_by_id = {}
    members_by_session = {}
    for call in calls:
        session_id = call["source_session_id"]
        if session_id in session_by_id:
            continue
        session_date = call["session_date"]
        session_by_id[session_id] = {
            "session_id": session_id,
            "country": "US",
            "session_window_name": "CUSTOM_CONFIG_WINDOW",
            "session_start_ts": session_date + "T00:00:00Z",
            "session_end_ts": session_date + "T23:59:00Z",
            "forecast_cutoff": session_date + "T00:00:00Z",
        }
        members_by_session[session_id] = [
            {
                "event_id": "EVT1_" + session_id.replace("|", "_"),
                "batch_id": "",
                "type": "EVENT",
                "indicator_name": "Fixture 1 " + session_date,
                "genre": "Macro",
                "importance": "High",
                "release_ts": session_date + "T12:00:00Z",
                "consensus_value": "",
                "prev_revision": "",
                "member_order": 1,
            },
            {
                "event_id": "EVT2_" + session_id.replace("|", "_"),
                "batch_id": "",
                "type": "EVENT",
                "indicator_name": "Fixture 2 " + session_date,
                "genre": "Macro",
                "importance": "Medium",
                "release_ts": session_date + "T12:05:00Z",
                "consensus_value": "",
                "prev_revision": "",
                "member_order": 2,
            },
        ]
    return session_by_id, members_by_session


class CompletenessDispatcher(CountingDispatcher):
    def __call__(self, request):
        payload = json.loads(request["prompt"]["user"])
        events = payload["events"]
        raw = {
            "object": "session_attention_map",
            "session_id": request["session_id"],
            "provider": request["provider"],
            "status": "ok",
            "attention_items": [
                {
                    "event_id": row["event_id"],
                    "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST",
                    "attention_rank": index + 1,
                    "attention_reason": "fixture",
                    "expected_market_channel": "treasury_yields",
                    "driver_role": "primary" if index == 0 else "watch",
                    "confidence": 0.7,
                }
                for index, row in enumerate(events)
            ],
        }
        emitted = "```json\n" + json.dumps(raw) + "\n```" if request["provider"] == "Anthropic" else json.dumps(raw)
        self.calls.append({"provider": request["provider"], "model": request["model"], "session_id": request["session_id"]})
        return {
            "status": "ok",
            "actual_provider": request["provider"],
            "actual_model": request["model"],
            "raw_output": emitted,
            "completed_timestamp": "2026-07-29T06:00:00Z",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "latency_ms": 1234,
        }


class IncompleteDispatcher(CountingDispatcher):
    def __call__(self, request):
        payload = json.loads(request["prompt"]["user"])
        events = payload["events"][:-1]
        raw = {
            "object": "session_attention_map",
            "session_id": request["session_id"],
            "provider": request["provider"],
            "status": "ok",
            "attention_items": [
                {
                    "event_id": row["event_id"],
                    "attention_label": "PRIMARY_DRIVER" if index == 0 else "WATCHLIST",
                    "attention_rank": index + 1,
                    "attention_reason": "fixture",
                    "expected_market_channel": "treasury_yields",
                    "driver_role": "primary" if index == 0 else "watch",
                    "confidence": 0.7,
                }
                for index, row in enumerate(events)
            ],
        }
        self.calls.append({"provider": request["provider"], "model": request["model"], "session_id": request["session_id"]})
        return {
            "status": "ok",
            "actual_provider": request["provider"],
            "actual_model": request["model"],
            "raw_output": json.dumps(raw),
            "completed_timestamp": "2026-07-29T06:00:00Z",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "latency_ms": 1234,
        }


class DuplicateDispatcher(CountingDispatcher):
    def __call__(self, request):
        payload = json.loads(request["prompt"]["user"])
        event = payload["events"][0]
        raw = {
            "object": "session_attention_map",
            "session_id": request["session_id"],
            "provider": request["provider"],
            "status": "ok",
            "attention_items": [
                {
                    "event_id": event["event_id"],
                    "attention_label": "PRIMARY_DRIVER",
                    "attention_rank": 1,
                    "attention_reason": "fixture",
                    "expected_market_channel": "treasury_yields",
                    "driver_role": "primary",
                    "confidence": 0.7,
                },
                {
                    "event_id": event["event_id"],
                    "attention_label": "WATCHLIST",
                    "attention_rank": 2,
                    "attention_reason": "fixture",
                    "expected_market_channel": "treasury_yields",
                    "driver_role": "watch",
                    "confidence": 0.7,
                },
            ],
        }
        self.calls.append({"provider": request["provider"], "model": request["model"], "session_id": request["session_id"]})
        return {
            "status": "ok",
            "actual_provider": request["provider"],
            "actual_model": request["model"],
            "raw_output": json.dumps(raw),
            "completed_timestamp": "2026-07-29T06:00:00Z",
        }


class AuthorityConflictDispatcher(CountingDispatcher):
    def __call__(self, request):
        response = valid_dispatcher(request)
        response["actual_provider"] = "OpenAI" if request["provider"] == "Gemini" else request["provider"]
        self.calls.append({"provider": request["provider"], "model": request["model"], "session_id": request["session_id"]})
        return response


class ExecuteAttentionBatch004Test(unittest.TestCase):
    def test_only_batch_004_calls_are_loaded(self) -> None:
        calls = batch004.load_batch_calls()
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({row["call_id"] for row in calls}), 12)
        prior = (
            {row["call_id"] for row in batch001.load_batch_calls()}
            | {row["call_id"] for row in batch002.load_batch_calls()}
            | {row["call_id"] for row in batch003.load_batch_calls()}
        )
        self.assertFalse(prior & {row["call_id"] for row in calls})

    def test_provider_model_assignments_remain_frozen(self) -> None:
        calls = batch004.load_batch_calls()
        self.assertEqual({row["provider"] for row in calls}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(all(row["model"] == batch004.base.PROVIDER_MODELS[row["provider"]] for row in calls))

    def test_manifest_transport_agreement_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = AuthorityConflictDispatcher()
            result = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(result["reconciliation"]["failed_provider_authority_calls"], 4)

    def test_expected_and_returned_event_sets_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = IncompleteDispatcher()
            result = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(result["reconciliation"]["completeness_failed_calls"], 12)
            rows = batch004.read_jsonl(result["run_dir"] / "event_completeness_results.jsonl")
            self.assertTrue(all(row["missing_event_ids"] for row in rows))

    def test_duplicate_and_unexpected_ids_fail_completeness(self) -> None:
        checked = batch004.base.load_runtime_contract()
        call = {
            "call_id": "C",
            "provider": "OpenAI",
            "model": "gpt-4o-mini-2024-07-18",
        }
        transport = {"actual_provider": "OpenAI", "actual_model": "gpt-4o-mini-2024-07-18"}
        raw = json.dumps({
            "object": "session_attention_map",
            "session_id": "S",
            "provider": "OpenAI",
            "status": "ok",
            "attention_items": [
                {"event_id": "E1", "attention_label": "WATCHLIST", "attention_rank": 1, "attention_reason": "x", "expected_market_channel": "unknown", "driver_role": "watch", "confidence": 0.5},
                {"event_id": "E1", "attention_label": "WATCHLIST", "attention_rank": 2, "attention_reason": "x", "expected_market_channel": "unknown", "driver_role": "watch", "confidence": 0.5},
                {"event_id": "E3", "attention_label": "WATCHLIST", "attention_rank": 3, "attention_reason": "x", "expected_market_channel": "unknown", "driver_role": "watch", "confidence": 0.5},
            ],
            "session_attention_summary": "x",
        })
        completeness, _ = batch004.determine_event_completeness(
            raw_output=raw,
            call=call,
            contract=checked,
            expected_event_ids=["E1", "E2"],
            transport=transport,
        )
        self.assertEqual(completeness["duplicate_event_ids"], ["E1"])
        self.assertEqual(completeness["missing_event_ids"], ["E2"])
        self.assertEqual(completeness["unexpected_event_ids"], ["E3"])

    def test_raw_output_preserved_and_successful_calls_cannot_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            first = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            raw = batch004.read_jsonl(first["run_dir"] / "raw_provider_outputs.jsonl")
            self.assertEqual(len(raw), 12)
            second = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                resume_run_dir=first["run_dir"],
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            self.assertEqual(second["reconciliation"]["skipped_already_successful_calls"], 12)

    def test_only_complete_validated_results_enter_normalized_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            result = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            normalized = batch004.read_jsonl(result["run_dir"] / "normalized_attention_results.jsonl")
            self.assertEqual(len(normalized), 12)
            self.assertEqual(result["reconciliation"]["successful_valid_calls"], 12)

    def test_blocked_preflight_fails_closed_before_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch004, "preflight_credentials", side_effect=GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing token")):
                result = batch004.execute_batch(output_root=Path(tmp), fixed_timestamp="2026-07-29T06:00:00Z", enforce_head=False)
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_004_BLOCKED")
            self.assertEqual(result["reconciliation"]["attempted_calls"], 0)

    def test_no_pack_no_forecast_no_batch_005_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            result = batch004.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T06:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            manifest = batch004.base.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(result["decision"]["scaling_decision"], "READY_FOR_ATTENTION_BATCH_005")


if __name__ == "__main__":
    unittest.main()
