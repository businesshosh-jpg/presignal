from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import bind_presignal_v21_attention_to_pack_lineage as binding


class AttentionToPackLineageBindingTest(unittest.TestCase):
    def test_real_lineage_binding_counts_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            summary = result["summary"]
            decision = result["decision"]
            self.assertEqual(summary["episode_provider_attention_lineage_row_count"], 1239)
            self.assertEqual(summary["unique_episode_provider_attention_key_count"], 1239)
            self.assertEqual(summary["episode_pack_source_lineage_row_count"], 413)
            self.assertEqual(summary["future_pack_binding_row_count"], 1239)
            self.assertEqual(summary["unique_future_pack_binding_key_count"], 1239)
            self.assertEqual(summary["provider_counts"], {"Anthropic": 413, "Gemini": 413, "OpenAI": 413})
            self.assertEqual(summary["episode_count"], 413)
            self.assertEqual(summary["episodes_retaining_exactly_three_providers"], 413)
            self.assertEqual(summary["pack_a_resolved_count"], 1023)
            self.assertEqual(summary["pack_a_blocked_count"], 216)
            self.assertEqual(summary["pack_a_not_required_count"], 0)
            self.assertEqual(summary["pack_e_resolved_count"], 1023)
            self.assertEqual(summary["pack_e_blocked_count"], 216)
            self.assertEqual(summary["pack_e_not_required_count"], 0)
            self.assertEqual(summary["fully_resolved_episode_provider_rows"], 1023)
            self.assertEqual(summary["partially_resolved_episode_provider_rows"], 0)
            self.assertEqual(summary["fully_blocked_episode_provider_rows"], 216)
            self.assertEqual(summary["missing_source_count"], 144)
            self.assertEqual(summary["identity_conflict_count"], 0)
            self.assertEqual(summary["fuzzy_bindings_accepted"], 0)
            self.assertEqual(summary["attention_scientific_field_mutation_count"], 0)
            self.assertEqual(summary["cross_population_reconciliation_result"], "PASSED")
            self.assertEqual(decision["lineage_binding_status"], "ATTENTION_TO_PACK_LINEAGE_BINDING_PARTIALLY_COMPLETE")
            self.assertEqual(decision["attention_integrity_decision"], "ALL_1239_ATTENTION_ROWS_BOUND_WITHOUT_MUTATION")
            self.assertEqual(decision["pack_a_lineage_decision"], "PACK_A_LINEAGE_PARTIALLY_RESOLVED")
            self.assertEqual(decision["pack_e_lineage_decision"], "PACK_E_LINEAGE_PARTIALLY_RESOLVED")
            self.assertEqual(decision["scientific_boundary_decision"], "LINEAGE_ONLY_NO_PACK_CONSTRUCTION")
            self.assertEqual(decision["next_phase_decision"], "REPAIR_PACK_LINEAGE_BINDING")

    def test_all_resolved_bindings_cite_existing_frozen_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            rows = binding.read_jsonl(result["run_dir"] / "episode_provider_pack_binding.jsonl")
            for row in rows:
                if row["pack_a_lineage_status"] == "RESOLVED":
                    for ref in row["pack_a_source_references"]:
                        path = Path(ref["artifact"]) if not ref["artifact"].startswith("outputs/") else binding.ROOT / ref["artifact"]
                        self.assertTrue(path.exists(), ref["artifact"])
                if row["pack_e_lineage_status"] == "RESOLVED":
                    for ref in row["pack_e_source_references"]:
                        path = Path(ref["artifact"]) if not ref["artifact"].startswith("outputs/") else binding.ROOT / ref["artifact"]
                        self.assertTrue(path.exists(), ref["artifact"])

    def test_pack_a_and_pack_e_lineage_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            rows = binding.read_jsonl(result["run_dir"] / "episode_provider_pack_binding.jsonl")
            sample = next(row for row in rows if row["pack_a_lineage_status"] == "RESOLVED" and row["pack_e_lineage_status"] == "RESOLVED")
            self.assertNotEqual(sample["pack_a_source_references"], sample["pack_e_source_references"])

    def test_identity_conflicts_fail_closed(self) -> None:
        loaded = binding.load_required_artifacts()
        bad_episode_map = [dict(row) for row in loaded["episode_to_attention_call_map"]]
        bad_episode_map[0] = {
            **bad_episode_map[0],
            "provider_call_ids": {**bad_episode_map[0]["provider_call_ids"], "Anthropic": "ATN_FAKE_CONFLICT"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(binding, "load_required_artifacts", return_value={**loaded, "episode_to_attention_call_map": bad_episode_map}):
                result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            self.assertGreater(result["summary"]["identity_conflict_count"], 0)

    def test_missing_sources_produce_explicit_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            blockers = binding.read_jsonl(result["run_dir"] / "lineage_blocker_ledger.jsonl")
            missing = binding.read_jsonl(result["run_dir"] / "missing_source_ledger.jsonl")
            self.assertGreater(len(blockers), 0)
            self.assertGreater(len(missing), 0)
            self.assertTrue(all(row["scientific_interpretation_required"] is False for row in blockers))

    def test_no_provider_calls_google_writes_pack_construction_forecast_or_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = binding.execute_lineage_binding(output_root=Path(tmp), fixed_timestamp="2026-07-29T13:00:00Z")
            manifest = binding.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["google_writes_executed"], 0)
            self.assertEqual(manifest["pack_a_constructed"], 0)
            self.assertEqual(manifest["pack_e_constructed"], 0)
            self.assertEqual(manifest["forecast_execution_executed"], 0)
            self.assertEqual(manifest["outcome_attachment_executed"], 0)
            self.assertEqual(manifest["matrix_updates_executed"], 0)
            self.assertEqual(manifest["consensus_or_ranking_executed"], 0)


if __name__ == "__main__":
    unittest.main()
