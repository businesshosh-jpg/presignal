from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import repair_presignal_v21_attention_pack_lineage as repair


class AttentionPackLineageRepairTest(unittest.TestCase):
    def test_real_repair_counts_and_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            summary = result["summary"]
            decision = result["decision"]
            self.assertEqual(summary["blocked_episode_count_audited"], 72)
            self.assertEqual(summary["blocked_episode_provider_row_count_audited"], 216)
            self.assertEqual(summary["episode_pack_audit_row_count"], 144)
            self.assertEqual(summary["shared_cause_group_count"], 2)
            self.assertEqual(summary["pack_a_episodes_resolved_through_deterministic_lookup_repair"], 72)
            self.assertEqual(summary["pack_e_episodes_resolved_through_deterministic_lookup_repair"], 72)
            self.assertEqual(summary["pack_a_provider_rows_newly_resolved"], 216)
            self.assertEqual(summary["pack_e_provider_rows_newly_resolved"], 216)
            self.assertEqual(summary["fully_resolved_episode_provider_rows"], 1239)
            self.assertEqual(summary["partially_resolved_episode_provider_rows"], 0)
            self.assertEqual(summary["fully_blocked_episode_provider_rows"], 0)
            self.assertEqual(summary["remaining_unresolved_episode_pack_issues"], 0)
            self.assertEqual(summary["fuzzy_bindings_accepted"], 0)
            self.assertEqual(summary["attention_scientific_field_mutation_count"], 0)
            self.assertTrue(summary["all_1239_attention_rows_remain"])
            self.assertTrue(summary["previously_resolved_1023_rows_remained_unchanged"])
            self.assertEqual(decision["repair_status"], "ATTENTION_TO_PACK_LINEAGE_REPAIR_COMPLETE")
            self.assertEqual(decision["pack_a_repair_decision"], "PACK_A_ALL_REQUIRED_LINEAGE_RESOLVED")
            self.assertEqual(decision["pack_e_repair_decision"], "PACK_E_ALL_REQUIRED_LINEAGE_RESOLVED")
            self.assertEqual(decision["attention_integrity_decision"], "ALL_1239_ATTENTION_ROWS_PRESERVED_UNCHANGED")
            self.assertEqual(decision["scientific_boundary_decision"], "LINEAGE_REPAIR_ONLY_NO_PACK_CONSTRUCTION")
            self.assertEqual(decision["next_phase_decision"], "READY_FOR_BOUNDED_PACK_POPULATION_CONSTRUCTION")

    def test_shared_cause_groups_use_exact_frozen_classifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            groups = repair.read_jsonl(result["run_dir"] / "shared_cause_diagnostic.jsonl")
            self.assertEqual(len(groups), 2)
            group_counts = {row["group_id"]: row["episode_count"] for row in groups}
            self.assertEqual(group_counts["GROUP_EVENT_DATE_JOIN_64"], 64)
            self.assertEqual(group_counts["GROUP_PRIOR_JOIN_REPAIR_8"], 8)
            for row in groups:
                self.assertIn("prior_classification", row["exact_grouping_fields"])
                self.assertIn("final_classification", row["exact_grouping_fields"])

    def test_all_blocked_rows_are_repaired_and_previously_resolved_rows_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            repaired = repair.read_jsonl(result["run_dir"] / "repaired_episode_provider_pack_binding.jsonl")
            original = repair.read_jsonl(repair.LINEAGE_ROOT / "episode_provider_pack_binding.jsonl")
            original_by_key = {(row["episode_id"], row["provider"]): row for row in original}
            changed = 0
            unchanged_resolved = 0
            for row in repaired:
                key = (row["episode_id"], row["provider"])
                if original_by_key[key]["future_pack_binding_status"] == "FULLY_BLOCKED":
                    self.assertEqual(row["future_pack_binding_status"], "FULLY_RESOLVED")
                    changed += 1
                else:
                    self.assertEqual(row, original_by_key[key])
                    unchanged_resolved += 1
            self.assertEqual(changed, 216)
            self.assertEqual(unchanged_resolved, 1023)

    def test_only_lineage_fields_change_for_repaired_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            repaired = repair.read_jsonl(result["run_dir"] / "repaired_episode_provider_pack_binding.jsonl")
            original = repair.read_jsonl(repair.LINEAGE_ROOT / "episode_provider_pack_binding.jsonl")
            original_by_key = {(row["episode_id"], row["provider"]): row for row in original}
            for row in repaired:
                key = (row["episode_id"], row["provider"])
                prior = original_by_key[key]
                for field in repair.SCIENTIFIC_FIELDS:
                    self.assertEqual(row[field], prior[field])

    def test_pack_a_and_pack_e_stay_independent_and_no_blockers_remain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            rows = repair.read_jsonl(result["run_dir"] / "repaired_episode_provider_pack_binding.jsonl")
            repaired_rows = [row for row in rows if row.get("lineage_repair_method") == "EXACT_SESSION_DATE_AND_ROUTE_REPAIR"]
            self.assertEqual(len(repaired_rows), 216)
            self.assertTrue(all(row["pack_a_lineage_status"] == "RESOLVED_DETERMINISTIC_LOOKUP_REPAIR" for row in repaired_rows))
            self.assertTrue(all(row["pack_e_lineage_status"] == "RESOLVED_DETERMINISTIC_LOOKUP_REPAIR" for row in repaired_rows))
            self.assertEqual(repair.read_jsonl(result["run_dir"] / "remaining_lineage_blockers.jsonl"), [])

    def test_no_provider_calls_google_writes_or_pack_construction_occur(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = repair.execute_lineage_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T14:00:00Z")
            manifest = repair.read_json(result["run_dir"] / "run_manifest.json")
            self.assertEqual(manifest["provider_calls_executed"], 0)
            self.assertEqual(manifest["google_writes_executed"], 0)
            self.assertEqual(manifest["pack_a_constructed"], 0)
            self.assertEqual(manifest["pack_e_constructed"], 0)
            self.assertEqual(manifest["forecast_execution_executed"], 0)
            self.assertEqual(manifest["outcome_attachment_executed"], 0)
            self.assertEqual(manifest["matrix_updates_executed"], 0)
            self.assertEqual(manifest["consensus_or_ranking_executed"], 0)


if __name__ == "__main__":
    unittest.main()
