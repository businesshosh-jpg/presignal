import argparse
import json
import sys
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
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


INPUT_AUDIT_SHEET = "Market_State_Source_Audit"
INPUT_AUDIT_DETAIL_SHEET = "Market_State_Source_Audit_Candidate_Detail"
INPUT_AUDIT_SUMMARY_SHEET = "Market_State_Source_Audit_Summary"
INPUT_CANDIDATE_SHEET = "Market_State_Pack_Candidates"
INPUT_BACKLOG_SHEET = "Market_State_Pack_Acquisition_Backlog"
INPUT_CANDIDATE_SUMMARY_SHEET = "Market_State_Pack_Candidate_Summary"

REFERENCE_SHEETS_MAIN = [
    "Config",
    "FRED_Series_ID",
    "FMP_EventCatalog",
    "Event",
    "SeriesMap",
    "SeriesMap_Suggestions",
]
REFERENCE_SHEETS_DIAGNOSTICS = [
    "Session_Information_Requests_History",
    "Information_Requirement_Library",
]

OUTPUT_MAPPING_SHEET = "Market_State_Source_Mapping"
OUTPUT_SEMANTICS_SHEET = "Market_State_Source_Semantics"
OUTPUT_SUMMARY_SHEET = "Market_State_Source_Mapping_Summary"

SCHEMA_VERSION = "presignal_v2_market_state_source_mapping_0.1"
SHADOW_VERSION = "shadow_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 8A-3"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_STATE_SOURCE_MAPPING"
REGISTRY_OWNER_MODULE = "market_state"

IN_SCOPE_FAMILIES = [
    "treasury_yields",
    "dxy",
    "usdjpy_trend",
    "fed_expectations",
    "upcoming_larger_events",
]

ALLOWED_SUMMARY_INTERPRETATIONS = {
    "MARKET_STATE_SOURCE_AUDIT_READY",
    "MARKET_STATE_SOURCE_AUDIT_READY_WITH_WARNINGS",
    "MARKET_STATE_SOURCE_AUDIT_NEEDS_REVIEW",
}

MAPPING_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "mapping_run_id",
    "candidate_family",
    "candidate_field",
    "field_status",
    "source_lock_status",
    "primary_provider",
    "primary_source_name",
    "primary_symbol_or_series_id",
    "primary_source_type",
    "primary_frequency",
    "primary_historical_available",
    "primary_intraday_available",
    "primary_timestamp_policy",
    "fallback_provider",
    "fallback_source_name",
    "fallback_symbol_or_series_id",
    "fallback_source_type",
    "fallback_frequency",
    "fallback_rule",
    "acquisition_method",
    "source_priority_rank",
    "point_in_time_rule_id",
    "leakage_rule_id",
    "backtest_safe",
    "expected_latency",
    "cost_risk",
    "license_risk",
    "implementation_difficulty",
    "mapping_decision",
    "blocker",
    "notes",
]

SEMANTICS_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "mapping_run_id",
    "candidate_family",
    "candidate_field",
    "canonical_definition",
    "purpose",
    "unit",
    "direction_interpretation",
    "calculation_window",
    "forecast_cutoff_rule",
    "required_input_timestamp",
    "allowed_data_timestamp",
    "forbidden_data",
    "point_in_time_rule",
    "leakage_rule",
    "missing_data_rule",
    "fallback_semantics",
    "provider_visible_label",
    "provider_visible_description",
    "provider_warning_label",
    "backtest_safe",
    "semantics_status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "mapping_run_id",
    "build_status",
    "final_interpretation",
    "candidate_families_processed",
    "candidate_fields_processed",
    "source_mapping_locked_count",
    "source_mapping_warning_count",
    "source_mapping_blocked_count",
    "ready_for_limited_acquisition_design_count",
    "blocked_true_source_missing_count",
    "backtest_safe_count",
    "point_in_time_rule_count",
    "leakage_rule_count",
    "missing_required_sheet_count",
    "production_value_write_count",
    "market_state_pack_write_count",
    "provider_prompt_change_count",
    "v1_sheet_write_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _mapping_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"market_state_source_mapping_v0_{stamp}"


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _get_sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _read_optional_rows(
    service,
    spreadsheet_id: str,
    sheet_titles: Set[str],
    sheet_name: str,
    missing_sheets: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in sheet_titles:
        missing_sheets.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing_sheets.append(sheet_name)
        return []


def _require_rows(sheet_name: str, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")


def _candidate_status_map(candidate_rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in candidate_rows:
        family = _norm(row.get("information_category")).lower()
        if family not in IN_SCOPE_FAMILIES:
            continue
        existing = out.get(family)
        if existing:
            continue
        out[family] = _norm(row.get("candidate_status")) or "CANDIDATE_FEATURE"
    return out


def _detail_map(detail_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("candidate_family")).lower(): row for row in detail_rows if _norm(row.get("candidate_family"))}


def _audit_index(audit_rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    out: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in audit_rows:
        key = (_norm(row.get("candidate_family")).lower(), _norm(row.get("candidate_field")))
        out.setdefault(key, []).append(row)
    return out


def _find_audit_row(
    audit_rows: Sequence[Dict[str, Any]],
    provider: str,
    symbol: str,
) -> Dict[str, Any]:
    provider_u = _upper(provider)
    symbol_n = _norm(symbol)
    for row in audit_rows:
        if _upper(row.get("provider")) != provider_u:
            continue
        if _norm(row.get("symbol_or_series_id")) == symbol_n:
            return row
    return {}


def _bool_or_unknown(value: Any, default: str = "UNKNOWN") -> str:
    raw = _upper(value)
    if raw in {"TRUE", "FALSE", "UNKNOWN"}:
        return raw
    return default


def _mapping_status(
    family: str,
    candidate_field: str,
) -> Tuple[str, str, str]:
    if family == "treasury_yields":
        return (
            "SOURCE_MAPPING_LOCKED_WITH_WARNINGS",
            "LOCKED_WITH_WARNINGS",
            "READY_WITH_WARNINGS_FOR_LIMITED_ACQUISITION_DESIGN",
        )
    if family == "dxy":
        return (
            "SOURCE_MAPPING_LOCKED_WITH_WARNINGS",
            "LOCKED_WITH_WARNINGS",
            "READY_WITH_WARNINGS_FOR_LIMITED_ACQUISITION_DESIGN",
        )
    if family == "usdjpy_trend":
        return (
            "SOURCE_MAPPING_LOCKED",
            "LOCKED",
            "READY_FOR_LIMITED_ACQUISITION_DESIGN",
        )
    if family == "upcoming_larger_events":
        return (
            "SOURCE_MAPPING_LOCKED",
            "LOCKED",
            "READY_FOR_LIMITED_ACQUISITION_DESIGN",
        )
    if family == "fed_expectations" and candidate_field == "FED_EXPECTATION_PROXY_FROM_US2Y":
        return (
            "SOURCE_MAPPING_NEEDS_REVIEW",
            "NEEDS_REVIEW",
            "BLOCKED_TRUE_SOURCE_MISSING",
        )
    return (
        "BLOCKED_SOURCE_UNCLEAR",
        "BLOCKED",
        "BLOCKED_TRUE_SOURCE_MISSING",
    )


def _semantics_status(family: str, candidate_field: str) -> str:
    if family == "treasury_yields":
        return "LOCKED_WITH_WARNINGS"
    if family == "dxy":
        return "LOCKED_WITH_WARNINGS"
    if family == "usdjpy_trend":
        return "LOCKED"
    if family == "upcoming_larger_events":
        return "LOCKED"
    if family == "fed_expectations" and candidate_field == "FED_EXPECTATION_PROXY_FROM_US2Y":
        return "NEEDS_REVIEW"
    return "BLOCKED"


def _audit_notes(family: str, field: str, audit_rows: Sequence[Dict[str, Any]], detail_row: Dict[str, Any]) -> str:
    provider_symbols = []
    for row in audit_rows:
        provider = _norm(row.get("provider"))
        symbol = _norm(row.get("symbol_or_series_id"))
        if provider or symbol:
            provider_symbols.append(f"{provider}[{symbol}]")
    bits = []
    if provider_symbols:
        bits.append("audit_sources=" + ", ".join(sorted(dict.fromkeys(provider_symbols))))
    if detail_row:
        bits.append("phase8a2_decision=" + _norm(detail_row.get("phase8a2_decision")))
        bits.append("source_found_count=" + str(_safe_int(detail_row.get("source_found_count"))))
        bits.append("source_warning_count=" + str(_safe_int(detail_row.get("source_warning_count"))))
    bits.append(f"field={field}")
    return _truncate_text("; ".join(bits), 350)


def _make_mapping_row(
    generated_ts: str,
    mapping_run_id: str,
    candidate_family: str,
    candidate_field: str,
    field_status: str,
    source_lock_status: str,
    primary_provider: str,
    primary_source_name: str,
    primary_symbol_or_series_id: str,
    primary_source_type: str,
    primary_frequency: str,
    primary_historical_available: str,
    primary_intraday_available: str,
    primary_timestamp_policy: str,
    fallback_provider: str,
    fallback_source_name: str,
    fallback_symbol_or_series_id: str,
    fallback_source_type: str,
    fallback_frequency: str,
    fallback_rule: str,
    acquisition_method: str,
    source_priority_rank: Any,
    point_in_time_rule_id: str,
    leakage_rule_id: str,
    backtest_safe: str,
    expected_latency: str,
    cost_risk: str,
    license_risk: str,
    implementation_difficulty: str,
    mapping_decision: str,
    blocker: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "mapping_run_id": mapping_run_id,
        "candidate_family": candidate_family,
        "candidate_field": candidate_field,
        "field_status": field_status,
        "source_lock_status": source_lock_status,
        "primary_provider": primary_provider,
        "primary_source_name": primary_source_name,
        "primary_symbol_or_series_id": primary_symbol_or_series_id,
        "primary_source_type": primary_source_type,
        "primary_frequency": primary_frequency,
        "primary_historical_available": primary_historical_available,
        "primary_intraday_available": primary_intraday_available,
        "primary_timestamp_policy": primary_timestamp_policy,
        "fallback_provider": fallback_provider,
        "fallback_source_name": fallback_source_name,
        "fallback_symbol_or_series_id": fallback_symbol_or_series_id,
        "fallback_source_type": fallback_source_type,
        "fallback_frequency": fallback_frequency,
        "fallback_rule": fallback_rule,
        "acquisition_method": acquisition_method,
        "source_priority_rank": source_priority_rank,
        "point_in_time_rule_id": point_in_time_rule_id,
        "leakage_rule_id": leakage_rule_id,
        "backtest_safe": backtest_safe,
        "expected_latency": expected_latency,
        "cost_risk": cost_risk,
        "license_risk": license_risk,
        "implementation_difficulty": implementation_difficulty,
        "mapping_decision": mapping_decision,
        "blocker": blocker,
        "notes": _truncate_text(notes, 400),
    }


def _make_semantics_row(
    generated_ts: str,
    mapping_run_id: str,
    candidate_family: str,
    candidate_field: str,
    canonical_definition: str,
    purpose: str,
    unit: str,
    direction_interpretation: str,
    calculation_window: str,
    forecast_cutoff_rule: str,
    required_input_timestamp: str,
    allowed_data_timestamp: str,
    forbidden_data: str,
    point_in_time_rule: str,
    leakage_rule: str,
    missing_data_rule: str,
    fallback_semantics: str,
    provider_visible_label: str,
    provider_visible_description: str,
    provider_warning_label: str,
    backtest_safe: str,
    semantics_status: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "mapping_run_id": mapping_run_id,
        "candidate_family": candidate_family,
        "candidate_field": candidate_field,
        "canonical_definition": canonical_definition,
        "purpose": purpose,
        "unit": unit,
        "direction_interpretation": direction_interpretation,
        "calculation_window": calculation_window,
        "forecast_cutoff_rule": forecast_cutoff_rule,
        "required_input_timestamp": required_input_timestamp,
        "allowed_data_timestamp": allowed_data_timestamp,
        "forbidden_data": forbidden_data,
        "point_in_time_rule": point_in_time_rule,
        "leakage_rule": leakage_rule,
        "missing_data_rule": missing_data_rule,
        "fallback_semantics": fallback_semantics,
        "provider_visible_label": provider_visible_label,
        "provider_visible_description": provider_visible_description,
        "provider_warning_label": provider_warning_label,
        "backtest_safe": backtest_safe,
        "semantics_status": semantics_status,
        "notes": _truncate_text(notes, 400),
    }


def _treasury_specs() -> List[Dict[str, str]]:
    common = {
        "family": "treasury_yields",
        "primary_provider": "FRED",
        "primary_source_name": "FRED Treasury Yield Series",
        "primary_source_type": "fred_daily_series",
        "primary_frequency": "DAILY",
        "primary_historical_available": "TRUE",
        "primary_intraday_available": "FALSE",
        "primary_timestamp_policy": "latest_known_before_forecast; if same-day publish time is not confirmed, use prior available business-day observation",
        "fallback_provider": "FederalReserve",
        "fallback_source_name": "H.15 Reference Publication",
        "fallback_symbol_or_series_id": "H.15",
        "fallback_source_type": "publication_reference",
        "fallback_frequency": "DAILY",
        "fallback_rule": "Use only as a reference/fallback validation path; do not assume same-day availability without publication-time confirmation",
        "cost_risk": "LOW",
        "license_risk": "LOW",
        "implementation_difficulty": "LOW",
        "expected_latency": "daily_publication_dependent",
        "point_in_time_rule_id": "PIT_FRED_DAILY_PRIOR_KNOWN",
        "leakage_rule_id": "LEAK_NO_UNCONFIRMED_SAME_DAY_FRED",
        "backtest_safe": "TRUE",
        "acquisition_method": "deterministic_fetch",
        "source_priority_rank": "1",
        "blocker": "Same-day FRED publication timing must be preserved; do not assume same-day observation was known before forecast_timestamp.",
        "forecast_cutoff_rule": "Use the latest observation known before forecast_timestamp. If same-day publish time is not confirmed, fall back to the prior business-day observation.",
        "required_input_timestamp": "series observation date and publication availability before forecast_timestamp",
        "allowed_data_timestamp": "daily yield observation available at or before forecast_timestamp",
        "forbidden_data": "same-day yield value with unconfirmed publication time; any value first known after forecast_timestamp",
        "point_in_time_rule": "Point-in-time safe only when the chosen yield observation was already available before forecast_timestamp; otherwise use the prior business-day value.",
        "leakage_rule": "Never use same-day daily observations if publication-time availability is not confirmed before forecast_timestamp.",
        "missing_data_rule": "If the required observation is unavailable, use the most recent earlier business-day value and flag the field as fallback-applied.",
        "fallback_semantics": "Fallback remains a treasury-yield field; it does not change the meaning of the metric, only the source hierarchy.",
        "provider_warning_label": "Daily series timing caution: same-day values may lag publication.",
    }
    return [
        {
            **common,
            "field": "US2Y_YIELD_LEVEL",
            "primary_symbol": "DGS2",
            "canonical_definition": "Latest known US 2-year Treasury yield level before forecast_timestamp.",
            "purpose": "Capture the short-end rate level relevant to Fed-path transmission.",
            "unit": "percent",
            "direction_interpretation": "Higher value indicates a more elevated short-rate backdrop; interpretation is contextual, not directional advice.",
            "calculation_window": "single latest-known level",
            "provider_visible_label": "US 2Y Yield Level",
            "provider_visible_description": "Latest known US 2-year Treasury yield level before the forecast cutoff.",
        },
        {
            **common,
            "field": "US10Y_YIELD_LEVEL",
            "primary_symbol": "DGS10",
            "canonical_definition": "Latest known US 10-year Treasury yield level before forecast_timestamp.",
            "purpose": "Capture the long-end rate level relevant to broad USD/risk transmission.",
            "unit": "percent",
            "direction_interpretation": "Higher value indicates a more elevated long-rate backdrop; interpretation is contextual, not directional advice.",
            "calculation_window": "single latest-known level",
            "provider_visible_label": "US 10Y Yield Level",
            "provider_visible_description": "Latest known US 10-year Treasury yield level before the forecast cutoff.",
        },
        {
            **common,
            "field": "US2Y_CHANGE_FROM_PRIOR_CLOSE",
            "primary_symbol": "DGS2",
            "canonical_definition": "Change in US 2-year Treasury yield from the prior known business-day close to the latest known pre-forecast observation.",
            "purpose": "Capture recent short-end rate drift entering the session.",
            "unit": "basis_points",
            "direction_interpretation": "Positive means the 2Y yield is higher versus the prior close; negative means lower.",
            "calculation_window": "prior available close to latest known pre-forecast observation",
            "provider_visible_label": "US 2Y Change From Prior Close",
            "provider_visible_description": "Pre-session change in the US 2-year Treasury yield versus the prior known close.",
        },
        {
            **common,
            "field": "US10Y_CHANGE_FROM_PRIOR_CLOSE",
            "primary_symbol": "DGS10",
            "canonical_definition": "Change in US 10-year Treasury yield from the prior known business-day close to the latest known pre-forecast observation.",
            "purpose": "Capture recent long-end rate drift entering the session.",
            "unit": "basis_points",
            "direction_interpretation": "Positive means the 10Y yield is higher versus the prior close; negative means lower.",
            "calculation_window": "prior available close to latest known pre-forecast observation",
            "provider_visible_label": "US 10Y Change From Prior Close",
            "provider_visible_description": "Pre-session change in the US 10-year Treasury yield versus the prior known close.",
        },
        {
            **common,
            "field": "US10Y_MINUS_US2Y_CURVE",
            "primary_symbol": "DGS10-DGS2",
            "canonical_definition": "Difference between the latest known US 10-year yield and the latest known US 2-year yield before forecast_timestamp.",
            "purpose": "Capture curve shape entering the session.",
            "unit": "basis_points",
            "direction_interpretation": "Positive means a steeper curve; lower or negative means a flatter/inverted curve.",
            "calculation_window": "latest known DGS10 minus latest known DGS2 before forecast_timestamp",
            "provider_visible_label": "US 10Y Minus 2Y Curve",
            "provider_visible_description": "Pre-session slope between the US 10-year and US 2-year Treasury yields.",
        },
    ]


def _dxy_specs() -> List[Dict[str, str]]:
    return [
        {
            "family": "dxy",
            "field": "DXY_LEVEL",
            "primary_provider": "FMP",
            "primary_source_name": "FMP DXY",
            "primary_symbol": "DX-Y.NYB",
            "primary_source_type": "market_index_price_daily",
            "primary_frequency": "DAILY",
            "primary_historical_available": "TRUE",
            "primary_intraday_available": "FALSE",
            "primary_timestamp_policy": "use the latest DXY price or bar that was available before forecast_timestamp; do not infer intraday availability unless explicitly mapped later",
            "fallback_provider": "",
            "fallback_source_name": "",
            "fallback_symbol_or_series_id": "",
            "fallback_source_type": "",
            "fallback_frequency": "",
            "fallback_rule": "No automatic fallback. Do not substitute a broad USD proxy for actual DXY.",
            "acquisition_method": "deterministic_fetch",
            "source_priority_rank": "1",
            "point_in_time_rule_id": "PIT_DXY_PRE_FORECAST_BAR",
            "leakage_rule_id": "LEAK_NO_POST_FORECAST_DXY_PRICE",
            "backtest_safe": "TRUE",
            "expected_latency": "market_data_close_or_bar_dependent",
            "cost_risk": "LOW",
            "license_risk": "LOW",
            "implementation_difficulty": "LOW",
            "canonical_definition": "Latest known actual DXY level available before forecast_timestamp.",
            "purpose": "Capture broad USD level using the actual DXY path, not a proxy.",
            "unit": "index_level",
            "direction_interpretation": "Higher means a stronger broad USD backdrop; lower means weaker.",
            "calculation_window": "single latest-known level",
            "forecast_cutoff_rule": "Use only the latest DXY price or daily close known before forecast_timestamp.",
            "required_input_timestamp": "price/bar timestamp at or before forecast_timestamp",
            "allowed_data_timestamp": "actual DXY bar or close available before forecast_timestamp",
            "forbidden_data": "post-forecast bars or any broad-USD proxy substituted as if it were actual DXY",
            "point_in_time_rule": "Only actual DXY data known before forecast_timestamp may populate this field.",
            "leakage_rule": "Never use post-forecast DXY prices or replace DXY with a proxy source.",
            "missing_data_rule": "If actual DXY is unavailable, leave the field blank and use proxy fields separately rather than substituting.",
            "fallback_semantics": "No fallback substitution is allowed because proxy and actual DXY are semantically different.",
            "provider_visible_label": "DXY Level",
            "provider_visible_description": "Latest known actual DXY level before the forecast cutoff.",
            "provider_warning_label": "Do not substitute proxy USD indexes for DXY.",
            "blocker": "Timestamp semantics still depend on exact data-granularity mapping.",
        },
        {
            "family": "dxy",
            "field": "DXY_CHANGE_PRESESSION",
            "primary_provider": "FMP",
            "primary_source_name": "FMP DXY",
            "primary_symbol": "DX-Y.NYB",
            "primary_source_type": "market_index_price_daily",
            "primary_frequency": "DAILY",
            "primary_historical_available": "TRUE",
            "primary_intraday_available": "FALSE",
            "primary_timestamp_policy": "compute from the latest known pre-session DXY point and the prior known comparison point before forecast_timestamp",
            "fallback_provider": "",
            "fallback_source_name": "",
            "fallback_symbol_or_series_id": "",
            "fallback_source_type": "",
            "fallback_frequency": "",
            "fallback_rule": "No automatic proxy fallback for actual DXY change fields.",
            "acquisition_method": "computed_feature",
            "source_priority_rank": "1",
            "point_in_time_rule_id": "PIT_DXY_PRE_FORECAST_BAR",
            "leakage_rule_id": "LEAK_NO_POST_FORECAST_DXY_PRICE",
            "backtest_safe": "TRUE",
            "expected_latency": "market_data_close_or_bar_dependent",
            "cost_risk": "LOW",
            "license_risk": "LOW",
            "implementation_difficulty": "LOW",
            "canonical_definition": "Change in actual DXY over the defined pre-session comparison window ending at forecast_timestamp.",
            "purpose": "Capture recent broad USD momentum entering the session.",
            "unit": "percent_change",
            "direction_interpretation": "Positive means DXY rose into the session; negative means it fell.",
            "calculation_window": "pre-session comparison window ending at forecast_timestamp",
            "forecast_cutoff_rule": "Use only prices known before forecast_timestamp for both endpoints.",
            "required_input_timestamp": "start and end timestamps at or before forecast_timestamp",
            "allowed_data_timestamp": "pre-forecast DXY price points only",
            "forbidden_data": "post-forecast prices and proxy substitutions",
            "point_in_time_rule": "Both comparison endpoints must be known before forecast_timestamp.",
            "leakage_rule": "No post-forecast price may enter either endpoint.",
            "missing_data_rule": "If the comparison window cannot be constructed safely, leave the field blank.",
            "fallback_semantics": "No semantic fallback to a proxy field.",
            "provider_visible_label": "DXY Change Pre-Session",
            "provider_visible_description": "Actual DXY change over the defined pre-session window before the forecast cutoff.",
            "provider_warning_label": "Actual DXY only; no proxy substitution.",
            "blocker": "Exact comparison window still needs final operational mapping.",
        },
        {
            "family": "dxy",
            "field": "DXY_DIRECTION_LABEL",
            "primary_provider": "FMP",
            "primary_source_name": "FMP DXY",
            "primary_symbol": "DX-Y.NYB",
            "primary_source_type": "computed_from_market_index_price",
            "primary_frequency": "DAILY",
            "primary_historical_available": "TRUE",
            "primary_intraday_available": "FALSE",
            "primary_timestamp_policy": "derive only from actual DXY observations available before forecast_timestamp",
            "fallback_provider": "",
            "fallback_source_name": "",
            "fallback_symbol_or_series_id": "",
            "fallback_source_type": "",
            "fallback_frequency": "",
            "fallback_rule": "No automatic fallback to proxy fields for DXY direction labels.",
            "acquisition_method": "computed_feature",
            "source_priority_rank": "1",
            "point_in_time_rule_id": "PIT_DXY_PRE_FORECAST_BAR",
            "leakage_rule_id": "LEAK_NO_POST_FORECAST_DXY_PRICE",
            "backtest_safe": "TRUE",
            "expected_latency": "market_data_close_or_bar_dependent",
            "cost_risk": "LOW",
            "license_risk": "LOW",
            "implementation_difficulty": "LOW",
            "canonical_definition": "Categorical label derived from actual DXY pre-session direction before forecast_timestamp.",
            "purpose": "Provide a simplified broad-USD direction cue.",
            "unit": "label",
            "direction_interpretation": "up if DXY rose, down if DXY fell, flat if change is within the configured neutral band.",
            "calculation_window": "same window as DXY_CHANGE_PRESESSION",
            "forecast_cutoff_rule": "Use only pre-forecast DXY data.",
            "required_input_timestamp": "same as DXY_CHANGE_PRESESSION endpoints",
            "allowed_data_timestamp": "pre-forecast DXY values only",
            "forbidden_data": "post-forecast data and proxy substitutions",
            "point_in_time_rule": "Direction label must be derived only from data available before forecast_timestamp.",
            "leakage_rule": "Never derive the label using any post-forecast bar.",
            "missing_data_rule": "If the underlying change cannot be computed safely, leave the label blank.",
            "fallback_semantics": "Proxy direction is a separate field family and must not replace actual DXY direction.",
            "provider_visible_label": "DXY Direction Label",
            "provider_visible_description": "Categorical direction label derived from actual DXY movement before the forecast cutoff.",
            "provider_warning_label": "Actual DXY direction only; proxy labels remain separate.",
            "blocker": "Neutral-band semantics need final operational tolerance setting.",
        },
        {
            "family": "dxy",
            "field": "USD_INDEX_PROXY_LEVEL",
            "primary_provider": "FRED",
            "primary_source_name": "Broad USD Trade-Weighted Proxy",
            "primary_symbol": "DTWEXBGS",
            "primary_source_type": "fred_daily_series_proxy",
            "primary_frequency": "DAILY",
            "primary_historical_available": "UNKNOWN",
            "primary_intraday_available": "FALSE",
            "primary_timestamp_policy": "use the latest known daily proxy value available before forecast_timestamp; if same-day timing is unclear, use the prior available business-day value",
            "fallback_provider": "",
            "fallback_source_name": "",
            "fallback_symbol_or_series_id": "",
            "fallback_source_type": "",
            "fallback_frequency": "",
            "fallback_rule": "This field is itself the proxy path; it should not be relabeled as actual DXY.",
            "acquisition_method": "deterministic_fetch",
            "source_priority_rank": "2",
            "point_in_time_rule_id": "PIT_FRED_PROXY_PRIOR_KNOWN",
            "leakage_rule_id": "LEAK_NO_UNCONFIRMED_SAME_DAY_PROXY",
            "backtest_safe": "UNKNOWN",
            "expected_latency": "daily_publication_dependent",
            "cost_risk": "LOW",
            "license_risk": "LOW",
            "implementation_difficulty": "MEDIUM",
            "canonical_definition": "Latest known broad USD index proxy value available before forecast_timestamp.",
            "purpose": "Provide a broad USD proxy when actual DXY is unavailable or intentionally separated.",
            "unit": "index_level",
            "direction_interpretation": "Higher means a stronger broad USD proxy backdrop.",
            "calculation_window": "single latest-known daily level",
            "forecast_cutoff_rule": "Use only the latest daily proxy value known before forecast_timestamp; otherwise use the prior available business-day value.",
            "required_input_timestamp": "daily proxy observation date and availability before forecast_timestamp",
            "allowed_data_timestamp": "daily proxy value known before forecast_timestamp",
            "forbidden_data": "proxy value labeled as actual DXY; post-forecast values",
            "point_in_time_rule": "Proxy values are allowed only when they were already known before forecast_timestamp.",
            "leakage_rule": "Do not use same-day values with unconfirmed availability.",
            "missing_data_rule": "If the proxy is unavailable, leave the field blank rather than synthesizing an internal basket here.",
            "fallback_semantics": "Proxy remains a proxy and must be labeled distinctly from actual DXY.",
            "provider_visible_label": "USD Index Proxy Level",
            "provider_visible_description": "Latest known broad-USD proxy level before the forecast cutoff, separate from actual DXY.",
            "provider_warning_label": "Proxy only: not equivalent to actual DXY.",
            "blocker": "Proxy symbol confirmation and availability semantics still need review.",
        },
        {
            "family": "dxy",
            "field": "USD_INDEX_PROXY_CHANGE",
            "primary_provider": "FRED",
            "primary_source_name": "Broad USD Trade-Weighted Proxy",
            "primary_symbol": "DTWEXBGS",
            "primary_source_type": "computed_from_fred_daily_proxy",
            "primary_frequency": "DAILY",
            "primary_historical_available": "UNKNOWN",
            "primary_intraday_available": "FALSE",
            "primary_timestamp_policy": "compute from daily proxy values that were known before forecast_timestamp",
            "fallback_provider": "",
            "fallback_source_name": "",
            "fallback_symbol_or_series_id": "",
            "fallback_source_type": "",
            "fallback_frequency": "",
            "fallback_rule": "No substitution into actual DXY fields.",
            "acquisition_method": "computed_feature",
            "source_priority_rank": "2",
            "point_in_time_rule_id": "PIT_FRED_PROXY_PRIOR_KNOWN",
            "leakage_rule_id": "LEAK_NO_UNCONFIRMED_SAME_DAY_PROXY",
            "backtest_safe": "UNKNOWN",
            "expected_latency": "daily_publication_dependent",
            "cost_risk": "LOW",
            "license_risk": "LOW",
            "implementation_difficulty": "MEDIUM",
            "canonical_definition": "Change in the broad USD index proxy over the defined pre-session window ending before forecast_timestamp.",
            "purpose": "Provide a proxy broad-USD momentum measure distinct from actual DXY.",
            "unit": "percent_change",
            "direction_interpretation": "Positive means the proxy strengthened into the session; negative means it weakened.",
            "calculation_window": "pre-session comparison window ending before forecast_timestamp",
            "forecast_cutoff_rule": "Use only proxy values known before forecast_timestamp.",
            "required_input_timestamp": "start and end timestamps known before forecast_timestamp",
            "allowed_data_timestamp": "pre-forecast proxy values only",
            "forbidden_data": "post-forecast values and relabeling as DXY",
            "point_in_time_rule": "Both proxy endpoints must be known before forecast_timestamp.",
            "leakage_rule": "Never include a proxy value first known after forecast_timestamp.",
            "missing_data_rule": "Leave blank if the proxy comparison window cannot be built safely.",
            "fallback_semantics": "Proxy change remains a proxy-only field.",
            "provider_visible_label": "USD Index Proxy Change",
            "provider_visible_description": "Broad-USD proxy change over the defined pre-session window before the forecast cutoff.",
            "provider_warning_label": "Proxy only: not interchangeable with actual DXY.",
            "blocker": "Proxy timing semantics still need confirmation.",
        },
    ]


def _usdjpy_specs() -> List[Dict[str, str]]:
    window_map = {
        "USDJPY_RETURN_1H_PRESESSION": ("1 hour before forecast_timestamp to forecast_timestamp", "1-hour return"),
        "USDJPY_RETURN_4H_PRESESSION": ("4 hours before forecast_timestamp to forecast_timestamp", "4-hour return"),
        "USDJPY_RETURN_24H_PRESESSION": ("24 hours before forecast_timestamp to forecast_timestamp", "24-hour return"),
        "USDJPY_TREND_LABEL": ("same comparison window used for the selected trend-return input", "trend label"),
        "USDJPY_REALIZED_VOL_1H_PRESESSION": ("1 hour of bars ending at or before forecast_timestamp", "1-hour realized volatility"),
    }
    common = {
        "family": "usdjpy_trend",
        "primary_provider": "EODHD",
        "primary_source_name": "USDJPY FX Bars",
        "primary_symbol": "USDJPY.FOREX",
        "primary_source_type": "fx_bar_series",
        "primary_frequency": "INTRADAY",
        "primary_historical_available": "TRUE",
        "primary_intraday_available": "TRUE",
        "primary_timestamp_policy": "use only bars with timestamps at or before forecast_timestamp",
        "fallback_provider": "FMP",
        "fallback_source_name": "USDJPY Daily",
        "fallback_symbol_or_series_id": "USDJPY",
        "fallback_source_type": "daily_fx_series",
        "fallback_frequency": "DAILY",
        "fallback_rule": "Use fallback only for daily-compatible fields; do not use it to emulate missing intraday bars for 1H/4H/volatility fields.",
        "acquisition_method": "computed_feature",
        "source_priority_rank": "1",
        "point_in_time_rule_id": "PIT_USDJPY_PRE_FORECAST_BARS_ONLY",
        "leakage_rule_id": "LEAK_NO_POST_FORECAST_USDJPY_BARS",
        "backtest_safe": "TRUE",
        "expected_latency": "intraday_market_data",
        "cost_risk": "LOW",
        "license_risk": "LOW",
        "implementation_difficulty": "LOW",
        "forecast_cutoff_rule": "All bars used for calculation must end at or before forecast_timestamp.",
        "required_input_timestamp": "intraday bar timestamps at or before forecast_timestamp",
        "allowed_data_timestamp": "only pre-forecast USDJPY bars",
        "forbidden_data": "any price or bar that starts or ends after forecast_timestamp",
        "point_in_time_rule": "Every bar included in the feature must already exist before forecast_timestamp.",
        "leakage_rule": "Never use post-forecast bars, even if they fall on the same calendar date.",
        "missing_data_rule": "If required bars are missing, leave the field blank rather than widening the window with post-cutoff data.",
        "fallback_semantics": "Daily fallback is allowed only where the field remains semantically consistent with daily data.",
        "provider_warning_label": "Strict leakage control: no post-forecast USDJPY bars.",
    }
    specs = []
    for field, (window_text, purpose) in window_map.items():
        definition = {
            "USDJPY_RETURN_1H_PRESESSION": "Percentage return of USDJPY over the 1 hour ending at forecast_timestamp.",
            "USDJPY_RETURN_4H_PRESESSION": "Percentage return of USDJPY over the 4 hours ending at forecast_timestamp.",
            "USDJPY_RETURN_24H_PRESESSION": "Percentage return of USDJPY over the 24 hours ending at forecast_timestamp.",
            "USDJPY_TREND_LABEL": "Categorical label derived from pre-session USDJPY movement before forecast_timestamp.",
            "USDJPY_REALIZED_VOL_1H_PRESESSION": "Realized volatility of USDJPY over the 1 hour ending at forecast_timestamp.",
        }[field]
        unit = {
            "USDJPY_TREND_LABEL": "label",
            "USDJPY_REALIZED_VOL_1H_PRESESSION": "annualized_or_window_volatility",
        }.get(field, "percent_return")
        direction = {
            "USDJPY_TREND_LABEL": "up if USDJPY rose, down if it fell, flat if movement stays within the configured neutral band.",
            "USDJPY_REALIZED_VOL_1H_PRESESSION": "Higher means more realized price variability entering the session.",
        }.get(field, "Positive means USDJPY rose into the session; negative means it fell.")
        specs.append(
            {
                **common,
                "field": field,
                "canonical_definition": definition,
                "purpose": purpose,
                "unit": unit,
                "direction_interpretation": direction,
                "calculation_window": window_text,
                "provider_visible_label": field.replace("_", " ").title(),
                "provider_visible_description": definition,
                "blocker": "",
            }
        )
    return specs


def _fed_specs() -> List[Dict[str, str]]:
    fields = [
        "NEXT_FOMC_CUT_PROBABILITY",
        "NEXT_FOMC_HIKE_PROBABILITY",
        "NEXT_FOMC_NO_CHANGE_PROBABILITY",
        "NEXT_FOMC_MOST_LIKELY_TARGET_RANGE",
        "FED_EXPECTATION_SHIFT_1D",
        "FED_EXPECTATION_SHIFT_1W",
        "FED_EXPECTATION_PROXY_FROM_US2Y",
    ]
    specs = []
    for field in fields:
        is_proxy = field == "FED_EXPECTATION_PROXY_FROM_US2Y"
        specs.append(
            {
                "family": "fed_expectations",
                "field": field,
                "primary_provider": "CME" if not is_proxy else "FRED",
                "primary_source_name": "FedWatch API" if not is_proxy else "US 2Y Yield Proxy",
                "primary_symbol": "FedWatch API" if not is_proxy else "DGS2",
                "primary_source_type": "probability_snapshot_api" if not is_proxy else "proxy_computed_feature",
                "primary_frequency": "SNAPSHOT" if not is_proxy else "DAILY",
                "primary_historical_available": "UNKNOWN" if not is_proxy else "TRUE",
                "primary_intraday_available": "UNKNOWN" if not is_proxy else "FALSE",
                "primary_timestamp_policy": "true point-in-time historical timestamp semantics not yet confirmed" if not is_proxy else "proxy derived only from pre-forecast DGS2 values",
                "fallback_provider": "FRED",
                "fallback_source_name": "DGS2 / DFF / FEDFUNDS Proxy Set",
                "fallback_symbol_or_series_id": "DGS2|DFF|FEDFUNDS",
                "fallback_source_type": "proxy_reference",
                "fallback_frequency": "DAILY",
                "fallback_rule": "Fallback proxies may support research references but must not be labeled as true Fed expectations.",
                "acquisition_method": "source_audit_only" if not is_proxy else "computed_feature",
                "source_priority_rank": "1",
                "point_in_time_rule_id": "PIT_TRUE_FED_EXPECTATION_SOURCE_REQUIRED",
                "leakage_rule_id": "LEAK_NO_PROXY_AS_TRUE_FED_EXPECTATION",
                "backtest_safe": "FALSE" if not is_proxy else "TRUE",
                "expected_latency": "unknown" if not is_proxy else "daily_publication_dependent",
                "cost_risk": "MEDIUM" if not is_proxy else "LOW",
                "license_risk": "MEDIUM" if not is_proxy else "LOW",
                "implementation_difficulty": "HIGH" if not is_proxy else "MEDIUM",
                "canonical_definition": (
                    "Point-in-time market-implied expectation field for the next FOMC outcome."
                    if not is_proxy
                    else "Proxy field derived from US 2Y yield behavior before forecast_timestamp; not a true market-implied FOMC probability."
                ),
                "purpose": (
                    "True Fed expectations input."
                    if not is_proxy
                    else "Research-only proxy for comparing yield-based Fed expectations against future true-source options."
                ),
                "unit": "probability_or_target_range" if not is_proxy else "proxy_signal",
                "direction_interpretation": (
                    "Interpretation depends on true FOMC probabilities or target-range state."
                    if not is_proxy
                    else "Proxy-only. It may suggest tighter/easier Fed tone indirectly but is not a probability."
                ),
                "calculation_window": "point-in-time snapshot before forecast_timestamp" if not is_proxy else "pre-forecast DGS2 change/reference window",
                "forecast_cutoff_rule": "Only a true point-in-time source known before forecast_timestamp may populate the true field." if not is_proxy else "Use only pre-forecast DGS2 values; never relabel the result as true expectations.",
                "required_input_timestamp": "confirmed historical snapshot timestamp before forecast_timestamp" if not is_proxy else "DGS2 observations known before forecast_timestamp",
                "allowed_data_timestamp": "true historical expectation snapshot known before forecast_timestamp" if not is_proxy else "pre-forecast DGS2 data only",
                "forbidden_data": "proxy data labeled as true expectations; any post-forecast expectation value",
                "point_in_time_rule": "Do not unlock true Fed expectations fields without a confirmed point-in-time historical source." if not is_proxy else "Proxy field must still use only pre-forecast data, but it does not satisfy the true-source requirement.",
                "leakage_rule": "Never substitute proxies or post-forecast expectations into true Fed expectations fields.",
                "missing_data_rule": "If true-source snapshots are unavailable, keep the field blocked and blank." if not is_proxy else "If DGS2 is unavailable, leave the proxy blank.",
                "fallback_semantics": "Fallback remains non-equivalent research reference data." if not is_proxy else "Proxy semantics must remain explicitly labeled as proxy semantics.",
                "provider_visible_label": field.replace("_", " ").title(),
                "provider_visible_description": (
                    "Future-design label only. This field remains blocked pending true-source confirmation."
                    if not is_proxy
                    else "Future-design proxy label only. Not a true Fed expectations field."
                ),
                "provider_warning_label": "Blocked: true point-in-time Fed expectations source not confirmed." if not is_proxy else "Proxy only: not true Fed expectations.",
                "blocker": "True point-in-time Fed expectations source is not confirmed." if not is_proxy else "Proxy field cannot unblock true Fed expectations.",
            }
        )
    return specs


def _upcoming_specs() -> List[Dict[str, str]]:
    field_definitions = {
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H": (
            "Boolean flag set to TRUE when a high-importance scheduled event exists after forecast_timestamp and within the next 24 hours.",
            "24 hours after forecast_timestamp",
            "boolean",
        ),
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H": (
            "Boolean flag set to TRUE when a high-importance scheduled event exists after forecast_timestamp and within the next 48 hours.",
            "48 hours after forecast_timestamp",
            "boolean",
        ),
        "NEXT_CPI_OR_FOMC_WITHIN_72H": (
            "Boolean flag set to TRUE when a CPI, FOMC, Fed rate decision, or similarly classified major inflation/Fed event exists after forecast_timestamp and within the next 72 hours.",
            "72 hours after forecast_timestamp",
            "boolean",
        ),
        "NEXT_NFP_WITHIN_7D": (
            "Boolean flag set to TRUE when a Nonfarm Payrolls-style event exists after forecast_timestamp and within the next 7 days.",
            "7 days after forecast_timestamp",
            "boolean",
        ),
        "EVENT_CLUSTER_DENSITY_NEXT_24H": (
            "Count of relevant scheduled events after forecast_timestamp and within the next 24 hours.",
            "24 hours after forecast_timestamp",
            "count",
        ),
        "UPCOMING_EVENT_RISK_LABEL": (
            "Categorical label summarizing near-term scheduled event density and importance after forecast_timestamp.",
            "24 to 72 hours after forecast_timestamp depending on label rule",
            "label",
        ),
    }
    specs = []
    for field, (definition, window_text, unit) in field_definitions.items():
        specs.append(
            {
                "family": "upcoming_larger_events",
                "field": field,
                "primary_provider": "PreSignal",
                "primary_source_name": "Event Sheet",
                "primary_symbol": "Event",
                "primary_source_type": "scheduled_calendar_sheet",
                "primary_frequency": "EVENT_SCHEDULE",
                "primary_historical_available": "TRUE",
                "primary_intraday_available": "FALSE",
                "primary_timestamp_policy": "use only scheduled event rows already known before forecast_timestamp",
                "fallback_provider": "FMP",
                "fallback_source_name": "FMP Event Catalog",
                "fallback_symbol_or_series_id": "FMP_EventCatalog",
                "fallback_source_type": "scheduled_calendar_catalog",
                "fallback_frequency": "EVENT_SCHEDULE",
                "fallback_rule": "Use FMP_EventCatalog or external calendar APIs only when the canonical Event sheet cannot provide the needed scheduled metadata.",
                "acquisition_method": "calendar_derived_feature",
                "source_priority_rank": "1",
                "point_in_time_rule_id": "PIT_SCHEDULED_EVENTS_PRE_FORECAST_ONLY",
                "leakage_rule_id": "LEAK_NO_ACTUALS_NO_POST_EVENT_REVISIONS",
                "backtest_safe": "TRUE",
                "expected_latency": "calendar_refresh_dependent",
                "cost_risk": "LOW",
                "license_risk": "LOW",
                "implementation_difficulty": "LOW",
                "canonical_definition": definition,
                "purpose": "Capture upcoming scheduled-event pressure around the session without using future actuals.",
                "unit": unit,
                "direction_interpretation": (
                    "TRUE means future scheduled event risk is present."
                    if unit == "boolean"
                    else "Higher count or higher risk label means denser upcoming event risk."
                ),
                "calculation_window": window_text,
                "forecast_cutoff_rule": "Include only events scheduled after forecast_timestamp that were already known before forecast_timestamp.",
                "required_input_timestamp": "scheduled event release_ts and pre-forecast calendar availability",
                "allowed_data_timestamp": "scheduled calendar metadata known before forecast_timestamp",
                "forbidden_data": "actual released values, revised actuals, and events first added after forecast_timestamp",
                "point_in_time_rule": "Only use scheduled event information that was already known before forecast_timestamp.",
                "leakage_rule": "Never use actuals or post-event revisions when deriving upcoming-event fields.",
                "missing_data_rule": "If scheduled-event metadata is incomplete, leave the field blank or unknown rather than inferring from actual outcomes.",
                "fallback_semantics": "Fallback sources may fill the same scheduled-event concept if they preserve pre-forecast visibility.",
                "provider_visible_label": field.replace("_", " ").title(),
                "provider_visible_description": definition,
                "provider_warning_label": "Scheduled-event only: no actuals or post-event revisions.",
                "blocker": "",
            }
        )
    return specs


FIELD_SPECS = _treasury_specs() + _dxy_specs() + _usdjpy_specs() + _fed_specs() + _upcoming_specs()


def _build_rows(
    generated_ts: str,
    mapping_run_id: str,
    candidate_statuses: Dict[str, str],
    detail_by_family: Dict[str, Dict[str, Any]],
    audit_by_field: Dict[Tuple[str, str], List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    mapping_rows: List[Dict[str, Any]] = []
    semantics_rows: List[Dict[str, Any]] = []
    for spec in FIELD_SPECS:
        family = spec["family"]
        field = spec["field"]
        audit_rows = audit_by_field.get((family, field), [])
        detail_row = detail_by_family.get(family, {})
        field_status, source_lock_status, mapping_decision = _mapping_status(family, field)
        semantics_status = _semantics_status(family, field)

        primary_audit = _find_audit_row(audit_rows, spec["primary_provider"], spec["primary_symbol"])
        fallback_audit = _find_audit_row(audit_rows, spec["fallback_provider"], spec["fallback_symbol_or_series_id"]) if spec["fallback_provider"] else {}

        primary_hist = _bool_or_unknown(primary_audit.get("historical_available"), spec["primary_historical_available"])
        primary_intraday = _bool_or_unknown(primary_audit.get("intraday_available"), spec["primary_intraday_available"])
        backtest_safe = _bool_or_unknown(primary_audit.get("backtest_safe"), spec["backtest_safe"])

        if family == "fed_expectations" and field != "FED_EXPECTATION_PROXY_FROM_US2Y":
            primary_hist = "UNKNOWN"
            primary_intraday = "UNKNOWN"
            backtest_safe = "FALSE"
        elif family == "fed_expectations":
            backtest_safe = "TRUE"

        if mapping_decision == "BLOCKED_TRUE_SOURCE_MISSING":
            blocker = spec["blocker"]
        elif mapping_decision == "READY_WITH_WARNINGS_FOR_LIMITED_ACQUISITION_DESIGN":
            blocker = spec["blocker"]
        else:
            blocker = spec["blocker"]

        note = _audit_notes(family, field, audit_rows, detail_row)
        if detail_row:
            detail_decision = _norm(detail_row.get("phase8a2_decision"))
            note = _truncate_text(f"{note}; inherited_phase8a2={detail_decision}; candidate_status_in={candidate_statuses.get(family, 'CANDIDATE_FEATURE')}", 400)

        mapping_rows.append(
            _make_mapping_row(
                generated_ts=generated_ts,
                mapping_run_id=mapping_run_id,
                candidate_family=family,
                candidate_field=field,
                field_status=field_status,
                source_lock_status=source_lock_status,
                primary_provider=spec["primary_provider"],
                primary_source_name=spec["primary_source_name"],
                primary_symbol_or_series_id=spec["primary_symbol"],
                primary_source_type=spec["primary_source_type"],
                primary_frequency=spec["primary_frequency"],
                primary_historical_available=primary_hist,
                primary_intraday_available=primary_intraday,
                primary_timestamp_policy=spec["primary_timestamp_policy"],
                fallback_provider=spec["fallback_provider"],
                fallback_source_name=spec["fallback_source_name"],
                fallback_symbol_or_series_id=spec["fallback_symbol_or_series_id"],
                fallback_source_type=spec["fallback_source_type"],
                fallback_frequency=spec["fallback_frequency"],
                fallback_rule=spec["fallback_rule"],
                acquisition_method=spec["acquisition_method"],
                source_priority_rank=spec["source_priority_rank"],
                point_in_time_rule_id=spec["point_in_time_rule_id"],
                leakage_rule_id=spec["leakage_rule_id"],
                backtest_safe=backtest_safe,
                expected_latency=spec["expected_latency"],
                cost_risk=spec["cost_risk"],
                license_risk=spec["license_risk"],
                implementation_difficulty=spec["implementation_difficulty"],
                mapping_decision=mapping_decision,
                blocker=blocker,
                notes=note,
            )
        )

        fallback_text = (
            f"{spec['fallback_source_name']} ({spec['fallback_symbol_or_series_id']})"
            if spec["fallback_source_name"] or spec["fallback_symbol_or_series_id"]
            else "No automatic fallback"
        )
        if fallback_audit:
            fallback_text = f"{fallback_text}; fallback_audit_historical={_bool_or_unknown(fallback_audit.get('historical_available'))}"
        semantics_rows.append(
            _make_semantics_row(
                generated_ts=generated_ts,
                mapping_run_id=mapping_run_id,
                candidate_family=family,
                candidate_field=field,
                canonical_definition=spec["canonical_definition"],
                purpose=spec["purpose"],
                unit=spec["unit"],
                direction_interpretation=spec["direction_interpretation"],
                calculation_window=spec["calculation_window"],
                forecast_cutoff_rule=spec["forecast_cutoff_rule"],
                required_input_timestamp=spec["required_input_timestamp"],
                allowed_data_timestamp=spec["allowed_data_timestamp"],
                forbidden_data=spec["forbidden_data"],
                point_in_time_rule=spec["point_in_time_rule"],
                leakage_rule=spec["leakage_rule"],
                missing_data_rule=spec["missing_data_rule"],
                fallback_semantics=spec["fallback_semantics"] + f" Fallback path: {fallback_text}.",
                provider_visible_label=spec["provider_visible_label"],
                provider_visible_description=spec["provider_visible_description"],
                provider_warning_label=spec["provider_warning_label"],
                backtest_safe=backtest_safe,
                semantics_status=semantics_status,
                notes=note,
            )
        )

    mapping_rows.sort(key=lambda row: (_norm(row.get("candidate_family")), _norm(row.get("candidate_field"))))
    semantics_rows.sort(key=lambda row: (_norm(row.get("candidate_family")), _norm(row.get("candidate_field"))))
    return mapping_rows, semantics_rows


def _build_summary_row(
    generated_ts: str,
    mapping_run_id: str,
    mapping_rows: Sequence[Dict[str, Any]],
    semantics_rows: Sequence[Dict[str, Any]],
    missing_sheets: Sequence[str],
    warnings: Sequence[str],
) -> Dict[str, Any]:
    production_value_write_count = 0
    market_state_pack_write_count = 0
    provider_prompt_change_count = 0
    v1_sheet_write_count = 0

    source_mapping_locked_count = sum(1 for row in mapping_rows if _upper(row.get("field_status")) == "SOURCE_MAPPING_LOCKED")
    source_mapping_warning_count = sum(
        1
        for row in mapping_rows
        if _upper(row.get("field_status")) in {"SOURCE_MAPPING_LOCKED_WITH_WARNINGS", "SOURCE_MAPPING_NEEDS_REVIEW"}
    )
    source_mapping_blocked_count = sum(
        1
        for row in mapping_rows
        if _upper(row.get("field_status")) in {"BLOCKED_SOURCE_UNCLEAR", "BLOCKED_BACKTEST_UNSAFE", "DEFERRED"}
    )
    ready_for_design_count = sum(
        1
        for row in mapping_rows
        if _upper(row.get("mapping_decision")) in {
            "READY_FOR_LIMITED_ACQUISITION_DESIGN",
            "READY_WITH_WARNINGS_FOR_LIMITED_ACQUISITION_DESIGN",
        }
    )
    blocked_true_source_missing_count = sum(
        1 for row in mapping_rows if _upper(row.get("mapping_decision")) == "BLOCKED_TRUE_SOURCE_MISSING"
    )
    backtest_safe_count = sum(1 for row in semantics_rows if _upper(row.get("backtest_safe")) == "TRUE")
    point_in_time_rule_count = len({_norm(row.get("point_in_time_rule_id")) for row in mapping_rows if _norm(row.get("point_in_time_rule_id"))})
    leakage_rule_count = len({_norm(row.get("leakage_rule_id")) for row in mapping_rows if _norm(row.get("leakage_rule_id"))})

    if any([production_value_write_count, market_state_pack_write_count, provider_prompt_change_count, v1_sheet_write_count]):
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_SOURCE_MAPPING_BLOCKED"
    elif not mapping_rows or not semantics_rows:
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_SOURCE_MAPPING_BLOCKED"
    elif source_mapping_blocked_count > 0 or warnings or missing_sheets:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_SOURCE_MAPPING_READY_WITH_WARNINGS"
    elif source_mapping_warning_count > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_SOURCE_MAPPING_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        final_interpretation = "MARKET_STATE_SOURCE_MAPPING_READY"

    notes = _truncate_text(
        "warnings="
        + json.dumps(list(warnings), ensure_ascii=True)
        + "; missing_sheets="
        + json.dumps(list(missing_sheets), ensure_ascii=True),
        500,
    )
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "mapping_run_id": mapping_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "candidate_families_processed": len(IN_SCOPE_FAMILIES),
        "candidate_fields_processed": len(mapping_rows),
        "source_mapping_locked_count": source_mapping_locked_count,
        "source_mapping_warning_count": source_mapping_warning_count,
        "source_mapping_blocked_count": source_mapping_blocked_count,
        "ready_for_limited_acquisition_design_count": ready_for_design_count,
        "blocked_true_source_missing_count": blocked_true_source_missing_count,
        "backtest_safe_count": backtest_safe_count,
        "point_in_time_rule_count": point_in_time_rule_count,
        "leakage_rule_count": leakage_rule_count,
        "missing_required_sheet_count": len(missing_sheets),
        "production_value_write_count": production_value_write_count,
        "market_state_pack_write_count": market_state_pack_write_count,
        "provider_prompt_change_count": provider_prompt_change_count,
        "v1_sheet_write_count": v1_sheet_write_count,
        "notes": notes,
    }


def _blocked_summary_row(generated_ts: str, mapping_run_id: str, message: str, missing_required_sheet_count: int) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "mapping_run_id": mapping_run_id,
        "build_status": "FAIL",
        "final_interpretation": "MARKET_STATE_SOURCE_MAPPING_BLOCKED",
        "candidate_families_processed": 0,
        "candidate_fields_processed": 0,
        "source_mapping_locked_count": 0,
        "source_mapping_warning_count": 0,
        "source_mapping_blocked_count": 0,
        "ready_for_limited_acquisition_design_count": 0,
        "blocked_true_source_missing_count": 0,
        "backtest_safe_count": 0,
        "point_in_time_rule_count": 0,
        "leakage_rule_count": 0,
        "missing_required_sheet_count": missing_required_sheet_count,
        "production_value_write_count": 0,
        "market_state_pack_write_count": 0,
        "provider_prompt_change_count": 0,
        "v1_sheet_write_count": 0,
        "notes": _truncate_text(message, 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_MAPPING",
            "physical_sheet_name": OUTPUT_MAPPING_SHEET,
            "sheet_role": "source_mapping_lock_table",
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
            "notes": "shadow_v0 source mapping lock only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_SEMANTICS",
            "physical_sheet_name": OUTPUT_SEMANTICS_SHEET,
            "sheet_role": "source_semantics_lock_table",
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
            "notes": "shadow_v0 field semantics lock only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_MAPPING_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "source_mapping_summary",
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
            "notes": "shadow_v0 source mapping summary only",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Market-State Source Mapping Repair / Semantics Lock v0.")
    return parser.parse_args(argv)


def build_market_state_source_mapping_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    mapping_run_id = _mapping_run_id(generated_ts)

    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    diagnostics_titles = _get_sheet_titles(sheets_service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(sheets_service, MAIN_SPREADSHEET_ID)

    missing_optional_sheets: List[str] = []
    warnings: List[str] = []

    audit_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_AUDIT_SHEET,
        missing_optional_sheets,
    )
    detail_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_AUDIT_DETAIL_SHEET,
        missing_optional_sheets,
    )
    summary_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_AUDIT_SUMMARY_SHEET,
        missing_optional_sheets,
    )
    candidate_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_CANDIDATE_SHEET,
        missing_optional_sheets,
    )
    _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_BACKLOG_SHEET,
        missing_optional_sheets,
    )
    _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_CANDIDATE_SUMMARY_SHEET,
        missing_optional_sheets,
    )
    for sheet_name in REFERENCE_SHEETS_DIAGNOSTICS:
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet_name, missing_optional_sheets)
    for sheet_name in REFERENCE_SHEETS_MAIN:
        _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, sheet_name, missing_optional_sheets)

    if not audit_rows or not detail_rows or not summary_rows:
        message = "Phase 8A-2 source audit outputs are missing, so Phase 8A-3 source mapping cannot proceed."
        mapping_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAPPING_SHEET, MAPPING_HEADERS)
        semantics_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SEMANTICS_SHEET, SEMANTICS_HEADERS)
        summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAPPING_SHEET, mapping_headers, [])
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SEMANTICS_SHEET, semantics_headers, [])
        summary_row = _blocked_summary_row(generated_ts, mapping_run_id, message, 3)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
        registry_result = _upsert_registry_rows(sheets_service)
        return {
            "mapping_run_id": mapping_run_id,
            "build_status": summary_row["build_status"],
            "final_interpretation": summary_row["final_interpretation"],
            "mapping_rows_written": 0,
            "semantics_rows_written": 0,
            "summary_rows_written": 1,
            "registry": registry_result,
            "summary": summary_row,
            "missing_sheets": ["Phase 8A-2 required output missing"],
            "warnings": [],
        }

    _require_rows(INPUT_AUDIT_SUMMARY_SHEET, summary_rows)
    audit_summary = summary_rows[0]
    if _upper(audit_summary.get("final_interpretation")) not in ALLOWED_SUMMARY_INTERPRETATIONS:
        warnings.append(
            "Phase 8A-2 final interpretation is not in the expected ready/warning set: "
            + _norm(audit_summary.get("final_interpretation"))
        )

    candidate_statuses = _candidate_status_map(candidate_rows)
    detail_by_family = _detail_map(detail_rows)
    audit_by_field = _audit_index(audit_rows)
    mapping_rows, semantics_rows = _build_rows(generated_ts, mapping_run_id, candidate_statuses, detail_by_family, audit_by_field)
    summary_row = _build_summary_row(
        generated_ts=generated_ts,
        mapping_run_id=mapping_run_id,
        mapping_rows=mapping_rows,
        semantics_rows=semantics_rows,
        missing_sheets=sorted(set(missing_optional_sheets)),
        warnings=warnings,
    )

    mapping_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAPPING_SHEET, MAPPING_HEADERS)
    semantics_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SEMANTICS_SHEET, SEMANTICS_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAPPING_SHEET, mapping_headers, mapping_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SEMANTICS_SHEET, semantics_headers, semantics_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    registry_result = _upsert_registry_rows(sheets_service)
    return {
        "mapping_run_id": mapping_run_id,
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "mapping_rows_written": len(mapping_rows),
        "semantics_rows_written": len(semantics_rows),
        "summary_rows_written": 1,
        "candidate_families_processed": summary_row["candidate_families_processed"],
        "candidate_fields_processed": summary_row["candidate_fields_processed"],
        "source_mapping_locked_count": summary_row["source_mapping_locked_count"],
        "source_mapping_warning_count": summary_row["source_mapping_warning_count"],
        "source_mapping_blocked_count": summary_row["source_mapping_blocked_count"],
        "ready_for_limited_acquisition_design_count": summary_row["ready_for_limited_acquisition_design_count"],
        "blocked_true_source_missing_count": summary_row["blocked_true_source_missing_count"],
        "missing_sheets": sorted(set(missing_optional_sheets)),
        "warnings": warnings,
        "registry": registry_result,
        "summary": summary_row,
    }


def main() -> None:
    result = build_market_state_source_mapping_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
