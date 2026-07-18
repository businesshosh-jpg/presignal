from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation.build_simplified_replay_package_v1 import (
    SNAPSHOT,
    apps_script_project_fingerprint,
    apps_script_source_binding,
    freeze_production_package,
)
from automation.run_simplified_replay_canary_v1 import (
    DurableExecutionError,
    execute_live_identity,
    initialize_durable_run,
    read_execution_deployment_metadata,
)
from automation.simplified_authoritative_replay_contract_v1 import driver_options


PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
DEPLOYMENT_ID = "AKfycbxd31I_td72HW0ZgScfYthYqliKfzBkQxE9EdURpTQU6ObQawGmX1sB5aVO3MADqXWf"
VERSION = 79
PROJECT_FINGERPRINT = "1de3a98607124c2ad052a87906daa388bab763850c43f49e4447bd76d4f9f054"
BRIDGE_SHA256 = "918a58462d69548cad155de231da63dbbcc984607dbc2262e32159211e99ec84"
RUNNER_SHA256 = "c0f5598deea761a1a55b5c02911e37d2e5e922fa8043e03e62792793800c483b"
GIT_COMMIT = "8bc7275412c64559e6698fef46668cbdfac160d7"


def clean_git_state(_repository_path: Path) -> dict:
    return {
        "git_commit": GIT_COMMIT,
        "git_branch": "codex-simplified-authoritative-replay",
        "git_worktree_clean": True,
        "git_detached_head": False,
        "git_repository_path": str(Path(__file__).resolve().parents[1]),
        "git_remote_name": "origin",
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def package_inputs(root: Path, package_id: str = "DEPLOYMENT-BINDING-PACKAGE") -> dict:
    return {
        "scientific_snapshot_path": SNAPSHOT,
        "durable_output_root": root,
        "package_id": package_id,
        "apps_script_project_id": PROJECT_ID,
        "execution_deployment_id": DEPLOYMENT_ID,
        "execution_deployment_version": VERSION,
        "immutable_apps_script_version": VERSION,
        "project_fingerprint": PROJECT_FINGERPRINT,
        "bridge_source_fingerprint": BRIDGE_SHA256,
        "prediction_runner_fingerprint": RUNNER_SHA256,
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
        "expected_git_commit": GIT_COMMIT,
        "repository_state_reader": clean_git_state,
    }


def init_inputs(package: Path, manifest: dict, run_root: Path, run_id: str = "DEPLOYMENT-BINDING-RUN") -> dict:
    binding = read_json(package / "binding" / "immutable_deployment_binding.json")
    git_binding = read_json(package / "binding" / "local_git_repository_binding.json")
    return {
        "package_dir": package,
        "durable_run_root": run_root,
        "run_id": run_id,
        "package_id": manifest["package_id"],
        "whole_package_fingerprint": manifest["whole_package_sha256"],
        "apps_script_project_id": binding["apps_script_project_id"],
        "execution_deployment_id": binding["execution_deployment_id"],
        "execution_deployment_version": binding["execution_deployment_version"],
        "immutable_version_number": binding["immutable_version_number"],
        "project_fingerprint": binding["project_fingerprint"],
        "bridge_sha256": binding["bridge_sha256"],
        "prediction_runner_sha256": binding["prediction_runner_sha256"],
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
        "git_commit": git_binding["git_commit"],
        "git_branch": git_binding["git_branch"],
        "git_worktree_clean": git_binding["git_worktree_clean"],
        "git_detached_head": git_binding["git_detached_head"],
    }


def matching_observation(project_id: str = PROJECT_ID, deployment_id: str = DEPLOYMENT_ID) -> dict:
    return {
        "apps_script_project_id": project_id,
        "execution_deployment_id": deployment_id,
        "execution_deployment_version": VERSION,
        "project_fingerprint": PROJECT_FINGERPRINT,
        "bridge_sha256": BRIDGE_SHA256,
        "prediction_runner_sha256": RUNNER_SHA256,
        "deployment_api_response": {
            "deploymentId": deployment_id,
            "deploymentConfig": {"scriptId": project_id, "versionNumber": VERSION},
        },
    }


def make_package_and_run(root: Path, run_id: str = "DEPLOYMENT-BINDING-RUN") -> tuple[Path, Path, dict]:
    manifest = freeze_production_package(**package_inputs(root / "packages"))
    package = root / "packages" / manifest["package_id"]
    initialize_durable_run(**init_inputs(package, manifest, root / "runs", run_id))
    return package, root / "runs" / run_id, manifest


def valid_response(identity: dict, members: list[dict]) -> dict:
    token = driver_options(members)[0]["token"]
    return {
        "actual_provider": identity["provider"],
        "actual_model": identity["model"],
        "raw_output": json.dumps({
            "primary_driver_token": token,
            "secondary_driver_token": None,
            "final_usdjpy_direction": "UP",
            "reaction_strength": "MODERATE",
            "confidence": 0.5,
            "primary_thesis": "fixture",
            "secondary_thesis": "",
            "reasoning_steps": ["one", "two"],
        }),
    }


def identity_and_members(package: Path, index: int = 0) -> tuple[dict, list[dict]]:
    identity = rows(package / "snapshot" / "authoritative_forecast_population.jsonl")[index]
    members = [
        row
        for row in rows(package / "snapshot" / "authoritative_session_members.jsonl")
        if row["session_id"] == identity["session_id"]
    ]
    return identity, members


class ActiveExecutionDeploymentBindingTest(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            "automation.run_simplified_replay_canary_v1.read_local_git_repository_state",
            side_effect=clean_git_state,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_committed_source_binding_matches_version_79_constants(self):
        self.assertEqual(apps_script_source_binding(), {
            "apps_script_project_id": PROJECT_ID,
            "project_fingerprint": PROJECT_FINGERPRINT,
            "bridge_sha256": BRIDGE_SHA256,
            "prediction_runner_sha256": RUNNER_SHA256,
            "file_count": 43,
        })

    def test_package_records_project_deployment_and_immutable_version_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = freeze_production_package(**package_inputs(root))
            binding = read_json(root / manifest["package_id"] / "binding" / "immutable_deployment_binding.json")
            self.assertEqual(binding["apps_script_project_id"], PROJECT_ID)
            self.assertEqual(binding["execution_deployment_id"], DEPLOYMENT_ID)
            self.assertEqual(binding["execution_deployment_version"], VERSION)
            self.assertEqual(binding["immutable_version_number"], VERSION)
            self.assertEqual(binding["project_fingerprint"], PROJECT_FINGERPRINT)
            self.assertEqual(binding["bridge_sha256"], BRIDGE_SHA256)
            self.assertEqual(binding["prediction_runner_sha256"], RUNNER_SHA256)

    def test_package_rejects_version_72_missing_fields_project_and_fingerprint_mismatches(self):
        cases = (
            ("deployment-version-72", "execution_deployment_version", 72, "EXECUTION_DEPLOYMENT_VERSION_MISMATCH"),
            ("missing-deployment-id", "execution_deployment_id", "", "EXECUTION_DEPLOYMENT_ID_MISSING"),
            ("missing-deployment-version", "execution_deployment_version", None, "EXECUTION_DEPLOYMENT_VERSION_MISSING"),
            ("project-mismatch", "apps_script_project_id", "different-project", "APPS_SCRIPT_PROJECT_ID_MISMATCH"),
            ("project-fingerprint", "project_fingerprint", "wrong", "APPS_SCRIPT_PROJECT_FINGERPRINT_MISMATCH"),
            ("bridge-fingerprint", "bridge_source_fingerprint", "wrong", "BRIDGE_SOURCE_FINGERPRINT_MISMATCH"),
            ("runner-fingerprint", "prediction_runner_fingerprint", "wrong", "PREDICTION_RUNNER_FINGERPRINT_MISMATCH"),
        )
        for name, key, value, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                inputs = package_inputs(Path(temporary), "PACKAGE-" + name.upper())
                inputs[key] = value
                with self.assertRaisesRegex(ValueError, error):
                    freeze_production_package(**inputs)

    def test_run_initialization_binds_exact_package_values_and_rejects_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = freeze_production_package(**package_inputs(root / "packages"))
            package = root / "packages" / manifest["package_id"]
            run_manifest = initialize_durable_run(**init_inputs(package, manifest, root / "runs", "RUN-MATCH"))
            self.assertEqual(run_manifest["binding"]["execution_deployment_id"], DEPLOYMENT_ID)
            self.assertEqual(run_manifest["binding"]["execution_deployment_version"], VERSION)
            self.assertEqual(run_manifest["binding"]["immutable_version_number"], VERSION)
            self.assertTrue(run_manifest["binding_sha256"])

            cases = (
                ("RUN-BAD-ID", "execution_deployment_id", "AKfy-different"),
                ("RUN-BAD-DEPLOYMENT-VERSION", "execution_deployment_version", 72),
                ("RUN-BAD-IMMUTABLE-VERSION", "immutable_version_number", 78),
            )
            for run_id, key, value in cases:
                inputs = init_inputs(package, manifest, root / "runs", run_id)
                inputs[key] = value
                with self.assertRaisesRegex(DurableExecutionError, key):
                    initialize_durable_run(**inputs)

    def test_run_binding_cannot_change_after_initialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            run_manifest = read_json(run_dir / "run_manifest.json")
            run_manifest["binding"]["execution_deployment_id"] = "AKfy-mutated"
            (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, sort_keys=True, indent=2) + "\n")
            identity, _members = identity_and_members(package)
            with self.assertRaisesRegex(DurableExecutionError, "RUN_DEPLOYMENT_BINDING_IMMUTABILITY_VIOLATION"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    deployment_metadata_reader=lambda _project, _deployment: matching_observation(),
                    dispatch_fn=lambda _payload: self.fail("dispatch must not run"),
                )
            self.assertFalse(list((run_dir / "ledgers" / "reservations").glob("*.json")))
            self.assertFalse(list((run_dir / "ledgers" / "invocations").glob("*.json")))

    def test_version_79_verification_is_durable_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            identity, members = identity_and_members(package)

            def dispatch(_payload):
                self.assertEqual(len(list((run_dir / "ledgers" / "deployment_verifications").glob("*.json"))), 1)
                self.assertEqual(len(list((run_dir / "ledgers" / "reservations").glob("*.json"))), 1)
                self.assertEqual(len(list((run_dir / "ledgers" / "invocations").glob("*.json"))), 1)
                return valid_response(identity, members)

            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                deployment_metadata_reader=lambda project_id, deployment_id: matching_observation(project_id, deployment_id),
                dispatch_fn=dispatch,
            )
            verification = read_json(next((run_dir / "ledgers" / "deployment_verifications").glob("*.json")))
            self.assertEqual(verification["verification_status"], "PASS")
            self.assertEqual(verification["expected_version"], VERSION)
            self.assertEqual(verification["observed_version"], VERSION)
            self.assertEqual(verification["expected_fingerprints"]["project_fingerprint"], PROJECT_FINGERPRINT)
            self.assertTrue(verification["api_response_fingerprint"])

    def test_failed_deployment_checks_stop_before_reservation_invocation_and_dispatch(self):
        def version_72(_project: str, _deployment: str) -> dict:
            return {**matching_observation(), "execution_deployment_version": 72}

        def unknown_version(_project: str, _deployment: str) -> dict:
            return {**matching_observation(), "execution_deployment_version": None}

        def missing_deployment(_project: str, _deployment: str) -> dict:
            return {}

        def api_failure(_project: str, _deployment: str) -> dict:
            raise RuntimeError("offline API failure")

        def wrong_deployment_id(_project: str, _deployment: str) -> dict:
            return {**matching_observation(), "execution_deployment_id": "AKfy-wrong"}

        def wrong_project_id(_project: str, _deployment: str) -> dict:
            return {**matching_observation(), "apps_script_project_id": "wrong-project"}

        def wrong_bridge_fingerprint(_project: str, _deployment: str) -> dict:
            return {**matching_observation(), "bridge_sha256": "wrong"}

        cases = (
            ("VERSION-72", version_72, "ACTIVE_EXECUTION_DEPLOYMENT_VERSION_MISMATCH"),
            ("UNKNOWN", unknown_version, "ACTIVE_EXECUTION_DEPLOYMENT_VERSION_UNKNOWN"),
            ("MISSING", missing_deployment, "ACTIVE_EXECUTION_DEPLOYMENT_MISSING"),
            ("API-FAILURE", api_failure, "ACTIVE_EXECUTION_DEPLOYMENT_METADATA_READ_FAILED"),
            ("WRONG-ID", wrong_deployment_id, "ACTIVE_EXECUTION_DEPLOYMENT_ID_MISMATCH"),
            ("WRONG-PROJECT", wrong_project_id, "ACTIVE_EXECUTION_DEPLOYMENT_PROJECT_MISMATCH"),
            ("WRONG-BRIDGE", wrong_bridge_fingerprint, "ACTIVE_EXECUTION_DEPLOYMENT_BRIDGE_FINGERPRINT_MISMATCH"),
        )
        for run_suffix, reader, error in cases:
            with self.subTest(case=run_suffix), tempfile.TemporaryDirectory() as temporary:
                package, run_dir, _manifest = make_package_and_run(Path(temporary), "RUN-" + run_suffix)
                identity, _members = identity_and_members(package)
                dispatched = {"count": 0}

                def dispatch(_payload):
                    dispatched["count"] += 1
                    return {}

                with self.assertRaisesRegex(DurableExecutionError, error):
                    execute_live_identity(
                        run_dir=run_dir,
                        package_dir=package,
                        identity=identity,
                        deployment_metadata_reader=reader,
                        dispatch_fn=dispatch,
                    )
                self.assertEqual(dispatched["count"], 0)
                self.assertFalse(list((run_dir / "ledgers" / "reservations").glob("*.json")))
                self.assertFalse(list((run_dir / "ledgers" / "invocations").glob("*.json")))
                verification = read_json(next((run_dir / "ledgers" / "deployment_verifications").glob("*.json")))
                self.assertEqual(verification["verification_status"], "FAIL")
                self.assertEqual(verification["failure_classification"], error)

    def test_resumed_execution_reverifies_before_another_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            calls = {"count": 0}

            def reader(project_id: str, deployment_id: str) -> dict:
                calls["count"] += 1
                return matching_observation(project_id, deployment_id)

            for index in (0, 1):
                identity, members = identity_and_members(package, index)
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    deployment_metadata_reader=reader,
                    dispatch_fn=lambda _payload, response=valid_response(identity, members): response,
                )
            self.assertEqual(calls["count"], 2)
            self.assertEqual(len(list((run_dir / "ledgers" / "deployment_verifications").glob("*.json"))), 2)

    def test_existing_apps_script_service_reads_deployment_and_version_source(self):
        bridge_source = "function apiCallAuthoritativeProviderJsonObject() {}"
        runner_source = "function _callProviderJsonObject_() {}"
        files = [
            {"name": "authoritative_provider_bridge", "type": "SERVER_JS", "source": bridge_source},
            {"name": "prediction_runner", "type": "SERVER_JS", "source": runner_source},
        ]
        projects = MagicMock()
        projects.deployments.return_value.get.return_value.execute.return_value = {
            "deploymentId": DEPLOYMENT_ID,
            "deploymentConfig": {"scriptId": PROJECT_ID, "versionNumber": VERSION},
        }
        projects.getContent.return_value.execute.return_value = {"files": files}
        service = MagicMock()
        service.projects.return_value = projects
        observed = read_execution_deployment_metadata(PROJECT_ID, DEPLOYMENT_ID, script_service=service)
        projects.deployments.return_value.get.assert_called_once_with(scriptId=PROJECT_ID, deploymentId=DEPLOYMENT_ID)
        projects.getContent.assert_called_once_with(scriptId=PROJECT_ID, versionNumber=VERSION)
        self.assertEqual(observed["project_fingerprint"], apps_script_project_fingerprint(files))
        self.assertEqual(observed["execution_deployment_version"], VERSION)

    def test_live_dispatch_uses_the_verified_execution_deployment_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            identity, members = identity_and_members(package)
            with patch(
                "automation.run_simplified_replay_canary_v1.production_bridge_dispatch",
                return_value=valid_response(identity, members),
            ) as dispatch:
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    deployment_metadata_reader=lambda project_id, deployment_id: matching_observation(project_id, deployment_id),
                )
            self.assertEqual(dispatch.call_args.kwargs["script_id"], DEPLOYMENT_ID)


if __name__ == "__main__":
    unittest.main()
