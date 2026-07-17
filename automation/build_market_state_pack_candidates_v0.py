import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
from automation.build_session_information_requests_v0 import (
    ALLOWED_INFORMATION_CATEGORIES,
    CATEGORY_NORMALIZATION_MAP,
    _iso_now,
    _normalize_provider_name,
    _truncate_text,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


REQUEST_SHEET = "Session_Information_Requests"
LIBRARY_SHEET = "Information_Requirement_Library"
SESSION_EVALUATION_SHEET = "Session_Evaluation"
BASELINE_COMPARE_SHEET = "Session_vs_Event_Baseline_Compare"
BASELINE_SUMMARY_SHEET = "Session_Baseline_Compare_Summary"

OUTPUT_CANDIDATE_SHEET = "Market_State_Pack_Candidates"
OUTPUT_BACKLOG_SHEET = "Market_State_Pack_Acquisition_Backlog"
OUTPUT_SUMMARY_SHEET = "Market_State_Pack_Candidate_Summary"

SCHEMA_VERSION = "presignal_v2_market_state_candidate_0.1"
SHADOW_VERSION = "shadow_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 7"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

ALLOWED_INFORMATION_CLASSES = {
    "quantitative_direct",
    "quantitative_derived",
    "qualitative_source_grounded",
    "qualitative_interpretive",
}
ALLOWED_ACQUISITION_METHODS = {
    "deterministic_fetch",
    "computed_feature",
    "ai_retrieved_provisional",
    "ai_research_summary",
    "manual_backfill",
    "not_available",
}
ALLOWED_CANDIDATE_STATUSES = {
    "REQUESTED",
    "REPEATED",
    "CANDIDATE_FEATURE",
    "SOURCE_FOUND",
    "IMPLEMENTED",
    "VALIDATED",
    "REJECTED",
    "MONITOR",
}

CANDIDATE_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "candidate_id",
    "information_key",
    "canonical_information",
    "information_class",
    "information_category",
    "request_count",
    "provider_count",
    "session_count",
    "providers_requesting",
    "example_requested_phrases",
    "priority_profile",
    "linked_success_count",
    "linked_failure_count",
    "candidate_status",
    "recommended_acquisition_method",
    "deterministic_source_candidate",
    "provisional_allowed",
    "backtest_safe_candidate",
    "risk_of_provider_bias",
    "promotion_reason",
    "rejection_reason",
    "notes",
]

BACKLOG_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "candidate_id",
    "information_key",
    "canonical_information",
    "information_class",
    "recommended_acquisition_method",
    "source_status",
    "source_name",
    "symbol_or_query",
    "implementation_status",
    "owner",
    "priority",
    "difficulty",
    "backtest_safe",
    "data_latency",
    "cost_estimate",
    "validation_status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "phase",
    "build_status",
    "final_interpretation",
    "requests_read",
    "library_rows_read",
    "candidate_rows_written",
    "backlog_rows_written",
    "quantitative_direct_count",
    "quantitative_derived_count",
    "qualitative_source_grounded_count",
    "qualitative_interpretive_count",
    "deterministic_fetch_candidate_count",
    "computed_feature_candidate_count",
    "ai_research_summary_candidate_count",
    "not_available_count",
    "backtest_safe_candidate_count",
    "high_bias_risk_count",
    "notes",
]


DIRECT_KEYWORDS = {
    "yield",
    "yields",
    "dxy",
    "volatility",
    "vix",
    "consensus",
    "prior",
    "revision",
    "calendar",
    "event",
}
DERIVED_KEYWORDS = {
    "trend",
    "direction",
    "positioning",
    "sensitivity",
    "expectation",
    "expectations",
    "surprise",
    "historical",
}
SOURCE_GROUNDED_KEYWORDS = {
    "narrative",
    "tone",
    "sentiment",
    "context",
    "larger events",
    "upcoming",
    "intervention",
    "announcements",
}
INTERPRETIVE_KEYWORDS = {
    "risk",
    "behavior",
    "assessment",
    "analysis",
    "market positioning",
}

DIRECT_CATEGORIES = {"treasury_yields", "dxy", "event_consensus_detail", "volatility"}
DERIVED_CATEGORIES = {"usdjpy_trend", "historical_surprise_sensitivity", "fed_expectations"}
SOURCE_GROUNDED_CATEGORIES = {
    "inflation_narrative",
    "equity_tone",
    "growth_context",
    "labor_market_trend",
    "upcoming_larger_events",
}
INTERPRETIVE_CATEGORIES = {"risk_sentiment", "market_positioning", "jpy_intervention_risk", "other"}

SOURCE_MAP = {
    "treasury_yields": ("UST 2Y/10Y market data", "US02Y, US10Y", "available_vendor_check"),
    "fed_expectations": ("Fed funds futures / OIS", "FEDFUNDS_PATH", "needs_mapping"),
    "dxy": ("DXY index feed", "DXY", "available_vendor_check"),
    "usdjpy_trend": ("USDJPY price history", "USDJPY", "available_vendor_check"),
    "risk_sentiment": ("Cross-asset risk dashboard", "SPX/NQ/TNX bundle", "needs_definition"),
    "equity_tone": ("US equity index session data", "SPX, NQ", "available_vendor_check"),
    "inflation_narrative": ("CPI/PCE source set", "CPI|PCE headlines", "needs_summary_logic"),
    "labor_market_trend": ("NFP/claims trend series", "NFP|ICSA|CJC", "available_vendor_check"),
    "growth_context": ("GDP/ISM source set", "GDP|ISM", "needs_summary_logic"),
    "market_positioning": ("CFTC / positioning proxies", "CFTC|options skew", "limited"),
    "upcoming_larger_events": ("Economic calendar", "calendar_lookup", "available_vendor_check"),
    "jpy_intervention_risk": ("MOF/BOJ statements", "BOJ|MOF headlines", "limited"),
    "volatility": ("FX implied/realized vol feed", "USDJPY_VOL", "available_vendor_check"),
    "historical_surprise_sensitivity": ("Historical event study", "event_study_query", "needs_compute"),
    "event_consensus_detail": ("Event calendar detail", "consensus|prior|revision", "available_vendor_check"),
    "other": ("unknown", "", "unmapped"),
}


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
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _safe_float_local(value: Any) -> Optional[float]:
    try:
        text = _norm(value)
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _priority_rank(priority: str) -> int:
    return {
        "must_have": 4,
        "useful": 3,
        "optional": 2,
        "low_value": 1,
    }.get(priority, 0)


def _normalize_category(value: Any) -> str:
    raw = _norm(value).lower()
    if not raw:
        return "other"
    if raw in ALLOWED_INFORMATION_CATEGORIES:
        return raw
    return CATEGORY_NORMALIZATION_MAP.get(raw, "other")


def _information_class(category: str, canonical_information: str) -> str:
    text = canonical_information.lower()
    if category in {"risk_sentiment", "market_positioning", "jpy_intervention_risk"}:
        return "qualitative_interpretive"
    if category in {"inflation_narrative", "growth_context", "upcoming_larger_events"}:
        return "qualitative_source_grounded"
    if category in DIRECT_CATEGORIES or any(token in text for token in DIRECT_KEYWORDS):
        return "quantitative_direct"
    if category in DERIVED_CATEGORIES or any(token in text for token in DERIVED_KEYWORDS):
        return "quantitative_derived"
    if category in SOURCE_GROUNDED_CATEGORIES or any(token in text for token in SOURCE_GROUNDED_KEYWORDS):
        return "qualitative_source_grounded"
    if category in INTERPRETIVE_CATEGORIES or any(token in text for token in INTERPRETIVE_KEYWORDS):
        return "qualitative_interpretive"
    return "qualitative_interpretive"


def _recommended_acquisition_method(category: str, information_class: str, available_now_values: Set[str]) -> str:
    if information_class == "quantitative_direct":
        return "deterministic_fetch"
    if information_class == "quantitative_derived":
        return "computed_feature"
    if information_class == "qualitative_source_grounded":
        if "yes" in available_now_values or "partial" in available_now_values:
            return "ai_retrieved_provisional"
        return "manual_backfill"
    if category in {"market_positioning", "jpy_intervention_risk"}:
        return "ai_research_summary"
    if "no" in available_now_values and len(available_now_values) == 1:
        return "not_available"
    return "ai_research_summary"


def _candidate_status(
    request_count: int,
    provider_count: int,
    linked_success_count: int,
    recommended_acquisition_method: str,
    backtest_safe: bool,
) -> str:
    if recommended_acquisition_method == "not_available":
        return "MONITOR"
    if provider_count >= 2 and request_count >= 3 and backtest_safe:
        return "CANDIDATE_FEATURE"
    if request_count >= 2 or provider_count >= 2:
        return "REPEATED"
    if linked_success_count == 0 and recommended_acquisition_method in {"ai_research_summary", "manual_backfill"}:
        return "MONITOR"
    return "REQUESTED"


def _backtest_safe(information_class: str, recommended_acquisition_method: str, category: str) -> bool:
    if recommended_acquisition_method in {"deterministic_fetch", "computed_feature"}:
        return True
    if information_class == "qualitative_source_grounded" and category in {"upcoming_larger_events", "inflation_narrative"}:
        return False
    return False


def _risk_of_provider_bias(information_class: str, recommended_acquisition_method: str) -> str:
    if recommended_acquisition_method in {"deterministic_fetch", "computed_feature"}:
        return "low"
    if information_class == "qualitative_source_grounded":
        return "medium"
    return "high"


def _priority_profile(rows: Sequence[Dict[str, Any]]) -> str:
    counts = Counter(_norm(row.get("priority")) for row in rows if _norm(row.get("priority")))
    ordered = [f"{priority}:{counts[priority]}" for priority in ["must_have", "useful", "optional", "low_value"] if counts[priority]]
    return "|".join(ordered)


def _source_candidate_fields(category: str) -> Tuple[str, str, str]:
    source_name, symbol_or_query, source_status = SOURCE_MAP.get(category, SOURCE_MAP["other"])
    return source_name, symbol_or_query, source_status


def _row_success_maps(
    evaluation_rows: Sequence[Dict[str, Any]],
    baseline_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str], bool], Dict[Tuple[str, str], str]]:
    eval_map: Dict[Tuple[str, str], bool] = {}
    for row in evaluation_rows:
        key = (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider")))
        if key[0] and key[1]:
            eval_map[key] = _as_bool(row.get("overall_ok"))
    baseline_map: Dict[Tuple[str, str], str] = {}
    for row in baseline_rows:
        key = (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider")))
        if key[0] and key[1]:
            baseline_map[key] = _norm(row.get("comparison_label"))
    return eval_map, baseline_map


def _validate_inputs(
    request_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
    evaluation_rows: Sequence[Dict[str, Any]],
    baseline_rows: Sequence[Dict[str, Any]],
    baseline_summary_rows: Sequence[Dict[str, Any]],
) -> None:
    _require_headers(
        REQUEST_SHEET,
        request_rows,
        [
            "session_id",
            "provider",
            "requested_information",
            "information_category",
            "priority",
            "available_now",
            "suggested_source",
            "expected_forecast_use",
            "is_market_state_candidate",
        ],
    )
    _require_headers(
        LIBRARY_SHEET,
        library_rows,
        [
            "information_key",
            "canonical_information",
            "information_category",
            "request_count",
            "provider_count",
            "session_count",
            "providers_requesting",
        ],
    )
    _require_headers(
        SESSION_EVALUATION_SHEET,
        evaluation_rows,
        ["session_id", "provider", "overall_ok", "information_quality_label"],
    )
    _require_headers(
        BASELINE_COMPARE_SHEET,
        baseline_rows,
        ["session_id", "provider", "comparison_label", "comparison_status"],
    )
    _require_headers(
        BASELINE_SUMMARY_SHEET,
        baseline_summary_rows,
        ["build_status", "final_interpretation"],
    )


def _library_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("information_key")): row for row in rows if _norm(row.get("information_key"))}


def _candidate_id(information_key: str) -> str:
    return f"market_state_candidate|{information_key}"


def _aggregate_candidates(
    generated_ts: str,
    request_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
    evaluation_rows: Sequence[Dict[str, Any]],
    baseline_rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Counter]:
    lib_map = _library_map(library_rows)
    eval_success_map, baseline_map = _row_success_maps(evaluation_rows, baseline_rows)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in request_rows:
        key = _norm(row.get("information_key"))
        if not key:
            category = _normalize_category(row.get("information_category"))
            key = f"{category}|{_canonical_slug(row.get('requested_information'))}"
        grouped[key].append(row)

    candidate_rows: List[Dict[str, Any]] = []
    backlog_rows: List[Dict[str, Any]] = []
    metrics = Counter()

    for information_key in sorted(grouped):
        rows = grouped[information_key]
        lib_row = lib_map.get(information_key, {})
        canonical_information = _norm(lib_row.get("canonical_information")) or _norm(rows[0].get("requested_information"))
        category = _normalize_category(_norm(lib_row.get("information_category")) or rows[0].get("information_category"))
        information_class = _information_class(category, canonical_information)
        providers = sorted({_normalize_provider_name(row.get("provider")) for row in rows if _normalize_provider_name(row.get("provider"))})
        sessions = sorted({_norm(row.get("session_id")) for row in rows if _norm(row.get("session_id"))})
        available_now_values = {_norm(row.get("available_now")).lower() for row in rows if _norm(row.get("available_now"))}
        recommended_method = _recommended_acquisition_method(category, information_class, available_now_values)
        source_name, symbol_or_query, source_status = _source_candidate_fields(category)
        backtest_safe = _backtest_safe(information_class, recommended_method, category)
        bias_risk = _risk_of_provider_bias(information_class, recommended_method)
        linked_success_count = 0
        linked_failure_count = 0
        for row in rows:
            pair = (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider")))
            if eval_success_map.get(pair) is True:
                linked_success_count += 1
            elif pair in eval_success_map:
                linked_failure_count += 1
            elif baseline_map.get(pair) in {"session_better", "v1_better", "same_result", "mixed_result"}:
                linked_failure_count += 1

        request_count = len(rows)
        provider_count = len(providers)
        session_count = len(sessions)
        candidate_status = _candidate_status(
            request_count,
            provider_count,
            linked_success_count,
            recommended_method,
            backtest_safe,
        )
        provisional_allowed = recommended_method in {"ai_retrieved_provisional", "ai_research_summary"}
        promotion_reason_bits = [
            f"request_count={request_count}",
            f"provider_count={provider_count}",
            f"session_count={session_count}",
            f"linked_success_count={linked_success_count}",
        ]
        if recommended_method == "deterministic_fetch":
            promotion_reason_bits.append("deterministic source candidate identified")
        if recommended_method == "computed_feature":
            promotion_reason_bits.append("can be derived from existing deterministic inputs")
        rejection_reason = ""
        if recommended_method == "not_available":
            rejection_reason = "no safe deterministic or provisional acquisition path identified yet"
        elif bias_risk == "high" and not backtest_safe:
            rejection_reason = "high interpretive/provider-bias risk; monitor before pack inclusion"

        candidate_id = _candidate_id(information_key)
        candidate_row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "candidate_id": candidate_id,
            "information_key": information_key,
            "canonical_information": canonical_information,
            "information_class": information_class,
            "information_category": category,
            "request_count": request_count,
            "provider_count": provider_count,
            "session_count": session_count,
            "providers_requesting": _join_unique(providers),
            "example_requested_phrases": _join_unique(row.get("requested_information") for row in rows[:5]),
            "priority_profile": _priority_profile(rows),
            "linked_success_count": linked_success_count,
            "linked_failure_count": linked_failure_count,
            "candidate_status": candidate_status,
            "recommended_acquisition_method": recommended_method,
            "deterministic_source_candidate": source_name,
            "provisional_allowed": "TRUE" if provisional_allowed else "FALSE",
            "backtest_safe_candidate": "TRUE" if backtest_safe else "FALSE",
            "risk_of_provider_bias": bias_risk,
            "promotion_reason": _truncate_text("; ".join(promotion_reason_bits), 240),
            "rejection_reason": _truncate_text(rejection_reason, 240),
            "notes": _truncate_text(
                f"source_status={source_status}; symbol_or_query={symbol_or_query or '<blank>'}; library_request_count={_norm(lib_row.get('request_count')) or '<blank>'}",
                240,
            ),
        }
        candidate_rows.append(candidate_row)

        numeric_priority = max((_priority_rank(_norm(row.get("priority"))) for row in rows), default=0)
        backlog_priority = {
            4: "high",
            3: "medium",
            2: "medium",
            1: "low",
            0: "low",
        }[numeric_priority]
        difficulty = {
            "deterministic_fetch": "low",
            "computed_feature": "medium",
            "ai_retrieved_provisional": "medium",
            "ai_research_summary": "high",
            "manual_backfill": "high",
            "not_available": "high",
        }[recommended_method]
        data_latency = {
            "deterministic_fetch": "intraday",
            "computed_feature": "intraday",
            "ai_retrieved_provisional": "same_day",
            "ai_research_summary": "same_day",
            "manual_backfill": "delayed",
            "not_available": "unknown",
        }[recommended_method]
        cost_estimate = {
            "deterministic_fetch": "low",
            "computed_feature": "low",
            "ai_retrieved_provisional": "medium",
            "ai_research_summary": "medium",
            "manual_backfill": "high",
            "not_available": "unknown",
        }[recommended_method]
        backlog_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "candidate_id": candidate_id,
                "information_key": information_key,
                "canonical_information": canonical_information,
                "information_class": information_class,
                "recommended_acquisition_method": recommended_method,
                "source_status": source_status,
                "source_name": source_name,
                "symbol_or_query": symbol_or_query,
                "implementation_status": "NOT_STARTED",
                "owner": "unassigned",
                "priority": backlog_priority,
                "difficulty": difficulty,
                "backtest_safe": "TRUE" if backtest_safe else "FALSE",
                "data_latency": data_latency,
                "cost_estimate": cost_estimate,
                "validation_status": "UNVALIDATED",
                "notes": _truncate_text(
                    f"candidate_status={candidate_status}; providers={_join_unique(providers)}; provisional_allowed={provisional_allowed}",
                    240,
                ),
            }
        )

        metrics[f"{information_class}_count"] += 1
        if recommended_method == "deterministic_fetch":
            metrics["deterministic_fetch_candidate_count"] += 1
        if recommended_method == "computed_feature":
            metrics["computed_feature_candidate_count"] += 1
        if recommended_method == "ai_research_summary":
            metrics["ai_research_summary_candidate_count"] += 1
        if recommended_method == "not_available":
            metrics["not_available_count"] += 1
        if backtest_safe:
            metrics["backtest_safe_candidate_count"] += 1
        if bias_risk == "high":
            metrics["high_bias_risk_count"] += 1

    return candidate_rows, backlog_rows, metrics


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
            "logical_sheet_id": "MARKET_STATE_PACK_CANDIDATES",
            "physical_sheet_name": OUTPUT_CANDIDATE_SHEET,
            "sheet_role": "market_state_pack_candidates",
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
            "notes": "shadow_v0 market-state pack candidate registry",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_ACQUISITION_BACKLOG",
            "physical_sheet_name": OUTPUT_BACKLOG_SHEET,
            "sheet_role": "market_state_pack_acquisition_backlog",
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
            "notes": "shadow_v0 acquisition backlog only, no fetch execution",
        },
        {
            "logical_sheet_id": "MARKET_STATE_PACK_CANDIDATE_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "market_state_pack_candidate_summary",
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
            "notes": "shadow_v0 candidate build summary",
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


def _build_summary_row(
    generated_ts: str,
    request_count: int,
    library_count: int,
    candidate_rows: Sequence[Dict[str, Any]],
    backlog_rows: Sequence[Dict[str, Any]],
    metrics: Counter,
) -> Dict[str, Any]:
    if not candidate_rows:
        build_status = "FAIL"
        final_interpretation = "MARKET_STATE_CANDIDATES_FAILED"
    elif metrics.get("high_bias_risk_count", 0) > 0 or metrics.get("not_available_count", 0) > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "MARKET_STATE_CANDIDATES_READY_WITH_LIMITATIONS"
    else:
        build_status = "PASS"
        final_interpretation = "MARKET_STATE_CANDIDATES_READY"
    notes = (
        f"candidate_statuses={json.dumps(Counter(_norm(row.get('candidate_status')) for row in candidate_rows), ensure_ascii=True)}; "
        f"acquisition_methods={json.dumps(Counter(_norm(row.get('recommended_acquisition_method')) for row in candidate_rows), ensure_ascii=True)}; "
        "phase7_is_classification_only"
    )
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "phase": PHASE_LABEL,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "requests_read": request_count,
        "library_rows_read": library_count,
        "candidate_rows_written": len(candidate_rows),
        "backlog_rows_written": len(backlog_rows),
        "quantitative_direct_count": metrics.get("quantitative_direct_count", 0),
        "quantitative_derived_count": metrics.get("quantitative_derived_count", 0),
        "qualitative_source_grounded_count": metrics.get("qualitative_source_grounded_count", 0),
        "qualitative_interpretive_count": metrics.get("qualitative_interpretive_count", 0),
        "deterministic_fetch_candidate_count": metrics.get("deterministic_fetch_candidate_count", 0),
        "computed_feature_candidate_count": metrics.get("computed_feature_candidate_count", 0),
        "ai_research_summary_candidate_count": metrics.get("ai_research_summary_candidate_count", 0),
        "not_available_count": metrics.get("not_available_count", 0),
        "backtest_safe_candidate_count": metrics.get("backtest_safe_candidate_count", 0),
        "high_bias_risk_count": metrics.get("high_bias_risk_count", 0),
        "notes": _truncate_text(notes, 500),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Market-State Pack Candidate Build v0 in diagnostics workbook.")
    return parser.parse_args(argv)


def build_market_state_pack_candidates_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    generated_ts = _iso_now()

    request_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, REQUEST_SHEET)
    library_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, LIBRARY_SHEET)
    evaluation_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, SESSION_EVALUATION_SHEET)
    baseline_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, BASELINE_COMPARE_SHEET)
    baseline_summary_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, BASELINE_SUMMARY_SHEET)

    _validate_inputs(request_rows, library_rows, evaluation_rows, baseline_rows, baseline_summary_rows)

    candidate_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CANDIDATE_SHEET, CANDIDATE_HEADERS)
    backlog_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_BACKLOG_SHEET, BACKLOG_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    candidate_rows, backlog_rows, metrics = _aggregate_candidates(
        generated_ts,
        request_rows,
        library_rows,
        evaluation_rows,
        baseline_rows,
    )
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CANDIDATE_SHEET, candidate_headers, candidate_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_BACKLOG_SHEET, backlog_headers, backlog_rows)
    registry_result = _upsert_registry_rows(sheets_service)
    summary_row = _build_summary_row(
        generated_ts,
        len(request_rows),
        len(library_rows),
        candidate_rows,
        backlog_rows,
        metrics,
    )
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "requests_read": len(request_rows),
        "library_rows_read": len(library_rows),
        "candidate_rows_written": len(candidate_rows),
        "backlog_rows_written": len(backlog_rows),
        "quantitative_direct_count": summary_row["quantitative_direct_count"],
        "quantitative_derived_count": summary_row["quantitative_derived_count"],
        "qualitative_source_grounded_count": summary_row["qualitative_source_grounded_count"],
        "qualitative_interpretive_count": summary_row["qualitative_interpretive_count"],
        "deterministic_fetch_candidate_count": summary_row["deterministic_fetch_candidate_count"],
        "computed_feature_candidate_count": summary_row["computed_feature_candidate_count"],
        "ai_research_summary_candidate_count": summary_row["ai_research_summary_candidate_count"],
        "not_available_count": summary_row["not_available_count"],
        "backtest_safe_candidate_count": summary_row["backtest_safe_candidate_count"],
        "high_bias_risk_count": summary_row["high_bias_risk_count"],
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "registry_result": registry_result,
        "sample_candidate_row": candidate_rows[0] if candidate_rows else {},
        "sample_backlog_row": backlog_rows[0] if backlog_rows else {},
    }


def main() -> None:
    print(json.dumps(build_market_state_pack_candidates_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
