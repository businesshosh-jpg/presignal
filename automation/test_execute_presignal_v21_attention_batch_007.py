from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_001 as batch001
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation import execute_presignal_v21_attention_batch_004 as batch004
from automation import execute_presignal_v21_attention_batch_005 as batch005
from automation import execute_presignal_v21_attention_batch_006 as batch006
from automation import execute_presignal_v21_attention_batch_007 as batch007
from automation.google_clients import GoogleCredentialError
from automation.test_execute_presignal_v21_attention_batch_004 import (
    AuthorityConflictDispatcher,
    CompletenessDispatcher,
    IncompleteDispatcher,
    fake_source_sessions_batch_004,
)


class ExecuteAttentionBatch007Test(unittest.TestCase):
    def test_only_batch_007_calls_are_loaded(self) -> None:
        calls = batch007.load_batch_calls()
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({row["call_id"] for row in calls}), 12)
        prior = (
            {row["call_id"] for row in batch001.load_batch_calls()}
            | {row["call_id"] for row in batch002.load_batch_calls()}
            | {row["call_id"] for row in batch003.load_batch_calls()}
            | {row["call_id"] for row in batch004.load_batch_calls()}
            | {row["call_id"] for row in batch005.load_batch_calls()}
            | {row["call_id"] for row in batch006.load_batch_calls()}
        )
        self.assertFalse(prior & {row["call_id"] for row in calls})

    def test_provider_model_assignments_remain_frozen(self) -> None:
        calls = batch007.load_batch_calls()
        self.assertEqual({row["provider"] for row in calls}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(all(row["model"] == batch007.batch004.base.PROVIDER_MODELS[row["provider"]] for row in calls))

    def test_manifest_transport_agreement_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = AuthorityConflictDispatcher()
            result = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(result["reconciliation"]["failed_provider_authority_calls"], 4)

    def test_expected_and_returned_event_sets_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = IncompleteDispatcher()
            result = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(result["reconciliation"]["completeness_failed_calls"], 12)
            rows = batch007.batch004.read_jsonl(result["run_dir"] / "event_completeness_results.jsonl")
            self.assertTrue(all(row["missing_event_ids"] for row in rows))

    def test_successful_calls_cannot_repeat_and_resume_skips_validated_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            first = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            second = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                resume_run_dir=first["run_dir"],
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(len(dispatcher.calls), 12)
            self.assertEqual(second["reconciliation"]["skipped_already_successful_calls"], 12)

    def test_only_complete_validated_results_enter_normalized_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            result = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            normalized = batch007.batch004.read_jsonl(result["run_dir"] / "normalized_attention_results.jsonl")
            self.assertEqual(len(normalized), 12)
            self.assertEqual(result["reconciliation"]["successful_valid_calls"], 12)

    def test_blocked_preflight_fails_closed_before_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(batch007.batch004, "preflight_credentials", side_effect=GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing token")):
                result = batch007.execute_batch(output_root=Path(tmp), fixed_timestamp="2026-07-29T09:00:00Z", enforce_head=False)
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_007_BLOCKED")
            self.assertEqual(result["reconciliation"]["attempted_calls"], 0)

    def test_no_pack_no_forecast_no_batch_008_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = CompletenessDispatcher()
            result = batch007.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T09:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            manifest = batch007.batch004.base.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_calls_executed"], 0)
            self.assertEqual(result["decision"]["scaling_decision"], "READY_FOR_ATTENTION_BATCH_008")


if __name__ == "__main__":
    unittest.main()
