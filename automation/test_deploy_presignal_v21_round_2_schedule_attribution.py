#!/usr/bin/env python3
"""Focused local checks for the one-shot Round 2 attribution deployment."""
from __future__ import annotations

import unittest

from automation import deploy_presignal_v21_round_2_schedule_attribution as deployment


class AttributionDeploymentTests(unittest.TestCase):
    def test_authorization_is_exact_and_non_refreshing(self) -> None:
        value = deployment.authorization()
        self.assertEqual(value["project_id"], deployment.PROJECT_ID)
        self.assertEqual(
            value["ceilings"],
            {
                "apps_script_source_updates": 1,
                "deployment_version_creations": 1,
                "deployment_activations": 1,
                "deployment_verification_reads": 2,
                "retries": 0,
            },
        )
        self.assertIn("Event-sheet writes", value["not_authorized"])
        self.assertIn("FMP requests", value["not_authorized"])

    def test_source_fingerprint_is_deterministic(self) -> None:
        self.assertEqual(deployment.source_fingerprint(), deployment.source_fingerprint())
        self.assertTrue(deployment.source_fingerprint().startswith("sha256:"))

    def test_contract_probe_is_present_in_local_source(self) -> None:
        source = (deployment.ROOT / "apps_script" / "automation_api.js").read_text()
        self.assertIn("apiGetScheduleRefreshAttributionContract", source)
        self.assertIn("pre_refresh_event_sheet_fingerprint", source)
        self.assertIn("post_refresh_event_sheet_fingerprint", source)

    def test_multiple_execution_api_deployments_fail_closed(self) -> None:
        deployments = [
            {"deploymentId": "one", "entryPoints": [{"entryPointType": "EXECUTION_API"}]},
            {"deploymentId": "two", "entryPoints": [{"entryPointType": "EXECUTION_API"}]},
        ]
        with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS:2"):
            deployment.select_unique_execution_api_deployment(deployments)


if __name__ == "__main__":
    unittest.main()
