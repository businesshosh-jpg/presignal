"""Focused validation for the offline R6 paired-smoke authorization contract."""
from __future__ import annotations

import subprocess
import unittest

from automation import run_presignal_v21_designed_drift_r6_authorization_v1 as authorization


class R6AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.value = authorization.build_authorization()
        self.reports = self.value["reports"]

    def test_freeze_binding_and_authorization_fingerprint_are_reproducible(self):
        self.assertEqual(self.value["identity"]["route_b_freeze"]["freeze_fingerprint"], authorization.FREEZE_FINGERPRINT)
        self.assertEqual(self.value["fingerprint"], authorization.build_authorization()["fingerprint"])
        self.assertNotIn("/Users/", authorization.canonical(self.value["identity"]))

    def test_exact_gemini_two_arm_zero_retry_budget(self):
        scope = self.reports["authorized_provider_scope.json"]
        budget = self.reports["provider_call_budget.json"]
        self.assertEqual(scope["provider"], "Gemini")
        self.assertEqual(scope["model"], "gemini-2.5-flash-lite")
        self.assertEqual(scope["experimental_arms"], ["Pack A", "Pack E"])
        self.assertEqual(budget["total_forecast_calls"], 2)
        self.assertEqual(budget["arm_calls"], {"Pack A": 1, "Pack E": 1})
        self.assertEqual(budget["retry_count"], 0)
        self.assertFalse(budget["third_call_permitted"])
        self.assertFalse(budget["provider_substitution_permitted"])
        self.assertFalse(budget["model_substitution_permitted"])

    def test_episode_and_paired_comparability_are_narrow(self):
        episode = self.reports["authorized_episode_scope.json"]
        paired = self.reports["paired_arm_contract.json"]
        self.assertEqual(episode["authorized_episode_count"], 1)
        self.assertFalse(episode["historical_episode_permitted"])
        self.assertFalse(episode["synthetic_episode_permitted"])
        self.assertFalse(episode["batch_episode_selection_permitted"])
        self.assertTrue(all(value is True for key, value in paired.items() if key.startswith("same_")))
        self.assertEqual(paired["only_intentional_difference"], "input Pack")

    def test_outcome_evaluation_and_retries_remain_prohibited(self):
        prohibited = self.reports["outcome_evaluation_prohibition.json"]
        self.assertEqual(prohibited["outcome_construction"], "PROHIBITED")
        self.assertEqual(prohibited["evaluation"], "PROHIBITED")
        self.assertEqual(self.reports["authorized_acquisition_scope.json"]["retry_acquisition_permitted"], False)
        self.assertIn("any retry is attempted", self.reports["failure_stop_policy.json"]["conditions"])

    def test_live_targets_are_explicitly_unresolved_not_silently_selected(self):
        acquisition = self.reports["authorized_acquisition_scope.json"]
        self.assertEqual(acquisition["approved_source_environment"]["blocking_code"], authorization.DECISION)
        self.assertEqual(self.reports["authorized_google_read_scope.json"]["authorization_status"], "UNRESOLVED")
        self.assertEqual(self.reports["authorized_google_write_scope.json"]["authorization_status"], "UNRESOLVED")
        self.assertEqual(self.reports["authorized_evidence_destination.json"]["authorization_status"], "UNRESOLVED")
        self.assertEqual(self.reports["final_authorization_decision.json"]["decision"], authorization.DECISION)

    def test_historical_registry_reference_resolves_as_git_provenance_only(self):
        subprocess.check_call(
            ["git", "cat-file", "-e", "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py"],
            cwd=authorization.ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        reviewed = self.reports["authorized_acquisition_scope.json"]["approved_source_environment"]["evidence_reviewed"]
        self.assertTrue(any(item["path"].startswith("git:e5a0ff") for item in reviewed))

    def test_all_mandatory_stop_conditions_and_external_counts_are_present(self):
        stops = self.reports["failure_stop_policy.json"]["conditions"]
        for expected in ("freeze fingerprint mismatch", "approved-source environment unresolved", "provider-call budget would exceed two", "Outcome or evaluation boundary is reached"):
            self.assertIn(expected, stops)
        self.assertEqual(sum(self.reports["final_authorization_decision.json"]["external_access"].values()), 0)


if __name__ == "__main__":
    unittest.main()
