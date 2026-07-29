from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_015 as batch015
from automation import execute_presignal_v21_attention_batch_016 as batch016
from automation import execute_presignal_v21_attention_batches_015_016 as coordinator
from automation.test_execute_presignal_v21_attention_batch_004 import (
    AuthorityConflictDispatcher,
    CompletenessDispatcher,
    fake_source_sessions_batch_004,
)


class ExecuteAttentionBatches015016Test(unittest.TestCase):
    def test_only_batches_015_and_016_are_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = coordinator.execute_move(
                output_root=Path(tmp),
                batch_output_root=Path(tmp),
                fixed_timestamp="2026-07-29T15:00:00Z",
                dispatcher_015=CompletenessDispatcher(),
                dispatcher_016=CompletenessDispatcher(),
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            manifest = coordinator.batch015.batch004.read_json(result["run_dir"] / "authorized_batch_manifest.json")
            self.assertEqual([row["batch_id"] for row in manifest["authorized_batches"]], ["ATTN_BATCH_015", "ATTN_BATCH_016"])

    def test_each_batch_contains_exactly_12_unique_calls(self) -> None:
        self.assertEqual(len(batch015.load_batch_calls()), 12)
        self.assertEqual(len({row["call_id"] for row in batch015.load_batch_calls()}), 12)
        self.assertEqual(len(batch016.load_batch_calls()), 12)
        self.assertEqual(len({row["call_id"] for row in batch016.load_batch_calls()}), 12)

    def test_no_overlap_between_batches(self) -> None:
        self.assertFalse({row["call_id"] for row in batch015.load_batch_calls()} & {row["call_id"] for row in batch016.load_batch_calls()})

    def test_batch_016_waits_for_batch_015_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = coordinator.execute_move(
                output_root=Path(tmp),
                batch_output_root=Path(tmp),
                fixed_timestamp="2026-07-29T15:00:00Z",
                dispatcher_015=CompletenessDispatcher(),
                dispatcher_016=CompletenessDispatcher(),
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            gate = coordinator.batch015.batch004.read_json(result["run_dir"] / "continuation_gate_decision.json")
            self.assertEqual(gate["continuation_decision"], "PROCEED_TO_ATTENTION_BATCH_016")
            self.assertIsNotNone(result["batch_016"])

    def test_shared_batch_015_failure_blocks_batch_016(self) -> None:
        blocked_result = {
            "run_dir": Path("/tmp/fake-batch-015"),
            "decision": {
                "execution_status": "ATTENTION_BATCH_015_BLOCKED",
                "contract_decision": "EXECUTION_ENVIRONMENT_FAILURE",
                "provider_authority_decision": "PROVIDER_AUTHORITY_NOT_REACHED",
                "completeness_decision": "COMPLETENESS_NOT_REACHED",
            },
            "reconciliation": {
                "attempted_calls": 0,
                "successful_valid_calls": 0,
                "skipped_already_successful_calls": 0,
                "unexpected_calls": 0,
                "duplicate_successful_calls": 0,
                "failed_transport_calls": 0,
                "failed_provider_calls": 0,
                "failed_provider_authority_calls": 0,
                "failed_parse_calls": 0,
                "completeness_failed_calls": 0,
                "failed_validation_calls": 0,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(coordinator.batch015, "execute_batch", return_value=blocked_result):
                result = coordinator.execute_move(
                    output_root=Path(tmp),
                    batch_output_root=Path(tmp),
                    fixed_timestamp="2026-07-29T15:00:00Z",
                    dispatcher_016=CompletenessDispatcher(),
                    source_session_loader=fake_source_sessions_batch_004,
                    enforce_head=False,
                )
            self.assertEqual(result["continuation_gate"], "STOP_BEFORE_ATTENTION_BATCH_016_SHARED_FAILURE")
            self.assertIsNone(result["batch_016"])

    def test_isolated_call_level_failure_does_not_automatically_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dispatcher = AuthorityConflictDispatcher()
            result = batch015.execute_batch(
                output_root=Path(tmp),
                dispatcher=dispatcher,
                fixed_timestamp="2026-07-29T15:00:00Z",
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(result["reconciliation"]["attempted_calls"], 12)
            self.assertEqual(result["reconciliation"]["failed_provider_authority_calls"], 4)
            self.assertEqual(result["decision"]["execution_status"], "ATTENTION_BATCH_015_PARTIALLY_COMPLETE")

    def test_continuation_decision_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = coordinator.execute_move(
                output_root=Path(tmp),
                batch_output_root=Path(tmp),
                fixed_timestamp="2026-07-29T15:00:00Z",
                dispatcher_015=CompletenessDispatcher(),
                dispatcher_016=CompletenessDispatcher(),
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertTrue((result["run_dir"] / "continuation_gate_decision.json").exists())

    def test_maximum_provider_calls_equal_24(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d15 = CompletenessDispatcher()
            d16 = CompletenessDispatcher()
            result = coordinator.execute_move(
                output_root=Path(tmp),
                batch_output_root=Path(tmp),
                fixed_timestamp="2026-07-29T15:00:00Z",
                dispatcher_015=d15,
                dispatcher_016=d16,
                source_session_loader=fake_source_sessions_batch_004,
                enforce_head=False,
            )
            self.assertEqual(len(d15.calls) + len(d16.calls), 24)
            self.assertEqual(result["move_reconciliation"]["total_attempted_provider_calls"], 24)


if __name__ == "__main__":
    unittest.main()
