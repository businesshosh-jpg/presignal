#!/usr/bin/env python3
from __future__ import annotations

import unittest

from automation import execute_presignal_v21_expanded_historical_validation_v1_1 as expanded
from automation import presignal_v21_event_path_contract_v1_1 as contract


class ExpandedHistoricalValidationSelectionTests(unittest.TestCase):
    def test_selection_is_frozen_to_twelve_callable_episodes(self) -> None:
        pack_a_rows, pack_e_rows = expanded.load_inputs()
        pairs = expanded.pair_rows(pack_a_rows, pack_e_rows)
        population_rows = expanded.read_jsonl(
            expanded.OUTPUT_ROOT / expanded.SOURCE_PREVALIDATION_RUN_ID / "population_admission.jsonl"
        )
        selected, frozen = expanded.build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
        self.assertEqual(len(selected), 12)
        self.assertEqual(sum(row["episode_type"] == "standalone" for row in selected), 6)
        self.assertEqual(sum(row["episode_type"] == "cluster" for row in selected), 6)
        self.assertEqual(
            [row["episode_id"] for row in selected],
            [
                "EP_EVENT_2d777c70a07c631e5f03",
                "EP_BATCH_80bbf91b9afbc592880f",
                "EP_BATCH_48e817a6f98121eb04dd",
                "EP_EVENT_fbb37fea272c4e76546e",
                "EP_EVENT_697fa043068a1f61838f",
                "EP_EVENT_1b999628b864d9bebb06",
                "EP_EVENT_870dc1a1acc371a30f04",
                "EP_BATCH_a170305f20ad150c2335",
                "EP_BATCH_4bf004a6c160d4763e06",
                "EP_EVENT_92769da428b1a43350e5",
                "EP_BATCH_4c1237b4fdba265e575f",
                "EP_BATCH_6bf769aa6603093027fc",
            ],
        )
        self.assertEqual(
            frozen["selection_protocol"],
            "EARLIEST_6_CALLABLE_STANDALONE_PLUS_EARLIEST_6_CALLABLE_CLUSTER_AFTER_SMALL_VALIDATION_THEN_CHRONOLOGICAL_SORT",
        )

    def test_selected_outcomes_are_v1_1_and_approximation_only(self) -> None:
        pack_a_rows, pack_e_rows = expanded.load_inputs()
        pairs = expanded.pair_rows(pack_a_rows, pack_e_rows)
        population_rows = expanded.read_jsonl(
            expanded.OUTPUT_ROOT / expanded.SOURCE_PREVALIDATION_RUN_ID / "population_admission.jsonl"
        )
        selected, _ = expanded.build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
        outcomes = expanded.build_outcomes_for_selected(selected)
        self.assertEqual(len(outcomes), 12)
        self.assertEqual(sorted({row["schema_version"] for row in outcomes}), [contract.SCHEMA_VERSION])
        self.assertEqual(sorted({row["immediate_impulse_outcome_state"] for row in outcomes}), ["APPROXIMATION_ONLY"])

    def test_ledger_count_and_provider_matrix_are_frozen(self) -> None:
        pack_a_rows, pack_e_rows = expanded.load_inputs()
        pairs = expanded.pair_rows(pack_a_rows, pack_e_rows)
        population_rows = expanded.read_jsonl(
            expanded.OUTPUT_ROOT / expanded.SOURCE_PREVALIDATION_RUN_ID / "population_admission.jsonl"
        )
        selected, _ = expanded.build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
        run_dir = expanded.OUTPUT_ROOT / "TEST-RUN"
        ledger, pair_symmetry = expanded.build_ledger(selected=selected, pair_index=pairs, run_dir=run_dir)
        self.assertEqual(len(ledger), 60)
        self.assertEqual(len(pair_symmetry), 30)
        self.assertEqual(sum(row["pack_arm"] == "PACK_A" for row in ledger), 30)
        self.assertEqual(sum(row["pack_arm"] == "PACK_E" for row in ledger), 30)
        self.assertEqual(sorted({row["contract"] for row in ledger}), [contract.CONTRACT_VERSION])
        self.assertEqual(sorted({row["schema"] for row in ledger}), [contract.SCHEMA_VERSION])


if __name__ == "__main__":
    unittest.main()
