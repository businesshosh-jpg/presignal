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
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


INPUT_SHADOW_SHEET = "Market_State_Pack_Shadow"
INPUT_ITEM_AUDIT_SHEET = "Market_State_Pack_Item_Audit"
INPUT_COVERAGE_SHEET = "Market_State_Pack_Coverage_Audit"
INPUT_SHADOW_SUMMARY_SHEET = "Market_State_Pack_Shadow_Summary"
INPUT_MAPPING_SHEET = "Market_State_Source_Mapping"
INPUT_SEMANTICS_SHEET = "Market_State_Source_Semantics"
INPUT_CANDIDATES_SHEET = "Market_State_Pack_Candidates"
INPUT_INFO_HISTORY_SHEET = "Session_Information_Requests_History"
INPUT_ATTENTION_HISTORY_SHEET = "Session_Attention_Map_History"
OPTIONAL_INPUT_SHEETS = [
    "Market_State_Pack_Shadow_Run_Log",
    "Market_State_Source_Audit",
    "Market_State_Source_Audit_Summary",
]

OUTPUT_DEFINITION_SHEET = "Market_State_Pack_Level_Definition"
OUTPUT_ITEMS_SHEET = "Market_State_Pack_Level_Items"
OUTPUT_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
OUTPUT_READINESS_SHEET = "Market_State_Pack_Level_Readiness_Audit"

SCHEMA_VERSION = "presignal_v2_market_state_pack_level_design_0.1"
PACK_DESIGN_VERSION = "pack_level_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 8C"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_STATE_PACK_LEVEL_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

FAMILY_ORDER = ["usdjpy_trend", "upcoming_larger_events", "treasury_yields", "dxy"]
EXPECTED_FIELDS = {
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
EXCLUDED_FIELDS = {"UPCOMING_EVENT_RISK_LABEL"}
BLOCKED_FAMILIES = {"fed_expectations"}

DEFINITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "pack_design_version",
    "pack_design_run_id",
    "pack_level",
    "pack_level_name",
    "pack_level_order",
    "pack_level_status",
    "phase_allowed",
    "provider_visible_in_this_phase",
    "used_in_forecast_in_this_phase",
    "description",
    "research_question",
    "included_family_count",
    "included_field_count",
    "excluded_family_count",
    "excluded_field_count",
    "expected_behavioral_effect",
    "accuracy_claim_allowed",
    "notes",
]

ITEM_HEADERS = [
    "generated_ts",
    "schema_version",
    "pack_design_version",
    "pack_design_run_id",
    "pack_level",
    "pack_level_name",
    "pack_level_order",
    "candidate_family",
    "candidate_field",
    "include_in_level",
    "inclusion_reason",
    "exclusion_reason",
    "lane_assignment",
    "early_pack_level_eligible",
    "field_refinement_status",
    "source_provider",
    "source_name",
    "symbol_or_series_id",
    "source_type",
    "acquisition_method",
    "point_in_time_status",
    "leakage_check_status",
    "backtest_safe",
    "warning_label",
    "field_available_session_count",
    "field_missing_session_count",
    "field_warning_session_count",
    "field_fail_session_count",
    "phase9_allowed",
    "provider_visible_in_this_phase",
    "used_in_forecast_in_this_phase",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "pack_design_version",
    "pack_design_run_id",
    "pack_level",
    "pack_level_name",
    "field_count",
    "eligible_field_count",
    "ineligible_field_count",
    "missing_field_count",
    "warning_field_count",
    "fail_field_count",
    "included_family_count",
    "has_usdjpy_trend",
    "has_upcoming_larger_events",
    "has_treasury_yields",
    "has_dxy",
    "has_fed_expectations",
    "has_qualitative_items",
    "has_interpretive_items",
    "has_upcoming_event_risk_label",
    "dxy_proxy_separation_preserved",
    "provider_visible_in_this_phase_count",
    "used_in_forecast_in_this_phase_count",
    "phase9_readiness_status",
    "blocking_reason",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "pack_design_version",
    "pack_design_run_id",
    "build_status",
    "final_interpretation",
    "pack_levels_defined",
    "pack_levels_ready",
    "pack_levels_with_warnings",
    "pack_levels_blocked",
    "placeholder_levels",
    "total_level_item_rows",
    "eligible_field_count",
    "ineligible_field_count",
    "feature_freeze_active",
    "new_deterministic_field_count",
    "fed_expectations_included_count",
    "upcoming_event_risk_label_included_count",
    "lane_b_included_count",
    "lane_c_included_count",
    "provider_visible_count",
    "used_in_forecast_count",
    "market_state_pack_write_count",
    "provider_prompt_change_count",
    "phase9_sheet_write_count",
    "v1_sheet_write_count",
    "production_behavior_change_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _design_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"market_state_pack_level_design_v0_{stamp}"


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


def _latest_run_id(summary_rows: Sequence[Dict[str, Any]]) -> str:
    if not summary_rows:
        return ""
    return _norm(summary_rows[-1].get("shadow_pack_run_id"))


def _field_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (_norm(row.get("candidate_family")).lower(), _norm(row.get("candidate_field")))


def _aggregate_status(values: Iterable[str], preferred: str = "PASS") -> str:
    rank = {"PASS": 0, "PASS_WITH_WARNINGS": 1, "NEEDS_REVIEW": 2, "FAIL": 3}
    vals = [_upper(v) for v in values if _norm(v)]
    if not vals:
        return preferred
    return max(vals, key=lambda value: rank.get(value, 2))


def _eligible_fields(shadow_rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    by_field: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in shadow_rows:
        family, field = _field_key(row)
        if family in BLOCKED_FAMILIES or field in EXCLUDED_FIELDS:
            continue
        if family not in EXPECTED_FIELDS or field not in EXPECTED_FIELDS[family]:
            continue
        by_field[(family, field)].append(row)

    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for key, rows in by_field.items():
        sample = rows[0]
        available = sum(1 for row in rows if _upper(row.get("data_available_flag")) == "TRUE")
        missing = sum(1 for row in rows if _upper(row.get("data_available_flag")) != "TRUE")
        warnings = sum(1 for row in rows if _norm(row.get("warning_label")) or _upper(row.get("point_in_time_status")) == "PASS_WITH_WARNINGS")
        fail = sum(1 for row in rows if _upper(row.get("leakage_check_status")) == "FAIL")
        lane = _norm(sample.get("lane_assignment"))
        eligible = _upper(sample.get("early_pack_level_eligible")) == "TRUE"
        phase9_allowed = "TRUE"
        notes: List[str] = []
        if not eligible:
            phase9_allowed = "FALSE"
            notes.append("early_pack_level_eligible is FALSE")
        if lane != "LANE_A_DETERMINISTIC":
            phase9_allowed = "FALSE"
            notes.append("field is not Lane A deterministic")
        if fail:
            phase9_allowed = "FALSE"
            notes.append("one or more sessions have leakage FAIL")
        out[key] = {
            "candidate_family": key[0],
            "candidate_field": key[1],
            "lane_assignment": lane,
            "early_pack_level_eligible": "TRUE" if eligible else "FALSE",
            "field_refinement_status": _norm(sample.get("field_refinement_status")),
            "source_provider": _norm(sample.get("source_provider")),
            "source_name": _norm(sample.get("source_name")),
            "symbol_or_series_id": _norm(sample.get("symbol_or_series_id")),
            "source_type": _norm(sample.get("source_type")),
            "acquisition_method": _norm(sample.get("acquisition_method")),
            "point_in_time_status": _aggregate_status(row.get("point_in_time_status") for row in rows),
            "leakage_check_status": _aggregate_status(row.get("leakage_check_status") for row in rows),
            "backtest_safe": "TRUE" if all(_upper(row.get("backtest_safe")) == "TRUE" for row in rows) else "FALSE",
            "warning_label": "|".join(sorted({label for label in (_norm(row.get("warning_label")) for row in rows) if label})),
            "field_available_session_count": available,
            "field_missing_session_count": missing,
            "field_warning_session_count": warnings,
            "field_fail_session_count": fail,
            "phase9_allowed": phase9_allowed,
            "notes": "; ".join(notes),
        }
    return out


def _level_specs() -> List[Dict[str, Any]]:
    return [
        {
            "level": "A",
            "name": "NO_PACK",
            "order": 1,
            "families": [],
            "status": "DEFINED",
            "phase_allowed": "FUTURE_PHASE9_DESIGN",
            "description": "Baseline comparison level with no Market-State Pack fields.",
            "research_question": "How do no-pack v2.0 session forecasts behave?",
            "effect": "baseline no-pack provider behavior.",
        },
        {
            "level": "B",
            "name": "TARGET_STATE_ONLY",
            "order": 2,
            "families": ["usdjpy_trend"],
            "status": "DEFINED_WITH_WARNINGS",
            "phase_allowed": "FUTURE_PHASE9_DESIGN",
            "description": "Target-instrument state only.",
            "research_question": "Does recent USDJPY state change provider behavior?",
            "effect": "tests whether target-instrument momentum changes direction, confidence, or no-signal behavior.",
        },
        {
            "level": "C",
            "name": "TARGET_PLUS_CALENDAR",
            "order": 3,
            "families": ["usdjpy_trend", "upcoming_larger_events"],
            "status": "DEFINED_WITH_WARNINGS",
            "phase_allowed": "FUTURE_PHASE9_DESIGN",
            "description": "Target state plus deterministic scheduled-event context.",
            "research_question": "Does scheduled event context alter caution, confidence, or no-signal behavior?",
            "effect": "tests whether upcoming scheduled event context increases caution or changes holding assumptions.",
        },
        {
            "level": "D",
            "name": "RATES_DOLLAR_CONTEXT",
            "order": 4,
            "families": ["usdjpy_trend", "upcoming_larger_events", "treasury_yields", "dxy"],
            "status": "DEFINED_WITH_WARNINGS",
            "phase_allowed": "FUTURE_PHASE9_DESIGN",
            "description": "Target, calendar, rates, and dollar context.",
            "research_question": "Do rates and dollar context change provider interpretation beyond target/calendar state?",
            "effect": "tests whether rates and dollar context alter causal-chain reasoning and USDJPY direction confidence.",
        },
        {
            "level": "E",
            "name": "FULL_APPROVED_DETERMINISTIC_PACK",
            "order": 5,
            "families": ["usdjpy_trend", "upcoming_larger_events", "treasury_yields", "dxy"],
            "status": "DEFINED_WITH_WARNINGS",
            "phase_allowed": "FUTURE_PHASE9_DESIGN",
            "description": "All currently approved Lane A deterministic fields under Feature Freeze.",
            "research_question": "How does the full approved deterministic core affect future provider behavior?",
            "effect": "tests the full approved deterministic core under Feature Freeze.",
        },
        {
            "level": "Q",
            "name": "PROVISIONAL_QUALITATIVE_OVERLAY",
            "order": 99,
            "families": [],
            "status": "PLACEHOLDER_ONLY",
            "phase_allowed": "FUTURE_PHASE_8Q_OR_LATER",
            "description": "Future qualitative overlay placeholder.",
            "research_question": "Not active in this deterministic pack-level design.",
            "effect": "future qualitative overlay; not part of current deterministic experiment.",
        },
    ]


def _fields_for_level(spec: Dict[str, Any], eligible_by_field: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    for family in spec["families"]:
        for field in EXPECTED_FIELDS.get(family, []):
            if (family, field) in eligible_by_field:
                fields.append((family, field))
    return fields


def _definition_rows(
    generated_ts: str,
    run_id: str,
    specs: Sequence[Dict[str, Any]],
    eligible_by_field: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    d_fields = set(_fields_for_level(specs[3], eligible_by_field))
    e_fields = set(_fields_for_level(specs[4], eligible_by_field))
    for spec in specs:
        fields = _fields_for_level(spec, eligible_by_field)
        families = sorted({family for family, _ in fields})
        excluded_fields = 0
        notes = ""
        if spec["level"] == "C":
            excluded_fields = 1
            notes = "UPCOMING_EVENT_RISK_LABEL excluded because it is Lane B provisional and not early-pack-level eligible."
        elif spec["level"] in {"D", "E"}:
            excluded_fields = 1
            notes = "UPCOMING_EVENT_RISK_LABEL and fed_expectations excluded; DXY and USD_INDEX_PROXY remain separated."
        if spec["level"] == "E" and d_fields == e_fields:
            notes = (notes + " " if notes else "") + "Pack E currently identical to Pack D under Feature Freeze."
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "pack_design_version": PACK_DESIGN_VERSION,
                "pack_design_run_id": run_id,
                "pack_level": spec["level"],
                "pack_level_name": spec["name"],
                "pack_level_order": spec["order"],
                "pack_level_status": spec["status"],
                "phase_allowed": spec["phase_allowed"],
                "provider_visible_in_this_phase": "FALSE",
                "used_in_forecast_in_this_phase": "FALSE",
                "description": spec["description"],
                "research_question": spec["research_question"],
                "included_family_count": len(families),
                "included_field_count": len(fields),
                "excluded_family_count": 1 if spec["level"] in {"D", "E"} else 0,
                "excluded_field_count": excluded_fields,
                "expected_behavioral_effect": spec["effect"],
                "accuracy_claim_allowed": "FALSE",
                "notes": _truncate_text(notes, 500),
            }
        )
    return rows


def _item_rows(
    generated_ts: str,
    run_id: str,
    specs: Sequence[Dict[str, Any]],
    eligible_by_field: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    all_fields = [(family, field) for family in FAMILY_ORDER for field in EXPECTED_FIELDS[family]]
    all_fields.append(("upcoming_larger_events", "UPCOMING_EVENT_RISK_LABEL"))
    for spec in specs:
        if spec["level"] == "Q":
            continue
        level_fields = set(_fields_for_level(spec, eligible_by_field))
        for family, field in all_fields:
            meta = eligible_by_field.get((family, field), {})
            include = (family, field) in level_fields
            if field == "UPCOMING_EVENT_RISK_LABEL":
                lane = "LANE_B_PROVISIONAL_CANDIDATE"
                early = "FALSE"
                phase9 = "FALSE"
                exclusion = "UPCOMING_EVENT_RISK_LABEL was downgraded to Lane B and excluded from early pack levels."
            else:
                lane = meta.get("lane_assignment", "LANE_A_DETERMINISTIC" if family in EXPECTED_FIELDS else "")
                early = meta.get("early_pack_level_eligible", "TRUE" if meta else "FALSE")
                phase9 = meta.get("phase9_allowed", "TRUE" if include else "FALSE")
                exclusion = "" if include else "field not included in this cumulative pack level"
            if family in BLOCKED_FAMILIES:
                phase9 = "FALSE"
                exclusion = "fed_expectations remains blocked."
            if not include:
                phase9 = "FALSE"
            rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "pack_design_version": PACK_DESIGN_VERSION,
                    "pack_design_run_id": run_id,
                    "pack_level": spec["level"],
                    "pack_level_name": spec["name"],
                    "pack_level_order": spec["order"],
                    "candidate_family": family,
                    "candidate_field": field,
                    "include_in_level": "TRUE" if include else "FALSE",
                    "inclusion_reason": "eligible Lane A deterministic field included by cumulative pack rule" if include else "",
                    "exclusion_reason": exclusion,
                    "lane_assignment": lane,
                    "early_pack_level_eligible": early,
                    "field_refinement_status": meta.get("field_refinement_status", "DOWNGRADED" if field == "UPCOMING_EVENT_RISK_LABEL" else ""),
                    "source_provider": meta.get("source_provider", ""),
                    "source_name": meta.get("source_name", ""),
                    "symbol_or_series_id": meta.get("symbol_or_series_id", ""),
                    "source_type": meta.get("source_type", ""),
                    "acquisition_method": meta.get("acquisition_method", ""),
                    "point_in_time_status": meta.get("point_in_time_status", ""),
                    "leakage_check_status": meta.get("leakage_check_status", ""),
                    "backtest_safe": meta.get("backtest_safe", ""),
                    "warning_label": meta.get("warning_label", "risk_label_heuristic_v0" if field == "UPCOMING_EVENT_RISK_LABEL" else ""),
                    "field_available_session_count": meta.get("field_available_session_count", 0),
                    "field_missing_session_count": meta.get("field_missing_session_count", 0),
                    "field_warning_session_count": meta.get("field_warning_session_count", 0),
                    "field_fail_session_count": meta.get("field_fail_session_count", 0),
                    "phase9_allowed": phase9 if include else "FALSE",
                    "provider_visible_in_this_phase": "FALSE",
                    "used_in_forecast_in_this_phase": "FALSE",
                    "notes": _truncate_text(meta.get("notes", ""), 500),
                }
            )
    return rows


def _readiness_rows(
    generated_ts: str,
    run_id: str,
    specs: Sequence[Dict[str, Any]],
    item_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_level: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in item_rows:
        by_level[_norm(row.get("pack_level"))].append(row)
    rows: List[Dict[str, Any]] = []
    for spec in specs:
        level_rows = [row for row in by_level.get(spec["level"], []) if _upper(row.get("include_in_level")) == "TRUE"]
        if spec["level"] == "Q":
            readiness = "PLACEHOLDER_ONLY"
            blocking = ""
        else:
            fail = sum(_safe_int(row.get("field_fail_session_count")) for row in level_rows)
            missing = sum(_safe_int(row.get("field_missing_session_count")) for row in level_rows)
            warning = sum(_safe_int(row.get("field_warning_session_count")) for row in level_rows)
            if fail or any(_upper(row.get("phase9_allowed")) == "FALSE" for row in level_rows):
                readiness = "BLOCKED"
                blocking = "included field failed eligibility or leakage checks"
            elif warning or missing:
                readiness = "READY_FOR_PHASE9_DESIGN_WITH_WARNINGS"
                blocking = ""
            else:
                readiness = "READY_FOR_PHASE9_DESIGN"
                blocking = ""
        families = {row.get("candidate_family") for row in level_rows}
        fields = {row.get("candidate_field") for row in level_rows}
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "pack_design_version": PACK_DESIGN_VERSION,
                "pack_design_run_id": run_id,
                "pack_level": spec["level"],
                "pack_level_name": spec["name"],
                "field_count": len(level_rows),
                "eligible_field_count": sum(1 for row in level_rows if _upper(row.get("early_pack_level_eligible")) == "TRUE"),
                "ineligible_field_count": sum(1 for row in level_rows if _upper(row.get("early_pack_level_eligible")) != "TRUE"),
                "missing_field_count": sum(_safe_int(row.get("field_missing_session_count")) for row in level_rows),
                "warning_field_count": sum(_safe_int(row.get("field_warning_session_count")) for row in level_rows),
                "fail_field_count": sum(_safe_int(row.get("field_fail_session_count")) for row in level_rows),
                "included_family_count": len(families),
                "has_usdjpy_trend": "TRUE" if "usdjpy_trend" in families else "FALSE",
                "has_upcoming_larger_events": "TRUE" if "upcoming_larger_events" in families else "FALSE",
                "has_treasury_yields": "TRUE" if "treasury_yields" in families else "FALSE",
                "has_dxy": "TRUE" if "dxy" in families else "FALSE",
                "has_fed_expectations": "TRUE" if "fed_expectations" in families else "FALSE",
                "has_qualitative_items": "FALSE",
                "has_interpretive_items": "TRUE" if "UPCOMING_EVENT_RISK_LABEL" in fields else "FALSE",
                "has_upcoming_event_risk_label": "TRUE" if "UPCOMING_EVENT_RISK_LABEL" in fields else "FALSE",
                "dxy_proxy_separation_preserved": "TRUE",
                "provider_visible_in_this_phase_count": sum(1 for row in level_rows if _upper(row.get("provider_visible_in_this_phase")) == "TRUE"),
                "used_in_forecast_in_this_phase_count": sum(1 for row in level_rows if _upper(row.get("used_in_forecast_in_this_phase")) == "TRUE"),
                "phase9_readiness_status": readiness,
                "blocking_reason": blocking,
                "notes": "Pack E currently identical to Pack D under Feature Freeze." if spec["level"] == "E" else "",
            }
        )
    return rows


def _summary_row(
    generated_ts: str,
    run_id: str,
    definition_rows: Sequence[Dict[str, Any]],
    item_rows: Sequence[Dict[str, Any]],
    readiness_rows: Sequence[Dict[str, Any]],
    warnings: Sequence[str],
) -> Dict[str, Any]:
    included = [row for row in item_rows if _upper(row.get("include_in_level")) == "TRUE"]
    unique_included_fields = {
        (_norm(row.get("candidate_family")).lower(), _norm(row.get("candidate_field")))
        for row in included
    }
    eligible_field_count = len(unique_included_fields)
    ineligible_field_count = len({
        (_norm(row.get("candidate_family")).lower(), _norm(row.get("candidate_field")))
        for row in item_rows
        if _upper(row.get("early_pack_level_eligible")) != "TRUE"
    })
    ready = sum(1 for row in readiness_rows if _norm(row.get("phase9_readiness_status")) == "READY_FOR_PHASE9_DESIGN")
    ready_warn = sum(1 for row in readiness_rows if _norm(row.get("phase9_readiness_status")) == "READY_FOR_PHASE9_DESIGN_WITH_WARNINGS")
    blocked = sum(1 for row in readiness_rows if _norm(row.get("phase9_readiness_status")) == "BLOCKED")
    placeholder = sum(1 for row in readiness_rows if _norm(row.get("phase9_readiness_status")) == "PLACEHOLDER_ONLY")
    safety = {
        "new_deterministic_field_count": 0,
        "fed_expectations_included_count": sum(1 for row in included if _norm(row.get("candidate_family")).lower() == "fed_expectations"),
        "upcoming_event_risk_label_included_count": sum(1 for row in included if _norm(row.get("candidate_field")) == "UPCOMING_EVENT_RISK_LABEL"),
        "lane_b_included_count": sum(1 for row in included if _norm(row.get("lane_assignment")) == "LANE_B_PROVISIONAL_CANDIDATE"),
        "lane_c_included_count": sum(1 for row in included if _norm(row.get("lane_assignment")) == "LANE_C_PROVIDER_INTERPRETATION"),
        "provider_visible_count": sum(1 for row in item_rows if _upper(row.get("provider_visible_in_this_phase")) == "TRUE"),
        "used_in_forecast_count": sum(1 for row in item_rows if _upper(row.get("used_in_forecast_in_this_phase")) == "TRUE"),
        "market_state_pack_write_count": 0,
        "provider_prompt_change_count": 0,
        "phase9_sheet_write_count": 0,
        "v1_sheet_write_count": 0,
        "production_behavior_change_count": 0,
    }
    if any(safety.values()):
        build_status = "FAIL"
        interpretation = "PACK_LEVEL_DESIGN_BLOCKED"
    elif blocked:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "PACK_LEVEL_DESIGN_NEEDS_REVIEW"
    elif ready_warn or warnings:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "PACK_LEVEL_DESIGN_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        interpretation = "PACK_LEVEL_DESIGN_READY"
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "pack_design_version": PACK_DESIGN_VERSION,
        "pack_design_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": interpretation,
        "pack_levels_defined": len(definition_rows),
        "pack_levels_ready": ready,
        "pack_levels_with_warnings": ready_warn,
        "pack_levels_blocked": blocked,
        "placeholder_levels": placeholder,
        "total_level_item_rows": len(item_rows),
        "eligible_field_count": eligible_field_count,
        "ineligible_field_count": ineligible_field_count,
        "feature_freeze_active": "TRUE",
        **safety,
        "notes": _truncate_text(json.dumps({"warnings": list(warnings)}, ensure_ascii=True), 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("MARKET_STATE_PACK_LEVEL_DEFINITION", OUTPUT_DEFINITION_SHEET, "market_state_pack_level_definition"),
        ("MARKET_STATE_PACK_LEVEL_ITEMS", OUTPUT_ITEMS_SHEET, "market_state_pack_level_items"),
        ("MARKET_STATE_PACK_LEVEL_SUMMARY", OUTPUT_SUMMARY_SHEET, "market_state_pack_level_summary"),
        ("MARKET_STATE_PACK_LEVEL_READINESS_AUDIT", OUTPUT_READINESS_SHEET, "market_state_pack_level_readiness_audit"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
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
            "notes": "Phase 8C design-only sheet; not provider-visible and not used in forecasts.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 8C pack level design.")
    return parser.parse_args(argv)


def build_market_state_pack_level_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    run_id = _design_run_id(generated_ts)
    creds = load_credentials()
    service = build_sheets_service(creds)
    titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing: List[str] = []
    warnings: List[str] = []

    shadow_summary = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_SHADOW_SUMMARY_SHEET, missing)
    latest_shadow_run_id = _latest_run_id(shadow_summary)
    shadow_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_SHADOW_SHEET, missing)
    item_audit_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_ITEM_AUDIT_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_COVERAGE_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_MAPPING_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_SEMANTICS_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_CANDIDATES_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_INFO_HISTORY_SHEET, missing)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_ATTENTION_HISTORY_SHEET, missing)
    for sheet in OPTIONAL_INPUT_SHEETS:
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, warnings)

    shadow_rows = [row for row in shadow_rows_all if _norm(row.get("shadow_pack_run_id")) == latest_shadow_run_id] if latest_shadow_run_id else []
    if not shadow_rows:
        warnings.append("Market_State_Pack_Shadow is missing or empty for the latest shadow run.")

    eligible_by_field = _eligible_fields(shadow_rows)
    specs = _level_specs()
    definition_rows = _definition_rows(generated_ts, run_id, specs, eligible_by_field)
    item_rows = _item_rows(generated_ts, run_id, specs, eligible_by_field)
    readiness_rows = _readiness_rows(generated_ts, run_id, specs, item_rows)
    summary = _summary_row(generated_ts, run_id, definition_rows, item_rows, readiness_rows, sorted(set(warnings + missing)))
    if not shadow_rows:
        summary["build_status"] = "FAIL"
        summary["final_interpretation"] = "PACK_LEVEL_DESIGN_BLOCKED"

    definition_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DEFINITION_SHEET, DEFINITION_HEADERS)
    item_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEMS_SHEET, ITEM_HEADERS)
    readiness_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_READINESS_SHEET, READINESS_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DEFINITION_SHEET, definition_headers, definition_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_ITEMS_SHEET, item_headers, item_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_READINESS_SHEET, readiness_headers, readiness_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary])
    registry = _upsert_registry_rows(service)

    return {
        "pack_design_run_id": run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "sheets_written": {
            OUTPUT_DEFINITION_SHEET: len(definition_rows),
            OUTPUT_ITEMS_SHEET: len(item_rows),
            OUTPUT_READINESS_SHEET: len(readiness_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "pack_levels_defined": summary["pack_levels_defined"],
        "pack_levels_ready": summary["pack_levels_ready"],
        "pack_levels_with_warnings": summary["pack_levels_with_warnings"],
        "pack_levels_blocked": summary["pack_levels_blocked"],
        "placeholder_levels": summary["placeholder_levels"],
        "eligible_field_count": summary["eligible_field_count"],
        "ineligible_field_count": summary["ineligible_field_count"],
        "feature_freeze_active": summary["feature_freeze_active"],
        "new_deterministic_field_count": summary["new_deterministic_field_count"],
        "fed_expectations_included_count": summary["fed_expectations_included_count"],
        "upcoming_event_risk_label_included_count": summary["upcoming_event_risk_label_included_count"],
        "lane_b_included_count": summary["lane_b_included_count"],
        "lane_c_included_count": summary["lane_c_included_count"],
        "provider_visible_count": summary["provider_visible_count"],
        "used_in_forecast_count": summary["used_in_forecast_count"],
        "market_state_pack_write_count": summary["market_state_pack_write_count"],
        "provider_prompt_change_count": summary["provider_prompt_change_count"],
        "phase9_sheet_write_count": summary["phase9_sheet_write_count"],
        "v1_sheet_write_count": summary["v1_sheet_write_count"],
        "production_behavior_change_count": summary["production_behavior_change_count"],
        "registry": registry,
        "warnings": sorted(set(warnings + missing)),
        "summary": summary,
    }


def main() -> None:
    result = build_market_state_pack_level_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
