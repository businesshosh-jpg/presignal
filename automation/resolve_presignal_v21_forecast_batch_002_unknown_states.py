#!/usr/bin/env python3
"""Resolve the three unknown-state forecast calls from Batch 002 without dispatching providers."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch001
from automation import google_clients

PLAN_ID = batch001.PLAN_ID
FAILED_BATCH_002_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-002-20260729T133420Z-0469b99f5e03"
FAILED_COORDINATION_ID = "PPHB-R1-FORECAST-EXECUTION-BATCHES-002-003-20260729T133416Z-9675b262960c"
BLOCKED_COORDINATION_ID = "PPHB-R1-FORECAST-EXECUTION-BATCHES-002-003-20260729T131559Z-49bc327a5c29"
SUCCESSFUL_BATCH_001_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8"
TRANSPORT_REPAIR_ID = "PPHB-R1-FORECAST-TRANSPORT-REPAIR-BATCH-002-20260729T145855Z-14b086004306"
EXPECTED_HEAD = "b07a2543510f85463805a09f062e441556e6023e"
PACK_TYPE = "PACK_A"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
OUTPUT_ROOT = batch001.OUTPUT_ROOT
RUN_PREFIX = "PPHB-R1-FORECAST-UNKNOWN-STATE-RESOLUTION-BATCH-002-"
UNKNOWN_CALL_IDS = [
    "FCL_befd6d6947490cc19f4754b9",
    "FCL_1ce38eb60f0865beca69bb31",
    "FCL_d72f741393a7643ea859edb8",
]
PROVEN_RETRY_SAFE_CALLS = [
    "FCL_1e7b6936b48bf931a7ed5e7d",
    "FCL_64c262f5f677009a4ce5c45a",
]
CALL_STATUS_ORDER = {cid: index for index, cid in enumerate(UNKNOWN_CALL_IDS)}
LOG_RANGE = "log!A:D"


class UnknownStateResolutionError(RuntimeError):
    """The audit failed closed."""


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
        "transport_repair_id": TRANSPORT_REPAIR_ID,
        "timestamp": timestamp,
    }
    run_id = RUN_PREFIX + timestamp.replace(":", "").replace("-", "") + "-" + hashlib.sha256(
        canonical_json(seed).encode("utf-8")
    ).hexdigest()[:12]
    return output_root / run_id


def bundle_for_batch_002() -> dict[str, Any]:
    return batch001.verified_batch_bundle(user_batch_label="FORECAST_BATCH_002", frozen_batch_id="FCB_PACK_A_002")


def extract_call_identities() -> dict[str, dict[str, Any]]:
    bundle = bundle_for_batch_002()
    identities: dict[str, dict[str, Any]] = {}
    for row in bundle["bundles"]:
        call = dict(row["call"])
        if call["forecast_call_id"] not in UNKNOWN_CALL_IDS:
            continue
        payload = batch001.step6.bridge_payload(
            row["pack_payload"],
            row["prompt_row"]["prompt_text"],
            run_id=FAILED_BATCH_002_ID,
            arm="BASELINE",
        )
        identities[call["forecast_call_id"]] = {
            "forecast_call_id": call["forecast_call_id"],
            "forecast_identity": payload["forecast_identity"],
            "episode_id": call["episode_id"],
            "provider": call["provider"],
            "model": call["model"],
            "source_session_id": call["source_session_id"],
            "execution_order": call["execution_order"],
            "pack_type": call["pack_type"],
            "pack_row_identity": call["pack_row_identity"],
            "pack_row_fingerprint": call["pack_row_fingerprint"],
            "pack_payload_input_fingerprint": call["pack_payload_input_fingerprint"],
            "prompt_text_fingerprint": row["prompt_fingerprint"]["prompt_text_fingerprint"],
            "prompt_context_fingerprint": row["prompt_fingerprint"]["prompt_context_fingerprint"],
            "historical_cutoff": row["prompt_row"]["historical_cutoff"],
        }
    if set(identities) != set(UNKNOWN_CALL_IDS):
        raise UnknownStateResolutionError("UNKNOWN_CALL_IDENTITY_SET_MISMATCH")
    return identities


def failed_batch_rows() -> dict[str, Any]:
    root = OUTPUT_ROOT / FAILED_BATCH_002_ID
    return {
        "run_manifest": read_json(root / "run_manifest.json"),
        "batch_call_manifest": read_jsonl(root / "batch_call_manifest.jsonl"),
        "operation_journal": read_jsonl(root / "operation_journal.jsonl"),
        "raw_transport_results": read_jsonl(root / "raw_transport_results.jsonl"),
        "raw_provider_outputs": read_jsonl(root / "raw_provider_outputs.jsonl"),
        "failed_call_ledger": read_jsonl(root / "failed_call_ledger.jsonl"),
    }


def local_lifecycle_rows(identities: Mapping[str, Mapping[str, Any]], failed_rows: Mapping[str, Any]) -> list[dict[str, Any]]:
    started_by_call = {
        row["forecast_call_id"]: row
        for row in failed_rows["operation_journal"]
        if row.get("event") == "CALL_STARTED" and row.get("forecast_call_id") in identities
    }
    transport_by_call = {
        row["forecast_call_id"]: row
        for row in failed_rows["raw_transport_results"]
        if row.get("forecast_call_id") in identities
    }
    provider_output_by_call = {
        row["forecast_call_id"]: row
        for row in failed_rows["raw_provider_outputs"]
        if row.get("forecast_call_id") in identities
    }
    failed_by_call = {
        row["forecast_call_id"]: row
        for row in failed_rows["failed_call_ledger"]
        if row.get("forecast_call_id") in identities
    }
    rows: list[dict[str, Any]] = []
    for call_id in UNKNOWN_CALL_IDS:
        identity = identities[call_id]
        started = started_by_call.get(call_id)
        transport = transport_by_call.get(call_id)
        provider_row = provider_output_by_call.get(call_id)
        failed = failed_by_call.get(call_id)
        classification = dict((transport or {}).get("transport_classification") or {})
        rows.append(
            {
                "forecast_call_id": call_id,
                "forecast_identity": identity["forecast_identity"],
                "episode_id": identity["episode_id"],
                "provider": identity["provider"],
                "model": identity["model"],
                "execution_order": identity["execution_order"],
                "authorized": True,
                "call_started_journaled": started is not None,
                "request_serialization_proven": transport is not None or started is not None,
                "google_api_request_initiation": transport is not None,
                "apps_script_execution_acceptance": classification.get("dispatch_certainty") == "CONFIRMED_RESPONSE",
                "apps_script_execution_id_created": None,
                "bridge_invocation_proven": classification.get("dispatch_certainty") == "CONFIRMED_RESPONSE",
                "provider_dispatch_proven": classification.get("dispatch_certainty") == "CONFIRMED_RESPONSE",
                "provider_response_proven": bool(provider_row and provider_row.get("raw_provider_output")),
                "bridge_response_proven": transport is not None,
                "apps_script_completion_proven": classification.get("dispatch_certainty") == "CONFIRMED_RESPONSE",
                "local_response_retrieval_proven": transport is not None,
                "raw_persistence_proven": transport is not None,
                "terminal_state_persisted": failed is not None,
                "started_at": started.get("started_at") if started else None,
                "dispatch_timestamp": transport.get("dispatch_timestamp") if transport else None,
                "completion_timestamp": transport.get("completion_timestamp") if transport else None,
                "transport_classification": classification if classification else None,
                "failed_terminal_state": failed.get("terminal_state") if failed else None,
                "failed_reason": failed.get("reason") if failed else None,
            }
        )
    return rows


def repo_search(identity: Mapping[str, Any]) -> dict[str, Any]:
    tokens = [
        identity["forecast_call_id"],
        identity["forecast_identity"],
        FAILED_BATCH_002_ID,
    ]
    cmd = ["rg", "-n", "-F"] + tokens + [
        "outputs",
        "automation",
        "apps_script",
        "-g",
        f"!outputs/presignal_v21_full_round_1_forecast_execution/{FAILED_BATCH_002_ID}/**",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    hits = [line for line in proc.stdout.splitlines() if line.strip()]
    exact_hits = []
    for line in hits:
        if identity["forecast_call_id"] in line or identity["forecast_identity"] in line:
            exact_hits.append(line)
    return {
        "forecast_call_id": identity["forecast_call_id"],
        "source": "LOCAL_REPO_EXACT_IDENTITY_SWEEP",
        "status": "MATCHES_FOUND" if exact_hits else "NO_MATCH",
        "exact_hits": exact_hits[:50],
    }


def fetch_log_rows(sheets_service: Any, spreadsheet_id: str) -> tuple[list[list[Any]], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        try:
            values = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=LOG_RANGE,
            ).execute().get("values", [])
            attempts.append({"attempt": attempt, "status": "PASSED", "row_count": len(values), "timestamp": now()})
            return values, attempts
        except HttpError as exc:
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "HTTP_ERROR",
                    "http_status": getattr(exc.resp, "status", None),
                    "message": str(exc),
                    "timestamp": now(),
                }
            )
            if attempt == 3:
                raise
            time.sleep(attempt)
    raise UnknownStateResolutionError("LOG_FETCH_UNREACHABLE")


def sheet_log_search(sheets_service: Any, spreadsheet_id: str, identities: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    values, attempts = fetch_log_rows(sheets_service, spreadsheet_id)
    rows: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for call_id in UNKNOWN_CALL_IDS:
        identity = identities[call_id]
        search_tokens = [
            identity["forecast_call_id"],
            identity["forecast_identity"],
            FAILED_BATCH_002_ID,
            identity["prompt_text_fingerprint"],
            identity["pack_row_fingerprint"],
            identity["episode_id"],
        ]
        exact_rows = []
        for row_number, row in enumerate(values[1:], start=2):
            text = " ".join(str(cell) for cell in row)
            if any(token in text for token in search_tokens):
                exact_rows.append({"row_number": row_number, "row": row})
        rows.append(
            {
                "forecast_call_id": call_id,
                "source": "GOOGLE_SHEET_LOG_EXACT_SEARCH",
                "status": "MATCH_FOUND" if exact_rows else "NO_MATCH",
                "search_tokens": search_tokens,
                "match_count": len(exact_rows),
            }
        )
        for match in exact_rows:
            matches.append(
                {
                    "forecast_call_id": call_id,
                    "source": "GOOGLE_SHEET_LOG_EXACT_SEARCH",
                    "row_number": match["row_number"],
                    "matched_on_exact_identifier": True,
                    "matched_fields": [token for token in search_tokens if token in " ".join(str(cell) for cell in match["row"])],
                    "record": match["row"],
                }
            )
    rows.append({"source": "GOOGLE_SHEET_LOG_FETCH_ATTEMPTS", "attempts": attempts, "range": LOG_RANGE})
    return rows, matches


def process_api_search(script_service: Any, script_id: str, identities: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    search_rows: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    queries = [
        ("LIST_SCRIPT_PROCESSES", lambda proc: proc.listScriptProcesses(scriptId=script_id, pageSize=25)),
        ("LIST_USER_PROCESSES", lambda proc: proc.list(userProcessFilter_scriptId=script_id, pageSize=25)),
    ]
    for label, builder in queries:
        try:
            response = builder(script_service.processes()).execute()
            search_rows.append(
                {
                    "source": label,
                    "status": "PASSED",
                    "response_keys": sorted(response.keys()),
                    "record_count": len(response.get("processes", [])),
                }
            )
            for process in response.get("processes", []):
                text = canonical_json(process)
                for call_id in UNKNOWN_CALL_IDS:
                    identity = identities[call_id]
                    exact_identifiers = [
                        identity["forecast_call_id"],
                        identity["forecast_identity"],
                        identity["prompt_text_fingerprint"],
                        identity["pack_row_fingerprint"],
                        identity["episode_id"],
                        identity["provider"],
                        identity["model"],
                    ]
                    matched = [token for token in exact_identifiers if token in text]
                    if matched:
                        matches.append(
                            {
                                "forecast_call_id": call_id,
                                "source": label,
                                "matched_on_exact_identifier": True,
                                "matched_fields": matched,
                                "record": process,
                            }
                        )
        except HttpError as exc:
            search_rows.append(
                {
                    "source": label,
                    "status": "HTTP_ERROR",
                    "http_status": getattr(exc.resp, "status", None),
                    "message": str(exc),
                }
            )
        except Exception as exc:
            search_rows.append({"source": label, "status": "ERROR", "exception_type": type(exc).__name__, "message": str(exc)})
    return search_rows, matches


def classify_calls(
    identities: Mapping[str, Mapping[str, Any]],
    local_rows: Mapping[str, Mapping[str, Any]],
    exact_matches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    match_by_call: dict[str, list[dict[str, Any]]] = {cid: [] for cid in UNKNOWN_CALL_IDS}
    for row in exact_matches:
        match_by_call.setdefault(row["forecast_call_id"], []).append(row)
    unknown_inventory: list[dict[str, Any]] = []
    retry_rows: list[dict[str, Any]] = []
    recovered_rows: list[dict[str, Any]] = []
    remote_terminal_failures: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    for call_id in UNKNOWN_CALL_IDS:
        identity = identities[call_id]
        local = local_rows[call_id]
        matches = match_by_call.get(call_id, [])
        if matches:
            classification = "IDENTITY_CONFLICT_REQUIRES_GOVERNANCE"
            reason = "EXACT_REMOTE_RECORD_MATCHED_BUT_REQUIRES_MANUAL_CONFLICT_REVIEW"
        else:
            classification = "REMOTE_EXECUTION_STATE_UNRESOLVED"
            reason = "NO_EXACT_REMOTE_RECORD_RECOVERED_AND_NO_NON_DISPATCH_PROOF"
        unknown_inventory.append(
            {
                **identity,
                "classification": classification,
                "classification_reason": reason,
                "local_transport_category": (local.get("transport_classification") or {}).get("category"),
                "local_dispatch_certainty": (local.get("transport_classification") or {}).get("dispatch_certainty"),
            }
        )
        retry_rows.append(
            {
                "forecast_call_id": call_id,
                "classification": classification,
                "retry_safe": False,
                "recommended_action": (
                    "MANUAL_GOVERNANCE_REVIEW_REQUIRED"
                    if classification == "REMOTE_EXECUTION_STATE_UNRESOLVED"
                    else "IDENTITY_CONFLICT_MANUAL_REVIEW_REQUIRED"
                ),
                "duplicate_risk": True,
            }
        )
        unresolved_rows.append(
            {
                "forecast_call_id": call_id,
                "forecast_identity": identity["forecast_identity"],
                "provider": identity["provider"],
                "model": identity["model"],
                "episode_id": identity["episode_id"],
                "classification": classification,
                "smallest_next_governance_option": (
                    "OPTION_A_CONTINUE_HOLD"
                    if classification == "REMOTE_EXECUTION_STATE_UNRESOLVED"
                    else "IDENTITY_CONFLICT_GOVERNANCE_REVIEW"
                ),
                "reason": reason,
            }
        )
    return unknown_inventory, retry_rows, recovered_rows, remote_terminal_failures, unresolved_rows


def governance_options(unresolved_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for row in unresolved_rows:
        call_id = row["forecast_call_id"]
        for option_id, consequences in (
            (
                "OPTION_A_CONTINUE_HOLD",
                [
                    "no duplicate risk",
                    "historical population remains incomplete",
                    "paired Pack A/Pack E population cannot be fully completed",
                ],
            ),
            (
                "OPTION_B_AUTHORIZE_RETRY_DESPITE_UNKNOWN_STATE",
                [
                    "population may be completed",
                    "duplicate hidden provider execution is possible",
                    "must preserve both executions if later discovered",
                    "requires explicit user authorization",
                ],
            ),
            (
                "OPTION_C_EXCLUDE_CALL",
                [
                    "population becomes intentionally incomplete",
                    "paired comparison coverage changes",
                    "material deviation from the frozen 564-call plan",
                    "requires DRIFTING WARNING and explicit authorization",
                ],
            ),
        ):
            options.append(
                {
                    "forecast_call_id": call_id,
                    "option_id": option_id,
                    "consequences": consequences,
                }
            )
    return options


def batch_reconciliation(
    unknown_inventory: list[Mapping[str, Any]],
    retry_rows: list[Mapping[str, Any]],
    recovered_rows: list[Mapping[str, Any]],
    unresolved_rows: list[Mapping[str, Any]],
    search_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    cls_counts: dict[str, int] = {}
    for row in unknown_inventory:
        cls_counts[row["classification"]] = cls_counts.get(row["classification"], 0) + 1
    return {
        "unknown_calls_audited": len(unknown_inventory),
        "classifications": cls_counts,
        "remote_results_recovered": len(recovered_rows),
        "retry_safe_calls": sum(1 for row in retry_rows if row["retry_safe"]),
        "retry_unsafe_calls": sum(1 for row in retry_rows if not row["retry_safe"]),
        "unresolved_calls": len(unresolved_rows),
        "process_api_scope_blocked": any(
            row.get("source") in {"LIST_SCRIPT_PROCESSES", "LIST_USER_PROCESSES"}
            and row.get("status") == "HTTP_ERROR"
            and row.get("http_status") == 403
            for row in search_rows
        ),
    }


def initialize_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_UNKNOWN_STATE_RESOLUTION_BATCH_002",
            "plan_id": PLAN_ID,
            "failed_batch_002_id": FAILED_BATCH_002_ID,
            "transport_repair_id": TRANSPORT_REPAIR_ID,
            "provider_calls_executed": 0,
            "batch_002_resumed": 0,
            "batch_003_executed": 0,
            "google_writes_executed": 0,
            "forecast_contract": FORECAST_CONTRACT,
            "pack_type": PACK_TYPE,
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
            "transport_repair_id": TRANSPORT_REPAIR_ID,
        },
    )


def execute_resolution(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise UnknownStateResolutionError("BRANCH_MISMATCH")
    head = git_head()
    if head != EXPECTED_HEAD and not is_descendant_of(EXPECTED_HEAD):
        raise UnknownStateResolutionError("HEAD_ANCESTRY_NOT_CLEAN")

    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir)

    identities = extract_call_identities()
    failed_rows = failed_batch_rows()
    local_rows_list = local_lifecycle_rows(identities, failed_rows)
    local_rows = {row["forecast_call_id"]: row for row in local_rows_list}

    credentials = google_clients.load_credentials(False, token_path=batch001.TOKEN_PATH, persist_refresh=False)
    sheets_service = google_clients.build_sheets_service(credentials)
    script_service = google_clients.build_script_service(credentials, 60)
    spreadsheet_id = failed_rows["run_manifest"]["google_preflight"]["resource_identity_result"]["spreadsheet_id"]
    script_id = failed_rows["run_manifest"]["google_preflight"]["resource_identity_result"]["script_id"]

    search_rows: list[dict[str, Any]] = []
    exact_matches: list[dict[str, Any]] = []

    repo_search_rows = [repo_search(identities[call_id]) for call_id in UNKNOWN_CALL_IDS]
    search_rows.extend(repo_search_rows)

    log_search_rows, log_matches = sheet_log_search(sheets_service, spreadsheet_id, identities)
    search_rows.extend(log_search_rows)
    exact_matches.extend(log_matches)

    process_search_rows, process_matches = process_api_search(script_service, script_id, identities)
    search_rows.extend(process_search_rows)
    exact_matches.extend(process_matches)

    (
        unknown_inventory,
        retry_rows,
        recovered_rows,
        remote_terminal_failures,
        unresolved_rows,
    ) = classify_calls(identities, local_rows, exact_matches)

    non_dispatch_rows: list[dict[str, Any]] = []
    governance_rows = governance_options(unresolved_rows)
    reconciliation = batch_reconciliation(unknown_inventory, retry_rows, recovered_rows, unresolved_rows, search_rows)

    write_jsonl(run_dir / "unknown_call_inventory.jsonl", unknown_inventory)
    write_jsonl(run_dir / "local_lifecycle_evidence.jsonl", local_rows_list)
    write_jsonl(run_dir / "remote_execution_search_ledger.jsonl", search_rows)
    write_jsonl(run_dir / "exact_identity_match_ledger.jsonl", exact_matches)
    write_jsonl(run_dir / "remote_result_recovery_ledger.jsonl", recovered_rows)
    write_jsonl(run_dir / "remote_terminal_failure_ledger.jsonl", remote_terminal_failures)
    write_jsonl(run_dir / "non_dispatch_proof_ledger.jsonl", non_dispatch_rows)
    write_jsonl(run_dir / "unresolved_remote_state_ledger.jsonl", unresolved_rows)
    write_jsonl(run_dir / "retry_eligibility_ledger.jsonl", retry_rows)
    write_jsonl(run_dir / "governance_option_analysis.jsonl", governance_rows)
    write_json(run_dir / "batch_002_recovery_reconciliation.json", reconciliation)

    decisions = {
        "unknown_state_resolution_status": "UNKNOWN_CALL_STATES_UNRESOLVED",
        "result_recovery_decision": "REMOTE_RESULT_RECOVERY_NOT_PROVEN",
        "retry_safety_decision": "SOME_BATCH_002_CALLS_RETRY_SAFE",
        "batch_002_next_decision": "GOVERNANCE_REVIEW_REQUIRED",
    }
    write_json(
        run_dir / "resolution_summary.json",
        {
            **reconciliation,
            "safe_retry_calls": sorted(PROVEN_RETRY_SAFE_CALLS),
            "unsafe_retry_calls": sorted(UNKNOWN_CALL_IDS),
        },
    )
    write_json(run_dir / "resolution_decision.json", decisions)

    return {
        "run_dir": run_dir,
        "identities": identities,
        "local_rows": local_rows_list,
        "search_rows": search_rows,
        "exact_matches": exact_matches,
        "recovered_rows": recovered_rows,
        "remote_terminal_failures": remote_terminal_failures,
        "non_dispatch_rows": non_dispatch_rows,
        "unresolved_rows": unresolved_rows,
        "retry_rows": retry_rows,
        "governance_rows": governance_rows,
        "reconciliation": reconciliation,
        "decisions": decisions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = execute_resolution(fixed_timestamp=args.fixed_timestamp)
    print(
        canonical_json(
            {
                "run_dir": str(result["run_dir"]),
                **result["decisions"],
            }
        )
    )


if __name__ == "__main__":
    main()
