#!/usr/bin/env python3
"""Offline regression coverage for the Move 4 fixture-admissibility gate."""
from __future__ import annotations

import builtins
import copy
import inspect
import json
import unittest
from pathlib import Path

from automation import run_presignal_v21_move4_proof_v1 as proof


ROOT = Path(__file__).resolve().parents[1]


class Move4ProofTests(unittest.TestCase):
    def test_frozen_fixture_sources_and_historical_fingerprint_validate(self):
        result = proof.run_offline_move4_fixture_admissibility(ROOT)
        self.assertEqual(result["expected_fingerprint"], proof.EXPECTED_FINGERPRINT)
        self.assertTrue(result["historical_fingerprint_matches_expected"])
        self.assertEqual(result["fixture_components"]["pack_input"]["pack_item_count"], 15)

    def test_fixture_manifest_checksums_validate(self):
        manifest = json.loads((ROOT / "contracts/presignal_v21_event_path/move4_episode_to_pack_fixture_manifest.json").read_text())
        components = {row["component"]: row for row in manifest["fixture_components"]}
        self.assertEqual(proof.file_sha256(ROOT / proof.EPISODE_SOURCE), components["canonical Event Episode"]["checksum"].removeprefix("sha256:"))
        self.assertEqual(proof.file_sha256(ROOT / proof.PACK_SOURCE), components["historical Pack E input and raw Gemini Request response"]["checksum"].removeprefix("sha256:"))

    def test_earliest_divergence_is_the_canonical_episode_cutoff(self):
        result = proof.run_offline_move4_fixture_admissibility(ROOT)
        divergence = result["first_divergence"]
        self.assertEqual(result["status"], "FIXTURE_INPUT_MISMATCH")
        self.assertEqual(divergence["object"], "forecast_cutoff_ts")
        self.assertEqual(divergence["expected_value"], "2024-05-08T06:50:00Z")
        self.assertEqual(divergence["actual_value"], "2024-05-08T11:00:00Z")
        self.assertFalse(divergence["representational_only"])

    def test_three_runs_are_deterministic_and_return_only(self):
        results = [proof.run_offline_move4_fixture_admissibility(ROOT) for _ in range(3)]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(sum(results[0]["external_access_counts"].values()), 0)

    def test_fixture_mutation_changes_historical_fingerprint(self):
        result = proof.run_offline_move4_fixture_admissibility(ROOT)
        mutated = copy.deepcopy(result)
        mutated["fixture_components"]["pack_input"]["pack_item_count"] += 1
        self.assertNotEqual(proof.sha256(result["fixture_components"]), proof.sha256(mutated["fixture_components"]))

    def test_runner_has_no_external_or_destination_capability(self):
        source = inspect.getsource(proof)
        for forbidden in ("build_sheets_service", "load_credentials", "requests.", "urllib", "socket.", "subprocess", "write_text(", "write_bytes(", "mkdir("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("production", source.lower().replace("production_writes", ""))


if __name__ == "__main__":
    unittest.main()
