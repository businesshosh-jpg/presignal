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
from automation.build_session_information_requests_v0 import _iso_now, _read_config_map, _truncate_text
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    get_sheet_values,
    load_credentials,
    run_script_function,
)


INPUT_CANDIDATE_SHEET = "Market_State_Pack_Candidates"
INPUT_BACKLOG_SHEET = "Market_State_Pack_Acquisition_Backlog"
INPUT_CANDIDATE_SUMMARY_SHEET = "Market_State_Pack_Candidate_Summary"
INPUT_REQUEST_HISTORY_SHEET = "Session_Information_Requests_History"
INPUT_LIBRARY_SHEET = "Information_Requirement_Library"
INPUT_EVENT_SHEET = "Event"
INPUT_FMP_EVENT_CATALOG_SHEET = "FMP_EventCatalog"
INPUT_FRED_SERIES_SHEET = "FRED_Series_ID"
INPUT_SERIES_MAP_SHEET = "SeriesMap"
INPUT_SERIES_MAP_SUGGESTIONS_SHEET = "SeriesMap_Suggestions"

OUTPUT_AUDIT_SHEET = "Market_State_Source_Audit"
OUTPUT_SUMMARY_SHEET = "Market_State_Source_Audit_Summary"
OUTPUT_DETAIL_SHEET = "Market_State_Source_Audit_Candidate_Detail"

SCHEMA_VERSION = "presignal_v2_market_state_source_audit_0.1"
SHADOW_VERSION = "shadow_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 8A-2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_STATE_SOURCE_AUDIT"
REGISTRY_OWNER_MODULE = "market_state"

IN_SCOPE_FAMILIES = [
    "treasury_yields",
    "dxy",
    "usdjpy_trend",
    "fed_expectations",
    "upcoming_larger_events",
]

FAMILY_FIELDS: Dict[str, List[str]] = {
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
    "usdjpy_trend": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
    ],
    "fed_expectations": [
        "NEXT_FOMC_CUT_PROBABILITY",
        "NEXT_FOMC_HIKE_PROBABILITY",
        "NEXT_FOMC_NO_CHANGE_PROBABILITY",
        "NEXT_FOMC_MOST_LIKELY_TARGET_RANGE",
        "FED_EXPECTATION_SHIFT_1D",
        "FED_EXPECTATION_SHIFT_1W",
        "FED_EXPECTATION_PROXY_FROM_US2Y",
    ],
    "upcoming_larger_events": [
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
        "NEXT_CPI_OR_FOMC_WITHIN_72H",
        "NEXT_NFP_WITHIN_7D",
        "EVENT_CLUSTER_DENSITY_NEXT_24H",
        "UPCOMING_EVENT_RISK_LABEL",
    ],
}

FAMILY_CONFIG: Dict[str, Dict[str, str]] = {
    "treasury_yields": {
        "promotion_review_status": "APPROVED_FOR_SOURCE_AUDIT_ONLY",
        "phase8a1_decision": "READY_FOR_DETERMINISTIC_SOURCE_AUDIT",
        "source_feasibility_rank": "3_high_confidence",
        "best_source_candidate": "FRED:DGS2|DGS10",
        "fallback_source_candidate": "Federal Reserve H.15",
        "recommended_acquisition_method": "deterministic_fetch",
    },
    "dxy": {
        "promotion_review_status": "APPROVED_FOR_SOURCE_AUDIT_ONLY",
        "phase8a1_decision": "READY_FOR_DETERMINISTIC_SOURCE_AUDIT",
        "source_feasibility_rank": "4_medium_high_confidence",
        "best_source_candidate": "FMP:DX-Y.NYB",
        "fallback_source_candidate": "FRED:DTWEXBGS",
        "recommended_acquisition_method": "deterministic_fetch",
    },
    "usdjpy_trend": {
        "promotion_review_status": "APPROVED_FOR_SOURCE_AUDIT_ONLY",
        "phase8a1_decision": "READY_FOR_DETERMINISTIC_SOURCE_AUDIT",
        "source_feasibility_rank": "2_high_confidence",
        "best_source_candidate": "EODHD:USDJPY.FOREX intraday",
        "fallback_source_candidate": "FMP:USDJPY daily",
        "recommended_acquisition_method": "computed_feature",
    },
    "fed_expectations": {
        "promotion_review_status": "APPROVED_FOR_SOURCE_AUDIT_ONLY",
        "phase8a1_decision": "READY_FOR_SOURCE_AUDIT_BUT_NOT_DETERMINISTIC_ACQUISITION",
        "source_feasibility_rank": "5_medium_confidence",
        "best_source_candidate": "CME FedWatch API",
        "fallback_source_candidate": "FRED:DGS2 proxy / FEDFUNDS / DFF",
        "recommended_acquisition_method": "source_audit_only",
    },
    "upcoming_larger_events": {
        "promotion_review_status": "APPROVED_FOR_SOURCE_AUDIT_ONLY",
        "phase8a1_decision": "READY_FOR_DETERMINISTIC_SOURCE_AUDIT",
        "source_feasibility_rank": "1_highest_confidence",
        "best_source_candidate": "Event sheet scheduled-calendar derivation",
        "fallback_source_candidate": "FMP_EventCatalog / FMP calendar API",
        "recommended_acquisition_method": "calendar_derived_feature",
    },
}

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "audit_run_id",
    "candidate_family",
    "candidate_field",
    "candidate_status_in",
    "source_candidate",
    "provider",
    "symbol_or_series_id",
    "acquisition_method",
    "historical_available",
    "intraday_available",
    "coverage_start",
    "coverage_end",
    "frequency",
    "source_timestamp_available",
    "point_in_time_safe",
    "backtest_safe",
    "expected_latency",
    "cost_risk",
    "license_risk",
    "implementation_difficulty",
    "fallback_source",
    "recommended_next_status",
    "audit_status",
    "notes",
]

DETAIL_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "audit_run_id",
    "candidate_family",
    "promotion_review_status",
    "phase8a1_decision",
    "source_feasibility_rank",
    "best_source_candidate",
    "fallback_source_candidate",
    "recommended_acquisition_method",
    "source_found_count",
    "source_warning_count",
    "source_fail_count",
    "point_in_time_safe_count",
    "backtest_safe_count",
    "phase8a2_decision",
    "reason",
    "blocker",
    "notes",
]

SUMMARY_HEADERS = [
    "audit_run_id",
    "generated_ts",
    "build_status",
    "final_interpretation",
    "candidate_families_audited",
    "candidate_fields_audited",
    "source_found_count",
    "source_warning_count",
    "source_fail_count",
    "backtest_safe_count",
    "point_in_time_safe_count",
    "ready_for_limited_acquisition_design_count",
    "hold_count",
    "missing_required_sheet_count",
    "test_read_count",
    "production_value_write_count",
    "market_state_pack_write_count",
    "provider_prompt_change_count",
    "v1_sheet_write_count",
    "notes",
]

BOOL_UNKNOWN = {"true": "TRUE", "false": "FALSE", "unknown": "UNKNOWN"}


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _audit_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"market_state_source_audit_v0_{stamp}"


def _read_local_text(relative_path: str) -> str:
    path = ROOT / relative_path
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


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


def _read_sheet_sample(
    service,
    spreadsheet_id: str,
    sheet_titles: Set[str],
    sheet_name: str,
    missing_sheets: List[str],
    row_limit: int = 5,
) -> List[List[Any]]:
    if sheet_name not in sheet_titles:
        missing_sheets.append(sheet_name)
        return []
    try:
        return get_sheet_values(service, spreadsheet_id, f"'{sheet_name}'!1:{row_limit}")
    except Exception:
        missing_sheets.append(sheet_name)
        return []


def _headers_from_sample(values: Sequence[Sequence[Any]]) -> List[str]:
    if not values:
        return []
    return [_norm(cell) for cell in values[0]]


def _row_map_by_family(candidate_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    family_map: Dict[str, Dict[str, Any]] = {}
    for row in candidate_rows:
        category = _norm(row.get("information_category")).lower()
        if category not in IN_SCOPE_FAMILIES:
            continue
        existing = family_map.get(category)
        if not existing:
            family_map[category] = row
            continue
        existing_request = _safe_int(existing.get("request_count"))
        row_request = _safe_int(row.get("request_count"))
        if row_request > existing_request:
            family_map[category] = row
    return family_map


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _has_headers(headers: Sequence[str], required: Sequence[str]) -> bool:
    current = {_upper(header) for header in headers if _norm(header)}
    return all(_upper(header) in current for header in required)


def _availability_index(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        provider = _upper(row.get("provider"))
        symbol = _upper(row.get("symbol")) or _upper(row.get("field"))
        if provider and symbol:
            out[(provider, symbol)] = row
    return out


def _availability_lookup(index: Dict[Tuple[str, str], Dict[str, Any]], provider: str, symbol: str) -> Dict[str, Any]:
    return index.get((_upper(provider), _upper(symbol)), {})


def _availability_bool(row: Dict[str, Any]) -> str:
    if not row:
        return "UNKNOWN"
    if _upper(row.get("success_fail")) == "SUCCESS":
        return "TRUE"
    if _norm(row.get("note")):
        return "FALSE"
    return "UNKNOWN"


def _coverage_start(row: Dict[str, Any]) -> str:
    return _norm(row.get("earliest_date"))


def _coverage_end(row: Dict[str, Any]) -> str:
    return _norm(row.get("latest_date"))


def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = _norm(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _join_pipe(values: Iterable[str]) -> str:
    return "|".join(_dedupe_keep_order(values))


def _find_library_stats(library_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"request_count": 0, "provider_count": 0, "session_count": 0})
    for row in library_rows:
        category = _norm(row.get("information_category")).lower()
        if category not in IN_SCOPE_FAMILIES:
            continue
        stats[category] = {
            "request_count": _safe_int(row.get("request_count")),
            "provider_count": _safe_int(row.get("provider_count")),
            "session_count": _safe_int(row.get("session_count")),
        }
    return stats


def _scan_repo_evidence() -> Dict[str, Any]:
    files = {
        "rulebook": _read_local_text("docs/RuleBook_v1.4.md"),
        "blueprint": _read_local_text("docs/Blueprint_v1.4.md"),
        "market_context_v2b": _read_local_text("apps_script/market_context_v2b.js"),
        "data_availability_audit": _read_local_text("apps_script/data_availability_audit.js"),
        "market_context_provider_repair": _read_local_text("apps_script/market_context_provider_repair.js"),
        "fx_candle_provider": _read_local_text("apps_script/fx_candle_provider.js"),
        "evaluation_report": _read_local_text("apps_script/evaluation_report.js"),
        "fmp_calendar": _read_local_text("apps_script/fmp_calendar.js"),
    }
    return {
        "fred_dgs2": "DGS2" in files["rulebook"] or "DGS2" in files["market_context_v2b"],
        "fred_dgs10": "DGS10" in files["rulebook"] or "DGS10" in files["market_context_v2b"],
        "fred_dff": "DFF" in files["rulebook"] or "DFF" in files["market_context_v2b"],
        "fred_fedfunds": "FEDFUNDS" in files["rulebook"] or "FEDFUNDS" in files["market_context_v2b"],
        "fmp_dxy": "DX-Y.NYB" in files["rulebook"] or "DX-Y.NYB" in files["evaluation_report"],
        "usdjpy_eodhd": "USDJPY.FOREX" in files["rulebook"] or "USDJPY.FOREX" in files["fx_candle_provider"],
        "usdjpy_intraday": "USDJPY.FOREX intraday" in files["evaluation_report"] or "apiGetUsdJpyWindowMove" in files["evaluation_report"],
        "event_catalog": "FMP_EventCatalog" in files["fmp_calendar"],
        "calendar_api": "Economic Calendar API" in files["fmp_calendar"] or "FMP_EventCatalog" in files["fmp_calendar"],
        "actual_dxy_confirmed": "DX-Y.NYB" in files["market_context_v2b"] or "DX-Y.NYB" in files["market_context_provider_repair"],
        "fedwatch_confirmed": "FedWatch" in files["market_context_v2b"] or "FedWatch" in files["evaluation_report"],
    }


def _make_row(
    generated_ts: str,
    audit_run_id: str,
    candidate_family: str,
    candidate_field: str,
    candidate_status_in: str,
    source_candidate: str,
    provider: str,
    symbol_or_series_id: str,
    acquisition_method: str,
    historical_available: str,
    intraday_available: str,
    coverage_start: str,
    coverage_end: str,
    frequency: str,
    source_timestamp_available: str,
    point_in_time_safe: str,
    backtest_safe: str,
    expected_latency: str,
    cost_risk: str,
    license_risk: str,
    implementation_difficulty: str,
    fallback_source: str,
    recommended_next_status: str,
    audit_status: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "audit_run_id": audit_run_id,
        "candidate_family": candidate_family,
        "candidate_field": candidate_field,
        "candidate_status_in": candidate_status_in,
        "source_candidate": source_candidate,
        "provider": provider,
        "symbol_or_series_id": symbol_or_series_id,
        "acquisition_method": acquisition_method,
        "historical_available": historical_available,
        "intraday_available": intraday_available,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "frequency": frequency,
        "source_timestamp_available": source_timestamp_available,
        "point_in_time_safe": point_in_time_safe,
        "backtest_safe": backtest_safe,
        "expected_latency": expected_latency,
        "cost_risk": cost_risk,
        "license_risk": license_risk,
        "implementation_difficulty": implementation_difficulty,
        "fallback_source": fallback_source,
        "recommended_next_status": recommended_next_status,
        "audit_status": audit_status,
        "notes": _truncate_text(notes, 400),
    }


def _candidate_status_in(family: str, candidate_map: Dict[str, Dict[str, Any]]) -> str:
    row = candidate_map.get(family, {})
    return _norm(row.get("candidate_status")) or "CANDIDATE_FEATURE"


def _family_request_stats_text(family: str, candidate_map: Dict[str, Dict[str, Any]], library_stats: Dict[str, Dict[str, int]]) -> str:
    candidate_row = candidate_map.get(family, {})
    library_row = library_stats.get(family, {})
    parts = []
    if candidate_row:
        parts.append(
            "candidate_sheet request_count="
            + str(_safe_int(candidate_row.get("request_count")))
            + " provider_count="
            + str(_safe_int(candidate_row.get("provider_count")))
            + " session_count="
            + str(_safe_int(candidate_row.get("session_count")))
        )
    if library_row:
        parts.append(
            "library request_count="
            + str(library_row.get("request_count", 0))
            + " provider_count="
            + str(library_row.get("provider_count", 0))
            + " session_count="
            + str(library_row.get("session_count", 0))
        )
    return "; ".join(parts) if parts else "no prior structured candidate/library counts found"


def _build_treasury_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    availability: Dict[Tuple[str, str], Dict[str, Any]],
    repo_evidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidate_status_in = _candidate_status_in("treasury_yields", candidate_map)
    request_stats = _family_request_stats_text("treasury_yields", candidate_map, library_stats)
    dgs2_row = _availability_lookup(availability, "FRED", "DGS2")
    dgs10_row = _availability_lookup(availability, "FRED", "DGS10")
    for field in FAMILY_FIELDS["treasury_yields"]:
        if "US2Y" in field and "CURVE" not in field:
            symbol = "DGS2"
            source_row = dgs2_row
        elif "US10Y" in field and "CURVE" not in field:
            symbol = "DGS10"
            source_row = dgs10_row
        else:
            symbol = "DGS10|DGS2"
            source_row = dgs10_row if dgs10_row and dgs2_row else {}
        point_in_time_safe = "TRUE" if "CHANGE_FROM_PRIOR_CLOSE" in field or "CURVE" in field else "UNKNOWN"
        backtest_safe = "TRUE"
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "treasury_yields",
                field,
                candidate_status_in,
                "FRED_DAILY_SERIES",
                "FRED",
                symbol,
                "deterministic_fetch",
                _availability_bool(source_row) if source_row else ("TRUE" if symbol == "DGS10|DGS2" and dgs2_row and dgs10_row else "UNKNOWN"),
                "FALSE",
                _coverage_start(source_row) if source_row else (_coverage_start(dgs2_row) if symbol == "DGS10|DGS2" else ""),
                _coverage_end(source_row) if source_row else (_coverage_end(dgs10_row) if symbol == "DGS10|DGS2" else ""),
                "DAILY",
                "UNKNOWN",
                point_in_time_safe,
                backtest_safe,
                "same_day_or_delayed_daily",
                "LOW",
                "LOW",
                "LOW",
                "Federal Reserve H.15",
                "SOURCE_FOUND" if _availability_bool(source_row) == "TRUE" or (symbol == "DGS10|DGS2" and dgs2_row and dgs10_row) else "SOURCE_AUDIT_REQUIRED",
                "PASS_WITH_WARNINGS",
                f"Validated FRED series present in repo={repo_evidence.get('fred_dgs2') and repo_evidence.get('fred_dgs10')}. Daily series supports deterministic history, but same-day publication timing must be mapped before live pack use. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "treasury_yields",
                field,
                candidate_status_in,
                "FEDERAL_RESERVE_H15_REFERENCE",
                "FederalReserve",
                "H.15",
                "deterministic_fetch",
                "UNKNOWN",
                "FALSE",
                "",
                "",
                "DAILY",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "publication_schedule_dependent",
                "LOW",
                "LOW",
                "MEDIUM",
                "FRED:DGS2|DGS10",
                "SOURCE_AUDIT_REQUIRED",
                "NEEDS_REVIEW",
                f"Fallback/reference path only. Repo references H.15 as a conservative backup, but no direct source mapping was confirmed in automation code. {request_stats}",
            )
        )
    return rows


def _build_dxy_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    availability: Dict[Tuple[str, str], Dict[str, Any]],
    repo_evidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidate_status_in = _candidate_status_in("dxy", candidate_map)
    request_stats = _family_request_stats_text("dxy", candidate_map, library_stats)
    fmp_row = _availability_lookup(availability, "FMP", "DX-Y.NYB")
    for field in FAMILY_FIELDS["dxy"]:
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "dxy",
                field,
                candidate_status_in,
                "ACTUAL_DXY_SYMBOL",
                "FMP",
                "DX-Y.NYB",
                "deterministic_fetch",
                _availability_bool(fmp_row) if fmp_row else ("TRUE" if repo_evidence.get("actual_dxy_confirmed") else "UNKNOWN"),
                "FALSE",
                _coverage_start(fmp_row),
                _coverage_end(fmp_row),
                "DAILY",
                "UNKNOWN",
                "TRUE" if field in {"DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL"} else "UNKNOWN",
                "TRUE",
                "same_day_or_delayed_daily",
                "LOW",
                "LOW",
                "LOW",
                "FRED:DTWEXBGS",
                "SOURCE_FOUND" if repo_evidence.get("actual_dxy_confirmed") else "SOURCE_AUDIT_REQUIRED",
                "PASS_WITH_WARNINGS",
                f"Existing repo mappings confirm DX-Y.NYB as the current actual-DXY path. Keep it separate from broad USD proxies and confirm daily timestamp semantics before pack design. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "dxy",
                field,
                candidate_status_in,
                "BROAD_USD_INDEX_PROXY",
                "FRED",
                "DTWEXBGS",
                "deterministic_fetch",
                "UNKNOWN",
                "FALSE",
                "",
                "",
                "DAILY",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "same_day_or_delayed_daily",
                "LOW",
                "LOW",
                "MEDIUM",
                "FMP:DX-Y.NYB",
                "SOURCE_AUDIT_REQUIRED",
                "NEEDS_REVIEW",
                f"Proxy candidate only. The repo does not currently confirm DTWEXBGS usage, so this remains an audit path and must not be labeled as actual DXY. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "dxy",
                field,
                candidate_status_in,
                "INTERNAL_USD_BASKET_PROXY",
                "INTERNAL",
                "custom_usd_basket",
                "deterministic_fetch",
                "FALSE",
                "UNKNOWN",
                "",
                "",
                "CUSTOM",
                "UNKNOWN",
                "UNKNOWN",
                "FALSE",
                "implementation_required",
                "LOW",
                "LOW",
                "HIGH",
                "FMP:DX-Y.NYB or FRED:DTWEXBGS",
                "HOLD_SOURCE_UNCLEAR",
                "NEEDS_REVIEW",
                f"Audit-only placeholder for a future internal basket. No current source mapping or reproducible implementation exists in the environment. {request_stats}",
            )
        )
    return rows


def _build_usdjpy_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    availability: Dict[Tuple[str, str], Dict[str, Any]],
    repo_evidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidate_status_in = _candidate_status_in("usdjpy_trend", candidate_map)
    request_stats = _family_request_stats_text("usdjpy_trend", candidate_map, library_stats)
    eodhd_row = _availability_lookup(availability, "EODHD", "USDJPY.FOREX")
    fmp_row = _availability_lookup(availability, "FMP", "USDJPY")
    for field in FAMILY_FIELDS["usdjpy_trend"]:
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "usdjpy_trend",
                field,
                candidate_status_in,
                "USDJPY_INTRADAY_PRIMARY",
                "EODHD",
                "USDJPY.FOREX",
                "computed_feature",
                _availability_bool(eodhd_row) if eodhd_row else ("TRUE" if repo_evidence.get("usdjpy_eodhd") else "UNKNOWN"),
                "TRUE" if repo_evidence.get("usdjpy_intraday") else "UNKNOWN",
                _coverage_start(eodhd_row),
                _coverage_end(eodhd_row),
                "INTRADAY",
                "TRUE" if repo_evidence.get("usdjpy_intraday") else "UNKNOWN",
                "TRUE",
                "TRUE",
                "intraday_market_data",
                "LOW",
                "LOW",
                "LOW",
                "FMP:USDJPY daily",
                "SOURCE_FOUND",
                "PASS",
                f"Existing evaluation and market-context code already resolve USDJPY from EODHD/FMP, with intraday USDJPY.FOREX support visible in evaluation helpers. Pre-session windows can be computed without leakage if forecast_timestamp is enforced. {request_stats}",
            )
        )
        fallback_recommended = (
            "SOURCE_FOUND"
            if field in {"USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"} and _availability_bool(fmp_row) == "TRUE"
            else "HOLD_SOURCE_UNCLEAR"
        )
        fallback_point_in_time = "TRUE" if field in {"USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"} else "FALSE"
        fallback_backtest_safe = "TRUE" if field in {"USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"} else "FALSE"
        fallback_status = "PASS_WITH_WARNINGS" if fallback_recommended == "SOURCE_FOUND" else "NEEDS_REVIEW"
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "usdjpy_trend",
                field,
                candidate_status_in,
                "USDJPY_DAILY_FALLBACK",
                "FMP",
                "USDJPY",
                "computed_feature",
                _availability_bool(fmp_row) if fmp_row else "UNKNOWN",
                "FALSE",
                _coverage_start(fmp_row),
                _coverage_end(fmp_row),
                "DAILY",
                "TRUE" if _availability_bool(fmp_row) == "TRUE" else "UNKNOWN",
                fallback_point_in_time,
                fallback_backtest_safe,
                "same_day_or_delayed_daily",
                "LOW",
                "LOW",
                "MEDIUM",
                "EODHD:USDJPY.FOREX intraday",
                fallback_recommended,
                fallback_status,
                f"Daily fallback can support 24H-style features, but not 1H/4H or intraday realized-vol features. Use only as a limited backup path, not as a full substitute for intraday replay-safe USDJPY windows. {request_stats}",
            )
        )
    return rows


def _build_fed_expectations_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    availability: Dict[Tuple[str, str], Dict[str, Any]],
    repo_evidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidate_status_in = _candidate_status_in("fed_expectations", candidate_map)
    request_stats = _family_request_stats_text("fed_expectations", candidate_map, library_stats)
    dgs2_row = _availability_lookup(availability, "FRED", "DGS2")
    dff_row = _availability_lookup(availability, "FRED", "DFF")
    fedfunds_row = _availability_lookup(availability, "FRED", "FEDFUNDS")
    for field in FAMILY_FIELDS["fed_expectations"]:
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "fed_expectations",
                field,
                candidate_status_in,
                "CME_FEDWATCH_PRIMARY",
                "CME",
                "FedWatch API",
                "source_audit_only",
                "UNKNOWN",
                "UNKNOWN",
                "",
                "",
                "SNAPSHOT",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "unknown",
                "MEDIUM",
                "MEDIUM",
                "MEDIUM",
                "30-Day Fed Funds Futures / FRED proxies",
                "SOURCE_AUDIT_REQUIRED",
                "NEEDS_REVIEW",
                f"No existing repo mapping confirms historical point-in-time FedWatch snapshots. This remains the highest-value but least-proven true expectations path. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "fed_expectations",
                field,
                candidate_status_in,
                "FED_FUNDS_FUTURES_SECONDARY",
                "MARKET_DATA",
                "30D_FED_FUNDS_FUTURES",
                "source_audit_only",
                "UNKNOWN",
                "UNKNOWN",
                "",
                "",
                "CONTRACT_SERIES",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "market_data_vendor_dependent",
                "MEDIUM",
                "MEDIUM",
                "HIGH",
                "FRED:DGS2/DFF/FEDFUNDS proxy set",
                "SOURCE_AUDIT_REQUIRED",
                "NEEDS_REVIEW",
                f"Futures-based reconstruction is plausible but not currently mapped in the repo, and historical point-in-time replay safety is unverified. {request_stats}",
            )
        )
        proxy_symbol = "DGS2|DFF|FEDFUNDS"
        proxy_hist = "TRUE" if dgs2_row and (dff_row or fedfunds_row) else "UNKNOWN"
        proxy_recommend = "SOURCE_FOUND" if field == "FED_EXPECTATION_PROXY_FROM_US2Y" and proxy_hist == "TRUE" else "HOLD_SOURCE_UNCLEAR"
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "fed_expectations",
                field,
                candidate_status_in,
                "YIELD_AND_POLICY_PROXY",
                "FRED",
                proxy_symbol,
                "computed_feature",
                proxy_hist,
                "FALSE",
                _coverage_start(dgs2_row) or _coverage_start(dff_row) or _coverage_start(fedfunds_row),
                _coverage_end(dgs2_row) or _coverage_end(dff_row) or _coverage_end(fedfunds_row),
                "DAILY",
                "UNKNOWN",
                "TRUE" if proxy_hist == "TRUE" else "UNKNOWN",
                "TRUE" if proxy_hist == "TRUE" else "UNKNOWN",
                "same_day_or_delayed_daily",
                "LOW",
                "LOW",
                "MEDIUM",
                "CME FedWatch / futures-derived path",
                proxy_recommend,
                "PASS_WITH_WARNINGS" if proxy_hist == "TRUE" else "NEEDS_REVIEW",
                f"Proxy-only path. FRED DGS2/DFF/FEDFUNDS can support a backtest-safe Fed-expectation proxy, but must never be labeled as true FOMC probability data for the probability or target-range fields. {request_stats}",
            )
        )
    return rows


def _build_upcoming_event_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    event_headers: Sequence[str],
    event_catalog_headers: Sequence[str],
    repo_evidence: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    candidate_status_in = _candidate_status_in("upcoming_larger_events", candidate_map)
    request_stats = _family_request_stats_text("upcoming_larger_events", candidate_map, library_stats)
    event_has_required = _has_headers(event_headers, ["event_id", "country", "release_ts", "indicator_name", "importance"])
    catalog_has_required = _has_headers(event_catalog_headers, ["country", "indicator_name_norm", "indicator_name_sample"])
    for field in FAMILY_FIELDS["upcoming_larger_events"]:
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "upcoming_larger_events",
                field,
                candidate_status_in,
                "EVENT_SHEET_DERIVATION",
                "PreSignal",
                "Event",
                "calendar_derived_feature",
                "TRUE" if event_has_required else "FALSE",
                "FALSE",
                "",
                "",
                "SCHEDULED_EVENT_CALENDAR",
                "TRUE" if event_has_required else "FALSE",
                "TRUE" if event_has_required else "UNKNOWN",
                "TRUE" if event_has_required else "UNKNOWN",
                "immediate_from_known_calendar_rows",
                "LOW",
                "LOW",
                "LOW",
                "FMP_EventCatalog / FMP calendar API",
                "SOURCE_FOUND" if event_has_required else "SOURCE_AUDIT_REQUIRED",
                "PASS" if event_has_required else "NEEDS_REVIEW",
                f"Derivation is feasible if it uses only scheduled-event metadata such as release_ts, importance, and indicator families already present in Event. No actual values are required. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "upcoming_larger_events",
                field,
                candidate_status_in,
                "FMP_EVENT_CATALOG_DERIVATION",
                "FMP",
                "FMP_EventCatalog",
                "calendar_derived_feature",
                "TRUE" if catalog_has_required else "UNKNOWN",
                "FALSE",
                "",
                "",
                "SCHEDULED_EVENT_CATALOG",
                "TRUE" if catalog_has_required else "UNKNOWN",
                "TRUE" if catalog_has_required else "UNKNOWN",
                "TRUE" if catalog_has_required else "UNKNOWN",
                "same_day_catalog_refresh",
                "LOW",
                "LOW",
                "LOW",
                "Event sheet",
                "SOURCE_FOUND" if catalog_has_required else "SOURCE_AUDIT_REQUIRED",
                "PASS_WITH_WARNINGS" if catalog_has_required else "NEEDS_REVIEW",
                f"Catalog fallback is plausible and already exists in repo tooling, but final derivation should prefer the canonical Event sheet when session inputs are available. {request_stats}",
            )
        )
        rows.append(
            _make_row(
                generated_ts,
                audit_run_id,
                "upcoming_larger_events",
                field,
                candidate_status_in,
                "FMP_CALENDAR_API_FALLBACK",
                "FMP",
                "economic_calendar_api",
                "calendar_derived_feature",
                "UNKNOWN" if repo_evidence.get("calendar_api") else "FALSE",
                "FALSE",
                "",
                "",
                "API_CALENDAR",
                "UNKNOWN",
                "UNKNOWN",
                "UNKNOWN",
                "api_call_dependent",
                "LOW",
                "MEDIUM",
                "MEDIUM",
                "Event / FMP_EventCatalog",
                "SOURCE_AUDIT_REQUIRED",
                "NEEDS_REVIEW",
                f"API fallback exists conceptually in repo calendar tooling, but this Phase 8A-2 audit does not approve value acquisition or timing semantics from external calendar refreshes. {request_stats}",
            )
        )
    return rows


def _build_audit_rows(
    generated_ts: str,
    audit_run_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
    availability_index: Dict[Tuple[str, str], Dict[str, Any]],
    repo_evidence: Dict[str, Any],
    event_headers: Sequence[str],
    event_catalog_headers: Sequence[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.extend(_build_treasury_rows(generated_ts, audit_run_id, candidate_map, library_stats, availability_index, repo_evidence))
    rows.extend(_build_dxy_rows(generated_ts, audit_run_id, candidate_map, library_stats, availability_index, repo_evidence))
    rows.extend(_build_usdjpy_rows(generated_ts, audit_run_id, candidate_map, library_stats, availability_index, repo_evidence))
    rows.extend(_build_fed_expectations_rows(generated_ts, audit_run_id, candidate_map, library_stats, availability_index, repo_evidence))
    rows.extend(
        _build_upcoming_event_rows(
            generated_ts,
            audit_run_id,
            candidate_map,
            library_stats,
            event_headers,
            event_catalog_headers,
            repo_evidence,
        )
    )
    rows.sort(
        key=lambda row: (
            _norm(row.get("candidate_family")),
            _norm(row.get("candidate_field")),
            _norm(row.get("provider")),
            _norm(row.get("symbol_or_series_id")),
        )
    )
    return rows


def _detail_decision(family: str, rows: Sequence[Dict[str, Any]]) -> Tuple[str, str, str]:
    source_found_count = sum(1 for row in rows if _upper(row.get("recommended_next_status")) == "SOURCE_FOUND")
    warning_count = sum(1 for row in rows if _upper(row.get("audit_status")) in {"PASS_WITH_WARNINGS", "NEEDS_REVIEW"})
    fail_count = sum(1 for row in rows if _upper(row.get("audit_status")) == "FAIL")
    pit_count = sum(1 for row in rows if _upper(row.get("point_in_time_safe")) == "TRUE")
    backtest_count = sum(1 for row in rows if _upper(row.get("backtest_safe")) == "TRUE")
    if family == "fed_expectations":
        return (
            "HOLD_SOURCE_UNCLEAR",
            f"True Fed expectations sources remain unconfirmed even though proxy rows exist (source_found_rows={source_found_count}).",
            "Historical point-in-time FedWatch/futures source mapping is not yet confirmed.",
        )
    if fail_count >= len(rows):
        return ("HOLD_SOURCE_UNCLEAR", "No feasible source path was confirmed.", "All audited source candidates failed.")
    if pit_count == 0 or backtest_count == 0:
        return (
            "HOLD_BACKTEST_UNSAFE",
            f"Family has source evidence but no point-in-time/backtest-safe candidate row yet (pit={pit_count}, backtest={backtest_count}).",
            "Point-in-time or backtest-safe derivation remains unresolved.",
        )
    if warning_count > 0:
        return (
            "READY_FOR_SOURCE_MAPPING_FIX",
            f"Best source path is visible, but timestamp/fallback semantics still need explicit mapping repair (warnings={warning_count}).",
            "Finalize source/timestamp semantics before limited acquisition design.",
        )
    return (
        "READY_FOR_LIMITED_ACQUISITION_DESIGN",
        f"At least one source path is confirmed and point-in-time safe/backtest-safe rows exist (source_found={source_found_count}).",
        "",
    )


def _build_detail_rows(
    generated_ts: str,
    audit_run_id: str,
    audit_rows: Sequence[Dict[str, Any]],
    candidate_map: Dict[str, Dict[str, Any]],
    library_stats: Dict[str, Dict[str, int]],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        grouped[_norm(row.get("candidate_family")).lower()].append(row)
    detail_rows: List[Dict[str, Any]] = []
    for family in IN_SCOPE_FAMILIES:
        family_rows = grouped.get(family, [])
        cfg = FAMILY_CONFIG[family]
        if not family_rows:
            continue
        decision, reason, blocker = _detail_decision(family, family_rows)
        source_found_count = sum(1 for row in family_rows if _upper(row.get("recommended_next_status")) == "SOURCE_FOUND")
        source_warning_count = sum(1 for row in family_rows if _upper(row.get("audit_status")) in {"PASS_WITH_WARNINGS", "NEEDS_REVIEW"})
        source_fail_count = sum(1 for row in family_rows if _upper(row.get("audit_status")) == "FAIL")
        point_in_time_safe_count = sum(1 for row in family_rows if _upper(row.get("point_in_time_safe")) == "TRUE")
        backtest_safe_count = sum(1 for row in family_rows if _upper(row.get("backtest_safe")) == "TRUE")
        best_sources = [
            f"{_norm(row.get('provider'))}[{_norm(row.get('symbol_or_series_id'))}]"
            for row in family_rows
            if _upper(row.get("recommended_next_status")) == "SOURCE_FOUND"
        ]
        best_source_value = ", ".join(_dedupe_keep_order(best_sources)) or cfg["best_source_candidate"]
        notes_bits = [
            _family_request_stats_text(family, candidate_map, library_stats),
            "audited_fields=" + str(len(FAMILY_FIELDS[family])),
            "source_found_rows=" + str(source_found_count),
            "warning_rows=" + str(source_warning_count),
        ]
        detail_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "audit_run_id": audit_run_id,
                "candidate_family": family,
                "promotion_review_status": cfg["promotion_review_status"],
                "phase8a1_decision": cfg["phase8a1_decision"],
                "source_feasibility_rank": cfg["source_feasibility_rank"],
                "best_source_candidate": best_source_value,
                "fallback_source_candidate": cfg["fallback_source_candidate"],
                "recommended_acquisition_method": cfg["recommended_acquisition_method"],
                "source_found_count": source_found_count,
                "source_warning_count": source_warning_count,
                "source_fail_count": source_fail_count,
                "point_in_time_safe_count": point_in_time_safe_count,
                "backtest_safe_count": backtest_safe_count,
                "phase8a2_decision": decision,
                "reason": _truncate_text(reason, 280),
                "blocker": _truncate_text(blocker, 280),
                "notes": _truncate_text("; ".join(notes_bits), 400),
            }
        )
    return detail_rows


def _build_summary_row(
    audit_run_id: str,
    generated_ts: str,
    audit_rows: Sequence[Dict[str, Any]],
    detail_rows: Sequence[Dict[str, Any]],
    missing_sheets: Sequence[str],
    test_read_count: int,
    warnings: Sequence[str],
) -> Dict[str, Any]:
    production_value_write_count = 0
    market_state_pack_write_count = 0
    provider_prompt_change_count = 0
    v1_sheet_write_count = 0
    source_found_count = sum(1 for row in audit_rows if _upper(row.get("recommended_next_status")) == "SOURCE_FOUND")
    source_warning_count = sum(1 for row in audit_rows if _upper(row.get("audit_status")) in {"PASS_WITH_WARNINGS", "NEEDS_REVIEW"})
    source_fail_count = sum(1 for row in audit_rows if _upper(row.get("audit_status")) == "FAIL")
    backtest_safe_count = sum(1 for row in audit_rows if _upper(row.get("backtest_safe")) == "TRUE")
    point_in_time_safe_count = sum(1 for row in audit_rows if _upper(row.get("point_in_time_safe")) == "TRUE")
    ready_for_design_count = sum(1 for row in detail_rows if _upper(row.get("phase8a2_decision")) == "READY_FOR_LIMITED_ACQUISITION_DESIGN")
    hold_count = sum(1 for row in detail_rows if _upper(row.get("phase8a2_decision")).startswith("HOLD"))
    if any([production_value_write_count, market_state_pack_write_count, provider_prompt_change_count, v1_sheet_write_count]):
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_SOURCE_AUDIT_BLOCKED"
    elif not audit_rows or not detail_rows:
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_SOURCE_AUDIT_BLOCKED"
    elif source_fail_count > 0 or hold_count > 0 or missing_sheets:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_SOURCE_AUDIT_READY_WITH_WARNINGS"
    elif source_warning_count > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_SOURCE_AUDIT_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        final_interpretation = "MARKET_STATE_SOURCE_AUDIT_READY"
    notes_bits = [
        "warnings=" + json.dumps(list(warnings), ensure_ascii=True),
        "missing_sheets=" + json.dumps(list(missing_sheets), ensure_ascii=True),
        "detail_decisions=" + json.dumps(Counter(_norm(row.get("phase8a2_decision")) for row in detail_rows), ensure_ascii=True),
    ]
    return {
        "audit_run_id": audit_run_id,
        "generated_ts": generated_ts,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "candidate_families_audited": len(detail_rows),
        "candidate_fields_audited": sum(len(fields) for fields in FAMILY_FIELDS.values()),
        "source_found_count": source_found_count,
        "source_warning_count": source_warning_count,
        "source_fail_count": source_fail_count,
        "backtest_safe_count": backtest_safe_count,
        "point_in_time_safe_count": point_in_time_safe_count,
        "ready_for_limited_acquisition_design_count": ready_for_design_count,
        "hold_count": hold_count,
        "missing_required_sheet_count": len(missing_sheets),
        "test_read_count": test_read_count,
        "production_value_write_count": production_value_write_count,
        "market_state_pack_write_count": market_state_pack_write_count,
        "provider_prompt_change_count": provider_prompt_change_count,
        "v1_sheet_write_count": v1_sheet_write_count,
        "notes": _truncate_text("; ".join(notes_bits), 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates: List[Dict[str, Any]] = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "sheet_role": "source_audit_matrix",
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
            "notes": "shadow_v0 market-state source audit matrix only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_AUDIT_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "source_audit_summary",
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
            "notes": "shadow_v0 market-state source audit summary only",
        },
        {
            "logical_sheet_id": "MARKET_STATE_SOURCE_AUDIT_CANDIDATE_DETAIL",
            "physical_sheet_name": OUTPUT_DETAIL_SHEET,
            "sheet_role": "source_audit_candidate_detail",
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
            "notes": "shadow_v0 market-state source audit per-family detail only",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Market-State Source Audit v0.")
    parser.add_argument(
        "--skip-test-read",
        action="store_true",
        help="Skip the Apps Script minimal source-availability test read.",
    )
    return parser.parse_args(argv)


def build_market_state_source_audit_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    audit_run_id = _audit_run_id(generated_ts)
    warnings: List[str] = []
    missing_sheets: List[str] = []
    test_read_count = 0

    creds = load_credentials()
    sheets_service = build_sheets_service(creds)

    main_titles = _get_sheet_titles(sheets_service, MAIN_SPREADSHEET_ID)
    diagnostics_titles = _get_sheet_titles(sheets_service, DIAGNOSTICS_SPREADSHEET_ID)

    candidate_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_CANDIDATE_SHEET,
        missing_sheets,
    )
    _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_BACKLOG_SHEET,
        missing_sheets,
    )
    _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_CANDIDATE_SUMMARY_SHEET,
        missing_sheets,
    )
    _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_REQUEST_HISTORY_SHEET,
        missing_sheets,
    )
    library_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_LIBRARY_SHEET,
        missing_sheets,
    )
    event_sample = _read_sheet_sample(
        sheets_service,
        MAIN_SPREADSHEET_ID,
        main_titles,
        INPUT_EVENT_SHEET,
        missing_sheets,
    )
    event_catalog_sample = _read_sheet_sample(
        sheets_service,
        MAIN_SPREADSHEET_ID,
        main_titles,
        INPUT_FMP_EVENT_CATALOG_SHEET,
        missing_sheets,
    )
    _read_sheet_sample(
        sheets_service,
        MAIN_SPREADSHEET_ID,
        main_titles,
        INPUT_FRED_SERIES_SHEET,
        missing_sheets,
    )
    _read_sheet_sample(
        sheets_service,
        MAIN_SPREADSHEET_ID,
        main_titles,
        INPUT_SERIES_MAP_SHEET,
        missing_sheets,
    )
    _read_sheet_sample(
        sheets_service,
        MAIN_SPREADSHEET_ID,
        main_titles,
        INPUT_SERIES_MAP_SUGGESTIONS_SHEET,
        missing_sheets,
    )
    config_map = _read_config_map(sheets_service)
    repo_evidence = _scan_repo_evidence()

    availability_rows: List[Dict[str, Any]] = []
    if not args.skip_test_read:
        try:
            script_service = build_script_service(creds)
            audit_result = run_script_function(
                script_service,
                default_script_id(),
                "runMinimalDataAvailabilityAudit",
                [],
            )
            if isinstance(audit_result, dict):
                availability_rows = audit_result.get("rows", []) or []
                test_read_count += 1
            else:
                warnings.append("Apps Script minimal data availability audit returned a non-dict payload.")
        except Exception as exc:
            warnings.append(f"Apps Script minimal data availability audit failed: {exc}")
    else:
        warnings.append("Skipped external test read by CLI flag.")

    candidate_map = _row_map_by_family(candidate_rows)
    library_stats = _find_library_stats(library_rows)
    event_headers = _headers_from_sample(event_sample)
    event_catalog_headers = _headers_from_sample(event_catalog_sample)
    audit_rows = _build_audit_rows(
        generated_ts,
        audit_run_id,
        candidate_map,
        library_stats,
        _availability_index(availability_rows),
        repo_evidence,
        event_headers,
        event_catalog_headers,
    )
    detail_rows = _build_detail_rows(generated_ts, audit_run_id, audit_rows, candidate_map, library_stats)
    summary_row = _build_summary_row(
        audit_run_id,
        generated_ts,
        audit_rows,
        detail_rows,
        sorted(set(missing_sheets)),
        test_read_count,
        warnings,
    )

    audit_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    detail_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DETAIL_SHEET, DETAIL_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DETAIL_SHEET, detail_headers, detail_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
    registry_result = _upsert_registry_rows(sheets_service)

    return {
        "audit_run_id": audit_run_id,
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "audit_rows_written": len(audit_rows),
        "detail_rows_written": len(detail_rows),
        "summary_rows_written": 1,
        "candidate_families_audited": summary_row["candidate_families_audited"],
        "candidate_fields_audited": summary_row["candidate_fields_audited"],
        "missing_sheets": sorted(set(missing_sheets)),
        "test_read_count": test_read_count,
        "warnings": warnings,
        "registry": registry_result,
        "summary": summary_row,
        "detail_rows": detail_rows,
    }


def main() -> None:
    result = build_market_state_source_audit_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
