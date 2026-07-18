from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.build_simplified_replay_package_v1 import (
    SNAPSHOT,
    apps_script_source_binding,
    freeze_production_package,
    verify_whole_package_fingerprint,
)
from automation.local_git_repository_state_v1 import read_local_git_repository_state
from automation.run_simplified_replay_canary_v1 import (
    DurableExecutionError,
    _load_package_state,
    _sha256,
    execute_live_identity,
    initialize_durable_run,
)
from automation.simplified_authoritative_replay_contract_v1 import driver_options


ROOT = Path(__file__).resolve().parents[1]
GIT_COMMIT = "8bc7275412c64559e6698fef46668cbdfac160d7"
GIT_BRANCH = "codex-simplified-authoritative-replay"
PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
DEPLOYMENT_ID = "AKfycbxd31I_td72HW0ZgScfYthYqliKfzBkQxE9EdURpTQU6ObQawGmX1sB5aVO3MADqXWf"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def git_state(
    commit: str = GIT_COMMIT,
    *,
    branch: str | None = GIT_BRANCH,
    clean: bool = True,
    detached: bool = False,
    repository_path: Path = ROOT,
    remote_name: str | None = "origin",
) -> dict:
    return {
        "git_commit": commit,
        "git_branch": branch,
        "git_worktree_clean": clean,
        "git_detached_head": detached,
        "git_repository_path": str(repository_path),
        "git_remote_name": remote_name,
    }


def package_inputs(root: Path, state: dict | None = None, package_id: str = "LOCAL-GIT-PACKAGE") -> dict:
    observed = dict(state or git_state())
    source = apps_script_source_binding()
    return {
        "scientific_snapshot_path": SNAPSHOT,
        "durable_output_root": root,
        "package_id": package_id,
        "apps_script_project_id": source["apps_script_project_id"],
        "execution_deployment_id": DEPLOYMENT_ID,
        "execution_deployment_version": 79,
        "immutable_apps_script_version": 79,
        "project_fingerprint": source["project_fingerprint"],
        "bridge_source_fingerprint": source["bridge_sha256"],
        "prediction_runner_fingerprint": source["prediction_runner_sha256"],
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
        "expected_git_commit": observed.get("git_commit"),
        "repository_path": observed.get("git_repository_path", ROOT),
        "repository_state_reader": lambda _path: dict(observed),
    }


def init_inputs(package: Path, manifest: dict, run_root: Path, run_id: str = "LOCAL-GIT-RUN") -> dict:
    deployment = read_json(package / "binding" / "immutable_deployment_binding.json")
    git_binding = read_json(package / "binding" / "local_git_repository_binding.json")
    return {
        "package_dir": package,
        "durable_run_root": run_root,
        "run_id": run_id,
        "package_id": manifest["package_id"],
        "whole_package_fingerprint": manifest["whole_package_sha256"],
        "apps_script_project_id": deployment["apps_script_project_id"],
        "execution_deployment_id": deployment["execution_deployment_id"],
        "execution_deployment_version": deployment["execution_deployment_version"],
        "immutable_version_number": deployment["immutable_version_number"],
        "project_fingerprint": deployment["project_fingerprint"],
        "bridge_sha256": deployment["bridge_sha256"],
        "prediction_runner_sha256": deployment["prediction_runner_sha256"],
        "contract_fingerprint": "contract-sha",
        "executor_fingerprint": "executor-sha",
        **git_binding,
    }


def matching_deployment(project_id: str, deployment_id: str) -> dict:
    source = apps_script_source_binding()
    return {
        "apps_script_project_id": project_id,
        "execution_deployment_id": deployment_id,
        "execution_deployment_version": 79,
        "project_fingerprint": source["project_fingerprint"],
        "bridge_sha256": source["bridge_sha256"],
        "prediction_runner_sha256": source["prediction_runner_sha256"],
    }


def make_package_and_run(root: Path, state: dict | None = None, run_id: str = "LOCAL-GIT-RUN") -> tuple[Path, Path, dict]:
    observed = dict(state or git_state())
    manifest = freeze_production_package(**package_inputs(root / "packages", observed))
    package = root / "packages" / manifest["package_id"]
    run_manifest = initialize_durable_run(**init_inputs(package, manifest, root / "runs", run_id))
    return package, root / "runs" / run_id, run_manifest


def identity_and_response(package: Path, index: int = 0) -> tuple[dict, dict]:
    state = _load_package_state(package)
    identity = list(state["population"].values())[index]
    members = state["members_by_session"][identity["session_id"]]
    token = driver_options(members)[0]["token"]
    return identity, {
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


def create_temporary_git_repository(path: Path) -> str:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "offline@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Offline Fixture"], cwd=path, check=True)
    (path / ".gitignore").write_text("*.generated\n")
    (path / "tracked.txt").write_text("baseline\n")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=path, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, text=True, capture_output=True, check=True).stdout.strip()


class LocalGitRepositoryBindingTest(unittest.TestCase):
    def test_package_records_git_binding_manifest_and_informational_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = freeze_production_package(**package_inputs(root))
            package = root / manifest["package_id"]
            binding = read_json(package / "binding" / "local_git_repository_binding.json")
            provenance = read_json(package / "provenance" / "local_git_repository.json")
            self.assertEqual(binding, {
                "git_commit": GIT_COMMIT,
                "git_branch": GIT_BRANCH,
                "git_worktree_clean": True,
                "git_detached_head": False,
            })
            self.assertEqual(manifest["local_git_repository_binding"], binding)
            self.assertEqual(manifest["local_git_repository_provenance"], provenance)
            self.assertEqual(provenance["git_remote_name"], "origin")
            self.assertTrue(verify_whole_package_fingerprint(package))

    def test_git_commit_changes_whole_package_fingerprint(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_manifest = freeze_production_package(**package_inputs(Path(first), git_state("a" * 40)))
            second_manifest = freeze_production_package(**package_inputs(Path(second), git_state("b" * 40)))
            self.assertNotEqual(first_manifest["whole_package_sha256"], second_manifest["whole_package_sha256"])

    def test_package_rejects_missing_malformed_mismatched_dirty_and_unreadable_git_state(self):
        cases = []
        missing_observed = package_inputs(Path("unused"), git_state())
        missing_observed["repository_state_reader"] = lambda _path: {**git_state(), "git_commit": ""}
        cases.append(("missing", missing_observed, "LOCAL_GIT_COMMIT_MISSING"))
        malformed = package_inputs(Path("unused"), git_state())
        malformed["expected_git_commit"] = "short"
        cases.append(("malformed", malformed, "EXPECTED_GIT_COMMIT_MALFORMED"))
        mismatched = package_inputs(Path("unused"), git_state())
        mismatched["expected_git_commit"] = "b" * 40
        cases.append(("mismatch", mismatched, "LOCAL_GIT_HEAD_MISMATCH"))
        dirty = package_inputs(Path("unused"), git_state(clean=False))
        cases.append(("dirty", dirty, "LOCAL_GIT_TRACKED_WORKTREE_DIRTY"))
        unreadable = package_inputs(Path("unused"), git_state())
        unreadable["repository_state_reader"] = lambda _path: (_ for _ in ()).throw(RuntimeError("offline unreadable"))
        cases.append(("unreadable", unreadable, "LOCAL_GIT_REPOSITORY_UNREADABLE"))
        for name, inputs, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                inputs["durable_output_root"] = Path(temporary)
                inputs["package_id"] = "PACKAGE-" + name.upper()
                with self.assertRaisesRegex(ValueError, error):
                    freeze_production_package(**inputs)

    def test_local_reader_ignores_untracked_outputs_and_ignored_files_without_remote_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            commit = create_temporary_git_repository(repo)
            (repo / "outputs").mkdir()
            (repo / "outputs" / "evidence.json").write_text("{}\n")
            (repo / "cache.generated").write_text("ignored\n")
            with patch("automation.local_git_repository_state_v1.subprocess.run", wraps=subprocess.run) as runner:
                observed = read_local_git_repository_state(repo)
            self.assertEqual(observed["git_commit"], commit)
            self.assertTrue(observed["git_worktree_clean"])
            self.assertIsNone(observed["git_remote_name"])
            commands = [call.args[0] for call in runner.call_args_list]
            self.assertFalse(any("remote" in command or "fetch" in command for command in commands))
            inputs = package_inputs(repo / "packages", observed, "UNTRACKED-OUTPUTS-PERMITTED")
            inputs["repository_path"] = repo
            inputs["repository_state_reader"] = read_local_git_repository_state
            self.assertEqual(freeze_production_package(**inputs)["local_git_repository_binding"]["git_commit"], commit)

    def test_local_reader_detects_modified_and_staged_tracked_files(self):
        for staged in (False, True):
            with self.subTest(staged=staged), tempfile.TemporaryDirectory() as temporary:
                repo = Path(temporary)
                create_temporary_git_repository(repo)
                (repo / "tracked.txt").write_text("changed\n")
                if staged:
                    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
                observed = read_local_git_repository_state(repo)
                self.assertFalse(observed["git_worktree_clean"])
                inputs = package_inputs(repo / "packages", {**observed, "git_worktree_clean": True}, "DIRTY-PACKAGE")
                inputs["expected_git_commit"] = observed["git_commit"]
                inputs["repository_path"] = repo
                inputs["repository_state_reader"] = read_local_git_repository_state
                with self.assertRaisesRegex(ValueError, "LOCAL_GIT_TRACKED_WORKTREE_DIRTY"):
                    freeze_production_package(**inputs)

    def test_detached_head_with_matching_commit_is_recorded_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            commit = create_temporary_git_repository(repo)
            subprocess.run(["git", "checkout", "--detach", commit], cwd=repo, check=True, capture_output=True)
            observed = read_local_git_repository_state(repo)
            self.assertTrue(observed["git_detached_head"])
            self.assertIsNone(observed["git_branch"])
            manifest = freeze_production_package(
                **{
                    **package_inputs(repo / "packages", observed, "DETACHED-PACKAGE"),
                    "repository_path": repo,
                    "repository_state_reader": read_local_git_repository_state,
                }
            )
            binding = read_json(repo / "packages" / manifest["package_id"] / "binding" / "local_git_repository_binding.json")
            self.assertIsNone(binding["git_branch"])
            self.assertTrue(binding["git_detached_head"])

    def test_run_copies_git_binding_and_binding_hash_covers_git_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, _run_dir, manifest = make_package_and_run(Path(temporary))
            binding = manifest["binding"]
            self.assertEqual(binding["git_commit"], GIT_COMMIT)
            self.assertEqual(binding["git_branch"], GIT_BRANCH)
            self.assertTrue(binding["git_worktree_clean"])
            self.assertEqual(manifest["binding_sha256"], _sha256(binding))
            changed = dict(binding)
            changed["git_commit"] = "c" * 40
            self.assertNotEqual(manifest["binding_sha256"], _sha256(changed))
            package_provenance = read_json(package / "provenance" / "local_git_repository.json")
            self.assertEqual(manifest["local_git_repository_provenance"], package_provenance)

    def test_run_initialization_rejects_commit_branch_and_detached_mismatches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_manifest = freeze_production_package(**package_inputs(root / "packages"))
            package = root / "packages" / package_manifest["package_id"]
            cases = (
                ("COMMIT", "git_commit", "d" * 40),
                ("BRANCH", "git_branch", "different-branch"),
                ("DETACHED", "git_detached_head", True),
            )
            for name, key, value in cases:
                inputs = init_inputs(package, package_manifest, root / "runs", "RUN-" + name)
                inputs[key] = value
                with self.assertRaisesRegex(DurableExecutionError, key):
                    initialize_durable_run(**inputs)

    def test_matching_predispatch_git_state_is_recorded_before_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            identity, response = identity_and_response(package)

            def dispatch(_payload):
                self.assertEqual(len(list((run_dir / "ledgers" / "provenance_verifications").glob("*.json"))), 1)
                self.assertEqual(len(list((run_dir / "ledgers" / "deployment_verifications").glob("*.json"))), 1)
                self.assertEqual(len(list((run_dir / "ledgers" / "reservations").glob("*.json"))), 1)
                return response

            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                repository_state_reader=lambda _path: git_state(remote_name="descriptive-only"),
                deployment_metadata_reader=matching_deployment,
                dispatch_fn=dispatch,
            )
            record = read_json(next((run_dir / "ledgers" / "provenance_verifications").glob("*.json")))
            self.assertEqual(record["verification_status"], "PASS")
            self.assertEqual(record["expected_git_commit"], GIT_COMMIT)
            self.assertEqual(record["observed_git_commit"], GIT_COMMIT)
            self.assertEqual(record["expected_git_branch"], GIT_BRANCH)
            self.assertEqual(record["observed_git_branch"], GIT_BRANCH)
            self.assertFalse(record["observed_detached_head"])
            self.assertTrue(record["tracked_worktree_clean"])
            self.assertTrue(record["package_run_git_binding_match"])
            self.assertTrue(record["metadata_digest"])

    def test_failed_predispatch_git_checks_create_no_execution_state(self):
        cases = (
            ("HEAD", git_state("e" * 40), "LOCAL_GIT_HEAD_MISMATCH"),
            ("DIRTY", git_state(clean=False), "LOCAL_GIT_TRACKED_WORKTREE_DIRTY"),
        )
        for name, observed, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                package, run_dir, _manifest = make_package_and_run(Path(temporary), run_id="RUN-" + name)
                identity, _response = identity_and_response(package)
                calls = {"dispatch": 0, "deployment": 0}

                def deployment_reader(_project: str, _deployment: str) -> dict:
                    calls["deployment"] += 1
                    return {}

                def dispatch(_payload):
                    calls["dispatch"] += 1
                    return {}

                with self.assertRaisesRegex(DurableExecutionError, error):
                    execute_live_identity(
                        run_dir=run_dir,
                        package_dir=package,
                        identity=identity,
                        repository_state_reader=lambda _path, value=observed: value,
                        deployment_metadata_reader=deployment_reader,
                        dispatch_fn=dispatch,
                    )
                self.assertEqual(calls, {"dispatch": 0, "deployment": 0})
                for ledger in ("reservations", "invocations", "transactions", "deployment_verifications"):
                    self.assertFalse(list((run_dir / "ledgers" / ledger).glob("*.json")))
                verification = read_json(next((run_dir / "ledgers" / "provenance_verifications").glob("*.json")))
                self.assertEqual(verification["failure_classification"], error)

    def test_resumed_execution_reverifies_and_stops_after_local_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            observations = [git_state(), git_state(clean=False)]
            calls = {"git": 0, "dispatch": 0}

            def repository_reader(_path: Path) -> dict:
                value = observations[calls["git"]]
                calls["git"] += 1
                return value

            first_identity, first_response = identity_and_response(package, 0)
            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=first_identity,
                repository_state_reader=repository_reader,
                deployment_metadata_reader=matching_deployment,
                dispatch_fn=lambda _payload: first_response,
            )
            second_identity, _second_response = identity_and_response(package, 1)
            with self.assertRaisesRegex(DurableExecutionError, "LOCAL_GIT_TRACKED_WORKTREE_DIRTY"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=second_identity,
                    repository_state_reader=repository_reader,
                    deployment_metadata_reader=matching_deployment,
                    dispatch_fn=lambda _payload: calls.__setitem__("dispatch", calls["dispatch"] + 1),
                )
            self.assertEqual(calls["git"], 2)
            self.assertEqual(calls["dispatch"], 0)
            self.assertEqual(len(list((run_dir / "ledgers" / "provenance_verifications").glob("*.json"))), 2)
            self.assertEqual(len(list((run_dir / "ledgers" / "deployment_verifications").glob("*.json"))), 1)
            self.assertEqual(len(list((run_dir / "ledgers" / "invocations").glob("*.json"))), 1)
            self.assertEqual(len(list((run_dir / "ledgers" / "transactions").glob("*.json"))), 1)

    def test_git_binding_mutation_is_rejected_before_verification_or_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest = make_package_and_run(Path(temporary))
            identity, _response = identity_and_response(package)
            run_manifest = read_json(run_dir / "run_manifest.json")
            run_manifest["binding"]["git_commit"] = "f" * 40
            (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, sort_keys=True, indent=2) + "\n")
            with self.assertRaisesRegex(DurableExecutionError, "RUN_DEPLOYMENT_BINDING_IMMUTABILITY_VIOLATION"):
                execute_live_identity(
                    run_dir=run_dir,
                    package_dir=package,
                    identity=identity,
                    repository_state_reader=lambda _path: git_state(),
                    deployment_metadata_reader=matching_deployment,
                    dispatch_fn=lambda _payload: self.fail("dispatch must not run"),
                )
            self.assertFalse(list((run_dir / "ledgers" / "provenance_verifications").glob("*.json")))


if __name__ == "__main__":
    unittest.main()
