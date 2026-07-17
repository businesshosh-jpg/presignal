import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _parse_dt,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_market_state_pack_candidates_v0 import build_market_state_pack_candidates_v0
from automation.build_presignal_v2_run_status_v0 import build_presignal_v2_run_status_v0
from automation.build_presignal_v2_replay_queue_v0 import OUTPUT_QUEUE_SHEET as REPLAY_QUEUE_SHEET
from automation.build_session_attention_map_v0 import build_session_attention_map_v0
from automation.build_session_baseline_compare_v0 import build_session_baseline_compare_v0
from automation.build_session_evaluation_v0 import build_session_evaluation_v0
from automation.build_session_forecasts_v0 import build_session_forecasts_v0
from automation.build_session_information_requests_v0 import build_session_information_requests_v0
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials
from automation.build_market_sessions_shadow_v0 import build_market_sessions_shadow_v0
from googleapiclient.errors import HttpError


OUTPUT_LOG_SHEET = "PreSignal_v2_Replay_Run_Log"
OUTPUT_SUMMARY_SHEET = "PreSignal_v2_Replay_Run_Summary"
HISTORY_CAPTURE_LOG_SHEET = "Replay_History_Capture_Log"
HISTORY_CAPTURE_SUMMARY_SHEET = "Replay_History_Capture_Summary"

MARKET_SESSIONS_SHEET = "Market_Sessions"
MARKET_SESSION_MEMBERS_SHEET = "Market_Session_Members"
SESSION_ATTENTION_MAP_SHEET = "Session_Attention_Map"
SESSION_ATTENTION_SUMMARY_SHEET = "Session_Attention_Summary"
SESSION_INFORMATION_REQUESTS_SHEET = "Session_Information_Requests"
SESSION_FORECASTS_SHEET = "Session_Forecasts"
SESSION_EVALUATION_SHEET = "Session_Evaluation"
SESSION_BASELINE_COMPARE_SHEET = "Session_vs_Event_Baseline_Compare"
MARKET_STATE_PACK_CANDIDATES_SHEET = "Market_State_Pack_Candidates"

SESSION_ATTENTION_MAP_HISTORY_SHEET = "Session_Attention_Map_History"
SESSION_INFORMATION_REQUESTS_HISTORY_SHEET = "Session_Information_Requests_History"
SESSION_FORECASTS_HISTORY_SHEET = "Session_Forecasts_History"
SESSION_EVALUATION_HISTORY_SHEET = "Session_Evaluation_History"
SESSION_BASELINE_COMPARE_HISTORY_SHEET = "Session_vs_Event_Baseline_Compare_History"
MARKET_STATE_PACK_CANDIDATES_HISTORY_SHEET = "Market_State_Pack_Candidates_History"

SCHEMA_VERSION = "presignal_v2_replay_runner_0.1"
SHADOW_VERSION = "shadow_v0"
HISTORY_SCHEMA_VERSION = "presignal_v2_replay_history_0.1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

QUEUE_EXTRA_HEADERS = [
    "replay_started_ts",
    "replay_completed_ts",
    "last_phase_completed",
    "last_runner_replay_id",
    "last_error",
]

LOG_HEADERS = [
    "generated_ts",
    "replay_id",
    "session_id",
    "active_session_id",
    "artifact_session_ids_seen",
    "linkage_status",
    "linkage_error",
    "phase_completed",
    "phase_limit",
    "status",
    "elapsed_seconds",
    "warnings",
    "errors",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "replay_id",
    "sessions_requested",
    "sessions_started",
    "sessions_completed",
    "sessions_failed",
    "phase_limit",
    "linkage_check_count",
    "linkage_pass_count",
    "linkage_fail_count",
    "cross_session_mismatch_count",
    "missing_active_artifact_count",
    "total_elapsed",
    "build_status",
    "final_interpretation",
]

HISTORY_METADATA_HEADERS = [
    "history_capture_ts",
    "history_schema_version",
    "shadow_version",
    "replay_id",
    "campaign_id",
    "experiment_id",
    "active_session_id",
    "source_sheet",
    "source_row_hash",
    "capture_phase",
    "capture_status",
    "history_key",
]

HISTORY_LOG_HEADERS = [
    "generated_ts",
    "history_schema_version",
    "shadow_version",
    "replay_id",
    "campaign_id",
    "experiment_id",
    "active_session_id",
    "capture_phase",
    "source_sheet",
    "history_sheet",
    "source_rows_seen",
    "rows_captured",
    "duplicate_rows_skipped",
    "linkage_status",
    "capture_status",
    "error_message",
    "notes",
]

HISTORY_SUMMARY_HEADERS = [
    "generated_ts",
    "history_schema_version",
    "shadow_version",
    "replay_id",
    "active_session_id",
    "attention_history_rows_captured",
    "information_history_rows_captured",
    "forecast_history_rows_captured",
    "evaluation_history_rows_captured",
    "baseline_history_rows_captured",
    "candidate_history_rows_captured",
    "duplicate_rows_skipped",
    "history_capture_status",
    "final_interpretation",
    "notes",
]

HISTORY_PHASE_SPECS: Dict[int, Tuple[str, str, bool]] = {
    2: (SESSION_ATTENTION_MAP_SHEET, SESSION_ATTENTION_MAP_HISTORY_SHEET, True),
    3: (SESSION_INFORMATION_REQUESTS_SHEET, SESSION_INFORMATION_REQUESTS_HISTORY_SHEET, True),
    4: (SESSION_FORECASTS_SHEET, SESSION_FORECASTS_HISTORY_SHEET, True),
    5: (SESSION_EVALUATION_SHEET, SESSION_EVALUATION_HISTORY_SHEET, True),
    6: (SESSION_BASELINE_COMPARE_SHEET, SESSION_BASELINE_COMPARE_HISTORY_SHEET, True),
    7: (MARKET_STATE_PACK_CANDIDATES_SHEET, MARKET_STATE_PACK_CANDIDATES_HISTORY_SHEET, False),
}


class ReplaySessionLinkageError(RuntimeError):
    def __init__(
        self,
        linkage_status: str,
        linkage_error: str,
        artifact_session_ids_seen: Sequence[str],
        failed_phase: int,
    ) -> None:
        super().__init__(f"{linkage_status}: {linkage_error}")
        self.linkage_status = linkage_status
        self.linkage_error = linkage_error
        self.artifact_session_ids_seen = list(artifact_session_ids_seen)
        self.failed_phase = failed_phase


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _is_rate_limit_error(exc: Exception) -> bool:
    if not isinstance(exc, HttpError):
        return False
    status = getattr(getattr(exc, "resp", None), "status", None)
    return status == 429


def _upsert_registry_rows_with_retry(service, max_attempts: int = 4) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _upsert_registry_rows(service)
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt == max_attempts:
                raise
            time.sleep(15 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("registry upsert retry exited without result")


def _with_rate_limit_retry(fn: Callable[..., Any], *args, max_attempts: int = 4, **kwargs) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt == max_attempts:
                raise
            time.sleep(15 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("rate limit retry exited without result")


def _upsert_registry_rows(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    updates = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "PRESIGNAL_V2_REPLAY_RUN_LOG",
            "physical_sheet_name": OUTPUT_LOG_SHEET,
            "sheet_role": "v2_replay_run_log",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5B",
            "notes": "shadow_v0 replay runner log",
        },
        {
            "logical_sheet_id": "PRESIGNAL_V2_REPLAY_RUN_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_replay_run_summary",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5B",
            "notes": "shadow_v0 replay runner summary",
        },
        {
            "logical_sheet_id": "SESSION_ATTENTION_MAP_HISTORY",
            "physical_sheet_name": SESSION_ATTENTION_MAP_HISTORY_SHEET,
            "sheet_role": "v2_replay_attention_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only attention replay history",
        },
        {
            "logical_sheet_id": "SESSION_INFORMATION_REQUESTS_HISTORY",
            "physical_sheet_name": SESSION_INFORMATION_REQUESTS_HISTORY_SHEET,
            "sheet_role": "v2_replay_information_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only information replay history",
        },
        {
            "logical_sheet_id": "SESSION_FORECASTS_HISTORY",
            "physical_sheet_name": SESSION_FORECASTS_HISTORY_SHEET,
            "sheet_role": "v2_replay_forecast_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only forecast replay history",
        },
        {
            "logical_sheet_id": "SESSION_EVALUATION_HISTORY",
            "physical_sheet_name": SESSION_EVALUATION_HISTORY_SHEET,
            "sheet_role": "v2_replay_evaluation_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only evaluation replay history",
        },
        {
            "logical_sheet_id": "SESSION_VS_EVENT_BASELINE_COMPARE_HISTORY",
            "physical_sheet_name": SESSION_BASELINE_COMPARE_HISTORY_SHEET,
            "sheet_role": "v2_replay_baseline_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only baseline compare replay history",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_CANDIDATES_HISTORY",
            "physical_sheet_name": MARKET_STATE_PACK_CANDIDATES_HISTORY_SHEET,
            "sheet_role": "v2_replay_candidate_history",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 append-only market state candidate replay history",
        },
        {
            "logical_sheet_id": "REPLAY_HISTORY_CAPTURE_LOG",
            "physical_sheet_name": HISTORY_CAPTURE_LOG_SHEET,
            "sheet_role": "v2_replay_history_capture_log",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 replay history capture log",
        },
        {
            "logical_sheet_id": "REPLAY_HISTORY_CAPTURE_SUMMARY",
            "physical_sheet_name": HISTORY_CAPTURE_SUMMARY_SHEET,
            "sheet_role": "v2_replay_history_capture_summary",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5G",
            "notes": "shadow_v0 replay history capture summary",
        },
    ]
    for row in registry_rows:
        key = _norm(row["logical_sheet_id"]).upper()
        existing = existing_by_id.get(key, {})
        merged = dict(row)
        merged["registry_created_ts"] = _norm(existing.get("registry_created_ts")) or now
        merged["registry_last_verified_ts"] = now
        merged["registry_migration_ts"] = _norm(existing.get("registry_migration_ts"))
        merged["registry_rename_ts"] = _norm(existing.get("registry_rename_ts"))
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _append_rows(service, spreadsheet_id: str, sheet_name: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        return
    existing_rows = _with_rate_limit_retry(_sheet_to_rows, service, spreadsheet_id, sheet_name)
    start_row = len(existing_rows) + 2
    values = [[row.get(header, "") for header in headers] for row in rows]
    def _write() -> None:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A{start_row}",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    _with_rate_limit_retry(_write)


def _history_source_headers(rows: Sequence[Dict[str, Any]]) -> List[str]:
    headers: List[str] = []
    for row in rows:
        for key in row.keys():
            if key.startswith("__"):
                continue
            if key in HISTORY_METADATA_HEADERS:
                continue
            if key not in headers:
                headers.append(key)
    return headers


def _stable_row_hash(row: Dict[str, Any]) -> str:
    payload: Dict[str, str] = {}
    for key in sorted(row.keys()):
        if key.startswith("__"):
            continue
        if key == "generated_ts":
            continue
        if key.endswith("_run_id"):
            continue
        payload[key] = _norm(row.get(key))
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _history_key(active_session_id: str, source_sheet: str, capture_phase: str, source_row_hash: str) -> str:
    return f"{active_session_id}|{source_sheet}|{capture_phase}|{source_row_hash}"


def _history_context(args: argparse.Namespace) -> Dict[str, str]:
    return {
        "campaign_id": _norm(getattr(args, "campaign_id", "")),
        "experiment_id": _norm(getattr(args, "experiment_id", "")),
    }


def _ensure_history_sheets(service) -> Dict[str, List[str]]:
    headers_by_sheet: Dict[str, List[str]] = {}
    for history_sheet in [
        SESSION_ATTENTION_MAP_HISTORY_SHEET,
        SESSION_INFORMATION_REQUESTS_HISTORY_SHEET,
        SESSION_FORECASTS_HISTORY_SHEET,
        SESSION_EVALUATION_HISTORY_SHEET,
        SESSION_BASELINE_COMPARE_HISTORY_SHEET,
        MARKET_STATE_PACK_CANDIDATES_HISTORY_SHEET,
    ]:
        headers_by_sheet[history_sheet] = _ensure_sheet(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            history_sheet,
            HISTORY_METADATA_HEADERS,
        )
    headers_by_sheet[HISTORY_CAPTURE_LOG_SHEET] = _ensure_sheet(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        HISTORY_CAPTURE_LOG_SHEET,
        HISTORY_LOG_HEADERS,
    )
    headers_by_sheet[HISTORY_CAPTURE_SUMMARY_SHEET] = _ensure_sheet(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        HISTORY_CAPTURE_SUMMARY_SHEET,
        HISTORY_SUMMARY_HEADERS,
    )
    return headers_by_sheet


def _existing_history_keys(service, history_sheet: str) -> Set[str]:
    try:
        rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, history_sheet)
    except Exception:
        rows = []
    return {_norm(row.get("history_key")) for row in rows if _norm(row.get("history_key"))}


def _capture_phase_history(
    service,
    active_session_id: str,
    replay_id: str,
    phase_number: int,
    linkage_status: str,
    context: Dict[str, str],
    history_keys_cache: Dict[str, Set[str]],
    history_rows_to_append: Dict[str, List[Dict[str, Any]]],
    history_log_rows: List[Dict[str, Any]],
    session_history_counts: Dict[str, int],
    history_duplicate_skips: List[int],
    history_dry_run: bool,
) -> None:
    spec = HISTORY_PHASE_SPECS.get(phase_number)
    if not spec:
        return

    source_sheet, history_sheet, filter_by_session = spec
    capture_phase = f"Phase {phase_number}"
    source_rows = _read_sheet_rows(service, source_sheet)
    if filter_by_session:
        source_rows = [row for row in source_rows if _norm(row.get("session_id")) == active_session_id]
    source_rows_seen = len(source_rows)

    if linkage_status != "LINKED":
        history_log_rows.append(
            {
                "generated_ts": _iso_now(),
                "history_schema_version": HISTORY_SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "replay_id": replay_id,
                "campaign_id": context["campaign_id"],
                "experiment_id": context["experiment_id"],
                "active_session_id": active_session_id,
                "capture_phase": capture_phase,
                "source_sheet": source_sheet,
                "history_sheet": history_sheet,
                "source_rows_seen": source_rows_seen,
                "rows_captured": 0,
                "duplicate_rows_skipped": 0,
                "linkage_status": linkage_status,
                "capture_status": "SKIPPED_LINKAGE_NOT_VERIFIED",
                "error_message": "",
                "notes": "",
            }
        )
        return

    if not source_rows:
        history_log_rows.append(
            {
                "generated_ts": _iso_now(),
                "history_schema_version": HISTORY_SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "replay_id": replay_id,
                "campaign_id": context["campaign_id"],
                "experiment_id": context["experiment_id"],
                "active_session_id": active_session_id,
                "capture_phase": capture_phase,
                "source_sheet": source_sheet,
                "history_sheet": history_sheet,
                "source_rows_seen": 0,
                "rows_captured": 0,
                "duplicate_rows_skipped": 0,
                "linkage_status": linkage_status,
                "capture_status": "SKIPPED_NO_ROWS",
                "error_message": "",
                "notes": "",
            }
        )
        return

    existing_keys = history_keys_cache.setdefault(history_sheet, _existing_history_keys(service, history_sheet))
    headers = _history_source_headers(source_rows)
    if not history_dry_run:
        _ensure_sheet(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            history_sheet,
            list(HISTORY_METADATA_HEADERS) + headers,
        )
    captured_rows: List[Dict[str, Any]] = []
    duplicate_rows_skipped = 0

    for source_row in source_rows:
        source_row_hash = _stable_row_hash(source_row)
        history_key = _history_key(active_session_id, source_sheet, capture_phase, source_row_hash)
        if history_key in existing_keys:
            duplicate_rows_skipped += 1
            continue
        history_row = {
            "history_capture_ts": _iso_now(),
            "history_schema_version": HISTORY_SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "replay_id": replay_id,
            "campaign_id": context["campaign_id"],
            "experiment_id": context["experiment_id"],
            "active_session_id": active_session_id,
            "source_sheet": source_sheet,
            "source_row_hash": source_row_hash,
            "capture_phase": capture_phase,
            "capture_status": "CAPTURED",
            "history_key": history_key,
        }
        for key, value in source_row.items():
            if key.startswith("__"):
                continue
            history_row[key] = value
        captured_rows.append(history_row)
        existing_keys.add(history_key)

    if not history_dry_run:
        history_rows_to_append.setdefault(history_sheet, []).extend(captured_rows)
    history_log_rows.append(
        {
            "generated_ts": _iso_now(),
            "history_schema_version": HISTORY_SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "replay_id": replay_id,
            "campaign_id": context["campaign_id"],
            "experiment_id": context["experiment_id"],
            "active_session_id": active_session_id,
            "capture_phase": capture_phase,
            "source_sheet": source_sheet,
            "history_sheet": history_sheet,
            "source_rows_seen": source_rows_seen,
            "rows_captured": len(captured_rows),
            "duplicate_rows_skipped": duplicate_rows_skipped,
            "linkage_status": linkage_status,
            "capture_status": "CAPTURED" if captured_rows else "SKIPPED_NO_ROWS",
            "error_message": "",
            "notes": "history_dry_run=TRUE" if history_dry_run else "",
        }
    )
    session_key = {
        SESSION_ATTENTION_MAP_HISTORY_SHEET: "attention_history_rows_captured",
        SESSION_INFORMATION_REQUESTS_HISTORY_SHEET: "information_history_rows_captured",
        SESSION_FORECASTS_HISTORY_SHEET: "forecast_history_rows_captured",
        SESSION_EVALUATION_HISTORY_SHEET: "evaluation_history_rows_captured",
        SESSION_BASELINE_COMPARE_HISTORY_SHEET: "baseline_history_rows_captured",
        MARKET_STATE_PACK_CANDIDATES_HISTORY_SHEET: "candidate_history_rows_captured",
    }[history_sheet]
    session_history_counts[session_key] += len(captured_rows)
    history_duplicate_skips[0] += duplicate_rows_skipped


def _history_summary_row(
    replay_id: str,
    active_session_id: str,
    session_history_counts: Dict[str, int],
    duplicate_rows_skipped: int,
    had_capture_warning: bool,
) -> Dict[str, Any]:
    if had_capture_warning and sum(session_history_counts.values()) == 0:
        history_capture_status = "READY_WITH_WARNINGS"
        final_interpretation = "REPLAY_HISTORY_CAPTURE_READY_WITH_WARNINGS"
    elif had_capture_warning:
        history_capture_status = "READY_WITH_WARNINGS"
        final_interpretation = "REPLAY_HISTORY_CAPTURE_READY_WITH_WARNINGS"
    else:
        history_capture_status = "READY"
        final_interpretation = "REPLAY_HISTORY_CAPTURE_READY"
    return {
        "generated_ts": _iso_now(),
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "replay_id": replay_id,
        "active_session_id": active_session_id,
        "attention_history_rows_captured": session_history_counts.get("attention_history_rows_captured", 0),
        "information_history_rows_captured": session_history_counts.get("information_history_rows_captured", 0),
        "forecast_history_rows_captured": session_history_counts.get("forecast_history_rows_captured", 0),
        "evaluation_history_rows_captured": session_history_counts.get("evaluation_history_rows_captured", 0),
        "baseline_history_rows_captured": session_history_counts.get("baseline_history_rows_captured", 0),
        "candidate_history_rows_captured": session_history_counts.get("candidate_history_rows_captured", 0),
        "duplicate_rows_skipped": duplicate_rows_skipped,
        "history_capture_status": history_capture_status,
        "final_interpretation": final_interpretation,
        "notes": "",
    }


def _parse_queue_time_for_phase1(ts: str) -> str:
    from datetime import timezone

    dt = _parse_dt(ts)
    if dt is None:
        raise RuntimeError(f"Invalid queue timestamp: {ts}")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _queue_headers(service):
    return _ensure_sheet(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        REPLAY_QUEUE_SHEET,
        [
            "generated_ts",
            "schema_version",
            "shadow_version",
            "replay_queue_id",
            "replay_order",
            "session_id",
            "session_date",
            "country",
            "session_window_name",
            "session_start_ts",
            "session_end_ts",
            "member_event_count",
            "member_event_ids",
            "member_indicator_names",
            "earliest_release_ts",
            "latest_release_ts",
            "replay_status",
            "recommended_run_mode",
            "phase1_ready",
            "phase2_requires_provider_calls",
            "phase3_requires_provider_calls",
            "phase4_requires_provider_calls",
            "estimated_provider_call_count",
            "notes",
            *QUEUE_EXTRA_HEADERS,
        ],
    )


def _queue_row_filters(args: argparse.Namespace, row: Dict[str, Any]) -> bool:
    if args.replay_queue_id and _norm(row.get("replay_queue_id")) != _norm(args.replay_queue_id):
        return False
    if args.session_id and _norm(row.get("session_id")) != _norm(args.session_id):
        return False
    status = _norm(row.get("replay_status"))
    if args.retry_failed and status == "FAILED":
        return True
    if args.resume:
        return status in {"READY_FOR_REPLAY", "RUNNING"}
    return status == "READY_FOR_REPLAY"


def _select_queue_rows(rows: Sequence[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    selected = [row for row in rows if _queue_row_filters(args, row)]
    selected.sort(
        key=lambda row: (
            int(_norm(row.get("replay_order")) or "0"),
            _norm(row.get("session_id")),
        )
    )
    if args.max_sessions is not None:
        selected = selected[: args.max_sessions]
    return selected


def _phase_functions() -> Dict[int, Tuple[str, Callable[..., Dict[str, Any]]]]:
    return {
        1: ("phase1", build_market_sessions_shadow_v0),
        2: ("phase2", build_session_attention_map_v0),
        3: ("phase3", build_session_information_requests_v0),
        4: ("phase4", build_session_forecasts_v0),
        5: ("phase5", build_session_evaluation_v0),
        6: ("phase6", build_session_baseline_compare_v0),
        7: ("phase7", build_market_state_pack_candidates_v0),
        8: ("status", build_presignal_v2_run_status_v0),
    }


def _invoke_phase(phase_number: int, queue_row: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    phase_map = _phase_functions()
    phase_name, fn = phase_map[phase_number]
    if phase_number == 1:
        args = argparse.Namespace(
            window_from=_parse_queue_time_for_phase1(queue_row.get("session_start_ts")),
            window_to=_parse_queue_time_for_phase1(queue_row.get("session_end_ts")),
            timezone="UTC",
            country=_norm(queue_row.get("country")) or "US",
            session_window_name=_norm(queue_row.get("session_window_name")),
        )
        return fn(args)
    if phase_number == 2:
        args = argparse.Namespace(dry_run=dry_run, mock=False, live=not dry_run)
        return fn(args)
    if phase_number == 3:
        args = argparse.Namespace(dry_run=dry_run, mock=False, live=not dry_run)
        return fn(args)
    if phase_number == 4:
        args = argparse.Namespace(dry_run=dry_run, live=not dry_run)
        return fn(args)
    if phase_number in {5, 6, 7, 8}:
        args = argparse.Namespace()
        return fn(args)
    raise RuntimeError(f"Unsupported phase number: {phase_number}")


def _latest_row(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {}
    return sorted(
        rows,
        key=lambda row: (
            _norm(row.get("generated_ts")),
            str(row.get("__source_row_number__") or ""),
        ),
    )[-1]


def _session_ids_in_rows(rows: Sequence[Dict[str, Any]]) -> List[str]:
    seen = []
    used = set()
    for row in rows:
        session_id = _norm(row.get("session_id"))
        if session_id and session_id not in used:
            used.add(session_id)
            seen.append(session_id)
    return seen


def _read_sheet_rows(service, sheet_name: str) -> List[Dict[str, Any]]:
    try:
        return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
    except Exception:
        return []


def _rows_by_sheet(service, sheet_names: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    return {sheet_name: _read_sheet_rows(service, sheet_name) for sheet_name in sheet_names}


def _check_required_session_detail(
    active_session_id: str,
    rows_by_sheet: Dict[str, List[Dict[str, Any]]],
    required_sheets: Sequence[str],
) -> Tuple[str, str, List[str]]:
    artifact_session_ids: List[str] = []
    per_sheet_ids: Dict[str, List[str]] = {}

    for sheet_name in required_sheets:
        rows = rows_by_sheet.get(sheet_name, [])
        session_ids = _session_ids_in_rows(rows)
        per_sheet_ids[sheet_name] = session_ids
        for session_id in session_ids:
            if session_id not in artifact_session_ids:
                artifact_session_ids.append(session_id)

    if not artifact_session_ids:
        return (
            "ACTIVE_SESSION_ARTIFACT_MISSING",
            f"Required replay artifacts were not written for sheets={json.dumps(list(required_sheets))}.",
            artifact_session_ids,
        )

    for sheet_name, session_ids in per_sheet_ids.items():
        if active_session_id not in session_ids:
            mismatch_status = (
                "ACTIVE_SESSION_ARTIFACT_MISSING"
                if not session_ids
                else "CROSS_SESSION_ARTIFACT_MISMATCH"
            )
            return (
                mismatch_status,
                f"{sheet_name} does not contain active session_id={active_session_id}. seen={json.dumps(session_ids)}",
                artifact_session_ids,
            )
        extra_ids = [session_id for session_id in session_ids if session_id != active_session_id]
        if extra_ids:
            return (
                "CROSS_SESSION_ARTIFACT_MISMATCH",
                f"{sheet_name} contains session_ids outside the active replay session. active={active_session_id} seen={json.dumps(session_ids)}",
                artifact_session_ids,
            )

    return ("LINKED", "", artifact_session_ids)


def _phase_linkage_check(
    service,
    active_session_id: str,
    phase_number: int,
) -> Tuple[str, str, List[str], List[str]]:
    summary_warning_sheets: List[str] = []
    if phase_number == 1:
        required_sheets = [MARKET_SESSIONS_SHEET, MARKET_SESSION_MEMBERS_SHEET]
    elif phase_number == 2:
        required_sheets = [SESSION_ATTENTION_MAP_SHEET]
        summary_rows = _read_sheet_rows(service, SESSION_ATTENTION_SUMMARY_SHEET)
        if summary_rows:
            summary_warning_sheets.append(SESSION_ATTENTION_SUMMARY_SHEET)
    elif phase_number == 3:
        required_sheets = [SESSION_INFORMATION_REQUESTS_SHEET]
    elif phase_number == 4:
        required_sheets = [SESSION_FORECASTS_SHEET]
    elif phase_number == 5:
        required_sheets = [SESSION_EVALUATION_SHEET]
    elif phase_number == 6:
        required_sheets = [SESSION_BASELINE_COMPARE_SHEET]
    elif phase_number == 7:
        required_sheets = [SESSION_INFORMATION_REQUESTS_SHEET]
    else:
        return ("NOT_CHECKED", "", [], [])

    status, error, artifact_session_ids = _check_required_session_detail(
        active_session_id,
        _rows_by_sheet(service, required_sheets),
        required_sheets,
    )
    return (status, error, artifact_session_ids, summary_warning_sheets)


def _update_queue_rows(
    service,
    headers: Sequence[str],
    queue_rows: Sequence[Dict[str, Any]],
) -> None:
    updates = []
    for row in queue_rows:
        row_number = row.get("__source_row_number__")
        if not row_number:
            continue
        values = [row.get(header, "") for header in headers]
        updates.append(
            {
                "range": f"'{REPLAY_QUEUE_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2 replay pipeline runner v0.")
    parser.add_argument("--phase-limit", type=int, required=True)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--replay-queue-id", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--capture-history", action="store_true")
    parser.add_argument("--history-dry-run", action="store_true")
    return parser.parse_args(argv)


def build_presignal_v2_replay_runner_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])
    if args.phase_limit < 1 or args.phase_limit > 7:
        raise RuntimeError("--phase-limit must be between 1 and 7.")

    replay_id = f"presignal_v2_replay_run|{_iso_now()}"
    started_at = time.time()

    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    queue_headers = _with_rate_limit_retry(_queue_headers, service)
    queue_rows = _with_rate_limit_retry(_sheet_to_rows, service, DIAGNOSTICS_SPREADSHEET_ID, REPLAY_QUEUE_SHEET)
    _require_headers(REPLAY_QUEUE_SHEET, queue_rows, ["session_id", "replay_status", "session_start_ts", "session_end_ts", "country", "session_window_name"])

    selected_rows = _select_queue_rows(queue_rows, args)
    log_headers = _with_rate_limit_retry(_ensure_sheet, service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_LOG_SHEET, LOG_HEADERS)
    summary_headers = _with_rate_limit_retry(_ensure_sheet, service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    history_headers_by_sheet: Dict[str, List[str]] = {}
    history_rows_to_append: Dict[str, List[Dict[str, Any]]] = {}
    history_log_rows: List[Dict[str, Any]] = []
    history_summary_rows: List[Dict[str, Any]] = []
    history_keys_cache: Dict[str, Set[str]] = {}
    context = _history_context(args)
    if args.capture_history and not args.history_dry_run:
        history_headers_by_sheet = _with_rate_limit_retry(_ensure_history_sheets, service)

    log_rows: List[Dict[str, Any]] = []
    sessions_started = 0
    sessions_completed = 0
    sessions_failed = 0
    linkage_check_count = 0
    linkage_pass_count = 0
    linkage_fail_count = 0
    cross_session_mismatch_count = 0
    missing_active_artifact_count = 0

    for queue_row in selected_rows:
        session_id = _norm(queue_row.get("session_id"))
        phase_completed = 0
        warnings: List[str] = []
        errors: List[str] = []
        linkage_status = "NOT_CHECKED"
        linkage_error = ""
        artifact_session_ids_seen: List[str] = []
        session_history_counts = {
            "attention_history_rows_captured": 0,
            "information_history_rows_captured": 0,
            "forecast_history_rows_captured": 0,
            "evaluation_history_rows_captured": 0,
            "baseline_history_rows_captured": 0,
            "candidate_history_rows_captured": 0,
        }
        session_duplicate_rows_skipped = [0]
        session_history_warning = False
        row_started = time.time()

        if not args.dry_run:
            queue_row["replay_status"] = "RUNNING"
            queue_row["replay_started_ts"] = _iso_now()
            queue_row["last_runner_replay_id"] = replay_id
            queue_row["last_error"] = ""
            _update_queue_rows(service, queue_headers, [queue_row])

        sessions_started += 1
        status = "COMPLETED"
        try:
            if args.dry_run:
                phase_completed = args.phase_limit
                linkage_status = "NOT_CHECKED"
                warnings.append("dry_run skipped builder execution and queue status mutation")
                if args.capture_history:
                    for phase_number in range(2, min(args.phase_limit, 7) + 1):
                        _capture_phase_history(
                            service=service,
                            active_session_id=session_id,
                            replay_id=replay_id,
                            phase_number=phase_number,
                            linkage_status="NOT_CHECKED",
                            context=context,
                            history_keys_cache=history_keys_cache,
                            history_rows_to_append=history_rows_to_append,
                            history_log_rows=history_log_rows,
                            session_history_counts=session_history_counts,
                            history_duplicate_skips=session_duplicate_rows_skipped,
                            history_dry_run=args.history_dry_run,
                        )
                    session_history_warning = True
            else:
                for phase_number in range(1, args.phase_limit + 1):
                    result = _invoke_phase(phase_number, queue_row, args.dry_run)
                    if phase_number == 1 and _norm(result.get("summary_status")) not in {"PASS", "REVIEW_NEEDED"}:
                        warnings.append(f"phase1_summary_status={_norm(result.get('summary_status'))}")
                    if phase_number >= 2 and _norm(result.get("build_status")) not in {"PASS", "PASS_WITH_WARNINGS", "SCAFFOLD_PASS"}:
                        warnings.append(f"phase{phase_number}_build_status={_norm(result.get('build_status'))}")
                    linkage_check_count += 1
                    linkage_status, linkage_error, artifact_session_ids_seen, summary_warning_sheets = _phase_linkage_check(
                        service,
                        session_id,
                        phase_number,
                    )
                    if summary_warning_sheets:
                        warnings.append(
                            f"phase{phase_number}_global_summary_not_session_scoped={','.join(summary_warning_sheets)}"
                        )
                    if linkage_status == "LINKED":
                        linkage_pass_count += 1
                        if args.capture_history and phase_number in HISTORY_PHASE_SPECS:
                            _capture_phase_history(
                                service=service,
                                active_session_id=session_id,
                                replay_id=replay_id,
                                phase_number=phase_number,
                                linkage_status=linkage_status,
                                context=context,
                                history_keys_cache=history_keys_cache,
                                history_rows_to_append=history_rows_to_append,
                                history_log_rows=history_log_rows,
                                session_history_counts=session_history_counts,
                                history_duplicate_skips=session_duplicate_rows_skipped,
                                history_dry_run=args.history_dry_run,
                            )
                        phase_completed = phase_number
                        continue
                    linkage_fail_count += 1
                    if linkage_status == "CROSS_SESSION_ARTIFACT_MISMATCH":
                        cross_session_mismatch_count += 1
                    if linkage_status == "ACTIVE_SESSION_ARTIFACT_MISSING":
                        missing_active_artifact_count += 1
                    if args.capture_history and phase_number in HISTORY_PHASE_SPECS:
                        _capture_phase_history(
                            service=service,
                            active_session_id=session_id,
                            replay_id=replay_id,
                            phase_number=phase_number,
                            linkage_status=linkage_status,
                            context=context,
                            history_keys_cache=history_keys_cache,
                            history_rows_to_append=history_rows_to_append,
                            history_log_rows=history_log_rows,
                            session_history_counts=session_history_counts,
                            history_duplicate_skips=session_duplicate_rows_skipped,
                            history_dry_run=args.history_dry_run,
                        )
                        session_history_warning = True
                    raise ReplaySessionLinkageError(
                        linkage_status=linkage_status,
                        linkage_error=linkage_error,
                        artifact_session_ids_seen=artifact_session_ids_seen,
                        failed_phase=phase_number,
                    )
                if args.phase_limit >= 7:
                    build_presignal_v2_run_status_v0(argparse.Namespace())
            sessions_completed += 1
        except ReplaySessionLinkageError as exc:
            status = "FAILED"
            errors.append(f"{exc.linkage_status}: {exc.linkage_error}")
            sessions_failed += 1
        except Exception as exc:
            status = "FAILED"
            errors.append(f"{type(exc).__name__}: {exc}")
            sessions_failed += 1

        elapsed = round(time.time() - row_started, 3)
        if args.capture_history:
            if any(_norm(row.get("capture_status")) != "CAPTURED" for row in history_log_rows if _norm(row.get("replay_id")) == replay_id and _norm(row.get("active_session_id")) == session_id):
                session_history_warning = True
            history_summary_rows.append(
                _history_summary_row(
                    replay_id=replay_id,
                    active_session_id=session_id,
                    session_history_counts=session_history_counts,
                    duplicate_rows_skipped=session_duplicate_rows_skipped[0],
                    had_capture_warning=session_history_warning or args.history_dry_run,
                )
            )
        if not args.dry_run:
            queue_row["replay_status"] = status
            queue_row["replay_completed_ts"] = _iso_now()
            queue_row["last_phase_completed"] = phase_completed
            queue_row["last_runner_replay_id"] = replay_id
            queue_row["last_error"] = linkage_status if linkage_status in {
                "CROSS_SESSION_ARTIFACT_MISMATCH",
                "ACTIVE_SESSION_ARTIFACT_MISSING",
            } else " | ".join(errors)
            _update_queue_rows(service, queue_headers, [queue_row])

        log_rows.append(
            {
                "generated_ts": _iso_now(),
                "replay_id": replay_id,
                "session_id": session_id,
                "active_session_id": session_id,
                "artifact_session_ids_seen": json.dumps(artifact_session_ids_seen),
                "linkage_status": linkage_status,
                "linkage_error": linkage_error,
                "phase_completed": phase_completed,
                "phase_limit": args.phase_limit,
                "status": "DRY_RUN" if args.dry_run and status == "COMPLETED" else status,
                "elapsed_seconds": elapsed,
                "warnings": " | ".join(warnings),
                "errors": " | ".join(errors),
            }
        )

    total_elapsed = round(time.time() - started_at, 3)
    if sessions_failed == 0:
        build_status = "PASS"
        final_interpretation = "PRESIGNAL_V2_REPLAY_READY"
    elif sessions_completed > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "PRESIGNAL_V2_REPLAY_READY"
    else:
        build_status = "FAIL"
        final_interpretation = "PRESIGNAL_V2_REPLAY_NEEDS_REVIEW"

    summary_row = {
        "generated_ts": _iso_now(),
        "replay_id": replay_id,
        "sessions_requested": len(selected_rows),
        "sessions_started": sessions_started,
        "sessions_completed": sessions_completed,
        "sessions_failed": sessions_failed,
        "phase_limit": args.phase_limit,
        "linkage_check_count": linkage_check_count,
        "linkage_pass_count": linkage_pass_count,
        "linkage_fail_count": linkage_fail_count,
        "cross_session_mismatch_count": cross_session_mismatch_count,
        "missing_active_artifact_count": missing_active_artifact_count,
        "total_elapsed": total_elapsed,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
    }

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_LOG_SHEET, log_headers, log_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
    if args.capture_history and not args.history_dry_run:
        for history_sheet, rows in history_rows_to_append.items():
            source_headers = _history_source_headers(rows)
            history_headers = _ensure_sheet(
                service,
                DIAGNOSTICS_SPREADSHEET_ID,
                history_sheet,
                list(HISTORY_METADATA_HEADERS) + source_headers,
            )
            history_headers_by_sheet[history_sheet] = history_headers
            _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, history_sheet, history_headers, rows)
        if history_log_rows:
            history_log_headers = history_headers_by_sheet.get(HISTORY_CAPTURE_LOG_SHEET) or _ensure_sheet(
                service,
                DIAGNOSTICS_SPREADSHEET_ID,
                HISTORY_CAPTURE_LOG_SHEET,
                HISTORY_LOG_HEADERS,
            )
            _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, HISTORY_CAPTURE_LOG_SHEET, history_log_headers, history_log_rows)
        if history_summary_rows:
            history_summary_headers = history_headers_by_sheet.get(HISTORY_CAPTURE_SUMMARY_SHEET) or _ensure_sheet(
                service,
                DIAGNOSTICS_SPREADSHEET_ID,
                HISTORY_CAPTURE_SUMMARY_SHEET,
                HISTORY_SUMMARY_HEADERS,
            )
            _append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, HISTORY_CAPTURE_SUMMARY_SHEET, history_summary_headers, history_summary_rows)
    registry_result = _upsert_registry_rows_with_retry(service)

    capture_totals = {
        "attention_history_rows_captured": sum(_safe_int(row.get("attention_history_rows_captured")) for row in history_summary_rows),
        "information_history_rows_captured": sum(_safe_int(row.get("information_history_rows_captured")) for row in history_summary_rows),
        "forecast_history_rows_captured": sum(_safe_int(row.get("forecast_history_rows_captured")) for row in history_summary_rows),
        "evaluation_history_rows_captured": sum(_safe_int(row.get("evaluation_history_rows_captured")) for row in history_summary_rows),
        "baseline_history_rows_captured": sum(_safe_int(row.get("baseline_history_rows_captured")) for row in history_summary_rows),
        "candidate_history_rows_captured": sum(_safe_int(row.get("candidate_history_rows_captured")) for row in history_summary_rows),
        "duplicate_rows_skipped": sum(_safe_int(row.get("duplicate_rows_skipped")) for row in history_summary_rows),
    }
    if args.capture_history:
        if args.history_dry_run:
            history_capture_final_interpretation = "REPLAY_HISTORY_CAPTURE_READY_WITH_WARNINGS"
        elif any(_norm(row.get("final_interpretation")) == "REPLAY_HISTORY_CAPTURE_FAILED" for row in history_summary_rows):
            history_capture_final_interpretation = "REPLAY_HISTORY_CAPTURE_FAILED"
        elif any(_norm(row.get("final_interpretation")) == "REPLAY_HISTORY_CAPTURE_READY_WITH_WARNINGS" for row in history_summary_rows):
            history_capture_final_interpretation = "REPLAY_HISTORY_CAPTURE_READY_WITH_WARNINGS"
        else:
            history_capture_final_interpretation = "REPLAY_HISTORY_CAPTURE_READY"
    else:
        history_capture_final_interpretation = ""

    return {
        "replay_id": replay_id,
        "sessions_requested": len(selected_rows),
        "sessions_started": sessions_started,
        "sessions_completed": sessions_completed,
        "sessions_failed": sessions_failed,
        "phase_limit": args.phase_limit,
        "total_elapsed": total_elapsed,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "capture_history": args.capture_history,
        "history_dry_run": args.history_dry_run,
        "history_capture_final_interpretation": history_capture_final_interpretation,
        "history_capture_counts": capture_totals,
        "history_capture_rows_written": len(history_log_rows),
        "registry_result": registry_result,
        "sample_log_row": log_rows[0] if log_rows else {},
        "sample_history_summary_row": history_summary_rows[0] if history_summary_rows else {},
    }


def main() -> None:
    print(json.dumps(build_presignal_v2_replay_runner_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
