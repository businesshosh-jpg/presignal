#!/usr/bin/env python3
from __future__ import annotations

import unittest

from automation import execute_presignal_v21_targeted_provider_validation_v1_1 as targeted


class TargetedProviderValidationTests(unittest.TestCase):
    def test_common_openai_anthropic_selection_is_frozen_and_shortfall_explicit(self) -> None:
        pack_a_rows, pack_e_rows = targeted.load_inputs()
        pairs = targeted.pair_rows(pack_a_rows, pack_e_rows)
        population_rows = targeted.read_jsonl(
            targeted.OUTPUT_ROOT / targeted.PREVALIDATION_RUN_ID / "population_admission.jsonl"
        )
        selected, frozen = targeted.build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
        self.assertEqual(len(selected), 3)
        self.assertEqual(sum(row["episode_type"] == "standalone" for row in selected), 3)
        self.assertEqual(sum(row["episode_type"] == "cluster" for row in selected), 0)
        self.assertEqual(frozen["available_common_episode_count"], 3)
        self.assertEqual(frozen["shortfall_reason"], "INSUFFICIENT_COMMON_OPENAI_ANTHROPIC_EPISODES_AFTER_EXPANDED_WINDOW")
        self.assertEqual(
            [row["episode_id"] for row in selected],
            [
                "EP_EVENT_f2862037fd8c6ab5315a",
                "EP_EVENT_3ae230535bdb433af7ca",
                "EP_EVENT_b7dfc476aa8eebf6d2a5",
            ],
        )

    def test_reason_taxonomy_is_deterministic(self) -> None:
        self.assertEqual(targeted.classify_no_signal_reason("Critical must-have information unavailable at forecast cutoff."), "MISSING_REQUIRED_CONTEXT")
        self.assertEqual(targeted.classify_no_signal_reason("Event is CONTEXT_ONLY with low direct market impact."), "EVENT_IRRELEVANT_TO_USDJPY")
        self.assertEqual(targeted.classify_no_signal_reason("Competing forces and conflicting signals prevent directional conviction."), "CONFLICTING_INPUTS")
        self.assertEqual(targeted.classify_no_signal_reason("Confidence falls below threshold under uncertainty."), "HIGH_UNCERTAINTY")
        self.assertEqual(targeted.classify_no_signal_reason("No directional signal can be established."), "INSUFFICIENT_DIRECTIONAL_EDGE")

    def test_targeted_ledger_count_matches_shortfall_population(self) -> None:
        pack_a_rows, pack_e_rows = targeted.load_inputs()
        pairs = targeted.pair_rows(pack_a_rows, pack_e_rows)
        population_rows = targeted.read_jsonl(
            targeted.OUTPUT_ROOT / targeted.PREVALIDATION_RUN_ID / "population_admission.jsonl"
        )
        selected, _ = targeted.build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
        ledger, pair_symmetry = targeted.build_ledger(selected=selected, pair_index=pairs, run_dir=targeted.OUTPUT_ROOT / "TEST-RUN")
        self.assertEqual(len(ledger), 12)
        self.assertEqual(len(pair_symmetry), 6)
        self.assertTrue(all(row["provider"] in {"Anthropic", "OpenAI"} for row in ledger))


if __name__ == "__main__":
    unittest.main()
