#!/usr/bin/env python3
"""Regression tests for the read-only frozen Step 6 paired analysis."""
from __future__ import annotations

import json
import unittest

from automation import analyze_presignal_v21_step6_paired_batch_v1 as analysis


class FrozenBatchPairedAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = analysis.run(batch_run_id="STEP6-BATCH-f718192a7566138c3fda", verify_only=True)

    def test_frozen_population_reconciles_without_external_calls(self) -> None:
        verification = self.result["verification"]
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["approved_pair_count"], 21)
        self.assertEqual(verification["completion_counts"], {
            "COMPLETE_PAIRED": 14, "INCOMPLETE_BOTH": 3, "INCOMPLETE_PACK_A": 3, "INCOMPLETE_PACK_E": 1,
        })
        self.assertEqual(len(self.result["complete_rows"]), 14)
        self.assertEqual(len(self.result["rejected"]), 10)

    def test_primary_contingency_and_exact_paired_test_are_stable(self) -> None:
        primary = self.result["primary"]
        self.assertEqual((primary["both_correct"], primary["pack_a_only_correct"], primary["pack_e_only_correct"], primary["both_incorrect"]), (3, 3, 1, 7))
        self.assertEqual((primary["pack_a_correct"], primary["pack_e_correct"]), (6, 4))
        self.assertAlmostEqual(primary["paired_risk_difference_pack_a_minus_pack_e"], 2 / 14)
        self.assertAlmostEqual(primary["exact_mcnemar_two_sided_p_value"], 0.625)

    def test_episode_cluster_permutation_swaps_whole_episode_clusters(self) -> None:
        clustered = self.result["cluster"]
        self.assertEqual(clustered["method"], "EXACT_EPISODE_LEVEL_LABEL_SWAP_ENUMERATION")
        self.assertEqual(clustered["unique_episode_clusters"], 10)
        self.assertEqual(clustered["possible_permutations"], 1024)
        self.assertAlmostEqual(clustered["two_sided_p_value"], 0.625)
        self.assertIn(3, clustered["cluster_pair_counts"].values())

    def test_missingness_and_sensitivity_bounds_preserve_observed_arms(self) -> None:
        table = self.result["completion_table"]
        bounds = self.result["bounds"]
        self.assertEqual(table, {"both_accepted": 14, "pack_a_only_accepted": 1, "pack_e_only_accepted": 3, "neither_accepted": 3, "exact_paired_completion_mcnemar_p_value": 0.625})
        self.assertAlmostEqual(bounds["worst_case_pack_a_difference"], -3 / 21)
        self.assertAlmostEqual(bounds["best_case_pack_a_difference"], 7 / 21)
        self.assertFalse(bounds["effect_sign_survives_bounds"])

    def test_rejected_outputs_remain_excluded_and_produce_one_narrow_candidate(self) -> None:
        diagnostics = self.result["diagnostics"]
        self.assertEqual(diagnostics["rejected_response_count"], 10)
        self.assertEqual(diagnostics["frozen_rejection_reason_counts"], {"PATH_NEUTRAL_PIP_RANGE": 6, "PATH_PIPS_MIN": 1, "PREDICTION_REVERSAL_FLAG": 3})
        self.assertEqual(diagnostics["future_targeted_repair_candidates"], {"PROSPECTIVE_FLAT_STAGE_ZERO_PIP_CONSTRAINT": 6})
        self.assertTrue(all(row["historical_disposition"] == "REMAIN_EXCLUDED" for row in self.result["rejected"]))

    def test_attention_and_decision_are_frozen_evidence_only(self) -> None:
        attention = self.result["attention"]
        self.assertEqual(attention["attention_scope_adequate"], 14)
        self.assertEqual(attention["extension_candidates"], 0)
        self.assertEqual(self.result["interpretation"]["pack_superiority_claim"], "NOT_SUPPORTED")
        self.assertEqual(self.result["decision"]["decision"], "V2_1_STEP7_TARGETED_OUTPUT_CONTRACT_REPAIR_REQUIRED")

    def test_repeated_verify_only_analysis_is_identical(self) -> None:
        repeated = analysis.run(batch_run_id="STEP6-BATCH-f718192a7566138c3fda", verify_only=True)
        self.assertEqual(self.result["analysis_fingerprint"], repeated["analysis_fingerprint"])

    def test_exact_mcnemar_edge_cases(self) -> None:
        self.assertEqual(analysis.exact_mcnemar_pvalue(0, 0), 1.0)
        self.assertEqual(analysis.exact_mcnemar_pvalue(3, 1), 0.625)

    def test_written_manifest_records_zero_external_operations(self) -> None:
        run_dir = analysis.OUTPUT_ROOT / self.result["analysis_run_id"]
        manifest = json.loads((run_dir / "analysis_manifest.json").read_text())
        self.assertEqual(manifest["external_calls"], {
            "provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0,
        })


if __name__ == "__main__":
    unittest.main()
