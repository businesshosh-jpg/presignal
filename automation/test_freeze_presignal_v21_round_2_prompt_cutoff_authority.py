from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import freeze_presignal_v21_round_2_prompt_cutoff_authority as authority


class Round2PromptCutoffAuthorityTests(unittest.TestCase):
    def test_future_prompt_is_unique_and_pack_distinction_is_input_bound(self) -> None:
        result = authority.prompt_authority()
        packs = result["prompt_authority"]
        self.assertEqual(result["decision"], "ROUND_2_PACK_PROMPT_AUTHORITY_FROZEN")
        self.assertEqual(
            packs["pack_a"]["prompt_instruction_fingerprint"],
            "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77",
        )
        self.assertEqual(packs["pack_a"]["complete_prompt_source"], packs["pack_e"]["complete_prompt_source"])
        self.assertNotEqual(packs["pack_a"]["canonical_information_arm"], packs["pack_e"]["canonical_information_arm"])

    def test_cutoff_rejects_ungoverned_numeric_offset(self) -> None:
        result = authority.cutoff_authority()
        self.assertEqual(result["decision"], "ROUND_2_PROSPECTIVE_CUTOFF_AUTHORITY_BLOCKED")
        self.assertIn("cutoff offset relative to release", result["missing_required_numeric_authority"])
        self.assertIn("forecast_freeze_deadline_ts < release_ts", result["accepted_ordering_rule"])

    def test_evidence_is_deterministic_and_zero_access(self) -> None:
        first = authority.build_evidence()
        second = authority.build_evidence()
        self.assertEqual(first["artifact_fingerprint"], second["artifact_fingerprint"])
        self.assertEqual(first["activity"]["provider_calls"], 0)
        with tempfile.TemporaryDirectory() as directory:
            written = authority.freeze(Path(directory) / "evidence")
            self.assertEqual(written["downstream_decisions"]["manifest"], "ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED")


if __name__ == "__main__":
    unittest.main()
