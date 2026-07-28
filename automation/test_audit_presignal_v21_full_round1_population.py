#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_full_round1_population as audit


class FullRound1PopulationAuditTest(unittest.TestCase):
    def test_may_july_boundaries_are_inclusive_exclusive(self) -> None:
        self.assertTrue(audit.in_range("2024-05-01T00:00:00Z"))
        self.assertTrue(audit.in_range("2024-07-31T23:59:59Z"))
        self.assertFalse(audit.in_range("2024-04-30T23:59:59Z"))
        self.assertFalse(audit.in_range("2024-08-01T00:00:00Z"))

    def test_existing_pack_ready_subset_explains_47_plus_removed_one(self) -> None:
        pack_a, pack_e = audit.load_step5_inputs()
        existing = audit.load_existing_47()
        admission = audit.load_population_admission()
        ready_ids = set(pack_a) & set(pack_e)
        self.assertEqual(len(ready_ids), 48)
        self.assertEqual(len(existing), 47)
        excluded_ready = [episode_id for episode_id in ready_ids if admission[episode_id]["population_status"] != "ELIGIBLE"]
        self.assertEqual(excluded_ready, ["EP_EVENT_757e72165d3ec05306a6"])

    def test_round_population_contains_462_candidates_and_374_eligible(self) -> None:
        rows, _ = audit.load_round_population()
        admission = audit.load_population_admission()
        self.assertEqual(len(rows), 462)
        self.assertEqual(sum(item["population_status"] == "ELIGIBLE" for item in admission.values()), 374)
        self.assertEqual(sum(item["population_status"] == "EXCLUDED_LINEAGE_UNSAFE" for item in admission.values()), 73)
        self.assertEqual(sum(item["population_status"] == "EXCLUDED_OUTCOME_UNAVAILABLE" for item in admission.values()), 15)

    def test_existing_47_are_not_earliest_eligible_population(self) -> None:
        rows, _ = audit.load_round_population()
        admission = audit.load_population_admission()
        existing = audit.load_existing_47()
        earliest_existing = min(row["release_ts"] for row in rows if row["episode_id"] in existing)
        earlier_eligible = [
            row["episode_id"]
            for row in rows
            if row["release_ts"] < earliest_existing and admission[row["episode_id"]]["population_status"] == "ELIGIBLE"
        ]
        self.assertTrue(earlier_eligible)

    def test_omission_reason_prefers_attention_then_explicit_rule(self) -> None:
        admission = {
            "population_status": "ELIGIBLE",
            "historical_attention_status": "ATTENTION_LINEAGE_MISSING",
        }
        self.assertEqual(
            audit.omission_reason(admission=admission, episode_id="EP_X", source_pack_ready_ids=set()),
            "PREVIOUSLY_EXCLUDED_BY_ATTENTION_SELECTION",
        )
        explicit = {
            "population_status": "EXCLUDED_OUTCOME_UNAVAILABLE",
            "historical_attention_status": "ATTENTION_LINEAGE_AVAILABLE",
        }
        self.assertEqual(
            audit.omission_reason(admission=explicit, episode_id="EP_Y", source_pack_ready_ids=set()),
            "PREVIOUSLY_EXCLUDED_BY_EXPLICIT_RULE",
        )

    def test_build_audit_writes_deterministic_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = audit.build_audit(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            run_dir = Path(tmp) / result["run_id"]
            self.assertTrue((run_dir / "run_manifest.json").exists())
            self.assertTrue((run_dir / "population_summary.json").exists())
            summary = json.loads((run_dir / "population_summary.json").read_text())
            self.assertEqual(summary["summary_counts"]["candidate_episodes"], 462)
            self.assertEqual(summary["summary_counts"]["existing_47_exact_match_count"], 47)
            self.assertEqual(summary["summary_counts"]["additional_episode_count"], 415)
            self.assertEqual(summary["summary_counts"]["deterministic_cutoff_count"], 462)
            self.assertEqual(summary["summary_counts"]["existing_pack_a_availability_count"], 48)
            self.assertEqual(summary["summary_counts"]["existing_pack_e_availability_count"], 48)
            self.assertEqual(summary["summary_counts"]["reconstructable_missing_pack_a_count"], 341)
            self.assertEqual(summary["summary_counts"]["reconstructable_missing_pack_e_count"], 341)
            self.assertEqual(result["projected_gemini_arm_count"], 748)
            self.assertEqual(result["projected_openai_arm_count"], 748)
            self.assertEqual(result["projected_anthropic_arm_count"], 748)
            self.assertEqual(result["total_projected_six_arm_matrix_count"], 2244)


if __name__ == "__main__":
    unittest.main()
