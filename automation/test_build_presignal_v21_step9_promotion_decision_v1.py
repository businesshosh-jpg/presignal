from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_step9_promotion_decision_v1 as step9


class PromotionDecisionTests(unittest.TestCase):
    def test_frozen_evidence_and_prospective_contract_verify(self) -> None:
        evidence = step9.verify_evidence()
        self.assertEqual(evidence["accepted_forecasts"], 32)
        self.assertEqual(evidence["rejected_responses"], 10)
        self.assertEqual(evidence["unique_complete_episodes"], 10)
        self.assertTrue(evidence["historical_trees_unchanged"])

    def test_indeterminate_evidence_defers_promotion_without_rejecting_architecture(self) -> None:
        evidence = step9.verify_evidence()
        content = step9.artifacts(evidence)
        self.assertEqual(content["promotion_decision.json"]["decision"], step9.DECISION)
        self.assertEqual(content["promotion_decision.json"]["main_path_promotion"], "DEFERRED")
        self.assertEqual(content["scientific_validity_assessment.json"]["status"], "VALID_FOR_PROSPECTIVE_SHADOW_REPLICATION")
        self.assertEqual(content["v3_status.json"]["status"], "NOT_AUTHORIZED")

    def test_shadow_plan_is_bounded_paired_clustered_and_non_optimizing(self) -> None:
        plan = step9.prospective_population_plan()
        endpoint = step9.artifacts(step9.verify_evidence())["prospective_endpoint_preregistration.json"]
        self.assertEqual(plan["minimum_interpretable_unique_episodes"], 40)
        self.assertEqual(plan["target_unique_episodes"], 60)
        self.assertEqual(plan["maximum_bounded_unique_episodes"], 80)
        self.assertEqual(endpoint["primary_endpoint"], "15-minute direction correctness")
        self.assertEqual(endpoint["primary_cluster"], "Episode")
        self.assertIn("prompt optimization based on accuracy", plan["prohibited_checkpoint_actions"])

    def test_decision_run_is_deterministic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, manifest_a = step9.run(Path(directory) / "a")
            second, manifest_b = step9.run(Path(directory) / "b")
            self.assertEqual(manifest_a["decision_fingerprint"], manifest_b["decision_fingerprint"])
            self.assertEqual(manifest_a["external_calls"]["provider"], 0)
            self.assertTrue((first / "prospective_shadow_authorization.json").exists())
            self.assertTrue((second / "future_promotion_criteria.json").exists())


if __name__ == "__main__":
    unittest.main()
