#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import implement_presignal_v21_full_round1_eligibility_separation as impl


class ImplementFullRound1EligibilitySeparationTest(unittest.TestCase):
    def test_all_462_episodes_remain_admitted(self) -> None:
        rows = impl.load_contract_application()
        self.assertEqual(len(rows), 462)
        self.assertTrue(all(row["episode_eligibility_status"] == "ELIGIBLE" for row in rows))

    def test_missing_attention_and_unavailable_pack_do_not_remove_episode(self) -> None:
        rows = {row["episode_id"]: row for row in impl.load_contract_application()}
        unavailable = rows["EP_BATCH_801c20917321a78fded4"]
        self.assertEqual(unavailable["episode_eligibility_status"], "ELIGIBLE")
        self.assertEqual(unavailable["attention_status"], "ATTENTION_UNAVAILABLE")
        self.assertEqual(unavailable["pack_a_status"], "PACK_UNAVAILABLE")

    def test_outcome_unavailable_exact_episode_stays_in_population(self) -> None:
        rows = {row["episode_id"]: row for row in impl.load_contract_application()}
        special = rows["EP_EVENT_757e72165d3ec05306a6"]
        self.assertEqual(special["episode_eligibility_status"], "ELIGIBLE")
        self.assertEqual(special["outcome_status_t15"], "OUTCOME_UNAVAILABLE")
        self.assertEqual(special["attention_status"], "ATTENTION_AVAILABLE")

    def test_total_expected_arm_count_is_2772(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = impl.build_ledgers(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            self.assertEqual(result["expected_gemini_arm_count"], 924)
            self.assertEqual(result["expected_openai_arm_count"], 924)
            self.assertEqual(result["expected_anthropic_arm_count"], 924)
            self.assertEqual(result["expected_pack_a_arm_count"], 1386)
            self.assertEqual(result["expected_pack_e_arm_count"], 1386)
            self.assertEqual(result["total_expected_arm_count"], 2772)

    def test_existing_and_blocked_arm_counts_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = impl.build_ledgers(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            self.assertEqual(result["existing_immutable_gemini_openai_arm_count"], 170)
            self.assertEqual(result["missing_anthropic_original_cohort_arm_count"], 94)
            self.assertEqual(result["blocked_reconstructable_arm_count"], 2046)
            self.assertEqual(result["blocked_unavailable_arm_count"], 438)
            self.assertEqual(result["ready_for_execution_arm_count"], 22)
            self.assertEqual(result["blocked_provider_contract_arm_count"], 96)
            self.assertEqual(
                result["existing_immutable_gemini_openai_arm_count"]
                + result["blocked_reconstructable_arm_count"]
                + result["blocked_unavailable_arm_count"]
                + result["ready_for_execution_arm_count"]
                + result["blocked_provider_contract_arm_count"],
                2772,
            )

    def test_runtime_forecast_and_evaluation_axes_stay_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = impl.build_ledgers(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            run_dir = Path(tmp) / result["run_id"]
            rows = [json.loads(line) for line in (run_dir / "expected_arm_ledger.jsonl").read_text().splitlines() if line.strip()]
            sample = rows[0]
            self.assertEqual(sample["runtime_status_if_executed"], "STATUS_UNKNOWN")
            self.assertEqual(sample["forecast_status_if_executed"], "INCOMPLETE")
            self.assertIn(sample["evaluation_status_t15"], {"NOT_APPLICABLE", "OUTCOME_UNAVAILABLE"})

    def test_deterministic_rerun_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = impl.build_ledgers(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            second = impl.build_ledgers(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            self.assertEqual(first["run_id"], second["run_id"])


if __name__ == "__main__":
    unittest.main()
