#!/usr/bin/env python3
from __future__ import annotations

import unittest

from automation import execute_presignal_v21_full_reproducible_round1_v1_1 as full


EXCLUDED_EPISODE_ID = "EP_EVENT_757e72165d3ec05306a6"


class FullReproducibleRound1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack_a_rows, self.pack_e_rows = full.load_inputs()
        self.pairs = full.pair_rows(self.pack_a_rows, self.pack_e_rows)
        self.population_rows = full.read_jsonl(full.OUTPUT_ROOT / full.PREVALIDATION_RUN_ID / "population_admission.jsonl")

    def test_full_manifest_applies_strict_population_admission(self) -> None:
        executable_rows, coverage, unique_episodes, removed_identities, removed_reconciliation = full.build_full_manifest(
            population_rows=self.population_rows,
            pair_index=self.pairs,
        )

        self.assertEqual(len(executable_rows), 85)
        self.assertEqual(len(unique_episodes), 47)
        self.assertEqual(len(removed_identities), 2)
        self.assertEqual({row["episode_id"] for row in removed_identities}, {EXCLUDED_EPISODE_ID})
        self.assertEqual({row["provider"] for row in removed_identities}, {"Gemini", "OpenAI"})
        self.assertEqual(
            {row["population_status"] for row in removed_identities},
            {"EXCLUDED_OUTCOME_UNAVAILABLE"},
        )
        self.assertEqual(
            {row["population_exclusion_detail"] for row in removed_identities},
            {"MISSING_OR_STALE_ANCHOR_PRICE_5M_PRICE_15M_PRICE_30M_PRICE_60M"},
        )

        self.assertEqual(coverage["scientifically_eligible_episode_count"], 374)
        self.assertEqual(coverage["unique_executable_episode_count"], 47)
        self.assertEqual(coverage["gemini_covered_episode_count"], 47)
        self.assertEqual(coverage["openai_covered_episode_count"], 38)
        self.assertEqual(coverage["both_provider_episode_count"], 38)
        self.assertEqual(coverage["eligible_episode_count_without_executable_provider_coverage"], 327)

        self.assertEqual(removed_reconciliation["source_pack_paired_provider_episode_identity_count"], 87)
        self.assertEqual(removed_reconciliation["authorized_provider_episode_identity_count"], 85)
        self.assertEqual(removed_reconciliation["removed_provider_episode_identity_count"], 2)
        self.assertEqual(removed_reconciliation["source_pack_paired_forecast_arm_count"], 174)
        self.assertEqual(removed_reconciliation["authorized_forecast_arm_count"], 170)
        self.assertEqual(removed_reconciliation["removed_forecast_arm_count"], 4)

    def test_excluded_episode_cannot_enter_call_ledger(self) -> None:
        executable_rows, _, unique_episodes, _, _ = full.build_full_manifest(
            population_rows=self.population_rows,
            pair_index=self.pairs,
        )
        self.assertNotIn(EXCLUDED_EPISODE_ID, {row["episode_id"] for row in executable_rows})
        self.assertNotIn(EXCLUDED_EPISODE_ID, {row["episode_id"] for row in unique_episodes})

        outcomes = full.build_outcomes_for_executable(unique_episodes)
        ledger, pair_symmetry = full.build_ledger(
            executable_rows=executable_rows,
            pair_index=self.pairs,
            outcomes_by_episode={row["episode_id"]: row for row in outcomes},
            run_dir=full.OUTPUT_ROOT / "TEST-FULL",
        )
        self.assertEqual(len(ledger), 170)
        self.assertEqual(len(pair_symmetry), 85)
        self.assertEqual(sum(row["pack_arm"] == "PACK_A" for row in ledger), 85)
        self.assertEqual(sum(row["pack_arm"] == "PACK_E" for row in ledger), 85)
        self.assertNotIn(EXCLUDED_EPISODE_ID, {row["episode_id"] for row in ledger})


if __name__ == "__main__":
    unittest.main()
