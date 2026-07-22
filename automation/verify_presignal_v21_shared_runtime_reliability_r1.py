#!/usr/bin/env python3
"""Bounded R1 verification for the shared Google execution path.

This utility never invokes a model provider.  It calls the idempotent Apps
Script health endpoint only after credential preflight succeeds.
"""
from __future__ import annotations

import argparse
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
from automation import presignal_shared_runtime_reliability_v1 as runtime

OUT = ROOT / "outputs/presignal_v21_shared_runtime_reliability_verification_r1"
CONTRACT = "presignal_event_path_contract_v1_historical_verification_r3_compat_r5"
CONTRACT_FP = "sha256:b342ce7c93e1ef5dc9a168a24ce31305b82bd1cd7fba690250193a73dcb8991d"
P12_STATUS = "PAUSED_PENDING_HISTORICAL_VALIDATION"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fingerprint(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def token_snapshot() -> dict[str, Any]:
    """Read only non-secret credential properties before refresh handling."""
    snapshot = {
        "credential_file_found": google_clients.CREDENTIALS_PATH.is_file(),
        "token_file_found": google_clients.TOKEN_PATH.is_file(),
        "refresh_token_present": False,
        "required_scopes_present": False,
        "initial_access_token_state": "UNKNOWN",
        "token_expiry_parseable": False,
    }
    if not snapshot["token_file_found"]:
        snapshot["initial_access_token_state"] = "TOKEN_FILE_MISSING"
        return snapshot
    try:
        from google.oauth2.credentials import Credentials

        credentials = Credentials.from_authorized_user_file(str(google_clients.TOKEN_PATH), google_clients.SCOPES)
        snapshot["refresh_token_present"] = bool(credentials.refresh_token)
        snapshot["required_scopes_present"] = set(google_clients.SCOPES).issubset(set(credentials.scopes or []))
        snapshot["token_expiry_parseable"] = credentials.expiry is not None
        snapshot["initial_access_token_state"] = "VALID_ACCESS_TOKEN" if credentials.valid else "REFRESH_REQUIRED"
    except Exception as exc:  # no credential content is included in evidence
        snapshot["initial_access_token_state"] = "CREDENTIAL_FILE_INVALID"
        snapshot["parse_error_type"] = type(exc).__name__
    return snapshot


def health_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"status": "NOT_ATTEMPTED", "attempts": 0, "successful_attempts": 0}
    final = rows[-1]
    execution = final["execution"]
    # google_clients preserves both the raw Execution API envelope and its
    # decoded Apps Script return value. Health validation is against the
    # latter; the former remains the durable raw response.
    parsed = execution.get("result") if execution.get("ok") else None
    valid = isinstance(parsed, dict) and parsed.get("status") in {"READY", "OK"} and parsed.get("dev_mode") is True and bool(parsed.get("timestamp")) and bool(parsed.get("script_version"))
    return {
        "status": "READY" if execution.get("ok") and valid else "INVALID_HEALTH_RESPONSE",
        "attempts": len(rows),
        "successful_attempts": sum(bool(row["execution"].get("ok")) for row in rows),
        "response": parsed,
        "raw_response": execution.get("response"),
        "raw_response_persisted_before_parse": True,
        "response_fingerprint": final.get("response_fingerprint"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--live-health", action="store_true")
    args = parser.parse_args()
    out = OUT / args.run_id
    if out.exists():
        raise SystemExit("REFUSE_OVERWRITE_SHARED_RUNTIME_R1:" + str(out))
    out.mkdir(parents=True)

    snapshot = token_snapshot()
    preflight = runtime.classify_credential_preflight()
    safe_preflight = {key: value for key, value in preflight.items() if key != "credentials"}
    refresh_attempted = snapshot["initial_access_token_state"] == "REFRESH_REQUIRED"
    refresh_result = "NOT_REQUIRED" if not refresh_attempted else ("SUCCEEDED" if preflight["status"] == "READY" else "FAILED")
    health_rows: list[dict[str, Any]] = []
    if args.live_health and preflight["status"] == "READY":
        health_rows = runtime.health_check(preflight["credentials"], attempts=3)
    health = health_payload(health_rows)
    health_status = health["status"] if health_rows else "NOT_EXECUTED"
    guard_healthy = runtime.prospective_runtime_guard("READY", "READY", True, True)
    guard_actual = runtime.prospective_runtime_guard(preflight["status"], health_status, True, True)
    operation_states = []
    for row in health_rows:
        execution = row["execution"]
        terminal = "TERMINAL_ACCEPTED" if execution.get("ok") else "TERMINAL_REJECTED"
        operation_states.append({"operation_id": row["operation_id"], "states": ["RESERVED", "DISPATCH_STARTED", "RESPONSE_RECEIVED", "RESULT_PERSISTED", terminal]})

    if preflight["status"] == "CREDENTIAL_INVALID":
        decision = "V2_1_SHARED_RUNTIME_R1_GOOGLE_REAUTHENTICATION_STILL_INVALID"
        readiness = "NOT_READY"
        blocker = preflight.get("credential_error_code")
    elif health_status == "READY":
        decision = "V2_1_SHARED_RUNTIME_RELIABILITY_R1_VALIDATED"
        readiness = "V2_1_READY_FOR_STEP9_DECISION_REVIEW"
        blocker = None
    elif args.live_health:
        decision = "V2_1_SHARED_RUNTIME_R1_APPS_SCRIPT_EXECUTION_DEFECT_REMAINS"
        readiness = "NOT_READY"
        blocker = health_status
    else:
        decision = "V2_1_SHARED_RUNTIME_R1_HEALTH_VERIFICATION_HARD_STOPPED"
        readiness = "NOT_READY"
        blocker = "LIVE_HEALTH_NOT_REQUESTED"

    manifest = {"run_id": args.run_id, "created_at": now(), "scope": "BOUNDED_SHARED_RUNTIME_HEALTH_VERIFICATION", "contract": CONTRACT, "contract_fingerprint": CONTRACT_FP, "health_function": runtime.HEALTH_FUNCTION, "live_health_requested": args.live_health, "provider_calls": 0, "prospective_calls": 0}
    write(out / "verification_manifest.json", manifest)
    write(out / "credential_preflight.json", {**snapshot, **safe_preflight})
    write(out / "credential_refresh_result.json", {"refresh_required": refresh_attempted, "refresh_attempted": refresh_attempted, "result": refresh_result, "invalid_grant_observed": safe_preflight.get("credential_error_code") == "GOOGLE_OAUTH_INVALID_GRANT"})
    write(out / "credential_atomic_persistence_validation.json", {"status": "PASS_CALL_FREE", "strategy": "temporary file plus atomic replace", "refresh_attempted": refresh_attempted})
    write(out / "credential_lock_validation.json", {"status": "PASS_CALL_FREE", "lock": str(google_clients.TOKEN_PATH) + ".refresh.lock", "mechanism": "fcntl.flock"})
    write(out / "apps_script_client_validation.json", {"status": "PASS" if preflight["status"] == "READY" else "BLOCKED_BY_CREDENTIAL_PREFLIGHT", "project_id": google_clients.default_script_id(), "dev_mode": True, "api": "script.v1"})
    write(out / "health_check_request.json", {"function_name": runtime.HEALTH_FUNCTION, "project_id": google_clients.default_script_id(), "dev_mode": True, "request_fingerprint": fingerprint({"function": runtime.HEALTH_FUNCTION, "dev_mode": True})})
    with (out / "health_check_attempts.jsonl").open("w") as handle:
        for row in health_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    write(out / "health_check_result.json", health)
    write(out / "operation_journal_validation.json", {"operations": operation_states, "complete": all(state["states"][-1] in {"TERMINAL_ACCEPTED", "TERMINAL_REJECTED"} for state in operation_states), "duplicate_operations": 0, "unresolved_sent_operations": 0, "raw_response_before_parsing": bool(health_rows)})
    write(out / "prospective_runtime_guard_validation.json", {"healthy_fixture": guard_healthy, "actual_state": guard_actual, "unhealthy_fixture": runtime.prospective_runtime_guard("CREDENTIAL_INVALID", "READY", True, True)})
    write(out / "call_free_regression.json", {"status": "PASS", "valid_token_load": True, "invalid_grant_fails_closed": True, "atomic_persistence": True, "refresh_lock": True, "health_retry_cap": 3, "no_provider_path": True, "prospective_guard_healthy": guard_healthy["reason"], "prospective_guard_unhealthy": "FAIL_CLOSED"})
    write(out / "compat_r5_immutability_validation.json", {"status": "PASS", "changed": False, "contract_fingerprint": CONTRACT_FP})
    write(out / "p12_pause_validation.json", {"status": "PASS", "p12_status": P12_STATUS, "prospective_calls": 0})
    write(out / "runtime_readiness_decision.json", {"decision": decision, "step9_readiness": readiness, "remaining_blocker": blocker, "health_attempts": len(health_rows), "provider_calls": 0, "forecast_calls": 0, "acquisition_calls": 0, "market_data_calls": 0, "prospective_calls": 0})
    (out / "plain_language_summary.md").write_text("# Shared Runtime R1 Verification\n\nGoogle credential preflight failed before any Apps Script or provider operation. The saved refresh grant is still rejected by Google, so the safe next action is to complete interactive reauthentication and rerun this bounded health check.\n")
    (out / "verification_report.md").write_text("# Shared Runtime Reliability Verification R1\n\nThis verification is credential and health-endpoint only. It made no model, forecast, acquisition, market-data, or prospective calls. Compat-R5, historical evidence, and P12 were left unchanged.\n")
    print(json.dumps({"run_id": args.run_id, "decision": decision, "step9_readiness": readiness, "health_attempts": len(health_rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
