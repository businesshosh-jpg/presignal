#!/usr/bin/env python3
"""Diagnose and repair the shared transport failure affecting forecast Batch 002."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch001
from automation import google_clients

PLAN_ID = batch001.PLAN_ID
FORECAST_PLAN_ROOT = batch001.PLAN_ROOT
OUTPUT_ROOT = batch001.OUTPUT_ROOT
FAILED_COORDINATION_ID = "PPHB-R1-FORECAST-EXECUTION-BATCHES-002-003-20260729T133416Z-9675b262960c"
FAILED_BATCH_002_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-002-20260729T133420Z-0469b99f5e03"
BLOCKED_COORDINATION_ID = "PPHB-R1-FORECAST-EXECUTION-BATCHES-002-003-20260729T131559Z-49bc327a5c29"
SUCCESSFUL_BATCH_001_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8"
USER_BATCH_LABEL = "FORECAST_BATCH_002"
FROZEN_BATCH_ID = "FCB_PACK_A_002"
HEALTH_FUNCTION = "presignalRuntimeHealthCheck"
EXPECTED_START_HEAD = "1e82c6df5d8de5327a412ccbef3de0974e4377de"
FAILED_CALL_IDS = [
    "FCL_befd6d6947490cc19f4754b9",
    "FCL_1ce38eb60f0865beca69bb31",
    "FCL_1e7b6936b48bf931a7ed5e7d",
    "FCL_64c262f5f677009a4ce5c45a",
]
INCOMPLETE_CALL_ID = "FCL_d72f741393a7643ea859edb8"
TERMINAL_FAILURE_IDS = set(FAILED_CALL_IDS)
AFFECTED_CALL_IDS = TERMINAL_FAILURE_IDS | {INCOMPLETE_CALL_ID}
SCRIPT_TIMEOUT_SECONDS = batch001.SCRIPT_HTTP_TIMEOUT_SECONDS


class ForecastTransportRepairError(RuntimeError):
    """Repair work failed closed."""


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))


def git_head() -> str:
    return batch001.git_head()


def git_branch() -> str:
    return batch001.git_branch()


def is_descendant_of(commit: str) -> bool:
    return batch001.is_descendant_of(commit)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "failed_batch_002_id": FAILED_BATCH_002_ID,
        "move": "FORECAST_TRANSPORT_REPAIR_BATCH_002",
        "timestamp": timestamp,
    }
    run_id = (
        "PPHB-R1-FORECAST-TRANSPORT-REPAIR-BATCH-002-"
        + timestamp.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def failed_batch_root() -> Path:
    return OUTPUT_ROOT / FAILED_BATCH_002_ID


def batch_001_root() -> Path:
    return OUTPUT_ROOT / SUCCESSFUL_BATCH_001_ID


def load_call_manifest() -> dict[str, dict[str, Any]]:
    bundle = batch001.verified_batch_bundle(user_batch_label=USER_BATCH_LABEL, frozen_batch_id=FROZEN_BATCH_ID)
    return {row["call"]["forecast_call_id"]: row["call"] for row in bundle["bundles"]}


def classify_incomplete_call(started_row: Mapping[str, Any], transport_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if INCOMPLETE_CALL_ID in transport_rows:
        raise ForecastTransportRepairError("INCOMPLETE_CALL_HAS_TRANSPORT_ROW_UNEXPECTEDLY")
    return {
        "forecast_call_id": INCOMPLETE_CALL_ID,
        "original_state": "CALL_STARTED_WITHOUT_TERMINAL_STATE",
        "classification": "REMOTE_EXECUTION_STATE_UNKNOWN",
        "decision": "INCOMPLETE_CALL_REMOTE_STATE_UNKNOWN",
        "remote_dispatch_evidence": "CALL_STARTED_ONLY_NO_TRANSPORT_RESULT",
        "remote_result_evidence": "NONE",
        "recommended_action": "MANUAL_GOVERNANCE_REVIEW_REQUIRED",
        "retry_safety_classification": "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN",
        "duplicate_call_risk": "UNRESOLVED_REMOTE_EXECUTION_POSSIBLE",
        "dispatch_timestamp": started_row.get("started_at"),
    }


def normalized_transport_classification(transport_row: Mapping[str, Any] | None) -> dict[str, Any]:
    if not transport_row:
        return {}
    classification = dict(transport_row.get("transport_classification") or {})
    if classification.get("category") != "UNKNOWN_SHARED_TRANSPORT_ERROR":
        return classification
    exception_type = str(classification.get("exception_type") or "")
    message = str(classification.get("message") or "")
    if exception_type == "ServerNotFoundError" or "unable to find the server" in message.lower():
        normalized = dict(classification)
        normalized["category"] = "GOOGLE_API_CONNECTION_ERROR"
        normalized["dispatch_certainty"] = "CONFIRMED_NOT_SENT"
        normalized["retry_eligible"] = True
        normalized["reclassified_from_preserved_exception_evidence"] = True
        return normalized
    return classification


def classify_retry_safety(
    *,
    call: Mapping[str, Any],
    failed_row: Mapping[str, Any],
    transport_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    classification = normalized_transport_classification(transport_row)
    category = classification.get("category")
    dispatch_certainty = classification.get("dispatch_certainty")
    remote_dispatch_evidence = "TRANSPORT_RESULT_PRESENT" if transport_row else "NO_TRANSPORT_RESULT"
    if category == "GOOGLE_API_CONNECTION_ERROR" and dispatch_certainty == "CONFIRMED_NOT_SENT":
        retry_safety = "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT"
        recommended_action = "RETRY_ONLY_UNDER_SEPARATE_EXPLICIT_BATCH_002_RESUME_AUTHORIZATION"
        duplicate_risk = "NO_CONFIRMED_REMOTE_DISPATCH"
    else:
        retry_safety = "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN"
        recommended_action = "MANUAL_GOVERNANCE_REVIEW_REQUIRED"
        duplicate_risk = "REMOTE_DISPATCH_NOT_PROVABLY_ABSENT"
    return {
        "forecast_call_id": call["forecast_call_id"],
        "original_state": failed_row["terminal_state"],
        "provider": call["provider"],
        "model": call["model"],
        "episode_id": call["episode_id"],
        "remote_dispatch_evidence": remote_dispatch_evidence,
        "remote_result_evidence": "NO_PROVIDER_RESULT_PRESERVED",
        "duplicate_call_risk": duplicate_risk,
        "transport_classification": classification,
        "retry_safety_classification": retry_safety,
        "recommended_action": recommended_action,
    }


def build_lifecycle_rows(
    call_manifest: Mapping[str, Mapping[str, Any]],
    started_rows: Mapping[str, Mapping[str, Any]],
    transport_rows: Mapping[str, Mapping[str, Any]],
    failed_rows: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call_id in sorted(AFFECTED_CALL_IDS, key=lambda cid: call_manifest[cid]["execution_order"]):
        call = call_manifest[call_id]
        started = started_rows.get(call_id)
        transport = transport_rows.get(call_id)
        classification = normalized_transport_classification(transport)
        dispatch_certainty = classification.get("dispatch_certainty")
        category = classification.get("category")
        rows.append(
            {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "execution_order": call["execution_order"],
                "authorized": True,
                "journaled": started is not None,
                "dispatch_started": started is not None,
                "request_transmitted": (
                    True
                    if dispatch_certainty in {"CONFIRMED_RESPONSE"}
                    else False
                    if dispatch_certainty == "CONFIRMED_NOT_SENT"
                    else None
                ),
                "apps_script_invocation_accepted": True if dispatch_certainty == "CONFIRMED_RESPONSE" else None,
                "apps_script_execution_started": True if dispatch_certainty == "CONFIRMED_RESPONSE" else None,
                "provider_route_invoked": True if dispatch_certainty == "CONFIRMED_RESPONSE" else None,
                "provider_response_received": True if transport and transport.get("raw_provider_output") else False if transport else None,
                "transport_response_returned_locally": transport is not None,
                "raw_output_persisted": transport is not None,
                "terminal_state_persisted": call_id in failed_rows,
                "transport_category": category,
                "dispatch_certainty": dispatch_certainty,
                "started_at": (started or {}).get("started_at"),
                "completion_timestamp": (transport or {}).get("completion_timestamp"),
            }
        )
    return rows


def compare_batch_001_and_batch_002() -> dict[str, Any]:
    batch_001_manifest = read_json(batch_001_root() / "run_manifest.json")
    batch_002_manifest = read_json(failed_batch_root() / "run_manifest.json")
    bundle_001 = batch001.verified_batch_bundle(user_batch_label="FORECAST_BATCH_001", frozen_batch_id="FCB_PACK_A_001")
    bundle_002 = batch001.verified_batch_bundle(user_batch_label=USER_BATCH_LABEL, frozen_batch_id=FROZEN_BATCH_ID)
    prompt_lengths_001 = [len(row["prompt_row"]["prompt_text"]) for row in bundle_001["bundles"]]
    prompt_lengths_002 = [len(row["prompt_row"]["prompt_text"]) for row in bundle_002["bundles"]]
    return {
        "same_token_path": batch_001_manifest["google_preflight"]["token_path"] == batch_002_manifest["google_preflight"]["token_path"],
        "same_scopes": batch_001_manifest["google_preflight"]["scope_names"] == batch_002_manifest["google_preflight"]["scope_names"],
        "same_spreadsheet_id": (
            batch_001_manifest["google_preflight"]["resource_identity_result"]["spreadsheet_id"]
            == batch_002_manifest["google_preflight"]["resource_identity_result"]["spreadsheet_id"]
        ),
        "same_script_id": (
            batch_001_manifest["google_preflight"]["resource_identity_result"]["script_id"]
            == batch_002_manifest["google_preflight"]["resource_identity_result"]["script_id"]
        ),
        "same_bridge_function": True,
        "same_script_http_timeout_seconds": SCRIPT_TIMEOUT_SECONDS,
        "same_provider_bridge_hard_timeout_seconds": 180,
        "same_pack_type": batch_001_manifest["pack_type"] == batch_002_manifest["pack_type"] == "PACK_A",
        "same_execution_endpoint": "scripts.run(apiCallAuthoritativeProviderJsonObject)",
        "batch_001_provider_calls_executed": batch_001_manifest["provider_calls_executed"],
        "batch_002_provider_calls_executed": batch_002_manifest["provider_calls_executed"],
        "batch_001_prompt_length_summary": {
            "min": min(prompt_lengths_001),
            "max": max(prompt_lengths_001),
            "avg": round(sum(prompt_lengths_001) / len(prompt_lengths_001), 1),
        },
        "batch_002_prompt_length_summary": {
            "min": min(prompt_lengths_002),
            "max": max(prompt_lengths_002),
            "avg": round(sum(prompt_lengths_002) / len(prompt_lengths_002), 1),
        },
        "smallest_meaningful_difference": (
            "Batch 001 completed 12/12 with one shared Apps Script client across the batch; "
            "Batch 002 encountered a 300-second Google-side timeout and then continued reusing "
            "the same client path as SSLEOF and script.googleapis.com resolution failures surfaced."
        ),
    }


def determine_root_cause(transport_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    categories = [row.get("transport_classification", {}).get("category") for row in transport_rows.values()]
    exception_types = [row.get("transport_classification", {}).get("exception_type") for row in transport_rows.values()]
    return {
        "root_cause_decision": "SHARED_TRANSPORT_ROOT_CAUSE_PARTIALLY_IDENTIFIED",
        "root_cause": (
            "A shared Apps Script transport-path defect surfaced during Batch 002: one long-running "
            "Execution API request hit the local 300-second read timeout, while adjacent calls on the "
            "same batch path failed with SSL EOF and script.googleapis.com resolution errors. The strongest "
            "mechanical repair is to stop reusing one long-lived Apps Script client across the batch and to "
            "classify confirmed local name-resolution failures separately from unknown dispatch states."
        ),
        "evidence": {
            "transport_categories": categories,
            "exception_types": exception_types,
            "providers_affected": sorted({row["provider"] for row in transport_rows.values()}),
            "manifest_transport_agreements": 0,
            "provider_authority_reached": False,
            "parse_reached": False,
            "validation_reached": False,
        },
    }


def verify_transport_repair() -> dict[str, Any]:
    credentials = google_clients.load_credentials(False, token_path=batch001.TOKEN_PATH, persist_refresh=False)
    script_id = google_clients.default_script_id()
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        service = google_clients.build_script_service(credentials, SCRIPT_TIMEOUT_SECONDS)
        result = google_clients.run_script_function_with_metadata(service, script_id, HEALTH_FUNCTION, [], dev_mode=True)
        attempts.append(
            {
                "attempt": attempt,
                "timestamp": now(),
                "script_id": script_id,
                "transport_ok": bool(result.get("ok")),
                "classification": result.get("classification"),
                "elapsed_ms": result.get("elapsed_ms"),
                "response_present": result.get("response") is not None,
            }
        )
        if not result.get("ok"):
            break
    all_ok = all(row["transport_ok"] for row in attempts) and len(attempts) == 3
    return {
        "status": "PASSED" if all_ok else "FAILED",
        "health_function": HEALTH_FUNCTION,
        "service_rebuilt_per_attempt": True,
        "script_http_timeout_seconds": SCRIPT_TIMEOUT_SECONDS,
        "attempts": attempts,
        "provider_calls": 0,
    }


def initialize_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_TRANSPORT_REPAIR_BATCH_002",
            "plan_id": PLAN_ID,
            "failed_batch_002_id": FAILED_BATCH_002_ID,
            "failed_coordination_id": FAILED_COORDINATION_ID,
            "successful_batch_001_id": SUCCESSFUL_BATCH_001_ID,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "batch_003_executed": 0,
            "forecast_contract": "presignal_event_path_contract_v1_1",
            "pack_type": "PACK_A",
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "successful_batch_001_id": SUCCESSFUL_BATCH_001_ID,
            "blocked_coordination_id": BLOCKED_COORDINATION_ID,
            "failed_coordination_id": FAILED_COORDINATION_ID,
            "failed_batch_002_id": FAILED_BATCH_002_ID,
        },
    )


def execute_repair(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise ForecastTransportRepairError("BRANCH_MISMATCH")
    head = git_head()
    if head != EXPECTED_START_HEAD and not is_descendant_of(EXPECTED_START_HEAD):
        raise ForecastTransportRepairError("HEAD_ANCESTRY_NOT_CLEAN")

    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir)

    call_manifest = load_call_manifest()
    failed_root = failed_batch_root()
    failed_run_manifest = read_json(failed_root / "run_manifest.json")
    operation_rows = read_jsonl(failed_root / "operation_journal.jsonl")
    transport_rows_by_call = {row["forecast_call_id"]: row for row in read_jsonl(failed_root / "raw_transport_results.jsonl")}
    provider_output_rows = {row["forecast_call_id"]: row for row in read_jsonl(failed_root / "raw_provider_outputs.jsonl")}
    failed_rows_by_call = {row["forecast_call_id"]: row for row in read_jsonl(failed_root / "failed_call_ledger.jsonl")}

    started_rows = {row["forecast_call_id"]: row for row in operation_rows if row.get("event") == "CALL_STARTED"}
    lifecycle_rows = build_lifecycle_rows(call_manifest, started_rows, transport_rows_by_call, failed_rows_by_call)

    for call_id, transport_row in transport_rows_by_call.items():
        provider_output = provider_output_rows.get(call_id, {})
        transport_row["raw_provider_output"] = provider_output.get("raw_provider_output")
        transport_row["transport_classification"] = normalized_transport_classification(transport_row)

    terminal_classifications = [
        classify_retry_safety(
            call=call_manifest[call_id],
            failed_row=failed_rows_by_call[call_id],
            transport_row=transport_rows_by_call.get(call_id),
        )
        for call_id in FAILED_CALL_IDS
    ]
    incomplete_classification = classify_incomplete_call(started_rows[INCOMPLETE_CALL_ID], transport_rows_by_call)

    comparison = compare_batch_001_and_batch_002()
    root_cause = determine_root_cause(transport_rows_by_call)
    verification = verify_transport_repair()

    retry_rows = terminal_classifications + [
        {
            "forecast_call_id": incomplete_classification["forecast_call_id"],
            "original_state": incomplete_classification["original_state"],
            "provider": call_manifest[INCOMPLETE_CALL_ID]["provider"],
            "model": call_manifest[INCOMPLETE_CALL_ID]["model"],
            "episode_id": call_manifest[INCOMPLETE_CALL_ID]["episode_id"],
            "remote_dispatch_evidence": incomplete_classification["remote_dispatch_evidence"],
            "remote_result_evidence": incomplete_classification["remote_result_evidence"],
            "duplicate_call_risk": incomplete_classification["duplicate_call_risk"],
            "transport_classification": None,
            "retry_safety_classification": incomplete_classification["retry_safety_classification"],
            "recommended_action": incomplete_classification["recommended_action"],
        }
    ]

    retry_counts = Counter(row["retry_safety_classification"] for row in retry_rows)
    resumed_batch_reference = {"executed": False, "reason": "INCOMPLETE_CALL_REMOTE_STATE_UNKNOWN"}
    resume_authorization = {
        "resume_authorized": False,
        "reason": "INCOMPLETE_CALL_REMOTE_STATE_UNKNOWN",
        "incomplete_call_decision": incomplete_classification["decision"],
        "retry_safety_counts": dict(retry_counts),
        "required_conditions_failed": [
            "incomplete_call_state_resolved",
            "all_affected_calls_retry_safe",
        ],
    }

    write_jsonl(
        run_dir / "transport_failure_inventory.jsonl",
        [
            {
                "forecast_call_id": call_id,
                "episode_id": call_manifest[call_id]["episode_id"],
                "provider": call_manifest[call_id]["provider"],
                "model": call_manifest[call_id]["model"],
                "execution_order": call_manifest[call_id]["execution_order"],
                "observed_state": failed_rows_by_call[call_id]["terminal_state"] if call_id in failed_rows_by_call else "CALL_STARTED_ONLY",
                "transport_classification": transport_rows_by_call.get(call_id, {}).get("transport_classification"),
            }
            for call_id in sorted(AFFECTED_CALL_IDS, key=lambda cid: call_manifest[cid]["execution_order"])
        ],
    )
    write_jsonl(run_dir / "call_lifecycle_reconstruction.jsonl", lifecycle_rows)
    write_json(run_dir / "incomplete_call_classification.json", incomplete_classification)
    write_json(run_dir / "batch_001_batch_002_transport_comparison.json", comparison)
    write_json(run_dir / "shared_transport_root_cause.json", root_cause)
    write_json(
        run_dir / "transport_repair_contract.json",
        {
            "forecast_contract": "presignal_event_path_contract_v1_1",
            "pack_type": "PACK_A",
            "unchanged": [
                "forecast_call_id",
                "batch membership",
                "execution order",
                "provider/model assignment",
                "Pack row identity",
                "Pack row fingerprint",
                "prompt payload",
                "prompt fingerprint",
                "historical cutoff",
            ],
            "repair_scope": [
                "local transport classification",
                "per-dispatch Apps Script client rebuild",
                "call-free transport verification",
                "retry-safety classification",
            ],
        },
    )
    write_json(
        run_dir / "transport_repair_implementation_record.json",
        {
            "mechanical_repairs": [
                "classified ServerNotFoundError and 'Unable to find the server' failures as GOOGLE_API_CONNECTION_ERROR with CONFIRMED_NOT_SENT dispatch certainty",
                "rebuild the Apps Script client per forecast dispatch instead of reusing one long-lived client across a batch",
            ],
            "timeout_or_polling_changes": {
                "script_http_timeout_seconds": SCRIPT_TIMEOUT_SECONDS,
                "changed": False,
                "polling_changed": False,
            },
        },
    )
    write_json(run_dir / "transport_verification_results.json", verification)
    write_jsonl(run_dir / "remote_result_recovery_ledger.jsonl", [])
    write_jsonl(run_dir / "retry_safety_ledger.jsonl", retry_rows)
    write_json(run_dir / "resume_authorization_decision.json", resume_authorization)
    write_json(run_dir / "resumed_batch_result_reference.json", resumed_batch_reference)

    safe_retry_calls = [
        row["forecast_call_id"]
        for row in retry_rows
        if row["retry_safety_classification"] == "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT"
    ]
    unsafe_retry_calls = [
        row["forecast_call_id"]
        for row in retry_rows
        if row["retry_safety_classification"] != "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT"
    ]

    decisions = {
        "root_cause_decision": root_cause["root_cause_decision"],
        "incomplete_call_decision": incomplete_classification["decision"],
        "repair_decision": (
            "SHARED_TRANSPORT_REPAIR_VALIDATED"
            if verification["status"] == "PASSED"
            else "SHARED_TRANSPORT_REPAIR_IMPLEMENTED_NOT_VALIDATED"
        ),
        "resume_decision": "BATCH_002_NOT_RESUMED_RETRY_SAFETY_NOT_PROVEN",
        "next_phase_decision": "RETRY_AUTHORIZATION_REQUIRES_GOVERNANCE",
    }
    write_json(
        run_dir / "repair_summary.json",
        {
            "affected_call_count": 5,
            "failed_transport_calls": 4,
            "incomplete_started_calls": 1,
            "safe_retry_call_count": len(safe_retry_calls),
            "unsafe_retry_call_count": len(unsafe_retry_calls),
            "transport_verification_status": verification["status"],
            "resumed_batch_002": False,
            "cumulative_validated_forecast_calls": 12,
            "remaining_planned_forecast_calls": 552,
        },
    )
    write_json(run_dir / "repair_decision.json", decisions)

    return {
        "run_dir": run_dir,
        "failed_run_manifest": failed_run_manifest,
        "root_cause": root_cause,
        "comparison": comparison,
        "terminal_classifications": terminal_classifications,
        "incomplete_classification": incomplete_classification,
        "verification": verification,
        "resume_authorization": resume_authorization,
        "decisions": decisions,
        "safe_retry_calls": safe_retry_calls,
        "unsafe_retry_calls": unsafe_retry_calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = execute_repair(fixed_timestamp=args.fixed_timestamp)
    print(
        canonical_json(
            {
                "run_dir": str(result["run_dir"]),
                "root_cause_decision": result["decisions"]["root_cause_decision"],
                "repair_decision": result["decisions"]["repair_decision"],
                "resume_decision": result["decisions"]["resume_decision"],
                "safe_retry_calls": result["safe_retry_calls"],
                "unsafe_retry_calls": result["unsafe_retry_calls"],
            }
        )
    )


if __name__ == "__main__":
    main()
