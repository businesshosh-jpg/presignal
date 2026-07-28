from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_provider_ready_matrix as matrix


class BuildProviderReadyMatrixTest(unittest.TestCase):
    def test_prior_matrix_is_preserved_and_sized_correctly(self) -> None:
        rows = matrix.load_prior_matrix_rows()
        self.assertEqual(len(rows), 2772)
        self.assertEqual(len({row["episode_id"] for row in rows}), 462)

    def test_recommendation_ledger_is_exact_96_anthropic_arms(self) -> None:
        rows = matrix.load_recommendation_rows()
        validation = matrix.validate_recommendation_rows(rows)
        self.assertEqual(validation["recommendation_count"], 96)
        self.assertEqual(validation["unique_arm_count"], 96)
        self.assertEqual(validation["provider_counts"], {"Anthropic": 96})
        self.assertEqual(validation["model_counts"], {"claude-haiku-4-5": 96})
        self.assertEqual(validation["pack_counts"], {"PACK_A": 48, "PACK_E": 48})
        self.assertEqual(validation["prior_status_counts"], {"BLOCKED_PROVIDER_CONTRACT": 96})
        self.assertEqual(validation["new_status_counts"], {"READY_FOR_EXECUTION": 96})

    def test_provider_ready_matrix_reconciles_core_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T17:05:00Z")
        self.assertEqual(result["changed_arm_count"], 96)
        self.assertEqual(result["unchanged_arm_count"], 2676)
        self.assertEqual(result["ready_count"], 118)
        self.assertEqual(result["provider_blocked_count"], 0)
        self.assertEqual(result["immutable_count"], 170)
        self.assertEqual(result["attention_blocked_count"], 2478)
        self.assertEqual(result["pack_unavailable_count"], 6)

    def test_only_blocked_provider_contract_rows_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T17:05:00Z")
            run_dir = Path(tmp) / result["run_id"]
            changes = [
                json.loads(line)
                for line in (run_dir / "provider_arm_reclassification.jsonl").read_text().splitlines()
                if line.strip()
            ]
        self.assertEqual(len(changes), 96)
        self.assertTrue(all(row["prior_status"] == "BLOCKED_PROVIDER_CONTRACT" for row in changes))
        self.assertTrue(all(row["new_status"] == "READY_FOR_EXECUTION" for row in changes))
        self.assertTrue(all(row["provider"] == "Anthropic" for row in changes))
        self.assertTrue(all(row["model"] == "claude-haiku-4-5" for row in changes))

    def test_final_status_counts_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T17:05:00Z")
        self.assertEqual(
            result["final_status_counts"],
            {
                "BLOCKED_ATTENTION_RECONSTRUCTION": 2478,
                "BLOCKED_PACK_UNAVAILABLE": 6,
                "BLOCKED_PROVIDER_CONTRACT": 0,
                "EXISTING_IMMUTABLE_RESULT": 170,
                "READY_FOR_EXECUTION": 118,
            },
        )
        self.assertEqual(
            result["status_transition_counts"],
            {
                "BLOCKED_ATTENTION_RECONSTRUCTION->BLOCKED_ATTENTION_RECONSTRUCTION": 2478,
                "BLOCKED_PACK_UNAVAILABLE->BLOCKED_PACK_UNAVAILABLE": 6,
                "BLOCKED_PROVIDER_CONTRACT->READY_FOR_EXECUTION": 96,
                "EXISTING_IMMUTABLE_RESULT->EXISTING_IMMUTABLE_RESULT": 170,
                "READY_FOR_EXECUTION->READY_FOR_EXECUTION": 22,
            },
        )

    def test_opec_rows_remain_blocked_with_pending_out_of_session_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T17:05:00Z")
            run_dir = Path(tmp) / result["run_id"]
            rows = [
                json.loads(line)
                for line in (run_dir / "provider_ready_execution_matrix.jsonl").read_text().splitlines()
                if line.strip()
            ]
        opec_rows = [row for row in rows if row["episode_id"] == matrix.OPEC_EPISODE_ID]
        self.assertEqual(len(opec_rows), 6)
        self.assertTrue(all(row["arm_execution_status"] == "BLOCKED_PACK_UNAVAILABLE" for row in opec_rows))
        self.assertTrue(all(row["blocking_reasons"] == [matrix.OUT_OF_SESSION_BLOCKER] for row in opec_rows))
        self.assertTrue(all(row["normal_session_status"] == "OUT_OF_NORMAL_SESSION" for row in opec_rows))

    def test_immutable_rows_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.build_matrix(output_root=Path(tmp), fixed_timestamp="2026-07-28T17:05:00Z")
            run_dir = Path(tmp) / result["run_id"]
            final_rows = [
                json.loads(line)
                for line in (run_dir / "provider_ready_execution_matrix.jsonl").read_text().splitlines()
                if line.strip()
            ]
        prior_rows = matrix.load_prior_matrix_rows()
        prior_by_id = {row["expected_arm_identity"]: row for row in prior_rows}
        for row in final_rows:
            prior = prior_by_id[row["expected_arm_identity"]]
            if prior["arm_execution_status"] == "EXISTING_IMMUTABLE_RESULT":
                self.assertEqual(row["arm_execution_status"], prior["arm_execution_status"])
                self.assertEqual(row["existing_immutable_call_id"], prior["existing_immutable_call_id"])
                self.assertEqual(row["blocking_reasons"], prior["blocking_reasons"])

    def test_deterministic_outputs_and_cli_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = matrix.build_matrix(output_root=root / "first", fixed_timestamp="2026-07-28T17:05:00Z")
            second = matrix.build_matrix(output_root=root / "second", fixed_timestamp="2026-07-28T17:05:00Z")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["final_status_counts"], second["final_status_counts"])
            self.assertEqual(first["status_transition_counts"], second["status_transition_counts"])

            subprocess.run(
                ["python3", str(Path(matrix.__file__)), "--output-root", str(root / "cli1"), "--fixed-timestamp", "2026-07-28T17:05:00Z"],
                cwd=matrix.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["python3", str(Path(matrix.__file__)), "--output-root", str(root / "cli2"), "--fixed-timestamp", "2026-07-28T17:05:00Z"],
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
                (first_dir / "provider_ready_execution_matrix.jsonl").read_text(),
                (second_dir / "provider_ready_execution_matrix.jsonl").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
