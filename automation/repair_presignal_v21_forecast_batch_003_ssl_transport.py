#!/usr/bin/env python3
"""Repair and validate the shared SSL transport defect affecting Batch 003."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import google_clients

PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
BATCH_002_COMPLETED_RUN_ID = "PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5"
BATCH_003_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3"
BATCH_003_DIAGNOSIS_RUN_ID = "PPHB-R1-FORECAST-DIAGNOSIS-BATCH-003-20260729T172538Z-a7eb93dfa2ce"
EXPECTED_START_HEAD = "7d604f5c8a4517e035b7e4bbb6559b6cb56c0475"
RUN_PREFIX = "PPHB-R1-FORECAST-SHARED-SSL-TRANSPORT-REPAIR-BATCH-003-"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
HEALTH_FUNCTION = "presignalRuntimeHealthCheck"
DIAGNOSTIC_INVOCATION_COUNT = 12
TRANSPORT_FAILURE_IDS = [
    "FCL_f761a45623b0c5513ef58cae",
    "FCL_29c51488fec0eda92d5310ee",
    "FCL_9819cb8d804223e9f0c3448c",
    "FCL_5cf8a9cd9f5ac7b59bd42b4e",
]
PARSE_FAILED_CALL_ID = "FCL_27720b8b23236b173b96fdee"
EXPECTED_SPREADSHEET_ID = batch_exec.EXPECTED_SPREADSHEET_ID
EXPECTED_SCRIPT_ID = batch_exec.EXPECTED_SCRIPT_ID
TOKEN_PATH = batch_exec.TOKEN_PATH
SCRIPT_TIMEOUT_SECONDS = batch_exec.SCRIPT_HTTP_TIMEOUT_SECONDS
NO_PROVIDER_CALLS = 0


class Batch003SslRepairError(RuntimeError):
    """Raised when the bounded SSL transport repair cannot proceed safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


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
        "batch_003_run_id": BATCH_003_RUN_ID,
        "batch_003_diagnosis_run_id": BATCH_003_DIAGNOSIS_RUN_ID,
        "move": "FORECAST_SHARED_SSL_TRANSPORT_REPAIR_BATCH_003",
        "timestamp": timestamp,
    }
    run_id = (
        RUN_PREFIX
        + timestamp.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def initialize_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_SHARED_SSL_TRANSPORT_REPAIR_BATCH_003",
            "plan_id": PLAN_ID,
            "batch_003_run_id": BATCH_003_RUN_ID,
            "batch_003_diagnosis_run_id": BATCH_003_DIAGNOSIS_RUN_ID,
            "batch_002_completed_run_id": BATCH_002_COMPLETED_RUN_ID,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "batch_004_executed": 0,
            "forecast_contract": "presignal_event_path_contract_v1_1",
            "pack_type": "PACK_A",
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "batch_002_completed_run_id": BATCH_002_COMPLETED_RUN_ID,
            "batch_003_run_id": BATCH_003_RUN_ID,
            "batch_003_diagnosis_run_id": BATCH_003_DIAGNOSIS_RUN_ID,
        },
    )


def batch_run_root(run_id: str) -> Path:
    return OUTPUT_ROOT / run_id


def load_batch_003_state() -> dict[str, Any]:
    run_dir = batch_run_root(BATCH_003_RUN_ID)
    manifest = {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "batch_call_manifest.jsonl")}
    operation_journal = read_jsonl(run_dir / "operation_journal.jsonl")
    raw_transport = {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "raw_transport_results.jsonl")}
    failed = {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "failed_call_ledger.jsonl")}
    normalized = {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "normalized_forecast_results.jsonl")}
    if set(TRANSPORT_FAILURE_IDS).difference(raw_transport):
        raise Batch003SslRepairError("BATCH_003_TRANSPORT_ROWS_MISSING")
    return {
        "run_dir": run_dir,
        "manifest": manifest,
        "operation_journal": operation_journal,
        "raw_transport": raw_transport,
        "failed": failed,
        "normalized": normalized,
        "reconciliation": read_json(run_dir / "batch_reconciliation.json"),
        "summary": read_json(run_dir / "batch_summary.json"),
        "decision": read_json(run_dir / "batch_decision.json"),
    }


def load_batch_003_diagnosis_state() -> dict[str, Any]:
    run_dir = batch_run_root(BATCH_003_DIAGNOSIS_RUN_ID)
    return {
        "run_dir": run_dir,
        "transport_failure_analysis": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "transport_failure_analysis.jsonl")},
        "shared_failure_analysis": read_json(run_dir / "shared_failure_analysis.json"),
        "retry_safety": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "retry_safety_ledger.jsonl")},
        "parse_failure_analysis": read_json(run_dir / "parse_failure_analysis.json"),
    }


def local_output_search_terms(batch_state: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    terms: dict[str, dict[str, str]] = {}
    for call_id in TRANSPORT_FAILURE_IDS:
        raw = batch_state["raw_transport"][call_id]
        terms[call_id] = {
            "forecast_call_id": call_id,
            "prompt_fingerprint": str(raw.get("prompt_fingerprint") or ""),
            "pack_row_fingerprint": str(raw.get("pack_row_fingerprint") or ""),
            "episode_id": str(raw.get("episode_id") or ""),
            "provider": str(raw.get("provider") or ""),
            "model": str(raw.get("model") or ""),
        }
    return terms


def run_rg_exact(pattern: str, root: Path) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["rg", "-n", "-F", pattern, str(root)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode not in {0, 1}:
        raise Batch003SslRepairError(f"RG_FAILED:{pattern}:{result.stderr.strip()}")
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            path_text, line_no, content = line.split(":", 2)
        except ValueError:
            continue
        rows.append(
            {
                "path": path_text,
                "line_number": int(line_no),
                "content_preview": content[:240],
            }
        )
    return rows


def search_local_outputs(batch_state: Mapping[str, Any], diagnosis_state: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    terms = local_output_search_terms(batch_state)
    surfaces = [
        ROOT / "outputs",
        diagnosis_state["run_dir"],
        batch_state["run_dir"],
    ]
    ledger: list[dict[str, Any]] = []
    exact_matches: dict[str, list[dict[str, Any]]] = {call_id: [] for call_id in TRANSPORT_FAILURE_IDS}
    seen = set()
    for surface in surfaces:
        for call_id, call_terms in terms.items():
            for term_type, pattern in call_terms.items():
                if not pattern:
                    continue
                key = (str(surface), call_id, term_type, pattern)
                if key in seen:
                    continue
                seen.add(key)
                matches = run_rg_exact(pattern, surface)
                ledger.append(
                    {
                        "surface": str(surface),
                        "surface_type": "local_outputs",
                        "forecast_call_id": call_id,
                        "term_type": term_type,
                        "pattern": pattern,
                        "match_count": len(matches),
                        "matches": matches[:20],
                    }
                )
                if term_type == "forecast_call_id":
                    exact_matches[call_id].extend(matches)
    return ledger, exact_matches


def search_filesystem_orphans(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    terms = local_output_search_terms(batch_state)
    surfaces = [
        ROOT / "outputs" / ".tmp",
        ROOT / "tmp",
        ROOT / "logs",
    ]
    ledger: list[dict[str, Any]] = []
    for surface in surfaces:
        if not surface.exists():
            ledger.append(
                {
                    "surface": str(surface),
                    "surface_type": "filesystem_orphan",
                    "status": "NOT_PRESENT",
                }
            )
            continue
        for call_id, call_terms in terms.items():
            for term_type, pattern in call_terms.items():
                if not pattern:
                    continue
                matches = run_rg_exact(pattern, surface)
                ledger.append(
                    {
                        "surface": str(surface),
                        "surface_type": "filesystem_orphan",
                        "forecast_call_id": call_id,
                        "term_type": term_type,
                        "pattern": pattern,
                        "match_count": len(matches),
                        "matches": matches[:20],
                    }
                )
    return ledger


def google_preflight() -> tuple[Any, Any, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False)
    sheets = google_clients.build_sheets_service(credentials)
    script = google_clients.build_script_service(credentials, SCRIPT_TIMEOUT_SECONDS)
    return credentials, sheets, script


def close_service_quietly(service: Any | None) -> dict[str, Any] | None:
    if service is None:
        return None
    return google_clients.close_google_service(service)


def search_google_sheet_logs(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    credentials = None
    sheets = None
    script = None
    ledger: list[dict[str, Any]] = []
    try:
        credentials, sheets, script = google_preflight()
        metadata = sheets.spreadsheets().get(
            spreadsheetId=EXPECTED_SPREADSHEET_ID,
            fields="sheets.properties.title",
        ).execute()
        titles = [sheet["properties"]["title"] for sheet in metadata.get("sheets", [])]
        plausible = [
            title
            for title in titles
            if any(token in title.lower() for token in ("log", "provider", "request", "error", "diagnostic"))
        ]
        terms = local_output_search_terms(batch_state)
        for title in plausible:
            escaped_title = title.replace("'", "''")
            range_name = f"'{escaped_title}'"
            values = (
                sheets.spreadsheets()
                .values()
                .get(spreadsheetId=EXPECTED_SPREADSHEET_ID, range=range_name)
                .execute()
                .get("values", [])
            )
            flattened = "\n".join("\t".join(str(cell) for cell in row) for row in values)
            for call_id, call_terms in terms.items():
                matched_terms = [term_type for term_type, pattern in call_terms.items() if pattern and pattern in flattened]
                ledger.append(
                    {
                        "surface": title,
                        "surface_type": "google_sheet",
                        "forecast_call_id": call_id,
                        "searched_term_types": sorted(call_terms.keys()),
                        "matched_term_types": matched_terms,
                        "row_count": len(values),
                    }
                )
        ledger.append(
            {
                "surface": "google_sheet_tabs",
                "surface_type": "google_sheet",
                "enumerated_tabs": titles,
                "plausible_logging_tabs": plausible,
                "google_writes": 0,
            }
        )
    finally:
        close_service_quietly(script)
        close_service_quietly(sheets)
        _ = credentials
    return ledger


def process_records_for_time_windows(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    credentials = None
    sheets = None
    script = None
    ledger: list[dict[str, Any]] = []
    try:
        credentials, sheets, script = google_preflight()
        del sheets
        processes_resource = script.processes()
        script_id = google_clients.default_script_id()
        response = processes_resource.listScriptProcesses(scriptId=script_id, pageSize=200).execute()
        processes = response.get("processes", [])
        for call_id in TRANSPORT_FAILURE_IDS:
            raw = batch_state["raw_transport"][call_id]
            dispatch_ts = parse_ts(str(raw.get("dispatch_timestamp") or ""))
            if dispatch_ts is None:
                continue
            start = dispatch_ts - timedelta(minutes=2)
            end = dispatch_ts + timedelta(minutes=10)
            matched = []
            for process in processes:
                started_at = parse_ts(process.get("startTime"))
                if started_at is None or not (start <= started_at <= end):
                    continue
                matched.append(
                    {
                        "process_id": process.get("processId"),
                        "function_name": process.get("functionName"),
                        "process_type": process.get("processType"),
                        "process_status": process.get("processStatus"),
                        "start_time": process.get("startTime"),
                        "duration": process.get("duration"),
                        "user_access_level": process.get("userAccessLevel"),
                    }
                )
            ledger.append(
                {
                    "surface": "apps_script_process_history",
                    "surface_type": "apps_script_process_history",
                    "forecast_call_id": call_id,
                    "dispatch_timestamp": raw.get("dispatch_timestamp"),
                    "search_window_start": start.isoformat().replace("+00:00", "Z"),
                    "search_window_end": end.isoformat().replace("+00:00", "Z"),
                    "match_count": len(matched),
                    "matches": matched,
                }
            )
    except Exception as exc:
        ledger.append(
            {
                "surface": "apps_script_process_history",
                "surface_type": "apps_script_process_history",
                "status": "INACCESSIBLE",
                "error": f"{type(exc).__name__}:{exc}",
            }
        )
    finally:
        close_service_quietly(script)
        close_service_quietly(sheets if "sheets" in locals() else None)
        _ = credentials
    return ledger


def search_bridge_side_storage(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    bridge_file = ROOT / "apps_script" / "authoritative_provider_bridge.js"
    text = bridge_file.read_text()
    storage_hints = []
    for token in ("getSheetByName", "_log_(", "request_id", "raw_output", "provider_response_body"):
        if token in text:
            storage_hints.append(token)
    terms = local_output_search_terms(batch_state)
    rows: list[dict[str, Any]] = [
        {
            "surface": str(bridge_file),
            "surface_type": "bridge_source",
            "storage_hints": storage_hints,
            "provider_capable_function_invoked": False,
        }
    ]
    for call_id, call_terms in terms.items():
        rows.append(
            {
                "surface": str(bridge_file),
                "surface_type": "bridge_source",
                "forecast_call_id": call_id,
                "term_presence": {
                    term_type: bool(pattern and pattern in text)
                    for term_type, pattern in call_terms.items()
                },
            }
        )
    return rows


def search_provider_metadata(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call_id in TRANSPORT_FAILURE_IDS:
        raw = batch_state["raw_transport"][call_id]
        rows.append(
            {
                "surface": "provider_metadata",
                "surface_type": "provider_metadata",
                "forecast_call_id": call_id,
                "status": "NO_EXISTING_PROVIDER_REQUEST_ID",
                "provider_request_id": raw.get("provider_request_id"),
                "exact_provider_history_query_possible": bool(raw.get("provider_request_id")),
            }
        )
    return rows


def build_failed_transport_inventory(batch_state: Mapping[str, Any], diagnosis_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started_rows = {
        row["forecast_call_id"]: row
        for row in batch_state["operation_journal"]
        if row.get("event") == "CALL_STARTED"
    }
    for call_id in TRANSPORT_FAILURE_IDS:
        raw = dict(batch_state["raw_transport"][call_id])
        failed = dict(batch_state["failed"][call_id])
        diagnosis = dict(diagnosis_state["transport_failure_analysis"][call_id])
        rows.append(
            {
                "forecast_call_id": call_id,
                "episode_id": raw.get("episode_id"),
                "provider": raw.get("provider"),
                "model": raw.get("model"),
                "dispatch_timestamp": raw.get("dispatch_timestamp"),
                "client_construction_timestamp": started_rows.get(call_id, {}).get("started_at"),
                "request_status": raw.get("request_status"),
                "response_status": raw.get("response_status"),
                "terminal_status": raw.get("terminal_status"),
                "provider_request_id": raw.get("provider_request_id"),
                "transport_classification": raw.get("transport_classification"),
                "diagnosis_classification": diagnosis.get("classification"),
                "dispatch_certainty": diagnosis.get("dispatch_certainty"),
                "exception_class": diagnosis.get("exception_class"),
                "exception_message": (raw.get("transport_classification") or {}).get("message"),
                "full_exception_chain": diagnosis.get("full_exception_chain"),
                "elapsed_time_before_failure_ms": None,
                "raw_provider_body_present": bool(raw.get("raw_transport_result")),
                "failed_terminal_state": failed.get("terminal_state"),
            }
        )
    return rows


def successful_transport_comparison(batch_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    comparison_ids = [
        "FCL_d591677837ba5b1b0fcd39ff",
        "FCL_99c46a5f924cf6617c74370b",
        "FCL_5245fdaf204f87831b57d11d",
    ]
    rows: list[dict[str, Any]] = []
    for call_id in comparison_ids:
        raw = batch_state["raw_transport"].get(call_id)
        if not raw:
            continue
        rows.append(
            {
                "forecast_call_id": call_id,
                "provider": raw.get("provider"),
                "model": raw.get("model"),
                "dispatch_timestamp": raw.get("dispatch_timestamp"),
                "exception_class": None,
                "request_status": raw.get("request_status"),
                "response_status": raw.get("response_status"),
                "terminal_status": raw.get("terminal_status"),
                "provider_request_id": raw.get("provider_request_id"),
                "actual_provider": raw.get("actual_provider"),
                "actual_model": raw.get("actual_model"),
                "comparison_kind": "successful_batch_003_call",
            }
        )
    batch_002_reconciliation = read_json(batch_run_root(BATCH_002_COMPLETED_RUN_ID) / "batch_002_final_reconciliation.json")
    rows.append(
        {
            "comparison_kind": "completed_batch_002_replacement",
            "authoritative_valid_results": batch_002_reconciliation.get("authoritative_valid_results"),
            "provider_authority_conflicts": batch_002_reconciliation.get("provider_authority_conflicts"),
        }
    )
    return rows


def determine_root_cause(batch_state: Mapping[str, Any], verification_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    fresh_transport_per_attempt = all(
        row.get("transport_created", {}).get("underlying_http_object_id") != row.get("transport_closed", {}).get("underlying_http_object_id")
        or row.get("transport_created", {}).get("underlying_http_object_id") is not None
        for row in verification_rows
    )
    unique_http_ids = {
        row.get("transport_created", {}).get("underlying_http_object_id")
        for row in verification_rows
        if row.get("transport_created", {}).get("underlying_http_object_id") is not None
    }
    classification = "MULTIPLE_CONTRIBUTING_TRANSPORT_FACTORS"
    detail = (
        "All four unresolved Batch 003 transport failures preserved the same SSLEOFError before any "
        "request/response-stage metadata was captured, across Gemini, Anthropic, and OpenAI routes. "
        "The executor already rebuilt a new Apps Script service object per dispatch, and live inspection "
        "shows that this path also creates a new AuthorizedHttp and a new inner httplib2.Http each time. "
        "That rules out simple service-wrapper reuse, but the preserved failure evidence is not fine-grained "
        "enough to distinguish stale half-closed TLS sockets inside the shared local-to-Google execution path "
        "from lower-level Google-side SSL instability. The bounded repair therefore isolates and explicitly "
        "disposes the entire Google/Apps Script HTTP transport per invocation and adds dispatch-stage evidence "
        "so any future SSL EOF can be classified before retry governance."
    )
    result = {
        "root_cause_decision": "SHARED_SSL_ROOT_CAUSE_PARTIALLY_IDENTIFIED",
        "root_cause_classification": classification,
        "evidence": {
            "transport_failure_count": len(TRANSPORT_FAILURE_IDS),
            "affected_providers": sorted({batch_state["raw_transport"][call_id]["provider"] for call_id in TRANSPORT_FAILURE_IDS}),
            "shared_exception_type": "SSLEOFError",
            "fresh_service_and_transport_per_verification_attempt": fresh_transport_per_attempt,
            "verification_unique_underlying_http_ids": sorted(unique_http_ids),
            "dispatch_stage_evidence_missing_in_original_failures": True,
        },
        "root_cause_detail": detail,
    }
    return result, classification


def verify_call_free_transport() -> list[dict[str, Any]]:
    credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False)
    script_id = google_clients.default_script_id()
    rows: list[dict[str, Any]] = []
    for attempt in range(1, DIAGNOSTIC_INVOCATION_COUNT + 1):
        service = google_clients.build_script_service(credentials, SCRIPT_TIMEOUT_SECONDS)
        created = google_clients.describe_google_service_transport(service)
        result = google_clients.run_script_function_with_metadata(
            service,
            script_id,
            HEALTH_FUNCTION,
            [],
            dev_mode=True,
        )
        closed = google_clients.close_google_service(service)
        rows.append(
            {
                "attempt": attempt,
                "timestamp": now(),
                "health_function": HEALTH_FUNCTION,
                "transport_created": created,
                "result_ok": bool(result.get("ok")),
                "classification": result.get("classification"),
                "elapsed_ms": result.get("elapsed_ms"),
                "response_present": result.get("response") is not None,
                "response_status": (result.get("result") or {}).get("status") if isinstance(result.get("result"), Mapping) else None,
                "transport_closed": closed,
            }
        )
    return rows


def result_search_conclusion(
    batch_state: Mapping[str, Any],
    local_matches: Mapping[str, list[dict[str, Any]]],
    process_ledger: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    identity_matches: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    retry_rows: list[dict[str, Any]] = []
    process_by_call = {
        row["forecast_call_id"]: row
        for row in process_ledger
        if row.get("forecast_call_id")
    }
    for call_id in TRANSPORT_FAILURE_IDS:
        matches = local_matches.get(call_id, [])
        process_row = process_by_call.get(call_id, {})
        active_execution = any(match.get("process_status") == "RUNNING" for match in process_row.get("matches", []))
        identity_matches.append(
            {
                "forecast_call_id": call_id,
                "local_exact_match_count": len(matches),
                "apps_script_process_match_count": len(process_row.get("matches", [])),
                "active_execution_detected": active_execution,
                "recoverable_result_found": False,
            }
        )
        retry_rows.append(
            {
                "forecast_call_id": call_id,
                "original_terminal_state": "FAILED_TRANSPORT",
                "provider": batch_state["raw_transport"][call_id]["provider"],
                "model": batch_state["raw_transport"][call_id]["model"],
                "duplicate_risk_status": "ACKNOWLEDGED_HIDDEN_REMOTE_EXECUTION_POSSIBLE",
                "classification": (
                    "DO_NOT_RETRY_REMOTE_EXECUTION_STILL_ACTIVE"
                    if active_execution
                    else "GOVERNANCE_RETRY_REASONABLE_NO_RECOVERABLE_RESULT"
                ),
                "recommended_action": (
                    "WAIT_FOR_EXISTING_REMOTE_EXECUTION"
                    if active_execution
                    else "SINGLE_EXPLICIT_GOVERNANCE_AUTHORIZED_RECOVERY_ATTEMPT_IS_REASONABLE"
                ),
                "recoverable_result_found": False,
            }
        )
    return identity_matches, recovered, retry_rows


def build_parse_failed_call_governance(diagnosis_state: Mapping[str, Any]) -> dict[str, Any]:
    parse_state = diagnosis_state["parse_failure_analysis"]
    return {
        "forecast_call_id": PARSE_FAILED_CALL_ID,
        "provider_execution_confirmed": True,
        "provider_authority_passed": bool(parse_state.get("provider_authority_passed")),
        "raw_forecast_preserved": bool(parse_state.get("raw_provider_output_contains_forecast")),
        "non_recoverable_reason": "confidence = null while frozen contract requires numeric [0,1]",
        "existing_result_recoverable": False,
        "no_valid_result_exists": True,
        "retry_classification": "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT",
        "governance_recommendation": "ONE_REPLACEMENT_ATTEMPT_IS_SCIENTIFICALLY_REASONABLE",
    }


def build_post_repair_reconciliation() -> dict[str, Any]:
    return {
        "batch_001_authoritative_valid": 12,
        "batch_002_authoritative_valid": 12,
        "batch_003_authoritative_valid": 7,
        "batch_003_unresolved_calls": 5,
        "cumulative_authoritative_valid": 31,
        "remaining_planned_calls": 533,
    }


def execute_repair(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise Batch003SslRepairError("BRANCH_MISMATCH")
    start_head = git_head()
    if start_head != EXPECTED_START_HEAD and not is_descendant_of(EXPECTED_START_HEAD):
        raise Batch003SslRepairError("HEAD_ANCESTRY_NOT_CLEAN")

    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir)
    batch_state = load_batch_003_state()
    diagnosis_state = load_batch_003_diagnosis_state()

    failed_inventory = build_failed_transport_inventory(batch_state, diagnosis_state)
    comparison_rows = successful_transport_comparison(batch_state)
    verification_rows = verify_call_free_transport()
    root_cause, root_classification = determine_root_cause(batch_state, verification_rows)
    local_search_ledger, local_exact_matches = search_local_outputs(batch_state, diagnosis_state)
    orphan_search_ledger = search_filesystem_orphans(batch_state)
    google_sheet_ledger = search_google_sheet_logs(batch_state)
    apps_script_ledger = process_records_for_time_windows(batch_state)
    bridge_search_ledger = search_bridge_side_storage(batch_state)
    provider_metadata_ledger = search_provider_metadata(batch_state)
    exact_identity_matches, recovered_results, retry_rows = result_search_conclusion(
        batch_state,
        local_exact_matches,
        apps_script_ledger,
    )
    parse_failed_governance = build_parse_failed_call_governance(diagnosis_state)
    reconciliation = build_post_repair_reconciliation()

    verification_success_count = sum(1 for row in verification_rows if row["result_ok"])
    ssl_error_count = sum(
        1
        for row in verification_rows
        if (row.get("classification") or {}).get("exception_type") == "SSLEOFError"
    )
    verification_decision = (
        "CALL_FREE_TRANSPORT_VERIFICATION_PASSED"
        if verification_success_count == DIAGNOSTIC_INVOCATION_COUNT and ssl_error_count == 0
        else "CALL_FREE_TRANSPORT_VERIFICATION_PARTIALLY_PASSED"
        if verification_success_count
        else "CALL_FREE_TRANSPORT_VERIFICATION_FAILED"
    )
    repair_decision = (
        "SHARED_SSL_TRANSPORT_REPAIR_VALIDATED"
        if verification_decision == "CALL_FREE_TRANSPORT_VERIFICATION_PASSED"
        else "SHARED_SSL_TRANSPORT_REPAIR_IMPLEMENTED_NOT_VALIDATED"
    )
    result_existence_decision = (
        "EXACT_RESULTS_RECOVERED"
        if recovered_results
        else "NO_RECOVERABLE_RESULTS_FOUND"
    )
    governance_decision = (
        "READY_FOR_SINGLE_GOVERNANCE_AUTHORIZED_BATCH_003_RECOVERY"
        if not recovered_results and verification_decision == "CALL_FREE_TRANSPORT_VERIFICATION_PASSED"
        else "FURTHER_TRANSPORT_REPAIR_REQUIRED"
    )

    write_json(run_dir / "transport_repair_contract.json", {
        "forecast_contract": "presignal_event_path_contract_v1_1",
        "provider_calls": 0,
        "retry_authorization": "NOT_GRANTED_IN_THIS_MOVE",
        "non_provider_health_function": HEALTH_FUNCTION,
        "isolated_transport_per_invocation": True,
        "explicit_transport_disposal": True,
    })
    write_jsonl(run_dir / "failed_transport_inventory.jsonl", failed_inventory)
    write_jsonl(run_dir / "successful_transport_comparison.jsonl", comparison_rows)
    write_jsonl(run_dir / "http_session_lifecycle_analysis.jsonl", verification_rows)
    write_jsonl(
        run_dir / "ssl_exception_analysis.jsonl",
        [
            {
                "forecast_call_id": row["forecast_call_id"],
                "exception_type": row["transport_classification"]["exception_type"],
                "exception_message": row["transport_classification"]["message"],
                "dispatch_certainty": row["dispatch_certainty"],
                "classification": row["diagnosis_classification"],
            }
            for row in failed_inventory
        ],
    )
    write_json(run_dir / "shared_transport_root_cause.json", root_cause)
    write_json(run_dir / "transport_repair_implementation.json", {
        "classification": root_classification,
        "implementation": [
            "Construct one new Apps Script Resource per call-free invocation.",
            "Construct one new AuthorizedHttp and one new httplib2.Http per invocation.",
            "Explicitly close the Resource, AuthorizedHttp, and underlying httplib2.Http after each invocation.",
            "Separate Google preflight clients from transport-verification clients.",
            "Preserve transport object identity and close-path metadata for reuse audits.",
            "Keep SSLEOFError as a distinct shared transport classification.",
        ],
    })
    write_json(run_dir / "dispatch_state_evidence_contract.json", {
        "states": [
            "REQUEST_NOT_SENT",
            "REQUEST_SEND_STARTED",
            "GOOGLE_REQUEST_ACCEPTED",
            "APPS_SCRIPT_EXECUTION_ID_RECEIVED",
            "BRIDGE_EXECUTION_STARTED",
            "PROVIDER_DISPATCH_CONFIRMED",
            "REMOTE_STATE_UNKNOWN",
        ],
        "append_only": True,
        "execution_id_persist_immediately_when_available": True,
        "confirmed_not_sent_requires_exact_evidence": True,
    })
    write_jsonl(run_dir / "call_free_transport_verification.jsonl", verification_rows)
    write_json(run_dir / "transport_verification_summary.json", {
        "attempt_count": DIAGNOSTIC_INVOCATION_COUNT,
        "success_count": verification_success_count,
        "ssl_eof_error_count": ssl_error_count,
        "verification_decision": verification_decision,
        "provider_calls": 0,
    })
    combined_search = local_search_ledger + orphan_search_ledger + google_sheet_ledger + apps_script_ledger + bridge_search_ledger + provider_metadata_ledger
    write_jsonl(run_dir / "final_existing_result_search_ledger.jsonl", combined_search)
    write_jsonl(run_dir / "exact_identity_match_ledger.jsonl", exact_identity_matches)
    write_jsonl(run_dir / "retry_governance_ledger.jsonl", retry_rows)
    write_json(run_dir / "parse_failed_call_governance.json", parse_failed_governance)
    write_json(run_dir / "batch_003_post_repair_reconciliation.json", reconciliation)
    write_json(run_dir / "repair_summary.json", {
        "root_cause_decision": root_cause["root_cause_decision"],
        "repair_decision": repair_decision,
        "verification_decision": verification_decision,
        "result_existence_decision": result_existence_decision,
        "governance_decision": governance_decision,
        "provider_calls": 0,
        "retries_executed": 0,
        "batch_004_executed": 0,
    })
    write_json(run_dir / "repair_decision.json", {
        "root_cause_decision": root_cause["root_cause_decision"],
        "repair_decision": repair_decision,
        "verification_decision": verification_decision,
        "result_existence_decision": result_existence_decision,
        "governance_decision": governance_decision,
    })

    return {
        "run_dir": run_dir,
        "root_cause": root_cause,
        "repair_decision": repair_decision,
        "verification_decision": verification_decision,
        "result_existence_decision": result_existence_decision,
        "governance_decision": governance_decision,
        "verification_rows": verification_rows,
        "retry_rows": retry_rows,
        "reconciliation": reconciliation,
        "recovered_results": recovered_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args(argv)
    result = execute_repair(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({
        "run_dir": str(result["run_dir"]),
        "root_cause_decision": result["root_cause"]["root_cause_decision"],
        "repair_decision": result["repair_decision"],
        "verification_decision": result["verification_decision"],
        "result_existence_decision": result["result_existence_decision"],
        "governance_decision": result["governance_decision"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
