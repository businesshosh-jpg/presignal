import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
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
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
    run_script_function,
)


MAPPING_SHEET = "Market_State_Source_Mapping"
SEMANTICS_SHEET = "Market_State_Source_Semantics"
MAPPING_SUMMARY_SHEET = "Market_State_Source_Mapping_Summary"

MARKET_SESSIONS_SHEET = "Market_Sessions"
MARKET_SESSION_MEMBERS_SHEET = "Market_Session_Members"
ATTENTION_HISTORY_SHEET = "Session_Attention_Map_History"
INFO_HISTORY_SHEET = "Session_Information_Requests_History"
EVALUATION_HISTORY_SHEET = "Session_Evaluation_History"
BASELINE_HISTORY_SHEET = "Session_vs_Event_Baseline_Compare_History"
REPLAY_QUEUE_SHEET = "PreSignal_v2_Replay_Queue"

EVENT_SHEET = "Event"
CONFIG_SHEET = "Config"
FRED_SERIES_SHEET = "FRED_Series_ID"
FMP_EVENT_CATALOG_SHEET = "FMP_EventCatalog"
SERIES_MAP_SHEET = "SeriesMap"
SERIES_MAP_SUGGESTIONS_SHEET = "SeriesMap_Suggestions"

OUTPUT_SHADOW_SHEET = "Market_State_Pack_Shadow"
OUTPUT_SUMMARY_SHEET = "Market_State_Pack_Shadow_Summary"
OUTPUT_ITEM_AUDIT_SHEET = "Market_State_Pack_Item_Audit"
OUTPUT_COVERAGE_SHEET = "Market_State_Pack_Coverage_Audit"
OUTPUT_RUN_LOG_SHEET = "Market_State_Pack_Shadow_Run_Log"

SCHEMA_VERSION = "presignal_v2_market_state_pack_shadow_0.1"
SHADOW_VERSION = "shadow_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 8A-4R.2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_STATE_PACK_SHADOW"
REGISTRY_OWNER_MODULE = "market_state"

INCLUDED_FAMILIES = ["usdjpy_trend", "upcoming_larger_events", "treasury_yields", "dxy"]
EXCLUDED_FAMILIES = ["fed_expectations"]
FAMILY_FIELD_ORDER = {
    "usdjpy_trend": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
    ],
    "upcoming_larger_events": [
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
        "NEXT_CPI_OR_FOMC_WITHIN_72H",
        "NEXT_NFP_WITHIN_7D",
        "EVENT_CLUSTER_DENSITY_NEXT_24H",
        "UPCOMING_EVENT_RISK_LABEL",
    ],
    "treasury_yields": [
        "US2Y_YIELD_LEVEL",
        "US10Y_YIELD_LEVEL",
        "US2Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_MINUS_US2Y_CURVE",
    ],
    "dxy": [
        "DXY_LEVEL",
        "DXY_CHANGE_PRESESSION",
        "DXY_DIRECTION_LABEL",
        "USD_INDEX_PROXY_LEVEL",
        "USD_INDEX_PROXY_CHANGE",
    ],
}

SHADOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "shadow_pack_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "forecast_timestamp",
    "candidate_family",
    "candidate_field",
    "field_value",
    "field_value_numeric",
    "field_value_text",
    "field_unit",
    "source_provider",
    "source_name",
    "symbol_or_series_id",
    "source_type",
    "acquisition_method",
    "calculation_window",
    "input_start_ts",
    "input_end_ts",
    "source_observation_ts",
    "source_publication_ts",
    "as_of_timestamp",
    "data_available_flag",
    "missing_reason",
    "fallback_used",
    "fallback_source",
    "warning_label",
    "point_in_time_status",
    "leakage_check_status",
    "backtest_safe",
    "provider_visible",
    "used_in_forecast",
    "publication_timestamp_policy",
    "dxy_source_type",
    "lane_assignment",
    "early_pack_level_eligible",
    "field_refinement_status",
    "field_refinement_reason",
    "start_candle_exact",
    "start_candle_gap_minutes",
    "start_candle_gap_reason",
    "weekend_gap_flag",
    "notes",
]

ITEM_AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "shadow_pack_run_id",
    "session_id",
    "candidate_family",
    "candidate_field",
    "attempted",
    "success",
    "data_available_flag",
    "source_provider",
    "symbol_or_series_id",
    "source_status",
    "fallback_used",
    "missing_reason",
    "warning_count",
    "error_count",
    "point_in_time_status",
    "leakage_check_status",
    "backtest_safe",
    "actual_value_used",
    "post_forecast_data_used",
    "post_event_revision_used",
    "same_day_value_used",
    "same_day_timestamp_confirmed",
    "proxy_used",
    "proxy_warning",
    "publication_timestamp_policy",
    "dxy_source_type",
    "lane_assignment",
    "early_pack_level_eligible",
    "field_refinement_status",
    "field_refinement_reason",
    "start_candle_exact",
    "start_candle_gap_minutes",
    "start_candle_gap_reason",
    "weekend_gap_flag",
    "audit_status",
    "notes",
]

COVERAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "shadow_pack_run_id",
    "session_id",
    "candidate_family",
    "fields_expected",
    "fields_attempted",
    "fields_success",
    "fields_missing",
    "fields_warning",
    "fields_fail",
    "coverage_ratio",
    "complete_family_flag",
    "backtest_safe_family_flag",
    "point_in_time_family_status",
    "leakage_family_status",
    "family_audit_status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "shadow_pack_run_id",
    "build_status",
    "final_interpretation",
    "sessions_processed",
    "candidate_families_in_scope",
    "candidate_fields_in_scope",
    "shadow_rows_written",
    "item_audit_rows_written",
    "coverage_rows_written",
    "successful_field_count",
    "missing_field_count",
    "warning_field_count",
    "failed_field_count",
    "complete_session_count",
    "partial_session_count",
    "blocked_family_count",
    "fed_expectations_included_count",
    "provider_visible_count",
    "used_in_forecast_count",
    "post_forecast_data_used_count",
    "actual_value_used_count",
    "post_event_revision_used_count",
    "market_state_pack_write_count",
    "provider_prompt_change_count",
    "v1_sheet_write_count",
    "production_behavior_change_count",
    "refinement_run_id",
    "refined_field_count",
    "downgraded_field_count",
    "early_pack_level_eligible_count",
    "early_pack_level_ineligible_count",
    "normal_session_no_start_candle_count",
    "normal_session_no_start_candle_repaired_count",
    "weekend_gap_missing_count",
    "notes",
]

RUN_LOG_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "shadow_pack_run_id",
    "script_name",
    "build_status",
    "final_interpretation",
    "started_ts",
    "completed_ts",
    "runtime_seconds",
    "input_sheets_found",
    "input_sheets_missing",
    "output_sheets_written",
    "candidate_families_in_scope",
    "candidate_families_excluded",
    "safety_status",
    "error_message",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _shadow_pack_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"market_state_pack_shadow_v0_{stamp}"


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _safe_float(value: Any) -> Optional[float]:
    try:
        text = _norm(value)
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _iso_z(dt) -> str:
    if dt is None:
        return ""
    return dt.astimezone(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _read_optional_rows(
    service,
    spreadsheet_id: str,
    sheet_titles: Set[str],
    sheet_name: str,
    missing: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in sheet_titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _parse_session_id(session_id: str) -> Dict[str, str]:
    parts = (_norm(session_id) or "||").split("|", 2)
    while len(parts) < 3:
        parts.append("")
    return {"country": parts[0], "session_date": parts[1], "session_window_name": parts[2]}


def _prefer_earlier_ts(existing: Any, candidate: Any) -> str:
    existing_text = _norm(existing)
    candidate_text = _norm(candidate)
    if not candidate_text:
        return existing_text
    if not existing_text:
        return candidate_text
    existing_dt = _parse_dt(existing_text)
    candidate_dt = _parse_dt(candidate_text)
    if existing_dt and candidate_dt:
        return candidate_text if candidate_dt < existing_dt else existing_text
    return existing_text


def _prefer_later_ts(existing: Any, candidate: Any) -> str:
    existing_text = _norm(existing)
    candidate_text = _norm(candidate)
    if not candidate_text:
        return existing_text
    if not existing_text:
        return candidate_text
    existing_dt = _parse_dt(existing_text)
    candidate_dt = _parse_dt(candidate_text)
    if existing_dt and candidate_dt:
        return candidate_text if candidate_dt > existing_dt else existing_text
    return existing_text


def _session_metadata(
    market_sessions_rows: Sequence[Dict[str, Any]],
    replay_queue_rows: Sequence[Dict[str, Any]],
    attention_history_rows: Sequence[Dict[str, Any]],
    info_history_rows: Sequence[Dict[str, Any]],
    evaluation_history_rows: Sequence[Dict[str, Any]],
    baseline_history_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}

    def ensure(session_id: str) -> Dict[str, Any]:
        row = meta.get(session_id)
        if row is None:
            parsed = _parse_session_id(session_id)
            row = {
                "session_id": session_id,
                "session_date": parsed["session_date"],
                "country": parsed["country"],
                "session_window_name": parsed["session_window_name"],
                "session_start_ts": "",
                "session_end_ts": "",
                "forecast_timestamp": "",
                "earliest_release_ts": "",
                "latest_release_ts": "",
            }
            meta[session_id] = row
        return row

    for row in replay_queue_rows:
        session_id = _norm(row.get("session_id"))
        if not session_id:
            continue
        target = ensure(session_id)
        target["session_date"] = _norm(row.get("session_date")) or target["session_date"]
        target["country"] = _norm(row.get("country")) or target["country"]
        target["session_window_name"] = _norm(row.get("session_window_name")) or target["session_window_name"]
        target["session_start_ts"] = _norm(row.get("session_start_ts")) or target["session_start_ts"]
        target["session_end_ts"] = _norm(row.get("session_end_ts")) or target["session_end_ts"]
        target["earliest_release_ts"] = _norm(row.get("earliest_release_ts")) or target["earliest_release_ts"]
        target["latest_release_ts"] = _norm(row.get("latest_release_ts")) or target["latest_release_ts"]

    for row in market_sessions_rows:
        session_id = _norm(row.get("session_id"))
        if not session_id:
            continue
        target = ensure(session_id)
        target["session_date"] = _norm(row.get("session_date")) or target["session_date"]
        target["country"] = _norm(row.get("country")) or target["country"]
        target["session_window_name"] = _norm(row.get("session_window_name")) or target["session_window_name"]
        target["session_start_ts"] = _norm(row.get("session_start_ts")) or target["session_start_ts"]
        target["session_end_ts"] = _norm(row.get("session_end_ts")) or target["session_end_ts"]
        target["earliest_release_ts"] = _norm(row.get("primary_release_ts")) or target["earliest_release_ts"]
        target["latest_release_ts"] = _norm(row.get("last_release_ts")) or target["latest_release_ts"]

    for rows, key in [
        (attention_history_rows, "active_session_id"),
        (info_history_rows, "active_session_id"),
    ]:
        for row in rows:
            session_id = _norm(row.get(key))
            if session_id:
                target = ensure(session_id)
                target["session_date"] = _norm(row.get("session_date")) or target["session_date"]
                target["country"] = _norm(row.get("country")) or target["country"]
                target["session_window_name"] = _norm(row.get("session_window_name")) or target["session_window_name"]
                release_ts = _norm(row.get("release_ts"))
                if release_ts:
                    target["earliest_release_ts"] = _prefer_earlier_ts(target["earliest_release_ts"], release_ts)
                    target["latest_release_ts"] = _prefer_later_ts(target["latest_release_ts"], release_ts)
                    target["session_start_ts"] = _prefer_earlier_ts(target["session_start_ts"], release_ts)
                    target["session_end_ts"] = _prefer_later_ts(target["session_end_ts"], release_ts)
    for rows in [evaluation_history_rows, baseline_history_rows]:
        for row in rows:
            session_id = _norm(row.get("active_session_id")) or _norm(row.get("session_id"))
            if session_id:
                target = ensure(session_id)
                target["session_date"] = _norm(row.get("session_date")) or target["session_date"]
                target["country"] = _norm(row.get("country")) or target["country"]
                target["session_window_name"] = _norm(row.get("session_window_name")) or target["session_window_name"]

    for session_id, row in meta.items():
        forecast_timestamp = _norm(row.get("earliest_release_ts")) or _norm(row.get("session_start_ts"))
        row["forecast_timestamp"] = forecast_timestamp
    return sorted(meta.values(), key=lambda row: (_norm(row.get("session_date")), _norm(row.get("forecast_timestamp")), _norm(row.get("session_id"))))


def _mapping_rows_by_field(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        family = _norm(row.get("candidate_family")).lower()
        field = _norm(row.get("candidate_field"))
        if family and field:
            out[(family, field)] = row
    return out


def _semantics_rows_by_field(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        family = _norm(row.get("candidate_family")).lower()
        field = _norm(row.get("candidate_field"))
        if family and field:
            out[(family, field)] = row
    return out


def _allowed_mapping_row(row: Dict[str, Any]) -> bool:
    if not row:
        return False
    family = _norm(row.get("candidate_family")).lower()
    if family not in INCLUDED_FAMILIES:
        return False
    return _upper(row.get("mapping_decision")) in {
        "READY_FOR_LIMITED_ACQUISITION_DESIGN",
        "READY_WITH_WARNINGS_FOR_LIMITED_ACQUISITION_DESIGN",
    }


def _event_family_label(indicator_name: str) -> str:
    text = _norm(indicator_name).lower()
    if "cpi" in text or "consumer price" in text:
        return "cpi"
    if "fomc" in text or "fed chair powell" in text or "fed " in text or "federal reserve" in text or "rate decision" in text:
        return "fomc_fed"
    if "nonfarm" in text or "nfp" in text:
        return "nfp"
    return "other"


def _build_upcoming_event_pack(
    event_rows: Sequence[Dict[str, Any]],
    country: str,
    forecast_dt,
) -> Dict[str, Dict[str, Any]]:
    future_rows = []
    for row in event_rows:
        if _norm(row.get("country")).upper() != _norm(country).upper():
            continue
        release_dt = _parse_dt(row.get("release_ts"))
        if release_dt is None or release_dt <= forecast_dt:
            continue
        future_rows.append({
            "release_dt": release_dt,
            "indicator_name": _norm(row.get("indicator_name")),
            "importance": _norm(row.get("importance")).lower(),
            "event_family": _event_family_label(row.get("indicator_name")),
        })
    future_rows.sort(key=lambda row: row["release_dt"])

    def within(hours: float) -> List[Dict[str, Any]]:
        out = []
        cutoff = forecast_dt.timestamp() + hours * 3600.0
        for row in future_rows:
            if row["release_dt"].timestamp() <= cutoff:
                out.append(row)
            else:
                break
        return out

    rows_24h = within(24)
    rows_48h = within(48)
    rows_72h = within(72)
    rows_7d = within(24 * 7)
    high_24h = any(row["importance"] == "high" for row in rows_24h)
    high_48h = any(row["importance"] == "high" for row in rows_48h)
    cpi_or_fomc = any(row["event_family"] in {"cpi", "fomc_fed"} for row in rows_72h)
    nfp_7d = any(row["event_family"] == "nfp" for row in rows_7d)
    cluster_count = len(rows_24h)
    if cpi_or_fomc or high_24h or cluster_count >= 5:
        risk_label = "high"
    elif high_48h or nfp_7d or cluster_count >= 3:
        risk_label = "medium"
    elif cluster_count > 0:
        risk_label = "low"
    else:
        risk_label = "none"

    return {
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H": {
            "value": "TRUE" if high_24h else "FALSE",
            "numeric": 1 if high_24h else 0,
            "text": "TRUE" if high_24h else "FALSE",
            "unit": "boolean",
            "warning": "scheduled_calendar_point_in_time_not_fully_verifiable",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H": {
            "value": "TRUE" if high_48h else "FALSE",
            "numeric": 1 if high_48h else 0,
            "text": "TRUE" if high_48h else "FALSE",
            "unit": "boolean",
            "warning": "scheduled_calendar_point_in_time_not_fully_verifiable",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
        "NEXT_CPI_OR_FOMC_WITHIN_72H": {
            "value": "TRUE" if cpi_or_fomc else "FALSE",
            "numeric": 1 if cpi_or_fomc else 0,
            "text": "TRUE" if cpi_or_fomc else "FALSE",
            "unit": "boolean",
            "warning": "scheduled_calendar_point_in_time_not_fully_verifiable",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
        "NEXT_NFP_WITHIN_7D": {
            "value": "TRUE" if nfp_7d else "FALSE",
            "numeric": 1 if nfp_7d else 0,
            "text": "TRUE" if nfp_7d else "FALSE",
            "unit": "boolean",
            "warning": "scheduled_calendar_point_in_time_not_fully_verifiable",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
        "EVENT_CLUSTER_DENSITY_NEXT_24H": {
            "value": str(cluster_count),
            "numeric": cluster_count,
            "text": str(cluster_count),
            "unit": "count",
            "warning": "scheduled_calendar_point_in_time_not_fully_verifiable",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
        "UPCOMING_EVENT_RISK_LABEL": {
            "value": risk_label,
            "numeric": "",
            "text": risk_label,
            "unit": "label",
            "warning": "risk_label_heuristic_v0",
            "point_in_time_status": "PASS_WITH_WARNINGS",
            "leakage_status": "PASS",
        },
    }


def _status_rank(value: str) -> int:
    return {"PASS": 0, "PASS_WITH_WARNINGS": 1, "NEEDS_REVIEW": 2, "FAIL": 3, "NOT_APPLICABLE": 0}.get(_upper(value), 2)


def _aggregate_status(values: Iterable[str], fallback: str = "PASS") -> str:
    vals = [_norm(v) for v in values if _norm(v)]
    if not vals:
        return fallback
    return max(vals, key=_status_rank)


def _usdjpy_label(value: Optional[float]) -> str:
    if value is None:
        return ""
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _bool_text(value: Any) -> str:
    return "TRUE" if _upper(value) == "TRUE" else "FALSE"


def _is_weekday_timestamp(value: Any) -> bool:
    dt = _parse_dt(value)
    if dt is None:
        return False
    return dt.weekday() < 5


def _field_lane_metadata(
    candidate_family: str,
    candidate_field: str,
    source_status: str,
    start_candle_exact: str,
) -> Tuple[str, str, str, str]:
    if candidate_family == "upcoming_larger_events" and candidate_field == "UPCOMING_EVENT_RISK_LABEL":
        return (
            "LANE_B_PROVISIONAL_CANDIDATE",
            "FALSE",
            "DOWNGRADED",
            "Heuristic risk label is not early Lane A deterministic pack-level ready.",
        )
    if candidate_family in INCLUDED_FAMILIES:
        if candidate_family == "usdjpy_trend" and _upper(source_status) == "LEAKAGE_SAFE_NEAREST_START":
            return (
                "LANE_A_DETERMINISTIC",
                "TRUE",
                "REFINED",
                "Nearest leakage-safe start candle used within bounded tolerance.",
            )
        if candidate_family == "usdjpy_trend" and _upper(source_status) in {
            "WEEKEND_GAP_OUTSIDE_TOLERANCE",
            "INSUFFICIENT_HISTORY",
            "MARKET_CLOSED_MISSING",
            "SOURCE_UNAVAILABLE",
        }:
            return (
                "LANE_A_DETERMINISTIC",
                "TRUE",
                "NEEDS_REVIEW",
                "Deterministic field remains valid, but acquisition window could not be built cleanly.",
            )
        return ("LANE_A_DETERMINISTIC", "TRUE", "UNCHANGED", "")
    return ("BLOCKED", "FALSE", "BLOCKED", "Field is outside the deterministic shadow acquisition scope.")


def _shadow_row(
    generated_ts: str,
    shadow_pack_run_id: str,
    session: Dict[str, Any],
    candidate_family: str,
    candidate_field: str,
    field_value: Any,
    field_value_numeric: Any,
    field_value_text: Any,
    field_unit: str,
    source_provider: str,
    source_name: str,
    symbol_or_series_id: str,
    source_type: str,
    acquisition_method: str,
    calculation_window: str,
    input_start_ts: str,
    input_end_ts: str,
    source_observation_ts: str,
    source_publication_ts: str,
    as_of_timestamp: str,
    data_available_flag: str,
    missing_reason: str,
    fallback_used: str,
    fallback_source: str,
    warning_label: str,
    point_in_time_status: str,
    leakage_check_status: str,
    backtest_safe: str,
    publication_timestamp_policy: str,
    dxy_source_type: str,
    lane_assignment: str,
    early_pack_level_eligible: str,
    field_refinement_status: str,
    field_refinement_reason: str,
    start_candle_exact: str,
    start_candle_gap_minutes: Any,
    start_candle_gap_reason: str,
    weekend_gap_flag: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "shadow_pack_run_id": shadow_pack_run_id,
        "session_id": _norm(session.get("session_id")),
        "session_date": _norm(session.get("session_date")),
        "country": _norm(session.get("country")),
        "session_window_name": _norm(session.get("session_window_name")),
        "forecast_timestamp": _norm(session.get("forecast_timestamp")),
        "candidate_family": candidate_family,
        "candidate_field": candidate_field,
        "field_value": field_value,
        "field_value_numeric": field_value_numeric,
        "field_value_text": field_value_text,
        "field_unit": field_unit,
        "source_provider": source_provider,
        "source_name": source_name,
        "symbol_or_series_id": symbol_or_series_id,
        "source_type": source_type,
        "acquisition_method": acquisition_method,
        "calculation_window": calculation_window,
        "input_start_ts": input_start_ts,
        "input_end_ts": input_end_ts,
        "source_observation_ts": source_observation_ts,
        "source_publication_ts": source_publication_ts,
        "as_of_timestamp": as_of_timestamp,
        "data_available_flag": data_available_flag,
        "missing_reason": missing_reason,
        "fallback_used": fallback_used,
        "fallback_source": fallback_source,
        "warning_label": warning_label,
        "point_in_time_status": point_in_time_status,
        "leakage_check_status": leakage_check_status,
        "backtest_safe": backtest_safe,
        "provider_visible": "FALSE",
        "used_in_forecast": "FALSE",
        "publication_timestamp_policy": publication_timestamp_policy,
        "dxy_source_type": dxy_source_type,
        "lane_assignment": lane_assignment,
        "early_pack_level_eligible": early_pack_level_eligible,
        "field_refinement_status": field_refinement_status,
        "field_refinement_reason": _truncate_text(field_refinement_reason, 300),
        "start_candle_exact": start_candle_exact,
        "start_candle_gap_minutes": start_candle_gap_minutes,
        "start_candle_gap_reason": start_candle_gap_reason,
        "weekend_gap_flag": weekend_gap_flag,
        "notes": _truncate_text(notes, 400),
    }


def _item_audit_row(
    generated_ts: str,
    shadow_pack_run_id: str,
    session_id: str,
    candidate_family: str,
    candidate_field: str,
    attempted: str,
    success: str,
    data_available_flag: str,
    source_provider: str,
    symbol_or_series_id: str,
    source_status: str,
    fallback_used: str,
    missing_reason: str,
    warning_count: int,
    error_count: int,
    point_in_time_status: str,
    leakage_check_status: str,
    backtest_safe: str,
    actual_value_used: str,
    post_forecast_data_used: str,
    post_event_revision_used: str,
    same_day_value_used: str,
    same_day_timestamp_confirmed: str,
    proxy_used: str,
    proxy_warning: str,
    publication_timestamp_policy: str,
    dxy_source_type: str,
    lane_assignment: str,
    early_pack_level_eligible: str,
    field_refinement_status: str,
    field_refinement_reason: str,
    start_candle_exact: str,
    start_candle_gap_minutes: Any,
    start_candle_gap_reason: str,
    weekend_gap_flag: str,
    audit_status: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "shadow_pack_run_id": shadow_pack_run_id,
        "session_id": session_id,
        "candidate_family": candidate_family,
        "candidate_field": candidate_field,
        "attempted": attempted,
        "success": success,
        "data_available_flag": data_available_flag,
        "source_provider": source_provider,
        "symbol_or_series_id": symbol_or_series_id,
        "source_status": source_status,
        "fallback_used": fallback_used,
        "missing_reason": missing_reason,
        "warning_count": warning_count,
        "error_count": error_count,
        "point_in_time_status": point_in_time_status,
        "leakage_check_status": leakage_check_status,
        "backtest_safe": backtest_safe,
        "actual_value_used": actual_value_used,
        "post_forecast_data_used": post_forecast_data_used,
        "post_event_revision_used": post_event_revision_used,
        "same_day_value_used": same_day_value_used,
        "same_day_timestamp_confirmed": same_day_timestamp_confirmed,
        "proxy_used": proxy_used,
        "proxy_warning": proxy_warning,
        "publication_timestamp_policy": publication_timestamp_policy,
        "dxy_source_type": dxy_source_type,
        "lane_assignment": lane_assignment,
        "early_pack_level_eligible": early_pack_level_eligible,
        "field_refinement_status": field_refinement_status,
        "field_refinement_reason": _truncate_text(field_refinement_reason, 300),
        "start_candle_exact": start_candle_exact,
        "start_candle_gap_minutes": start_candle_gap_minutes,
        "start_candle_gap_reason": start_candle_gap_reason,
        "weekend_gap_flag": weekend_gap_flag,
        "audit_status": audit_status,
        "notes": _truncate_text(notes, 400),
    }


def _build_session_field_rows(
    generated_ts: str,
    shadow_pack_run_id: str,
    session: Dict[str, Any],
    mapping_by_field: Dict[Tuple[str, str], Dict[str, Any]],
    semantics_by_field: Dict[Tuple[str, str], Dict[str, Any]],
    event_rows: Sequence[Dict[str, Any]],
    snapshot_payload: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    shadow_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    forecast_timestamp = _norm(session.get("forecast_timestamp"))
    forecast_dt = _parse_dt(forecast_timestamp)
    if forecast_dt is None:
        for family in INCLUDED_FAMILIES:
            for field in FAMILY_FIELD_ORDER[family]:
                if not _allowed_mapping_row(mapping_by_field.get((family, field))):
                    continue
                shadow_rows.append(
                    _shadow_row(
                        generated_ts,
                        shadow_pack_run_id,
                        session,
                        family,
                        field,
                        "",
                        "",
                        "",
                        _norm(semantics_by_field.get((family, field), {}).get("unit")),
                        _norm(mapping_by_field.get((family, field), {}).get("primary_provider")),
                        _norm(mapping_by_field.get((family, field), {}).get("primary_source_name")),
                        _norm(mapping_by_field.get((family, field), {}).get("primary_symbol_or_series_id")),
                        _norm(mapping_by_field.get((family, field), {}).get("primary_source_type")),
                        _norm(mapping_by_field.get((family, field), {}).get("acquisition_method")),
                        _norm(semantics_by_field.get((family, field), {}).get("calculation_window")),
                        "",
                        "",
                        "",
                        "",
                        "",
                        "FALSE",
                        "missing_forecast_timestamp",
                        "FALSE",
                        "",
                        "",
                        "FAIL",
                        "FAIL",
                        _norm(mapping_by_field.get((family, field), {}).get("backtest_safe")) or "FALSE",
                        "",
                        "",
                        "LANE_A_DETERMINISTIC" if family != "fed_expectations" else "BLOCKED",
                        "FALSE" if field == "UPCOMING_EVENT_RISK_LABEL" else "TRUE",
                        "NEEDS_REVIEW",
                        "forecast_timestamp missing",
                        "FALSE",
                        "",
                        "",
                        "FALSE",
                        "forecast_timestamp missing",
                    )
                )
                audit_rows.append(
                    _item_audit_row(
                        generated_ts,
                        shadow_pack_run_id,
                        _norm(session.get("session_id")),
                        family,
                        field,
                        "FALSE",
                        "FALSE",
                        "FALSE",
                        _norm(mapping_by_field.get((family, field), {}).get("primary_provider")),
                        _norm(mapping_by_field.get((family, field), {}).get("primary_symbol_or_series_id")),
                        "missing_forecast_timestamp",
                        "FALSE",
                        "missing_forecast_timestamp",
                        0,
                        1,
                        "FAIL",
                        "FAIL",
                        _norm(mapping_by_field.get((family, field), {}).get("backtest_safe")) or "FALSE",
                        "FALSE",
                        "FALSE",
                        "FALSE",
                        "FALSE",
                        "UNKNOWN",
                        "FALSE",
                        "FALSE",
                        "",
                        "",
                        "LANE_A_DETERMINISTIC" if family != "fed_expectations" else "BLOCKED",
                        "FALSE" if field == "UPCOMING_EVENT_RISK_LABEL" else "TRUE",
                        "NEEDS_REVIEW",
                        "forecast_timestamp missing",
                        "FALSE",
                        "",
                        "",
                        "FALSE",
                        "FAIL",
                        "forecast_timestamp missing",
                    )
                )
        return shadow_rows, audit_rows

    upcoming_pack = _build_upcoming_event_pack(event_rows, _norm(session.get("country")), forecast_dt)
    daily = snapshot_payload.get("daily_snapshots", {}) if isinstance(snapshot_payload, dict) else {}
    usdjpy_windows = snapshot_payload.get("usdjpy_windows", {}) if isinstance(snapshot_payload, dict) else {}

    for family in INCLUDED_FAMILIES:
        for field in FAMILY_FIELD_ORDER[family]:
            mapping_row = mapping_by_field.get((family, field), {})
            if not _allowed_mapping_row(mapping_row):
                continue
            semantics_row = semantics_by_field.get((family, field), {})
            unit = _norm(semantics_row.get("unit"))
            backtest_safe = _norm(mapping_row.get("backtest_safe")) or "FALSE"
            warning_label = ""
            point_in_time_status = "PASS"
            leakage_status = "PASS"
            missing_reason = ""
            data_available_flag = "TRUE"
            fallback_used = "FALSE"
            fallback_source = ""
            field_value = ""
            field_value_numeric = ""
            field_value_text = ""
            source_provider = _norm(mapping_row.get("primary_provider"))
            source_name = _norm(mapping_row.get("primary_source_name"))
            symbol_or_series_id = _norm(mapping_row.get("primary_symbol_or_series_id"))
            source_type = _norm(mapping_row.get("primary_source_type"))
            acquisition_method = _norm(mapping_row.get("acquisition_method"))
            calculation_window = _norm(semantics_row.get("calculation_window"))
            input_start_ts = ""
            input_end_ts = ""
            source_observation_ts = ""
            source_publication_ts = ""
            same_day_value_used = "FALSE"
            same_day_timestamp_confirmed = "UNKNOWN"
            proxy_used = "FALSE"
            proxy_warning = "FALSE"
            publication_timestamp_policy = ""
            dxy_source_type = ""
            lane_assignment = "LANE_A_DETERMINISTIC"
            early_pack_level_eligible = "TRUE"
            field_refinement_status = "UNCHANGED"
            field_refinement_reason = ""
            start_candle_exact = "FALSE"
            start_candle_gap_minutes = ""
            start_candle_gap_reason = ""
            weekend_gap_flag = "FALSE"
            source_status = "ok"
            actual_value_used = "FALSE"
            post_forecast_data_used = "FALSE"
            post_event_revision_used = "FALSE"
            notes = ""

            if family == "upcoming_larger_events":
                payload = upcoming_pack[field]
                field_value = payload["value"]
                field_value_numeric = payload["numeric"]
                field_value_text = payload["text"]
                warning_label = payload["warning"]
                point_in_time_status = payload["point_in_time_status"]
                leakage_status = payload["leakage_status"]
                source_provider = "PreSignal"
                source_name = "Event"
                symbol_or_series_id = "Event"
                source_type = "scheduled_calendar_sheet"
                acquisition_method = "calendar_derived_feature"
                lane_assignment, early_pack_level_eligible, field_refinement_status, field_refinement_reason = _field_lane_metadata(
                    family,
                    field,
                    source_status,
                    start_candle_exact,
                )
                notes = "scheduled metadata only; actual values and revisions not used"

            elif family == "usdjpy_trend":
                key = {
                    "USDJPY_RETURN_1H_PRESESSION": "return_1h",
                    "USDJPY_RETURN_4H_PRESESSION": "return_4h",
                    "USDJPY_RETURN_24H_PRESESSION": "return_24h",
                    "USDJPY_TREND_LABEL": "return_24h",
                    "USDJPY_REALIZED_VOL_1H_PRESESSION": "realized_vol_1h",
                }[field]
                payload = usdjpy_windows.get(key, {})
                source_provider = _norm(payload.get("provider")) or source_provider
                input_start_ts = _norm(payload.get("start_ts"))
                input_end_ts = _norm(payload.get("end_ts"))
                source_observation_ts = _norm(payload.get("end_candle_ts"))
                source_status = _norm(payload.get("status")) or "missing"
                start_candle_exact = "TRUE" if _upper(payload.get("start_candle_exact")) == "TRUE" else "FALSE"
                start_candle_gap_minutes = _norm(payload.get("start_candle_gap_minutes"))
                start_candle_gap_reason = _norm(payload.get("start_candle_gap_reason"))
                weekend_gap_flag = "TRUE" if _upper(payload.get("weekend_gap_flag")) == "TRUE" else "FALSE"
                if key == "realized_vol_1h":
                    numeric_val = _safe_float(payload.get("realized_volatility"))
                else:
                    numeric_val = _safe_float(payload.get("return_pct"))
                if source_status not in {"exact_window", "leakage_safe_nearest_start"} or numeric_val is None and field != "USDJPY_TREND_LABEL":
                    data_available_flag = "FALSE"
                    missing_reason = {
                        "market_closed_missing": "market_closed",
                        "weekend_gap_outside_tolerance": "weekend_gap_outside_tolerance",
                        "insufficient_history": "insufficient_history",
                        "source_unavailable": "source_unavailable",
                        "no_end_candle": "source_unavailable",
                    }.get(source_status, source_status or "missing_usdjpy_window")
                    point_in_time_status = "NEEDS_REVIEW"
                    leakage_status = "PASS_WITH_WARNINGS" if source_status in {"market_closed_missing", "weekend_gap_outside_tolerance"} else "NEEDS_REVIEW"
                    notes = "USDJPY window data unavailable from leakage-safe intraday source"
                else:
                    point_in_time_status = "PASS"
                    leakage_status = "FAIL" if _upper(payload.get("post_forecast_data_used")) == "TRUE" else "PASS"
                    post_forecast_data_used = "TRUE" if _upper(payload.get("post_forecast_data_used")) == "TRUE" else "FALSE"
                    if source_status == "leakage_safe_nearest_start":
                        warning_label = "leakage_safe_nearest_start"
                        point_in_time_status = "PASS_WITH_WARNINGS"
                    if field == "USDJPY_TREND_LABEL":
                        trend_source = _safe_float(usdjpy_windows.get("return_24h", {}).get("return_pct"))
                        label = _usdjpy_label(trend_source)
                        field_value = label
                        field_value_text = label
                        field_value_numeric = ""
                    elif field == "USDJPY_REALIZED_VOL_1H_PRESESSION":
                        field_value = numeric_val
                        field_value_numeric = numeric_val
                        field_value_text = str(numeric_val)
                        warning_label = (
                            "realized_volatility_bar_count_low"
                            if _safe_int(payload.get("realized_volatility_bar_count")) < 10
                            else ""
                        )
                    else:
                        field_value = numeric_val
                        field_value_numeric = numeric_val
                        field_value_text = str(numeric_val)
                    notes = _truncate_text(
                        f"source_status={source_status}; candle_count={_safe_int(payload.get('candle_count'))}; start_candle_ts={_norm(payload.get('start_candle_ts'))}; end_candle_ts={_norm(payload.get('end_candle_ts'))}; start_candle_exact={start_candle_exact}; start_candle_gap_minutes={start_candle_gap_minutes}; start_candle_gap_reason={start_candle_gap_reason}",
                        300,
                    )
                lane_assignment, early_pack_level_eligible, field_refinement_status, field_refinement_reason = _field_lane_metadata(
                    family,
                    field,
                    source_status,
                    start_candle_exact,
                )

            elif family == "treasury_yields":
                key = {
                    "US2Y_YIELD_LEVEL": "us2y",
                    "US10Y_YIELD_LEVEL": "us10y",
                    "US2Y_CHANGE_FROM_PRIOR_CLOSE": "us2y",
                    "US10Y_CHANGE_FROM_PRIOR_CLOSE": "us10y",
                    "US10Y_MINUS_US2Y_CURVE": "curve",
                }[field]
                if key == "curve":
                    us2y = daily.get("us2y", {})
                    us10y = daily.get("us10y", {})
                    us2y_val = _safe_float((us2y.get("chosen") or {}).get("value"))
                    us10y_val = _safe_float((us10y.get("chosen") or {}).get("value"))
                    if us2y_val is None or us10y_val is None:
                        data_available_flag = "FALSE"
                        missing_reason = "missing_curve_inputs"
                        point_in_time_status = "NEEDS_REVIEW"
                    else:
                        curve_bps = round((us10y_val - us2y_val) * 100.0, 4)
                        field_value = curve_bps
                        field_value_numeric = curve_bps
                        field_value_text = str(curve_bps)
                        source_observation_ts = _norm((us10y.get("chosen") or {}).get("date")) or _norm((us2y.get("chosen") or {}).get("date"))
                        point_in_time_status = "PASS_WITH_WARNINGS"
                        warning_label = "conservative_daily_prior_known"
                        publication_timestamp_policy = "conservative"
                        notes = "Curve computed from conservative prior-known DGS10 and DGS2 observations"
                else:
                    payload = daily.get(key, {})
                    chosen = payload.get("chosen") or {}
                    prior = payload.get("prior") or {}
                    chosen_val = _safe_float(chosen.get("value"))
                    prior_val = _safe_float(prior.get("value"))
                    source_observation_ts = _norm(chosen.get("date"))
                    source_status = _norm(payload.get("status")) or "missing"
                    same_day_timestamp_confirmed = _norm(payload.get("same_day_timestamp_confirmed")) or "UNKNOWN"
                    same_day_value_used = "TRUE" if _upper(payload.get("same_day_value_used")) == "TRUE" else "FALSE"
                    publication_timestamp_policy = _norm(payload.get("publication_timestamp_policy")) or "conservative"
                    if chosen_val is None:
                        data_available_flag = "FALSE"
                        missing_reason = source_status or "missing_daily_snapshot"
                        point_in_time_status = "NEEDS_REVIEW"
                        warning_label = "conservative_daily_missing"
                    else:
                        if field.endswith("_LEVEL"):
                            field_value = chosen_val
                            field_value_numeric = chosen_val
                            field_value_text = str(chosen_val)
                        else:
                            if prior_val is None:
                                data_available_flag = "FALSE"
                                missing_reason = "missing_prior_close"
                                point_in_time_status = "NEEDS_REVIEW"
                            else:
                                diff_bps = round((chosen_val - prior_val) * 100.0, 4)
                                field_value = diff_bps
                                field_value_numeric = diff_bps
                                field_value_text = str(diff_bps)
                        point_in_time_status = "PASS_WITH_WARNINGS" if data_available_flag == "TRUE" else point_in_time_status
                        warning_label = "conservative_daily_prior_known"
                        notes = _truncate_text(
                            f"chosen_date={_norm(chosen.get('date'))}; prior_date={_norm(prior.get('date'))}; same_day_candidate_found={_norm(payload.get('same_day_candidate_found'))}",
                            300,
                        )

            elif family == "dxy":
                key = {
                    "DXY_LEVEL": "dxy",
                    "DXY_CHANGE_PRESESSION": "dxy",
                    "DXY_DIRECTION_LABEL": "dxy",
                    "USD_INDEX_PROXY_LEVEL": "usd_index_proxy",
                    "USD_INDEX_PROXY_CHANGE": "usd_index_proxy",
                }[field]
                payload = daily.get(key, {})
                chosen = payload.get("chosen") or {}
                prior = payload.get("prior") or {}
                chosen_val = _safe_float(chosen.get("value"))
                prior_val = _safe_float(prior.get("value"))
                source_observation_ts = _norm(chosen.get("date"))
                source_status = _norm(payload.get("status")) or "missing"
                same_day_timestamp_confirmed = _norm(payload.get("same_day_timestamp_confirmed")) or "UNKNOWN"
                same_day_value_used = "TRUE" if _upper(payload.get("same_day_value_used")) == "TRUE" else "FALSE"
                publication_timestamp_policy = _norm(payload.get("publication_timestamp_policy")) or "conservative"
                if key == "usd_index_proxy":
                    proxy_used = "TRUE"
                    proxy_warning = "TRUE"
                    dxy_source_type = "USD_INDEX_PROXY"
                else:
                    dxy_source_type = "ACTUAL_DXY"
                if chosen_val is None:
                    data_available_flag = "FALSE"
                    missing_reason = source_status or "missing_daily_snapshot"
                    point_in_time_status = "NEEDS_REVIEW"
                    warning_label = "daily_snapshot_missing"
                else:
                    if field.endswith("_LEVEL"):
                        field_value = chosen_val
                        field_value_numeric = chosen_val
                        field_value_text = str(chosen_val)
                    elif field.endswith("_CHANGE"):
                        if prior_val is None or prior_val == 0:
                            data_available_flag = "FALSE"
                            missing_reason = "missing_prior_close"
                            point_in_time_status = "NEEDS_REVIEW"
                        else:
                            pct = round(((chosen_val - prior_val) / prior_val) * 100.0, 6)
                            field_value = pct
                            field_value_numeric = pct
                            field_value_text = str(pct)
                    else:
                        if prior_val is None or prior_val == 0:
                            data_available_flag = "FALSE"
                            missing_reason = "missing_prior_close"
                            point_in_time_status = "NEEDS_REVIEW"
                        else:
                            pct = round(((chosen_val - prior_val) / prior_val) * 100.0, 6)
                            label = "up" if pct > 0 else "down" if pct < 0 else "flat"
                            field_value = label
                            field_value_text = label
                            field_value_numeric = ""
                            warning_label = "dxy_direction_zero_threshold_v0"
                    if data_available_flag == "TRUE":
                        point_in_time_status = "PASS_WITH_WARNINGS"
                        if key == "usd_index_proxy" and not warning_label:
                            warning_label = "usd_index_proxy_not_equivalent_to_actual_dxy"
                        elif key == "dxy" and not warning_label:
                            warning_label = "actual_dxy_daily_timestamp_warning"
                    notes = _truncate_text(
                        f"chosen_date={_norm(chosen.get('date'))}; prior_date={_norm(prior.get('date'))}; source_type={'USD_INDEX_PROXY' if key == 'usd_index_proxy' else 'ACTUAL_DXY'}",
                        300,
                    )

            if data_available_flag != "TRUE" and not missing_reason:
                missing_reason = "field_not_available"
            if not lane_assignment:
                lane_assignment, early_pack_level_eligible, field_refinement_status, field_refinement_reason = _field_lane_metadata(
                    family,
                    field,
                    source_status,
                    start_candle_exact,
                )
            if leakage_status == "FAIL":
                point_in_time_status = "FAIL"
            warning_count = 1 if warning_label else 0
            error_count = 1 if data_available_flag == "FALSE" and missing_reason else 0
            if leakage_status == "FAIL":
                error_count += 1
            if leakage_status == "FAIL":
                audit_status = "FAIL"
            elif data_available_flag == "FALSE":
                audit_status = "NEEDS_REVIEW"
            elif warning_count > 0 or _upper(point_in_time_status) == "PASS_WITH_WARNINGS":
                audit_status = "PASS_WITH_WARNINGS"
            else:
                audit_status = "PASS"

            shadow_rows.append(
                _shadow_row(
                    generated_ts,
                    shadow_pack_run_id,
                    session,
                    family,
                    field,
                    field_value,
                    field_value_numeric,
                    field_value_text,
                    unit,
                    source_provider,
                    source_name,
                    symbol_or_series_id,
                    source_type,
                    acquisition_method,
                    calculation_window,
                    input_start_ts,
                    input_end_ts,
                    source_observation_ts,
                    source_publication_ts,
                    forecast_timestamp,
                    data_available_flag,
                    missing_reason,
                    fallback_used,
                    fallback_source,
                    warning_label,
                    point_in_time_status,
                    leakage_status,
                    backtest_safe,
                    publication_timestamp_policy,
                    dxy_source_type,
                    lane_assignment,
                    early_pack_level_eligible,
                    field_refinement_status,
                    field_refinement_reason,
                    start_candle_exact,
                    start_candle_gap_minutes,
                    start_candle_gap_reason,
                    weekend_gap_flag,
                    notes,
                )
            )
            audit_rows.append(
                _item_audit_row(
                    generated_ts,
                    shadow_pack_run_id,
                    _norm(session.get("session_id")),
                    family,
                    field,
                    "TRUE",
                    "TRUE" if data_available_flag == "TRUE" and leakage_status != "FAIL" else "FALSE",
                    data_available_flag,
                    source_provider,
                    symbol_or_series_id,
                    source_status,
                    fallback_used,
                    missing_reason,
                    warning_count,
                    error_count,
                    point_in_time_status,
                    leakage_status,
                    backtest_safe,
                    actual_value_used,
                    post_forecast_data_used,
                    post_event_revision_used,
                    same_day_value_used,
                    same_day_timestamp_confirmed,
                    proxy_used,
                    proxy_warning,
                    publication_timestamp_policy,
                    dxy_source_type,
                    lane_assignment,
                    early_pack_level_eligible,
                    field_refinement_status,
                    field_refinement_reason,
                    start_candle_exact,
                    start_candle_gap_minutes,
                    start_candle_gap_reason,
                    weekend_gap_flag,
                    audit_status,
                    notes,
                )
            )

    return shadow_rows, audit_rows


def _coverage_rows(
    generated_ts: str,
    shadow_pack_run_id: str,
    session_ids: Sequence[str],
    audit_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_session_family: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        by_session_family[(_norm(row.get("session_id")), _norm(row.get("candidate_family")).lower())].append(row)

    rows: List[Dict[str, Any]] = []
    for session_id in session_ids:
        for family in INCLUDED_FAMILIES:
            items = by_session_family.get((session_id, family), [])
            expected = len(FAMILY_FIELD_ORDER[family])
            attempted = len(items)
            success = sum(1 for row in items if _upper(row.get("success")) == "TRUE")
            missing = sum(1 for row in items if _upper(row.get("data_available_flag")) != "TRUE")
            warning = sum(1 for row in items if _upper(row.get("audit_status")) == "PASS_WITH_WARNINGS")
            fail = sum(1 for row in items if _upper(row.get("audit_status")) == "FAIL")
            complete = "TRUE" if success == expected else "FALSE"
            backtest_safe_family_flag = "TRUE" if items and all(_upper(row.get("backtest_safe")) == "TRUE" for row in items) else "FALSE"
            pit_status = _aggregate_status((row.get("point_in_time_status") for row in items), "NEEDS_REVIEW" if items else "SKIPPED_BLOCKED")
            leak_status = _aggregate_status((row.get("leakage_check_status") for row in items), "NEEDS_REVIEW" if items else "SKIPPED_BLOCKED")
            if not items:
                family_status = "SKIPPED_BLOCKED"
            elif fail > 0:
                family_status = "FAIL"
            elif missing > 0:
                family_status = "NEEDS_REVIEW"
            elif warning > 0:
                family_status = "PASS_WITH_WARNINGS"
            else:
                family_status = "PASS"
            rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "shadow_version": SHADOW_VERSION,
                    "shadow_pack_run_id": shadow_pack_run_id,
                    "session_id": session_id,
                    "candidate_family": family,
                    "fields_expected": expected,
                    "fields_attempted": attempted,
                    "fields_success": success,
                    "fields_missing": missing,
                    "fields_warning": warning,
                    "fields_fail": fail,
                    "coverage_ratio": round(success / expected, 4) if expected else 0,
                    "complete_family_flag": complete,
                    "backtest_safe_family_flag": backtest_safe_family_flag,
                    "point_in_time_family_status": pit_status,
                    "leakage_family_status": leak_status,
                    "family_audit_status": family_status,
                    "notes": _truncate_text(f"attempted={attempted}; success={success}; missing={missing}; warning={warning}; fail={fail}", 300),
                }
            )
    return rows


def _summary_row(
    generated_ts: str,
    shadow_pack_run_id: str,
    session_ids: Sequence[str],
    shadow_rows: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    coverage_rows: Sequence[Dict[str, Any]],
    warnings: Sequence[str],
) -> Dict[str, Any]:
    successful_field_count = sum(1 for row in audit_rows if _upper(row.get("success")) == "TRUE")
    missing_field_count = sum(1 for row in audit_rows if _upper(row.get("data_available_flag")) != "TRUE")
    warning_field_count = sum(1 for row in audit_rows if _upper(row.get("audit_status")) == "PASS_WITH_WARNINGS")
    failed_field_count = sum(1 for row in audit_rows if _upper(row.get("audit_status")) == "FAIL")
    complete_session_count = 0
    partial_session_count = 0
    by_session = defaultdict(list)
    for row in coverage_rows:
        by_session[_norm(row.get("session_id"))].append(row)
    for session_id in session_ids:
        rows = by_session.get(session_id, [])
        if rows and all(_upper(row.get("complete_family_flag")) == "TRUE" for row in rows):
            complete_session_count += 1
        elif rows:
            partial_session_count += 1

    fed_expectations_included_count = 0
    provider_visible_count = sum(1 for row in shadow_rows if _upper(row.get("provider_visible")) == "TRUE")
    used_in_forecast_count = sum(1 for row in shadow_rows if _upper(row.get("used_in_forecast")) == "TRUE")
    post_forecast_data_used_count = sum(1 for row in audit_rows if _upper(row.get("post_forecast_data_used")) == "TRUE")
    actual_value_used_count = sum(1 for row in audit_rows if _upper(row.get("actual_value_used")) == "TRUE")
    post_event_revision_used_count = sum(1 for row in audit_rows if _upper(row.get("post_event_revision_used")) == "TRUE")
    market_state_pack_write_count = 0
    provider_prompt_change_count = 0
    v1_sheet_write_count = 0
    production_behavior_change_count = 0
    refinement_run_id = shadow_pack_run_id
    refined_field_count = sum(1 for row in shadow_rows if _upper(row.get("field_refinement_status")) == "REFINED")
    downgraded_field_count = sum(1 for row in shadow_rows if _upper(row.get("field_refinement_status")) == "DOWNGRADED")
    early_pack_level_eligible_count = sum(1 for row in shadow_rows if _upper(row.get("early_pack_level_eligible")) == "TRUE")
    early_pack_level_ineligible_count = sum(1 for row in shadow_rows if _upper(row.get("early_pack_level_eligible")) == "FALSE")
    normal_session_no_start_candle_count = sum(
        1
        for row in shadow_rows
        if _norm(row.get("candidate_family")).lower() == "usdjpy_trend"
        and _upper(row.get("weekend_gap_flag")) != "TRUE"
        and _norm(row.get("missing_reason")) in {"insufficient_history", "no_start_candle"}
    )
    normal_session_no_start_candle_repaired_count = sum(
        1
        for row in shadow_rows
        if _norm(row.get("candidate_family")).lower() == "usdjpy_trend"
        and "leakage_safe_nearest_start" in _norm(row.get("notes"))
        and _is_weekday_timestamp(row.get("input_end_ts"))
    )
    weekend_gap_missing_count = sum(
        1
        for row in shadow_rows
        if _norm(row.get("candidate_family")).lower() == "usdjpy_trend"
        and _upper(row.get("weekend_gap_flag")) == "TRUE"
        and _upper(row.get("data_available_flag")) != "TRUE"
    )

    if any([
        fed_expectations_included_count,
        provider_visible_count,
        used_in_forecast_count,
        post_forecast_data_used_count,
        actual_value_used_count,
        post_event_revision_used_count,
        market_state_pack_write_count,
        provider_prompt_change_count,
        v1_sheet_write_count,
        production_behavior_change_count,
    ]):
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINEMENT_BLOCKED"
    elif not shadow_rows:
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINEMENT_BLOCKED"
    elif failed_field_count > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINEMENT_NEEDS_REVIEW"
    elif normal_session_no_start_candle_count > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINEMENT_NEEDS_REVIEW"
    elif missing_field_count > 0 or warning_field_count > 0 or warnings:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINED_WITH_WARNINGS"
    else:
        build_status = "PASS"
        final_interpretation = "MARKET_STATE_PACK_SHADOW_REFINED"

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "shadow_pack_run_id": shadow_pack_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_processed": len(session_ids),
        "candidate_families_in_scope": len(INCLUDED_FAMILIES),
        "candidate_fields_in_scope": sum(len(v) for v in FAMILY_FIELD_ORDER.values()),
        "shadow_rows_written": len(shadow_rows),
        "item_audit_rows_written": len(audit_rows),
        "coverage_rows_written": len(coverage_rows),
        "successful_field_count": successful_field_count,
        "missing_field_count": missing_field_count,
        "warning_field_count": warning_field_count,
        "failed_field_count": failed_field_count,
        "complete_session_count": complete_session_count,
        "partial_session_count": partial_session_count,
        "blocked_family_count": len(EXCLUDED_FAMILIES),
        "fed_expectations_included_count": fed_expectations_included_count,
        "provider_visible_count": provider_visible_count,
        "used_in_forecast_count": used_in_forecast_count,
        "post_forecast_data_used_count": post_forecast_data_used_count,
        "actual_value_used_count": actual_value_used_count,
        "post_event_revision_used_count": post_event_revision_used_count,
        "market_state_pack_write_count": market_state_pack_write_count,
        "provider_prompt_change_count": provider_prompt_change_count,
        "v1_sheet_write_count": v1_sheet_write_count,
        "production_behavior_change_count": production_behavior_change_count,
        "refinement_run_id": refinement_run_id,
        "refined_field_count": refined_field_count,
        "downgraded_field_count": downgraded_field_count,
        "early_pack_level_eligible_count": early_pack_level_eligible_count,
        "early_pack_level_ineligible_count": early_pack_level_ineligible_count,
        "normal_session_no_start_candle_count": normal_session_no_start_candle_count,
        "normal_session_no_start_candle_repaired_count": normal_session_no_start_candle_repaired_count,
        "weekend_gap_missing_count": weekend_gap_missing_count,
        "notes": _truncate_text(json.dumps({"warnings": list(warnings)}, ensure_ascii=True), 500),
    }


def _run_log_row(
    generated_ts: str,
    shadow_pack_run_id: str,
    started_ts: str,
    completed_ts: str,
    runtime_seconds: float,
    input_found: Sequence[str],
    input_missing: Sequence[str],
    summary: Dict[str, Any],
    error_message: str = "",
) -> Dict[str, Any]:
    safety_ok = all(
        _safe_int(summary.get(name)) == 0
        for name in [
            "fed_expectations_included_count",
            "provider_visible_count",
            "used_in_forecast_count",
            "post_forecast_data_used_count",
            "actual_value_used_count",
            "post_event_revision_used_count",
            "market_state_pack_write_count",
            "provider_prompt_change_count",
            "v1_sheet_write_count",
            "production_behavior_change_count",
        ]
    )
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "shadow_pack_run_id": shadow_pack_run_id,
        "script_name": "build_market_state_pack_shadow_v0.py",
        "build_status": _norm(summary.get("build_status")),
        "final_interpretation": _norm(summary.get("final_interpretation")),
        "started_ts": started_ts,
        "completed_ts": completed_ts,
        "runtime_seconds": round(runtime_seconds, 3),
        "input_sheets_found": "|".join(sorted(dict.fromkeys(input_found))),
        "input_sheets_missing": "|".join(sorted(dict.fromkeys(input_missing))),
        "output_sheets_written": "|".join(
            [
                OUTPUT_SHADOW_SHEET,
                OUTPUT_SUMMARY_SHEET,
                OUTPUT_ITEM_AUDIT_SHEET,
                OUTPUT_COVERAGE_SHEET,
                OUTPUT_RUN_LOG_SHEET,
            ]
        ),
        "candidate_families_in_scope": "|".join(INCLUDED_FAMILIES),
        "candidate_families_excluded": "|".join(EXCLUDED_FAMILIES),
        "safety_status": "PASS" if safety_ok else "FAIL",
        "error_message": error_message,
        "notes": _truncate_text(
            f"sessions_processed={_safe_int(summary.get('sessions_processed'))}; successful_field_count={_safe_int(summary.get('successful_field_count'))}; missing_field_count={_safe_int(summary.get('missing_field_count'))}",
            300,
        ),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        {
            "logical_sheet_id": "MARKET_STATE_PACK_SHADOW",
            "physical_sheet_name": OUTPUT_SHADOW_SHEET,
            "sheet_role": "shadow_market_state_values",
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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 deterministic market-state values only; not provider-visible",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_SHADOW_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "shadow_market_state_summary",
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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 deterministic market-state summary only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_ITEM_AUDIT",
            "physical_sheet_name": OUTPUT_ITEM_AUDIT_SHEET,
            "sheet_role": "shadow_market_state_item_audit",
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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 deterministic market-state field audit only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_COVERAGE_AUDIT",
            "physical_sheet_name": OUTPUT_COVERAGE_SHEET,
            "sheet_role": "shadow_market_state_coverage_audit",
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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 deterministic market-state family coverage only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_SHADOW_RUN_LOG",
            "physical_sheet_name": OUTPUT_RUN_LOG_SHEET,
            "sheet_role": "shadow_market_state_run_log",
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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 deterministic market-state run log only",
        },
    ]

    updates: List[Dict[str, Any]] = []
    appended = 0
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Controlled Shadow Acquisition v0.")
    return parser.parse_args(argv)


def build_market_state_pack_shadow_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    started_ts = _iso_now()
    started_mono = time.monotonic()
    generated_ts = started_ts
    shadow_pack_run_id = _shadow_pack_run_id(generated_ts)
    warnings: List[str] = []

    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)

    diagnostics_titles = _get_sheet_titles(sheets_service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(sheets_service, MAIN_SPREADSHEET_ID)

    missing_diag: List[str] = []
    missing_main: List[str] = []

    mapping_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, MAPPING_SHEET, missing_diag)
    semantics_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, SEMANTICS_SHEET, missing_diag)
    mapping_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, MAPPING_SUMMARY_SHEET, missing_diag)

    market_sessions_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, MARKET_SESSIONS_SHEET, missing_diag)
    market_session_members_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, MARKET_SESSION_MEMBERS_SHEET, missing_diag)
    attention_history_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, ATTENTION_HISTORY_SHEET, missing_diag)
    info_history_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INFO_HISTORY_SHEET, missing_diag)
    evaluation_history_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, EVALUATION_HISTORY_SHEET, missing_diag)
    baseline_history_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, BASELINE_HISTORY_SHEET, missing_diag)
    replay_queue_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, REPLAY_QUEUE_SHEET, missing_diag)

    event_rows = _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, EVENT_SHEET, missing_main)
    _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, CONFIG_SHEET, missing_main)
    _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, FRED_SERIES_SHEET, missing_main)
    _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, FMP_EVENT_CATALOG_SHEET, missing_main)
    _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, SERIES_MAP_SHEET, missing_main)
    _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, SERIES_MAP_SUGGESTIONS_SHEET, missing_main)

    if not mapping_rows or not semantics_rows or not mapping_summary_rows:
        mapping_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHADOW_SHEET, SHADOW_HEADERS)
        summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
        item_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEM_AUDIT_SHEET, ITEM_AUDIT_HEADERS)
        coverage_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COVERAGE_SHEET, COVERAGE_HEADERS)
        log_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHADOW_SHEET, mapping_headers, [])
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEM_AUDIT_SHEET, item_headers, [])
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COVERAGE_SHEET, coverage_headers, [])
        summary_row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "shadow_pack_run_id": shadow_pack_run_id,
            "build_status": "FAIL",
            "final_interpretation": "MARKET_STATE_PACK_SHADOW_REFINEMENT_BLOCKED",
            "sessions_processed": 0,
            "candidate_families_in_scope": len(INCLUDED_FAMILIES),
            "candidate_fields_in_scope": sum(len(v) for v in FAMILY_FIELD_ORDER.values()),
            "shadow_rows_written": 0,
            "item_audit_rows_written": 0,
            "coverage_rows_written": 0,
            "successful_field_count": 0,
            "missing_field_count": 0,
            "warning_field_count": 0,
            "failed_field_count": 0,
            "complete_session_count": 0,
            "partial_session_count": 0,
            "blocked_family_count": len(EXCLUDED_FAMILIES),
            "fed_expectations_included_count": 0,
            "provider_visible_count": 0,
            "used_in_forecast_count": 0,
            "post_forecast_data_used_count": 0,
            "actual_value_used_count": 0,
            "post_event_revision_used_count": 0,
            "market_state_pack_write_count": 0,
            "provider_prompt_change_count": 0,
            "v1_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "notes": "Required Phase 8A-3 mapping sheets missing",
        }
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
        completed_ts = _iso_now()
        run_log = _run_log_row(
            generated_ts,
            shadow_pack_run_id,
            started_ts,
            completed_ts,
            time.monotonic() - started_mono,
            [],
            [MAPPING_SHEET, SEMANTICS_SHEET, MAPPING_SUMMARY_SHEET],
            summary_row,
            "Required Phase 8A-3 mapping sheets missing",
        )
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RUN_LOG_SHEET, log_headers, [run_log])
        registry = _upsert_registry_rows(sheets_service)
        return {
            "shadow_pack_run_id": shadow_pack_run_id,
            "build_status": summary_row["build_status"],
            "final_interpretation": summary_row["final_interpretation"],
            "registry": registry,
            "summary": summary_row,
            "warnings": [],
            "errors": ["Required Phase 8A-3 mapping sheets missing"],
        }

    mapping_by_field = _mapping_rows_by_field(mapping_rows)
    semantics_by_field = _semantics_rows_by_field(semantics_rows)
    sessions = _session_metadata(
        market_sessions_rows,
        replay_queue_rows,
        attention_history_rows,
        info_history_rows,
        evaluation_history_rows,
        baseline_history_rows,
    )
    if not sessions:
        warnings.append("No sessions found from Market_Sessions, replay queue, or replay history.")

    shadow_rows: List[Dict[str, Any]] = []
    item_audit_rows: List[Dict[str, Any]] = []
    session_ids: List[str] = []

    for session in sessions:
        session_id = _norm(session.get("session_id"))
        forecast_timestamp = _norm(session.get("forecast_timestamp"))
        if not session_id:
            continue
        session_ids.append(session_id)
        if not forecast_timestamp:
            warnings.append(f"Missing forecast_timestamp for session {session_id}")
            snapshot_payload = {}
        else:
            try:
                snapshot_payload = run_script_function(
                    script_service,
                    default_script_id(),
                    "apiBuildMarketStateShadowSnapshot",
                    [{"cutoff_ts": forecast_timestamp}],
                )
            except Exception as exc:
                snapshot_payload = {}
                warnings.append(f"Shadow snapshot fetch failed for {session_id}: {exc}")
        session_shadow_rows, session_item_audits = _build_session_field_rows(
            generated_ts,
            shadow_pack_run_id,
            session,
            mapping_by_field,
            semantics_by_field,
            event_rows,
            snapshot_payload if isinstance(snapshot_payload, dict) else {},
        )
        shadow_rows.extend(session_shadow_rows)
        item_audit_rows.extend(session_item_audits)

    coverage_rows = _coverage_rows(generated_ts, shadow_pack_run_id, session_ids, item_audit_rows)
    summary_row = _summary_row(generated_ts, shadow_pack_run_id, session_ids, shadow_rows, item_audit_rows, coverage_rows, warnings)

    shadow_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHADOW_SHEET, SHADOW_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    item_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEM_AUDIT_SHEET, ITEM_AUDIT_HEADERS)
    coverage_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COVERAGE_SHEET, COVERAGE_HEADERS)
    log_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS)

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHADOW_SHEET, shadow_headers, shadow_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEM_AUDIT_SHEET, item_headers, item_audit_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COVERAGE_SHEET, coverage_headers, coverage_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    completed_ts = _iso_now()
    run_log_row = _run_log_row(
        generated_ts,
        shadow_pack_run_id,
        started_ts,
        completed_ts,
        time.monotonic() - started_mono,
        input_found=[
            MAPPING_SHEET,
            SEMANTICS_SHEET,
            MAPPING_SUMMARY_SHEET,
            MARKET_SESSIONS_SHEET,
            MARKET_SESSION_MEMBERS_SHEET,
            ATTENTION_HISTORY_SHEET,
            INFO_HISTORY_SHEET,
            EVENT_SHEET,
            CONFIG_SHEET,
            FRED_SERIES_SHEET,
            FMP_EVENT_CATALOG_SHEET,
            SERIES_MAP_SHEET,
            SERIES_MAP_SUGGESTIONS_SHEET,
        ],
        input_missing=sorted(set(missing_diag + missing_main)),
        summary=summary_row,
    )
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RUN_LOG_SHEET, log_headers, [run_log_row])
    registry = _upsert_registry_rows(sheets_service)

    return {
        "shadow_pack_run_id": shadow_pack_run_id,
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "sheets_written": {
            OUTPUT_SHADOW_SHEET: len(shadow_rows),
            OUTPUT_ITEM_AUDIT_SHEET: len(item_audit_rows),
            OUTPUT_COVERAGE_SHEET: len(coverage_rows),
            OUTPUT_SUMMARY_SHEET: 1,
            OUTPUT_RUN_LOG_SHEET: 1,
        },
        "sessions_processed": len(session_ids),
        "candidate_families_included": INCLUDED_FAMILIES,
        "candidate_families_excluded": EXCLUDED_FAMILIES,
        "successful_field_count": summary_row["successful_field_count"],
        "missing_field_count": summary_row["missing_field_count"],
        "warning_field_count": summary_row["warning_field_count"],
        "failed_field_count": summary_row["failed_field_count"],
        "complete_session_count": summary_row["complete_session_count"],
        "partial_session_count": summary_row["partial_session_count"],
        "warnings": warnings,
        "errors": [],
        "registry": registry,
        "summary": summary_row,
    }


def main() -> None:
    result = build_market_state_pack_shadow_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
