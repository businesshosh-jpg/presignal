from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import migrate_presignal_v21_future_no_signal_prompt_version as migration


class FutureNoSignalPromptMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.result = migration.construct_migration(
            Path(cls.temp_dir.name),
            fixed_timestamp="2026-08-01T11:00:00Z",
            enforce_head=False,
        )
        cls.run_dir = cls.result["run_dir"]
        cls.calls = migration.read_jsonl(cls.run_dir / "migrated_call_manifest.jsonl")
        cls.batches = migration.read_jsonl(cls.run_dir / "migrated_batch_manifest.jsonl")
        cls.lineage = migration.read_jsonl(cls.run_dir / "old_to_new_call_lineage.jsonl")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_exact_future_population_is_migrated(self) -> None:
        reconciliation = migration.read_json(self.run_dir / "migration_reconciliation.json")
        self.assertEqual(reconciliation["future_batch_count"], 45)
        self.assertEqual(reconciliation["migrated_call_count"], 528)
        self.assertEqual(reconciliation["migrated_pack_a_call_count"], 246)
        self.assertEqual(reconciliation["migrated_pack_e_call_count"], 282)

    def test_completed_batches_remain_excluded(self) -> None:
        migrated_ids = {row["batch_id"] for row in self.batches}
        self.assertNotIn("FCB_PACK_A_001", migrated_ids)
        self.assertNotIn("FCB_PACK_A_002", migrated_ids)
        self.assertNotIn("FCB_PACK_A_003", migrated_ids)
        self.assertEqual(min(row["execution_order"] for row in self.calls), 37)

    def test_only_the_authorized_sentence_changes_prompt_text(self) -> None:
        diff = migration.read_json(self.run_dir / "exact_prompt_diff.json")
        self.assertTrue(diff["all_diffs_passed"])
        self.assertTrue(diff["one_added_sentence"])
        self.assertTrue(diff["zero_deleted_scientific_instructions"])
        self.assertTrue(diff["zero_modified_scientific_instructions"])
        self.assertTrue(all(row["prompt_text"].count(migration.ADDED_PROMPT_SENTENCE) == 1 for row in self.calls))

    def test_pack_provider_model_and_cutoff_are_unchanged(self) -> None:
        plan = migration.load_authoritative_plan()
        old_calls = {row["forecast_call_id"]: row for row in plan["calls"]}
        for row in self.calls:
            old = old_calls[row["forecast_call_id"]]
            self.assertEqual(row["episode_id"], old["episode_id"])
            self.assertEqual(row["pack_row_identity"], old["pack_row_identity"])
            self.assertEqual(row["pack_row_fingerprint"], old["pack_row_fingerprint"])
            self.assertEqual(row["provider"], old["provider"])
            self.assertEqual(row["model"], old["model"])
            self.assertEqual(row["historical_cutoff"], old["historical_cutoff"])

    def test_call_identity_is_preserved_one_to_one(self) -> None:
        self.assertEqual(len(self.lineage), 528)
        self.assertEqual(len({row["old_forecast_call_id"] for row in self.lineage}), 528)
        self.assertEqual(len({row["new_forecast_call_id"] for row in self.lineage}), 528)
        self.assertTrue(all(row["old_forecast_call_id"] == row["new_forecast_call_id"] for row in self.lineage))
        self.assertTrue(all(row["call_identity_preserved"] for row in self.lineage))

    def test_batch_identity_is_preserved_with_new_revisions(self) -> None:
        rows = migration.read_jsonl(self.run_dir / "old_to_new_batch_lineage.jsonl")
        self.assertEqual(len(rows), 45)
        self.assertTrue(all(row["old_batch_id"] == row["new_batch_id"] for row in rows))
        self.assertTrue(all(row["old_batch_manifest_fingerprint"] != row["new_batch_manifest_fingerprint"] for row in rows))

    def test_superseded_unexecuted_manifest_revisions_are_disabled(self) -> None:
        rows = migration.read_jsonl(self.run_dir / "superseded_identity_ledger.jsonl")
        self.assertEqual(len(rows), 528)
        self.assertTrue(all(row["status"] == migration.SUPERSEDED_STATUS for row in rows))
        self.assertTrue(all(row["dispatch_prohibited"] for row in rows))

    def test_new_manifest_revisions_start_with_zero_attempts(self) -> None:
        self.assertTrue(all(row["prior_attempt_count"] == 0 for row in self.calls))
        self.assertTrue(all(row["new_manifest_revision_attempt_count"] == 0 for row in self.calls))
        self.assertTrue(all("manifest_revision_id" in row["migration_resume_key"] for row in self.calls))

    def test_future_execution_requires_the_migrated_source(self) -> None:
        with self.assertRaisesRegex(batch_exec.ForecastBatchError, "FUTURE_PROMPT_VERSION_MIGRATION_REQUIRED"):
            batch_exec.verified_batch_bundle(
                user_batch_label="FORECAST_BATCH_004",
                frozen_batch_id="FCB_PACK_A_004",
            )
        bundle = batch_exec.verified_batch_bundle(
            user_batch_label="FORECAST_BATCH_004",
            frozen_batch_id="FCB_PACK_A_004",
            migration_run_dir=self.run_dir,
        )
        self.assertEqual(len(bundle["bundles"]), 12)
        self.assertEqual(bundle["manifest_source"]["kind"], "AUTHORIZED_FUTURE_PROMPT_MIGRATION")
        self.assertTrue(
            all(
                row["prompt_fingerprint"]["prompt_instruction_fingerprint"] == migration.FUTURE_PROMPT_FINGERPRINT
                for row in bundle["bundles"]
            )
        )

    def test_completed_batches_reject_new_prompt_manifest_source(self) -> None:
        with self.assertRaisesRegex(batch_exec.ForecastBatchError, "COMPLETED_BATCH_MIGRATION_SOURCE_FORBIDDEN"):
            batch_exec.verified_batch_bundle(
                user_batch_label="FORECAST_BATCH_003",
                frozen_batch_id="FCB_PACK_A_003",
                migration_run_dir=self.run_dir,
            )

    def test_pack_e_requires_the_clarified_prompt_version(self) -> None:
        source = migration.load_migrated_manifest_source(self.run_dir, "FCB_PACK_E_001")
        self.assertEqual(len(source["ledger_rows"]), 12)
        self.assertTrue(all(row["pack_type"] == "PACK_E" for row in source["ledger_rows"]))
        self.assertTrue(all(row["prompt_version"] == migration.FUTURE_PROMPT_VERSION for row in source["ledger_rows"]))

    def test_final_six_call_pack_e_remainder_stays_bounded_and_migrated(self) -> None:
        bundle = batch_exec.verified_batch_bundle(
            user_batch_label="FORECAST_BATCH_E_024",
            frozen_batch_id="FCB_PACK_E_024",
            migration_run_dir=self.run_dir,
        )
        self.assertEqual(bundle["authorized_call_count"], 6)
        self.assertEqual(len(bundle["bundles"]), 6)
        self.assertTrue(all(row["call"]["prompt_version"] == migration.FUTURE_PROMPT_VERSION for row in bundle["bundles"]))

    def test_evaluation_cohorts_and_non_execution_boundaries_are_recorded(self) -> None:
        cohorts = migration.read_json(self.run_dir / "evaluation_prompt_cohort_metadata.json")
        manifest = migration.read_json(self.run_dir / "run_manifest.json")
        self.assertEqual(cohorts["completed_call_prompt_cohort"]["frozen_call_count"], 36)
        self.assertEqual(cohorts["clarified_prompt_cohort"]["unexecuted_call_count"], 528)
        self.assertEqual(manifest["provider_calls_executed"], 0)
        self.assertFalse(manifest["batch_004_executed"])
        self.assertEqual(manifest["google_writes_executed"], 0)


if __name__ == "__main__":
    unittest.main()
