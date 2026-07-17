import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    _sheet_to_rows,
    _write_rows,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


REPLAY_LOG_SHEET = "PreSignal_v2_Replay_Run_Log"
REPLAY_SUMMARY_SHEET = "PreSignal_v2_Replay_Run_Summary"
ATTENTION_MAP_SHEET = "Session_Attention_Map"
ATTENTION_SUMMARY_SHEET = "Session_Attention_Summary"
ATTENTION_AUDIT_SHEET = "Session_Attention_Provider_Response_Audit"
INFO_SUMMARY_SHEET = "Session_Information_Request_Summary"
FORECAST_SUMMARY_SHEET = "Session_Forecast_Summary"
REPLAY_QUEUE_SHEET = "PreSignal_v2_Replay_Queue"

OUTPUT_DIAGNOSTIC_SHEET = "Replay_Failure_Diagnostics"
OUTPUT_SUMMARY_SHEET = "Replay_Failure_Summary"

SCHEMA_VERSION = "presignal_v2_replay_failure_diagnostics_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

DIAGNOSTIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "session_id",
    "phase_failed",
    "failure_category",
    "failure_reason",
    "providers_attempted",
    "providers_succeeded",
    "providers_failed",
    "usable_provider_count",
    "attention_rows",
    "summary_build_status",
    "summary_final_interpretation",
    "recommended_runner_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "sessions_analyzed",
    "phase2_warning_count",
    "transport_failure_count",
    "contract_failure_count",
    "provider_failure_count",
    "schema_failure_count",
    "recommended_continue_count",
    "recommended_stop_count",
    "build_status",
    "final_interpretation",
    "notes",
]


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _join_unique(values: Iterable[Any]) -> str:
    seen = set()
    out: List[str] = []
    for value in values:
        text = _norm(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return "|".join(out)


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _latest_by_session(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _norm(row.get("session_id")),
            _norm(row.get("generated_ts")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )
    latest: Dict[str, Dict[str, Any]] = {}
    for row in ordered:
        session_id = _norm(row.get("session_id"))
        if session_id:
            latest[session_id] = row
    return latest


def _latest_audit_by_provider(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _norm(row.get("provider")),
            _safe_int(row.get("attempt_number")),
            _norm(row.get("generated_ts")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )
    latest: Dict[str, Dict[str, Any]] = {}
    for row in ordered:
        provider = _norm(row.get("provider"))
        if provider:
            latest[provider] = row
    return latest


def _latest_row(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {}
    return sorted(
        rows,
        key=lambda row: (
            _norm(row.get("generated_ts")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )[-1]


def _provider_success(row: Dict[str, Any]) -> bool:
    notes = _norm(row.get("notes")).lower()
    contract_status = _norm(row.get("contract_status")).lower()
    response_status = _norm(row.get("response_status")).lower()
    parse_status = _norm(row.get("parse_status")).lower()
    if "success=true" in notes:
        return True
    if response_status == "ok" and parse_status in {"parsed_as_is", "parsed_recovered"} and contract_status in {
        "",
        "ok",
        "valid",
        "valid_provider_mismatch_tolerated",
    }:
        return True
    return False


def _transport_error(row: Dict[str, Any]) -> bool:
    text = " ".join(
        [
            _norm(row.get("error_type")).lower(),
            _norm(row.get("error_message")).lower(),
            _norm(row.get("response_status")).lower(),
            _norm(row.get("retry_status")).lower(),
        ]
    )
    return any(
        token in text
        for token in [
            "503",
            "502",
            "504",
            "rate_limit",
            "temporarily_unavailable",
            "service_unavailable",
            "deadline_exceeded",
            "timeout",
            "connection reset",
            "transient_provider_error",
        ]
    )


def _parse_error(row: Dict[str, Any]) -> bool:
    parse_status = _norm(row.get("parse_status")).lower()
    error_type = _norm(row.get("error_type")).lower()
    return ("parse" in parse_status and parse_status not in {"parsed_as_is", "parsed_recovered"}) or "parse" in error_type


def _contract_error(row: Dict[str, Any]) -> bool:
    contract_status = _norm(row.get("contract_status")).lower()
    if not contract_status:
        return False
    return contract_status not in {"ok", "valid", "valid_provider_mismatch_tolerated"}


def _provider_error(row: Dict[str, Any]) -> bool:
    return _norm(row.get("response_status")).lower() == "provider_error" or _norm(row.get("request_status")).lower() == "provider_error"


def _phase_failed(log_row: Dict[str, Any]) -> str:
    if _norm(log_row.get("status")) != "FAILED":
        return ""
    completed = _safe_int(log_row.get("phase_completed"))
    errors = _norm(log_row.get("errors"))
    if "Session_Attention_Summary is not ready" in errors:
        return "Phase 3"
    if completed <= 0:
        return "Phase 1"
    return f"Phase {completed + 1}"


def _failure_category(
    log_row: Dict[str, Any],
    summary_row: Dict[str, Any],
    audit_rows: Sequence[Dict[str, Any]],
    session_attention_rows: Sequence[Dict[str, Any]],
    other_attention_sessions: Sequence[str],
    usable_provider_count: int,
    attention_rows: int,
) -> Tuple[str, str]:
    errors = _norm(log_row.get("errors"))
    summary_build_status = _norm(summary_row.get("build_status"))
    summary_interp = _norm(summary_row.get("final_interpretation"))
    transport_count = sum(1 for row in audit_rows if _transport_error(row))
    parse_count = sum(1 for row in audit_rows if _parse_error(row))
    contract_count = sum(1 for row in audit_rows if _contract_error(row))
    provider_count = sum(1 for row in audit_rows if _provider_error(row))
    omission_count = sum(_safe_int(row.get("omitted_event_count")) for row in audit_rows)

    if attention_rows == 0 and not audit_rows and other_attention_sessions:
        return (
            "structural_sheet_problem",
            "Phase 2 artifacts exist, but they are linked to different session_ids than the replay session under review.",
        )
    if "Session_Attention_Summary is not ready" in errors:
        if usable_provider_count >= 2 and attention_rows > 0 and contract_count > 0 and transport_count == 0 and parse_count == 0:
            return "summary_gating", "Phase 3 was blocked by a Phase 2 summary gate after partial provider success."
        return "summary_gating", "Phase 3 was blocked because Phase 2 did not meet its summary readiness gate."
    if transport_count > 0:
        return "transport_failure", "Replay warning/failure evidence points to transient provider transport issues."
    if parse_count > 0:
        return "parse_failure", "Replay warning/failure evidence points to provider parse issues."
    if contract_count > 0:
        return "contract_failure", "Replay warning/failure evidence points to provider contract/schema issues."
    if provider_count > 0:
        return "provider_failure", "Replay warning/failure evidence points to provider-side errors."
    if attention_rows == 0:
        return "missing_rows", "No attention rows were written for the replay session."
    if summary_build_status == "PASS_WITH_WARNINGS" or "NEEDS_REVIEW" in summary_interp:
        if omission_count > 0:
            return "provider_warning", "Attention summary is warning due to omission/provider coverage concerns."
        return "provider_warning", "Attention summary is warning despite structural sheet output being present."
    return "other", "No single dominant failure category could be isolated from current evidence."


def _recommended_action(
    category: str,
    providers_succeeded: int,
    providers_attempted: int,
    usable_provider_count: int,
    attention_rows: int,
    summary_build_status: str,
    summary_final_interpretation: str,
) -> str:
    if category == "transport_failure":
        return "RETRY_TRANSPORT"
    if category == "provider_failure":
        return "RETRY_PROVIDER"
    if category == "parse_failure":
        return "NEEDS_MANUAL_REVIEW"
    if category == "contract_failure":
        return "NEEDS_MANUAL_REVIEW"
    if category == "structural_sheet_problem":
        return "STOP_REPLAY"
    if category == "summary_gating":
        if usable_provider_count >= 2 and attention_rows > 0 and providers_succeeded >= 2 and "NEEDS_REVIEW" in summary_final_interpretation:
            return "ALLOW_PHASE3"
        return "STOP_REPLAY"
    if category in {"missing_rows", "schema_failure"}:
        return "STOP_REPLAY"
    if summary_build_status == "PASS_WITH_WARNINGS" and providers_attempted > 0 and providers_succeeded == providers_attempted:
        return "ALLOW_PHASE3"
    return "NEEDS_MANUAL_REVIEW"


def _ensure_registry(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "REPLAY_FAILURE_DIAGNOSTICS",
            "physical_sheet_name": OUTPUT_DIAGNOSTIC_SHEET,
            "sheet_role": "v2_replay_failure_diagnostics",
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
            "created_phase": "PreSignal v2.0 Phase 7.5D",
            "notes": "shadow_v0 replay failure diagnostics",
        },
        {
            "logical_sheet_id": "REPLAY_FAILURE_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_replay_failure_summary",
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
            "created_phase": "PreSignal v2.0 Phase 7.5D",
            "notes": "shadow_v0 replay failure summary",
        },
    ]
    for row in registry_rows:
        key = _upper(row["logical_sheet_id"])
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


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build replay failure diagnostics from existing replay artifacts.")
    return parser.parse_args(argv)


def build_presignal_v2_replay_failure_diagnostics_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()

    replay_log_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, REPLAY_LOG_SHEET)
    replay_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, REPLAY_SUMMARY_SHEET)
    attention_map_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, ATTENTION_MAP_SHEET)
    attention_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, ATTENTION_SUMMARY_SHEET)
    attention_audit_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, ATTENTION_AUDIT_SHEET)
    info_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INFO_SUMMARY_SHEET)
    forecast_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, FORECAST_SUMMARY_SHEET)
    replay_queue_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, REPLAY_QUEUE_SHEET)
    _ = replay_summary_rows, info_summary_rows, forecast_summary_rows, replay_queue_rows

    _require_headers(REPLAY_LOG_SHEET, replay_log_rows, ["session_id", "phase_completed", "status", "errors"])
    _require_headers(REPLAY_SUMMARY_SHEET, replay_summary_rows, ["replay_id", "build_status", "final_interpretation"])
    _require_headers(ATTENTION_MAP_SHEET, attention_map_rows, ["session_id", "provider"])
    _require_headers(ATTENTION_SUMMARY_SHEET, attention_summary_rows, ["build_status", "final_interpretation", "providers_attempted", "providers_succeeded", "providers_failed"])
    _require_headers(
        ATTENTION_AUDIT_SHEET,
        attention_audit_rows,
        ["session_id", "provider", "response_status", "parse_status", "contract_status", "error_type", "error_message", "omitted_event_count", "notes"],
    )
    _require_headers(REPLAY_QUEUE_SHEET, replay_queue_rows, ["session_id", "replay_status"])

    diagnostic_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DIAGNOSTIC_SHEET, DIAGNOSTIC_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    latest_logs = _latest_by_session(replay_log_rows)
    attention_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in attention_map_rows:
        attention_by_session[_norm(row.get("session_id"))].append(row)
    audit_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in attention_audit_rows:
        audit_by_session[_norm(row.get("session_id"))].append(row)

    attention_summary_row = _latest_row(attention_summary_rows)
    diagnostic_rows: List[Dict[str, Any]] = []
    counters = Counter()

    for session_id, log_row in sorted(latest_logs.items()):
        session_attention_rows = attention_by_session.get(session_id, [])
        session_audits = audit_by_session.get(session_id, [])
        latest_provider_rows = _latest_audit_by_provider(session_audits)
        attention_providers = {_norm(row.get("provider")) for row in session_attention_rows if _norm(row.get("provider"))}
        if latest_provider_rows:
            providers_attempted = len(latest_provider_rows)
            providers_succeeded = sum(1 for row in latest_provider_rows.values() if _provider_success(row))
        elif attention_providers:
            providers_attempted = len(attention_providers)
            providers_succeeded = len(attention_providers)
        else:
            providers_attempted = 0
            providers_succeeded = 0
        providers_failed = max(0, providers_attempted - providers_succeeded)
        usable_provider_count = providers_succeeded
        attention_rows = len(session_attention_rows)
        summary_build_status = _norm(attention_summary_row.get("build_status"))
        summary_final_interpretation = _norm(attention_summary_row.get("final_interpretation"))
        other_attention_sessions = sorted(
            seen_session_id
            for seen_session_id in attention_by_session
            if seen_session_id and seen_session_id != session_id and attention_by_session.get(seen_session_id)
        )

        phase_failed = _phase_failed(log_row)
        category, category_reason = _failure_category(
            log_row,
            attention_summary_row,
            list(latest_provider_rows.values()),
            session_attention_rows,
            other_attention_sessions,
            usable_provider_count,
            attention_rows,
        )
        if not phase_failed:
            if category in {
                "summary_gating",
                "transport_failure",
                "parse_failure",
                "contract_failure",
                "provider_failure",
                "missing_rows",
                "structural_sheet_problem",
                "provider_warning",
            }:
                phase_failed = "Phase 2"
        failure_reason = _norm(log_row.get("errors")) or category_reason
        recommended_action = _recommended_action(
            category,
            providers_succeeded,
            providers_attempted,
            usable_provider_count,
            attention_rows,
            summary_build_status,
            summary_final_interpretation,
        )

        provider_warning_ratio = round(providers_failed / providers_attempted, 4) if providers_attempted else 0
        notes = [
            f"provider_warning_ratio={provider_warning_ratio}",
            f"attention_audit_rows={len(session_audits)}",
            f"attention_summary_notes={_norm(attention_summary_row.get('notes'))}",
        ]
        if other_attention_sessions and attention_rows == 0:
            notes.append(f"attention_sessions_present={json.dumps(other_attention_sessions)}")
        if category == "summary_gating" and recommended_action == "ALLOW_PHASE3":
            notes.append("evidence shows 2 usable providers and non-empty attention rows despite one provider contract failure")

        diagnostic_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "session_id": session_id,
                "phase_failed": phase_failed,
                "failure_category": category,
                "failure_reason": _norm(failure_reason),
                "providers_attempted": providers_attempted,
                "providers_succeeded": providers_succeeded,
                "providers_failed": providers_failed,
                "usable_provider_count": usable_provider_count,
                "attention_rows": attention_rows,
                "summary_build_status": summary_build_status,
                "summary_final_interpretation": summary_final_interpretation,
                "recommended_runner_action": recommended_action,
                "notes": " | ".join(notes),
            }
        )

        if summary_build_status == "PASS_WITH_WARNINGS" or "NEEDS_REVIEW" in summary_final_interpretation:
            counters["phase2_warning_count"] += 1
        if category == "transport_failure":
            counters["transport_failure_count"] += 1
        if category == "contract_failure" or any(_contract_error(row) for row in latest_provider_rows.values()):
            counters["contract_failure_count"] += 1
        if category == "provider_failure" or any(_provider_error(row) for row in latest_provider_rows.values()):
            counters["provider_failure_count"] += 1
        if category in {"schema_failure", "missing_rows", "structural_sheet_problem"}:
            counters["schema_failure_count"] += 1
        if recommended_action in {"ALLOW_PHASE3", "RETRY_PROVIDER", "RETRY_TRANSPORT"}:
            counters["recommended_continue_count"] += 1
        if recommended_action == "STOP_REPLAY":
            counters["recommended_stop_count"] += 1

    if diagnostic_rows:
        build_status = "PASS"
        final_interpretation = "REPLAY_FAILURE_DIAGNOSTICS_READY"
    else:
        build_status = "FAIL"
        final_interpretation = "REPLAY_FAILURE_DIAGNOSTICS_NEEDS_REVIEW"

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "sessions_analyzed": len(diagnostic_rows),
        "phase2_warning_count": counters.get("phase2_warning_count", 0),
        "transport_failure_count": counters.get("transport_failure_count", 0),
        "contract_failure_count": counters.get("contract_failure_count", 0),
        "provider_failure_count": counters.get("provider_failure_count", 0),
        "schema_failure_count": counters.get("schema_failure_count", 0),
        "recommended_continue_count": counters.get("recommended_continue_count", 0),
        "recommended_stop_count": counters.get("recommended_stop_count", 0),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "notes": _join_unique(row.get("failure_category") for row in diagnostic_rows),
    }

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DIAGNOSTIC_SHEET, diagnostic_headers, diagnostic_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
    registry_result = _ensure_registry(service)

    return {
        "sessions_analyzed": len(diagnostic_rows),
        "failure_categories": dict(Counter(_norm(row.get("failure_category")) for row in diagnostic_rows)),
        "provider_failures": counters.get("provider_failure_count", 0),
        "transport_failures": counters.get("transport_failure_count", 0),
        "recommended_continue_count": counters.get("recommended_continue_count", 0),
        "recommended_stop_count": counters.get("recommended_stop_count", 0),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "registry_result": registry_result,
        "sample_diagnostic_row": diagnostic_rows[0] if diagnostic_rows else {},
    }


def main() -> None:
    print(json.dumps(build_presignal_v2_replay_failure_diagnostics_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
