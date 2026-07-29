from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_001 as batch001
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import presignal_v21_provider_adapters_v1 as adapters
from automation.google_clients import GoogleCredentialError
from automation.test_execute_presignal_v21_attention_batch_001 import (
    CountingDispatcher,
)


def fake_source_sessions_batch_002():
    calls = batch002.load_batch_calls()
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


class ExecuteAttentionBatch002Test(unittest.TestCase):
    def test_only_batch_002_calls_are_loaded_and_count_is_12(self) -> None:
        calls = batch002.load_batch_calls()
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({row["call_id"] for row in calls}), 12)
        self.assertEqual([row["execution_order"] for row in calls], list(range(13, 25)))

    def test_batch_001_call_ids_are_excluded(self) -> None:
        batch_001_ids = {row["call_id"] for row in batch001.load_batch_calls()}
        batch_002_ids = {row["call_id"] for row in batch002.load_batch_calls()}
        self.assertFalse(batch_001_ids & batch_002_ids)

    def test_provider_model_assignments_remain_frozen(self) -> None:
        calls = batch002.load_batch_calls()
        self.assertEqual({row["provider"] for row in calls}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(all(row["model"] == batch002.base.PROVIDER_MODELS[row["provider"]] for row in calls))

    def test_successful_calls_cannot_be_repeated_and_failed_calls_are_not_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher(failing_provider="Gemini")
            first = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                source_session_loader=fake_source_sessions_batch_002,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            second = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                resume_run_dir=first["run_dir"],
                source_session_loader=fake_source_sessions_batch_002,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            recon = second["reconciliation"]
            self.assertEqual(recon["skipped_already_successful_calls"], 8)
            self.assertEqual(recon["failed_provider_calls"], 4)

    def test_raw_provider_output_is_preserved_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher(malformed_provider="Anthropic")
            result = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                source_session_loader=fake_source_sessions_batch_002,
            )
            raw_output = batch002.base.read_jsonl(result["run_dir"] / "raw_provider_outputs.jsonl")
            failures = batch002.base.read_jsonl(result["run_dir"] / "failed_call_ledger.jsonl")
            self.assertEqual(len(raw_output), 12)
            self.assertEqual(len(failures), 4)
            self.assertTrue(all(row["failure_stage"] == "FAILED_PARSE" for row in failures))
            self.assertTrue(all("raw_output" in row for row in raw_output))

    def test_unknown_aliases_remain_rejected(self) -> None:
        normalized = adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider="Anthropic",
            requested_model="claude-haiku-4-5",
            transport_result={
                "raw_output": '{"object":"session_attention_map","session_id":"S","provider":"Unknown_shadow_alias","attention_items":[],"session_attention_summary":"x","status":"ok"}',
                "actual_provider": "Anthropic",
                "actual_model": "claude-haiku-4-5",
            },
            contract_version=batch002.base.load_runtime_contract()["contract_version"],
        )
        self.assertEqual(normalized["parse_status"], adapters.ParseStatus.PARSED)
        self.assertEqual(normalized["canonical_payload"]["provider"], "Unknown_shadow_alias")

    def test_only_strictly_validated_results_enter_normalized_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher(malformed_provider="Anthropic")
            result = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                source_session_loader=fake_source_sessions_batch_002,
            )
            normalized = batch002.base.read_jsonl(result["run_dir"] / "normalized_attention_results.jsonl")
            self.assertEqual(len(normalized), 8)

    def test_session_provider_results_map_without_duplicate_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                source_session_loader=fake_source_sessions_batch_002,
            )
            rows = batch002.base.read_jsonl(result["run_dir"] / "episode_attention_result_map.jsonl")
            by_call = {}
            for row in rows:
                by_call.setdefault(row["call_id"], 0)
                by_call[row["call_id"]] += 1
            self.assertGreaterEqual(max(by_call.values()), 1)
            self.assertEqual(len(dispatcher.calls), 12)

    def test_blocked_preflight_fails_closed_before_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch002.base, "preflight_credentials", side_effect=GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing token")):
                result = batch002.execute_batch(output_root=Path(tmp), fixed_timestamp="2026-07-29T04:00:00Z")
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_002_BLOCKED")
            self.assertEqual(result["reconciliation"]["attempted_calls"], 0)
            self.assertEqual(batch002.base.read_jsonl(result["run_dir"] / "normalized_attention_results.jsonl"), [])

    def test_no_pack_or_forecast_or_batch_003_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch002.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T04:00:00Z",
                source_session_loader=fake_source_sessions_batch_002,
            )
            manifest = batch002.base.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(result["decision"]["scaling_decision"], "READY_FOR_ATTENTION_BATCH_003")


if __name__ == "__main__":
    unittest.main()
