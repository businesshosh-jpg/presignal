from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_final_rescue_matrix as matrix


class BuildFinalRescueMatrixTest(unittest.TestCase):
    def test_prior_matrix_is_preserved_with_expected_size(self) -> None:
        rows = matrix.load_prior_matrix_rows()
        self.assertEqual(len(rows), 2772)
        self.assertEqual(len({row["episode_id"] for row in rows}), 462)

    def test_promotion_candidates_are_exact_72_and_exclude_opec(self) -> None:
        validation = matrix.validate_promotion_candidates(matrix.load_promotion_candidates())
        self.assertEqual(validation["candidate_count"], 72)
        self.assertEqual(validation["unique_episode_count"], 72)
        rows = matrix.load_promotion_candidates()
        self.assertNotIn(matrix.OPEC_EPISODE_ID, {row["episode_id"] for row in rows})

    def test_opec_timezone_conversion_is_aware(self) -> None:
        utc_text, eastern_text, eastern_date = matrix.to_us_eastern("2024-06-02T03:00:00Z")
        self.assertEqual(utc_text, "2024-06-02T03:00:00Z")
        self.assertEqual(eastern_text, "2024-06-01T23:00:00-04:00")
        self.assertEqual(eastern_date, "2024-06-01")

    def test_final_matrix_reconciles_counts_and_promotions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            self.assertEqual(result["final_episode_count"], 462)
            self.assertEqual(result["final_arm_count"], 2772)
            self.assertEqual(result["promotion_candidate_count"], 72)
            self.assertEqual(result["out_of_session_arm_count"], 6)
            self.assertEqual(result["actual_changed_arm_count"], 438)
            self.assertEqual(result["unchanged_arm_count"], 2334)

    def test_no_more_than_432_normal_rescue_arms_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            recon = result["matrix_reconciliation"]
            self.assertEqual(recon["normal_rescue_changed_arm_count"], 432)
            self.assertEqual(recon["out_of_session_changed_arm_count"], 6)

    def test_opec_episode_remains_blocked_and_no_session_is_invented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            run_dir = Path(tmp) / result["run_id"]
            rows = [
                json.loads(line)
                for line in (run_dir / "final_rescue_aware_execution_matrix.jsonl").read_text().splitlines()
                if line.strip()
            ]
            opec_rows = [row for row in rows if row["episode_id"] == matrix.OPEC_EPISODE_ID]
            self.assertEqual(len(opec_rows), 6)
            self.assertTrue(all(row["episode_eligibility_status"] == "ELIGIBLE" for row in opec_rows))
            self.assertTrue(all(row["arm_execution_status"] == "BLOCKED_PACK_UNAVAILABLE" for row in opec_rows))
            self.assertTrue(all(row["normal_session_status"] == "OUT_OF_NORMAL_SESSION" for row in opec_rows))
            self.assertTrue(all(row["normal_session_id"] is None for row in opec_rows))
            self.assertTrue(all(row["event_level_route_status"] == "NOT_YET_VALIDATED" for row in opec_rows))
            self.assertTrue(all(row["blocking_reasons"] == [matrix.OUT_OF_SESSION_BLOCKER] for row in opec_rows))

    def test_blocker_reason_is_not_no_recovery_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            run_dir = Path(tmp) / result["run_id"]
            ledger = [
                json.loads(line)
                for line in (run_dir / "out_of_session_episode_ledger.jsonl").read_text().splitlines()
                if line.strip()
            ]
            self.assertEqual(len(ledger), 1)
            self.assertEqual(ledger[0]["blocker_reason"], matrix.OUT_OF_SESSION_BLOCKER)
            self.assertNotEqual(ledger[0]["blocker_reason"], "NO_RECOVERY_ROUTE")

    def test_unaffected_immutable_results_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            run_dir = Path(tmp) / result["run_id"]
            final_rows = [
                json.loads(line)
                for line in (run_dir / "final_rescue_aware_execution_matrix.jsonl").read_text().splitlines()
                if line.strip()
            ]
            prior_rows = matrix.load_prior_matrix_rows()
            prior_by_id = {row["expected_arm_identity"]: row for row in prior_rows}
            for row in final_rows:
                prior = prior_by_id[row["expected_arm_identity"]]
                if prior["references_existing_immutable_result"]:
                    self.assertEqual(row["arm_execution_status"], prior["arm_execution_status"])
                    self.assertEqual(row["existing_immutable_call_id"], prior["existing_immutable_call_id"])

    def test_final_status_counts_are_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            self.assertEqual(
                result["final_status_counts"],
                {
                    "BLOCKED_ATTENTION_RECONSTRUCTION": 2478,
                    "BLOCKED_PACK_UNAVAILABLE": 6,
                    "BLOCKED_PROVIDER_CONTRACT": 96,
                    "EXISTING_IMMUTABLE_RESULT": 170,
                    "READY_FOR_EXECUTION": 22,
                },
            )
            self.assertEqual(
                result["status_transition_counts"],
                {
                    "BLOCKED_ATTENTION_RECONSTRUCTION->BLOCKED_ATTENTION_RECONSTRUCTION": 2046,
                    "BLOCKED_PACK_UNAVAILABLE->BLOCKED_ATTENTION_RECONSTRUCTION": 432,
                    "BLOCKED_PACK_UNAVAILABLE->BLOCKED_PACK_UNAVAILABLE": 6,
                    "BLOCKED_PROVIDER_CONTRACT->BLOCKED_PROVIDER_CONTRACT": 96,
                    "EXISTING_IMMUTABLE_RESULT->EXISTING_IMMUTABLE_RESULT": 170,
                    "READY_FOR_EXECUTION->READY_FOR_EXECUTION": 22,
                },
            )

    def test_canonical_status_and_route_state_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T16:30:00Z")
            run_dir = Path(tmp) / result["run_id"]
            rows = [
                json.loads(line)
                for line in (run_dir / "final_rescue_aware_execution_matrix.jsonl").read_text().splitlines()
                if line.strip()
            ]
            opec = next(row for row in rows if row["episode_id"] == matrix.OPEC_EPISODE_ID)
            self.assertEqual(opec["arm_execution_status"], "BLOCKED_PACK_UNAVAILABLE")
            self.assertEqual(opec["normal_session_status"], "OUT_OF_NORMAL_SESSION")
            self.assertEqual(opec["event_level_route_status"], "NOT_YET_VALIDATED")

    def test_deterministic_outputs_and_cli_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = matrix.build_matrix(output_root=root / "first", fixed_timestamp="2026-07-28T16:30:00Z")
            second = matrix.build_matrix(output_root=root / "second", fixed_timestamp="2026-07-28T16:30:00Z")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["matrix_reconciliation"]["scientific_fingerprint"], second["matrix_reconciliation"]["scientific_fingerprint"])

            subprocess.run(
                ["python3", str(Path(matrix.__file__)), "--output-root", str(root / "cli1"), "--fixed-timestamp", "2026-07-28T16:30:00Z"],
                cwd=matrix.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["python3", str(Path(matrix.__file__)), "--output-root", str(root / "cli2"), "--fixed-timestamp", "2026-07-28T16:30:00Z"],
                cwd=matrix.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            first_dir = next((root / "cli1").iterdir())
            second_dir = next((root / "cli2").iterdir())
            self.assertEqual(
                json.loads((first_dir / "matrix_reconciliation.json").read_text())["scientific_fingerprint"],
                json.loads((second_dir / "matrix_reconciliation.json").read_text())["scientific_fingerprint"],
            )
            self.assertEqual(
                (first_dir / "final_rescue_aware_execution_matrix.jsonl").read_text(),
                (second_dir / "final_rescue_aware_execution_matrix.jsonl").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
