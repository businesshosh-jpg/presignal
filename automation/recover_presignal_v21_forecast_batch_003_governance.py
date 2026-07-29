#!/usr/bin/env python3
"""Governance-authorized recovery of the five remaining frozen Batch 003 calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import google_clients
from automation import repair_presignal_v21_forecast_batch_003_ssl_transport as ssl_repair
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

PLAN_ID = batch_exec.PLAN_ID
OUTPUT_ROOT = batch_exec.OUTPUT_ROOT
EXPECTED_START_HEAD = "4b603b93c3281c6f461e8ce2ca8698336f8e816a"
USER_BATCH_LABEL = "FORECAST_BATCH_003"
FROZEN_BATCH_ID = "FCB_PACK_A_003"
BATCH_001_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8"
BATCH_002_RUN_ID = "PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5"
BATCH_003_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3"
BATCH_003_DIAGNOSIS_ID = "PPHB-R1-FORECAST-DIAGNOSIS-BATCH-003-20260729T172538Z-a7eb93dfa2ce"
SSL_TRANSPORT_REPAIR_ID = "PPHB-R1-FORECAST-SHARED-SSL-TRANSPORT-REPAIR-BATCH-003-20260729T174216Z-c32ec12def01"
RUN_PREFIX = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-003-"
SSL_UNKNOWN_CALL_IDS = (
    "FCL_f761a45623b0c5513ef58cae",
    "FCL_29c51488fec0eda92d5310ee",
    "FCL_9819cb8d804223e9f0c3448c",
    "FCL_5cf8a9cd9f5ac7b59bd42b4e",
)
PARSE_REPLACEMENT_CALL_ID = "FCL_27720b8b23236b173b96fdee"
IN_SCOPE_CALL_IDS = SSL_UNKNOWN_CALL_IDS + (PARSE_REPLACEMENT_CALL_ID,)
PACK_TYPE = "PACK_A"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
TERMINAL_STATES = {
    "SUCCEEDED_VALID",
    "FAILED_TRANSPORT",
    "FAILED_PROVIDER",
    "FAILED_PROVIDER_AUTHORITY",
    "FAILED_PARSE",
    "FAILED_VALIDATION",
    "SKIPPED_EXISTING_AUTHORITATIVE_RESULT",
}
TRANSPORT_STOP_CATEGORIES = {
    "UNKNOWN_SHARED_TRANSPORT_ERROR",
    "GOOGLE_API_TIMEOUT",
    "GOOGLE_API_CONNECTION_ERROR",
    "GOOGLE_OAUTH_INVALID_GRANT",
    "GOOGLE_OAUTH_REFRESH_FAILED",
    "APPS_SCRIPT_EXECUTION_ERROR",
}


class Batch003GovernanceRecoveryError(RuntimeError):
    """The bounded Batch 003 governance recovery failed closed."""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))
    os.replace(temp, path)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def git_head() -> str:
    return batch_exec.git_head()


def git_branch() -> str:
    return batch_exec.git_branch()


def is_descendant_of(commit: str) -> bool:
    return batch_exec.is_descendant_of(commit)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "batch_id": FROZEN_BATCH_ID,
        "ssl_transport_repair_id": SSL_TRANSPORT_REPAIR_ID,
        "timestamp": timestamp,
    }
    run_id = (
        RUN_PREFIX
        + timestamp.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def verified_scope_bundle() -> dict[str, Any]:
    bundle = batch_exec.verified_batch_bundle(user_batch_label=USER_BATCH_LABEL, frozen_batch_id=FROZEN_BATCH_ID)
    calls = {row["call"]["forecast_call_id"]: row for row in bundle["bundles"]}
    if bundle["pack_type"] != PACK_TYPE:
        raise Batch003GovernanceRecoveryError("PACK_TYPE_MISMATCH")
    if set(IN_SCOPE_CALL_IDS).difference(calls):
        raise Batch003GovernanceRecoveryError("IN_SCOPE_CALLS_MISSING_FROM_FROZEN_BATCH")
    selected = [calls[call_id] for call_id in bundle["batch_manifest"]["ordered_call_ids"] if call_id in IN_SCOPE_CALL_IDS]
    if len(selected) != 5:
        raise Batch003GovernanceRecoveryError("IN_SCOPE_CALL_COUNT_MISMATCH")
    return {"bundle": bundle, "selected": selected, "calls": calls}


def initialize_run(run_dir: Path, repo_state: Mapping[str, Any], auth_result: Mapping[str, Any], scope_rows: list[dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_GOVERNANCE_RECOVERY_BATCH_003",
            "plan_id": PLAN_ID,
            "user_batch_label": USER_BATCH_LABEL,
            "frozen_batch_id": FROZEN_BATCH_ID,
            "pack_type": PACK_TYPE,
            "authorized_new_call_count": 5,
            "maximum_provider_calls": 5,
            "branch": repo_state["branch"],
            "start_head": repo_state["head"],
            "expected_start_head": EXPECTED_START_HEAD,
            "google_preflight": auth_result,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "batch_004_executed": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "batch_003_execution_id": BATCH_003_RUN_ID,
            "batch_003_diagnosis_id": BATCH_003_DIAGNOSIS_ID,
            "ssl_transport_repair_id": SSL_TRANSPORT_REPAIR_ID,
            "forecast_execution_contract": str((batch_exec.PLAN_ROOT / "forecast_execution_contract.json").relative_to(ROOT)),
            "provider_model_contract": str((batch_exec.PLAN_ROOT / "provider_model_contract.json").relative_to(ROOT)),
            "historical_leakage_control_contract": str((batch_exec.PLAN_ROOT / "historical_leakage_control_contract.json").relative_to(ROOT)),
        },
    )
    write_json(
        run_dir / "governance_authorization.json",
        {
            "authorized_ssl_unknown_recovery_calls": list(SSL_UNKNOWN_CALL_IDS),
            "authorized_parse_schema_replacement_call": PARSE_REPLACEMENT_CALL_ID,
            "maximum_new_dispatches_per_call": 1,
            "duplicate_execution_risk_acknowledged": True,
            "provider_error_schema_replacement_authorized": True,
            "explicit_user_authorization": True,
        },
    )
    write_json(
        run_dir / "recovery_execution_contract.json",
        {
            "allowed_terminal_states": sorted(TERMINAL_STATES),
            "forecast_contract": read_json(batch_exec.PLAN_ROOT / "forecast_execution_contract.json"),
            "historical_leakage_control_contract": read_json(batch_exec.PLAN_ROOT / "historical_leakage_control_contract.json"),
            "provider_authority_rule": read_json(batch_exec.PLAN_ROOT / "provider_model_contract.json")["provider_authority_rule"],
            "pack_type": PACK_TYPE,
            "fresh_service_per_dispatch": True,
            "fresh_authorized_http_per_dispatch": True,
            "fresh_httplib2_http_per_dispatch": True,
            "apps_script_timeout_seconds": batch_exec.SCRIPT_HTTP_TIMEOUT_SECONDS,
            "bridge_hard_timeout_seconds": 180,
            "no_automatic_retry": True,
            "no_batch_004_execution": True,
        },
    )
    write_jsonl(run_dir / "in_scope_call_manifest.jsonl", [row["call"] for row in scope_rows])
    for name in (
        "attempt_category_ledger.jsonl",
        "operation_journal.jsonl",
        "dispatch_state_ledger.jsonl",
        "transport_lifecycle_ledger.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "forecast_parse_results.jsonl",
        "forecast_validation_results.jsonl",
        "normalized_forecast_results.jsonl",
        "duplicate_risk_lineage.jsonl",
        "authoritative_result_selection.jsonl",
        "failed_call_ledger.jsonl",
    ):
        (run_dir / name).write_text("")


def load_authoritative_batch_003_call_ids() -> set[str]:
    original = read_jsonl(batch_exec.OUTPUT_ROOT / BATCH_003_RUN_ID / "normalized_forecast_results.jsonl")
    recovered = read_jsonl(batch_exec.OUTPUT_ROOT / BATCH_003_DIAGNOSIS_ID / "recoverable_result_ledger.jsonl")
    call_ids = {row["forecast_call_id"] for row in original if row.get("terminal_state") == "SUCCEEDED_VALID"}
    call_ids.update(row["forecast_call_id"] for row in recovered if row.get("validation_status") == "VALID")
    return call_ids


def find_existing_valid_result(call_id: str, output_root: Path) -> dict[str, Any] | None:
    for path in output_root.rglob("normalized_forecast_results.jsonl"):
        try:
            for row in read_jsonl(path):
                if row.get("forecast_call_id") == call_id and row.get("terminal_state") == "SUCCEEDED_VALID":
                    return row
        except Exception:
            continue
    return None


def category_map(scope_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in scope_rows:
        call = row["call"]
        call_id = call["forecast_call_id"]
        if call_id in SSL_UNKNOWN_CALL_IDS:
            mapping[call_id] = {
                "attempt_category": "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY",
                "recovery_authorization": "USER_AUTHORIZED_SINGLE_RECOVERY",
                "original_remote_state": "REMOTE_EXECUTION_STATE_UNKNOWN",
                "duplicate_execution_risk": "ACKNOWLEDGED",
                "maximum_new_dispatches": 1,
                "governance_reference": SSL_TRANSPORT_REPAIR_ID,
            }
        elif call_id == PARSE_REPLACEMENT_CALL_ID:
            mapping[call_id] = {
                "attempt_category": "GOVERNANCE_AUTHORIZED_PROVIDER_SCHEMA_REPLACEMENT",
                "replacement_authorization": "USER_AUTHORIZED_SINGLE_REPLACEMENT",
                "original_result_state": "FAILED_PARSE",
                "original_failure_reason": "PROVIDER_OUTPUT_TYPES_CONFIDENCE_NULL",
                "valid_original_result_exists": False,
                "duplicate_execution_risk": "NONE_ORIGINAL_RESULT_INVALID",
                "maximum_new_dispatches": 1,
                "governance_reference": BATCH_003_DIAGNOSIS_ID,
            }
        else:  # pragma: no cover - protected by verified scope
            raise Batch003GovernanceRecoveryError("UNEXPECTED_IN_SCOPE_CALL")
    return mapping


def leakage_audit(scope_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in scope_rows:
        audit = batch_exec.leakage_audit(row["prompt_row"]["prompt_text"], row["prompt_row"]["prompt_payload"], row["call"]["pack_type"])
        rows.append({"forecast_call_id": row["call"]["forecast_call_id"], "passed": audit["passed"], "violations": audit["violations"]})
        if not audit["passed"]:
            raise Batch003GovernanceRecoveryError("HISTORICAL_LEAKAGE_DETECTED:" + row["call"]["forecast_call_id"])
    return {"decision": "NO_HISTORICAL_LEAKAGE_DETECTED", "rows": rows}


def build_isolated_script_service() -> tuple[Any, str, dict[str, Any]]:
    credentials = google_clients.load_credentials(False, token_path=batch_exec.TOKEN_PATH, persist_refresh=False)
    script_id = google_clients.default_script_id()
    service = google_clients.build_script_service(credentials, batch_exec.SCRIPT_HTTP_TIMEOUT_SECONDS)
    return service, script_id, google_clients.describe_google_service_transport(service)


def dispatch_states_from_result(
    call_id: str,
    transport_meta: Mapping[str, Any],
    transport_result: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    states = [
        {"forecast_call_id": call_id, "state": "REQUEST_SEND_STARTED", "timestamp": now(), "evidence": "LOCAL_DISPATCH_ENTERED"},
    ]
    if transport_meta.get("ok") and isinstance(transport_result, Mapping):
        states.append({"forecast_call_id": call_id, "state": "GOOGLE_REQUEST_ACCEPTED", "timestamp": now(), "evidence": "EXECUTION_API_RESPONSE_RETURNED"})
        execution_id = transport_result.get("execution_id") or transport_result.get("apps_script_execution_id")
        if execution_id:
            states.append({"forecast_call_id": call_id, "state": "APPS_SCRIPT_EXECUTION_ID_RECEIVED", "timestamp": now(), "evidence": execution_id})
        if str(transport_result.get("request_status") or "") == "attempted":
            states.append({"forecast_call_id": call_id, "state": "BRIDGE_EXECUTION_STARTED", "timestamp": now(), "evidence": "REQUEST_STATUS_ATTEMPTED"})
            states.append({"forecast_call_id": call_id, "state": "PROVIDER_DISPATCH_CONFIRMED", "timestamp": now(), "evidence": "BRIDGE_REQUEST_STATUS_ATTEMPTED"})
    else:
        classification = dict(transport_meta.get("classification") or {})
        dispatch_certainty = classification.get("dispatch_certainty")
        if dispatch_certainty == "CONFIRMED_NOT_SENT":
            states.append({"forecast_call_id": call_id, "state": "REQUEST_NOT_SENT", "timestamp": now(), "evidence": classification.get("category")})
        else:
            states.append({"forecast_call_id": call_id, "state": "REMOTE_STATE_UNKNOWN", "timestamp": now(), "evidence": classification.get("category")})
    return states


def authoritative_selection_row(call: Mapping[str, Any], attempt_meta: Mapping[str, Any], terminal_state: str, run_dir: Path) -> dict[str, Any]:
    if terminal_state == "SUCCEEDED_VALID":
        if call["forecast_call_id"] in SSL_UNKNOWN_CALL_IDS:
            reason = "NO_RECOVERABLE_ORIGINAL_RESULT_FOUND_AFTER_FINAL_BOUNDED_SEARCH_AND_SINGLE_RECOVERY_WAS_EXPLICITLY_AUTHORIZED"
        else:
            reason = "ORIGINAL_PROVIDER_RESULT_FAILED_FROZEN_SCHEMA_WITH_NULL_CONFIDENCE_AND_SINGLE_REPLACEMENT_WAS_EXPLICITLY_AUTHORIZED"
        return {
            "forecast_call_id": call["forecast_call_id"],
            "selected_result_run_id": run_dir.name,
            "selected_terminal_state": terminal_state,
            "authoritative_result": "RECOVERY_OR_REPLACEMENT_RESULT",
            "authority_reason": reason,
            "attempt_category": attempt_meta["attempt_category"],
            "original_attempt_reference": attempt_meta["original_attempt_reference"],
        }
    return {
        "forecast_call_id": call["forecast_call_id"],
        "selected_result_run_id": None,
        "selected_terminal_state": terminal_state,
        "authoritative_result": "NO_VALID_RESULT_SELECTED",
        "authority_reason": "NO_CONTRACT_VALID_RESULT_AVAILABLE",
        "attempt_category": attempt_meta["attempt_category"],
        "original_attempt_reference": attempt_meta["original_attempt_reference"],
    }


def load_original_reference_rows() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    failed_batch = {row["forecast_call_id"]: row for row in read_jsonl(batch_exec.OUTPUT_ROOT / BATCH_003_RUN_ID / "failed_call_ledger.jsonl")}
    ssl_retry = {row["forecast_call_id"]: row for row in read_jsonl(batch_exec.OUTPUT_ROOT / SSL_TRANSPORT_REPAIR_ID / "retry_governance_ledger.jsonl")}
    diagnosis_retry = {row["forecast_call_id"]: row for row in read_jsonl(batch_exec.OUTPUT_ROOT / BATCH_003_DIAGNOSIS_ID / "retry_safety_ledger.jsonl")}
    return failed_batch, ssl_retry, diagnosis_retry


def update_manifest(path: Path, **updates: Any) -> None:
    manifest = read_json(path)
    manifest.update(updates)
    write_json(path, manifest)


def execute_recovery(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    branch = git_branch()
    head = git_head()
    if branch != "codex/immediate-impulse-outcome-recovery-r1":
        raise Batch003GovernanceRecoveryError("BRANCH_MISMATCH")
    if enforce_head and head != EXPECTED_START_HEAD and not is_descendant_of(EXPECTED_START_HEAD):
        raise Batch003GovernanceRecoveryError("HEAD_ANCESTRY_NOT_CLEAN")
    repo_state = {
        "branch": branch,
        "head": head,
        "expected_head_matched": head == EXPECTED_START_HEAD,
        "clean_descendant_of_expected_head": is_descendant_of(EXPECTED_START_HEAD),
    }

    scope_bundle = verified_scope_bundle()
    scope_rows = scope_bundle["selected"]
    authoritative_existing = load_authoritative_batch_003_call_ids()
    if len(authoritative_existing) != 7:
        raise Batch003GovernanceRecoveryError("BATCH_003_PRIOR_AUTHORITATIVE_COUNT_MISMATCH")
    if authoritative_existing.intersection(IN_SCOPE_CALL_IDS):
        raise Batch003GovernanceRecoveryError("IN_SCOPE_CALL_ALREADY_AUTHORITATIVE")

    leakage = leakage_audit(scope_rows)
    auth_result = dict(batch_exec.verify_google_preflight())
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, repo_state, auth_result, scope_rows)

    attempt_categories = category_map(scope_rows)
    failed_batch_rows, ssl_retry_rows, diagnosis_retry_rows = load_original_reference_rows()
    dispatched_this_move: set[str] = set()
    duplicate_lineage_rows: list[dict[str, Any]] = []
    call_results: list[dict[str, Any]] = []
    stop_remaining = False

    for scope_row in scope_rows:
        call = scope_row["call"]
        call_id = call["forecast_call_id"]
        attempt_meta = dict(attempt_categories[call_id])
        attempt_meta.update(
            {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "original_attempt_reference": {
                    "batch_003_execution_id": BATCH_003_RUN_ID,
                    "batch_003_diagnosis_id": BATCH_003_DIAGNOSIS_ID,
                    "ssl_transport_repair_id": SSL_TRANSPORT_REPAIR_ID if call_id in SSL_UNKNOWN_CALL_IDS else None,
                },
            }
        )
        append_jsonl(run_dir / "attempt_category_ledger.jsonl", attempt_meta)

        if stop_remaining:
            break
        if call_id in dispatched_this_move:
            raise Batch003GovernanceRecoveryError("CALL_ALREADY_DISPATCHED:" + call_id)
        if find_existing_valid_result(call_id, output_root) is not None:
            skipped = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "SKIPPED_EXISTING_AUTHORITATIVE_RESULT",
                "reason": "EXISTING_AUTHORITATIVE_RESULT_DISCOVERED_BEFORE_DISPATCH",
            }
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "SKIPPED_EXISTING_AUTHORITATIVE_RESULT", **skipped})
            append_jsonl(run_dir / "failed_call_ledger.jsonl", skipped)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "SKIPPED_EXISTING_AUTHORITATIVE_RESULT", run_dir))
            call_results.append(skipped)
            stop_remaining = True
            continue

        append_jsonl(
            run_dir / "operation_journal.jsonl",
            {
                "event": "CALL_STARTED",
                "forecast_call_id": call_id,
                "batch_id": FROZEN_BATCH_ID,
                "user_batch_label": USER_BATCH_LABEL,
                "execution_order": call["execution_order"],
                "attempt_number": 1,
                "attempt_category": attempt_meta["attempt_category"],
                "provider": call["provider"],
                "model": call["model"],
                "episode_id": call["episode_id"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": scope_row["prompt_fingerprint"]["prompt_text_fingerprint"],
                "started_at": now(),
            },
        )

        service, script_id, created_transport = build_isolated_script_service()
        append_jsonl(
            run_dir / "transport_lifecycle_ledger.jsonl",
            {
                "forecast_call_id": call_id,
                "attempt_category": attempt_meta["attempt_category"],
                "phase": "CREATED",
                "timestamp": now(),
                "transport": created_transport,
            },
        )
        payload = step6.bridge_payload(scope_row["pack_payload"], scope_row["prompt_row"]["prompt_text"], run_id=run_dir.name, arm="BASELINE")
        transport_meta = batch_exec.default_dispatch(service, script_id, payload)
        transport_result = transport_meta.get("result") if isinstance(transport_meta, Mapping) else None
        closed_transport = google_clients.close_google_service(service)
        append_jsonl(
            run_dir / "transport_lifecycle_ledger.jsonl",
            {
                "forecast_call_id": call_id,
                "attempt_category": attempt_meta["attempt_category"],
                "phase": "CLOSED",
                "timestamp": now(),
                "transport": closed_transport,
            },
        )
        dispatched_this_move.add(call_id)

        for state_row in dispatch_states_from_result(call_id, transport_meta, transport_result):
            append_jsonl(run_dir / "dispatch_state_ledger.jsonl", state_row)

        raw_output = transport_result.get("raw_output") if isinstance(transport_result, Mapping) else None
        raw_transport_row = {
            "forecast_call_id": call_id,
            "attempt_category": attempt_meta["attempt_category"],
            "dispatch_timestamp": now(),
            "requested_provider": call["provider"],
            "requested_model": call["model"],
            "selected_adapter": transport_result.get("provider") if isinstance(transport_result, Mapping) else None,
            "actual_provider": transport_result.get("actual_provider") if isinstance(transport_result, Mapping) else None,
            "actual_model": transport_result.get("actual_model") if isinstance(transport_result, Mapping) else None,
            "request_status": transport_result.get("request_status") if isinstance(transport_result, Mapping) else None,
            "response_status": transport_result.get("response_status") if isinstance(transport_result, Mapping) else None,
            "terminal_status": transport_result.get("terminal_status") if isinstance(transport_result, Mapping) else None,
            "provider_request_id": transport_result.get("request_id") if isinstance(transport_result, Mapping) else None,
            "provider_error": transport_result.get("error") if isinstance(transport_result, Mapping) else None,
            "raw_transport_result": transport_result,
            "transport_ok": bool(transport_meta.get("ok")) if isinstance(transport_meta, Mapping) else False,
            "transport_request": transport_meta.get("request") if isinstance(transport_meta, Mapping) else None,
            "transport_classification": transport_meta.get("classification") if isinstance(transport_meta, Mapping) else None,
            "stop_reason": transport_result.get("stop_reason") if isinstance(transport_result, Mapping) else None,
            "prompt_tokens": transport_result.get("prompt_tokens") if isinstance(transport_result, Mapping) else None,
            "completion_tokens": transport_result.get("completion_tokens") if isinstance(transport_result, Mapping) else None,
            "response_length": len(raw_output) if isinstance(raw_output, str) else None,
            "completion_timestamp": transport_result.get("completed_timestamp") if isinstance(transport_result, Mapping) else None,
            "pack_row_fingerprint": call["pack_row_fingerprint"],
            "prompt_fingerprint": scope_row["prompt_fingerprint"]["prompt_text_fingerprint"],
        }
        append_jsonl(run_dir / "raw_transport_results.jsonl", raw_transport_row)
        append_jsonl(
            run_dir / "raw_provider_outputs.jsonl",
            {
                "forecast_call_id": call_id,
                "attempt_category": attempt_meta["attempt_category"],
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_fingerprint": scope_row["prompt_fingerprint"]["prompt_text_fingerprint"],
                "raw_provider_output": raw_output,
            },
        )
        duplicate_lineage = {
            "forecast_call_id": call_id,
            "attempt_category": attempt_meta["attempt_category"],
            "original_attempt_reference": attempt_meta["original_attempt_reference"],
            "duplicate_execution_risk": attempt_meta["duplicate_execution_risk"],
            "new_recovery_attempt_run_id": run_dir.name,
            "new_dispatch_count_in_move": 1,
            "ssl_retry_governance_reference": ssl_retry_rows.get(call_id) if call_id in ssl_retry_rows else None,
            "batch_003_failed_row": failed_batch_rows.get(call_id),
            "diagnosis_retry_reference": diagnosis_retry_rows.get(call_id),
        }
        append_jsonl(run_dir / "duplicate_risk_lineage.jsonl", duplicate_lineage)
        duplicate_lineage_rows.append(duplicate_lineage)

        if not transport_meta.get("ok") or not isinstance(transport_result, Mapping):
            terminal_state = batch_exec.classify_transport_failure(transport_result if isinstance(transport_result, Mapping) else None)
            reason = transport_meta.get("classification", {}).get("category", "TRANSPORT_NOT_OK")
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": terminal_state,
                "reason": reason,
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": terminal_state, **failed_row})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, terminal_state, run_dir))
            call_results.append(failed_row)
            if reason in TRANSPORT_STOP_CATEGORIES:
                stop_remaining = True
            continue

        status = str(transport_result.get("status") or "")
        if status in batch_exec.PROVIDER_FAILURE_STATUSES or batch_exec.provider_error_without_forecast_payload(transport_result):
            authority_row = batch_exec.provider_authority_result(call, transport_result) | {"attempt_category": attempt_meta["attempt_category"]}
            append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)
            reason = status if status in batch_exec.PROVIDER_FAILURE_STATUSES else "PROVIDER_RESPONSE_NOT_USABLE_FOR_FORECAST_PARSING"
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PROVIDER",
                "reason": reason,
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER", **failed_row})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "FAILED_PROVIDER", run_dir))
            call_results.append(failed_row)
            continue

        authority_row = batch_exec.provider_authority_result(call, transport_result) | {"attempt_category": attempt_meta["attempt_category"]}
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)
        if not authority_row["authority_passed"]:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PROVIDER_AUTHORITY",
                "reason": authority_row["reason"],
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER_AUTHORITY", **failed_row})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "FAILED_PROVIDER_AUTHORITY", run_dir))
            call_results.append(failed_row)
            stop_remaining = True
            continue

        raw_claimed_provider = None
        try:
            parsed, parse_audit = step6.normalize_provider_output(raw_output)
            if isinstance(parsed, Mapping):
                raw_claimed_provider = parsed.get("provider")
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "parse_status": "PARSED",
                    "raw_claimed_provider": raw_claimed_provider,
                    "parse_audit": parse_audit,
                },
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PARSE",
                "reason": str(exc),
            }
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "parse_status": "FAILED_PARSE",
                    "raw_claimed_provider": raw_claimed_provider,
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PARSE", **failed_row})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "FAILED_PARSE", run_dir))
            call_results.append(failed_row)
            continue

        try:
            prediction, paths = step6.response_to_contract(
                parsed,
                scope_row["pack_payload"],
                run_id=run_dir.name,
                created_ts=str(transport_result.get("completed_timestamp") or now()),
                raw_output=raw_output,
                bridge_result=transport_result,
            )
            normalized_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "pack_row_identity": call["pack_row_identity"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": scope_row["prompt_fingerprint"]["prompt_text_fingerprint"],
                "prompt_context_fingerprint": scope_row["prompt_fingerprint"]["prompt_context_fingerprint"],
                "terminal_state": "SUCCEEDED_VALID",
                "raw_claimed_provider": raw_claimed_provider,
                "prediction": prediction,
                "paths": paths,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "validation_status": "VALID",
                    "prediction_id": prediction["prediction_id"],
                    "path_count": len(paths),
                },
            )
            append_jsonl(run_dir / "normalized_forecast_results.jsonl", normalized_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "SUCCEEDED_VALID", "forecast_call_id": call_id, "attempt_category": attempt_meta["attempt_category"], "prediction_id": prediction["prediction_id"]})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "SUCCEEDED_VALID", run_dir))
            call_results.append(
                {
                    "forecast_call_id": call_id,
                    "episode_id": call["episode_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "pack_type": call["pack_type"],
                    "attempt_category": attempt_meta["attempt_category"],
                    "terminal_state": "SUCCEEDED_VALID",
                    "raw_claimed_provider": raw_claimed_provider,
                }
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_VALIDATION",
                "reason": str(exc),
                "raw_claimed_provider": raw_claimed_provider,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "validation_status": "FAILED_VALIDATION",
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_VALIDATION", **failed_row})
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", authoritative_selection_row(call, attempt_meta, "FAILED_VALIDATION", run_dir))
            call_results.append(failed_row)

    terminal_counts = Counter(row["terminal_state"] for row in call_results)
    authority_rows = read_jsonl(run_dir / "provider_authority_results.jsonl")
    agreements = sum(1 for row in authority_rows if row.get("authority_passed"))
    conflicts = sum(1 for row in authority_rows if not row.get("authority_passed"))
    normalized_rows = read_jsonl(run_dir / "normalized_forecast_results.jsonl")
    failed_rows = read_jsonl(run_dir / "failed_call_ledger.jsonl")
    provider_model_results = dict(Counter(f"{row['provider']}|{row['model']}|{row['terminal_state']}" for row in call_results))

    batch001_valid = read_json(batch_exec.OUTPUT_ROOT / BATCH_001_RUN_ID / "batch_reconciliation.json")["successful_valid_calls"]
    batch002_valid = read_json(batch_exec.OUTPUT_ROOT / BATCH_002_RUN_ID / "batch_002_final_reconciliation.json")["authoritative_valid_results"]
    prior_batch003_valid = read_json(batch_exec.OUTPUT_ROOT / BATCH_003_DIAGNOSIS_ID / "batch_003_reconciliation.json")["authoritative_valid_results_after_diagnosis"]
    total_batch003_valid = prior_batch003_valid + len(normalized_rows)
    unresolved_batch003 = 12 - total_batch003_valid
    cumulative_validated = batch001_valid + batch002_valid + total_batch003_valid

    reconciliation = {
        "authorized_new_calls": 5,
        "attempted_new_calls": sum(1 for row in call_results if row["terminal_state"] != "SKIPPED_EXISTING_AUTHORITATIVE_RESULT"),
        "valid_new_results": terminal_counts["SUCCEEDED_VALID"],
        "failed_transport_calls": terminal_counts["FAILED_TRANSPORT"],
        "failed_provider_calls": terminal_counts["FAILED_PROVIDER"],
        "failed_provider_authority_calls": terminal_counts["FAILED_PROVIDER_AUTHORITY"],
        "failed_parse_calls": terminal_counts["FAILED_PARSE"],
        "failed_validation_calls": terminal_counts["FAILED_VALIDATION"],
        "skipped_existing_authoritative_results": terminal_counts["SKIPPED_EXISTING_AUTHORITATIVE_RESULT"],
        "four_ssl_unknown_recovery_outcomes": [row for row in call_results if row["forecast_call_id"] in SSL_UNKNOWN_CALL_IDS],
        "parse_schema_replacement_outcome": next((row for row in call_results if row["forecast_call_id"] == PARSE_REPLACEMENT_CALL_ID), None),
        "results_by_provider_model": provider_model_results,
        "manifest_transport_agreements": agreements,
        "manifest_transport_conflicts": conflicts,
        "transport_lifecycle_result": "ALL_TRANSPORTS_EXPLICITLY_DISPOSED",
        "dispatch_state_evidence_result": "APPEND_ONLY_STATES_RECORDED",
        "raw_output_preservation_result": "PRESERVED_BEFORE_PARSE_FOR_ALL_DISPATCHED_CALLS",
        "parse_results": dict(Counter(row.get("parse_status") for row in read_jsonl(run_dir / "forecast_parse_results.jsonl"))),
        "contract_validation_results": dict(Counter(row.get("validation_status") for row in read_jsonl(run_dir / "forecast_validation_results.jsonl"))),
        "leakage_control_result": leakage["decision"],
        "duplicate_risk_lineage_result": "PRESERVED",
        "exact_failed_calls": failed_rows,
        "batch_003_authoritative_valid_results": total_batch003_valid,
        "batch_003_unresolved_results": unresolved_batch003,
        "batch_003_provider_authority_conflicts": conflicts,
        "batch_003_duplicate_authoritative_results": 0,
        "cumulative_validated_forecast_calls": cumulative_validated,
        "remaining_planned_forecast_calls": 564 - cumulative_validated,
    }
    write_json(run_dir / "batch_003_final_reconciliation.json", reconciliation)
    write_json(run_dir / "recovery_summary.json", reconciliation)

    if terminal_counts["SKIPPED_EXISTING_AUTHORITATIVE_RESULT"]:
        recovery_status = "BATCH_003_GOVERNANCE_RECOVERY_BLOCKED"
        transport_decision = "RECOVERY_TRANSPORT_NOT_REACHED"
        provider_decision = "RECOVERY_PROVIDER_AUTHORITY_NOT_REACHED"
        contract_decision = "RECOVERY_FORECAST_CONTRACT_NOT_REACHED"
        duplicate_decision = "DUPLICATE_RESULT_DISCOVERED_RECONCILIATION_REQUIRED"
        batch003_decision = "FORECAST_BATCH_003_GOVERNANCE_REVIEW_REQUIRED"
        scaling = "REPAIR_BEFORE_FURTHER_FORECAST_EXECUTION"
    elif any(terminal_counts[state] for state in ("FAILED_TRANSPORT", "FAILED_PROVIDER", "FAILED_PROVIDER_AUTHORITY", "FAILED_PARSE", "FAILED_VALIDATION")):
        recovery_status = "BATCH_003_GOVERNANCE_RECOVERY_PARTIALLY_COMPLETE"
        transport_decision = "RECOVERY_TRANSPORT_FAILURES_PRESENT" if terminal_counts["FAILED_TRANSPORT"] else "ALL_RECOVERY_TRANSPORTS_SUCCEEDED"
        provider_decision = "RECOVERY_PROVIDER_AUTHORITY_FAILURES_PRESENT" if terminal_counts["FAILED_PROVIDER_AUTHORITY"] else "ALL_RECOVERY_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        contract_decision = "RECOVERY_FORECAST_CONTRACT_FAILURES_PRESENT" if (terminal_counts["FAILED_PARSE"] or terminal_counts["FAILED_VALIDATION"]) else "ALL_RECOVERY_FORECAST_RESULTS_CONTRACT_VALID"
        duplicate_decision = "DUPLICATE_RISK_ACCEPTED_AND_LINEAGE_PRESERVED"
        batch003_decision = "FORECAST_BATCH_003_REMAINS_INCOMPLETE"
        scaling = "REPAIR_BEFORE_FURTHER_FORECAST_EXECUTION" if terminal_counts["FAILED_TRANSPORT"] else "RETRY_FAILED_CALLS_REQUIRES_AUTHORIZATION"
    else:
        recovery_status = "BATCH_003_GOVERNANCE_RECOVERY_COMPLETE"
        transport_decision = "ALL_RECOVERY_TRANSPORTS_SUCCEEDED"
        provider_decision = "ALL_RECOVERY_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        contract_decision = "ALL_RECOVERY_FORECAST_RESULTS_CONTRACT_VALID"
        duplicate_decision = "DUPLICATE_RISK_ACCEPTED_AND_LINEAGE_PRESERVED"
        batch003_decision = "FORECAST_BATCH_003_COMPLETE"
        scaling = "READY_FOR_NEXT_FORECAST_BATCH_RANGE"

    decision = {
        "recovery_status": recovery_status,
        "transport_decision": transport_decision,
        "provider_authority_decision": provider_decision,
        "contract_decision": contract_decision,
        "duplicate_risk_decision": duplicate_decision,
        "batch_003_decision": batch003_decision,
        "scaling_decision": scaling,
    }
    write_json(run_dir / "recovery_decision.json", decision)
    update_manifest(
        run_dir / "run_manifest.json",
        provider_calls_executed=reconciliation["attempted_new_calls"],
        successful_valid_calls=reconciliation["valid_new_results"],
        failed_transport_calls=reconciliation["failed_transport_calls"],
        failed_provider_calls=reconciliation["failed_provider_calls"],
        failed_provider_authority_calls=reconciliation["failed_provider_authority_calls"],
        failed_parse_calls=reconciliation["failed_parse_calls"],
        failed_validation_calls=reconciliation["failed_validation_calls"],
        skipped_existing_authoritative_results=reconciliation["skipped_existing_authoritative_results"],
        normalized_result_count=len(normalized_rows),
    )
    return {
        "run_dir": run_dir,
        "repo_state": repo_state,
        "auth_result": auth_result,
        "decision": decision,
        "reconciliation": reconciliation,
        "leakage": leakage,
        "duplicate_lineage_rows": duplicate_lineage_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = execute_recovery(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp, enforce_head=not args.skip_head_check)
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
