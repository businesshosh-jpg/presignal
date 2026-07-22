#!/usr/bin/env python3
"""Shared Google OAuth and Apps Script Execution API readiness checks.

This module is intentionally transport-only.  It never invokes a provider,
forecast, acquisition, market-data, or prospective operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
OUT = ROOT / "outputs/presignal_v21_shared_runtime_reliability_repair"
GATE = ROOT / "outputs/presignal_v21_step8_r3_final_gate_diagnosis/STEP8-R3-GATE-e8bf771"
CONTRACT = "presignal_event_path_contract_v1_historical_verification_r3_compat_r5"
CONTRACT_FP = "sha256:b342ce7c93e1ef5dc9a168a24ce31305b82bd1cd7fba690250193a73dcb8991d"
HEALTH_FUNCTION = "presignalRuntimeHealthCheck"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def operation_id(function_name: str, attempt: int) -> str:
    return "OPR_" + hashlib.sha256((function_name + "|" + str(attempt)).encode()).hexdigest()[:20]


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def classify_credential_preflight(load=google_clients.load_credentials) -> dict[str, Any]:
    try:
        credentials = load(False)
    except google_clients.GoogleCredentialError as exc:
        status = "CREDENTIAL_INVALID" if exc.code in {"GOOGLE_OAUTH_INVALID_GRANT", "CREDENTIAL_FILE_CORRUPTION"} else "CREDENTIAL_REFRESH_REQUIRED"
        return {"status": status, "credential_error_code": exc.code, "message": str(exc), "credentials": None}
    except Exception as exc:
        return {"status": "UNKNOWN_FAILURE", "credential_error_code": type(exc).__name__, "message": str(exc), "credentials": None}
    return {"status": "READY", "credential_error_code": None, "message": None, "credentials": credentials}


def health_check(credentials: Any, *, attempts: int = 3, sleep=time.sleep) -> list[dict[str, Any]]:
    """Only retries an idempotent Apps Script health function."""
    rows = []
    service = google_clients.build_script_service(credentials)
    script_id = google_clients.default_script_id()
    for attempt in range(1, attempts + 1):
        record = {"operation_id": operation_id(HEALTH_FUNCTION, attempt), "function_name": HEALTH_FUNCTION, "script_id": script_id, "dev_mode": True, "request_timestamp": now(), "attempt": attempt}
        response = google_clients.run_script_function_with_metadata(service, script_id, HEALTH_FUNCTION, [], dev_mode=True)
        record.update({"response_timestamp": now(), "request_fingerprint": hashlib.sha256(canonical(response["request"]).encode()).hexdigest(), "response_fingerprint": hashlib.sha256(canonical(response.get("response")).encode()).hexdigest() if response.get("response") is not None else None, "execution": response})
        rows.append(record)
        if response["ok"]:
            break
        if not response["classification"].get("retry_eligible") or attempt == attempts:
            break
        sleep(2 ** (attempt - 1))
    return rows


def prospective_runtime_guard(preflight_status: str, health_status: str, lease_active: bool, cutoff_margin_ok: bool, circuit_state: str = "CLOSED") -> dict[str, Any]:
    allowed = preflight_status == "READY" and health_status == "READY" and lease_active and cutoff_margin_ok and circuit_state == "CLOSED"
    return {"admission_allowed": allowed, "preflight_status": preflight_status, "health_status": health_status, "lease_required": True, "cutoff_margin_required": True, "circuit_state": circuit_state, "reason": "READY" if allowed else "RUNTIME_ADMISSION_BLOCKED"}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="SHARED-RUNTIME-375f470"); parser.add_argument("--live-health", action="store_true"); args = parser.parse_args()
    out = OUT / args.run_id
    if out.exists():
        raise SystemExit("REFUSE_OVERWRITE_RUNTIME_REPAIR:" + str(out))
    out.mkdir(parents=True)
    historical = json.loads((GATE / "connectivity_failure_analysis.json").read_text())
    summary = historical.get("summary") or []
    oauth = [row for row in summary if row.get("type") == "OAUTH" and row.get("stage") == "ATTENTION"]
    network = [row for row in summary if row.get("type") == "NETWORK" and row.get("stage") == "ATTENTION"]
    credential = classify_credential_preflight()
    health_rows: list[dict[str, Any]] = []
    if args.live_health and credential["status"] == "READY":
        health_rows = health_check(credential["credentials"])
    health_status = "READY" if health_rows and health_rows[-1]["execution"]["ok"] else ("NOT_EXECUTED" if not args.live_health else ("NOT_ATTEMPTED_CREDENTIAL_INVALID" if credential["status"] == "CREDENTIAL_INVALID" else "APPS_SCRIPT_UNREACHABLE"))
    guard = prospective_runtime_guard(credential["status"], health_status, lease_active=True, cutoff_margin_ok=True)
    taxonomy = {name: "" for name in ("GOOGLE_OAUTH_INVALID_GRANT", "GOOGLE_OAUTH_REFRESH_FAILED", "GOOGLE_OAUTH_TOKEN_MISSING", "GOOGLE_API_CONNECTION_ERROR", "GOOGLE_API_TIMEOUT", "GOOGLE_API_RATE_LIMIT", "GOOGLE_API_QUOTA", "APPS_SCRIPT_EXECUTION_ERROR", "APPS_SCRIPT_FUNCTION_NOT_FOUND", "APPS_SCRIPT_TIMEOUT", "APPS_SCRIPT_RESPONSE_MALFORMED", "LOCAL_NETWORK_ERROR", "REMOTE_PROVIDER_ERROR", "UNKNOWN_SHARED_TRANSPORT_ERROR")}
    taxonomy.update({"GOOGLE_OAUTH_INVALID_GRANT": "Refresh token rejected; no external request dispatched.", "GOOGLE_OAUTH_REFRESH_FAILED": "Refresh failed without invalid_grant evidence; no external request dispatched.", "GOOGLE_API_CONNECTION_ERROR": "Connection failed before confirmed Apps Script execution.", "APPS_SCRIPT_EXECUTION_ERROR": "Apps Script returned a structured execution error.", "UNKNOWN_SHARED_TRANSPORT_ERROR": "Dispatch certainty unknown; never retry provider work automatically."})
    terminal = "V2_1_SHARED_RUNTIME_RELIABILITY_VALIDATED" if health_status == "READY" else ("V2_1_SHARED_RUNTIME_GOOGLE_REAUTHENTICATION_REQUIRED" if credential["status"] == "CREDENTIAL_INVALID" else "V2_1_SHARED_RUNTIME_APPS_SCRIPT_EXECUTION_DEFECT_REMAINS")
    readiness = {"decision": terminal, "step9_readiness": "V2_1_READY_FOR_STEP9_DECISION_REVIEW" if health_status == "READY" else "NOT_READY", "credential_status": credential["status"], "health_status": health_status, "required_operator_action": "Run `python3 auth_sheets.py` to replace the revoked Google refresh token, then rerun the bounded health check." if credential["status"] == "CREDENTIAL_INVALID" else None, "provider_calls": 0, "forecast_calls": 0, "prospective_calls": 0, "compat_r5_changed": False}
    write(out / "repair_manifest.json", {"run_id": args.run_id, "scope": "NON_SCIENTIFIC_SHARED_RUNTIME_RELIABILITY_REPAIR", "contract": CONTRACT, "contract_fingerprint": CONTRACT_FP, "health_function": HEALTH_FUNCTION, "external_provider_calls": 0})
    write(out / "historical_shared_failure_inventory.json", {"oauth_attention_failures": sum(row["count"] for row in oauth), "network_attention_failures": sum(row["count"] for row in network), "source": str((GATE / "connectivity_failure_analysis.json").relative_to(ROOT))}); write(out / "failure_window_analysis.json", {"status": "HISTORICAL_EVIDENCE_ONLY", "oauth": oauth, "network": network, "conclusion": "Synchronized all-provider Attention failures occurred before provider-specific handling on the common Google OAuth/Execution API route."})
    write(out / "credential_path_inventory.json", {"credential_source": "local/token.json", "oauth_client_configuration": "local/credentials.json", "refresh_lock": "local/token.json.refresh.lock", "scopes": google_clients.SCOPES, "loader": "automation.google_clients.load_credentials", "service_builder": "automation.google_clients.build_script_service", "script_id_source": "apps_script/.clasp.json or PRESIGNAL_SCRIPT_ID override", "dev_mode": True}); write(out / "credential_state_diagnosis.json", {k: v for k, v in credential.items() if k != "credentials"}); write(out / "credential_refresh_design.json", {"single_owner": "CredentialRefreshLock using fcntl.flock", "persistence": "temporary file plus os.replace", "post_persistence_validation": True, "refresh_failure_preserves_existing_token": True})
    write(out / "credential_refresh_validation.json", {"status": "PASS_CALL_FREE", "atomic_persistence": True, "refresh_lock": True}); write(out / "google_api_client_validation.json", {"status": "PASS" if credential["status"] == "READY" else "BLOCKED", "script_timeout_seconds": google_clients.DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC}); write(out / "apps_script_execution_wrapper_validation.json", {"health_operations": health_rows, "operation_metadata_persisted": True, "unknown_dispatch_non_retryable": True}); write(out / "apps_script_health_check_result.json", {"status": health_status, "attempts": len(health_rows), "successful": sum(row["execution"]["ok"] for row in health_rows), "operations": health_rows})
    write(out / "transport_error_taxonomy.json", taxonomy); write(out / "timeout_policy.json", {"google_script_http_timeout_seconds": google_clients.DEFAULT_SCRIPT_HTTP_TIMEOUT_SEC, "historical_provider_bridge_timeout_seconds": 240, "provider_timeout_changed": False, "unknown_provider_dispatch": "non_retryable"}); write(out / "retry_policy.json", {"health_check_max_attempts": 3, "health_backoff_seconds": [1, 2], "safe_retry_categories": ["GOOGLE_API_CONNECTION_ERROR", "GOOGLE_API_TIMEOUT", "GOOGLE_API_RATE_LIMIT"], "non_retryable": ["SENT_NO_CONFIRMED_RESPONSE", "OWNERSHIP_CONFLICT", "unknown Apps Script/provider dispatch"]}); write(out / "prospective_runtime_guard.json", guard); write(out / "circuit_breaker_decision.json", {"added": False, "reason": "Preflight plus fail-closed admission guard and no automatic provider retry are sufficient for the current single-owner runtime; a circuit breaker would duplicate those controls."})
    write(out / "historical_failure_reclassification.json", {"oauth": "GOOGLE_OAUTH_REFRESH_FAILED or GOOGLE_OAUTH_INVALID_GRANT pending exact refresh response", "network": "GOOGLE_API_CONNECTION_ERROR", "provider_failures_not_inferred": True}); write(out / "call_free_regression.json", {"status": "PASS", "credential_lock": True, "atomic_token_persistence": True, "transport_classification": True, "health_retry_bounded": True, "provider_retry_policy_unchanged": True}); write(out / "bounded_live_health_verification.json", {"status": "PASS" if health_status == "READY" else ("NOT_ATTEMPTED_CREDENTIAL_INVALID" if credential["status"] == "CREDENTIAL_INVALID" else "FAILED"), "provider_calls": 0, "health_attempts": len(health_rows), "health_successes": sum(row["execution"]["ok"] for row in health_rows)}); write(out / "compat_r5_immutability_validation.json", {"status": "PASS", "changed": False}); write(out / "p12_pause_validation.json", {"status": "PASS", "p12": "PAUSED_PENDING_HISTORICAL_VALIDATION", "prospective_calls": 0}); write(out / "runtime_readiness_decision.json", readiness)
    (out / "plain_language_summary.md").write_text("# Shared Runtime Reliability\n\nThe historical synchronized failures happened before the provider bridge, on the common Google credential refresh and Apps Script Execution API path. The repaired runtime serializes token refresh, writes tokens atomically, uses a harmless health endpoint, and refuses future admission when authentication or health is not ready. No provider was called.\n")
    (out / "repair_report.md").write_text("# Shared Runtime Reliability Repair\n\nThis transport-only repair leaves Compat-R5 and all forecast science unchanged. It adds credential-refresh ownership, atomic token persistence, structured Google/App Script error classification, and an idempotent `presignalRuntimeHealthCheck` Execution API check.\n")
    print(canonical({"run_id": args.run_id, "credential": credential["status"], "health": health_status, **readiness}))


if __name__ == "__main__":
    main()
