from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import construct_presignal_v21_pack_population as construction


class PackPopulationConstructionTest(unittest.TestCase):
    def test_real_construction_counts_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = construction.construct_pack_population(output_root=Path(tmp), fixed_timestamp="2026-07-29T15:00:00Z")
            summary = result["summary"]
            decision = result["decision"]
            self.assertEqual(summary["pack_a_row_count"], 1239)
            self.assertEqual(summary["unique_pack_a_key_count"], 1239)
            self.assertEqual(summary["pack_e_row_count"], 1239)
            self.assertEqual(summary["unique_pack_e_key_count"], 1239)
            self.assertEqual(summary["construction_index_row_count"], 1239)
            self.assertEqual(summary["episode_count"], 413)
            self.assertEqual(summary["provider_counts"], {"Anthropic": 413, "Gemini": 413, "OpenAI": 413})
            self.assertEqual(summary["episodes_retaining_exactly_three_providers"], 413)
            self.assertEqual(summary["pack_a_valid_row_count"] + summary["pack_a_non_forecast_eligible_count"], 1239)
            self.assertEqual(summary["pack_e_valid_row_count"] + summary["pack_e_non_forecast_eligible_count"], 1239)
            self.assertEqual(summary["pack_a_blocked_count"], 0)
            self.assertEqual(summary["pack_e_blocked_count"], 0)
            self.assertEqual(summary["non_selected_attention_rows_retained"], 879)
            self.assertEqual(summary["pack_a_not_forecast_eligible_count"], summary["pack_a_non_forecast_eligible_count"])
            self.assertEqual(summary["pack_e_not_forecast_eligible_count"], summary["pack_e_non_forecast_eligible_count"])
            self.assertEqual(summary["attention_scientific_field_mutation_count"], 0)
            self.assertEqual(summary["unresolved_field_lineage_count"], 0)
            self.assertEqual(summary["cross_population_reconciliation_result"], "PASSED")
            self.assertEqual(decision["construction_status"], "PACK_POPULATION_CONSTRUCTION_COMPLETE")
            self.assertEqual(decision["pack_a_decision"], "PACK_A_POPULATION_COMPLETE")
            self.assertEqual(decision["pack_e_decision"], "PACK_E_POPULATION_COMPLETE")
            self.assertEqual(decision["attention_integrity_decision"], "ALL_1239_ATTENTION_ROWS_PRESERVED_UNCHANGED")
            self.assertEqual(decision["pack_separation_decision"], "PACK_A_AND_PACK_E_CONSTRUCTED_SEPARATELY")
            self.assertEqual(decision["forecast_boundary_decision"], "PACK_CONSTRUCTION_ONLY_NO_FORECAST_EXECUTION")
            self.assertEqual(decision["next_phase_decision"], "READY_FOR_BOUNDED_FORECAST_EXECUTION_PLANNING")

    def test_all_keys_are_unique_and_every_episode_has_three_provider_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = construction.construct_pack_population(output_root=Path(tmp), fixed_timestamp="2026-07-29T15:00:00Z")
            run_dir = result["run_dir"]
            pack_a_rows = construction.read_jsonl(run_dir / "pack_a_population.jsonl")
            pack_e_rows = construction.read_jsonl(run_dir / "pack_e_population.jsonl")
            index_rows = construction.read_jsonl(run_dir / "episode_provider_construction_index.jsonl")
            pack_a_keys = {construction.row_key(row["episode_id"], row["provider"]) for row in pack_a_rows}
            pack_e_keys = {construction.row_key(row["episode_id"], row["provider"]) for row in pack_e_rows}
            index_keys = {construction.row_key(row["episode_id"], row["provider"]) for row in index_rows}
            self.assertEqual(len(pack_a_keys), 1239)
            self.assertEqual(len(pack_e_keys), 1239)
            self.assertEqual(pack_a_keys, pack_e_keys)
            self.assertEqual(pack_a_keys, index_keys)
            per_episode = {}
            for row in index_rows:
                per_episode.setdefault(row["episode_id"], set()).add(row["provider"])
            self.assertEqual(len(per_episode), 413)
            self.assertTrue(all(len(providers) == 3 for providers in per_episode.values()))

    def test_non_selected_rows_remain_present_and_not_forecast_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = construction.construct_pack_population(output_root=Path(tmp), fixed_timestamp="2026-07-29T15:00:00Z")
            run_dir = result["run_dir"]
            pack_a_rows = construction.read_jsonl(run_dir / "pack_a_population.jsonl")
            not_forecast_eligible = [
                row for row in pack_a_rows
                if row["pack_a_construction_status"] == construction.PACK_STATUSES["not_eligible"]
            ]
            self.assertEqual(len(not_forecast_eligible), 957)
            self.assertTrue(all(row["future_forecast_eligibility_under_frozen_contract"] is False for row in not_forecast_eligible))
            self.assertTrue(all(row["pack_a_canonical_payload"]["provider_episode_selection"] != "FORECAST" for row in not_forecast_eligible))
            summary = construction.read_json(run_dir / "construction_summary.json")
            self.assertEqual(summary["non_selected_attention_rows_retained"], 879)

    def test_attention_fields_are_preserved_and_pack_a_pack_e_sources_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = construction.construct_pack_population(output_root=Path(tmp), fixed_timestamp="2026-07-29T15:00:00Z")
            run_dir = result["run_dir"]
            pack_a_rows = construction.read_jsonl(run_dir / "pack_a_population.jsonl")
            pack_e_rows = construction.read_jsonl(run_dir / "pack_e_population.jsonl")
            repaired = {
                (row["episode_id"], row["provider"]): row
                for row in construction.read_jsonl(construction.LINEAGE_REPAIR_ROOT / "repaired_episode_provider_pack_binding.jsonl")
            }
            for pack_a_row, pack_e_row in zip(pack_a_rows, pack_e_rows):
                key = (pack_a_row["episode_id"], pack_a_row["provider"])
                source = repaired[key]
                self.assertEqual(pack_a_row["attention_call_id"], source["attention_call_id"])
                self.assertEqual(pack_a_row["attention_request_identity"], source["attention_request_identity"])
                self.assertEqual(pack_a_row["attention_selection_state"], source["attention_selection_state"])
                self.assertEqual(pack_e_row["attention_call_id"], source["attention_call_id"])
                self.assertNotEqual(pack_a_row["pack_a_source_artifact_identities"], pack_e_row["pack_e_source_artifact_identities"])
                self.assertIsNone(pack_a_row["pack_a_canonical_payload"]["shared_market_state_pack"])
                self.assertIsNotNone(pack_e_row["pack_e_canonical_payload"]["shared_market_state_pack"])

    def test_no_provider_calls_google_writes_or_forecasts_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = construction.construct_pack_population(output_root=Path(tmp), fixed_timestamp="2026-07-29T15:00:00Z")
            manifest = construction.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["market_data_calls_executed"], 0)
            self.assertEqual(manifest["research_ai_calls_executed"], 0)
            self.assertEqual(manifest["web_calls_executed"], 0)
            self.assertEqual(manifest["google_writes_executed"], 0)
            self.assertEqual(manifest["forecast_execution_executed"], 0)
            self.assertEqual(manifest["outcome_attachment_executed"], 0)
            self.assertEqual(manifest["matrix_updates_executed"], 0)
            self.assertEqual(manifest["consensus_or_ranking_executed"], 0)


if __name__ == "__main__":
    unittest.main()
