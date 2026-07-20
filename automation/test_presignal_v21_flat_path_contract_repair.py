from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import validate_presignal_v21_flat_path_contract_v1 as validate


class ProspectiveFlatContractTests(unittest.TestCase):
    def test_contract_is_explicitly_prospective_and_fingerprinted(self) -> None:
        spec = prospective.contract_spec()
        self.assertTrue(spec["prospective_only"])
        self.assertEqual(spec["parent_contract_version"], prospective.PARENT_CONTRACT_VERSION)
        self.assertIn("expected_pips_min must be 0", spec["provider_visible_flat_rule"])

    def test_version_selection_fails_closed(self) -> None:
        with self.assertRaisesRegex(prospective.ProspectiveFlatContractError, "MISSING_CONTRACT_VERSION"):
            prospective.resolve_contract(None, prospective=True)
        with self.assertRaisesRegex(prospective.ProspectiveFlatContractError, "HISTORICAL_CONTRACT"):
            prospective.resolve_contract(prospective.PARENT_CONTRACT_VERSION, prospective=True)
        with self.assertRaisesRegex(prospective.ProspectiveFlatContractError, "CONTRACT_SUBSTITUTION"):
            prospective.verify_resume_contract(prospective.PARENT_CONTRACT_VERSION, prospective.PROSPECTIVE_CONTRACT_VERSION)

    def test_frozen_validator_handles_flat_and_directional_fixtures(self) -> None:
        result = validate.fixture_validation()
        self.assertTrue(all(row["expected_valid"] == row["actual_valid"] for row in result["results"]))
        self.assertEqual(len([row for row in result["results"] if row["category"] == "invalid_flat_stages"]), 6)

    def test_prompt_is_explicit_and_pack_symmetric(self) -> None:
        result = validate.provider_dry_run()
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual({row["provider"] for row in result["providers"]}, {"Anthropic", "Gemini", "OpenAI"})
        for provider in result["providers"]:
            self.assertTrue(all(row["prompt_symmetry"]["passed"] for row in provider["results"]))

    def test_historical_neutral_range_rejections_are_preserved(self) -> None:
        cases = validate.neutral_range_cases()
        self.assertEqual(len(cases), 6)
        self.assertTrue(all(row["frozen_rejection_reason"] == "PATH_NEUTRAL_PIP_RANGE" for row in cases))

    def test_full_validation_writes_only_new_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, manifest = validate.run(
                Path(directory) / "repair",
                contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION,
            )
            self.assertTrue((path / "repair_manifest.json").exists())
            self.assertEqual(manifest["provider_calls"], 0)
            self.assertFalse(manifest["historical_artifacts_changed"])


if __name__ == "__main__":
    unittest.main()
