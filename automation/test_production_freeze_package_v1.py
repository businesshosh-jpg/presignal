from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import build_simplified_replay_package_v1 as freezer
from automation.build_simplified_replay_package_v1 import (
    SNAPSHOT,
    freeze,
    freeze_production_package,
    verify_package_manifest,
    verify_whole_package_fingerprint,
)
from automation.run_simplified_replay_canary_v1 import execute


def production_inputs(root: Path, package_id: str = "PRODUCTION-FREEZE-TEST") -> dict:
    return {
        "scientific_snapshot_path": SNAPSHOT,
        "durable_output_root": root,
        "package_id": package_id,
        "immutable_apps_script_version": 78,
        "bridge_source_fingerprint": "bridge-sha",
        "prediction_runner_fingerprint": "runner-sha",
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
    }


class ProductionFreezePackageTest(unittest.TestCase):
    def test_production_package_finalizes_and_verifies_full_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = freeze_production_package(**production_inputs(root))
            package = root / "PRODUCTION-FREEZE-TEST"

            self.assertTrue(package.is_dir())
            self.assertFalse(list(root.glob(".PRODUCTION-FREEZE-TEST.tmp-*")))
            self.assertEqual(manifest["counts"]["sessions"], 239)
            self.assertEqual(manifest["counts"]["identities"], 1434)
            self.assertTrue(verify_package_manifest(package))
            self.assertTrue(verify_whole_package_fingerprint(package))

            binding = json.loads((package / "binding" / "immutable_deployment_binding.json").read_text())
            self.assertEqual(binding["apps_script_version"], 78)
            self.assertTrue(binding["version_is_immutable"])
            self.assertFalse(binding["deployment_performed"])

            fingerprints = json.loads((package / "fingerprints" / "implementation_fingerprints.json").read_text())
            self.assertEqual(fingerprints["bridge_source_fingerprint"], "bridge-sha")
            self.assertEqual(fingerprints["prediction_runner_fingerprint"], "runner-sha")
            self.assertEqual(fingerprints["contract_fingerprint"], "contract-sha")
            self.assertEqual(fingerprints["executor_fingerprint"], "executor-sha")

    def test_existing_package_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "EXISTING").mkdir()
            inputs = production_inputs(root, "EXISTING")
            with self.assertRaisesRegex(ValueError, "EXISTING_FINAL_PACKAGE_ID"):
                freeze_production_package(**inputs)

    def test_missing_immutable_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = production_inputs(Path(tmp))
            inputs["immutable_apps_script_version"] = None
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_APPS_SCRIPT_VERSION"):
                freeze_production_package(**inputs)

    def test_missing_fingerprint_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = production_inputs(Path(tmp))
            inputs["executor_fingerprint"] = ""
            with self.assertRaisesRegex(ValueError, "IMPLEMENTATION_FINGERPRINT_MISSING"):
                freeze_production_package(**inputs)

    def test_count_mismatch_fails_before_finalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_snapshot = root / "snapshot"
            shutil.copytree(SNAPSHOT, bad_snapshot)
            population_path = bad_snapshot / "authoritative_forecast_population.jsonl"
            population = population_path.read_text().splitlines()
            population_path.write_text("\n".join(population[:-1]) + "\n")

            inputs = production_inputs(root / "out")
            inputs["scientific_snapshot_path"] = bad_snapshot
            with self.assertRaisesRegex(ValueError, "SCIENTIFIC_COUNTS_MISMATCH"):
                freeze_production_package(**inputs)
            self.assertFalse((root / "out" / "PRODUCTION-FREEZE-TEST").exists())

    def test_token_ambiguity_fails(self):
        members = [
            {"session_id": "s1", "event_id": "event-a", "indicator_name": "A"},
            {"session_id": "s1", "event_id": "event-a", "indicator_name": "A duplicate"},
        ]
        with patch.object(freezer, "driver_options", return_value=[{"token": "DRV_one", "event_id": "event-a", "label": "A"}]):
            with self.assertRaisesRegex(ValueError, "TOKEN_RESOLVES_MULTIPLE_MEMBERS"):
                freezer._build_token_records(members)

    def test_dry_run_behavior_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "dry"
            manifest = freeze(package)
            self.assertEqual(manifest["counts"]["identities"], 1434)

            population = [json.loads(line) for line in (package / "snapshot" / "authoritative_forecast_population.jsonl").read_text().splitlines()]
            identity = population[0]
            members = [
                json.loads(line)
                for line in (package / "snapshot" / "authoritative_session_members.jsonl").read_text().splitlines()
                if json.loads(line)["session_id"] == identity["session_id"]
            ]
            audit = json.loads((package / "token_mapping_audit.json").read_text())[identity["session_id"]]
            raw = {
                "primary_driver_token": audit[0]["token"],
                "secondary_driver_token": "",
                "final_usdjpy_direction": "UP",
                "reaction_strength": "MODERATE",
                "confidence": 0.5,
                "primary_thesis": "x",
                "secondary_thesis": "",
                "reasoning_steps": ["a", "b"],
            }
            response = {
                "actual_provider": identity["provider"],
                "actual_model": identity["model"],
                "raw_output": json.dumps(raw),
            }
            self.assertTrue(execute(package, identity, members, response))


if __name__ == "__main__":
    unittest.main()
