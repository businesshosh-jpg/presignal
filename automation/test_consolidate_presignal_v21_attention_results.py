from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import consolidate_presignal_v21_attention_results as consolidation


class ConsolidateAttentionResultsTest(unittest.TestCase):
    def test_real_consolidation_counts_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = consolidation.execute_consolidation(output_root=Path(tmp), fixed_timestamp="2026-07-29T12:00:00Z")
            summary = result["summary"]
            decision = result["decision"]
            self.assertEqual(summary["authoritative_call_level_row_count"], 204)
            self.assertEqual(summary["unique_call_id_count"], 204)
            self.assertEqual(summary["session_provider_row_count"], 204)
            self.assertEqual(summary["unique_session_provider_key_count"], 204)
            self.assertEqual(summary["episode_count"], 413)
            self.assertEqual(summary["episode_provider_mapping_count"], 1239)
            self.assertEqual(summary["unique_episode_provider_key_count"], 1239)
            self.assertEqual(summary["provider_counts"], {"Anthropic": 413, "Gemini": 413, "OpenAI": 413})
            self.assertEqual(summary["provider_model_call_counts"], {
                "Anthropic|claude-haiku-4-5": 68,
                "Gemini|gemini-2.5-flash-lite": 68,
                "OpenAI|gpt-4o-mini-2024-07-18": 68,
            })
            self.assertEqual(summary["session_count"], 68)
            self.assertEqual(summary["episodes_with_exactly_three_provider_mappings"], 413)
            self.assertEqual(summary["episodes_with_missing_provider_mappings"], 0)
            self.assertEqual(summary["duplicate_mapping_count"], 0)
            self.assertEqual(summary["unexpected_provider_count"], 0)
            self.assertEqual(summary["authoritative_lineage_conflict_count"], 0)
            self.assertEqual(summary["blocked_runs_counted_as_authoritative"], 0)
            self.assertEqual(summary["repaired_or_retried_calls_double_counted"], 0)
            self.assertEqual(summary["scientific_field_mutation_count"], 0)
            self.assertEqual(summary["cross_population_reconciliation_result"], "PASSED")
            self.assertEqual(decision["consolidation_status"], "ATTENTION_RESULT_CONSOLIDATION_COMPLETE")
            self.assertEqual(decision["lineage_decision"], "ALL_AUTHORITATIVE_CALL_LINEAGE_RESOLVED")
            self.assertEqual(decision["coverage_decision"], "FULL_413_EPISODE_1239_PROVIDER_MAPPING_COVERAGE")
            self.assertEqual(decision["scientific_integrity_decision"], "SCIENTIFIC_FIELDS_PRESERVED_UNCHANGED")
            self.assertEqual(decision["next_phase_decision"], "READY_FOR_ATTENTION_TO_PACK_LINEAGE_BINDING")

    def test_completion_reconciliation_contains_exactly_204_authoritative_calls(self) -> None:
        calls, _, _ = consolidation.load_authoritative_inventory()
        self.assertEqual(len(calls), 204)
        self.assertEqual(len({row["call_id"] for row in calls}), 204)
        self.assertTrue(all(row["completion_status"] == "VALIDATED" for row in calls))

    def test_missing_mappings_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(consolidation, "load_episode_inventory", return_value=({}, {})):
                result = consolidation.execute_consolidation(output_root=Path(tmp), fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["decision"]["coverage_decision"], "EPISODE_PROVIDER_MAPPING_GAPS_PRESENT")
            self.assertEqual(result["decision"]["consolidation_status"], "ATTENTION_RESULT_CONSOLIDATION_INCOMPLETE")

    def test_duplicate_episode_provider_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls, batches, batch_by_id = consolidation.load_authoritative_inventory()
            duplicated_calls = [dict(row) for row in calls]
            first_call = duplicated_calls[0]
            second_call_index = next(
                index
                for index, row in enumerate(duplicated_calls[1:], start=1)
                if row["provider"] == first_call["provider"]
            )
            duplicated_calls[second_call_index]["episode_ids"] = list(first_call["episode_ids"])
            with patch.object(consolidation, "load_authoritative_inventory", return_value=(duplicated_calls, batches, batch_by_id)):
                result = consolidation.execute_consolidation(output_root=Path(tmp), fixed_timestamp="2026-07-29T12:00:00Z")
            self.assertEqual(result["decision"]["coverage_decision"], "EPISODE_PROVIDER_MAPPING_CONFLICTS_PRESENT")

    def test_blocked_runs_are_never_authoritative(self) -> None:
        calls, _, _ = consolidation.load_authoritative_inventory()
        authoritative_runs = {row["authoritative_run_id"] for row in calls}
        self.assertFalse(authoritative_runs & consolidation.BLOCKED_RUN_IDS)

    def test_no_provider_calls_google_writes_pack_forecast_outcome_or_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = consolidation.execute_consolidation(output_root=Path(tmp), fixed_timestamp="2026-07-29T12:00:00Z")
            manifest = consolidation.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["google_writes_executed"], 0)
            self.assertEqual(manifest["pack_construction_executed"], 0)
            self.assertEqual(manifest["forecast_execution_executed"], 0)
            self.assertEqual(manifest["outcome_attachment_executed"], 0)
            self.assertEqual(manifest["matrix_updates_executed"], 0)


if __name__ == "__main__":
    unittest.main()
