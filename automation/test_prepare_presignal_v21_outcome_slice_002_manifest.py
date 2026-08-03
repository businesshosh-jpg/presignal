import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121000Z-9c7adf4c2f2e"


class Slice002ManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((RUN / "slice_002_manifest.json").read_text())
        self.proof = json.loads((RUN / "population_proof.json").read_text())
        self.decision = json.loads((RUN / "manifest_decision.json").read_text())
        self.run_manifest = json.loads((RUN / "run_manifest.json").read_text())

    def test_frozen_population_and_order(self):
        episodes = self.manifest["episode_manifest"]
        self.assertEqual(self.manifest["slice_id"], "SLICE-002")
        self.assertEqual(len(episodes), 12)
        self.assertEqual(len({row["episode_id"] for row in episodes}), 12)
        self.assertEqual([row["selection_order"] for row in episodes], list(range(1, 13)))
        self.assertEqual(self.proof["slice_population"], {
            "episodes": 12,
            "valid_forecasts": 44,
            "pack_a": 22,
            "pack_e": 22,
            "complete_pack_a_e_pairs": 22,
            "pack_a_only": 0,
            "pack_e_only": 0,
            "terminal_invalid_excluded": 0,
        })

    def test_pairability_and_recovered_boundary(self):
        pairs = self.proof["pair_rows"]
        self.assertEqual(len(pairs), 22)
        self.assertEqual({row["provider"] for row in pairs}, {"Anthropic", "Gemini", "OpenAI"})
        recovered = self.proof["recovered_forecast"]
        self.assertEqual(recovered["status"], "RECOVERED_VALID_FROM_PRESERVED_RAW_OUTPUT")
        self.assertTrue(recovered["global_eligibility"].startswith("ELIGIBLE_"))
        self.assertFalse(recovered["included_in_slice_002"])
        excluded = set(self.proof["excluded_forecast_call_ids"])
        self.assertNotIn(recovered["forecast_call_id"], excluded)

    def test_manifest_fingerprints_and_no_external_activity(self):
        file_hash = "sha256:" + hashlib.sha256((RUN / "slice_002_manifest.json").read_bytes()).hexdigest()
        self.assertEqual(self.decision["manifest_fingerprint"], file_hash)
        self.assertEqual(self.run_manifest["manifest_fingerprint"], file_hash)
        self.assertEqual(self.run_manifest["google_reads"], 0)
        self.assertEqual(self.run_manifest["market_data_calls"], 0)
        self.assertEqual(self.run_manifest["provider_calls"], 0)
        self.assertEqual(self.run_manifest["google_writes"], 0)
        self.assertEqual(self.run_manifest["outcome_attachment"], 0)
        self.assertEqual(self.run_manifest["evaluation_calculations"], 0)

    def test_contract_and_decisions(self):
        self.assertEqual(self.manifest["forecast_contract"], "presignal_event_path_contract_v1_1")
        self.assertEqual(self.manifest["outcome_schema_version"], "2.1.1")
        self.assertEqual(self.manifest["primary_endpoint"], "T+15")
        self.assertEqual(self.manifest["secondary_measurement"], "Immediate Impulse")
        self.assertEqual(self.decision["decision"], "SLICE_002_OUTCOME_COLLECTION_MANIFEST_FROZEN")
        self.assertEqual(self.decision["authorization_decision"], "SLICE_002_OUTCOME_COLLECTION_AUTHORIZATION_READY")


if __name__ == "__main__":
    unittest.main()
