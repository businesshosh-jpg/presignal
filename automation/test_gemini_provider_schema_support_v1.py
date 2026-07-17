from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation.build_simplified_replay_package_v1 import SNAPSHOT, apps_script_source_binding, freeze_production_package
from automation.run_simplified_replay_canary_v1 import (
    _bridge_payload,
    _build_reduced_prompt,
    _load_package_state,
    execute_live_identity,
    initialize_durable_run,
)
from automation.simplified_authoritative_replay_contract_v1 import (
    ReducedForecastError,
    driver_options,
    reduced_output_response_schema,
    validate_and_resolve,
)


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "80d2789cb4071537220aaec719e24b5c14a3797c"
EVIDENCE_PACKAGE = ROOT / "outputs" / "simplified_authoritative_replay" / "production_packages" / "SIMPLIFIED-REPLAY-PROD-20260717T171207Z"
EVIDENCE_RUN = ROOT / "outputs" / "simplified_authoritative_replay" / "runs" / "SIMPLIFIED-REPLAY-CANARY-20260717T171207Z"
GEMINI_IDENTITIES = {
    "A": "AHRF_001102e8e2bfaaa792e13ceb213e",
    "E": "AHRF_009d2411c26358a782cef57e2c24",
}


NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = {};
vm.createContext(sandbox);
if (input.operation === 'validate' || input.operation === 'bridge') {
  vm.runInContext(fs.readFileSync('apps_script/authoritative_provider_bridge.js', 'utf8'), sandbox);
}
if (input.operation === 'gemini_body') {
  vm.runInContext(fs.readFileSync('apps_script/prediction_runner.js', 'utf8'), sandbox);
}
let output;
try {
  if (input.operation === 'validate') {
    output = {ok: true, schema: sandbox._validateAuthoritativeReducedResponseSchema_(input.schema, input.prompt_user)};
  } else if (input.operation === 'bridge') {
    let captured;
    sandbox._normalizeProviderName_ = value => value;
    sandbox._resolveProviders_ = () => [{name: 'Gemini', model: input.params.model, key: 'offline'}];
    sandbox._callProviderJsonObject_ = (provider, prompt, expected, responseSchema) => {
      captured = {provider, prompt, expected, response_schema: responseSchema};
      return {ai_name: provider.name, ai_model: provider.model, raw_output: '{}'};
    };
    output = {ok: true, result: sandbox.apiCallAuthoritativeProviderJsonObject(input.params), captured};
  } else if (input.operation === 'gemini_body') {
    output = {ok: true, body: sandbox._buildGeminiJsonObjectRequestBody_(input.prompt, input.schema)};
  } else {
    throw new Error('unknown operation');
  }
} catch (error) {
  output = {ok: false, error: String(error && error.message || error)};
}
process.stdout.write(JSON.stringify(output));
"""


def node_result(payload: dict) -> dict:
    result = subprocess.run(
        ["node", "-e", NODE_HARNESS],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def evidence_state() -> dict:
    return _load_package_state(EVIDENCE_PACKAGE)


def identity_context(arm: str) -> tuple[dict, list[dict], dict, dict]:
    state = evidence_state()
    identity = state["population"][GEMINI_IDENTITIES[arm]]
    members = state["members_by_session"][identity["session_id"]]
    schema = reduced_output_response_schema(members)
    prompt = _build_reduced_prompt(identity, state, members, schema)
    return identity, members, schema, prompt


def function_slice(source: str, name: str, next_name: str) -> str:
    start = source.index("function " + name)
    return source[start:source.index("function " + next_name, start)]


class GeminiProviderSchemaSupportTest(unittest.TestCase):
    def test_schema_is_separate_in_persisted_invocation_before_offline_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_binding = apps_script_source_binding()
            manifest = freeze_production_package(
                scientific_snapshot_path=SNAPSHOT,
                durable_output_root=root / "packages",
                package_id="GEMINI-SCHEMA-OFFLINE-PACKAGE",
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
                run_id="GEMINI-SCHEMA-OFFLINE-RUN",
                package_id=manifest["package_id"],
                whole_package_fingerprint=manifest["whole_package_sha256"],
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
            run_dir = root / "runs" / run_manifest["run_id"]
            state = _load_package_state(package)
            identity = state["population"][GEMINI_IDENTITIES["A"]]
            members = state["members_by_session"][identity["session_id"]]
            expected_tokens = [option["token"] for option in driver_options(members)]

            def dispatch(payload):
                invocation = json.loads(next((run_dir / "ledgers" / "invocations").glob("*.json")).read_text())
                self.assertEqual(invocation["payload"], payload)
                self.assertIn("response_schema", payload)
                self.assertNotIn("response_schema", payload["prompt"])
                self.assertEqual(payload["response_schema"]["properties"]["primary_driver_token"]["enum"], expected_tokens)
                return {
                    "actual_provider": identity["provider"],
                    "actual_model": identity["model"],
                    "raw_output": json.dumps({
                        "primary_driver_token": expected_tokens[0],
                        "secondary_driver_token": None,
                        "final_usdjpy_direction": "UP",
                        "reaction_strength": "MODERATE",
                        "confidence": 0.5,
                        "primary_thesis": "fixture",
                        "secondary_thesis": "",
                        "reasoning_steps": ["one", "two"],
                    }),
                }

            execute_live_identity(
                run_dir=run_dir,
                package_dir=package,
                identity=identity,
                deployment_metadata_reader=lambda project_id, deployment_id: {
                    "apps_script_project_id": project_id,
                    "execution_deployment_id": deployment_id,
                    "execution_deployment_version": 79,
                    "project_fingerprint": source_binding["project_fingerprint"],
                    "bridge_sha256": source_binding["bridge_sha256"],
                    "prediction_runner_sha256": source_binding["prediction_runner_sha256"],
                },
                dispatch_fn=dispatch,
            )

    def test_pack_a_and_e_use_the_same_frozen_schema_construction(self):
        schemas = {}
        for arm in ("A", "E"):
            identity, members, schema, prompt = identity_context(arm)
            payload = _bridge_payload("OFFLINE", identity, prompt, response_schema=schema)
            tokens = [option["token"] for option in driver_options(members)]
            self.assertEqual(payload["model"], "gemini-2.5-flash-lite")
            self.assertEqual(schema["properties"]["primary_driver_token"]["enum"], tokens)
            self.assertEqual(schema["properties"]["secondary_driver_token"]["anyOf"], [
                {"type": "string", "enum": tokens},
                {"type": "null"},
            ])
            schemas[arm] = copy.deepcopy(schema)
        for schema in schemas.values():
            schema["properties"]["primary_driver_token"]["enum"] = []
            schema["properties"]["secondary_driver_token"]["anyOf"][0]["enum"] = []
        self.assertEqual(schemas["A"], schemas["E"])

    def test_apps_script_validates_schema_and_rejects_unsupported_injection(self):
        _identity, _members, schema, prompt = identity_context("A")
        valid = node_result({"operation": "validate", "schema": schema, "prompt_user": prompt["user"]})
        self.assertTrue(valid["ok"])

        invalid_cases = []
        unknown = copy.deepcopy(schema)
        unknown["properties"]["prediction_path"] = {"type": "string"}
        invalid_cases.append(unknown)
        missing = copy.deepcopy(schema)
        missing["required"].remove("confidence")
        invalid_cases.append(missing)
        malformed = copy.deepcopy(schema)
        malformed["properties"]["primary_driver_token"]["enum"][0] = "not-a-driver-token"
        invalid_cases.append(malformed)
        empty = copy.deepcopy(schema)
        empty["properties"]["primary_driver_token"]["enum"] = []
        invalid_cases.append(empty)
        cross_session = copy.deepcopy(schema)
        _other_identity, other_members, _other_schema, _other_prompt = identity_context("E")
        cross_session["properties"]["primary_driver_token"]["enum"][0] = driver_options(other_members)[0]["token"]
        invalid_cases.append(cross_session)
        relational = copy.deepcopy(schema)
        relational["properties"]["prediction_path_target_type"] = {"type": "string"}
        invalid_cases.append(relational)
        arbitrary = copy.deepcopy(schema)
        arbitrary["$ref"] = "https://example.invalid/arbitrary-schema"
        invalid_cases.append(arbitrary)

        for candidate in invalid_cases:
            result = node_result({"operation": "validate", "schema": candidate, "prompt_user": prompt["user"]})
            self.assertFalse(result["ok"])
            self.assertIn("AUTHORITATIVE_RESPONSE_SCHEMA_INVALID", result["error"])

    def test_bridge_threads_schema_and_remains_backward_compatible_without_it(self):
        identity, _members, schema, prompt = identity_context("A")
        params = _bridge_payload("OFFLINE-RUN", identity, prompt, response_schema=schema)
        with_schema = node_result({"operation": "bridge", "params": params})
        self.assertTrue(with_schema["ok"])
        self.assertEqual(with_schema["captured"]["response_schema"], schema)

        without_schema_params = dict(params)
        without_schema_params.pop("response_schema")
        without_schema = node_result({"operation": "bridge", "params": without_schema_params})
        self.assertTrue(without_schema["ok"])
        self.assertIsNone(without_schema["captured"]["response_schema"])

    def test_gemini_request_attaches_schema_without_changing_existing_options(self):
        _identity, _members, schema, prompt = identity_context("A")
        with_schema = node_result({"operation": "gemini_body", "schema": schema, "prompt": prompt})
        without_schema = node_result({"operation": "gemini_body", "schema": None, "prompt": prompt})
        self.assertTrue(with_schema["ok"])
        generation = with_schema["body"]["generationConfig"]
        baseline_generation = without_schema["body"]["generationConfig"]
        self.assertEqual(generation["responseJsonSchema"], schema)
        self.assertEqual(generation["response_mime_type"], "application/json")
        self.assertEqual(generation["temperature"], baseline_generation["temperature"])
        self.assertEqual(generation["seed"], baseline_generation["seed"])
        self.assertNotIn("responseJsonSchema", baseline_generation)
        self.assertEqual(with_schema["body"]["contents"], without_schema["body"]["contents"])

    def test_openai_and_anthropic_request_builders_are_unchanged(self):
        baseline = subprocess.run(
            ["git", "show", f"{BASELINE}:apps_script/prediction_runner.js"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        current = (ROOT / "apps_script" / "prediction_runner.js").read_text()
        self.assertEqual(
            function_slice(current, "_callOpenAiJsonObject_", "_buildGeminiJsonObjectRequestBody_"),
            function_slice(baseline, "_callOpenAiJsonObject_", "_callGeminiJsonObject_"),
        )
        self.assertEqual(
            function_slice(current, "_callClaudeJsonObject_", "_strictParseJsonObject_"),
            function_slice(baseline, "_callClaudeJsonObject_", "_strictParseJsonObject_"),
        )

    def test_invalid_gemini_token_remains_rejected_without_coercion(self):
        state = evidence_state()
        identity = state["population"][GEMINI_IDENTITIES["A"]]
        members = state["members_by_session"][identity["session_id"]]
        raw_record = next(
            json.loads(path.read_text())
            for path in (EVIDENCE_RUN / "ledgers" / "raw_responses").glob("*.json")
            if json.loads(path.read_text())["identity_id"] == identity["forecast_identity"]
        )
        payload = json.loads(raw_record["response"]["raw_output"])
        self.assertEqual(payload["secondary_driver_token"], "DRV_67df-4653-033b-9e97")
        with self.assertRaisesRegex(ReducedForecastError, "SECONDARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, members)
        self.assertEqual(payload["secondary_driver_token"], "DRV_67df-4653-033b-9e97")


if __name__ == "__main__":
    unittest.main()
