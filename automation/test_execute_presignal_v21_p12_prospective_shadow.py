from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import execute_presignal_v21_p12_prospective_shadow as p12
from automation import presignal_v21_prospective_flat_contract_v1 as prospective


class P12ProspectiveShadowExecutionTests(unittest.TestCase):
    def test_frozen_authorization_and_timing_overlay_verify(self) -> None:
        verified = p12.verify_preparation()
        timing = p12.timing_semantics_control()
        self.assertEqual(verified["study_id"], p12.STUDY_ID)
        self.assertEqual(verified["preparation_fingerprint"], p12.PREPARATION_FINGERPRINT)
        self.assertEqual(verified["prospective_contract"]["version"], prospective.PROSPECTIVE_CONTRACT_VERSION)
        self.assertEqual(timing["classification"], "NON_SCIENTIFIC_EXECUTION_CONTROL")
        self.assertIn("information_cutoff_ts <= prompt_freeze_ts", timing["required_order"])
        self.assertTrue(timing["archived_preparation_unchanged"])

    def test_scientific_authorization_drift_fails_closed(self) -> None:
        with self.assertRaisesRegex(p12.P12ShadowError, "V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT"):
            p12.run(mode="execute", study_id="wrong", preparation_fingerprint=p12.PREPARATION_FINGERPRINT, contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION)
        with self.assertRaisesRegex(p12.P12ShadowError, "V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT"):
            p12.run(mode="execute", study_id=p12.STUDY_ID, preparation_fingerprint="sha256:wrong", contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION)

    def test_minimal_explicit_lineage_is_ready_without_any_external_call(self) -> None:
        capability = p12.live_lineage_capability()
        self.assertTrue(capability["passed"])
        self.assertEqual(capability["lineage_mode"], "MINIMAL_EXPLICIT_INPUT_LOCAL_SIDECAR")
        self.assertTrue(capability["requires_explicit_new_session"])
        self.assertEqual(capability["external_calls"], 0)

    def test_in_progress_preflight_is_deterministic_and_preserves_empty_population(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args = {"mode": "execute", "study_id": p12.STUDY_ID, "preparation_fingerprint": p12.PREPARATION_FINGERPRINT, "contract_version": prospective.PROSPECTIVE_CONTRACT_VERSION}
            left_path, left = p12.run(**args, output_dir=Path(directory) / "left")
            right_path, right = p12.run(**args, output_dir=Path(directory) / "right")
            self.assertEqual(left["status"], "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS")
            self.assertEqual(left["checkpoint_decision"], "P12_NOT_YET_REACHED")
            self.assertEqual(left["collection_run_id"], right["collection_run_id"])
            self.assertEqual(left["external_calls"]["forecast"], 0)
            self.assertTrue((left_path / "timing_semantics_verification.json").exists())
            self.assertTrue((left_path / "historical_evidence_verification.json").exists())
            self.assertEqual((left_path / "population_accrual_ledger.jsonl").read_text(), "")
            self.assertEqual((right_path / "forecast_call_ledger.jsonl").read_text(), "")


if __name__ == "__main__":
    unittest.main()
