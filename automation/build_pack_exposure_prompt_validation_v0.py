import argparse
import hashlib
import json
import math
import sys
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
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


INPUT_PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
INPUT_OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
INPUT_GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
INPUT_COMPARISON_SHEET = "Pack_Exposure_Comparison_Design"
INPUT_PROMPT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Design_Summary"
INPUT_LEVEL_DEFINITION_SHEET = "Market_State_Pack_Level_Definition"
INPUT_LEVEL_ITEMS_SHEET = "Market_State_Pack_Level_Items"
INPUT_LEVEL_READINESS_SHEET = "Market_State_Pack_Level_Readiness_Audit"
INPUT_LEVEL_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
INPUT_SHADOW_SHEET = "Market_State_Pack_Shadow"
INPUT_ITEM_AUDIT_SHEET = "Market_State_Pack_Item_Audit"
INPUT_COVERAGE_SHEET = "Market_State_Pack_Coverage_Audit"
INPUT_SHADOW_SUMMARY_SHEET = "Market_State_Pack_Shadow_Summary"
DIAGNOSTICS_CONTEXT_SHEETS = [
    "Market_Sessions",
    "Market_Session_Members",
    "Session_Attention_Map_History",
    "Session_Information_Requests_History",
]
OPTIONAL_DIAGNOSTICS_SHEETS = [
    "Session_Forecasts",
    "Session_Evaluation",
    "Session_vs_Event_Baseline_Compare",
    "Market_State_Source_Mapping",
    "Market_State_Source_Semantics",
]
MAIN_CONTEXT_SHEETS = ["Event", "Config"]

OUTPUT_DRY_RUN_SHEET = "Pack_Exposure_Prompt_Dry_Run"
OUTPUT_VALIDATION_AUDIT_SHEET = "Pack_Exposure_Prompt_Validation_Audit"
OUTPUT_FIELD_AUDIT_SHEET = "Pack_Exposure_Field_Exposure_Audit"
OUTPUT_GUARDRAIL_VALIDATION_SHEET = "Pack_Exposure_Guardrail_Validation"
OUTPUT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Validation_Summary"

SCHEMA_VERSION = "presignal_v2_pack_exposure_prompt_validation_0.1"
PROMPT_VALIDATION_VERSION = "pack_exposure_prompt_validation_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PACK_EXPOSURE_PROMPT_VALIDATION"
REGISTRY_OWNER_MODULE = "market_state"

ACTIVE_PACK_LEVELS = ["A", "B", "C", "D", "E"]
PACK_Q_LEVEL = "Q"
PACK_NAME_TO_LEVEL = {
    "NO_PACK": "A",
    "TARGET_STATE_ONLY": "B",
    "TARGET_PLUS_CALENDAR": "C",
    "RATES_DOLLAR_CONTEXT": "D",
    "FULL_APPROVED_DETERMINISTIC_PACK": "E",
    "PROVISIONAL_QUALITATIVE_OVERLAY": "Q",
}
EXPECTED_FIELDS_BY_LEVEL = {
    "A": [],
    "B": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
    ],
    "C": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
        "NEXT_CPI_OR_FOMC_WITHIN_72H",
        "NEXT_NFP_WITHIN_7D",
        "EVENT_CLUSTER_DENSITY_NEXT_24H",
    ],
    "D": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
        "NEXT_CPI_OR_FOMC_WITHIN_72H",
        "NEXT_NFP_WITHIN_7D",
        "EVENT_CLUSTER_DENSITY_NEXT_24H",
        "US2Y_YIELD_LEVEL",
        "US10Y_YIELD_LEVEL",
        "US2Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_MINUS_US2Y_CURVE",
        "DXY_LEVEL",
        "DXY_CHANGE_PRESESSION",
        "DXY_DIRECTION_LABEL",
        "USD_INDEX_PROXY_LEVEL",
        "USD_INDEX_PROXY_CHANGE",
    ],
    "E": [
        "USDJPY_RETURN_1H_PRESESSION",
        "USDJPY_RETURN_4H_PRESESSION",
        "USDJPY_RETURN_24H_PRESESSION",
        "USDJPY_TREND_LABEL",
        "USDJPY_REALIZED_VOL_1H_PRESESSION",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
        "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
        "NEXT_CPI_OR_FOMC_WITHIN_72H",
        "NEXT_NFP_WITHIN_7D",
        "EVENT_CLUSTER_DENSITY_NEXT_24H",
        "US2Y_YIELD_LEVEL",
        "US10Y_YIELD_LEVEL",
        "US2Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_CHANGE_FROM_PRIOR_CLOSE",
        "US10Y_MINUS_US2Y_CURVE",
        "DXY_LEVEL",
        "DXY_CHANGE_PRESESSION",
        "DXY_DIRECTION_LABEL",
        "USD_INDEX_PROXY_LEVEL",
        "USD_INDEX_PROXY_CHANGE",
    ],
}
FORBIDDEN_FIELD_TERMS = [
    "fed_expectations",
    "FED_EXPECTATION_PROXY_FROM_US2Y",
    "UPCOMING_EVENT_RISK_LABEL",
    "risk_sentiment",
    "equity_tone",
    "volatility",
    "inflation_narrative",
    "labor_market_trend",
    "market_positioning",
    "jpy_intervention_risk",
    "historical_surprise_sensitivity",
    "growth_context",
    "event_consensus_detail",
]
FORBIDDEN_INTERPRETIVE_TERMS = [
    "bad-news-is-good-news",
    "risk-on",
    "risk-off",
    "Fed-path session",
    "growth-scare session",
    "market likely to fade",
    "USD reaction asymmetry",
]
FORBIDDEN_INSTRUCTION_TERMS = [
    "browse the web",
    "use external information",
    "use current market data",
    "improve accuracy",
    "this pack should improve your forecast",
    "historically this field helps",
]
REQUIRED_GUARDRAILS = {
    "NO_EXTERNAL_BROWSING",
    "NO_OTHER_PACK_LEVELS",
    "NO_EXCLUDED_FIELDS",
    "NO_FED_EXPECTATIONS",
    "NO_UPCOMING_EVENT_RISK_LABEL",
    "NO_ACCURACY_COACHING",
    "DXY_PROXY_SEPARATION",
    "WARNING_METADATA_PRESERVED",
    "USE_ONLY_ASSIGNED_CONTEXT",
    "NO_PROVIDER_VISIBLE_THIS_PHASE",
}

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_validation_version",
    "prompt_validation_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "model",
    "pack_level",
    "pack_level_name",
    "dry_run_status",
    "prompt_design_row_found",
    "market_session_context_built",
    "market_state_context_built",
    "output_schema_attached",
    "guardrails_attached",
    "assembled_prompt_text",
    "assembled_prompt_hash",
    "prompt_token_estimate",
    "allowed_pack_fields",
    "actual_pack_fields_in_prompt",
    "excluded_pack_fields_detected",
    "forbidden_terms_detected",
    "forbidden_content_appears_in_guardrail_only",
    "warning_metadata_included",
    "missing_field_metadata_included",
    "dxy_proxy_separation_text_present",
    "external_browsing_prohibition_present",
    "accuracy_coaching_detected",
    "provider_visible_in_this_phase",
    "used_in_forecast_in_this_phase",
    "provider_call_made",
    "forecast_output_created",
    "pack_e_identical_to_pack_d",
    "notes",
]

FIELD_AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_validation_version",
    "prompt_validation_run_id",
    "session_id",
    "provider",
    "pack_level",
    "pack_level_name",
    "candidate_family",
    "candidate_field",
    "field_expected_for_level",
    "field_present_in_prompt",
    "field_value_present",
    "field_metadata_present",
    "lane_assignment",
    "early_pack_level_eligible",
    "phase9_allowed",
    "exposure_status",
    "exclusion_reason",
    "notes",
]

GUARDRAIL_VALIDATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_validation_version",
    "prompt_validation_run_id",
    "session_id",
    "provider",
    "pack_level",
    "pack_level_name",
    "guardrail_name",
    "guardrail_category",
    "guardrail_expected",
    "guardrail_present",
    "guardrail_text_present",
    "blocking_if_violated",
    "validation_status",
    "violation_details",
    "notes",
]

VALIDATION_AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_validation_version",
    "prompt_validation_run_id",
    "session_id",
    "provider",
    "pack_level",
    "pack_level_name",
    "dry_run_status",
    "field_exposure_status",
    "guardrail_status",
    "schema_status",
    "warning_metadata_status",
    "dxy_proxy_status",
    "external_browsing_status",
    "accuracy_coaching_status",
    "pack_q_status",
    "fed_expectations_status",
    "upcoming_event_risk_label_status",
    "lane_b_status",
    "lane_c_status",
    "provider_call_status",
    "forecast_output_status",
    "prompt_hash",
    "forbidden_content_appears_in_guardrail_only",
    "pack_e_identical_to_pack_d",
    "blocking_issue_count",
    "warning_count",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_validation_version",
    "prompt_validation_run_id",
    "build_status",
    "final_interpretation",
    "dry_run_rows_written",
    "field_exposure_rows_written",
    "guardrail_validation_rows_written",
    "validation_audit_rows_written",
    "sessions_validated",
    "providers_validated",
    "pack_levels_validated",
    "prompt_design_rows_checked",
    "prompts_passed",
    "prompts_passed_with_warnings",
    "prompts_needing_review",
    "prompts_failed",
    "blocked_field_present_count",
    "unexpected_field_present_count",
    "expected_field_missing_count",
    "missing_guardrail_count",
    "schema_error_count",
    "warning_metadata_missing_count",
    "dxy_proxy_separation_missing_count",
    "external_browsing_allowed_count",
    "accuracy_coaching_detected_count",
    "pack_q_included_count",
    "fed_expectations_included_count",
    "upcoming_event_risk_label_included_count",
    "lane_b_included_count",
    "lane_c_included_count",
    "provider_visible_count",
    "used_in_forecast_count",
    "provider_call_count",
    "forecast_output_count",
    "market_state_pack_write_count",
    "phase9_forecast_sheet_write_count",
    "v1_sheet_write_count",
    "production_behavior_change_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _safe_int(value: Any) -> int:
    try:
        raw = _norm(value)
        return int(float(raw)) if raw else 0
    except Exception:
        return 0


def _prompt_validation_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_exposure_prompt_validation_v0_{stamp}"


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


def _latest_run_id(rows: Sequence[Dict[str, Any]], key: str) -> str:
    if not rows:
        return ""
    return _norm(rows[-1].get(key))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _token_estimate(text: str) -> int:
    return int(math.ceil(len(text) / 4.0)) if text else 0


def _preview_text(text: str, limit: int = 3500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[prompt preview truncated in dry-run sheet]..."


def _split_pipe(value: Any) -> List[str]:
    raw = _norm(value)
    if not raw:
        return []
    return [part for part in raw.split("|") if part]


def _normalize_required_fields(schema_rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [_norm(row.get("field_name")) for row in schema_rows if _as_bool(row.get("required"))]


def _group_prompt_rows(rows: Sequence[Dict[str, Any]], latest_run_id: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        if latest_run_id and _norm(row.get("prompt_design_run_id")) != latest_run_id:
            continue
        level = _norm(row.get("pack_level"))
        provider = _norm(row.get("provider"))
        if level and provider:
            out[(level, provider)] = row
    return out


def _filter_by_run(rows: Sequence[Dict[str, Any]], key: str, run_id: str) -> List[Dict[str, Any]]:
    if not run_id:
        return list(rows)
    return [row for row in rows if _norm(row.get(key)) == run_id]


def _build_level_field_meta(level_item_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    out: Dict[str, Dict[str, Dict[str, Any]]] = {level: {} for level in ACTIVE_PACK_LEVELS}
    for row in level_item_rows:
        level = _norm(row.get("pack_level"))
        field = _norm(row.get("candidate_field"))
        if level in out and field:
            out[level][field] = row
    return out


def _all_field_meta(level_item_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in level_item_rows:
        field = _norm(row.get("candidate_field"))
        if field and field not in out:
            out[field] = row
    return out


def _shadow_index(shadow_rows: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Dict[str, Any]]]]:
    session_meta: Dict[str, Dict[str, Any]] = {}
    field_rows: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in shadow_rows:
        session_id = _norm(row.get("session_id"))
        field = _norm(row.get("candidate_field"))
        if not session_id or not field:
            continue
        session_meta.setdefault(
            session_id,
            {
                "session_id": session_id,
                "session_date": _norm(row.get("session_date")),
                "country": _norm(row.get("country")),
                "session_window_name": _norm(row.get("session_window_name")),
                "forecast_timestamp": _norm(row.get("forecast_timestamp")),
            },
        )
        field_rows[session_id][field] = row
    return session_meta, field_rows


def _event_index(event_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("event_id")): row for row in event_rows if _norm(row.get("event_id"))}


def _attention_history_index(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        session_id = _norm(row.get("session_id")) or _norm(row.get("active_session_id"))
        event_id = _norm(row.get("event_id"))
        if session_id and event_id and event_id not in out[session_id]:
            out[session_id][event_id] = row
    return {session_id: list(events.values()) for session_id, events in out.items()}


def _member_index(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        session_id = _norm(row.get("session_id"))
        if session_id:
            out[session_id].append(row)
    return out


def _build_event_context(
    session_id: str,
    session_meta: Dict[str, Any],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    attention_by_session: Dict[str, List[Dict[str, Any]]],
    event_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool, List[str]]:
    notes: List[str] = []
    events: List[Dict[str, Any]] = []
    member_rows = sorted(members_by_session.get(session_id, []), key=lambda row: (_norm(row.get("release_ts")), _safe_int(row.get("member_order"))))
    if member_rows:
        for row in member_rows:
            event_id = _norm(row.get("event_id"))
            event_ref = event_by_id.get(event_id, {})
            events.append(
                {
                    "event_id": event_id,
                    "indicator_name": _norm(row.get("indicator_name")) or _norm(event_ref.get("indicator_name")),
                    "release_ts": _norm(row.get("release_ts")) or _norm(event_ref.get("release_ts")),
                    "importance": _norm(row.get("importance")) or _norm(event_ref.get("importance")),
                    "consensus_value": _norm(row.get("consensus_value")) or _norm(event_ref.get("consensus_value")),
                    "previous_value": _norm(row.get("prev_revision")) or _norm(event_ref.get("prev_revision")),
                    "revision_info_if_available": _norm(row.get("prev_revision")) or _norm(event_ref.get("prev_revision")),
                }
            )
        notes.append("event_context_source=market_session_members")
    else:
        attention_rows = sorted(attention_by_session.get(session_id, []), key=lambda row: (_norm(row.get("release_ts")), _safe_int(row.get("member_order"))))
        for row in attention_rows:
            event_id = _norm(row.get("event_id"))
            event_ref = event_by_id.get(event_id, {})
            events.append(
                {
                    "event_id": event_id,
                    "indicator_name": _norm(row.get("indicator_name")) or _norm(event_ref.get("indicator_name")),
                    "release_ts": _norm(row.get("release_ts")) or _norm(event_ref.get("release_ts")),
                    "importance": _norm(row.get("importance")) or _norm(event_ref.get("importance")),
                    "consensus_value": _norm(event_ref.get("consensus_value")),
                    "previous_value": _norm(event_ref.get("prev_revision")),
                    "revision_info_if_available": _norm(event_ref.get("prev_revision")),
                }
            )
        if events:
            notes.append("event_context_source=session_attention_history")
        else:
            notes.append("event_context_source=session_metadata_only")
            notes.append("event_list_missing_for_session")
    payload = {
        "session": {
            "session_id": session_id,
            "session_date": session_meta.get("session_date", ""),
            "country": session_meta.get("country", ""),
            "session_window_name": session_meta.get("session_window_name", ""),
            "session_start_ts": session_meta.get("forecast_timestamp", ""),
            "session_end_ts": session_meta.get("forecast_timestamp", ""),
            "member_event_count": len(events),
        },
        "events": events,
    }
    return payload, True, notes


def _build_market_state_context(
    level: str,
    allowed_fields: Sequence[str],
    session_field_rows: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    fields_payload: List[Dict[str, Any]] = []
    if level == "A":
        return (
            {"assigned_market_state_context": [], "instruction": "No Market-State Context is assigned for this run."},
            [],
            ["pack_level_a_no_market_state_fields"],
        )
    for field in allowed_fields:
        row = session_field_rows.get(field, {})
        entry = {
            "field_name": field,
            "field_value": _norm(row.get("field_value")),
            "field_unit": _norm(row.get("field_unit")),
            "as_of_timestamp": _norm(row.get("as_of_timestamp")),
            "source_observation_ts": _norm(row.get("source_observation_ts")),
            "source_publication_ts": _norm(row.get("source_publication_ts")),
            "warning_label": _norm(row.get("warning_label")),
            "missing_reason": _norm(row.get("missing_reason")),
            "backtest_safe": _norm(row.get("backtest_safe")),
            "data_available_flag": _norm(row.get("data_available_flag")),
        }
        fields_payload.append(entry)
    if any(field.startswith("DXY_") for field in allowed_fields) or "USD_INDEX_PROXY_LEVEL" in allowed_fields:
        notes.append("dxy_proxy_context_included")
    return (
        {
            "assigned_market_state_context": fields_payload,
            "instruction": "Use only these assigned fields. Missing fields must not be fabricated.",
            "dxy_proxy_note": "DXY and USD_INDEX_PROXY are not equivalent. Do not treat USD_INDEX_PROXY as actual DXY."
            if any(field in {"DXY_LEVEL", "DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL", "USD_INDEX_PROXY_LEVEL", "USD_INDEX_PROXY_CHANGE"} for field in allowed_fields)
            else "",
        },
        fields_payload,
        notes,
    )


def _schema_payload(schema_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "field_name": _norm(row.get("field_name")),
            "field_type": _norm(row.get("field_type")),
            "required": _norm(row.get("required")),
            "allowed_values": _norm(row.get("allowed_values")),
            "description": _norm(row.get("description")),
        }
        for row in schema_rows
    ]


def _guardrail_payload(guardrail_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "guardrail_name": _norm(row.get("guardrail_name")),
            "guardrail_text": _norm(row.get("guardrail_text")),
            "blocking_if_violated": _norm(row.get("blocking_if_violated")),
        }
        for row in guardrail_rows
    ]


def _assemble_prompt_text(
    design_row: Dict[str, Any],
    event_context: Dict[str, Any],
    market_state_context: Dict[str, Any],
    schema_payload: Sequence[Dict[str, Any]],
    guardrail_payload: Sequence[Dict[str, Any]],
) -> Tuple[str, str]:
    system_text = _norm(design_row.get("system_prompt_template"))
    user_text = _norm(design_row.get("user_prompt_template"))
    market_text = json.dumps(market_state_context, ensure_ascii=True)
    event_text = json.dumps(event_context, ensure_ascii=True)
    schema_text = json.dumps({"required_json_output_schema": list(schema_payload)}, ensure_ascii=True)
    guardrail_text = json.dumps({"guardrails": list(guardrail_payload)}, ensure_ascii=True)
    core_prompt = "\n\n".join(
        [
            "SYSTEM INSTRUCTIONS",
            system_text,
            "USER TASK",
            user_text,
            "MARKET SESSION CONTEXT",
            event_text,
            "ASSIGNED MARKET-STATE CONTEXT",
            market_text,
            "REQUIRED JSON OUTPUT SCHEMA",
            schema_text,
        ]
    )
    full_prompt = core_prompt + "\n\nGUARDRAILS\n" + guardrail_text
    return core_prompt, full_prompt


def _detect_terms(text: str, terms: Iterable[str]) -> List[str]:
    lowered = text.lower()
    found: List[str] = []
    for term in terms:
        if term.lower() in lowered:
            found.append(term)
    return sorted(set(found))


def _expected_schema_status(schema_rows: Sequence[Dict[str, Any]], full_prompt: str) -> Tuple[str, List[str]]:
    required_fields = _normalize_required_fields(schema_rows)
    missing = [field for field in required_fields if f"\"field_name\": \"{field}\"" not in full_prompt]
    if "\"allowed_values\": \"up|down|flat|no_clear_direction\"" not in full_prompt:
        missing.append("forecast_direction_allowed_values")
    if missing:
        return "FAIL", missing
    return "PASS", []


def _guardrail_validation_status(
    level: str,
    guardrail_rows: Sequence[Dict[str, Any]],
    guardrail_text: str,
    core_text: str,
) -> Tuple[List[Dict[str, Any]], str, int]:
    rows: List[Dict[str, Any]] = []
    missing_blocking = 0
    overall = "PASS"
    for row in guardrail_rows:
        name = _norm(row.get("guardrail_name"))
        text = _norm(row.get("guardrail_text"))
        expected = name in REQUIRED_GUARDRAILS and level in ACTIVE_PACK_LEVELS
        text_present = text in guardrail_text if text else False
        name_present = name in guardrail_text
        present = text_present or name_present
        blocking = _as_bool(row.get("blocking_if_violated"))
        status = "PASS"
        details = ""
        if expected and not present:
            status = "FAIL" if blocking else "PASS_WITH_WARNINGS"
            details = "guardrail text missing from assembled guardrail section"
            if blocking:
                missing_blocking += 1
                overall = "FAIL"
            elif overall != "FAIL":
                overall = "PASS_WITH_WARNINGS"
        elif name == "NO_OTHER_PACK_LEVELS":
            if any(f"Pack {other}" in core_text for other in ACTIVE_PACK_LEVELS if other != level):
                status = "FAIL"
                details = "assembled core prompt mentions another pack level"
                missing_blocking += 1
                overall = "FAIL"
        rows.append(
            {
                "guardrail_name": name,
                "guardrail_category": _norm(row.get("guardrail_category")),
                "guardrail_expected": "TRUE" if expected else "FALSE",
                "guardrail_present": "TRUE" if present else "FALSE",
                "guardrail_text_present": "TRUE" if text_present else "FALSE",
                "blocking_if_violated": _norm(row.get("blocking_if_violated")),
                "validation_status": status,
                "violation_details": details,
            }
        )
    return rows, overall, missing_blocking


def _exposure_status(expected: bool, present: bool, blocked: bool) -> str:
    if blocked and present:
        return "BLOCKED_FIELD_PRESENT"
    if expected and present:
        return "EXPECTED_AND_PRESENT"
    if expected and not present:
        return "EXPECTED_BUT_MISSING"
    if not expected and present:
        return "NOT_EXPECTED_BUT_PRESENT"
    return "NOT_EXPECTED_AND_ABSENT"


def _build_registry_updates(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_EXPOSURE_PROMPT_DRY_RUN", OUTPUT_DRY_RUN_SHEET, "pack_exposure_prompt_dry_run"),
        ("PACK_EXPOSURE_PROMPT_VALIDATION_AUDIT", OUTPUT_VALIDATION_AUDIT_SHEET, "pack_exposure_prompt_validation_audit"),
        ("PACK_EXPOSURE_FIELD_EXPOSURE_AUDIT", OUTPUT_FIELD_AUDIT_SHEET, "pack_exposure_field_exposure_audit"),
        ("PACK_EXPOSURE_GUARDRAIL_VALIDATION", OUTPUT_GUARDRAIL_VALIDATION_SHEET, "pack_exposure_guardrail_validation"),
        ("PACK_EXPOSURE_PROMPT_VALIDATION_SUMMARY", OUTPUT_SUMMARY_SHEET, "pack_exposure_prompt_validation_summary"),
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
            "notes": "Phase 9A-1 dry-run validation only; no provider calls and no forecasts.",
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


def _blocked_summary(generated_ts: str, run_id: str, missing_required: Sequence[str]) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "prompt_validation_version": PROMPT_VALIDATION_VERSION,
        "prompt_validation_run_id": run_id,
        "build_status": "FAIL",
        "final_interpretation": "PACK_EXPOSURE_PROMPT_VALIDATION_BLOCKED",
        "dry_run_rows_written": 0,
        "field_exposure_rows_written": 0,
        "guardrail_validation_rows_written": 0,
        "validation_audit_rows_written": 0,
        "sessions_validated": 0,
        "providers_validated": 0,
        "pack_levels_validated": 0,
        "prompt_design_rows_checked": 0,
        "prompts_passed": 0,
        "prompts_passed_with_warnings": 0,
        "prompts_needing_review": 0,
        "prompts_failed": 0,
        "blocked_field_present_count": 0,
        "unexpected_field_present_count": 0,
        "expected_field_missing_count": 0,
        "missing_guardrail_count": 0,
        "schema_error_count": 0,
        "warning_metadata_missing_count": 0,
        "dxy_proxy_separation_missing_count": 0,
        "external_browsing_allowed_count": 0,
        "accuracy_coaching_detected_count": 0,
        "pack_q_included_count": 0,
        "fed_expectations_included_count": 0,
        "upcoming_event_risk_label_included_count": 0,
        "lane_b_included_count": 0,
        "lane_c_included_count": 0,
        "provider_visible_count": 0,
        "used_in_forecast_count": 0,
        "provider_call_count": 0,
        "forecast_output_count": 0,
        "market_state_pack_write_count": 0,
        "phase9_forecast_sheet_write_count": 0,
        "v1_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "notes": _truncate_text(json.dumps({"missing_required": list(missing_required)}, ensure_ascii=True), 500),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-1 pack exposure prompt validation dry run.")
    return parser.parse_args(argv)


def build_pack_exposure_prompt_validation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    run_id = _prompt_validation_run_id(generated_ts)

    creds = load_credentials()
    service = build_sheets_service(creds)
    diagnostics_titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(service, MAIN_SPREADSHEET_ID)

    missing_required: List[str] = []
    warnings: List[str] = []

    prompt_summary_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_SUMMARY_SHEET, missing_required)
    prompt_design_run_id = _latest_run_id(prompt_summary_rows, "prompt_design_run_id")
    prompt_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_DESIGN_SHEET, missing_required)
    output_schema_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_OUTPUT_SCHEMA_SHEET, missing_required)
    guardrail_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_GUARDRAILS_SHEET, missing_required)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_COMPARISON_SHEET, warnings)

    level_summary_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_SUMMARY_SHEET, missing_required)
    pack_design_run_id = _latest_run_id(level_summary_rows, "pack_design_run_id")
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_DEFINITION_SHEET, missing_required)
    level_item_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_ITEMS_SHEET, missing_required)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_READINESS_SHEET, missing_required)

    shadow_summary_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SUMMARY_SHEET, missing_required)
    shadow_run_id = _latest_run_id(shadow_summary_rows, "shadow_pack_run_id")
    shadow_rows_all = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SHEET, missing_required)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_ITEM_AUDIT_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_COVERAGE_SHEET, warnings)

    diagnostics_context: Dict[str, List[Dict[str, Any]]] = {}
    for sheet in DIAGNOSTICS_CONTEXT_SHEETS:
        diagnostics_context[sheet] = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet, warnings)
    for sheet in OPTIONAL_DIAGNOSTICS_SHEETS:
        diagnostics_context[sheet] = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet, warnings)

    main_context: Dict[str, List[Dict[str, Any]]] = {}
    for sheet in MAIN_CONTEXT_SHEETS:
        main_context[sheet] = _read_optional_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, warnings)

    prompt_rows_filtered = _filter_by_run(prompt_rows_all, "prompt_design_run_id", prompt_design_run_id)
    schema_rows_filtered = _filter_by_run(output_schema_rows_all, "prompt_design_run_id", prompt_design_run_id)
    guardrail_rows_filtered = _filter_by_run(guardrail_rows_all, "prompt_design_run_id", prompt_design_run_id)
    level_item_rows_filtered = _filter_by_run(level_item_rows_all, "pack_design_run_id", pack_design_run_id)
    shadow_rows_filtered = _filter_by_run(shadow_rows_all, "shadow_pack_run_id", shadow_run_id)

    if not prompt_rows_filtered or not schema_rows_filtered or not guardrail_rows_filtered or not level_item_rows_filtered or not shadow_rows_filtered:
        dry_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DRY_RUN_SHEET, DRY_RUN_HEADERS)
        validation_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_AUDIT_SHEET, VALIDATION_AUDIT_HEADERS)
        field_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FIELD_AUDIT_SHEET, FIELD_AUDIT_HEADERS)
        guardrail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAIL_VALIDATION_SHEET, GUARDRAIL_VALIDATION_HEADERS)
        summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DRY_RUN_SHEET, dry_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_AUDIT_SHEET, validation_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FIELD_AUDIT_SHEET, field_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAIL_VALIDATION_SHEET, guardrail_headers, [])
        summary = _blocked_summary(generated_ts, run_id, sorted(set(missing_required + ["required_phase9a0_or_phase8c_input_empty"])))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary])
        registry = _build_registry_updates(service)
        return {
            "prompt_validation_run_id": run_id,
            "build_status": summary["build_status"],
            "final_interpretation": summary["final_interpretation"],
            "sheets_written": {
                OUTPUT_DRY_RUN_SHEET: 0,
                OUTPUT_VALIDATION_AUDIT_SHEET: 0,
                OUTPUT_FIELD_AUDIT_SHEET: 0,
                OUTPUT_GUARDRAIL_VALIDATION_SHEET: 0,
                OUTPUT_SUMMARY_SHEET: 1,
            },
            "registry": registry,
            "warnings": sorted(set(warnings)),
            "missing_required": sorted(set(missing_required)),
            "summary": summary,
        }

    prompt_rows_by_key = _group_prompt_rows(prompt_rows_filtered, prompt_design_run_id)
    level_field_meta = _build_level_field_meta(level_item_rows_filtered)
    all_field_meta = _all_field_meta(level_item_rows_filtered)
    session_meta_by_id, shadow_field_rows = _shadow_index(shadow_rows_filtered)
    event_by_id = _event_index(main_context.get("Event", []))
    attention_by_session = _attention_history_index(diagnostics_context.get("Session_Attention_Map_History", []))
    members_by_session = _member_index(diagnostics_context.get("Market_Session_Members", []))

    session_ids = sorted(session_meta_by_id)
    providers = sorted({_norm(row.get("provider")) for row in prompt_rows_filtered if _norm(row.get("provider"))})
    schema_payload = _schema_payload(schema_rows_filtered)
    required_schema_fields = _normalize_required_fields(schema_rows_filtered)
    guardrail_payload = _guardrail_payload(guardrail_rows_filtered)

    dry_run_rows: List[Dict[str, Any]] = []
    field_audit_rows: List[Dict[str, Any]] = []
    guardrail_validation_rows: List[Dict[str, Any]] = []
    validation_rows: List[Dict[str, Any]] = []

    pack_e_identical = EXPECTED_FIELDS_BY_LEVEL["D"] == EXPECTED_FIELDS_BY_LEVEL["E"]

    for session_id in session_ids:
        session_meta = session_meta_by_id[session_id]
        event_context, market_context_built, event_notes = _build_event_context(
            session_id,
            session_meta,
            members_by_session,
            attention_by_session,
            event_by_id,
        )
        session_field_map = shadow_field_rows.get(session_id, {})
        for provider in providers:
            for level in ACTIVE_PACK_LEVELS:
                design_row = prompt_rows_by_key.get((level, provider), {})
                level_meta = level_field_meta.get(level, {})
                pack_level_name = _norm(design_row.get("pack_level_name")) or _norm(PACK_NAME_TO_LEVEL.get(level, level))
                allowed_fields = _split_pipe(design_row.get("allowed_pack_fields")) or list(EXPECTED_FIELDS_BY_LEVEL[level])
                market_state_context, market_state_entries, market_state_notes = _build_market_state_context(level, allowed_fields, session_field_map)
                core_prompt_text, full_prompt_text = _assemble_prompt_text(
                    design_row,
                    event_context,
                    market_state_context,
                    schema_payload,
                    guardrail_payload,
                )
                guardrail_text = json.dumps({"guardrails": guardrail_payload}, ensure_ascii=True)
                actual_fields_in_prompt = [entry.get("field_name", "") for entry in market_state_entries if entry.get("field_name")]
                core_forbidden_terms = _detect_terms(core_prompt_text, FORBIDDEN_FIELD_TERMS + FORBIDDEN_INTERPRETIVE_TERMS + FORBIDDEN_INSTRUCTION_TERMS)
                guardrail_only_terms = [
                    term
                    for term in _detect_terms(guardrail_text, FORBIDDEN_FIELD_TERMS + FORBIDDEN_INTERPRETIVE_TERMS + FORBIDDEN_INSTRUCTION_TERMS)
                    if term not in core_forbidden_terms
                ]
                excluded_fields_detected = sorted(
                    field for field in actual_fields_in_prompt if field not in set(EXPECTED_FIELDS_BY_LEVEL[level])
                )
                schema_status, schema_issues = _expected_schema_status(schema_rows_filtered, full_prompt_text)
                guardrail_results, guardrail_status, missing_guardrails = _guardrail_validation_status(level, guardrail_rows_filtered, guardrail_text, core_prompt_text)

                warning_fields = [entry for entry in market_state_entries if _norm(entry.get("warning_label"))]
                missing_fields = [entry for entry in market_state_entries if _upper(entry.get("data_available_flag")) != "TRUE"]
                warning_metadata_included = "TRUE" if not warning_fields or all("warning_label" in entry for entry in warning_fields) else "FALSE"
                missing_field_metadata_included = "TRUE" if not missing_fields or all("missing_reason" in entry for entry in missing_fields) else "FALSE"

                dxy_required = level in {"D", "E"}
                dxy_phrase = "DXY and USD_INDEX_PROXY are not equivalent. Do not treat USD_INDEX_PROXY as actual DXY."
                dxy_present = dxy_phrase in core_prompt_text
                dxy_status = "PASS" if (not dxy_required or dxy_present) else "FAIL"

                external_browsing_present = "Do not browse." in core_prompt_text and "Do not use external market information." in core_prompt_text
                external_browsing_status = "PASS" if external_browsing_present else "FAIL"

                accuracy_coaching_detected = _detect_terms(core_prompt_text, FORBIDDEN_INSTRUCTION_TERMS)
                accuracy_coaching_status = "FAIL" if accuracy_coaching_detected else "PASS"

                field_statuses: List[str] = []
                expected_missing_count = 0
                blocked_present_count = 0
                unexpected_present_count = 0
                for field, meta_row in sorted(all_field_meta.items()):
                    expected = field in EXPECTED_FIELDS_BY_LEVEL[level]
                    present = field in actual_fields_in_prompt
                    blocked = field in {"UPCOMING_EVENT_RISK_LABEL", "fed_expectations", "FED_EXPECTATION_PROXY_FROM_US2Y"} or _norm(meta_row.get("lane_assignment")) in {
                        "LANE_B_PROVISIONAL_CANDIDATE",
                        "LANE_C_PROVIDER_INTERPRETATION",
                    }
                    exposure = _exposure_status(expected, present, blocked)
                    if exposure == "EXPECTED_BUT_MISSING":
                        expected_missing_count += 1
                    elif exposure == "BLOCKED_FIELD_PRESENT":
                        blocked_present_count += 1
                    elif exposure == "NOT_EXPECTED_BUT_PRESENT":
                        unexpected_present_count += 1
                    field_statuses.append(exposure)
                    field_entry = next((entry for entry in market_state_entries if entry.get("field_name") == field), None)
                    field_audit_rows.append(
                        {
                            "generated_ts": generated_ts,
                            "schema_version": SCHEMA_VERSION,
                            "prompt_validation_version": PROMPT_VALIDATION_VERSION,
                            "prompt_validation_run_id": run_id,
                            "session_id": session_id,
                            "provider": provider,
                            "pack_level": level,
                            "pack_level_name": pack_level_name,
                            "candidate_family": _norm(meta_row.get("candidate_family")),
                            "candidate_field": field,
                            "field_expected_for_level": "TRUE" if expected else "FALSE",
                            "field_present_in_prompt": "TRUE" if present else "FALSE",
                            "field_value_present": "TRUE" if field_entry and _upper(field_entry.get("data_available_flag")) == "TRUE" else "FALSE",
                            "field_metadata_present": "TRUE" if field_entry is not None else "FALSE",
                            "lane_assignment": _norm(meta_row.get("lane_assignment")),
                            "early_pack_level_eligible": _norm(meta_row.get("early_pack_level_eligible")),
                            "phase9_allowed": _norm(meta_row.get("phase9_allowed")),
                            "exposure_status": exposure,
                            "exclusion_reason": _norm(meta_row.get("exclusion_reason")) if not expected else "",
                            "notes": "blocked field should remain absent from active prompts" if blocked else "",
                        }
                    )

                if blocked_present_count or unexpected_present_count:
                    field_exposure_status = "FAIL"
                elif expected_missing_count:
                    field_exposure_status = "NEEDS_REVIEW"
                else:
                    field_exposure_status = "PASS"

                for guardrail_result in guardrail_results:
                    guardrail_validation_rows.append(
                        {
                            "generated_ts": generated_ts,
                            "schema_version": SCHEMA_VERSION,
                            "prompt_validation_version": PROMPT_VALIDATION_VERSION,
                            "prompt_validation_run_id": run_id,
                            "session_id": session_id,
                            "provider": provider,
                            "pack_level": level,
                            "pack_level_name": pack_level_name,
                            **guardrail_result,
                            "notes": "",
                        }
                    )

                prompt_design_found = bool(design_row)
                output_schema_attached = bool(schema_payload)
                guardrails_attached = bool(guardrail_payload)
                pack_q_status = "FAIL" if "Pack Q" in core_prompt_text else "PASS"
                fed_expectations_status = "FAIL" if any(term in core_forbidden_terms for term in ["fed_expectations", "FED_EXPECTATION_PROXY_FROM_US2Y"]) else "PASS"
                upcoming_event_risk_label_status = "FAIL" if "UPCOMING_EVENT_RISK_LABEL" in core_forbidden_terms else "PASS"
                lane_b_status = "FAIL" if any(term in core_forbidden_terms for term in ["Lane B provisional summaries", "UPCOMING_EVENT_RISK_LABEL"]) else "PASS"
                lane_c_status = "FAIL" if "Lane C interpretive labels" in core_forbidden_terms else "PASS"
                warning_metadata_status = "PASS" if warning_metadata_included == "TRUE" and missing_field_metadata_included == "TRUE" else "FAIL"
                provider_call_status = "PASS"
                forecast_output_status = "PASS"

                blocking_issue_count = 0
                warning_count = 0
                if not prompt_design_found:
                    blocking_issue_count += 1
                if field_exposure_status == "FAIL":
                    blocking_issue_count += 1
                elif field_exposure_status == "NEEDS_REVIEW":
                    warning_count += 1
                if guardrail_status == "FAIL":
                    blocking_issue_count += 1
                elif guardrail_status == "PASS_WITH_WARNINGS":
                    warning_count += 1
                if schema_status == "FAIL":
                    blocking_issue_count += 1
                if warning_metadata_status == "FAIL":
                    blocking_issue_count += 1
                if dxy_status == "FAIL":
                    blocking_issue_count += 1
                if external_browsing_status == "FAIL":
                    blocking_issue_count += 1
                if accuracy_coaching_status == "FAIL":
                    blocking_issue_count += 1
                if pack_q_status == "FAIL" or fed_expectations_status == "FAIL" or upcoming_event_risk_label_status == "FAIL" or lane_b_status == "FAIL" or lane_c_status == "FAIL":
                    blocking_issue_count += 1
                if not event_context.get("events"):
                    warning_count += 1
                if level != "A" and (warning_fields or missing_fields or _norm(design_row.get("prompt_status")) == "DESIGNED_WITH_WARNINGS"):
                    warning_count += 1

                if blocking_issue_count:
                    dry_run_status = "FAIL"
                elif warning_count:
                    dry_run_status = "PASS_WITH_WARNINGS"
                else:
                    dry_run_status = "PASS"

                notes = list(event_notes + market_state_notes)
                if pack_e_identical and level == "E":
                    notes.append("pack_e_identical_to_pack_d=TRUE")
                if guardrail_only_terms:
                    notes.append("forbidden_terms_present_in_guardrails_only")
                if schema_issues:
                    notes.append("schema_issues=" + "|".join(schema_issues))

                dry_run_rows.append(
                    {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "prompt_validation_version": PROMPT_VALIDATION_VERSION,
                        "prompt_validation_run_id": run_id,
                        "session_id": session_id,
                        "session_date": session_meta.get("session_date", ""),
                        "country": session_meta.get("country", ""),
                        "session_window_name": session_meta.get("session_window_name", ""),
                        "provider": provider,
                        "model": _norm(design_row.get("model")),
                        "pack_level": level,
                        "pack_level_name": pack_level_name,
                        "dry_run_status": dry_run_status,
                        "prompt_design_row_found": "TRUE" if prompt_design_found else "FALSE",
                        "market_session_context_built": "TRUE" if market_context_built else "FALSE",
                        "market_state_context_built": "TRUE",
                        "output_schema_attached": "TRUE" if output_schema_attached else "FALSE",
                        "guardrails_attached": "TRUE" if guardrails_attached else "FALSE",
                        "assembled_prompt_text": _preview_text(full_prompt_text),
                        "assembled_prompt_hash": _sha256_text(full_prompt_text),
                        "prompt_token_estimate": _token_estimate(full_prompt_text),
                        "allowed_pack_fields": "|".join(allowed_fields),
                        "actual_pack_fields_in_prompt": "|".join(actual_fields_in_prompt),
                        "excluded_pack_fields_detected": "|".join(excluded_fields_detected),
                        "forbidden_terms_detected": "|".join(core_forbidden_terms),
                        "forbidden_content_appears_in_guardrail_only": "TRUE" if guardrail_only_terms else "FALSE",
                        "warning_metadata_included": warning_metadata_included if warning_fields else "NOT_APPLICABLE",
                        "missing_field_metadata_included": missing_field_metadata_included if missing_fields else "NOT_APPLICABLE",
                        "dxy_proxy_separation_text_present": "TRUE" if dxy_present else ("NOT_APPLICABLE" if not dxy_required else "FALSE"),
                        "external_browsing_prohibition_present": "TRUE" if external_browsing_present else "FALSE",
                        "accuracy_coaching_detected": "TRUE" if accuracy_coaching_detected else "FALSE",
                        "provider_visible_in_this_phase": "FALSE",
                        "used_in_forecast_in_this_phase": "FALSE",
                        "provider_call_made": "FALSE",
                        "forecast_output_created": "FALSE",
                        "pack_e_identical_to_pack_d": "TRUE" if (pack_e_identical and level == "E") else "FALSE",
                        "notes": _truncate_text("; ".join(notes), 500),
                    }
                )

                validation_rows.append(
                    {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "prompt_validation_version": PROMPT_VALIDATION_VERSION,
                        "prompt_validation_run_id": run_id,
                        "session_id": session_id,
                        "provider": provider,
                        "pack_level": level,
                        "pack_level_name": pack_level_name,
                        "dry_run_status": dry_run_status,
                        "field_exposure_status": field_exposure_status,
                        "guardrail_status": guardrail_status,
                        "schema_status": schema_status,
                        "warning_metadata_status": warning_metadata_status,
                        "dxy_proxy_status": dxy_status,
                        "external_browsing_status": external_browsing_status,
                        "accuracy_coaching_status": accuracy_coaching_status,
                        "pack_q_status": pack_q_status,
                        "fed_expectations_status": fed_expectations_status,
                        "upcoming_event_risk_label_status": upcoming_event_risk_label_status,
                        "lane_b_status": lane_b_status,
                        "lane_c_status": lane_c_status,
                        "provider_call_status": provider_call_status,
                        "forecast_output_status": forecast_output_status,
                        "prompt_hash": _sha256_text(full_prompt_text),
                        "forbidden_content_appears_in_guardrail_only": "TRUE" if guardrail_only_terms else "FALSE",
                        "pack_e_identical_to_pack_d": "TRUE" if (pack_e_identical and level == "E") else "FALSE",
                        "blocking_issue_count": blocking_issue_count,
                        "warning_count": warning_count,
                        "notes": _truncate_text("; ".join(notes), 500),
                    }
                )

    prompts_passed = sum(1 for row in dry_run_rows if _norm(row.get("dry_run_status")) == "PASS")
    prompts_passed_with_warnings = sum(1 for row in dry_run_rows if _norm(row.get("dry_run_status")) == "PASS_WITH_WARNINGS")
    prompts_needing_review = sum(1 for row in dry_run_rows if _norm(row.get("dry_run_status")) == "NEEDS_REVIEW")
    prompts_failed = sum(1 for row in dry_run_rows if _norm(row.get("dry_run_status")) == "FAIL")

    blocked_field_present_count = sum(1 for row in field_audit_rows if _norm(row.get("exposure_status")) == "BLOCKED_FIELD_PRESENT")
    unexpected_field_present_count = sum(1 for row in field_audit_rows if _norm(row.get("exposure_status")) == "NOT_EXPECTED_BUT_PRESENT")
    expected_field_missing_count = sum(1 for row in field_audit_rows if _norm(row.get("exposure_status")) == "EXPECTED_BUT_MISSING")
    missing_guardrail_count = sum(
        1
        for row in guardrail_validation_rows
        if _as_bool(row.get("guardrail_expected")) and _norm(row.get("validation_status")) == "FAIL"
    )
    schema_error_count = sum(1 for row in validation_rows if _norm(row.get("schema_status")) == "FAIL")
    warning_metadata_missing_count = sum(1 for row in validation_rows if _norm(row.get("warning_metadata_status")) == "FAIL")
    dxy_proxy_separation_missing_count = sum(1 for row in validation_rows if _norm(row.get("dxy_proxy_status")) == "FAIL")
    external_browsing_allowed_count = sum(1 for row in validation_rows if _norm(row.get("external_browsing_status")) == "FAIL")
    accuracy_coaching_detected_count = sum(1 for row in validation_rows if _norm(row.get("accuracy_coaching_status")) == "FAIL")

    pack_q_included_count = sum(1 for row in validation_rows if _norm(row.get("pack_q_status")) == "FAIL")
    fed_expectations_included_count = sum(1 for row in validation_rows if _norm(row.get("fed_expectations_status")) == "FAIL")
    upcoming_event_risk_label_included_count = sum(1 for row in validation_rows if _norm(row.get("upcoming_event_risk_label_status")) == "FAIL")
    lane_b_included_count = sum(1 for row in validation_rows if _norm(row.get("lane_b_status")) == "FAIL")
    lane_c_included_count = sum(1 for row in validation_rows if _norm(row.get("lane_c_status")) == "FAIL")

    provider_visible_count = 0
    used_in_forecast_count = 0
    provider_call_count = 0
    forecast_output_count = 0
    market_state_pack_write_count = 0
    phase9_forecast_sheet_write_count = 0
    v1_sheet_write_count = 0
    production_behavior_change_count = 0

    safety_nonzero = any(
        [
            external_browsing_allowed_count,
            accuracy_coaching_detected_count,
            pack_q_included_count,
            fed_expectations_included_count,
            upcoming_event_risk_label_included_count,
            lane_b_included_count,
            lane_c_included_count,
            provider_visible_count,
            used_in_forecast_count,
            provider_call_count,
            forecast_output_count,
            market_state_pack_write_count,
            phase9_forecast_sheet_write_count,
            v1_sheet_write_count,
            production_behavior_change_count,
        ]
    )

    if safety_nonzero:
        build_status = "FAIL"
        final_interpretation = "PACK_EXPOSURE_PROMPT_VALIDATION_BLOCKED"
    elif prompts_failed:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "PACK_EXPOSURE_PROMPT_VALIDATION_NEEDS_REVIEW"
    elif prompts_needing_review or prompts_passed_with_warnings or missing_guardrail_count or schema_error_count or warning_metadata_missing_count or dxy_proxy_separation_missing_count:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "PACK_EXPOSURE_PROMPT_VALIDATION_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        final_interpretation = "PACK_EXPOSURE_PROMPT_VALIDATION_READY"

    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "prompt_validation_version": PROMPT_VALIDATION_VERSION,
        "prompt_validation_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "dry_run_rows_written": len(dry_run_rows),
        "field_exposure_rows_written": len(field_audit_rows),
        "guardrail_validation_rows_written": len(guardrail_validation_rows),
        "validation_audit_rows_written": len(validation_rows),
        "sessions_validated": len(session_ids),
        "providers_validated": len(providers),
        "pack_levels_validated": len(ACTIVE_PACK_LEVELS),
        "prompt_design_rows_checked": len(prompt_rows_filtered),
        "prompts_passed": prompts_passed,
        "prompts_passed_with_warnings": prompts_passed_with_warnings,
        "prompts_needing_review": prompts_needing_review,
        "prompts_failed": prompts_failed,
        "blocked_field_present_count": blocked_field_present_count,
        "unexpected_field_present_count": unexpected_field_present_count,
        "expected_field_missing_count": expected_field_missing_count,
        "missing_guardrail_count": missing_guardrail_count,
        "schema_error_count": schema_error_count,
        "warning_metadata_missing_count": warning_metadata_missing_count,
        "dxy_proxy_separation_missing_count": dxy_proxy_separation_missing_count,
        "external_browsing_allowed_count": external_browsing_allowed_count,
        "accuracy_coaching_detected_count": accuracy_coaching_detected_count,
        "pack_q_included_count": pack_q_included_count,
        "fed_expectations_included_count": fed_expectations_included_count,
        "upcoming_event_risk_label_included_count": upcoming_event_risk_label_included_count,
        "lane_b_included_count": lane_b_included_count,
        "lane_c_included_count": lane_c_included_count,
        "provider_visible_count": provider_visible_count,
        "used_in_forecast_count": used_in_forecast_count,
        "provider_call_count": provider_call_count,
        "forecast_output_count": forecast_output_count,
        "market_state_pack_write_count": market_state_pack_write_count,
        "phase9_forecast_sheet_write_count": phase9_forecast_sheet_write_count,
        "v1_sheet_write_count": v1_sheet_write_count,
        "production_behavior_change_count": production_behavior_change_count,
        "notes": _truncate_text(
            json.dumps(
                {
                    "warnings": sorted(set(warnings)),
                    "missing_required": sorted(set(missing_required)),
                    "shadow_sessions": session_ids,
                },
                ensure_ascii=True,
            ),
            500,
        ),
    }

    dry_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DRY_RUN_SHEET, DRY_RUN_HEADERS)
    validation_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_AUDIT_SHEET, VALIDATION_AUDIT_HEADERS)
    field_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FIELD_AUDIT_SHEET, FIELD_AUDIT_HEADERS)
    guardrail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAIL_VALIDATION_SHEET, GUARDRAIL_VALIDATION_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_DRY_RUN_SHEET, dry_headers, dry_run_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_AUDIT_SHEET, validation_headers, validation_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FIELD_AUDIT_SHEET, field_headers, field_audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAIL_VALIDATION_SHEET, guardrail_headers, guardrail_validation_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary])

    registry = _build_registry_updates(service)
    return {
        "prompt_validation_run_id": run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "sheets_written": {
            OUTPUT_DRY_RUN_SHEET: len(dry_run_rows),
            OUTPUT_FIELD_AUDIT_SHEET: len(field_audit_rows),
            OUTPUT_GUARDRAIL_VALIDATION_SHEET: len(guardrail_validation_rows),
            OUTPUT_VALIDATION_AUDIT_SHEET: len(validation_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "sessions_validated": summary["sessions_validated"],
        "providers_validated": summary["providers_validated"],
        "pack_levels_validated": summary["pack_levels_validated"],
        "prompt_design_rows_checked": summary["prompt_design_rows_checked"],
        "prompts_passed": summary["prompts_passed"],
        "prompts_passed_with_warnings": summary["prompts_passed_with_warnings"],
        "prompts_needing_review": summary["prompts_needing_review"],
        "prompts_failed": summary["prompts_failed"],
        "blocked_field_present_count": summary["blocked_field_present_count"],
        "unexpected_field_present_count": summary["unexpected_field_present_count"],
        "expected_field_missing_count": summary["expected_field_missing_count"],
        "missing_guardrail_count": summary["missing_guardrail_count"],
        "schema_error_count": summary["schema_error_count"],
        "warning_metadata_missing_count": summary["warning_metadata_missing_count"],
        "dxy_proxy_separation_missing_count": summary["dxy_proxy_separation_missing_count"],
        "external_browsing_allowed_count": summary["external_browsing_allowed_count"],
        "accuracy_coaching_detected_count": summary["accuracy_coaching_detected_count"],
        "pack_q_included_count": summary["pack_q_included_count"],
        "fed_expectations_included_count": summary["fed_expectations_included_count"],
        "upcoming_event_risk_label_included_count": summary["upcoming_event_risk_label_included_count"],
        "lane_b_included_count": summary["lane_b_included_count"],
        "lane_c_included_count": summary["lane_c_included_count"],
        "provider_visible_count": summary["provider_visible_count"],
        "used_in_forecast_count": summary["used_in_forecast_count"],
        "provider_call_count": summary["provider_call_count"],
        "forecast_output_count": summary["forecast_output_count"],
        "market_state_pack_write_count": summary["market_state_pack_write_count"],
        "phase9_forecast_sheet_write_count": summary["phase9_forecast_sheet_write_count"],
        "v1_sheet_write_count": summary["v1_sheet_write_count"],
        "production_behavior_change_count": summary["production_behavior_change_count"],
        "registry": registry,
        "warnings": sorted(set(warnings)),
        "missing_required": sorted(set(missing_required)),
        "summary": summary,
    }


def main() -> None:
    result = build_pack_exposure_prompt_validation_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
