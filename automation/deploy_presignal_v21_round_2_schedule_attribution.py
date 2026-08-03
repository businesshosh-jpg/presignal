#!/usr/bin/env python3
"""Deploy and verify the canonical Round 2 schedule attribution contract once."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUT = BASE / "PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-20260803T150000Z"
AUTH_ID = "PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-AUTHORIZATION-20260803T150000Z"
PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def source_fingerprint() -> str:
    files = {name: (ROOT / "apps_script" / name).read_text() for name in ("automation_api.js", "fmp_calendar.js")}
    return digest(files)


def authorization() -> dict[str, Any]:
    return {
        "authorization_id": AUTH_ID,
        "authorization_schema_version": "1.0.0",
        "authorization_status": "FROZEN_SINGLE_USE_ACTIVE_FOR_ATTRIBUTION_DEPLOYMENT",
        "project_id": PROJECT_ID,
        "protocol_binding": {"protocol_id": "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z", "protocol_fingerprint": "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f"},
        "envelope_binding": {"envelope_id": "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z", "envelope_fingerprint": "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0"},
        "source_files": ["apps_script/automation_api.js", "apps_script/fmp_calendar.js"],
        "source_fingerprint": source_fingerprint(),
        "canonical_function": "apiUpsertEventWindow_",
        "verification_function": "apiGetScheduleRefreshAttributionContract",
        "ceilings": {"apps_script_source_updates": 1, "deployment_version_creations": 1, "deployment_activations": 1, "deployment_verification_reads": 2, "retries": 0},
        "not_authorized": ["Event-sheet writes", "FMP requests", "provider calls", "Outcome collection", "evaluation", "unrelated Apps Script changes"],
    }


def freeze(output_dir: Path = OUT) -> dict[str, Any]:
    if output_dir.exists():
        auth = json.loads((output_dir / "deployment_authorization.json").read_text())
        supplied = auth.pop("authorization_fingerprint", "")
        if supplied != digest(auth):
            raise RuntimeError("DEPLOYMENT_AUTHORIZATION_FINGERPRINT_CONFLICT")
        auth["authorization_fingerprint"] = supplied
        return auth
    auth = authorization(); auth["authorization_fingerprint"] = digest(auth)
    output_dir.mkdir(parents=True)
    (output_dir / "deployment_authorization.json").write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n")
    return auth


def command(args: list[str]) -> dict[str, Any]:
    result = subprocess.run(args, cwd=ROOT / "apps_script", text=True, capture_output=True, check=False)
    return {"command": args, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def select_unique_execution_api_deployment(deployments: list[dict[str, Any]]) -> dict[str, Any]:
    """Refuse activation unless repository authority resolves to one live route."""
    executable = [row for row in deployments if any(point.get("entryPointType") == "EXECUTION_API" for point in row.get("entryPoints", []))]
    if len(executable) != 1:
        raise RuntimeError(f"EXECUTION_API_DEPLOYMENT_AUTHORITY_AMBIGUOUS:{len(executable)}")
    return executable[0]


def execute(output_dir: Path, auth: dict[str, Any]) -> dict[str, Any]:
    journal = [{"event": "DEPLOYMENT_INTENT_PERSISTED", "authorization_id": AUTH_ID, "authorization_fingerprint": auth["authorization_fingerprint"], "source_fingerprint": auth["source_fingerprint"], "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}]
    push = command(["clasp", "push"])
    journal.append({"event": "SOURCE_UPDATE_RETURNED", "result": push})
    if push["returncode"] != 0:
        result = {"decision": "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED", "stage": "SOURCE_UPDATE", "remote_state": "CONFIRMED_RESPONSE", "source_updates": 1, "version_creations": 0, "deployment_activations": 0, "verification_reads": 0, "detail": push}
        return persist(output_dir, journal, result)
    version = command(["clasp", "version", "Round 2 schedule refresh attribution v1"])
    journal.append({"event": "VERSION_CREATION_RETURNED", "result": version})
    match = re.search(r"version\s+(\d+)", version["stdout"] + "\n" + version["stderr"], re.I)
    if version["returncode"] != 0 or not match:
        result = {"decision": "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED", "stage": "VERSION_CREATION", "remote_state": "CONFIRMED_RESPONSE", "source_updates": 1, "version_creations": 1, "deployment_activations": 0, "verification_reads": 0, "detail": version}
        return persist(output_dir, journal, result)
    version_number = int(match.group(1))
    creds = google_clients.load_credentials(False, persist_refresh=False)
    service = google_clients.build_script_service(creds, 30)
    try:
        deployments = service.projects().deployments().list(scriptId=PROJECT_ID).execute().get("deployments", [])
        deployment_count = sum(
            1 for row in deployments
            if any(point.get("entryPointType") == "EXECUTION_API" for point in row.get("entryPoints", []))
        )
        try:
            selected = select_unique_execution_api_deployment(deployments)
        except RuntimeError:
            result = {"decision": "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED", "stage": "DEPLOYMENT_SELECTION", "remote_state": "CONFIRMED_RESPONSE", "source_updates": 1, "version_creations": 1, "deployment_activations": 0, "verification_reads": 1, "deployment_count": deployment_count}
            return persist(output_dir, journal, result)
        deployment_id = selected["deploymentId"]
        update = service.projects().deployments().update(scriptId=PROJECT_ID, deploymentId=deployment_id, body={"deploymentConfig": {"versionNumber": version_number, "description": "Round 2 schedule attribution v1"}}).execute()
        response = google_clients.run_script_function_with_metadata(service, PROJECT_ID, "apiGetScheduleRefreshAttributionContract", [], dev_mode=False)
    finally:
        google_clients.close_google_service(service)
    journal.extend([{"event": "DEPLOYMENT_ACTIVATION_RETURNED", "deployment_id": deployment_id, "version_number": version_number, "response": update}, {"event": "DEPLOYMENT_VERIFICATION_RETURNED", "response": response}])
    contract = response.get("result") if response.get("ok") else None
    expected = {"operation_id", "authorization_id", "source_window_fingerprint", "pre_refresh_event_sheet_fingerprint", "post_refresh_event_sheet_fingerprint", "invocation_id"}
    if not isinstance(contract, dict) or contract.get("contract_version") != "presignal_r2_schedule_refresh_attribution_v1" or not expected <= set(contract.get("required_response_fields", [])):
        result = {"decision": "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED", "stage": "DEPLOYMENT_VERIFICATION", "remote_state": "CONFIRMED_RESPONSE", "source_updates": 1, "version_creations": 1, "deployment_activations": 1, "verification_reads": 2, "deployment_id": deployment_id, "version_number": version_number, "contract": contract}
        return persist(output_dir, journal, result)
    result = {"decision": "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYED", "remote_state": "CERTAIN", "source_updates": 1, "version_creations": 1, "deployment_activations": 1, "verification_reads": 2, "deployment_id": deployment_id, "version_number": version_number, "source_fingerprint": auth["source_fingerprint"], "contract": contract}
    return persist(output_dir, journal, result)


def persist(output_dir: Path, journal: list[dict[str, Any]], result: dict[str, Any]) -> dict[str, Any]:
    (output_dir / "deployment_operation_journal.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in journal))
    (output_dir / "deployment_execution.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true"); parser.add_argument("--output-dir", type=Path, default=OUT); args = parser.parse_args()
    auth = freeze(args.output_dir)
    if not args.execute:
        print(json.dumps({"authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"]}, sort_keys=True)); return 0
    result = execute(args.output_dir, auth)
    print(json.dumps(result, sort_keys=True)); return 0 if result["decision"] == "ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
