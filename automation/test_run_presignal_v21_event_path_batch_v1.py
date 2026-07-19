#!/usr/bin/env python3
"""Regression tests for the dry-run-only v2.1 controlled batch preparation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from automation import run_presignal_v21_event_path_batch_v1 as batch


PREP = batch.PREPARATION_ROOT / "STEP6-BATCH-PREP-ccee43d7c9d8bf715f71"


class ControlledBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs_a = batch.rows(batch.STEP5 / "event_path_forecast_inputs_pack_a.jsonl")
        cls.inputs_e = batch.rows(batch.STEP5 / "event_path_forecast_inputs_pack_e.jsonl")
        cls.reconciliation = batch.reconcile_population(cls.inputs_a, cls.inputs_e)

    def test_all_104_pairs_have_one_explicit_category(self) -> None:
        self.assertEqual(len(self.inputs_a), 104)
        self.assertEqual(len(self.inputs_e), 104)
        self.assertEqual(len(self.reconciliation), 104)
        statuses = {row["eligibility_status"] for row in self.reconciliation}
        self.assertIn("BATCH_ELIGIBLE", statuses)
        self.assertEqual(sum(1 for row in self.reconciliation if row["eligibility_status"] == "BATCH_ELIGIBLE"), 21)
        self.assertTrue(all(row["eligibility_status"] == "BATCH_ELIGIBLE" or row["exclusion_reason"] for row in self.reconciliation))

    def test_outcome_values_do_not_affect_eligibility(self) -> None:
        first = self.reconciliation[0]
        self.assertNotIn("direction", batch.canonical_json(first).lower())
        self.assertNotIn("pips", batch.canonical_json(first).lower())
        self.assertIn("outcome_identity", first)

    def test_eligible_pairs_preflight_without_provider_calls(self) -> None:
        by_a = {batch.input_key(row): row for row in self.inputs_a}
        by_e = {batch.input_key(row): row for row in self.inputs_e}
        eligible = [row for row in self.reconciliation if row["eligibility_status"] == "BATCH_ELIGIBLE"]
        results = [batch.preflight_pair(by_a[(row["episode_id"], row["provider"], row["model"])], by_e[(row["episode_id"], row["provider"], row["model"])], row, "TEST") for row in eligible]
        self.assertTrue(all(row["status"] == "PASS" for row in results))
        self.assertTrue(all(row["provider_calls"] == 0 and row["apps_script_calls"] == 0 for row in results))
        self.assertTrue(all(row["prompt_symmetry"]["passed"] for row in results))

    def test_contract_freeze_matches_the_validated_single_pair(self) -> None:
        frozen = batch.batch_contract()
        self.assertEqual(frozen["single_pair_reference_run_id"], "STEP6-SINGLE-20260719T175850564590Z")
        self.assertEqual(frozen["runner_commit"], "c9606c9ec7515946348c4e922aac5b86c30b10ba")
        self.assertEqual(frozen["permitted_prompt_differences"], sorted(batch.single.ALLOWED_PROMPT_DIFFERENCES))
        self.assertEqual(frozen["required_horizons"], [5, 15, 30, 60])
        self.assertTrue(frozen["batch_contract_fingerprint"].startswith("sha256:"))

    def test_known_transport_defects_are_prevented_or_hard_stopped(self) -> None:
        defects = batch.known_transport_defects()
        self.assertEqual({row["defect_id"] for row in defects}, {"D1", "D2", "D3", "D4"})
        self.assertTrue(all(row["classification"] == "NON_SCIENTIFIC_BATCH_CONTROL" for row in defects))
        self.assertTrue(all(row["hard_stop_condition"] for row in defects))

    def test_static_capability_is_not_a_live_provider_call(self) -> None:
        capability = batch.provider_capability("Gemini", "gemini-2.5-flash-lite")
        self.assertEqual(capability["static_status"], "STATIC_CAPABLE")
        self.assertTrue(capability["exact_requested_model_is_enforced"])
        self.assertFalse(capability["live_call_performed"])

    def test_duplicate_and_retry_guards_are_hard_stops(self) -> None:
        budget = {"maximum_calls_per_pair": 4}
        accepted = {"accepted_forecast_count": 1, "provider_call_count": 1, "arms": {"PACK_A": {"state": "FORECAST_ACCEPTED", "accepted_forecast_identity": "ACC", "request_fingerprint": "same"}}}
        self.assertEqual(batch.can_dispatch_arm(accepted, "PACK_A", "same", budget), (False, "ACCEPTED_ARM_ALREADY_FROZEN"))
        mutated = {"accepted_forecast_count": 0, "provider_call_count": 0, "arms": {"PACK_A": {"state": "TRANSPORT_FAILED", "request_fingerprint": "old"}}}
        self.assertEqual(batch.can_dispatch_arm(mutated, "PACK_A", "new", budget), (False, "REQUEST_MUTATION_BETWEEN_ATTEMPTS"))
        self.assertEqual(batch.can_dispatch_arm({"arms": {}}, "PACK_A", "new", budget), (True, "DISPATCH_ALLOWED"))

    def test_outcome_attachment_requires_both_frozen_forecasts(self) -> None:
        with self.assertRaisesRegex(batch.BatchPreparationError, "EARLY_OUTCOME_ATTACHMENT_REJECTED"):
            batch.assert_outcome_attachment_allowed({"arms": {"PACK_A": {"state": "FORECAST_ACCEPTED"}, "PACK_E": {"state": "PREFLIGHTED"}}}, "OUT", "OUT")
        batch.assert_outcome_attachment_allowed({"arms": {"PACK_A": {"state": "FORECAST_ACCEPTED"}, "PACK_E": {"state": "FORECAST_ACCEPTED"}}}, "OUT", "OUT")

    def test_dry_run_artifacts_are_complete_and_safe(self) -> None:
        required = {
            "step5_population_reconciliation.jsonl", "step5_population_summary.json", "eligible_batch_manifest.json", "excluded_pair_ledger.jsonl",
            "batch_contract_manifest.json", "single_pair_contract_comparison.json", "known_transport_defects.json", "transport_prevention_validation.json",
            "provider_model_capability_manifest.json", "provider_call_budget.json", "arm_order_manifest.json", "restart_state_contract.json",
            "batch_execution_plan.json", "batch_preflight_results.jsonl", "batch_preflight_summary.json", "prompt_fingerprint_manifest.jsonl",
            "request_fingerprint_manifest.jsonl", "leakage_validation.json", "attention_scope_adequacy_contract.json", "dry_run_manifest.json",
        }
        self.assertTrue(PREP.exists())
        self.assertEqual(required, {path.name for path in PREP.iterdir() if path.is_file()})
        dry = json.loads((PREP / "dry_run_manifest.json").read_text())
        self.assertEqual(dry["provider_calls"], 0)
        self.assertEqual(dry["apps_script_calls"], 0)
        self.assertEqual(dry["google_sheets_writes"], 0)

    def test_arm_order_is_balanced_and_input_order_independent(self) -> None:
        eligible = [row for row in self.reconciliation if row["eligibility_status"] == "BATCH_ELIGIBLE"]
        forward = [batch.arm_order(row["pair_id"]) for row in eligible]
        reverse = [batch.arm_order(row["pair_id"]) for row in reversed(eligible)]
        self.assertEqual(sorted(forward), sorted(reverse))
        self.assertLessEqual(abs(sum(row[0] == "PACK_A" for row in forward) - sum(row[0] == "PACK_E" for row in forward)), 1)


if __name__ == "__main__":
    unittest.main()
