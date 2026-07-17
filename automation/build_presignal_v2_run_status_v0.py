import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
from automation.build_session_information_requests_v0 import _iso_now, _normalize_provider_name, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE1_SUMMARY_SHEET = "Market_Session_Shadow_Summary"

PHASE2_MAP_SHEET = "Session_Attention_Map"
PHASE2_SUMMARY_SHEET = "Session_Attention_Summary"

PHASE3_REQUEST_SHEET = "Session_Information_Requests"
PHASE3_LIBRARY_SHEET = "Information_Requirement_Library"
PHASE3_SUMMARY_SHEET = "Session_Information_Request_Summary"

PHASE4_FORECAST_SHEET = "Session_Forecasts"
PHASE4_SUMMARY_SHEET = "Session_Forecast_Summary"

PHASE5_EVALUATION_SHEET = "Session_Evaluation"
PHASE5_SUMMARY_SHEET = "Session_Evaluation_Summary"

PHASE6_COMPARE_SHEET = "Session_vs_Event_Baseline_Compare"
PHASE6_SUMMARY_SHEET = "Session_Baseline_Compare_Summary"
PHASE6_AUDIT_SHEET = "Session_Baseline_Event_Link_Audit"

PHASE7_CANDIDATE_SHEET = "Market_State_Pack_Candidates"
PHASE7_BACKLOG_SHEET = "Market_State_Pack_Acquisition_Backlog"
PHASE7_SUMMARY_SHEET = "Market_State_Pack_Candidate_Summary"

OUTPUT_STATUS_SHEET = "PreSignal_v2_Run_Status"
OUTPUT_SUMMARY_SHEET = "PreSignal_v2_Phase_Readiness_Summary"

SCHEMA_VERSION = "presignal_v2_run_status_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

STATUS_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "phase1_market_session_status",
    "phase1_member_event_count",
    "phase1_final_interpretation",
    "phase2_attention_status",
    "phase2_provider_count",
    "phase2_attention_rows",
    "phase2_final_interpretation",
    "phase3_information_status",
    "phase3_request_rows",
    "phase3_library_rows",
    "phase3_final_interpretation",
    "phase4_forecast_status",
    "phase4_forecast_rows",
    "phase4_provider_count",
    "phase4_final_interpretation",
    "phase5_evaluation_status",
    "phase5_evaluation_rows",
    "phase5_direction_ok_count",
    "phase5_overall_ok_count",
    "phase5_final_interpretation",
    "phase6_baseline_status",
    "phase6_compare_rows",
    "phase6_comparison_labels",
    "phase6_final_interpretation",
    "phase7_candidate_status",
    "phase7_candidate_rows",
    "phase7_backlog_rows",
    "phase7_quantitative_direct_count",
    "phase7_quantitative_derived_count",
    "phase7_qualitative_source_grounded_count",
    "phase7_qualitative_interpretive_count",
    "phase7_backtest_safe_candidate_count",
    "phase7_high_bias_risk_count",
    "phase7_final_interpretation",
    "overall_v2_pipeline_status",
    "phase8_readiness_status",
    "phase8_readiness_reason",
    "recommended_next_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "build_status",
    "final_interpretation",
    "sessions_total",
    "sessions_with_phase1",
    "sessions_with_phase2",
    "sessions_with_phase3",
    "sessions_with_phase4",
    "sessions_with_phase5",
    "sessions_with_phase6",
    "sessions_with_phase7",
    "sessions_complete_through_phase7",
    "total_member_events",
    "total_attention_rows",
    "total_information_request_rows",
    "total_forecast_rows",
    "total_evaluation_rows",
    "total_baseline_compare_rows",
    "total_candidate_rows",
    "total_backlog_rows",
    "candidate_quantitative_direct_count",
    "candidate_quantitative_derived_count",
    "candidate_qualitative_source_grounded_count",
    "candidate_qualitative_interpretive_count",
    "candidate_backtest_safe_count",
    "candidate_high_bias_risk_count",
    "repeated_candidate_count",
    "multi_provider_candidate_count",
    "multi_session_candidate_count",
    "phase8_ready_session_count",
    "phase8_not_ready_session_count",
    "recommended_next_action",
    "governance_forbidden_write_count",
    "input_missing_count",
    "warning_count",
    "error_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


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


def _canonical_slug(value: Any) -> str:
    text = _norm(value).lower()
    out = []
    previous_was_sep = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            previous_was_sep = False
        elif not previous_was_sep:
            out.append("_")
            previous_was_sep = True
    return "".join(out).strip("_")


def _request_information_key(row: Dict[str, Any]) -> str:
    existing = _norm(row.get("information_key"))
    if existing:
        return existing
    category = _norm(row.get("information_category")).lower() or "other"
    return f"{category}|{_canonical_slug(row.get('requested_information'))}"


def _summary_interpretation(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    return _norm(rows[0].get("final_interpretation"))


def _summary_build_status(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    return _norm(rows[0].get("build_status"))


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _group_by_session(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        session_id = _norm(row.get("session_id"))
        if session_id:
            out[session_id].append(row)
    return out


def _candidate_repeat_counts(candidate_rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    repeated = 0
    multi_provider = 0
    multi_session = 0
    for row in candidate_rows:
        if _safe_int(row.get("request_count")) >= 2:
            repeated += 1
        if _safe_int(row.get("provider_count")) >= 2:
            multi_provider += 1
        if _safe_int(row.get("session_count")) >= 2:
            multi_session += 1
    return {
        "repeated_candidate_count": repeated,
        "multi_provider_candidate_count": multi_provider,
        "multi_session_candidate_count": multi_session,
    }


def _phase8_readiness(
    sessions_complete_through_phase7: int,
    repeated_candidate_count: int,
    multi_provider_candidate_count: int,
    multi_session_candidate_count: int,
) -> Tuple[str, str, str]:
    if sessions_complete_through_phase7 < 3:
        return (
            "NOT_READY_TOO_FEW_SESSIONS",
            "Fewer than 3 sessions have completed through Phase 7.",
            "Accumulate more completed sessions before any acquisition planning.",
        )
    if repeated_candidate_count == 0:
        return (
            "NOT_READY_TOO_FEW_REPEATED_REQUESTS",
            "No candidate has repeated request_count >= 2 yet.",
            "Wait for repeated information needs before acquisition planning.",
        )
    if multi_provider_candidate_count == 0:
        return (
            "NOT_READY_CANDIDATE_LIMITATIONS",
            "No candidate has multi-provider evidence yet.",
            "Gather more provider overlap before acquisition planning.",
        )
    if multi_session_candidate_count == 0:
        return (
            "REVIEW_READY",
            "Repeated candidates exist, but they are not yet observed across multiple sessions.",
            "Run a Phase 8A source audit before any limited acquisition discussion.",
        )
    return (
        "READY_FOR_PHASE8A_SOURCE_AUDIT",
        "Repeated candidates have both multi-provider and multi-session support.",
        "Proceed to a conservative Phase 8A source audit only.",
    )


def _overall_pipeline_status(
    phase_present: Dict[str, bool],
    phase_interpretations: Dict[str, str],
) -> str:
    if not phase_present["phase1"]:
        return "FAILED"
    if not all(phase_present.values()):
        return "INCOMPLETE"
    interpretations = " ".join(phase_interpretations.values()).upper()
    if "FAILED" in interpretations or "BLOCKED" in interpretations:
        return "FAILED"
    if "NEEDS_REVIEW" in interpretations or "WITH_LIMITATIONS" in interpretations or "WARN" in interpretations:
        return "READY_WITH_LIMITATIONS"
    return "READY"


def _validate_inputs(data: Dict[str, Sequence[Dict[str, Any]]]) -> None:
    _require_headers(PHASE1_SESSION_SHEET, data[PHASE1_SESSION_SHEET], ["session_id", "session_date", "country", "session_window_name"])
    _require_headers(PHASE1_MEMBER_SHEET, data[PHASE1_MEMBER_SHEET], ["session_id", "event_id"])
    _require_headers(PHASE1_SUMMARY_SHEET, data[PHASE1_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE2_MAP_SHEET, data[PHASE2_MAP_SHEET], ["session_id", "provider"])
    _require_headers(PHASE2_SUMMARY_SHEET, data[PHASE2_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE3_REQUEST_SHEET, data[PHASE3_REQUEST_SHEET], ["session_id", "provider", "requested_information", "information_category"])
    _require_headers(PHASE3_LIBRARY_SHEET, data[PHASE3_LIBRARY_SHEET], ["information_key"])
    _require_headers(PHASE3_SUMMARY_SHEET, data[PHASE3_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE4_FORECAST_SHEET, data[PHASE4_FORECAST_SHEET], ["session_id", "provider"])
    _require_headers(PHASE4_SUMMARY_SHEET, data[PHASE4_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE5_EVALUATION_SHEET, data[PHASE5_EVALUATION_SHEET], ["session_id", "provider", "direction_ok", "overall_ok"])
    _require_headers(PHASE5_SUMMARY_SHEET, data[PHASE5_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE6_COMPARE_SHEET, data[PHASE6_COMPARE_SHEET], ["session_id", "provider", "comparison_label"])
    _require_headers(PHASE6_SUMMARY_SHEET, data[PHASE6_SUMMARY_SHEET], ["build_status", "final_interpretation"])
    _require_headers(PHASE6_AUDIT_SHEET, data[PHASE6_AUDIT_SHEET], ["session_id", "provider"])
    _require_headers(PHASE7_CANDIDATE_SHEET, data[PHASE7_CANDIDATE_SHEET], ["information_key", "request_count", "provider_count", "session_count"])
    _require_headers(PHASE7_BACKLOG_SHEET, data[PHASE7_BACKLOG_SHEET], ["candidate_id", "information_key"])
    _require_headers(PHASE7_SUMMARY_SHEET, data[PHASE7_SUMMARY_SHEET], ["build_status", "final_interpretation"])


def _upsert_registry_rows(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates = []
    appended = 0

    registry_rows = [
        {
            "logical_sheet_id": "PRESIGNAL_V2_RUN_STATUS",
            "physical_sheet_name": OUTPUT_STATUS_SHEET,
            "sheet_role": "v2_pipeline_session_status",
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
            "created_phase": "PreSignal v2.0 Post-Phase 7",
            "notes": "shadow_v0 v2 pipeline session status",
        },
        {
            "logical_sheet_id": "PRESIGNAL_V2_PHASE_READINESS_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_pipeline_readiness_summary",
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
            "created_phase": "PreSignal v2.0 Post-Phase 7",
            "notes": "shadow_v0 v2 pipeline readiness summary",
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


def build_presignal_v2_run_status_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = argparse.Namespace()

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    generated_ts = _iso_now()

    sheet_names = [
        PHASE1_SESSION_SHEET,
        PHASE1_MEMBER_SHEET,
        PHASE1_SUMMARY_SHEET,
        PHASE2_MAP_SHEET,
        PHASE2_SUMMARY_SHEET,
        PHASE3_REQUEST_SHEET,
        PHASE3_LIBRARY_SHEET,
        PHASE3_SUMMARY_SHEET,
        PHASE4_FORECAST_SHEET,
        PHASE4_SUMMARY_SHEET,
        PHASE5_EVALUATION_SHEET,
        PHASE5_SUMMARY_SHEET,
        PHASE6_COMPARE_SHEET,
        PHASE6_SUMMARY_SHEET,
        PHASE6_AUDIT_SHEET,
        PHASE7_CANDIDATE_SHEET,
        PHASE7_BACKLOG_SHEET,
        PHASE7_SUMMARY_SHEET,
    ]
    data = {sheet: _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in sheet_names}
    _validate_inputs(data)

    status_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_STATUS_SHEET, STATUS_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    sessions = data[PHASE1_SESSION_SHEET]
    members_by_session = _group_by_session(data[PHASE1_MEMBER_SHEET])
    attention_by_session = _group_by_session(data[PHASE2_MAP_SHEET])
    requests_by_session = _group_by_session(data[PHASE3_REQUEST_SHEET])
    forecasts_by_session = _group_by_session(data[PHASE4_FORECAST_SHEET])
    evaluations_by_session = _group_by_session(data[PHASE5_EVALUATION_SHEET])
    compare_by_session = _group_by_session(data[PHASE6_COMPARE_SHEET])

    phase1_interp = _summary_interpretation(data[PHASE1_SUMMARY_SHEET])
    phase2_interp = _summary_interpretation(data[PHASE2_SUMMARY_SHEET])
    phase3_interp = _summary_interpretation(data[PHASE3_SUMMARY_SHEET])
    phase4_interp = _summary_interpretation(data[PHASE4_SUMMARY_SHEET])
    phase5_interp = _summary_interpretation(data[PHASE5_SUMMARY_SHEET])
    phase6_interp = _summary_interpretation(data[PHASE6_SUMMARY_SHEET])
    phase7_interp = _summary_interpretation(data[PHASE7_SUMMARY_SHEET])

    candidate_rows = data[PHASE7_CANDIDATE_SHEET]
    backlog_rows = data[PHASE7_BACKLOG_SHEET]
    repeat_counts = _candidate_repeat_counts(candidate_rows)

    candidate_by_key = {_norm(row.get("information_key")): row for row in candidate_rows if _norm(row.get("information_key"))}
    backlog_keys = {_norm(row.get("information_key")) for row in backlog_rows if _norm(row.get("information_key"))}

    status_rows: List[Dict[str, Any]] = []
    phase8_ready_session_count = 0
    phase8_not_ready_session_count = 0
    warning_count = 0
    complete_through_phase7 = 0

    sessions_complete_global = len(sessions)
    global_phase8_status, global_phase8_reason, global_next_action = _phase8_readiness(
        sessions_complete_global,
        repeat_counts["repeated_candidate_count"],
        repeat_counts["multi_provider_candidate_count"],
        repeat_counts["multi_session_candidate_count"],
    )

    for session_row in sessions:
        session_id = _norm(session_row.get("session_id"))
        session_requests = requests_by_session.get(session_id, [])
        request_keys = {_request_information_key(row) for row in session_requests if _request_information_key(row)}
        linked_candidates = [candidate_by_key[key] for key in sorted(request_keys) if key in candidate_by_key]
        linked_backlog_count = sum(1 for key in request_keys if key in backlog_keys)

        phase_present = {
            "phase1": bool(session_id),
            "phase2": bool(attention_by_session.get(session_id)),
            "phase3": bool(session_requests),
            "phase4": bool(forecasts_by_session.get(session_id)),
            "phase5": bool(evaluations_by_session.get(session_id)),
            "phase6": bool(compare_by_session.get(session_id)),
            "phase7": bool(linked_candidates),
        }
        phase_interpretations = {
            "phase1": phase1_interp,
            "phase2": phase2_interp,
            "phase3": phase3_interp,
            "phase4": phase4_interp,
            "phase5": phase5_interp,
            "phase6": phase6_interp,
            "phase7": phase7_interp,
        }

        if all(phase_present.values()):
            complete_through_phase7 += 1

        comparison_labels = _join_unique(row.get("comparison_label") for row in compare_by_session.get(session_id, []))
        overall_status = _overall_pipeline_status(phase_present, phase_interpretations)
        if overall_status in {"READY_WITH_LIMITATIONS", "NEEDS_REVIEW"}:
            warning_count += 1

        if global_phase8_status.startswith("READY_") or global_phase8_status == "REVIEW_READY":
            phase8_ready_session_count += 1
        else:
            phase8_not_ready_session_count += 1

        notes = []
        if linked_candidates:
            notes.append("phase7 counts derived from candidate keys linked through session information requests")
        else:
            notes.append("phase7 linkage unavailable because session has no linked request-derived information keys")
        if global_phase8_status == "NOT_READY_TOO_FEW_SESSIONS":
            notes.append("global readiness constrained by fewer than 3 complete sessions")

        status_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "session_id": session_id,
                "session_date": _norm(session_row.get("session_date")),
                "country": _norm(session_row.get("country")),
                "session_window_name": _norm(session_row.get("session_window_name")),
                "phase1_market_session_status": "BUILT" if phase_present["phase1"] else "MISSING",
                "phase1_member_event_count": len(members_by_session.get(session_id, [])),
                "phase1_final_interpretation": phase1_interp,
                "phase2_attention_status": "AVAILABLE" if phase_present["phase2"] else "MISSING",
                "phase2_provider_count": len({_normalize_provider_name(row.get("provider")) for row in attention_by_session.get(session_id, []) if _normalize_provider_name(row.get("provider"))}),
                "phase2_attention_rows": len(attention_by_session.get(session_id, [])),
                "phase2_final_interpretation": phase2_interp,
                "phase3_information_status": "AVAILABLE" if phase_present["phase3"] else "MISSING",
                "phase3_request_rows": len(session_requests),
                "phase3_library_rows": len(request_keys),
                "phase3_final_interpretation": phase3_interp,
                "phase4_forecast_status": "AVAILABLE" if phase_present["phase4"] else "MISSING",
                "phase4_forecast_rows": len(forecasts_by_session.get(session_id, [])),
                "phase4_provider_count": len({_normalize_provider_name(row.get("provider")) for row in forecasts_by_session.get(session_id, []) if _normalize_provider_name(row.get("provider"))}),
                "phase4_final_interpretation": phase4_interp,
                "phase5_evaluation_status": "AVAILABLE" if phase_present["phase5"] else "MISSING",
                "phase5_evaluation_rows": len(evaluations_by_session.get(session_id, [])),
                "phase5_direction_ok_count": sum(1 for row in evaluations_by_session.get(session_id, []) if _as_bool(row.get("direction_ok"))),
                "phase5_overall_ok_count": sum(1 for row in evaluations_by_session.get(session_id, []) if _as_bool(row.get("overall_ok"))),
                "phase5_final_interpretation": phase5_interp,
                "phase6_baseline_status": "AVAILABLE" if phase_present["phase6"] else "MISSING",
                "phase6_compare_rows": len(compare_by_session.get(session_id, [])),
                "phase6_comparison_labels": comparison_labels,
                "phase6_final_interpretation": phase6_interp,
                "phase7_candidate_status": "LINKED" if phase_present["phase7"] else "UNLINKED",
                "phase7_candidate_rows": len(linked_candidates),
                "phase7_backlog_rows": linked_backlog_count,
                "phase7_quantitative_direct_count": sum(1 for row in linked_candidates if _norm(row.get("information_class")) == "quantitative_direct"),
                "phase7_quantitative_derived_count": sum(1 for row in linked_candidates if _norm(row.get("information_class")) == "quantitative_derived"),
                "phase7_qualitative_source_grounded_count": sum(1 for row in linked_candidates if _norm(row.get("information_class")) == "qualitative_source_grounded"),
                "phase7_qualitative_interpretive_count": sum(1 for row in linked_candidates if _norm(row.get("information_class")) == "qualitative_interpretive"),
                "phase7_backtest_safe_candidate_count": sum(1 for row in linked_candidates if _as_bool(row.get("backtest_safe_candidate"))),
                "phase7_high_bias_risk_count": sum(1 for row in linked_candidates if _norm(row.get("risk_of_provider_bias")).lower() == "high"),
                "phase7_final_interpretation": phase7_interp,
                "overall_v2_pipeline_status": overall_status,
                "phase8_readiness_status": global_phase8_status,
                "phase8_readiness_reason": global_phase8_reason,
                "recommended_next_action": global_next_action,
                "notes": _truncate_text("; ".join(notes), 240),
            }
        )

    total_candidate_rows = len(candidate_rows)
    total_backlog_rows = len(backlog_rows)
    sessions_total = len(sessions)

    if sessions_total == 0:
        build_status = "FAIL"
        final_interpretation = "PRESIGNAL_V2_STATUS_FAILED"
        error_count = 1
    elif global_phase8_status.startswith("NOT_READY"):
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "PRESIGNAL_V2_STATUS_READY_WITH_LIMITATIONS"
        error_count = 0
    else:
        build_status = "PASS"
        final_interpretation = "PRESIGNAL_V2_STATUS_READY"
        error_count = 0

    recommended_next_action = global_next_action
    summary_notes = _truncate_text(
        f"phase1={phase1_interp}; phase2={phase2_interp}; phase3={phase3_interp}; phase4={phase4_interp}; phase5={phase5_interp}; phase6={phase6_interp}; phase7={phase7_interp}; phase8_readiness={global_phase8_status}",
        500,
    )
    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_total": sessions_total,
        "sessions_with_phase1": sessions_total,
        "sessions_with_phase2": sum(1 for row in status_rows if _norm(row.get("phase2_attention_status")) == "AVAILABLE"),
        "sessions_with_phase3": sum(1 for row in status_rows if _norm(row.get("phase3_information_status")) == "AVAILABLE"),
        "sessions_with_phase4": sum(1 for row in status_rows if _norm(row.get("phase4_forecast_status")) == "AVAILABLE"),
        "sessions_with_phase5": sum(1 for row in status_rows if _norm(row.get("phase5_evaluation_status")) == "AVAILABLE"),
        "sessions_with_phase6": sum(1 for row in status_rows if _norm(row.get("phase6_baseline_status")) == "AVAILABLE"),
        "sessions_with_phase7": sum(1 for row in status_rows if _norm(row.get("phase7_candidate_status")) == "LINKED"),
        "sessions_complete_through_phase7": complete_through_phase7,
        "total_member_events": len(data[PHASE1_MEMBER_SHEET]),
        "total_attention_rows": len(data[PHASE2_MAP_SHEET]),
        "total_information_request_rows": len(data[PHASE3_REQUEST_SHEET]),
        "total_forecast_rows": len(data[PHASE4_FORECAST_SHEET]),
        "total_evaluation_rows": len(data[PHASE5_EVALUATION_SHEET]),
        "total_baseline_compare_rows": len(data[PHASE6_COMPARE_SHEET]),
        "total_candidate_rows": total_candidate_rows,
        "total_backlog_rows": total_backlog_rows,
        "candidate_quantitative_direct_count": sum(1 for row in candidate_rows if _norm(row.get("information_class")) == "quantitative_direct"),
        "candidate_quantitative_derived_count": sum(1 for row in candidate_rows if _norm(row.get("information_class")) == "quantitative_derived"),
        "candidate_qualitative_source_grounded_count": sum(1 for row in candidate_rows if _norm(row.get("information_class")) == "qualitative_source_grounded"),
        "candidate_qualitative_interpretive_count": sum(1 for row in candidate_rows if _norm(row.get("information_class")) == "qualitative_interpretive"),
        "candidate_backtest_safe_count": sum(1 for row in candidate_rows if _as_bool(row.get("backtest_safe_candidate"))),
        "candidate_high_bias_risk_count": sum(1 for row in candidate_rows if _norm(row.get("risk_of_provider_bias")).lower() == "high"),
        "repeated_candidate_count": repeat_counts["repeated_candidate_count"],
        "multi_provider_candidate_count": repeat_counts["multi_provider_candidate_count"],
        "multi_session_candidate_count": repeat_counts["multi_session_candidate_count"],
        "phase8_ready_session_count": phase8_ready_session_count,
        "phase8_not_ready_session_count": phase8_not_ready_session_count,
        "recommended_next_action": recommended_next_action,
        "governance_forbidden_write_count": 0,
        "input_missing_count": 0,
        "warning_count": warning_count,
        "error_count": error_count,
        "notes": summary_notes,
    }

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_STATUS_SHEET, status_headers, status_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
    registry_result = _upsert_registry_rows(sheets_service)

    return {
        "generated_ts": generated_ts,
        "sessions_total": sessions_total,
        "sessions_complete_through_phase7": complete_through_phase7,
        "total_information_request_rows": len(data[PHASE3_REQUEST_SHEET]),
        "total_candidate_rows": total_candidate_rows,
        "repeated_candidate_count": repeat_counts["repeated_candidate_count"],
        "multi_provider_candidate_count": repeat_counts["multi_provider_candidate_count"],
        "multi_session_candidate_count": repeat_counts["multi_session_candidate_count"],
        "phase8_ready_session_count": phase8_ready_session_count,
        "phase8_not_ready_session_count": phase8_not_ready_session_count,
        "final_interpretation": final_interpretation,
        "build_status": build_status,
        "registry_result": registry_result,
        "sample_status_row": status_rows[0] if status_rows else {},
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2 run status/readiness summary.")
    return parser.parse_args(argv)


def main() -> None:
    print(json.dumps(build_presignal_v2_run_status_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
