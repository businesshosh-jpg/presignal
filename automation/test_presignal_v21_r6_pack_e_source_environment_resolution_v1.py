"""Focused local-only Pack E environment-resolution tests."""
from __future__ import annotations

import unittest

from automation import run_presignal_v21_r6_pack_e_source_environment_resolution_v1 as env


class PackESourceEnvironmentTests(unittest.TestCase):
    def test_requirements_keep_environment_caller_supplied(self) -> None:
        trace = env.requirements()
        self.assertEqual(trace["required_environment_fields"], ["environment_id", "approved_source_ids"])
        self.assertIn("unavailable", trace["completeness_rule"])

    def test_registry_is_separate_from_runtime_readiness(self) -> None:
        rows = env.source_capabilities()
        self.assertTrue(all(row["registry_approval_status"] == "APPROVED_SOURCE_CAPABILITY_GATED" for row in rows))
        self.assertTrue(all(row["runtime_readiness"] != "APPROVED_AND_RUNTIME_READY" for row in rows))

    def test_no_legacy_writer_is_promoted_to_pack_e_adapter(self) -> None:
        fmp = next(row for row in env.source_capabilities() if row["source_identity"] == "KSRC_FMP")
        self.assertEqual(fmp["runtime_readiness"], "APPROVED_BUT_ADAPTER_UNAVAILABLE")
        self.assertFalse(fmp["prospective_use_permitted"])

    def test_incomplete_candidate_is_rejected_deterministically(self) -> None:
        first, second = env.candidate_environment(env.source_capabilities()), env.candidate_environment(env.source_capabilities())
        self.assertEqual(first, second)
        self.assertFalse(first[0]["required_coverage_complete"])
        self.assertEqual(first[0]["expected_source_call_count"], 0)

    def test_secret_audit_does_not_include_values(self) -> None:
        inventory = env.local_binding_inventory()
        self.assertFalse(inventory["secret_values_recorded"])
        self.assertTrue(all(status in {"SET", "NOT_SET"} for status in inventory["environment_variables"].values()))

    def test_external_operations_are_all_zero(self) -> None:
        self.assertTrue(all(value == 0 for value in env.audit().values()))


if __name__ == "__main__":
    unittest.main()
