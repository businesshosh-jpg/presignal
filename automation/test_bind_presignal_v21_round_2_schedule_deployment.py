#!/usr/bin/env python3
from __future__ import annotations

import unittest

from automation import bind_presignal_v21_round_2_schedule_deployment as binding


def deployment(deployment_id: str, version: int = 82) -> dict:
    return {"deploymentId": deployment_id, "deploymentConfig": {"scriptId": binding.PROJECT_ID, "versionNumber": version}, "entryPoints": [{"entryPointType": "EXECUTION_API"}]}


class DeploymentBindingTests(unittest.TestCase):
    def test_historical_exact_endpoint_selects_independent_of_order(self) -> None:
        inventory = [deployment("other", 99), deployment(binding.DEPLOYMENT_ID), deployment("older", 4)]
        proof = binding.authority_proof(list(reversed(inventory)))
        self.assertEqual(proof["selected_deployment_id"], binding.DEPLOYMENT_ID)
        self.assertEqual(proof["selected_before_version"], 82)

    def test_missing_historical_endpoint_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "DEPLOYMENT_MISSING"):
            binding.authority_proof([deployment("newest", 99)])

    def test_non_execution_or_wrong_project_fails_closed(self) -> None:
        row = deployment(binding.DEPLOYMENT_ID)
        row["deploymentConfig"]["scriptId"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "BINDING_CONFLICT"):
            binding.authority_proof([row])


if __name__ == "__main__":
    unittest.main()
