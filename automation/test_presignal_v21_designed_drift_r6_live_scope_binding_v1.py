"""Focused offline tests for the versioned R6 live-scope binding evidence."""
from __future__ import annotations

import hashlib
import subprocess
import unittest

from automation import run_presignal_v21_designed_drift_r6_live_scope_binding_v1 as binding


class R6LiveScopeBindingTests(unittest.TestCase):
    def setUp(self):
        self.value = binding.build_binding()
        self.reports = self.value["reports"]
        self.rows = self.reports["live_scope_candidate_inventory.json"]["candidates"]

    def test_candidate_matrix_is_deterministic_and_references_resolve(self):
        again = binding.build_binding()
        self.assertEqual(self.reports["live_scope_compatibility_matrix.json"], again["reports"]["live_scope_compatibility_matrix.json"])
        for row in self.rows:
            artifact = row["artifact"]
            if artifact["path"].startswith("git:"):
                subprocess.check_call(["git", "cat-file", "-e", artifact["path"][4:]], cwd=binding.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                raw = subprocess.check_output(["git", "show", artifact["path"][4:]], cwd=binding.ROOT)
                self.assertEqual(artifact["file_checksum"], "sha256:" + hashlib.sha256(raw).hexdigest())
            else:
                self.assertTrue((binding.ROOT / artifact["path"]).is_file())
                self.assertEqual(artifact["file_checksum"], binding._file_checksum(artifact["path"]))

    def test_fixture_and_historical_registry_cannot_be_selected(self):
        fixture = next(row for row in self.rows if row["identity"] == "MOVE4C_APPROVED_SOURCES_V1")
        registry = next(row for row in self.rows if row["identity"] == "AKSR_V1_INITIAL_REGISTRY")
        self.assertEqual(fixture["authority_status"], "TEST_ONLY")
        self.assertFalse(fixture["selected"])
        self.assertEqual(registry["authority_status"], "HISTORICAL_CAPABILITY_ONLY")
        self.assertFalse(registry["selected"])

    def test_google_targets_are_singular_only_when_explicitly_bound(self):
        for name in ("google_read_target_binding.json", "google_write_target_binding.json"):
            value = self.reports[name]
            self.assertIsNone(value["selected_identity"])
            self.assertEqual(value["binding_status"], "REQUIRES_EXPLICIT_USER_AUTHORIZATION")
            self.assertGreaterEqual(len(value["candidate_identities"]), 1)

    def test_legacy_benchmark_fails_r6_write_safety(self):
        legacy = next(row for row in self.rows if row["candidate_type"] == "GOOGLE_WRITE_TARGET" and row["identity"].startswith("LEGACY_BENCHMARK"))
        self.assertEqual(legacy["isolation_status"], "NOT_R6_WRITE_SAFE")
        self.assertIn("LEGACY_BENCHMARK_TARGET_NOT_R6_WRITE_SAFE", legacy["rejection_reason"])

    def test_v1_evidence_is_preserved_and_blocked_v2_identity_reproduces(self):
        prior = self.value["identity"]["previous_authorization"]
        self.assertEqual(prior["authorization_fingerprint"], binding.V1_FINGERPRINT)
        self.assertEqual(self.value["fingerprint"], binding.build_binding()["fingerprint"])
        self.assertFalse(self.value["identity"]["execution_authorized"])
        self.assertNotIn("/Users/", binding.canonical(self.value["identity"]))

    def test_experiment_budget_and_later_stages_remain_frozen(self):
        scope = self.value["identity"]["forecast_scope"]
        self.assertEqual(scope, {"provider": "Gemini", "model": "gemini-2.5-flash-lite", "arms": ["Pack A", "Pack E"], "call_budget": 2, "retry_count": 0})
        self.assertTrue(self.value["identity"]["outcome_prohibited"])
        self.assertTrue(self.value["identity"]["evaluation_prohibited"])
        self.assertEqual(sum(self.reports["final_live_scope_binding_decision.json"]["external_access"].values()), 0)


if __name__ == "__main__":
    unittest.main()
