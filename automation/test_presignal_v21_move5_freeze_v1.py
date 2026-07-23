"""Focused verification of the deterministic Move 5 Route B freeze."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from automation import run_presignal_v21_move5_freeze_v1 as freeze


ROOT = Path(__file__).resolve().parents[1]


class RouteBCapabilityFreezeTests(unittest.TestCase):
    def setUp(self):
        self.value = freeze.build_freeze()
        self.reports = freeze.reports()

    def test_inventory_paths_checksums_and_git_blobs_resolve(self):
        self.assertGreater(self.value["inventory"].__len__(), 0)
        for row in self.value["inventory"]:
            path = ROOT / row["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(row["file_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            subprocess.check_call(["git", "cat-file", "-e", row["git_blob_sha"] + "^{blob}"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_implementation_commit_and_proofs_are_bound_exactly(self):
        self.assertEqual(self.value["identity"]["implementation_commit"], freeze.IMPLEMENTATION_COMMIT)
        self.assertEqual(self.value["historical"]["actual_fingerprint"], freeze.HISTORICAL_FINGERPRINT)
        self.assertTrue(self.value["historical"]["exact_fingerprint_match"])
        self.assertEqual(self.value["native"]["decision"], "NATIVE_PROSPECTIVE_EPISODE_TO_PACK_CONTRACT_VALIDATED_MOVE_5_READY")

    def test_dependency_closure_is_complete_and_externals_are_outside_compute(self):
        self.assertEqual(self.value["dependency_counts"], {"MIGRATE": 3, "ADAPT": 3, "EXTERNAL_INTERFACE": 2, "TEST_STUB": 1, "EXCLUDE": 7})
        report = self.reports["dependency_closure_report.json"]
        self.assertEqual(report["unclassified_dependencies"], 0)
        self.assertTrue(report["closure_complete"])
        self.assertNotIn("google", " ".join(report["pure_compute_imports"]).lower())

    def test_freeze_fingerprint_is_reproducible_and_path_independent(self):
        second = freeze.build_freeze()
        self.assertEqual(self.value["fingerprint"], second["fingerprint"])
        self.assertNotIn(str(ROOT), freeze._json(self.value["identity"]))
        self.assertNotIn("/Users/", freeze._json(self.value["identity"]))

    def test_r6_boundary_has_required_fields_and_explicit_unresolved_authority(self):
        boundary = self.reports["r6_authorized_boundary.json"]
        for field in ("authorized_episode_count", "forecast_provider_call_count", "provider_scope", "retry_count", "acquisition_scope", "google_read_scope", "google_write_scope", "writer_destination", "forecast_execution_authorization", "outcome_authorization", "evaluation_authorization"):
            self.assertIn(field, boundary)
        self.assertEqual(boundary["authorized_episode_count"], 1)
        self.assertEqual(boundary["forecast_provider_call_count"], 2)
        self.assertEqual(boundary["provider_scope"], "REQUIRES_EXPLICIT_R6_AUTHORIZATION")

    def test_stop_writer_and_external_declarations_fail_closed(self):
        stops = self.reports["r6_stop_conditions.json"]["conditions"]
        self.assertGreaterEqual(len(stops), 17)
        writer = self.reports["writer_boundary_declaration.json"]
        self.assertFalse(writer["compute_performs_persistence"])
        self.assertTrue(writer["writer_is_caller_controlled"])
        self.assertFalse(writer["production_writer_implemented_in_move5"])
        self.assertEqual(sum(self.reports["external_access_declaration.json"].values()), 0)


if __name__ == "__main__":
    unittest.main()
