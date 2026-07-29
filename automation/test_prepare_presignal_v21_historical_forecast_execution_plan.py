from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import prepare_presignal_v21_historical_forecast_execution_plan as planning


class ForecastExecutionPlanTest(unittest.TestCase):
    def test_real_population_counts_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = planning.construct_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
            summary = result["summary"]
            decision = result["decision"]
            self.assertEqual(summary["pack_a_construction_rows"], 1239)
            self.assertEqual(summary["pack_e_construction_rows"], 1239)
            self.assertEqual(summary["pack_a_eligible_rows"], 282)
            self.assertEqual(summary["pack_e_eligible_rows"], 282)
            self.assertEqual(summary["eligible_keys_present_in_both"], 282)
            self.assertEqual(summary["pack_a_only_eligible_keys"], 0)
            self.assertEqual(summary["pack_e_only_eligible_keys"], 0)
            self.assertEqual(summary["unique_eligible_episode_provider_count"], 282)
            self.assertEqual(summary["unique_eligible_episode_count"], 151)
            self.assertEqual(summary["authorized_pack_a_call_count"], 282)
            self.assertEqual(summary["authorized_pack_e_call_count"], 282)
            self.assertEqual(summary["total_authorized_forecast_call_count"], 564)
            self.assertEqual(summary["unique_forecast_call_id_count"], 564)
            self.assertEqual(summary["ineligible_pack_row_count"], 1914)
            self.assertEqual(summary["paired_condition_index_row_count"], 282)
            self.assertEqual(summary["paired_condition_mismatch_count"], 0)
            self.assertEqual(summary["calls_per_provider"], {"Anthropic": 216, "Gemini": 168, "OpenAI": 180})
            self.assertEqual(
                summary["calls_per_provider_per_pack"],
                {
                    "PACK_A": {"Anthropic": 108, "Gemini": 84, "OpenAI": 90},
                    "PACK_E": {"Anthropic": 108, "Gemini": 84, "OpenAI": 90},
                },
            )
            self.assertEqual(summary["total_planned_batch_count"], 48)
            self.assertEqual(summary["pack_a_batch_count"], 24)
            self.assertEqual(summary["pack_e_batch_count"], 24)
            self.assertEqual(summary["full_size_batch_count"], 46)
            self.assertEqual(summary["remainder_batch_count"], 2)
            self.assertEqual(summary["remainder_batch_sizes"], [6, 6])
            self.assertEqual(summary["maximum_calls_per_batch"], 12)
            self.assertEqual(summary["duplicate_call_id_count"], 0)
            self.assertEqual(summary["calls_without_batch_membership"], 0)
            self.assertEqual(summary["calls_with_multiple_batch_memberships"], 0)
            self.assertEqual(summary["unresolved_pack_fingerprints"], 0)
            self.assertEqual(summary["unresolved_prompt_fingerprints"], 0)
            self.assertEqual(summary["leakage_control_violations"], 0)
            self.assertEqual(decision["planning_status"], "FORECAST_EXECUTION_PLAN_COMPLETE")
            self.assertEqual(decision["eligibility_decision"], "PACK_A_AND_PACK_E_FORECAST_ELIGIBILITY_FULLY_RECONCILED")
            self.assertEqual(decision["forecast_contract_decision"], "FROZEN_FORECAST_CONTRACT_BOUND")
            self.assertEqual(decision["leakage_control_decision"], "HISTORICAL_LEAKAGE_CONTROLS_PROVEN")
            self.assertEqual(decision["batch_planning_decision"], "FORECAST_BATCH_PLAN_COMPLETE")
            self.assertEqual(decision["execution_boundary_decision"], "PLANNING_ONLY_NO_FORECAST_CALLS")
            self.assertEqual(decision["next_phase_decision"], "READY_FOR_BOUNDED_FORECAST_EXECUTION")

    def test_call_ledgers_and_batch_membership_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = planning.construct_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
            run_dir = result["run_dir"]
            calls = planning.read_jsonl(run_dir / "authorized_forecast_call_ledger.jsonl")
            batches = planning.read_jsonl(run_dir / "forecast_batch_manifest.jsonl")
            paired = planning.read_jsonl(run_dir / "episode_provider_paired_condition_index.jsonl")
            call_ids = {row["forecast_call_id"] for row in calls}
            self.assertEqual(len(call_ids), 564)
            self.assertEqual(len(calls), 564)
            membership: dict[str, int] = {}
            for batch in batches:
                self.assertLessEqual(batch["call_count"], 12)
                for call_id in batch["ordered_call_ids"]:
                    membership[call_id] = membership.get(call_id, 0) + 1
            self.assertEqual(set(membership), call_ids)
            self.assertTrue(all(count == 1 for count in membership.values()))
            self.assertEqual(len(paired), 282)
            self.assertTrue(all(row["paired_cutoff_equality_result"] for row in paired))
            self.assertTrue(all(row["paired_provider_equality_result"] for row in paired))
            self.assertTrue(all(row["paired_episode_equality_result"] for row in paired))

    def test_pack_a_and_pack_e_remain_separate_with_distinct_call_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = planning.construct_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
            run_dir = result["run_dir"]
            calls = planning.read_jsonl(run_dir / "authorized_forecast_call_ledger.jsonl")
            paired = planning.read_jsonl(run_dir / "episode_provider_paired_condition_index.jsonl")
            by_id = {row["forecast_call_id"]: row for row in calls}
            for row in paired:
                pack_a = by_id[row["pack_a_call_id"]]
                pack_e = by_id[row["pack_e_call_id"]]
                self.assertEqual(pack_a["episode_id"], pack_e["episode_id"])
                self.assertEqual(pack_a["provider"], pack_e["provider"])
                self.assertEqual(pack_a["model"], pack_e["model"])
                self.assertEqual(pack_a["historical_cutoff"], pack_e["historical_cutoff"])
                self.assertEqual(pack_a["pack_type"], "PACK_A")
                self.assertEqual(pack_e["pack_type"], "PACK_E")
                self.assertNotEqual(pack_a["forecast_call_id"], pack_e["forecast_call_id"])
                self.assertNotEqual(pack_a["pack_row_identity"], pack_e["pack_row_identity"])

    def test_ineligible_rows_do_not_enter_authorized_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = planning.construct_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
            run_dir = result["run_dir"]
            eligibility = planning.read_jsonl(run_dir / "forecast_eligibility_population.jsonl")
            calls = planning.read_jsonl(run_dir / "authorized_forecast_call_ledger.jsonl")
            ineligible = planning.read_jsonl(run_dir / "ineligible_pack_row_ledger.jsonl")
            eligible_rows = [row for row in eligibility if row["forecast_eligibility"]]
            self.assertEqual(len(eligible_rows), 564)
            self.assertEqual(len(ineligible), 1914)
            call_row_keys = {(row["episode_id"], row["provider"], row["pack_type"]) for row in calls}
            eligible_keys = {(row["episode_id"], row["provider"], row["pack_type"]) for row in eligible_rows}
            ineligible_keys = {(row["episode_id"], row["provider"], row["pack_type"]) for row in ineligible}
            self.assertEqual(call_row_keys, eligible_keys)
            self.assertTrue(call_row_keys.isdisjoint(ineligible_keys))

    def test_prompt_payloads_have_no_outcomes_or_live_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = planning.construct_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
            run_dir = result["run_dir"]
            prompts = planning.read_jsonl(run_dir / "prompt_payload_manifest.jsonl")
            manifest = planning.read_json(run_dir / "run_manifest.json")
            self.assertEqual(len(prompts), 564)
            for row in prompts:
                prompt_text = row["prompt_text"]
                for token in planning.FORBIDDEN_PROMPT_TOKENS:
                    self.assertNotIn(token, prompt_text)
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["live_forecast_outputs_generated"], 0)
            self.assertEqual(manifest["market_data_calls_executed"], 0)
            self.assertEqual(manifest["research_ai_calls_executed"], 0)
            self.assertEqual(manifest["web_calls_executed"], 0)
            self.assertEqual(manifest["google_writes_executed"], 0)
            self.assertEqual(manifest["outcome_attachment_executed"], 0)
            self.assertEqual(manifest["matrix_updates_executed"], 0)
            self.assertEqual(manifest["forecast_accuracy_calculations_executed"], 0)
            self.assertEqual(manifest["consensus_or_ranking_executed"], 0)


if __name__ == "__main__":
    unittest.main()
