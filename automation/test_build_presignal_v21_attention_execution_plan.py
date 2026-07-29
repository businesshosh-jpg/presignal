from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_attention_execution_plan as plan


class BuildAttentionExecutionPlanTest(unittest.TestCase):
    def test_governing_matrix_has_expected_attention_blocked_population(self) -> None:
        rows = plan.load_matrix_rows()
        blocked = plan.blocked_attention_episodes(rows)
        self.assertEqual(len(blocked), 413)
        self.assertNotIn(plan.OPEC_EPISODE_ID, blocked)

    def test_merged_lineage_has_no_missing_session_ids(self) -> None:
        blocked = plan.blocked_attention_episodes(plan.load_matrix_rows())
        merged = plan.merge_episode_session_lineage(blocked, plan.load_dry_run_attention_plan())
        self.assertEqual(len(merged), 413)
        self.assertTrue(all(row["session_id"] for row in merged))
        self.assertEqual(sum(row["rescue_matrix_category"] == "UNCHANGED" for row in merged), 341)
        self.assertEqual(sum(row["rescue_matrix_category"] == "NORMAL_SESSION_RESCUE_PROMOTED" for row in merged), 72)

    def test_reconciled_session_and_call_counts_are_68_and_204(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        self.assertEqual(result["session_summary"]["unique_session_count"], 68)
        self.assertEqual(result["session_summary"]["attention_call_count"], 204)
        self.assertEqual(result["execution_plan"]["unique_session_count"], 68)
        self.assertEqual(result["execution_plan"]["unique_session_provider_call_count"], 204)

    def test_prior_projection_is_reconciled_with_rescued_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        summary = result["session_summary"]
        self.assertEqual(summary["prior_projection_sessions"], 62)
        self.assertEqual(summary["prior_projection_attention_calls"], 186)
        self.assertEqual(summary["reconciled_delta_sessions"], 6)
        self.assertEqual(summary["reconciled_delta_attention_calls"], 18)
        self.assertEqual(summary["rescued_only_session_count"], 6)

    def test_rescued_only_sessions_match_expected_six_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        self.assertEqual(
            result["session_summary"]["rescued_only_session_ids"],
            [
                "US|2024-05-08|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-10|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-14|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-15|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-16|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
            ],
        )

    def test_attention_calls_are_once_per_session_per_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        calls = result["attention_calls"]
        self.assertEqual(len(calls), 204)
        identities = {(row["session_id"], row["provider"]) for row in calls}
        self.assertEqual(len(identities), 204)
        self.assertEqual({row["provider"] for row in calls}, set(plan.EXPECTED_PROVIDER_SET))

    def test_deterministic_outputs_and_cli_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = plan.build_plan(output_root=root / "first", fixed_timestamp="2026-07-29T01:00:00Z")
            second = plan.build_plan(output_root=root / "second", fixed_timestamp="2026-07-29T01:00:00Z")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["session_summary"], second["session_summary"])
            self.assertEqual(first["reconciliation"], second["reconciliation"])

            subprocess.run(
                ["python3", str(Path(plan.__file__)), "--output-root", str(root / "cli1"), "--fixed-timestamp", "2026-07-29T01:00:00Z"],
                cwd=plan.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["python3", str(Path(plan.__file__)), "--output-root", str(root / "cli2"), "--fixed-timestamp", "2026-07-29T01:00:00Z"],
                cwd=plan.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            first_dir = next((root / "cli1").iterdir())
            second_dir = next((root / "cli2").iterdir())
            self.assertEqual(
                json.loads((first_dir / "reconciliation_summary.json").read_text())["scientific_fingerprint"],
                json.loads((second_dir / "reconciliation_summary.json").read_text())["scientific_fingerprint"],
            )
            self.assertEqual(
                (first_dir / "session_provider_attention_calls.jsonl").read_text(),
                (second_dir / "session_provider_attention_calls.jsonl").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
