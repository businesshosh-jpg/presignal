from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.build_simplified_replay_package_v1 import SNAPSHOT, apps_script_source_binding, freeze_production_package
from automation.run_simplified_replay_canary_v1 import (
    DurableExecutionError,
    PredictionPersistenceError,
    execute_live_identity,
    initialize_durable_run,
    production_bridge_dispatch,
    reconcile_run,
)
from automation.simplified_authoritative_replay_contract_v1 import driver_options


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


def package_inputs(root: Path, package_id: str = "PROD-FREEZE-FIXTURE") -> dict:
    source_binding = apps_script_source_binding()
    return {
        "scientific_snapshot_path": SNAPSHOT,
        "durable_output_root": root,
        "package_id": package_id,
        "apps_script_project_id": source_binding["apps_script_project_id"],
        "execution_deployment_id": "AKfycbxd31I_td72HW0ZgScfYthYqliKfzBkQxE9EdURpTQU6ObQawGmX1sB5aVO3MADqXWf",
        "execution_deployment_version": 79,
        "immutable_apps_script_version": 79,
        "project_fingerprint": source_binding["project_fingerprint"],
        "bridge_source_fingerprint": source_binding["bridge_sha256"],
        "prediction_runner_fingerprint": source_binding["prediction_runner_sha256"],
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
        "expected_git_commit": GIT_COMMIT,
        "repository_state_reader": clean_git_state,
    }


def init_inputs(package: Path, package_manifest: dict, run_root: Path, run_id: str = "RUN-FIXTURE") -> dict:
    binding = read_json(package / "binding" / "immutable_deployment_binding.json")
    git_binding = read_json(package / "binding" / "local_git_repository_binding.json")
    return {
        "package_dir": package,
        "durable_run_root": run_root,
        "run_id": run_id,
        "package_id": package_manifest["package_id"],
        "whole_package_fingerprint": (package / "whole_package_sha256.txt").read_text().strip(),
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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def make_package_and_run(tmp: str, run_id: str = "RUN-FIXTURE") -> tuple[Path, Path, dict, dict, list[dict]]:
    root = Path(tmp)
    manifest = freeze_production_package(**package_inputs(root / "packages"))
    package = root / "packages" / "PROD-FREEZE-FIXTURE"
    run_manifest = initialize_durable_run(**init_inputs(package, manifest, root / "runs", run_id))
    run_dir = root / "runs" / run_id
    identity = rows(package / "snapshot" / "authoritative_forecast_population.jsonl")[0]
    members = [row for row in rows(package / "snapshot" / "authoritative_session_members.jsonl") if row["session_id"] == identity["session_id"]]
    return package, run_dir, run_manifest, identity, members


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
            "primary_thesis": "fixture thesis",
            "secondary_thesis": "",
            "reasoning_steps": ["one", "two"],
        }),
    }


def matching_deployment_metadata(project_id: str, deployment_id: str) -> dict:
    source_binding = apps_script_source_binding()
    return {
        "apps_script_project_id": project_id,
        "execution_deployment_id": deployment_id,
        "execution_deployment_version": 79,
        "project_fingerprint": source_binding["project_fingerprint"],
        "bridge_sha256": source_binding["bridge_sha256"],
        "prediction_runner_sha256": source_binding["prediction_runner_sha256"],
        "deployment_api_response": {"deploymentId": deployment_id, "deploymentConfig": {"scriptId": project_id, "versionNumber": 79}},
    }


class DurableLiveExecutionTest(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            "automation.run_simplified_replay_canary_v1.read_execution_deployment_metadata",
            side_effect=matching_deployment_metadata,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        git_patcher = patch(
            "automation.run_simplified_replay_canary_v1.read_local_git_repository_state",
            side_effect=clean_git_state,
        )
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

    def test_valid_frozen_package_initializes_durable_run_with_zero_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = freeze_production_package(**package_inputs(root / "packages"))
            package = root / "packages" / "PROD-FREEZE-FIXTURE"
            run_manifest = initialize_durable_run(**init_inputs(package, manifest, root / "runs"))
            run_dir = root / "runs" / "RUN-FIXTURE"

            self.assertEqual(run_manifest["binding"]["package_id"], "PROD-FREEZE-FIXTURE")
            for ledger in (
                "invocations",
                "raw_responses",
                "reservations",
                "transactions",
                "accepted_predictions",
                "failures",
                "terminal_identity_states",
            ):
                self.assertTrue((run_dir / "ledgers" / ledger).is_dir())
            summary = read_json(run_dir / "reconciliation_summary.json")
            self.assertEqual(summary["invocations"], 0)
            self.assertEqual(summary["raw_responses"], 0)
            self.assertEqual(summary["accepted_predictions"], 0)
            self.assertEqual(summary["failures"], 0)
            self.assertEqual(summary["active_reservations"], 0)
            self.assertEqual(summary["unresolved_transactions"], 0)

    def test_run_initialization_binding_mismatches_and_duplicate_run_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = freeze_production_package(**package_inputs(root / "packages"))
            package = root / "packages" / "PROD-FREEZE-FIXTURE"

            bad_fingerprint = init_inputs(package, manifest, root / "runs", "RUN-BAD-FP")
            bad_fingerprint["whole_package_fingerprint"] = "wrong"
            with self.assertRaisesRegex(DurableExecutionError, "whole_package_fingerprint"):
                initialize_durable_run(**bad_fingerprint)

            bad_version = init_inputs(package, manifest, root / "runs", "RUN-BAD-VERSION")
            bad_version["immutable_version_number"] = 77
            with self.assertRaisesRegex(DurableExecutionError, "immutable_version_number"):
                initialize_durable_run(**bad_version)

            initialize_durable_run(**init_inputs(package, manifest, root / "runs", "RUN-DUP"))
            with self.assertRaisesRegex(DurableExecutionError, "DUPLICATE_RUN_ID"):
                initialize_durable_run(**init_inputs(package, manifest, root / "runs", "RUN-DUP"))

    def test_production_dispatch_uses_existing_run_script_function_route(self):
        with patch("automation.google_clients.run_script_function", return_value={"status": "ok"}) as run_script:
            result = production_bridge_dispatch({"x": 1}, script_service=object(), script_id="SCRIPT-ID")
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(run_script.call_args.args[2], "apiCallAuthoritativeProviderJsonObject")
        self.assertEqual(run_script.call_args.args[3], [{"x": 1}])

    def test_execution_ordering_and_raw_before_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)
            checkpoints = {}

            def dispatch(_payload):
                checkpoints["reservation_before_dispatch"] = bool(list((run_dir / "ledgers" / "reservations").glob("*.json")))
                checkpoints["invocation_before_dispatch"] = bool(list((run_dir / "ledgers" / "invocations").glob("*.json")))
                checkpoints["transaction_before_dispatch"] = bool(list((run_dir / "ledgers" / "transactions").glob("*.json")))
                return valid_response(identity, members)

            def parser(response, parse_members, context):
                checkpoints["raw_before_parser"] = Path(context["raw_response_path"]).exists()
                token = driver_options(parse_members)[0]["token"]
                return {
                    "primary_driver_event_id": driver_options(parse_members)[0]["event_id"],
                    "secondary_driver_event_id": "",
                    "final_usdjpy_direction": "UP",
                    "reaction_strength": "MODERATE",
                    "confidence": 0.5,
                    "primary_thesis": "fixture thesis",
                    "secondary_thesis": "",
                    "reasoning_steps": ["one", "two"],
                    "parser_saw_token": token,
                }

            prediction = execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=dispatch, parser_fn=parser)
            self.assertEqual(prediction["identity_id"], identity["forecast_identity"])
            self.assertTrue(checkpoints["reservation_before_dispatch"])
            self.assertTrue(checkpoints["invocation_before_dispatch"])
            self.assertTrue(checkpoints["transaction_before_dispatch"])
            self.assertTrue(checkpoints["raw_before_parser"])

    def test_live_invocation_persists_frozen_pack_prompt_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)
            captured = {}

            def dispatch(payload):
                captured.update(payload)
                invocation = read_json(next((run_dir / "ledgers" / "invocations").glob("*.json")))
                self.assertEqual(invocation["payload"], payload)
                return valid_response(identity, members)

            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                dispatch_fn=dispatch,
            )
            prompt_context = json.loads(captured["prompt"]["user"])
            self.assertEqual(prompt_context["forecast_identity"], identity["forecast_identity"])
            self.assertEqual(prompt_context["pack_arm"], "A")
            self.assertIsNone(prompt_context["historical_environment_pack"])
            self.assertEqual(len(prompt_context["driver_options"]), len(members))
            self.assertFalse(prompt_context["outcome_data_supplied"])
            self.assertFalse(prompt_context["evaluation_data_supplied"])

    def test_parser_cannot_run_when_raw_persistence_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)
            parser_called = {"value": False}

            def raw_writer(_path, _record):
                raise RuntimeError("disk full")

            def parser(_response, _members, _context):
                parser_called["value"] = True
                return {}

            with self.assertRaisesRegex(DurableExecutionError, "raw_response_persistence_failure"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    dispatch_fn=lambda _payload: valid_response(identity, members),
                    parser_fn=parser,
                    raw_response_persistor=raw_writer,
                )
            self.assertFalse(parser_called["value"])

    def test_successful_execution_ledgers_and_duplicate_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)
            prediction = execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                dispatch_fn=lambda _payload: valid_response(identity, members),
            )
            summary = read_json(run_dir / "reconciliation_summary.json")
            transaction = read_json(next((run_dir / "ledgers" / "transactions").glob("*.json")))
            reservation = read_json(next((run_dir / "ledgers" / "reservations").glob("*.json")))
            terminal = read_json(next((run_dir / "ledgers" / "terminal_identity_states").glob("*.json")))

            self.assertEqual(summary["accepted_predictions"], 1)
            self.assertEqual(summary["unresolved_transactions"], 0)
            self.assertEqual(prediction["identity_id"], identity["forecast_identity"])
            self.assertEqual(terminal["status"], "success")
            self.assertEqual(reservation["status"], "released")
            self.assertEqual(transaction["status"], "committed")
            self.assertFalse((run_dir / "prediction_path").exists())
            with self.assertRaisesRegex(DurableExecutionError, "IDENTITY_ALREADY_ACCEPTED"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    dispatch_fn=lambda _payload: valid_response(identity, members),
                )

    def test_dispatch_failure_writes_no_raw_and_reconciles_failed_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, _members = make_package_and_run(tmp)
            with self.assertRaisesRegex(DurableExecutionError, "dispatch_failure"):
                execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=lambda _payload: (_ for _ in ()).throw(RuntimeError("boom")))

            self.assertFalse(list((run_dir / "ledgers" / "raw_responses").glob("*.json")))
            summary = read_json(run_dir / "reconciliation_summary.json")
            reservation = read_json(next((run_dir / "ledgers" / "reservations").glob("*.json")))
            self.assertEqual(summary["unresolved_transactions"], 0)
            self.assertEqual(summary["terminal_failed"], 1)
            self.assertEqual(reservation["status"], "released")

    def test_parser_and_validation_failures_preserve_raw_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp, "RUN-PARSER")
            with self.assertRaisesRegex(DurableExecutionError, "parser_failure"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    dispatch_fn=lambda _payload: valid_response(identity, members),
                    parser_fn=lambda _response, _members, _context: (_ for _ in ()).throw(ValueError("parse failed")),
                )
            self.assertEqual(len(list((run_dir / "ledgers" / "raw_responses").glob("*.json"))), 1)
            self.assertFalse(list((run_dir / "ledgers" / "accepted_predictions").glob("*.json")))

        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp, "RUN-VALIDATION")
            bad_response = valid_response(identity, members)
            payload = json.loads(bad_response["raw_output"])
            payload.pop("primary_thesis")
            bad_response["raw_output"] = json.dumps(payload)
            with self.assertRaisesRegex(DurableExecutionError, "semantic_validation_failure"):
                execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=lambda _payload: bad_response)
            self.assertEqual(len(list((run_dir / "ledgers" / "raw_responses").glob("*.json"))), 1)
            self.assertFalse(list((run_dir / "ledgers" / "accepted_predictions").glob("*.json")))

    def test_prediction_persistence_failure_remains_recoverable_and_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)

            def prediction_writer(_path, _record):
                raise RuntimeError("cannot persist prediction")

            with self.assertRaisesRegex(PredictionPersistenceError, "prediction_persistence_failure"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    dispatch_fn=lambda _payload: valid_response(identity, members),
                    prediction_persistor=prediction_writer,
                )
            summary = read_json(run_dir / "reconciliation_summary.json")
            transaction = read_json(next((run_dir / "ledgers" / "transactions").glob("*.json")))
            reservation = read_json(next((run_dir / "ledgers" / "reservations").glob("*.json")))
            self.assertEqual(transaction["status"], "prediction_persistence_failed")
            self.assertEqual(summary["recoverable_transactions"], 1)
            self.assertEqual(summary["unresolved_transactions"], 1)
            self.assertEqual(reservation["status"], "released")
            self.assertEqual(len(list((run_dir / "ledgers" / "raw_responses").glob("*.json"))), 1)

    def test_retry_policy_transient_once_and_no_retry_for_non_retryable_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp, "RUN-RETRY")
            calls = {"count": 0}

            def flaky(_payload):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise TimeoutError("slow")
                return valid_response(identity, members)

            execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=flaky)
            transaction = read_json(next((run_dir / "ledgers" / "transactions").glob("*.json")))
            failure = read_json(next((run_dir / "ledgers" / "failures").glob("*.json")))
            self.assertEqual(calls["count"], 2)
            self.assertEqual(transaction["retry_count"], 1)
            self.assertTrue(failure["retryable"])

        for run_id, mutate_response, expected in [
            ("RUN-MALFORMED", lambda response: {**response, "raw_output": "not-json"}, "malformed_reduced_output"),
            ("RUN-BAD-TOKEN", lambda response: {**response, "raw_output": json.dumps({**json.loads(response["raw_output"]), "primary_driver_token": "DRV_bad"})}, "invalid_driver_token"),
            ("RUN-MODEL-SUB", lambda response: {**response, "actual_model": "different-model"}, "model_substitution"),
        ]:
            with tempfile.TemporaryDirectory() as tmp:
                package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp, run_id)
                calls = {"count": 0}
                response = mutate_response(valid_response(identity, members))

                def dispatch(_payload):
                    calls["count"] += 1
                    return response

                with self.assertRaisesRegex(DurableExecutionError, expected):
                    execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=dispatch)
                self.assertEqual(calls["count"], 1)

    def test_reconciliation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, run_dir, _run_manifest, identity, members = make_package_and_run(tmp)
            execute_live_identity(run_dir=run_dir, package_dir=package, identity=identity, dispatch_fn=lambda _payload: valid_response(identity, members))
            first = reconcile_run(run_dir)
            second = reconcile_run(run_dir)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
