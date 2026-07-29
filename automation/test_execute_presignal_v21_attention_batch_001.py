from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_001 as batch
from automation.google_clients import GoogleCredentialError


def valid_dispatcher(request):
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
    return {
        "status": "ok",
        "actual_provider": request["provider"],
        "actual_model": request["model"],
        "raw_output": emitted,
        "completed_timestamp": "2026-07-29T02:00:00Z",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "latency_ms": 1234,
    }


class CountingDispatcher:
    def __init__(self, failing_provider: str | None = None, malformed_provider: str | None = None):
        self.calls = []
        self.failing_provider = failing_provider
        self.malformed_provider = malformed_provider

    def __call__(self, request):
        self.calls.append({"provider": request["provider"], "model": request["model"], "session_id": request["session_id"]})
        if request["provider"] == self.failing_provider:
            return {"status": "provider_unavailable", "error": "fixture_provider_unavailable", "actual_provider": request["provider"], "actual_model": request["model"], "raw_output": ""}
        if request["provider"] == self.malformed_provider:
            return {"status": "ok", "actual_provider": request["provider"], "actual_model": request["model"], "raw_output": "not json", "completed_timestamp": "2026-07-29T02:00:00Z"}
        return valid_dispatcher(request)


def fake_source_sessions():
    calls = batch.load_batch_calls()
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
                "event_id": "EVT_" + session_id.replace("|", "_"),
                "batch_id": "",
                "type": "EVENT",
                "indicator_name": "Fixture " + session_date,
                "genre": "Macro",
                "importance": "High",
                "release_ts": session_date + "T12:00:00Z",
                "consensus_value": "",
                "prev_revision": "",
                "member_order": 1,
            }
        ]
    return session_by_id, members_by_session


class ExecuteAttentionBatch001Test(unittest.TestCase):
    def test_frozen_batch_contains_exactly_12_unique_calls(self) -> None:
        calls = batch.load_batch_calls()
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({row["call_id"] for row in calls}), 12)
        self.assertEqual([row["execution_order"] for row in calls], list(range(1, 13)))

    def test_provider_model_assignments_are_unchanged(self) -> None:
        calls = batch.load_batch_calls()
        self.assertEqual({row["provider"] for row in calls}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(all(row["model"] == batch.PROVIDER_MODELS[row["provider"]] for row in calls))

    def test_successful_call_cannot_be_repeated_and_failed_call_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher(failing_provider="Gemini")
            first = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            self.assertEqual(len(dispatcher.calls), 12)
            second = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", resume_run_dir=first["run_dir"], source_session_loader=fake_source_sessions)
            self.assertEqual(len(dispatcher.calls), 12)
            recon = second["reconciliation"]
            self.assertEqual(recon["skipped_already_successful_calls"], 8)
            self.assertEqual(recon["failed_provider_calls"], 4)

    def test_raw_and_normalized_outputs_are_stored_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            run_dir = result["run_dir"]
            raw_transport = batch.read_jsonl(run_dir / "raw_transport_results.jsonl")
            raw_output = batch.read_jsonl(run_dir / "raw_provider_outputs.jsonl")
            normalized = batch.read_jsonl(run_dir / "normalized_attention_results.jsonl")
            self.assertEqual(len(raw_transport), 12)
            self.assertEqual(len(raw_output), 12)
            self.assertEqual(len(normalized), 12)
            self.assertTrue(all("validated_attention_rows" in row for row in normalized))

    def test_invalid_results_cannot_enter_normalized_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher(malformed_provider="Anthropic")
            result = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            run_dir = result["run_dir"]
            normalized = batch.read_jsonl(run_dir / "normalized_attention_results.jsonl")
            failures = batch.read_jsonl(run_dir / "failed_call_ledger.jsonl")
            self.assertEqual(len(normalized), 8)
            self.assertEqual(len(failures), 4)
            self.assertTrue(all(row["failure_stage"] == "FAILED_PARSE" for row in failures))

    def test_one_session_provider_result_maps_to_multiple_episodes_without_duplicate_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            rows = batch.read_jsonl(result["run_dir"] / "episode_attention_result_map.jsonl")
            by_call = {}
            for row in rows:
                by_call.setdefault(row["call_id"], 0)
                by_call[row["call_id"]] += 1
            self.assertEqual(max(by_call.values()), 11)
            self.assertEqual(len(dispatcher.calls), 12)

    def test_operation_journals_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            journal_path = result["run_dir"] / "operation_journal.jsonl"
            first_lines = journal_path.read_text().splitlines()
            batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", resume_run_dir=result["run_dir"], source_session_loader=fake_source_sessions)
            second_lines = journal_path.read_text().splitlines()
            self.assertGreater(len(second_lines), len(first_lines))
            self.assertEqual(first_lines, second_lines[: len(first_lines)])

    def test_resume_run_skips_successful_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", source_session_loader=fake_source_sessions)
            journal_before = len((result["run_dir"] / "operation_journal.jsonl").read_text().splitlines())
            batch.execute_batch(output_root=Path(tmp), dispatcher=dispatcher, fixed_timestamp="2026-07-29T02:00:00Z", resume_run_dir=result["run_dir"], source_session_loader=fake_source_sessions)
            journal_after = len((result["run_dir"] / "operation_journal.jsonl").read_text().splitlines())
            self.assertEqual(len(dispatcher.calls), 12)
            self.assertGreater(journal_after, journal_before)

    def test_blocked_preflight_fails_closed_before_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch, "preflight_credentials", side_effect=GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing token")):
                result = batch.execute_batch(output_root=Path(tmp), fixed_timestamp="2026-07-29T02:00:00Z")
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_001_BLOCKED")
            self.assertEqual(result["reconciliation"]["attempted_calls"], 0)
            self.assertEqual(batch.read_jsonl(result["run_dir"] / "normalized_attention_results.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
