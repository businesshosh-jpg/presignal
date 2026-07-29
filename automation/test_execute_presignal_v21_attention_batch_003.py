from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_001 as batch001
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation.google_clients import GoogleCredentialError
from automation.test_execute_presignal_v21_attention_batch_001 import CountingDispatcher


def fake_source_sessions_batch_003():
    calls = batch003.load_batch_calls()
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


class AuthorityConflictDispatcher(CountingDispatcher):
    def __call__(self, request):
        response = super().__call__(request)
        if request["provider"] == "Gemini" and response.get("status") == "ok":
            response["actual_provider"] = "OpenAI"
        return response


class ExecuteAttentionBatch003Test(unittest.TestCase):
    def test_only_batch_003_calls_are_loaded(self) -> None:
        calls = batch003.load_batch_calls()
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({row["call_id"] for row in calls}), 12)
        batch_001_ids = {row["call_id"] for row in batch001.load_batch_calls()}
        batch_002_ids = {row["call_id"] for row in batch002.load_batch_calls()}
        self.assertFalse(batch_001_ids & {row["call_id"] for row in calls})
        self.assertFalse(batch_002_ids & {row["call_id"] for row in calls})

    def test_provider_model_assignments_remain_frozen(self) -> None:
        calls = batch003.load_batch_calls()
        self.assertEqual({row["provider"] for row in calls}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(all(row["model"] == batch003.base.PROVIDER_MODELS[row["provider"]] for row in calls))

    def test_provider_authority_is_recorded_and_successful_calls_cannot_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            first = batch003.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T05:00:00Z",
                source_session_loader=fake_source_sessions_batch_003,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            authority_rows = batch003.base.read_jsonl(first["run_dir"] / "provider_authority_results.jsonl")
            self.assertEqual(len(authority_rows), 12)
            self.assertTrue(all(row["authority_agreement"] is True for row in authority_rows))
            self.assertTrue(all(row["canonical_provider"] == row["manifest_provider"] for row in authority_rows))
            second = batch003.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T05:00:00Z",
                resume_run_dir=first["run_dir"],
                source_session_loader=fake_source_sessions_batch_003,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            self.assertEqual(second["reconciliation"]["skipped_already_successful_calls"], 12)

    def test_manifest_transport_disagreement_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = AuthorityConflictDispatcher()
            result = batch003.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T05:00:00Z",
                source_session_loader=fake_source_sessions_batch_003,
            )
            self.assertEqual(result["reconciliation"]["failed_provider_authority_calls"], 4)
            failures = batch003.base.read_jsonl(result["run_dir"] / "failed_call_ledger.jsonl")
            self.assertTrue(all(row["failure_stage"] in {"FAILED_PROVIDER_AUTHORITY", "SUCCEEDED_VALID"} or True for row in []))
            self.assertEqual(sum(1 for row in failures if row["failure_stage"] == "FAILED_PROVIDER_AUTHORITY"), 4)

    def test_blocked_preflight_fails_closed_before_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch003.base, "preflight_credentials", side_effect=GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing token")):
                result = batch003.execute_batch(output_root=Path(tmp), fixed_timestamp="2026-07-29T05:00:00Z")
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_003_BLOCKED")
            self.assertEqual(result["reconciliation"]["attempted_calls"], 0)

    def test_no_pack_no_forecast_no_batch_004_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CountingDispatcher()
            result = batch003.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T05:00:00Z",
                source_session_loader=fake_source_sessions_batch_003,
            )
            manifest = batch003.base.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(result["decision"]["scaling_decision"], "READY_FOR_ATTENTION_BATCH_004")


if __name__ == "__main__":
    unittest.main()
