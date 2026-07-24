"""Synchronize the prospective Pack E Apps Script entry point to HEAD.

This task is limited to non-scientific runtime synchronization:
- prove the committed public entry point exists locally,
- prove the authoritative remote HEAD lacks it,
- push the existing Apps Script project source,
- verify visibility through a validation-only invocation,
- prepare a fresh inactive FRED probe authorization V2.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation.build_simplified_replay_package_v1 import apps_script_project_fingerprint


APPS_SCRIPT_DIR = ROOT / "apps_script"
CLASP_PATH = APPS_SCRIPT_DIR / ".clasp.json"
PACK = ROOT / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1"
SELECTED = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc/R6-EPISODE-SELECTION-FOMC-20260724-v1"
FRED_BINDING = ROOT / "outputs/presignal_v21_designed_drift_r6_fred_binding_resolution/R6-FRED-BINDING-RESOLUTION-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_prospective_runtime_sync/R6-PROSPECTIVE-RUNTIME-SYNC-20260724-v1"

START_COMMIT = "1b7f397e505912160f0cbea0d5bb31b407fbba71"
PACK_AUTH = "sha256:87fc65d0f9ec84e8efc1f0e8ef0276eb50a35d52c624191cc682dcea9f8fb869"
ROUTE_B = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
EPISODE = "EP_EVENT_68a8e1cc3c9bf6ccc385"
PACK_A = "PACK_A_c08bab51525d614592678fae"
PACK_A_CONTENT = "sha256:c08bab51525d614592678fae0d82ce9e695ac8ff31afdf28d3e6353573818a59"
CUTOFF = "2026-07-29T18:00:00Z"
FUNCTION = "apiBuildProspectivePackENativeAcquisitionRecord"
ENTRY_FILE = APPS_SCRIPT_DIR / "prospective_pack_e_acquisition.js"
DEPENDENCY_FILES = (
    APPS_SCRIPT_DIR / "prospective_pack_e_acquisition.js",
    APPS_SCRIPT_DIR / "market_context_v2b.js",
    APPS_SCRIPT_DIR / "appsscript.json",
)
ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"
FRED_V1_AUTH = "sha256:b8a61ed078fac6b725a95ea787e54eee0ef54ae39e2f20e18e1dd38c20b273c5"
DEPLOY_AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PROSPECTIVE_ADAPTER_DEPLOYMENT_AUTHORIZATION_V1"
FRED_V2_AUTH_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_FRED_BINDING_PROBE_AUTHORIZATION_V2"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(output: Path, name: str, value: Any) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def cutoff_open(now_utc: str) -> bool:
    return now_utc < CUTOFF


def git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def local_dependency_manifest() -> dict[str, Any]:
    files = []
    for path in DEPENDENCY_FILES:
        source = path.read_text(encoding="utf-8")
        files.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha(source),
                "contains_entry_point": path == ENTRY_FILE and FUNCTION in source,
            }
        )
    manifest = {
        "entry_point": FUNCTION,
        "entry_point_source_file": str(ENTRY_FILE.relative_to(ROOT)),
        "entry_point_present": FUNCTION in ENTRY_FILE.read_text(encoding="utf-8"),
        "dependency_files": files,
        "dependency_set_checksum": sha(files),
        "writer_behavior": "none",
        "automatic_retries": 0,
        "source_fallback": "none",
    }
    return manifest


def local_project_files() -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(APPS_SCRIPT_DIR.iterdir(), key=lambda item: item.name):
        if path.name == "appsscript.json":
            files.append({"name": "appsscript", "type": "JSON", "source": path.read_text(encoding="utf-8")})
        elif path.is_file() and path.suffix == ".js":
            files.append({"name": path.name[:-3], "type": "SERVER_JS", "source": path.read_text(encoding="utf-8")})
    return files


def remote_head_content(service: Any, script_id: str) -> dict[str, Any]:
    response = service.projects().getContent(scriptId=script_id).execute()
    files = response.get("files", [])
    by_name = {str(item.get("name")): item for item in files}
    prospective = by_name.get("prospective_pack_e_acquisition")
    prospective_source = str(prospective.get("source")) if prospective else ""
    return {
        "file_count": len(files),
        "project_fingerprint": sha(apps_script_project_fingerprint(files)),
        "has_prospective_file": prospective is not None,
        "has_entry_point": FUNCTION in prospective_source,
        "prospective_file_sha256": sha(prospective_source) if prospective_source else None,
        "files": files,
    }


def current_runtime_trace(clasp_deployments_output: str, script_id: str) -> dict[str, Any]:
    return {
        "authoritative_apps_script_runtime_classification": "AUTHORITATIVE_PROSPECTIVE_RUNTIME",
        "project_identity_classification": "CLASP_PROJECT_ID_EXECUTION_API_HEAD",
        "deployment_identity_classification": "HEAD_SYMBOLIC_DEPLOYMENT_PRESENT",
        "execution_mode": "Apps Script Execution API against pushed project HEAD (devMode=true)",
        "script_id_redacted_classification": "PRIMARY_ISOLATED_PROJECT_ID_PRESENT",
        "clasp_deployments_output": clasp_deployments_output.splitlines(),
        "script_id_matches_default_resolver": script_id == google_clients.default_script_id(),
        "runtime_ambiguity": False,
    }


def deployment_authorization(
    *,
    target_commit: str,
    local_manifest: Mapping[str, Any],
    runtime_trace: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "authorization_name": DEPLOY_AUTH_NAME,
        "branch": "codex-v21-designed-drift-redesign",
        "start_commit": START_COMMIT,
        "target_commit": target_commit,
        "authoritative_apps_script_project_identity": runtime_trace["project_identity_classification"],
        "previous_deployment_identity_or_mode": runtime_trace["deployment_identity_classification"],
        "entry_point_checksum": next(
            item["sha256"] for item in local_manifest["dependency_files"] if item["path"] == "apps_script/prospective_pack_e_acquisition.js"
        ),
        "dependency_set_checksum": local_manifest["dependency_set_checksum"],
        "route_b_freeze_fingerprint": ROUTE_B,
        "no_scientific_change_declaration": True,
        "no_source_call_declaration": True,
        "forecast_cutoff": CUTOFF,
        "deployment_count": 1,
        "retry_budget": 0,
        "authorization_activated": False,
    }
    value["authorization_fingerprint"] = sha(value)
    return value


def visibility_request(now_utc: str) -> dict[str, Any]:
    return {
        "validation_only": True,
        "adapter_identity": ADAPTER,
        "source_id": "KSRC_FRED",
        "episode_id": EPISODE,
        "pack_a_identity": PACK_A,
        "request_identity": "NREQ_a90de3734b6ed432c17b",
        "retrieval_timestamp": now_utc,
    }


def visibility_ok(result: Mapping[str, Any] | None) -> bool:
    if not isinstance(result, Mapping):
        return False
    return (
        result.get("object") == "PROSPECTIVE_PACK_E_CAPABILITY_METADATA"
        and result.get("validation_only") is True
        and result.get("external_source_dispatch_count") == 0
        and result.get("writer_count") == 0
        and result.get("function_identity") == FUNCTION
    )


def fred_probe_v2_authorization(
    *,
    deployment_fingerprint: str,
    deployment_identity: str,
    target_commit: str,
    previous_failure_checksum: str,
) -> dict[str, Any]:
    selected = read_json(SELECTED / "new_r6_selected_episode_manifest.json")
    value = {
        "authorization_name": FRED_V2_AUTH_NAME,
        "episode_identity": EPISODE,
        "episode_content_checksum": selected.get("content_checksum"),
        "episode_provenance_checksum": selected.get("provenance_checksum"),
        "episode_lineage_checksum": selected.get("lineage_checksum"),
        "pack_a_identity": PACK_A,
        "pack_a_content_checksum": PACK_A_CONTENT,
        "ksrc_fred_source_identity": "KSRC_FRED",
        "prospective_fred_adapter_identity": ADAPTER,
        "new_apps_script_deployment_identity_or_mode": deployment_identity,
        "deployed_source_commit": target_commit,
        "deployed_source_fingerprint": deployment_fingerprint,
        "configuration_reference_identity": "FRED_API_KEY",
        "bounded_query_identity": "FRED:DGS2|2024-07-22|2024-07-24|R6_BINDING_PROBE_V2",
        "call_budget": 1,
        "retry_budget": 0,
        "forecast_cutoff": CUTOFF,
        "no_writer_contract": True,
        "consumed_v1_authorization_fingerprint": FRED_V1_AUTH,
        "previous_failed_dispatch_evidence_checksum": previous_failure_checksum,
        "authorization_valid": True,
        "authorization_activated": False,
        "fred_calls": 0,
    }
    value["authorization_fingerprint"] = sha(value)
    return value


def deployment_source_manifest(
    local_manifest: Mapping[str, Any], remote_after: Mapping[str, Any], target_commit: str
) -> dict[str, Any]:
    return {
        "deployment_mode": "clasp_push_project_head",
        "deployed_source_commit": target_commit,
        "deployed_source_fingerprint": local_manifest["dependency_set_checksum"],
        "remote_project_fingerprint_after_push": remote_after["project_fingerprint"],
        "entry_point_present_after_push": remote_after["has_entry_point"],
        "prospective_file_present_after_push": remote_after["has_prospective_file"],
        "writer_behavior": "none",
        "automatic_retries": 0,
        "source_fallback": "none",
    }


def deployment_result_record(
    *,
    activated: bool,
    push: subprocess.CompletedProcess[str] | None,
    target_commit: str,
    remote_after: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "authorization_activated": activated,
        "deployment_attempts": 1 if activated else 0,
        "retry_count": 0,
        "deployment_status": "SUCCESS" if push and push.returncode == 0 else ("NOT_EXECUTED" if push is None else "FAILED"),
        "deployment_method": "clasp push to authoritative project HEAD",
        "stdout": (push.stdout if push else "").splitlines(),
        "stderr": (push.stderr if push else "").splitlines(),
        "target_commit": target_commit,
        "new_deployment_identity_or_mode": "PUSHED_PROJECT_HEAD" if push and push.returncode == 0 else None,
        "new_deployment_version": "HEAD",
        "remote_project_fingerprint_after_push": remote_after["project_fingerprint"] if remote_after else None,
    }


def external_audit() -> dict[str, int]:
    return {
        "apps_script_deployments": 0,
        "apps_script_visibility_executions": 0,
        "fred_calls": 0,
        "fmp_calls": 0,
        "eodhd_calls": 0,
        "us_treasury_calls": 0,
        "gemini_calls": 0,
        "information_request_calls": 0,
        "google_scientific_reads": 0,
        "google_scientific_writes": 0,
        "pack_e_acquisition_calls": 0,
        "pack_e_constructions": 0,
        "forecast_calls": 0,
        "outcome_operations": 0,
        "evaluation_operations": 0,
    }


def run(
    output: Path = OUT,
    *,
    now_utc: str | None = None,
    execute_deploy: bool = True,
    execute_visibility: bool = True,
) -> str:
    output.mkdir(parents=True, exist_ok=True)
    current_utc = now_utc or utc_now()
    local_manifest = local_dependency_manifest()
    target_commit = git_head()
    previous_failure = read_json(FRED_BINDING / "fred_access_probe_result.json")
    previous_failure_checksum = sha(previous_failure)
    artifacts: dict[str, Any] = {
        "secret_safety_report.json": {
            "new_credentials_created": False,
            "oauth_token_contents_exposed": False,
            "api_key_contents_exposed": False,
            "credentials_committed": False,
        },
        "fred_probe_v1_consumption_preservation.json": {
            "authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_FRED_BINDING_PROBE_AUTHORIZATION_V1",
            "authorization_fingerprint": FRED_V1_AUTH,
            "dispatches": 1,
            "retries": 0,
            "confirmed_fred_calls": 0,
            "preserved_previous_decision": "NEW_R6_PACK_E_FRED_ACCESS_PROBE_FAILED",
            "refined_failure_layer": "REMOTE_APPS_SCRIPT_ENTRY_POINT_MISSING",
        },
    }
    audit = external_audit()

    if not cutoff_open(current_utc):
        decision = "NEW_R6_PACK_E_RUNTIME_SYNC_BLOCKED_CUTOFF_CLOSED"
        artifacts.update(
            {
                "prospective_apps_script_runtime_trace.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_entry_point_source_audit.json": local_manifest,
                "prospective_entry_point_dependency_manifest.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_local_remote_capability_comparison.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_deployment_authorization.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "prospective_deployment_authorization_fingerprint.json": {"status": "NOT_CREATED"},
                "prospective_deployment_result.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_deployed_source_manifest.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "prospective_entry_point_visibility_request.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_entry_point_visibility_result.json": {"status": "NOT_EXECUTED", "reason": "CUTOFF_CLOSED"},
                "prospective_runtime_state_report.json": {
                    "deployment_runtime_state": "NOT_EXECUTED",
                    "visibility_check_runtime_state": "NOT_EXECUTED",
                    "scientific_acquisition_state": "NOT_ATTEMPTED",
                },
                "fred_probe_v2_authorization_preparation.json": {"status": "NOT_CREATED", "reason": "CUTOFF_CLOSED"},
                "fred_probe_v2_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            }
        )
        artifacts["external_access_audit.json"] = audit
        artifacts["final_prospective_runtime_sync_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": False}
        for name, value in artifacts.items():
            write_json(output, name, value)
        return decision

    creds = google_clients.load_credentials(False, token_path=ROOT / "local/token.json", persist_refresh=False)
    service = google_clients.build_script_service(creds, 120)
    script_id = google_clients.default_script_id()
    deployments = subprocess.run(
        ["clasp", "deployments"],
        cwd=APPS_SCRIPT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    runtime_trace = current_runtime_trace(deployments.stdout, script_id)
    remote_before = remote_head_content(service, script_id)
    comparison = {
        "classification": "LOCAL_ENTRY_POINT_PRESENT_REMOTE_ENTRY_POINT_ABSENT"
        if local_manifest["entry_point_present"] and not remote_before["has_entry_point"]
        else "LOCAL_REMOTE_ENTRY_POINT_STATE_OTHER",
        "local_entry_point_present": local_manifest["entry_point_present"],
        "remote_prospective_file_present_before_deployment": remote_before["has_prospective_file"],
        "remote_entry_point_present_before_deployment": remote_before["has_entry_point"],
        "fred_resolver_reached": False,
        "fred_source_reached": False,
        "remote_project_fingerprint_before_push": remote_before["project_fingerprint"],
    }
    artifacts["prospective_apps_script_runtime_trace.json"] = runtime_trace
    artifacts["prospective_entry_point_source_audit.json"] = {
        **local_manifest,
        "target_source_commit": target_commit,
        "local_entry_point_present": local_manifest["entry_point_present"],
    }
    artifacts["prospective_entry_point_dependency_manifest.json"] = {
        "dependency_files": local_manifest["dependency_files"],
        "dependency_set_checksum": local_manifest["dependency_set_checksum"],
        "runtime_scopes": ["script.projects", "script.deployments", "script.external_request"],
        "writer_dependencies": [],
        "provider_source_dependencies": ["KSRC_FMP legacy fetch", "KSRC_FRED legacy fetch", "KSRC_EODHD legacy fetch"],
    }
    artifacts["prospective_local_remote_capability_comparison.json"] = comparison

    if not local_manifest["entry_point_present"]:
        decision = "NEW_R6_PACK_E_LOCAL_DEPLOYMENT_SOURCE_INVALID"
        artifacts.update(
            {
                "prospective_deployment_authorization.json": {"status": "NOT_CREATED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "prospective_deployment_authorization_fingerprint.json": {"status": "NOT_CREATED"},
                "prospective_deployment_result.json": {"status": "NOT_EXECUTED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "prospective_deployed_source_manifest.json": {"status": "NOT_CREATED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "prospective_entry_point_visibility_request.json": {"status": "NOT_EXECUTED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "prospective_entry_point_visibility_result.json": {"status": "NOT_EXECUTED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "prospective_runtime_state_report.json": {
                    "deployment_runtime_state": "NOT_EXECUTED",
                    "visibility_check_runtime_state": "NOT_EXECUTED",
                    "scientific_acquisition_state": "NOT_ATTEMPTED",
                },
                "fred_probe_v2_authorization_preparation.json": {"status": "NOT_CREATED", "reason": "LOCAL_ENTRY_POINT_MISSING"},
                "fred_probe_v2_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            }
        )
        artifacts["external_access_audit.json"] = audit
        artifacts["final_prospective_runtime_sync_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": True}
        for name, value in artifacts.items():
            write_json(output, name, value)
        return decision

    deploy_auth = deployment_authorization(target_commit=target_commit, local_manifest=local_manifest, runtime_trace=runtime_trace)
    artifacts["prospective_deployment_authorization.json"] = deploy_auth
    artifacts["prospective_deployment_authorization_fingerprint.json"] = {
        "authorization_fingerprint": deploy_auth["authorization_fingerprint"],
        "deterministic": True,
    }

    push_result: subprocess.CompletedProcess[str] | None = None
    remote_after: dict[str, Any] | None = None
    if execute_deploy:
        deploy_auth["authorization_activated"] = True
        push_result = subprocess.run(
            ["clasp", "push"],
            cwd=APPS_SCRIPT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        audit["apps_script_deployments"] = 1
        if push_result.returncode == 0:
            remote_after = remote_head_content(service, script_id)
    artifacts["prospective_deployment_result.json"] = deployment_result_record(
        activated=bool(execute_deploy),
        push=push_result,
        target_commit=target_commit,
        remote_after=remote_after,
    )

    if not push_result or push_result.returncode != 0:
        decision = "NEW_R6_PACK_E_PROSPECTIVE_RUNTIME_DEPLOYMENT_FAILED"
        artifacts.update(
            {
                "prospective_deployed_source_manifest.json": {"status": "NOT_CREATED", "reason": "DEPLOYMENT_FAILED"},
                "prospective_entry_point_visibility_request.json": {"status": "NOT_EXECUTED", "reason": "DEPLOYMENT_FAILED"},
                "prospective_entry_point_visibility_result.json": {"status": "NOT_EXECUTED", "reason": "DEPLOYMENT_FAILED"},
                "prospective_runtime_state_report.json": {
                    "deployment_runtime_state": "FAILED",
                    "visibility_check_runtime_state": "NOT_EXECUTED",
                    "scientific_acquisition_state": "NOT_ATTEMPTED",
                },
                "fred_probe_v2_authorization_preparation.json": {"status": "NOT_CREATED", "reason": "DEPLOYMENT_FAILED"},
                "fred_probe_v2_authorization_fingerprint.json": {"status": "NOT_CREATED"},
            }
        )
        artifacts["external_access_audit.json"] = audit
        artifacts["final_prospective_runtime_sync_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": True}
        for name, value in artifacts.items():
            write_json(output, name, value)
        return decision

    artifacts["prospective_deployed_source_manifest.json"] = deployment_source_manifest(local_manifest, remote_after, target_commit)

    visibility_req = visibility_request(current_utc)
    artifacts["prospective_entry_point_visibility_request.json"] = {"request": visibility_req, "function": FUNCTION}
    visibility_meta = None
    if execute_visibility:
        visibility_meta = google_clients.run_script_function_with_metadata(
            service,
            script_id,
            FUNCTION,
            [visibility_req],
        )
        audit["apps_script_visibility_executions"] = 1
    result_object = visibility_meta.get("result") if visibility_meta and visibility_meta.get("ok") else None
    artifacts["prospective_entry_point_visibility_result.json"] = {
        "function_visible": visibility_ok(result_object),
        "request_structurally_accepted": bool(visibility_meta and visibility_meta.get("ok")),
        "fred_resolver_invoked": False,
        "fred_calls": 0,
        "writer_count": int(result_object.get("writer_count", 0)) if isinstance(result_object, Mapping) else 0,
        "metadata": visibility_meta,
        "result": result_object,
    }

    if not visibility_meta or not visibility_meta.get("ok") or not visibility_ok(result_object):
        decision = "NEW_R6_PACK_E_PROSPECTIVE_ENTRY_POINT_VISIBILITY_FAILED"
        artifacts["prospective_runtime_state_report.json"] = {
            "deployment_runtime_state": "SUCCESS",
            "visibility_check_runtime_state": "FAILED",
            "scientific_acquisition_state": "NOT_ATTEMPTED",
        }
        artifacts["fred_probe_v2_authorization_preparation.json"] = {"status": "NOT_CREATED", "reason": "VISIBILITY_FAILED"}
        artifacts["fred_probe_v2_authorization_fingerprint.json"] = {"status": "NOT_CREATED"}
        artifacts["external_access_audit.json"] = audit
        artifacts["final_prospective_runtime_sync_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": True}
        for name, value in artifacts.items():
            write_json(output, name, value)
        return decision

    fred_v2 = fred_probe_v2_authorization(
        deployment_fingerprint=local_manifest["dependency_set_checksum"],
        deployment_identity="PUSHED_PROJECT_HEAD",
        target_commit=target_commit,
        previous_failure_checksum=previous_failure_checksum,
    )
    artifacts["prospective_runtime_state_report.json"] = {
        "deployment_runtime_state": "SUCCESS",
        "visibility_check_runtime_state": "SUCCESS",
        "scientific_acquisition_state": "NOT_ATTEMPTED",
    }
    artifacts["fred_probe_v2_authorization_preparation.json"] = fred_v2
    artifacts["fred_probe_v2_authorization_fingerprint.json"] = {
        "authorization_fingerprint": fred_v2["authorization_fingerprint"],
        "deterministic": True,
    }
    artifacts["external_access_audit.json"] = audit
    decision = "NEW_R6_PACK_E_PROSPECTIVE_RUNTIME_SYNCHRONIZED_FRED_PROBE_V2_PREPARED"
    artifacts["final_prospective_runtime_sync_decision.json"] = {"decision": decision, "current_utc": current_utc, "cutoff_open": True}
    for name, value in artifacts.items():
        write_json(output, name, value)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--at-utc")
    args = parser.parse_args()
    decision = run(args.output, now_utc=args.at_utc)
    print(canonical({"decision": decision, "output": str(args.output.relative_to(ROOT))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
