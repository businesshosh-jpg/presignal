#!/usr/bin/env python3
"""Bind and activate the historically authoritative Round 2 Execution API route."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUT = BASE / "PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-BINDING-20260804T000000Z"
AUTH_ID = "PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-BINDING-AUTHORIZATION-20260804T000000Z"
PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
DEPLOYMENT_ID = "AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN"
TARGET_VERSION = 83
SOURCE_FP = "sha256:5c9558f51b6ea7cca8f905b543ef3306d9e6a0acd9a5d07f2c33d7dc8acbf670"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def authority_proof(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in inventory if row.get("deploymentId") == DEPLOYMENT_ID]
    if len(selected) != 1:
        raise RuntimeError("AUTHORITATIVE_EXECUTION_API_DEPLOYMENT_MISSING")
    row = selected[0]
    config = row.get("deploymentConfig") or {}
    points = row.get("entryPoints") or []
    if config.get("scriptId") != PROJECT_ID or not any(point.get("entryPointType") == "EXECUTION_API" for point in points):
        raise RuntimeError("AUTHORITATIVE_EXECUTION_API_DEPLOYMENT_BINDING_CONFLICT")
    return {
        "decision": "AUTHORITATIVE_EXECUTION_API_DEPLOYMENT_CONFIRMED",
        "selected_deployment_id": DEPLOYMENT_ID,
        "selection_rule": "Exact deployment endpoint repeatedly bound by accepted Round 1 collection preflight and attachment manifests; other deployment descriptions, versions, recency, and list order are not selection inputs.",
        "accepted_invocation_references": [
            "PPHB-R1-OUTCOME-COLLECTION-SLICE-002-20260803T035402Z-5b2104c5270c/preflight_decision.json",
            "PPHB-R1-OUTCOME-COLLECTION-SLICE-012-20260803T112350Z-c68c116427d5/preflight_decision.json",
            "PPHB-R1-OUTCOME-ATTACH-SLICE-012-20260803T112356Z-c68c116427d5/run_manifest.json",
        ],
        "inventory_count": len(inventory),
        "selected_before_version": config.get("versionNumber"),
    }


def freeze() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if OUT.exists():
        auth = json.loads((OUT / "deployment_binding_authorization.json").read_text())
        supplied = auth.pop("authorization_fingerprint")
        if supplied != digest(auth):
            raise RuntimeError("DEPLOYMENT_BINDING_AUTHORIZATION_FINGERPRINT_CONFLICT")
        auth["authorization_fingerprint"] = supplied
        return auth, json.loads((OUT / "deployment_inventory.json").read_text())["deployments"]
    creds = google_clients.load_credentials(False, persist_refresh=False)
    service = google_clients.build_script_service(creds, 30)
    try:
        inventory = service.projects().deployments().list(scriptId=PROJECT_ID).execute().get("deployments", [])
    finally:
        google_clients.close_google_service(service)
    proof = authority_proof(inventory)
    auth = {
        "authorization_id": AUTH_ID,
        "authorization_schema_version": "1.0.0",
        "authorization_status": "FROZEN_SINGLE_USE_ACTIVE_FOR_EXACT_DEPLOYMENT_UPDATE",
        "project_id": PROJECT_ID,
        "deployment_id": DEPLOYMENT_ID,
        "target_hardened_version": TARGET_VERSION,
        "source_fingerprint": SOURCE_FP,
        "canonical_function": "apiUpsertEventWindow_",
        "verification_function": "apiGetScheduleRefreshAttributionContract",
        "workbook_binding": "accepted configured Event workbook via automation.google_clients.DEFAULT_SPREADSHEET_ID",
        "event_sheet_binding": "Event",
        "ceilings": {"deployment_updates": 1, "verification_reads": 2, "retries": 0, "unrelated_google_operations": 0},
        "authority_proof": proof,
        "prior_partial_deployment": "PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-20260803T150000Z",
    }
    auth["authorization_fingerprint"] = digest(auth)
    OUT.mkdir(parents=True)
    (OUT / "deployment_inventory.json").write_text(json.dumps({"project_id": PROJECT_ID, "deployments": inventory, "authority_proof": proof}, indent=2, sort_keys=True) + "\n")
    (OUT / "deployment_binding_authorization.json").write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n")
    return auth, inventory


def execute(auth: dict[str, Any]) -> dict[str, Any]:
    creds = google_clients.load_credentials(False, persist_refresh=False)
    service = google_clients.build_script_service(creds, 30)
    journal = [{"event": "DEPLOYMENT_UPDATE_INTENT", "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "authorization_id": AUTH_ID, "deployment_id": DEPLOYMENT_ID, "target_version": TARGET_VERSION}]
    try:
        before = service.projects().deployments().get(scriptId=PROJECT_ID, deploymentId=DEPLOYMENT_ID).execute()
        if (before.get("deploymentConfig") or {}).get("versionNumber") != 82:
            raise RuntimeError("AUTHORITATIVE_DEPLOYMENT_PREVIOUS_VERSION_CONFLICT")
        updated = service.projects().deployments().update(scriptId=PROJECT_ID, deploymentId=DEPLOYMENT_ID, body={"deploymentConfig": {"versionNumber": TARGET_VERSION, "description": "Read-only governed historical USD/JPY endpoint v1; provider/all_available surface"}}).execute()
        response = google_clients.run_script_function_with_metadata(service, DEPLOYMENT_ID, "apiGetScheduleRefreshAttributionContract", [], dev_mode=False)
    finally:
        google_clients.close_google_service(service)
    journal.append({"event": "DEPLOYMENT_UPDATE_RESPONSE", "before": before, "updated": updated, "verification": response})
    contract = response.get("result") if response.get("ok") else None
    required = {"operation_id", "authorization_id", "source_window_fingerprint", "invocation_id", "pre_refresh_event_sheet_fingerprint", "post_refresh_event_sheet_fingerprint", "dispatch_timestamp", "completion_timestamp", "terminal_status", "remote_state"}
    decision = "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYED" if isinstance(contract, dict) and required <= set(contract.get("required_response_fields", [])) else "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED"
    result = {"decision": decision, "remote_state": "CERTAIN" if decision.endswith("DEPLOYED") else "CONFIRMED_RESPONSE", "project_id": PROJECT_ID, "deployment_id": DEPLOYMENT_ID, "previous_version": 82, "target_version": TARGET_VERSION, "resulting_version": (updated.get("deploymentConfig") or {}).get("versionNumber"), "source_fingerprint": SOURCE_FP, "contract": contract, "deployment_updates": 1, "verification_reads": 2, "retries": 0}
    (OUT / "deployment_activation_journal.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in journal))
    (OUT / "deployment_activation_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    auth, _ = freeze()
    if "--execute" in sys.argv:
        print(json.dumps(execute(auth), sort_keys=True))
    else:
        print(json.dumps({"authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"]}, sort_keys=True))
