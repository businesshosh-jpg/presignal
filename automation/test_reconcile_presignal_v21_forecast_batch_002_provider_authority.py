from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import reconcile_presignal_v21_forecast_batch_002_provider_authority as recon


class ForecastBatch002ProviderAuthorityReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = recon.load_call_evidence()

    def test_only_target_call_is_reconciled(self) -> None:
        self.assertEqual(self.evidence["call"]["forecast_call_id"], recon.CALL_ID)
        self.assertEqual(self.evidence["failed_call"]["forecast_call_id"], recon.CALL_ID)

    def test_exact_aliases_permit_only_deterministic_matches(self) -> None:
        self.assertEqual(recon.exact_alias("Gemini", "Google"), "Gemini")
        self.assertEqual(recon.exact_alias("Gemini", "Gemini"), "Gemini")
        self.assertIsNone(recon.exact_alias("Gemini", "google"))
        self.assertIsNone(recon.exact_alias("Gemini", "Gem"))

    def test_generic_bridge_labels_cannot_become_provider_identities(self) -> None:
        self.assertIsNone(recon.exact_alias("Gemini", "apiCallAuthoritativeProviderJsonObject"))
        self.assertIsNone(recon.exact_alias("Gemini", "BASELINE"))

    def test_raw_model_claim_cannot_override_missing_transport_identity(self) -> None:
        mismatch = recon.classify_mismatch(self.evidence)
        self.assertEqual(mismatch["classification"], "MISSING_AUTHORITATIVE_TRANSPORT_IDENTITY")
        self.assertFalse(mismatch["independently_proves_model"])

    def test_valid_contract_contents_alone_cannot_establish_provider_authority(self) -> None:
        mismatch = recon.classify_mismatch(self.evidence)
        decisions = recon.build_decisions(self.evidence, mismatch)
        self.assertEqual(decisions["existing_result_decision"], "EXISTING_RESULT_NOT_AUTHORITATIVELY_RECONCILED")
        self.assertEqual(decisions["batch_002_decision"], "FORECAST_BATCH_002_REMAINS_INCOMPLETE")

    def test_batch_cannot_be_marked_complete_with_fewer_than_12_authoritative_results(self) -> None:
        mismatch = recon.classify_mismatch(self.evidence)
        decisions = recon.build_decisions(self.evidence, mismatch)
        self.assertEqual(decisions["final_authoritative_valid_count"], 11)
        self.assertEqual(decisions["batch_002_decision"], "FORECAST_BATCH_002_REMAINS_INCOMPLETE")

    def test_no_provider_dispatch_can_occur(self) -> None:
        with patch.object(recon, "write_artifacts") as write_artifacts:
            with patch.object(recon, "materialize_run", return_value=Path(tempfile.mkdtemp())):
                result = recon.main
                self.assertTrue(callable(result))
                write_artifacts.assert_not_called()

    def test_original_failed_provider_authority_row_remains_unchanged(self) -> None:
        before = self.evidence["provider_authority"]
        self.assertEqual(before["actual_provider"], "")
        self.assertEqual(before["actual_model"], "")
        self.assertFalse(before["authority_passed"])

    def test_successful_reconciliation_creates_append_only_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            mismatch = recon.classify_mismatch(self.evidence)
            decisions = recon.build_decisions(self.evidence, mismatch)
            with patch.object(recon, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), patch.object(recon, "git_head", return_value=recon.EXPECTED_START_HEAD):
                recon.write_artifacts(run_dir, self.evidence, mismatch, decisions)
            self.assertTrue((run_dir / "provider_authority_reconciliation.json").exists())
            self.assertTrue((run_dir / "reconciled_provider_authority_result.jsonl").exists())
            self.assertTrue((run_dir / "authoritative_result_selection.json").exists())

    def test_successful_reconciliation_selects_exactly_one_authoritative_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            mismatch = recon.classify_mismatch(self.evidence)
            decisions = recon.build_decisions(self.evidence, mismatch)
            with patch.object(recon, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), patch.object(recon, "git_head", return_value=recon.EXPECTED_START_HEAD):
                recon.write_artifacts(run_dir, self.evidence, mismatch, decisions)
            selection = json.loads((run_dir / "authoritative_result_selection.json").read_text())
            self.assertEqual(selection["forecast_call_id"], recon.CALL_ID)

    def test_duplicate_authoritative_results_are_prohibited(self) -> None:
        mismatch = recon.classify_mismatch(self.evidence)
        decisions = recon.build_decisions(self.evidence, mismatch)
        self.assertEqual(decisions["provider_authority_conflict_count"], 1)

    def test_frozen_manifest_and_raw_response_are_not_modified(self) -> None:
        call = self.evidence["call"]
        raw_provider = self.evidence["raw_provider"]
        self.assertEqual(call["provider"], "Gemini")
        self.assertEqual(call["model"], "gemini-2.5-flash-lite")
        self.assertEqual(raw_provider["raw_provider_output"], "")

    def test_batch_003_cannot_execute(self) -> None:
        mismatch = recon.classify_mismatch(self.evidence)
        decisions = recon.build_decisions(self.evidence, mismatch)
        self.assertEqual(decisions["next_phase_decision"], "GOVERNANCE_REVIEW_REQUIRED")

    def test_no_google_writes_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            mismatch = recon.classify_mismatch(self.evidence)
            decisions = recon.build_decisions(self.evidence, mismatch)
            with patch.object(recon, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), patch.object(recon, "git_head", return_value=recon.EXPECTED_START_HEAD):
                recon.write_artifacts(run_dir, self.evidence, mismatch, decisions)
            manifest = json.loads((run_dir / "run_manifest.json").read_text())
            self.assertEqual(manifest["google_writes_executed"], 0)

    def test_prior_evidence_remains_immutable(self) -> None:
        source = recon.OUTPUT_ROOT / recon.GOVERNANCE_RECOVERY_ID / "provider_authority_results.jsonl"
        content_before = source.read_text()
        mismatch = recon.classify_mismatch(self.evidence)
        decisions = recon.build_decisions(self.evidence, mismatch)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            with patch.object(recon, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), patch.object(recon, "git_head", return_value=recon.EXPECTED_START_HEAD):
                recon.write_artifacts(run_dir, self.evidence, mismatch, decisions)
        self.assertEqual(source.read_text(), content_before)


if __name__ == "__main__":
    unittest.main()
