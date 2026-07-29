#!/usr/bin/env python3
"""Final bounded existence verification for the three unknown-state Batch 002 forecast calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from automation import presignal_v21_event_path_contract_v1_1 as forecast_contract
from automation import resolve_presignal_v21_forecast_batch_002_unknown_states as baseline

PLAN_ID = batch001.PLAN_ID
FAILED_BATCH_002_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-002-20260729T133420Z-0469b99f5e03"
TRANSPORT_REPAIR_ID = "PPHB-R1-FORECAST-TRANSPORT-REPAIR-BATCH-002-20260729T145855Z-14b086004306"
UNKNOWN_STATE_RESOLUTION_ID = "PPHB-R1-FORECAST-UNKNOWN-STATE-RESOLUTION-BATCH-002-20260729T151816Z-f0c7e40b79bb"
EXPECTED_HEAD = "bf0b73b3772f655bf3683dcfd425dca43467830c"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
PACK_TYPE = "PACK_A"
OUTPUT_ROOT = batch001.OUTPUT_ROOT
RUN_PREFIX = "PPHB-R1-FORECAST-FINAL-EXISTENCE-VERIFICATION-BATCH-002-"
UNKNOWN_CALL_IDS = list(baseline.UNKNOWN_CALL_IDS)
SEARCH_WINDOW_BY_CALL = {
    "FCL_befd6d6947490cc19f4754b9": "2026-07-29T13:35:24Z",
    "FCL_1ce38eb60f0865beca69bb31": "2026-07-29T13:40:24Z",
    "FCL_d72f741393a7643ea859edb8": "2026-07-29T13:41:24Z",
}
PLANNING_ROOT = batch001.PLAN_ROOT
SPREADSHEET_ID = batch001.EXPECTED_SPREADSHEET_ID
SPREADSHEET_TITLE = batch001.EXPECTED_SPREADSHEET_TITLE
SCRIPT_ID = batch001.EXPECTED_SCRIPT_ID
PLAUSIBLE_LOG_SHEET_PATTERN = re.compile(r"(^|[_\s])(log|diag|exec|error|request|provider|bridge|raw)(s|ging|runs)?($|[_\s])", re.IGNORECASE)
TEMP_FILE_PATTERN = re.compile(r"(\.tmp$|\.partial$|\.json\.tmp$|\.jsonl\.tmp$|\.crash$|\.cache$|\.bak$|\.swp$)")
TEXT_FILE_PATTERN = re.compile(r"\.(json|jsonl|log|txt|tmp|partial|csv|md|js|py)$", re.IGNORECASE)
LIFECYCLE_STAGES = [
    "local_start_record",
    "local_request_serialization",
    "local_transport_initiation",
    "google_request_acceptance",
    "apps_script_execution_id",
    "bridge_invocation",
    "provider_dispatch",
    "provider_request_id",
    "provider_completion",
    "bridge_completion",
    "google_execution_completion",
    "local_response_retrieval",
    "raw_output_persistence",
    "terminal_state",
    "recoverable_result_existence",
]
PERMITTED_STAGE_VALUES = {
    "PROVEN_OCCURRED",
    "PROVEN_NOT_OCCURRED",
    "EVIDENCE_NOT_FOUND",
    "UNRESOLVED",
}


class FinalExistenceVerificationError(RuntimeError):
    """The final bounded verification failed closed."""


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
        "unknown_state_resolution_id": UNKNOWN_STATE_RESOLUTION_ID,
        "timestamp": timestamp,
    }
    run_id = RUN_PREFIX + timestamp.replace(":", "").replace("-", "") + "-" + hashlib.sha256(
        canonical_json(seed).encode("utf-8")
    ).hexdigest()[:12]
    return output_root / run_id


def identity_inventory() -> dict[str, dict[str, Any]]:
    identities = baseline.extract_call_identities()
    if set(identities) != set(UNKNOWN_CALL_IDS):
        raise FinalExistenceVerificationError("UNKNOWN_CALL_IDENTITY_SET_MISMATCH")
    return identities


def call_search_tokens(identity: Mapping[str, Any]) -> list[str]:
    return [
        identity["forecast_call_id"],
        identity["forecast_identity"],
        identity["prompt_text_fingerprint"],
        identity["prompt_context_fingerprint"],
        identity["pack_row_fingerprint"],
        identity["pack_payload_input_fingerprint"],
        identity["episode_id"],
        identity["provider"],
        identity["model"],
        identity["historical_cutoff"],
    ]


def primary_identity_tokens(identity: Mapping[str, Any]) -> list[str]:
    return [
        identity["forecast_call_id"],
        identity["forecast_identity"],
        identity["prompt_text_fingerprint"],
        identity["prompt_context_fingerprint"],
        identity["pack_row_fingerprint"],
        identity["pack_payload_input_fingerprint"],
    ]


def supportive_identity_tokens(identity: Mapping[str, Any]) -> list[str]:
    return [
        identity["episode_id"],
        identity["provider"],
        identity["model"],
        identity["historical_cutoff"],
    ]


def list_sheet_titles(sheets_service: Any, spreadsheet_id: str) -> list[str]:
    metadata = (
        sheets_service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="spreadsheetId,properties.title,sheets(properties(title,sheetType))")
        .execute()
    )
    if metadata.get("spreadsheetId") != spreadsheet_id:
        raise FinalExistenceVerificationError("SPREADSHEET_ID_MISMATCH")
    if metadata.get("properties", {}).get("title") != SPREADSHEET_TITLE:
        raise FinalExistenceVerificationError("SPREADSHEET_TITLE_MISMATCH")
    return [
        sheet["properties"]["title"]
        for sheet in metadata.get("sheets", [])
        if sheet.get("properties", {}).get("sheetType", "GRID") == "GRID"
    ]


def plausible_log_sheets(sheet_titles: Iterable[str]) -> list[str]:
    return [title for title in sheet_titles if PLAUSIBLE_LOG_SHEET_PATTERN.search(title)]


def safe_sheet_range(title: str) -> str:
    escaped = title.replace("'", "''")
    return f"'{escaped}'!A:Z"


def fetch_sheet_values(sheets_service: Any, spreadsheet_id: str, range_a1: str) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        try:
            values = (
                sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_a1)
                .execute()
                .get("values", [])
            )
            attempts.append({"attempt": attempt, "status": "PASSED", "row_count": len(values), "timestamp": now()})
            return {"status": "PASSED", "values": values, "attempts": attempts}
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
                return {"status": "HTTP_ERROR", "values": [], "attempts": attempts}
            time.sleep(attempt)
    return {"status": "UNREACHABLE", "values": [], "attempts": attempts}


def search_rows_for_tokens(rows: Iterable[Iterable[Any]], tokens: Iterable[str]) -> list[dict[str, Any]]:
    exact_matches: list[dict[str, Any]] = []
    token_list = [token for token in tokens if token]
    for row_number, row in enumerate(rows, start=1):
        row_text = " ".join(str(cell) for cell in row)
        matched = [token for token in token_list if token in row_text]
        if matched:
            exact_matches.append(
                {
                    "row_number": row_number,
                    "matched_fields": matched,
                    "row": list(row),
                }
            )
    return exact_matches


def reject_timestamp_only_candidate(candidate: Mapping[str, Any]) -> bool:
    matched_fields = set(candidate.get("matched_fields") or [])
    if not matched_fields:
        return False
    non_timestamp_fields = matched_fields - {"dispatch_timestamp_window"}
    return not non_timestamp_fields


def aggregate_provider_usage_is_exact_result(record: Mapping[str, Any]) -> bool:
    return bool(record.get("provider_request_id") and record.get("forecast_call_id"))


def rg_search(paths: list[str], tokens: list[str], extra_globs: list[str] | None = None) -> tuple[str, list[str]]:
    cmd = ["rg", "-n", "-F"]
    for token in tokens:
        cmd.extend(["-e", token])
    if extra_globs:
        for pattern in extra_globs:
            cmd.extend(["-g", pattern])
    cmd.extend(paths)
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    hits = [line for line in proc.stdout.splitlines() if line.strip()]
    status = "MATCHES_FOUND" if hits else "NO_MATCH"
    return status, hits


def local_output_search(identities: Mapping[str, Mapping[str, Any]], run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for call_id in UNKNOWN_CALL_IDS:
        identity = identities[call_id]
        tokens = primary_identity_tokens(identity)
        status, hits = rg_search(
            ["outputs"],
            tokens,
            extra_globs=[f"!outputs/presignal_v21_full_round_1_forecast_execution/{run_dir.name}/**"],
        )
        ledger.append(
            {
                "forecast_call_id": call_id,
                "search_scope": "outputs/",
                "searched_tokens": tokens,
                "status": status,
                "hit_count": len(hits),
            }
        )
        for hit in hits[:200]:
            match_fields = [token for token in tokens if token in hit]
            matches.append(
                {
                    "forecast_call_id": call_id,
                    "surface": "LOCAL_OUTPUT_SWEEP",
                    "path_hit": hit,
                    "matched_fields": match_fields,
                    "timestamp_only_rejected": reject_timestamp_only_candidate({"matched_fields": match_fields}),
                }
            )
    return ledger, matches


def filesystem_orphan_candidates() -> list[Path]:
    candidates: list[Path] = []
    for root_name in ("outputs", "automation", "apps_script", "local"):
        base = ROOT / root_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if TEMP_FILE_PATTERN.search(path.name) or (TEXT_FILE_PATTERN.search(path.name) and any(part.startswith(".") for part in path.parts)):
                candidates.append(path)
    return sorted(set(candidates))


def orphan_search(identities: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    candidates = filesystem_orphan_candidates()
    ledger.append(
        {
            "surface": "FILESYSTEM_ORPHAN_CANDIDATE_INVENTORY",
            "candidate_paths": [str(path) for path in candidates[:500]],
            "candidate_count": len(candidates),
        }
    )
    for path in candidates:
        try:
            text = path.read_text(errors="ignore")
        except Exception as exc:
            ledger.append({"surface": "FILESYSTEM_ORPHAN_READ_ERROR", "path": str(path), "exception_type": type(exc).__name__})
            continue
        for call_id in UNKNOWN_CALL_IDS:
            matched_fields = [token for token in primary_identity_tokens(identities[call_id]) if token in text]
            if matched_fields:
                matches.append(
                    {
                        "forecast_call_id": call_id,
                        "surface": "FILESYSTEM_ORPHAN_SEARCH",
                        "path": str(path),
                        "matched_fields": matched_fields,
                        "timestamp_only_rejected": reject_timestamp_only_candidate({"matched_fields": matched_fields}),
                    }
                )
    return ledger, matches


def google_sheet_search(sheets_service: Any, identities: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    ledger: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    titles = list_sheet_titles(sheets_service, SPREADSHEET_ID)
    plausible = plausible_log_sheets(titles)
    ledger.append({"surface": "SHEET_TITLE_ENUMERATION", "sheet_titles": titles, "plausible_log_tabs": plausible})
    for title in plausible:
        range_a1 = safe_sheet_range(title)
        fetched = fetch_sheet_values(sheets_service, SPREADSHEET_ID, range_a1)
        ledger.append(
            {
                "surface": "GOOGLE_SHEET_RANGE_FETCH",
                "sheet_title": title,
                "range": range_a1,
                "status": fetched["status"],
                "attempts": fetched["attempts"],
            }
        )
        rows = fetched["values"]
        if fetched["status"] != "PASSED":
            continue
        for call_id in UNKNOWN_CALL_IDS:
            identity = identities[call_id]
            tokens = primary_identity_tokens(identity) + [SEARCH_WINDOW_BY_CALL[call_id]]
            row_matches = search_rows_for_tokens(rows, tokens)
            ledger.append(
                {
                    "surface": "GOOGLE_SHEET_EXACT_SEARCH",
                    "forecast_call_id": call_id,
                    "sheet_title": title,
                    "range": range_a1,
                    "searched_tokens": tokens + supportive_identity_tokens(identity),
                    "match_count": len(row_matches),
                }
            )
            for match in row_matches[:100]:
                timestamp_only = reject_timestamp_only_candidate(
                    {"matched_fields": [field if field != SEARCH_WINDOW_BY_CALL[call_id] else "dispatch_timestamp_window" for field in match["matched_fields"]]}
                )
                matches.append(
                    {
                        "forecast_call_id": call_id,
                        "surface": "GOOGLE_SHEET_EXACT_SEARCH",
                        "sheet_title": title,
                        "range": range_a1,
                        "row_number": match["row_number"],
                        "matched_fields": match["matched_fields"],
                        "timestamp_only_rejected": timestamp_only,
                        "row": match["row"],
                    }
                )
    return ledger, matches, plausible


def apps_script_history_search(script_service: Any, identities: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    processes = script_service.processes()
    queries = [
        ("LIST_SCRIPT_PROCESSES", lambda: processes.listScriptProcesses(scriptId=SCRIPT_ID, pageSize=25)),
        ("LIST_USER_PROCESSES", lambda: processes.list(userProcessFilter_scriptId=SCRIPT_ID, pageSize=25)),
    ]
    for label, builder in queries:
        try:
            response = builder().execute()
            entries = response.get("processes", [])
            ledger.append({"surface": label, "status": "PASSED", "record_count": len(entries)})
            for process in entries:
                text = canonical_json(process)
                for call_id in UNKNOWN_CALL_IDS:
                    matched_fields = [token for token in primary_identity_tokens(identities[call_id]) if token in text]
                    if matched_fields:
                        matches.append(
                            {
                                "forecast_call_id": call_id,
                                "surface": label,
                                "matched_fields": matched_fields,
                                "record": process,
                            }
                        )
        except HttpError as exc:
            ledger.append(
                {
                    "surface": label,
                    "status": "HTTP_ERROR",
                    "http_status": getattr(exc.resp, "status", None),
                    "message": str(exc),
                    "searched_timestamp_windows": SEARCH_WINDOW_BY_CALL,
                }
            )
        except Exception as exc:
            ledger.append({"surface": label, "status": "ERROR", "exception_type": type(exc).__name__, "message": str(exc)})
    ledger.append(
        {
            "surface": "APPS_SCRIPT_EXECUTION_STATUS_API",
            "status": "NO_EXISTING_READ_ONLY_EXECUTION_STATUS_ROUTE_IDENTIFIED",
            "provider_capable_function_invoked": False,
        }
    )
    return ledger, matches


def cloud_log_search() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    status, hits = rg_search(
        ["apps_script", "automation", ".github"] if (ROOT / ".github").exists() else ["apps_script", "automation"],
        ["logging.googleapis.com", "google.cloud.logging", "entries.list", "cloud logging", "Stackdriver"],
    )
    ledger = [
        {
            "surface": "CLOUD_LOG_ROUTE_CONFIG_SEARCH",
            "status": status,
            "configured_route_count": len(hits),
            "reason": "Existing repo configuration search only; no new cloud logging route configured.",
        }
    ]
    matches = [{"surface": "CLOUD_LOG_ROUTE_CONFIG_SEARCH", "path_hit": hit} for hit in hits[:100]]
    if not hits:
        ledger.append(
            {
                "surface": "CLOUD_LOG_RUNTIME_SEARCH",
                "status": "NOT_ATTEMPTED_NO_CONFIGURED_READ_ONLY_ROUTE",
                "google_writes": 0,
            }
        )
    return ledger, matches


def bridge_storage_search() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    bridge_path = ROOT / "apps_script" / "authoritative_provider_bridge.js"
    log_shim_path = ROOT / "apps_script" / "00_logging_shim.gs.js"
    bridge_text = bridge_path.read_text()
    log_text = log_shim_path.read_text()
    ledger.append(
        {
            "surface": "BRIDGE_CODE_INSPECTION",
            "bridge_path": str(bridge_path),
            "log_shim_path": str(log_shim_path),
            "bridge_persists_request_id": "request_id" in bridge_text,
            "bridge_persists_raw_output": "raw_output" in bridge_text,
            "dedicated_forecast_call_storage_present": "forecast_call_id" in bridge_text,
        }
    )
    ledger.append(
        {
            "surface": "BRIDGE_STORAGE_CONCLUSION",
            "status": "NO_DEDICATED_APPEND_ONLY_BRIDGE_STORAGE_PROVEN",
            "notes": [
                "bridge returns request_id and raw_output in response objects",
                "logging shim can append generic log rows",
                "no separate existing bridge-side durable store with exact forecast_call_id persistence was identified in code",
            ],
        }
    )
    if "appendRow" in log_text:
        matches.append({"surface": "BRIDGE_LOGGING_SHIM", "path": str(log_shim_path), "matched_fields": ["appendRow"]})
    return ledger, matches


def provider_metadata_search() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    status, hits = rg_search(
        ["automation", "apps_script"],
        ["billing", "usage", "request history", "provider request id", "request_id"],
    )
    ledger = [
        {
            "surface": "PROVIDER_METADATA_ROUTE_SEARCH",
            "status": status,
            "configured_route_count": len(hits),
            "reason": "No existing read-only provider history/billing adapter is used for exact forecast-call recovery in this repo.",
        }
    ]
    matches = [{"surface": "PROVIDER_METADATA_ROUTE_SEARCH", "path_hit": hit} for hit in hits[:100] if "request_id" in hit.lower()]
    ledger.append(
        {
            "surface": "PROVIDER_METADATA_CONCLUSION",
            "status": "AGGREGATE_PROVIDER_USAGE_NOT_ACCEPTABLE_FOR_EXACT_RESULT_MATCHING",
            "aggregate_provider_usage_can_establish_exact_result": aggregate_provider_usage_is_exact_result({}),
        }
    )
    return ledger, matches


def strict_validate_recovered_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("object") == "PREDICTION":
        forecast_contract.validate_prediction(payload)
        return {"validated_object": "PREDICTION", "prediction_id": payload.get("prediction_id")}
    if payload.get("prediction") and payload.get("paths"):
        prediction = payload["prediction"]
        paths = payload["paths"]
        if not isinstance(prediction, Mapping) or not isinstance(paths, list):
            raise FinalExistenceVerificationError("RECOVERED_RESULT_SHAPE_INVALID")
        forecast_contract.validate_prediction_path_transaction(prediction, paths)
        return {
            "validated_object": "PREDICTION_PATH_TRANSACTION",
            "prediction_id": prediction.get("prediction_id"),
            "path_count": len(paths),
        }
    raise FinalExistenceVerificationError("RECOVERED_RESULT_UNSUPPORTED_SHAPE")


def classify_candidate_results(
    identities: Mapping[str, Mapping[str, Any]],
    all_matches: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    exact_matches: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    by_call: dict[str, list[Mapping[str, Any]]] = {call_id: [] for call_id in UNKNOWN_CALL_IDS}
    for row in all_matches:
        call_id = row.get("forecast_call_id")
        if call_id in by_call:
            by_call[call_id].append(row)
    for call_id in UNKNOWN_CALL_IDS:
        for row in by_call[call_id]:
            candidate = dict(row)
            candidate["accepted_as_exact_result"] = False
            candidate["rejection_reason"] = (
                "TIMESTAMP_ONLY_MATCH_REJECTED" if candidate.get("timestamp_only_rejected") else "NO_AUTHORITATIVE_RESULT_PAYLOAD_PRESENT"
            )
            candidates.append(candidate)
        authoritative_payloads = [
            row for row in by_call[call_id]
            if row.get("record") and not row.get("timestamp_only_rejected")
        ]
        if len(authoritative_payloads) > 1:
            conflicts.append(
                {
                    "forecast_call_id": call_id,
                    "conflict_type": "IDENTITY_OR_AUTHORITY_CONFLICT",
                    "candidate_count": len(authoritative_payloads),
                }
            )
        elif len(authoritative_payloads) == 1:
            exact_matches.append(
                {
                    "forecast_call_id": call_id,
                    "surface": authoritative_payloads[0]["surface"],
                    "matched_fields": authoritative_payloads[0].get("matched_fields", []),
                }
            )
            payload = authoritative_payloads[0].get("record")
            if isinstance(payload, Mapping):
                try:
                    parsed = strict_validate_recovered_payload(payload)
                    recovered.append(
                        {
                            "forecast_call_id": call_id,
                            "status": "VALID_REMOTE_RESULT_RECOVERED",
                            "parsed": parsed,
                        }
                    )
                except Exception as exc:
                    conflicts.append(
                        {
                            "forecast_call_id": call_id,
                            "conflict_type": "RECOVERED_RESULT_VALIDATION_FAILED",
                            "exception_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    )
    return candidates, exact_matches, recovered, conflicts


def lifecycle_stage_row(call_id: str, local_row: Mapping[str, Any], recovered_result: Mapping[str, Any] | None) -> dict[str, Any]:
    dispatch_certainty = (local_row.get("transport_classification") or {}).get("dispatch_certainty")
    row = {
        "forecast_call_id": call_id,
        "local_start_record": "PROVEN_OCCURRED" if local_row.get("call_started_journaled") else "EVIDENCE_NOT_FOUND",
        "local_request_serialization": "PROVEN_OCCURRED" if local_row.get("request_serialization_proven") else "EVIDENCE_NOT_FOUND",
        "local_transport_initiation": "PROVEN_OCCURRED" if local_row.get("google_api_request_initiation") else "EVIDENCE_NOT_FOUND",
        "google_request_acceptance": "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "PROVEN_OCCURRED" if dispatch_certainty == "CONFIRMED_RESPONSE" else "EVIDENCE_NOT_FOUND",
        "apps_script_execution_id": "EVIDENCE_NOT_FOUND",
        "bridge_invocation": "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "PROVEN_OCCURRED" if local_row.get("bridge_invocation_proven") else "EVIDENCE_NOT_FOUND",
        "provider_dispatch": "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "PROVEN_OCCURRED" if local_row.get("provider_dispatch_proven") else "EVIDENCE_NOT_FOUND",
        "provider_request_id": "EVIDENCE_NOT_FOUND",
        "provider_completion": "PROVEN_OCCURRED" if recovered_result else "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "EVIDENCE_NOT_FOUND",
        "bridge_completion": "PROVEN_OCCURRED" if recovered_result else "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "EVIDENCE_NOT_FOUND",
        "google_execution_completion": "PROVEN_OCCURRED" if recovered_result else "UNRESOLVED" if dispatch_certainty == "UNKNOWN" else "EVIDENCE_NOT_FOUND",
        "local_response_retrieval": "PROVEN_OCCURRED" if local_row.get("local_response_retrieval_proven") else "EVIDENCE_NOT_FOUND",
        "raw_output_persistence": "PROVEN_OCCURRED" if recovered_result else "EVIDENCE_NOT_FOUND",
        "terminal_state": "PROVEN_OCCURRED" if local_row.get("terminal_state_persisted") else "EVIDENCE_NOT_FOUND",
        "recoverable_result_existence": "PROVEN_OCCURRED" if recovered_result else "EVIDENCE_NOT_FOUND",
    }
    for stage in LIFECYCLE_STAGES:
        if row[stage] not in PERMITTED_STAGE_VALUES:
            raise FinalExistenceVerificationError(f"LIFECYCLE_STAGE_INVALID:{call_id}:{stage}")
    return row


def final_retry_rows(recovered: Mapping[str, Mapping[str, Any]], conflicts: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call_id in UNKNOWN_CALL_IDS:
        if call_id in recovered:
            recommendation = "DO_NOT_RETRY_VALID_RESULT_RECOVERED"
        elif call_id in conflicts:
            recommendation = "DO_NOT_RETRY_IDENTITY_CONFLICT"
        else:
            recommendation = "GOVERNANCE_RETRY_REASONABLE_NO_RECOVERABLE_RESULT"
        rows.append({"forecast_call_id": call_id, "recommendation": recommendation})
    return rows


def initialize_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_FINAL_EXISTENCE_VERIFICATION_BATCH_002",
            "plan_id": PLAN_ID,
            "failed_batch_002_id": FAILED_BATCH_002_ID,
            "transport_repair_id": TRANSPORT_REPAIR_ID,
            "unknown_state_resolution_id": UNKNOWN_STATE_RESOLUTION_ID,
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
            "failed_batch_002_id": FAILED_BATCH_002_ID,
            "transport_repair_id": TRANSPORT_REPAIR_ID,
            "unknown_state_resolution_id": UNKNOWN_STATE_RESOLUTION_ID,
        },
    )
    write_json(
        run_dir / "verification_contract.json",
        {
            "exact_identifier_preference_order": [
                "forecast_call_id",
                "bridge_request_id",
                "apps_script_execution_id",
                "provider_request_id",
                "prompt_text_fingerprint",
                "pack_row_fingerprint",
                "episode_id",
                "provider",
                "model",
                "historical_cutoff",
            ],
            "forbidden_fuzzy_match_basis": [
                "timestamp_proximity_only",
                "episode_title",
                "provider_name_alone",
                "payload_similarity",
                "date_only",
                "prompt_similarity",
                "manual_judgment",
            ],
            "provider_calls_permitted": 0,
            "google_writes_permitted": 0,
        },
    )


def execute_verification(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise FinalExistenceVerificationError("BRANCH_MISMATCH")
    head = git_head()
    if head != EXPECTED_HEAD and not is_descendant_of(EXPECTED_HEAD):
        raise FinalExistenceVerificationError("HEAD_ANCESTRY_NOT_CLEAN")

    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir)

    identities = identity_inventory()
    call_inventory = [identities[call_id] | {"dispatch_timestamp_window": SEARCH_WINDOW_BY_CALL[call_id]} for call_id in UNKNOWN_CALL_IDS]

    failed_rows = baseline.failed_batch_rows()
    local_rows_list = baseline.local_lifecycle_rows(identities, failed_rows)
    local_rows = {row["forecast_call_id"]: row for row in local_rows_list}

    credentials = google_clients.load_credentials(False, token_path=batch001.TOKEN_PATH, persist_refresh=False)
    sheets_service = google_clients.build_sheets_service(credentials)
    script_service = google_clients.build_script_service(credentials, 60)

    local_search_ledger, local_matches = local_output_search(identities, run_dir)
    orphan_ledger, orphan_matches = orphan_search(identities)
    sheet_ledger, sheet_matches, plausible_tabs = google_sheet_search(sheets_service, identities)
    apps_script_ledger, apps_script_matches = apps_script_history_search(script_service, identities)
    cloud_ledger, cloud_matches = cloud_log_search()
    bridge_ledger, bridge_matches = bridge_storage_search()
    provider_ledger, provider_matches = provider_metadata_search()
    enumerated_titles = next((row["sheet_titles"] for row in sheet_ledger if row.get("surface") == "SHEET_TITLE_ENUMERATION"), [])

    all_matches = (
        local_matches
        + orphan_matches
        + sheet_matches
        + apps_script_matches
        + cloud_matches
        + bridge_matches
        + provider_matches
    )
    candidate_results, exact_identity_matches, recovered_results, conflicts = classify_candidate_results(identities, all_matches)
    recovered_by_call = {row["forecast_call_id"]: row for row in recovered_results}
    conflict_by_call = {row["forecast_call_id"]: row for row in conflicts if row.get("forecast_call_id")}
    lifecycle_rows = [lifecycle_stage_row(call_id, local_rows[call_id], recovered_by_call.get(call_id)) for call_id in UNKNOWN_CALL_IDS]
    retry_rows = final_retry_rows(recovered_by_call, conflict_by_call)

    summary = {
        "calls_audited": len(UNKNOWN_CALL_IDS),
        "local_output_searches": len(local_search_ledger),
        "orphan_candidate_count": next((row["candidate_count"] for row in orphan_ledger if row.get("surface") == "FILESYSTEM_ORPHAN_CANDIDATE_INVENTORY"), 0),
        "google_sheet_tabs_enumerated": len(enumerated_titles),
        "google_sheet_tabs_searched": plausible_tabs,
        "apps_script_process_routes_attempted": [row["surface"] for row in apps_script_ledger if row.get("surface", "").startswith("LIST_")],
        "candidate_result_count": len(candidate_results),
        "exact_identity_match_count": len(exact_identity_matches),
        "recoverable_result_count": len(recovered_results),
        "conflict_count": len(conflicts),
    }
    decisions = {
        "verification_status": "FINAL_EXISTENCE_VERIFICATION_COMPLETE",
        "result_existence_decision": (
            "RECOVERABLE_RESULTS_FOUND"
            if recovered_results
            else "RESULT_EXISTENCE_CONFLICTS_PRESENT"
            if conflicts
            else "NO_RECOVERABLE_RESULTS_FOUND_AFTER_FINAL_BOUNDED_SEARCH"
        ),
        "retry_governance_decision": (
            "SOME_CALLS_MUST_NOT_BE_RETRIED"
            if recovered_results
            else "GOVERNANCE_CONFLICT_REQUIRES_REVIEW"
            if conflicts
            else "READY_FOR_SINGLE_GOVERNANCE_AUTHORIZED_RECOVERY_ATTEMPT"
        ),
    }

    write_jsonl(run_dir / "call_identity_inventory.jsonl", call_inventory)
    write_jsonl(run_dir / "local_evidence_search_ledger.jsonl", local_search_ledger)
    write_jsonl(run_dir / "filesystem_orphan_search_ledger.jsonl", orphan_ledger)
    write_jsonl(run_dir / "google_sheet_search_ledger.jsonl", sheet_ledger)
    write_jsonl(run_dir / "apps_script_execution_search_ledger.jsonl", apps_script_ledger)
    write_jsonl(run_dir / "cloud_log_search_ledger.jsonl", cloud_ledger)
    write_jsonl(run_dir / "bridge_storage_search_ledger.jsonl", bridge_ledger)
    write_jsonl(run_dir / "provider_metadata_search_ledger.jsonl", provider_ledger)
    write_jsonl(run_dir / "candidate_result_inventory.jsonl", candidate_results)
    write_jsonl(run_dir / "exact_identity_match_ledger.jsonl", exact_identity_matches)
    write_jsonl(run_dir / "final_call_lifecycle_reconstruction.jsonl", lifecycle_rows)
    write_jsonl(run_dir / "recovered_result_ledger.jsonl", recovered_results)
    write_jsonl(run_dir / "conflict_ledger.jsonl", conflicts)
    write_jsonl(run_dir / "final_retry_recommendation.jsonl", retry_rows)
    write_json(run_dir / "verification_summary.json", summary)
    write_json(run_dir / "verification_decision.json", decisions)

    return {
        "run_dir": run_dir,
        "call_inventory": call_inventory,
        "local_search_ledger": local_search_ledger,
        "orphan_ledger": orphan_ledger,
        "sheet_ledger": sheet_ledger,
        "apps_script_ledger": apps_script_ledger,
        "cloud_ledger": cloud_ledger,
        "bridge_ledger": bridge_ledger,
        "provider_ledger": provider_ledger,
        "candidate_results": candidate_results,
        "exact_identity_matches": exact_identity_matches,
        "recovered_results": recovered_results,
        "conflicts": conflicts,
        "lifecycle_rows": lifecycle_rows,
        "retry_rows": retry_rows,
        "summary": summary,
        "decisions": decisions,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = execute_verification(fixed_timestamp=args.fixed_timestamp)
    print(canonical_json({"run_dir": str(result["run_dir"]), **result["decisions"]}))


if __name__ == "__main__":
    main()
