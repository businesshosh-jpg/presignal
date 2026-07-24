"""Focused tests for the offline R6 prospective Pack E adapter migration."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import run_presignal_v21_r6_pack_e_native_adapter_migration_v1 as migration


class PackENativeAdapterMigrationTests(unittest.TestCase):
    def test_migration_keeps_existing_v2_fetchers_and_adds_no_writer_path(self) -> None:
        source = (migration.ROOT / "apps_script/prospective_pack_e_acquisition.js").read_text(encoding="utf-8")
        legacy = (migration.ROOT / "apps_script/market_context_v2b.js").read_text(encoding="utf-8")
        for function in ("_v2bFetchFmpHistory_", "_v2bFetchFredHistory_", "_v2bFetchEodhdHistory_"):
            self.assertIn(function, source)
            self.assertIn("function " + function, legacy)
        self.assertIn("NATIVE_ACQUISITION_RECORD", source)
        self.assertIn("caller_controlled_existing_v2_fetch", source)

    def test_source_inventory_separates_adapter_readiness_from_configuration_readiness(self) -> None:
        rows = {row["source_identity"]: row for row in migration.adapter_inventory()}
        self.assertTrue(all(rows[key]["native_acquisition_record_emitted"] for key in ("KSRC_FMP", "KSRC_FRED", "KSRC_EODHD")))
        self.assertEqual(rows["KSRC_FRED"]["runtime_readiness"], "APPROVED_BUT_CONFIGURATION_MISSING")
        self.assertEqual(rows["KSRC_US_TREASURY"]["runtime_readiness"], "APPROVED_BUT_ADAPTER_UNAVAILABLE")

    def test_runtime_audit_excludes_secret_values_and_uses_existing_cross_worktree_reference_only(self) -> None:
        audit = migration.local_binding_audit()
        self.assertFalse(audit["secret_values_recorded"])
        self.assertEqual(audit["apps_script_bridge_token"]["role"], "Apps Script bridge credential only; not a market-source API key")
        self.assertNotIn("token_contents", json.dumps(audit))

    def test_fixture_results_are_deterministic_temporally_bounded_and_writer_free(self) -> None:
        result = migration.fixture_results()
        self.assertTrue(result["fred_valid_record"]["deterministic_three_runs"])
        self.assertEqual(result["fred_valid_record"]["fetch_calls"]["writers"], 0)
        self.assertEqual(result["post_cutoff"]["failure"], "SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED")
        self.assertEqual(result["live_source_calls"], 0)

    def test_minimum_environment_rejects_incomplete_treasury_binding_and_writes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            decision = migration.run(output)
            self.assertEqual(decision, "NEW_R6_PACK_E_NATIVE_ADAPTERS_READY_BINDING_INCOMPLETE")
            expected = {
                "pack_e_native_acquisition_record_contract_trace.json", "pack_e_legacy_adapter_reuse_audit.json",
                "pack_e_prospective_adapter_migration_plan.json", "pack_e_prospective_adapter_manifest.json",
                "pack_e_prospective_adapter_fixture_results.json", "pack_e_runtime_configuration_reference_audit.json",
                "pack_e_cross_worktree_binding_report.json", "pack_e_secret_safety_report.json",
                "pack_e_minimum_required_coverage.json", "pack_e_source_field_binding_report.json",
                "pack_e_runtime_ready_capability_inventory.json", "pack_e_environment_candidates.json",
                "pack_e_environment_selection_report.json", "r6_pack_e_source_environment.json",
                "r6_pack_e_source_environment_fingerprint.json", "r6_pack_e_acquisition_authorization_preparation.json",
                "r6_pack_e_acquisition_authorization_fingerprint.json", "external_access_audit.json",
                "final_pack_e_native_adapter_migration_decision.json",
            }
            self.assertEqual({path.name for path in output.glob("*.json")}, expected)
            coverage = json.loads((output / "pack_e_minimum_required_coverage.json").read_text())
            self.assertEqual(coverage["required_fields"][0]["capability_id"], "TREASURY_2Y_10Y_PRESESSION_STATE")
            auth = json.loads((output / "r6_pack_e_acquisition_authorization_preparation.json").read_text())
            self.assertEqual(auth["status"], "NOT_CREATED")
            external = json.loads((output / "external_access_audit.json").read_text())
            self.assertTrue(all(value == 0 for value in external.values()))


if __name__ == "__main__":
    unittest.main()
