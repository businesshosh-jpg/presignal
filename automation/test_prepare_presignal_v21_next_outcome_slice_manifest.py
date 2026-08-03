import json
import hashlib
import unittest
from pathlib import Path

from automation.prepare_presignal_v21_next_outcome_slice_manifest import (
    INVALID_CALLS,
    SLICE_ID,
    build_package,
    canonical,
)


class NextOutcomeSliceManifestTests(unittest.TestCase):
    def test_next_slice_is_deterministic_and_pairable(self):
        manifest, auth, proof, decision = build_package()
        self.assertEqual(decision["decision"], "NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN")
        self.assertEqual(decision["authorization_inputs_decision"], "NEXT_PROSPECTIVE_SLICE_AUTHORIZATION_INPUTS_READY")
        self.assertEqual(manifest["slice_id"], SLICE_ID)
        self.assertEqual(manifest["episode_count"], 12)
        self.assertEqual(manifest["authorized_forecast_population"], {"valid_forecasts": 40, "pack_a": 20, "pack_e": 20, "complete_pack_a_e_pairs": 20, "pack_a_only": 0, "pack_e_only": 0})
        self.assertEqual([row["selection_order"] for row in manifest["episode_manifest"]], list(range(1, 13)))
        self.assertEqual([row["episode_id"] for row in manifest["episode_manifest"]], [
            "EP_EVENT_4b80366594480b554889", "EP_EVENT_e8d9ca85a946bdcbc5d9", "EP_EVENT_556c59fe6ef36f4ac156",
            "EP_EVENT_13e6e3247eaea46e42de", "EP_EVENT_08246fe90d4f62b05721", "EP_EVENT_a8905547406656cf53ae",
            "EP_BATCH_e14769aca1aaacc9c230", "EP_EVENT_ef630a47cf9a4a6f79fd", "EP_BATCH_5fe2f38977eb016fa947",
            "EP_BATCH_f537c8eb93513ab66253", "EP_BATCH_1ff2d721e3e93c9a9ac4", "EP_EVENT_aa41226bcb8107901555",
        ])
        self.assertEqual(proof["prior_slice_exclusions"]["slice_001_and_slice_002_unique_episode_count"], 12)
        self.assertEqual(set(proof["terminal_invalid_exclusions"]), INVALID_CALLS)
        self.assertEqual(proof["unresolved_conflicts"], [])
        self.assertEqual(auth["max_total_external_requests"], 15)
        self.assertEqual(auth["max_attachment_records"], 12)
        self.assertFalse(auth["evaluation_authorized"])

    def test_manifest_has_canonical_hashable_content_and_no_external_access(self):
        manifest, _, proof, _ = build_package()
        expected = "sha256:" + hashlib.sha256(canonical({k: v for k, v in manifest.items() if k != "manifest_fingerprint"}).encode()).hexdigest()
        self.assertEqual(manifest["manifest_fingerprint"], expected)
        self.assertEqual(proof["external_access"], {"provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "attachment": 0, "evaluation": 0})
        self.assertEqual(manifest["primary_endpoint"], "T+15")
        self.assertEqual(manifest["secondary_measurement"], "Immediate Impulse")
        self.assertEqual(len(canonical(manifest)), len(canonical(manifest)))


if __name__ == "__main__":
    unittest.main()
