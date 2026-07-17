from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from automation.build_simplified_replay_package_v1 import SNAPSHOT, apps_script_source_binding, freeze_production_package
from automation.run_simplified_replay_canary_v1 import (
    _build_reduced_prompt,
    _load_package_state,
    execute_live_identity,
    initialize_durable_run,
)
from automation.simplified_authoritative_replay_contract_v1 import (
    ReducedForecastError,
    driver_options,
    parse_reduced_output_json,
    validate_and_resolve,
)


ROOT = Path(__file__).resolve().parents[1]
FAILED_RUN = ROOT / "outputs" / "simplified_authoritative_replay" / "runs" / "SIMPLIFIED-REPLAY-CANARY-20260717T162807Z"
FAILED_PACKAGE = ROOT / "outputs" / "simplified_authoritative_replay" / "production_packages" / "SIMPLIFIED-REPLAY-PROD-20260717T162728Z"
FIXTURES = {
    "openai_e": ("AHRF_00333536b339e395ca3c2dd3759c", "7ba4daaac80f6d8fe96b3571431dcff131b69461642e83da1887f132e2011530"),
    "anthropic_a": ("AHRF_00ca261e4d74e2480ba89182727a", "fe07e70ca8211ee310c6feac9b7a98afe676d7cd633ff2565d436b1106709e3d"),
    "anthropic_e": ("AHRF_004876309f32b88b1b2c03fe2d5a", "ff77b4c8bd22caf75b9d6dec9d69ff3785eabfae6cb37819722929e585f865ae"),
}


def package_state(package: Path = FAILED_PACKAGE) -> dict:
    return _load_package_state(package)


def raw_fixture(name: str) -> tuple[dict, str]:
    identity_id, expected_sha = FIXTURES[name]
    for path in (FAILED_RUN / "ledgers" / "raw_responses").glob("*.json"):
        record = json.loads(path.read_text())
        if record["identity_id"] == identity_id:
            raw = record["response"]["raw_output"]
            if hashlib.sha256(raw.encode()).hexdigest() != expected_sha:
                raise AssertionError("FAILED_CANARY_FIXTURE_CHANGED:" + name)
            return record, raw
    raise AssertionError("FAILED_CANARY_FIXTURE_MISSING:" + name)


def temporary_package_and_run(root: Path) -> tuple[Path, Path, dict, dict]:
    source_binding = apps_script_source_binding()
    manifest = freeze_production_package(
        scientific_snapshot_path=SNAPSHOT,
        durable_output_root=root / "packages",
        package_id="OFFLINE-ADHERENCE-FIXTURE",
        apps_script_project_id=source_binding["apps_script_project_id"],
        execution_deployment_id="AKfycbxd31I_td72HW0ZgScfYthYqliKfzBkQxE9EdURpTQU6ObQawGmX1sB5aVO3MADqXWf",
        execution_deployment_version=79,
        immutable_apps_script_version=79,
        project_fingerprint=source_binding["project_fingerprint"],
        bridge_source_fingerprint=source_binding["bridge_sha256"],
        prediction_runner_fingerprint=source_binding["prediction_runner_sha256"],
        contract_fingerprint="contract-sha",
        executor_fingerprint="executor-sha",
    )
    package = root / "packages" / manifest["package_id"]
    run_manifest = initialize_durable_run(
        package_dir=package,
        durable_run_root=root / "runs",
        run_id="OFFLINE-ADHERENCE-RUN",
        package_id=manifest["package_id"],
        whole_package_fingerprint=(package / "whole_package_sha256.txt").read_text().strip(),
        apps_script_project_id=source_binding["apps_script_project_id"],
        execution_deployment_id="AKfycbxd31I_td72HW0ZgScfYthYqliKfzBkQxE9EdURpTQU6ObQawGmX1sB5aVO3MADqXWf",
        execution_deployment_version=79,
        immutable_version_number=79,
        project_fingerprint=source_binding["project_fingerprint"],
        bridge_sha256=source_binding["bridge_sha256"],
        prediction_runner_sha256=source_binding["prediction_runner_sha256"],
        contract_fingerprint="contract-sha",
        executor_fingerprint="executor-sha",
    )
    return package, root / "runs" / run_manifest["run_id"], manifest, _load_package_state(package)


class ProviderContractAdherenceRepairTest(unittest.TestCase):
    def test_exact_anthropic_fixtures_normalize_one_outer_fence_and_validate(self):
        state = package_state()
        for fixture_name in ("anthropic_a", "anthropic_e"):
            record, raw = raw_fixture(fixture_name)
            payload, metadata = parse_reduced_output_json(raw)
            identity = state["population"][record["identity_id"]]
            resolved = validate_and_resolve(payload, state["members_by_session"][identity["session_id"]])
            self.assertEqual(metadata["output_normalization"], "single_outer_markdown_fence_removed")
            self.assertEqual(resolved["primary_driver_event_id"], driver_options(state["members_by_session"][identity["session_id"]])[5 if fixture_name == "anthropic_a" else 4]["event_id"])

    def test_plain_json_and_invalid_fence_forms_fail_closed(self):
        plain = '{"primary_driver_token":"x"}'
        payload, metadata = parse_reduced_output_json(plain)
        self.assertEqual(payload["primary_driver_token"], "x")
        self.assertEqual(metadata["output_normalization"], "none")
        bare_fence_payload, bare_fence_metadata = parse_reduced_output_json('```\n{"primary_driver_token":"x"}\n```')
        self.assertEqual(bare_fence_payload, payload)
        self.assertEqual(bare_fence_metadata["output_normalization"], "single_outer_markdown_fence_removed")
        for raw in (
            'Explanation\\n```json\\n{}\\n```',
            '```json\\n{}\\n```\\n```json\\n{}\\n```',
            '```json\\n{not-json}\\n```',
            '```json\\n```json\\n{}\\n```\\n```',
        ):
            with self.assertRaises(json.JSONDecodeError):
                parse_reduced_output_json(raw)

    def test_openai_invalid_secondary_fixture_stays_invalid_without_coercion(self):
        state = package_state()
        record, raw = raw_fixture("openai_e")
        payload, metadata = parse_reduced_output_json(raw)
        identity = state["population"][record["identity_id"]]
        allowed = {option["token"] for option in driver_options(state["members_by_session"][identity["session_id"]])}
        self.assertEqual(metadata["output_normalization"], "none")
        self.assertEqual(payload["secondary_driver_token"], "DRV_26cc2b771aa3e0e75089")
        self.assertNotIn(payload["secondary_driver_token"], allowed)
        with self.assertRaisesRegex(ReducedForecastError, "SECONDARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, state["members_by_session"][identity["session_id"]])
        self.assertEqual(payload["secondary_driver_token"], "DRV_26cc2b771aa3e0e75089")

    def test_validator_rejects_event_names_and_other_session_tokens(self):
        state = package_state()
        identity = state["population"][FIXTURES["openai_e"][0]]
        members = state["members_by_session"][identity["session_id"]]
        payload, _metadata = parse_reduced_output_json(raw_fixture("openai_e")[1])
        payload["primary_driver_token"] = members[0]["indicator_name"]
        with self.assertRaisesRegex(ReducedForecastError, "PRIMARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, members)
        other_session = next(session_id for session_id in state["members_by_session"] if session_id != identity["session_id"])
        payload["primary_driver_token"] = driver_options(state["members_by_session"][other_session])[0]["token"]
        with self.assertRaisesRegex(ReducedForecastError, "PRIMARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, members)

    def test_prompt_materializes_only_frozen_session_tokens_and_null_secondary(self):
        state = package_state()
        identity = state["population"][FIXTURES["openai_e"][0]]
        members = state["members_by_session"][identity["session_id"]]
        prompt = _build_reduced_prompt(identity, state, members)
        context = json.loads(prompt["user"])
        expected = [option["token"] for option in driver_options(members)]
        self.assertEqual(context["allowed_primary_driver_tokens"], expected)
        self.assertEqual(context["allowed_secondary_driver_tokens"], expected)
        self.assertIn("JSON null", prompt["instruction"])
        self.assertEqual(context["dynamic_token_enum_schema"]["primary_driver_token"]["enum"], expected)
        secondary_any_of = context["dynamic_token_enum_schema"]["secondary_driver_token"]["anyOf"]
        self.assertEqual(secondary_any_of[0]["enum"], expected)
        self.assertEqual(secondary_any_of[1], {"type": "null"})
        other_session = next(session_id for session_id in state["members_by_session"] if session_id != identity["session_id"])
        other_tokens = {option["token"] for option in driver_options(state["members_by_session"][other_session])}
        self.assertFalse(set(expected) & other_tokens)
        self.assertFalse(set(context["allowed_primary_driver_tokens"]) & other_tokens)

    def test_exact_permitted_secondary_and_null_continue_to_resolve(self):
        state = package_state()
        identity = state["population"][FIXTURES["anthropic_a"][0]]
        members = state["members_by_session"][identity["session_id"]]
        payload, _metadata = parse_reduced_output_json(raw_fixture("anthropic_a")[1])
        self.assertTrue(validate_and_resolve(payload, members)["secondary_driver_event_id"])
        payload["secondary_driver_token"] = None
        payload["secondary_thesis"] = ""
        self.assertEqual(validate_and_resolve(payload, members)["secondary_driver_event_id"], "")
        payload["secondary_driver_token"] = ""
        with self.assertRaisesRegex(ReducedForecastError, "SECONDARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, members)

    def test_normalization_metadata_is_persisted_in_offline_execution(self):
        record, raw = raw_fixture("anthropic_e")
        with tempfile.TemporaryDirectory() as temporary:
            package, run_dir, _manifest, state = temporary_package_and_run(Path(temporary))
            identity = state["population"][record["identity_id"]]
            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                deployment_metadata_reader=lambda project_id, deployment_id: {
                    "apps_script_project_id": project_id,
                    "execution_deployment_id": deployment_id,
                    "execution_deployment_version": 79,
                    "project_fingerprint": apps_script_source_binding()["project_fingerprint"],
                    "bridge_sha256": apps_script_source_binding()["bridge_sha256"],
                    "prediction_runner_sha256": apps_script_source_binding()["prediction_runner_sha256"],
                },
                dispatch_fn=lambda _payload: {
                    "actual_provider": identity["provider"],
                    "actual_model": identity["model"],
                    "raw_output": raw,
                },
            )
            transaction = json.loads(next((run_dir / "ledgers" / "transactions").glob("*.json")).read_text())
            self.assertEqual(transaction["parser_metadata"]["output_normalization"], "single_outer_markdown_fence_removed")
            self.assertFalse((run_dir / "prediction_path").exists())


if __name__ == "__main__":
    unittest.main()
