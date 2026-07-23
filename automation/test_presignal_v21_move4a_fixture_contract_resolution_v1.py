"""Focused offline checks for the Move 4A evidence classification."""

from pathlib import Path
import unittest

from automation import presignal_v21_move4a_fixture_contract_resolution_v1 as resolution
from automation.presignal_v21_move4a_fixture_contract_resolution_v1 import (
    EXPECTED_FINGERPRINT,
    reports,
    resolve,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs/presignal_v21_designed_drift_move4a/MOVE4A-20260723-fixture-contract-resolution"


class Move4AFixtureContractResolutionTests(unittest.TestCase):
    def setUp(self):
        self.evidence = resolve(ROOT)
        self.reports = reports(ROOT)

    def test_referenced_evidence_paths_and_checksums_exist_and_validate(self):
        for relative_path, checksum in self.evidence["source_checksums"].items():
            self.assertTrue((ROOT / relative_path).is_file())
            self.assertEqual(checksum, f"sha256:{__import__('hashlib').sha256((ROOT / relative_path).read_bytes()).hexdigest()}")

    def test_historical_fingerprint_is_independently_reproduced(self):
        self.assertEqual(self.evidence["fingerprint"], EXPECTED_FINGERPRINT)
        self.assertTrue(self.evidence["fingerprint_matches_frozen"])

    def test_cutoffs_and_attention_are_traced_without_conversion(self):
        cutoff = self.reports["cutoff_contract_resolution.json"]
        attention = self.reports["attention_contract_resolution.json"]
        self.assertEqual(cutoff["historical_0650z"]["value"], "2024-05-08T06:50:00Z")
        self.assertEqual(cutoff["episode_1100z"]["value"], "2024-05-08T11:00:00Z")
        self.assertFalse(cutoff["same_scientific_boundary"])
        self.assertEqual(attention["historical_state"], "WATCH")
        self.assertFalse(attention["conversion_permitted"])

    def test_request_lineage_and_acquisition_classification_are_exact(self):
        self.assertEqual(self.evidence["provider_origins"], ["Anthropic", "Gemini", "OpenAI"])
        acquisition = self.reports["acquisition_evidence_resolution.json"]
        self.assertEqual(acquisition["classification"], "DERIVED_PACK_ITEMS_ONLY")
        self.assertFalse(acquisition["source_level_records_present"])
        self.assertFalse(acquisition["lossless_native_adaptation_possible"])

    def test_decision_matches_compatibility_matrix_and_committed_reports(self):
        decision = self.reports["final_fixture_contract_decision.json"]["decision"]
        matrix = self.reports["candidate_fixture_compatibility_matrix.json"]
        self.assertEqual(decision, "HISTORICAL_AND_PROSPECTIVE_PROOF_CONTRACTS_MUST_BE_SEPARATED")
        self.assertEqual(matrix["fully_compatible_fixture_count"], 0)
        self.assertTrue((REPORT_DIR / "final_fixture_contract_decision.json").is_file())

    def test_resolution_is_pure_and_has_no_external_call_surface(self):
        # The resolver imports only standard-library parsing and hashing and exposes no clients/writers.
        self.assertFalse(any("client" in name or "write" in name for name in vars(resolution)))


if __name__ == "__main__":
    unittest.main()
