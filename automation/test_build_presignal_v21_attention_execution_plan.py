from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_attention_execution_plan as plan


class BuildAttentionExecutionPlanTest(unittest.TestCase):
    def test_authoritative_matrix_population_is_unchanged(self) -> None:
        rows = plan.load_matrix_rows()
        self.assertEqual(len(rows), 2772)
        self.assertEqual(len({row["episode_id"] for row in rows}), 462)
        blocked = [row for row in rows if row["arm_execution_status"] == "BLOCKED_ATTENTION_RECONSTRUCTION"]
        ready = [row for row in rows if row["arm_execution_status"] == "READY_FOR_EXECUTION"]
        self.assertEqual(len(blocked), 2478)
        self.assertEqual(len(ready), 118)

    def test_attention_blocked_population_resolves_to_413_unique_episodes(self) -> None:
        rows = plan.load_matrix_rows()
        blocked = plan.blocked_attention_episodes(rows)
        self.assertEqual(len(blocked), 413)
        self.assertNotIn(plan.OPEC_EPISODE_ID, blocked)

    def test_ready_arms_are_excluded_from_attention_plan(self) -> None:
        rows = plan.load_matrix_rows()
        ready = plan.ready_execution_rows(rows)
        self.assertEqual(len(ready), 118)
        self.assertEqual(len({row["episode_id"] for row in ready}), 48)

    def test_opec_episode_is_excluded(self) -> None:
        rows = plan.load_matrix_rows()
        self.assertTrue(any(row["episode_id"] == plan.OPEC_EPISODE_ID for row in rows))
        blocked = plan.blocked_attention_episodes(rows)
        self.assertNotIn(plan.OPEC_EPISODE_ID, blocked)

    def test_all_413_episodes_map_to_exactly_one_session(self) -> None:
        blocked = plan.blocked_attention_episodes(plan.load_matrix_rows())
        merged = plan.merge_episode_session_lineage(
            blocked,
            plan.load_jsonl_by_episode(plan.ATTENTION_PLAN_PATH),
            plan.load_episode_rows_by_id(),
        )
        self.assertEqual(len(merged), 413)
        self.assertTrue(all(row["source_session_id"] for row in merged))
        self.assertEqual(len({row["episode_id"] for row in merged}), 413)

    def test_no_session_is_invented(self) -> None:
        blocked = plan.blocked_attention_episodes(plan.load_matrix_rows())
        merged = plan.merge_episode_session_lineage(
            blocked,
            plan.load_jsonl_by_episode(plan.ATTENTION_PLAN_PATH),
            plan.load_episode_rows_by_id(),
        )
        dry_run_sessions = {
            row["source_session_id"]
            for row in plan.read_jsonl(plan.ATTENTION_PLAN_PATH)
            if row.get("source_session_id")
        }
        for row in merged:
            if row["rescue_matrix_category"] == "UNCHANGED":
                self.assertIn(row["source_session_id"], dry_run_sessions)

    def test_calls_are_deduplicated_by_session_and_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        calls = result["attention_call_ledger"]
        identities = {(row["source_session_id"], row["provider"]) for row in calls}
        self.assertEqual(len(calls), 204)
        self.assertEqual(len(identities), 204)

    def test_calls_are_not_duplicated_by_episode_or_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
            episode_map = result["run_dir"] / "episode_to_attention_call_map.jsonl"
            rows = [json.loads(line) for line in episode_map.read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), 413)
            self.assertTrue(all(row["call_count"] == 3 for row in rows))
            self.assertTrue(all(len(row["attention_call_ids"]) == 3 for row in rows))

    def test_every_session_has_exactly_three_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        counts = {}
        for row in result["attention_call_ledger"]:
            counts.setdefault(row["source_session_id"], 0)
            counts[row["source_session_id"]] += 1
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(len(counts), 68)

    def test_every_episode_maps_to_exactly_three_attention_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
            rows = [json.loads(line) for line in (result["run_dir"] / "episode_to_attention_call_map.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), 413)
            self.assertTrue(all(len(row["provider_call_ids"]) == 3 for row in rows))

    def test_provider_model_routes_are_frozen_correctly(self) -> None:
        self.assertEqual(
            plan.PROVIDER_MODELS,
            {
                "Anthropic": "claude-haiku-4-5",
                "Gemini": "gemini-2.5-flash-lite",
                "OpenAI": "gpt-4o-mini-2024-07-18",
            },
        )

    def test_previous_62_session_reconciliation_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        recon = result["previous_plan_reconciliation"]
        self.assertEqual(recon["previous_unique_session_count"], 62)
        self.assertEqual(recon["previous_attention_call_count"], 186)
        self.assertEqual(recon["final_unique_session_count"], 68)
        self.assertEqual(recon["final_attention_call_count"], 204)

    def test_rescue_introduced_session_changes_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        recon = result["previous_plan_reconciliation"]
        self.assertEqual(recon["rescue_introduced_session_count"], 6)
        self.assertEqual(recon["rescued_episodes_mapped_to_existing_sessions"], 64)
        self.assertEqual(recon["rescued_episodes_mapped_to_new_sessions"], 8)
        self.assertEqual(
            recon["rescued_only_session_ids"],
            [
                "US|2024-05-08|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-10|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-14|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-15|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-16|CUSTOM_CONFIG_WINDOW",
                "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
            ],
        )

    def test_pack_a_and_pack_e_fanout_are_separate_from_attention_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
            fanout_rows = [json.loads(line) for line in (result["run_dir"] / "pack_reconstruction_fanout.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(len(fanout_rows), 413)
            self.assertTrue(all(len(row["attention_call_ids"]) == 3 for row in fanout_rows))
            self.assertTrue(all(len(row["expected_forecast_arm_identities"]) == 6 for row in fanout_rows))

    def test_expected_arm_counts_reconcile_to_2478(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = plan.build_plan(output_root=Path(tmp), fixed_timestamp="2026-07-29T01:00:00Z")
        preview = result["post_attention_preview"]
        self.assertEqual(preview["arm_transitions"]["BLOCKED_ATTENTION_RECONSTRUCTION->READY_FOR_EXECUTION"], 2478)
        self.assertEqual(preview["ready_arm_total_after_attention"], 2596)

    def test_deterministic_reruns_produce_same_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first = plan.build_plan(output_root=root / "first", fixed_timestamp="2026-07-29T01:00:00Z")
            second = plan.build_plan(output_root=root / "second", fixed_timestamp="2026-07-29T01:00:00Z")
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["scientific_fingerprint"], second["scientific_fingerprint"])

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
                json.loads((first_dir / "attention_plan_summary.json").read_text())["scientific_fingerprint"],
                json.loads((second_dir / "attention_plan_summary.json").read_text())["scientific_fingerprint"],
            )
            self.assertEqual(
                (first_dir / "attention_call_ledger.jsonl").read_text(),
                (second_dir / "attention_call_ledger.jsonl").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
