from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_attention_batch_017 as batch017
from automation import reconcile_presignal_v21_full_attention_completion as full_completion


def _write_json(path: Path, value) -> None:
    path.write_text(full_completion.json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(full_completion.json.dumps(row, sort_keys=True) + "\n" for row in rows))


class ReconcileFullAttentionCompletionTest(unittest.TestCase):
    def test_frozen_plan_contains_204_unique_call_ids(self) -> None:
        calls_by_batch = full_completion.plan_calls_by_batch()
        total = sum(len(rows) for rows in calls_by_batch.values())
        unique = {row["call_id"] for rows in calls_by_batch.values() for row in rows}
        self.assertEqual(total, 204)
        self.assertEqual(len(unique), 204)

    def test_missing_calls_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            batch_run = output_root / "fake-batch-017"
            batch_run.mkdir(parents=True)
            _write_jsonl(
                batch_run / "normalized_attention_results.jsonl",
                [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "result_fingerprint": "fp1"}],
            )
            _write_json(batch_run / "batch_summary.json", {"successful_valid_calls": 1, "normalized_result_count": 1})
            _write_json(batch_run / "batch_decision.json", {"execution_status": "ATTENTION_BATCH_017_PARTIALLY_COMPLETE"})
            _write_jsonl(batch_run / "episode_attention_result_map.jsonl", [{"episode_id": "E1"}])

            plan = {"ATTN_BATCH_017": [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "episode_ids": ["E1"]}, {"call_id": "ATN_2", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S2", "episode_ids": ["E2"]}]}
            with patch.object(full_completion, "load_plan_batch_ids", return_value=["ATTN_BATCH_017"]), patch.object(full_completion, "plan_calls_by_batch", return_value=plan):
                result = full_completion.execute_reconciliation(final_batch_017_run_dir=batch_run, output_root=output_root, fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["summary"]["missing_call_ids"], ["ATN_2"])
            self.assertEqual(result["decision"]["full_attention_completion_decision"], "FULL_ATTENTION_POPULATION_INCOMPLETE")

    def test_duplicate_final_results_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            batch_a = output_root / "batch-a"
            batch_b = output_root / "batch-b"
            batch_a.mkdir(parents=True)
            batch_b.mkdir(parents=True)
            for batch_run, fp in ((batch_a, "fp1"), (batch_b, "fp2")):
                _write_jsonl(
                    batch_run / "normalized_attention_results.jsonl",
                    [{"call_id": "ATN_DUP", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "result_fingerprint": fp}],
                )
                _write_json(batch_run / "batch_summary.json", {"successful_valid_calls": 1, "normalized_result_count": 1})
                _write_json(batch_run / "batch_decision.json", {"execution_status": "ATTENTION_BATCH_COMPLETE"})
                _write_jsonl(batch_run / "episode_attention_result_map.jsonl", [{"episode_id": "E1"}])

            plan = {
                "ATTN_BATCH_016": [{"call_id": "ATN_DUP", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "episode_ids": ["E1"]}],
                "ATTN_BATCH_017": [{"call_id": "ATN_DUP", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "episode_ids": ["E1"]}],
            }
            authoritative = {
                "ATTN_BATCH_016": {"run_id": "batch-a", "kind": "execution", "prior_evidence_runs": []},
                "ATTN_BATCH_017": {"run_id": "batch-b", "kind": "execution", "prior_evidence_runs": []},
            }
            with patch.object(full_completion, "load_plan_batch_ids", return_value=["ATTN_BATCH_016", "ATTN_BATCH_017"]), patch.object(full_completion, "plan_calls_by_batch", return_value=plan), patch.object(full_completion, "build_authoritative_batch_runs", return_value=authoritative):
                result = full_completion.execute_reconciliation(final_batch_017_run_dir=batch_b, output_root=output_root, fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["summary"]["duplicate_authoritative_result_ids"], ["ATN_DUP"])

    def test_blocked_runs_are_not_counted_as_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            batch_run = output_root / "fake-batch-017"
            batch_run.mkdir(parents=True)
            _write_jsonl(
                batch_run / "normalized_attention_results.jsonl",
                [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "result_fingerprint": "fp1"}],
            )
            _write_json(batch_run / "batch_summary.json", {"successful_valid_calls": 1, "normalized_result_count": 1})
            _write_json(batch_run / "batch_decision.json", {"execution_status": "ATTENTION_BATCH_017_COMPLETE"})
            _write_jsonl(batch_run / "episode_attention_result_map.jsonl", [{"episode_id": "E1"}])
            plan = {"ATTN_BATCH_017": [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "episode_ids": ["E1"]}]}
            with patch.object(full_completion, "load_plan_batch_ids", return_value=["ATTN_BATCH_017"]), patch.object(full_completion, "plan_calls_by_batch", return_value=plan):
                result = full_completion.execute_reconciliation(final_batch_017_run_dir=batch_run, output_root=output_root, fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["summary"]["blocked_runs_counted_as_valid"], 0)

    def test_repaired_or_retried_calls_are_not_double_counted_when_authoritative_set_is_unique(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            batch_run = output_root / "fake-batch-017"
            batch_run.mkdir(parents=True)
            _write_jsonl(
                batch_run / "normalized_attention_results.jsonl",
                [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "result_fingerprint": "fp1"}],
            )
            _write_json(batch_run / "batch_summary.json", {"successful_valid_calls": 1, "normalized_result_count": 1})
            _write_json(batch_run / "batch_decision.json", {"execution_status": "ATTENTION_BATCH_017_COMPLETE"})
            _write_jsonl(batch_run / "episode_attention_result_map.jsonl", [{"episode_id": "E1"}])
            plan = {"ATTN_BATCH_017": [{"call_id": "ATN_1", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "source_session_id": "S1", "episode_ids": ["E1"]}]}
            with patch.object(full_completion, "load_plan_batch_ids", return_value=["ATTN_BATCH_017"]), patch.object(full_completion, "plan_calls_by_batch", return_value=plan):
                result = full_completion.execute_reconciliation(final_batch_017_run_dir=batch_run, output_root=output_root, fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["summary"]["repaired_or_retried_calls_double_counted"], 0)


if __name__ == "__main__":
    unittest.main()
