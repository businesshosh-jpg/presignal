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


INPUT_LEVEL_DEFINITION_SHEET = "Market_State_Pack_Level_Definition"
INPUT_LEVEL_ITEMS_SHEET = "Market_State_Pack_Level_Items"
INPUT_LEVEL_READINESS_SHEET = "Market_State_Pack_Level_Readiness_Audit"
INPUT_LEVEL_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
DIAGNOSTICS_CONTEXT_SHEETS = [
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Item_Audit",
    "Market_State_Pack_Coverage_Audit",
    "Session_Forecasts",
    "Session_Attention_Map_History",
    "Session_Information_Requests_History",
    "Market_Sessions",
    "Market_Session_Members",
]
OPTIONAL_DIAGNOSTICS_SHEETS = [
    "Session_Evaluation",
    "Session_vs_Event_Baseline_Compare",
    "Market_State_Source_Mapping",
    "Market_State_Source_Semantics",
]
MAIN_CONTEXT_SHEETS = ["Event", "Config"]

OUTPUT_PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
OUTPUT_GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
OUTPUT_COMPARISON_SHEET = "Pack_Exposure_Comparison_Design"
OUTPUT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Design_Summary"

SCHEMA_VERSION = "presignal_v2_pack_exposure_prompt_design_0.1"
PROMPT_DESIGN_VERSION = "pack_exposure_prompt_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PACK_EXPOSURE_PROMPT_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"
OUTPUT_SCHEMA_ID = "pack_exposure_forecast_output_v0"
GUARDRAIL_SET_ID = "pack_exposure_guardrails_v0"
COMPARISON_GROUP_ID = "pack_exposure_comparison_v0"

ACTIVE_PACK_LEVELS = ["A", "B", "C", "D", "E"]
PACK_Q_LEVEL = "Q"
DEFAULT_PROVIDERS = [
    {"provider": "OpenAI", "model": ""},
    {"provider": "Gemini", "model": ""},
    {"provider": "Anthropic", "model": ""},
]

STRICT_EXCLUDED_TERMS = [
    "fed_expectations",
    "UPCOMING_EVENT_RISK_LABEL",
    "Pack Q",
    "Lane B provisional summaries",
    "Lane C interpretive labels",
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
    "bad-news-is-good-news",
    "risk-on / risk-off",
    "Fed-path session label",
    "growth-scare session label",
    "market likely to fade move",
    "USD reaction asymmetry",
]

PROMPT_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_design_version",
    "prompt_design_run_id",
    "pack_level",
    "pack_level_name",
    "provider",
    "model",
    "prompt_status",
    "provider_visible_in_this_phase",
    "used_in_forecast_in_this_phase",
    "system_prompt_template",
    "user_prompt_template",
    "market_state_context_template",
    "event_context_template",
    "output_schema_id",
    "guardrail_set_id",
    "comparison_group_id",
    "allowed_pack_fields",
    "excluded_pack_fields",
    "forbidden_information_categories",
    "warning_handling_rule",
    "dxy_proxy_handling_rule",
    "external_info_rule",
    "accuracy_coaching_rule",
    "behavior_measurement_rule",
    "notes",
]

SCHEMA_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_design_version",
    "prompt_design_run_id",
    "output_schema_id",
    "field_name",
    "field_type",
    "required",
    "allowed_values",
    "description",
    "behavior_audit_use",
    "accuracy_audit_use",
    "notes",
]

GUARDRAIL_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_design_version",
    "prompt_design_run_id",
    "guardrail_set_id",
    "guardrail_name",
    "guardrail_category",
    "guardrail_text",
    "applies_to_pack_levels",
    "blocking_if_violated",
    "violation_detection_hint",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_design_version",
    "prompt_design_run_id",
    "comparison_group_id",
    "comparison_name",
    "baseline_pack_level",
    "treatment_pack_level",
    "comparison_purpose",
    "behavior_fields_to_compare",
    "accuracy_fields_to_compare_later",
    "primary_behavior_hypothesis",
    "accuracy_claim_allowed_now",
    "minimum_required_sessions",
    "minimum_required_providers",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "prompt_design_version",
    "prompt_design_run_id",
    "build_status",
    "final_interpretation",
    "pack_levels_designed",
    "providers_designed",
    "prompt_rows_written",
    "output_schema_rows_written",
    "guardrail_rows_written",
    "comparison_rows_written",
    "feature_freeze_active",
    "pack_q_included_count",
    "fed_expectations_included_count",
    "upcoming_event_risk_label_included_count",
    "lane_b_included_count",
    "lane_c_included_count",
    "external_browsing_allowed_count",
    "accuracy_coaching_count",
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


def _prompt_design_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_exposure_prompt_design_v0_{stamp}"


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


def _safe_int(value: Any) -> int:
    try:
        raw = _norm(value)
        return int(float(raw)) if raw else 0
    except Exception:
        return 0


def _pack_level_definitions(rows: Sequence[Dict[str, Any]], latest_run_id: str) -> Dict[str, Dict[str, Any]]:
    selected = [row for row in rows if not latest_run_id or _norm(row.get("pack_design_run_id")) == latest_run_id]
    out: Dict[str, Dict[str, Any]] = {}
    for row in selected:
        level = _norm(row.get("pack_level"))
        if level:
            out[level] = row
    return out


def _pack_level_items(rows: Sequence[Dict[str, Any]], latest_run_id: str) -> Dict[str, List[Dict[str, Any]]]:
    selected = [row for row in rows if not latest_run_id or _norm(row.get("pack_design_run_id")) == latest_run_id]
    out: Dict[str, List[Dict[str, Any]]] = {level: [] for level in ACTIVE_PACK_LEVELS}
    for row in selected:
        level = _norm(row.get("pack_level"))
        if level in out:
            out[level].append(row)
    return out


def _included_fields(item_rows: Sequence[Dict[str, Any]]) -> List[str]:
    fields = [
        _norm(row.get("candidate_field"))
        for row in item_rows
        if _as_bool(row.get("include_in_level")) and _as_bool(row.get("phase9_allowed"))
    ]
    return sorted(dict.fromkeys(field for field in fields if field))


def _excluded_fields_for_level(level: str, all_known_fields: Iterable[str], allowed_fields: Sequence[str]) -> List[str]:
    excluded = set(STRICT_EXCLUDED_TERMS)
    excluded.update(field for field in all_known_fields if field not in set(allowed_fields))
    if level == "A":
        excluded.update(all_known_fields)
    return sorted(field for field in excluded if field)


def _infer_providers(forecast_rows: Sequence[Dict[str, Any]], attention_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    provider_models: Dict[str, str] = {}
    for source_rows in (forecast_rows, attention_rows):
        for row in source_rows:
            provider = _norm(row.get("provider"))
            if not provider:
                continue
            provider_models.setdefault(provider, _norm(row.get("model")))
    if not provider_models:
        return list(DEFAULT_PROVIDERS)
    return [{"provider": provider, "model": model} for provider, model in sorted(provider_models.items())]


def _system_prompt_template() -> str:
    return "\n".join(
        [
            "You are forecasting the USDJPY reaction for one Market Session.",
            "Use only the information provided in this prompt.",
            "Do not browse.",
            "Do not use external market information.",
            "Do not assume data from other pack levels or from unavailable sources.",
            "If provided market-state context is not useful, say so.",
            "If a field changes your reasoning, identify it.",
            "If a field does not affect your reasoning, identify it.",
            "Do not provide trading advice, entries, stops, take-profit levels, leverage, or position sizing.",
            "Return only valid JSON matching the required schema.",
        ]
    )


def _user_prompt_template() -> str:
    return "\n".join(
        [
            "Forecast the USDJPY market reaction for this Market Session.",
            "Use the supplied market session context, event context, and assigned Market-State Context only.",
            "If the assigned context does not materially affect your forecast, state that in the behavior fields.",
            "Do not use unavailable context, external data, or information from other pack levels.",
            "Return strict JSON only.",
        ]
    )


def _event_context_template() -> str:
    return json.dumps(
        {
            "session": {
                "session_id": "{{session_id}}",
                "session_date": "{{session_date}}",
                "country": "{{country}}",
                "session_window_name": "{{session_window_name}}",
                "session_start_ts": "{{session_start_ts}}",
                "session_end_ts": "{{session_end_ts}}",
                "member_event_count": "{{member_event_count}}",
            },
            "events": [
                {
                    "event_id": "{{event_id}}",
                    "indicator_name": "{{indicator_name}}",
                    "release_ts": "{{release_ts}}",
                    "importance": "{{importance}}",
                    "consensus_value": "{{consensus_value}}",
                    "previous_value": "{{previous_value}}",
                    "revision_info_if_available": "{{revision_info_if_available}}",
                    "known_before_forecast_only": True,
                }
            ],
        },
        ensure_ascii=True,
    )


def _market_state_template(level: str, allowed_fields: Sequence[str]) -> str:
    if level == "A" or not allowed_fields:
        payload: Dict[str, Any] = {
            "assigned_market_state_context": [],
            "instruction": "No Market-State Context is assigned for this run.",
        }
    else:
        payload = {
            "assigned_market_state_context": [
                {
                    "field_name": field,
                    "field_value": "{{field_value}}",
                    "field_unit": "{{field_unit}}",
                    "as_of_timestamp": "{{as_of_timestamp}}",
                    "source_observation_ts": "{{source_observation_ts}}",
                    "source_publication_ts": "{{source_publication_ts}}",
                    "warning_label": "{{warning_label}}",
                    "missing_reason": "{{missing_reason}}",
                    "backtest_safe": "{{backtest_safe}}",
                }
                for field in allowed_fields
            ],
            "instruction": "Use only these assigned fields. Missing fields must not be fabricated.",
            "dxy_proxy_note": "DXY and USD_INDEX_PROXY are not equivalent. Do not treat USD_INDEX_PROXY as actual DXY.",
        }
    return json.dumps(payload, ensure_ascii=True)


def _prompt_rows(
    generated_ts: str,
    run_id: str,
    definitions: Dict[str, Dict[str, Any]],
    items_by_level: Dict[str, List[Dict[str, Any]]],
    providers: Sequence[Dict[str, str]],
    readiness_by_level: Dict[str, str],
) -> List[Dict[str, Any]]:
    all_known_fields = sorted(
        {
            _norm(row.get("candidate_field"))
            for rows in items_by_level.values()
            for row in rows
            if _norm(row.get("candidate_field"))
        }
    )
    rows: List[Dict[str, Any]] = []
    system_template = _system_prompt_template()
    user_template = _user_prompt_template()
    event_template = _event_context_template()
    forbidden = "|".join(STRICT_EXCLUDED_TERMS)
    for level in ACTIVE_PACK_LEVELS:
        definition = definitions.get(level, {})
        level_name = _norm(definition.get("pack_level_name")) or level
        allowed_fields = _included_fields(items_by_level.get(level, []))
        excluded_fields = _excluded_fields_for_level(level, all_known_fields, allowed_fields)
        status = "DESIGNED_WITH_WARNINGS" if "WARNING" in readiness_by_level.get(level, "") else "DESIGNED"
        if not definition:
            status = "BLOCKED"
        notes = ""
        if level == "E" and set(_included_fields(items_by_level.get("D", []))) == set(allowed_fields):
            notes = "pack_e_identical_to_pack_d=TRUE; Feature Freeze produced no additional eligible Lane A deterministic fields."
        for provider in providers:
            rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "prompt_design_version": PROMPT_DESIGN_VERSION,
                    "prompt_design_run_id": run_id,
                    "pack_level": level,
                    "pack_level_name": level_name,
                    "provider": provider["provider"],
                    "model": provider.get("model", ""),
                    "prompt_status": status,
                    "provider_visible_in_this_phase": "FALSE",
                    "used_in_forecast_in_this_phase": "FALSE",
                    "system_prompt_template": _truncate_text(system_template, 4000),
                    "user_prompt_template": _truncate_text(user_template, 4000),
                    "market_state_context_template": _truncate_text(_market_state_template(level, allowed_fields), 4000),
                    "event_context_template": _truncate_text(event_template, 4000),
                    "output_schema_id": OUTPUT_SCHEMA_ID,
                    "guardrail_set_id": GUARDRAIL_SET_ID,
                    "comparison_group_id": COMPARISON_GROUP_ID,
                    "allowed_pack_fields": "|".join(allowed_fields),
                    "excluded_pack_fields": "|".join(excluded_fields),
                    "forbidden_information_categories": forbidden,
                    "warning_handling_rule": "Expose warnings as metadata only; do not hide warnings or overstate freshness.",
                    "dxy_proxy_handling_rule": "DXY and USD_INDEX_PROXY are not equivalent; never treat proxy values as actual DXY.",
                    "external_info_rule": "No browsing and no external information beyond assigned session/event/context payload.",
                    "accuracy_coaching_rule": "No accuracy coaching, no claims that any field is expected to help, and no correct-answer hints.",
                    "behavior_measurement_rule": "Collect used, discarded, changed-reasoning, did-not-change-reasoning, uncertainty, and no-signal fields.",
                    "notes": _truncate_text(notes, 500),
                }
            )
    return rows


def _schema_rows(generated_ts: str, run_id: str) -> List[Dict[str, Any]]:
    specs = [
        ("session_id", "string", "TRUE", "", "Session identifier.", "link forecast behavior to session", "link future accuracy evaluation", ""),
        ("provider", "string", "TRUE", "", "Provider name.", "provider behavior grouping", "provider accuracy grouping", ""),
        ("model", "string", "TRUE", "", "Provider model identifier.", "model behavior grouping", "model accuracy grouping", ""),
        ("pack_level", "string", "TRUE", "A|B|C|D|E", "Assigned internal pack level for this run.", "pack treatment grouping", "pack treatment grouping", ""),
        ("forecast_direction", "string", "TRUE", "up|down|flat|no_clear_direction", "Session-level USDJPY direction forecast.", "direction shift by pack", "future direction scoring", ""),
        ("forecast_confidence", "number", "FALSE", "0..1", "Provider confidence normalized to 0-1.", "confidence shift by pack", "future calibration review", ""),
        ("expected_move_pips_min", "number", "FALSE", "", "Expected move lower bound in pips.", "expected strength shift", "future strength review", ""),
        ("expected_move_pips_max", "number", "FALSE", "", "Expected move upper bound in pips.", "expected strength shift", "future strength review", ""),
        ("expected_holding_minutes", "number", "FALSE", "", "Expected reaction horizon in minutes.", "holding assumption shift", "future horizon review", ""),
        ("primary_driver_summary", "string", "TRUE", "", "Most important driver for the session forecast.", "driver attribution", "future attribution review", ""),
        ("secondary_driver_summary", "string", "FALSE", "", "Secondary driver summary.", "driver attribution", "future attribution review", ""),
        ("ignored_event_summary", "string", "FALSE", "", "Events intentionally ignored or deprioritized.", "attention behavior", "future attribution review", ""),
        ("information_used", "string", "FALSE", "", "Non-pack and pack information used.", "information uptake", "future attribution review", ""),
        ("information_not_used", "string", "FALSE", "", "Information explicitly not used.", "information discard behavior", "future attribution review", ""),
        ("pack_fields_used", "array", "FALSE", "", "Assigned pack fields that affected reasoning.", "pack uptake", "future attribution review", ""),
        ("pack_fields_discarded", "array", "FALSE", "", "Assigned pack fields explicitly discarded.", "pack discard behavior", "future attribution review", ""),
        ("pack_fields_that_changed_reasoning", "array", "FALSE", "", "Pack fields that changed causal reasoning.", "behavior-change measurement", "future attribution review", ""),
        ("pack_fields_that_did_not_change_reasoning", "array", "FALSE", "", "Pack fields that did not change causal reasoning.", "behavior-change measurement", "future attribution review", ""),
        ("causal_chain", "string", "TRUE", "", "Concise causal path from events/context to forecast.", "reasoning shift", "future attribution review", ""),
        ("invalidation_condition", "string", "FALSE", "", "Condition that would invalidate the forecast.", "uncertainty behavior", "future review", ""),
        ("no_signal_flag", "boolean", "TRUE", "TRUE|FALSE", "Whether provider chooses no clear directional signal.", "no-signal behavior", "future no-signal scoring", ""),
        ("no_signal_reason", "string", "FALSE", "", "Reason for no-signal if applicable.", "no-signal behavior", "future no-signal scoring", ""),
        ("uncertainty_sources", "array", "FALSE", "", "Sources of uncertainty.", "uncertainty behavior", "future error analysis", ""),
        ("missing_information", "string", "FALSE", "", "Missing information noted by provider.", "information gap behavior", "future error analysis", ""),
        ("confidence_change_explanation", "string", "FALSE", "", "Why confidence is high, low, or changed by assigned context.", "confidence behavior", "future calibration review", ""),
        ("raw_output", "string", "FALSE", "", "Raw provider output retained by later execution.", "audit support", "audit support", ""),
        ("status", "string", "TRUE", "ok|error", "Provider output status.", "execution audit", "execution audit", ""),
        ("error_message", "string", "FALSE", "", "Error details if status is error.", "execution audit", "execution audit", ""),
    ]
    return [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "prompt_design_version": PROMPT_DESIGN_VERSION,
            "prompt_design_run_id": run_id,
            "output_schema_id": OUTPUT_SCHEMA_ID,
            "field_name": name,
            "field_type": field_type,
            "required": required,
            "allowed_values": allowed,
            "description": description,
            "behavior_audit_use": behavior_use,
            "accuracy_audit_use": accuracy_use,
            "notes": notes,
        }
        for name, field_type, required, allowed, description, behavior_use, accuracy_use, notes in specs
    ]


def _guardrail_rows(generated_ts: str, run_id: str) -> List[Dict[str, Any]]:
    specs = [
        ("NO_EXTERNAL_BROWSING", "information_boundary", "Do not browse or use external market information.", "TRUE", "search for browsing claims or external source references"),
        ("NO_OTHER_PACK_LEVELS", "information_boundary", "Do not use or infer information from other pack levels or unavailable sources.", "TRUE", "mentions of other levels or unassigned fields"),
        ("NO_EXCLUDED_FIELDS", "information_boundary", "Do not include excluded fields or information categories in provider-facing context.", "TRUE", "excluded field names in prompt payload"),
        ("NO_FED_EXPECTATIONS", "scope_exclusion", "Do not expose fed_expectations or Fed expectations proxies in this phase.", "TRUE", "fed_expectations or FedWatch terms"),
        ("NO_UPCOMING_EVENT_RISK_LABEL", "scope_exclusion", "Do not expose UPCOMING_EVENT_RISK_LABEL in this phase.", "TRUE", "UPCOMING_EVENT_RISK_LABEL"),
        ("NO_ACCURACY_COACHING", "experiment_control", "Do not tell providers that any pack field should improve accuracy or indicates a correct answer.", "TRUE", "accuracy-coaching phrases"),
        ("DXY_PROXY_SEPARATION", "semantic_integrity", "DXY and USD_INDEX_PROXY are not equivalent and must remain clearly separated.", "TRUE", "proxy treated as actual DXY"),
        ("WARNING_METADATA_PRESERVED", "auditability", "Warnings must be preserved as metadata without interpretive overstatement.", "FALSE", "missing warning fields"),
        ("USE_ONLY_ASSIGNED_CONTEXT", "information_boundary", "Use only the assigned session, event, and market-state context.", "TRUE", "unassigned context references"),
        ("NO_PROVIDER_VISIBLE_THIS_PHASE", "phase_boundary", "This prompt design phase must not expose pack values to providers.", "TRUE", "provider calls or forecast output rows"),
    ]
    return [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "prompt_design_version": PROMPT_DESIGN_VERSION,
            "prompt_design_run_id": run_id,
            "guardrail_set_id": GUARDRAIL_SET_ID,
            "guardrail_name": name,
            "guardrail_category": category,
            "guardrail_text": text,
            "applies_to_pack_levels": "A|B|C|D|E",
            "blocking_if_violated": blocking,
            "violation_detection_hint": hint,
            "notes": "Pack Q is placeholder-only and not part of Phase 9A-0 prompt design.",
        }
        for name, category, text, blocking, hint in specs
    ]


def _comparison_rows(generated_ts: str, run_id: str) -> List[Dict[str, Any]]:
    behavior_fields = "|".join(
        [
            "forecast_direction",
            "forecast_confidence",
            "expected_move_pips_min",
            "expected_move_pips_max",
            "expected_holding_minutes",
            "no_signal_flag",
            "primary_driver_summary",
            "pack_fields_used",
            "pack_fields_discarded",
            "pack_fields_that_changed_reasoning",
            "pack_fields_that_did_not_change_reasoning",
            "causal_chain",
            "uncertainty_sources",
            "missing_information",
        ]
    )
    accuracy_fields = "direction_ok|overall_ok|realized_pips|forecast_quality_label|no_signal_ok"
    specs = [
        ("A_vs_B", "A", "B", "Target-state only versus no-pack baseline.", "Does target-state context change direction, confidence, or no-signal behavior?"),
        ("B_vs_C", "B", "C", "Calendar context increment over target-state.", "Does scheduled-event context change caution, confidence, or no-signal behavior?"),
        ("C_vs_D", "C", "D", "Rates/dollar context increment over target plus calendar.", "Do rates and dollar context change causal-chain reasoning or confidence?"),
        ("D_vs_E", "D", "E", "Full approved deterministic pack versus rates/dollar context.", "Does the frozen full deterministic core differ from Pack D; if identical, confirm no behavioral distinction is expected."),
        ("A_vs_D", "A", "D", "No-pack baseline versus rates/dollar deterministic context.", "How much behavior changes between no-pack and the primary deterministic context bundle?"),
        ("A_vs_E", "A", "E", "No-pack baseline versus full approved deterministic core.", "How much behavior changes between no-pack and the full frozen deterministic core?"),
    ]
    return [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "prompt_design_version": PROMPT_DESIGN_VERSION,
            "prompt_design_run_id": run_id,
            "comparison_group_id": COMPARISON_GROUP_ID,
            "comparison_name": name,
            "baseline_pack_level": baseline,
            "treatment_pack_level": treatment,
            "comparison_purpose": purpose,
            "behavior_fields_to_compare": behavior_fields,
            "accuracy_fields_to_compare_later": accuracy_fields,
            "primary_behavior_hypothesis": hypothesis,
            "accuracy_claim_allowed_now": "FALSE",
            "minimum_required_sessions": 10,
            "minimum_required_providers": 3,
            "notes": "Accuracy comparison is reserved for later Phase 9 evaluation; no accuracy claim is allowed now.",
        }
        for name, baseline, treatment, purpose, hypothesis in specs
    ]


def _summary_row(
    generated_ts: str,
    run_id: str,
    prompt_rows: Sequence[Dict[str, Any]],
    schema_rows: Sequence[Dict[str, Any]],
    guardrail_rows: Sequence[Dict[str, Any]],
    comparison_rows: Sequence[Dict[str, Any]],
    missing_required: Sequence[str],
    warnings: Sequence[str],
) -> Dict[str, Any]:
    active_rows = [row for row in prompt_rows if _norm(row.get("pack_level")) in ACTIVE_PACK_LEVELS]
    safety = {
        "pack_q_included_count": sum(1 for row in prompt_rows if _norm(row.get("pack_level")) == PACK_Q_LEVEL),
        "fed_expectations_included_count": sum(
            1
            for row in prompt_rows
            if "fed_expectations" in _norm(row.get("allowed_pack_fields")).lower()
        ),
        "upcoming_event_risk_label_included_count": sum(
            1 for row in prompt_rows if "UPCOMING_EVENT_RISK_LABEL" in _norm(row.get("allowed_pack_fields"))
        ),
        "lane_b_included_count": 0,
        "lane_c_included_count": 0,
        "external_browsing_allowed_count": 0,
        "accuracy_coaching_count": 0,
        "provider_visible_count": sum(1 for row in prompt_rows if _as_bool(row.get("provider_visible_in_this_phase"))),
        "used_in_forecast_count": sum(1 for row in prompt_rows if _as_bool(row.get("used_in_forecast_in_this_phase"))),
        "provider_call_count": 0,
        "forecast_output_count": 0,
        "market_state_pack_write_count": 0,
        "phase9_forecast_sheet_write_count": 0,
        "v1_sheet_write_count": 0,
        "production_behavior_change_count": 0,
    }
    if any(safety.values()):
        build_status = "FAIL"
        interpretation = "PACK_EXPOSURE_PROMPT_DESIGN_BLOCKED"
    elif missing_required:
        build_status = "FAIL"
        interpretation = "PACK_EXPOSURE_PROMPT_DESIGN_BLOCKED"
    elif warnings or any(_norm(row.get("prompt_status")) == "DESIGNED_WITH_WARNINGS" for row in active_rows):
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "PACK_EXPOSURE_PROMPT_DESIGN_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        interpretation = "PACK_EXPOSURE_PROMPT_DESIGN_READY"
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "prompt_design_version": PROMPT_DESIGN_VERSION,
        "prompt_design_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": interpretation,
        "pack_levels_designed": len({_norm(row.get("pack_level")) for row in active_rows}),
        "providers_designed": len({_norm(row.get("provider")) for row in active_rows if _norm(row.get("provider"))}),
        "prompt_rows_written": len(prompt_rows),
        "output_schema_rows_written": len(schema_rows),
        "guardrail_rows_written": len(guardrail_rows),
        "comparison_rows_written": len(comparison_rows),
        "feature_freeze_active": "TRUE",
        **safety,
        "notes": _truncate_text(
            json.dumps(
                {
                    "missing_required": sorted(set(missing_required)),
                    "warnings": sorted(set(warnings)),
                },
                ensure_ascii=True,
            ),
            500,
        ),
    }


def _blocked_summary_row(generated_ts: str, run_id: str, missing_required: Sequence[str]) -> Dict[str, Any]:
    return _summary_row(generated_ts, run_id, [], [], [], [], missing_required, [])


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_EXPOSURE_PROMPT_DESIGN", OUTPUT_PROMPT_DESIGN_SHEET, "pack_exposure_prompt_design"),
        ("PACK_EXPOSURE_OUTPUT_SCHEMA", OUTPUT_SCHEMA_SHEET, "pack_exposure_output_schema"),
        ("PACK_EXPOSURE_PROMPT_GUARDRAILS", OUTPUT_GUARDRAILS_SHEET, "pack_exposure_prompt_guardrails"),
        ("PACK_EXPOSURE_COMPARISON_DESIGN", OUTPUT_COMPARISON_SHEET, "pack_exposure_comparison_design"),
        ("PACK_EXPOSURE_PROMPT_DESIGN_SUMMARY", OUTPUT_SUMMARY_SHEET, "pack_exposure_prompt_design_summary"),
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
            "notes": "Phase 9A-0 prompt-design sheet only; no provider calls and no forecasts.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-0 pack exposure prompt design.")
    return parser.parse_args(argv)


def build_pack_exposure_prompt_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    run_id = _prompt_design_run_id(generated_ts)
    creds = load_credentials()
    service = build_sheets_service(creds)
    diagnostics_titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(service, MAIN_SPREADSHEET_ID)

    missing_required: List[str] = []
    warnings: List[str] = []

    level_summary_rows = _read_optional_rows(
        service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_SUMMARY_SHEET, missing_required
    )
    latest_level_run_id = _latest_run_id(level_summary_rows, "pack_design_run_id")
    level_definition_rows = _read_optional_rows(
        service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_DEFINITION_SHEET, missing_required
    )
    level_item_rows = _read_optional_rows(
        service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_ITEMS_SHEET, missing_required
    )
    level_readiness_rows = _read_optional_rows(
        service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_READINESS_SHEET, missing_required
    )

    context_rows: Dict[str, List[Dict[str, Any]]] = {}
    for sheet in DIAGNOSTICS_CONTEXT_SHEETS:
        target = warnings if sheet in OPTIONAL_DIAGNOSTICS_SHEETS else warnings
        context_rows[sheet] = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet, target)
    for sheet in OPTIONAL_DIAGNOSTICS_SHEETS:
        context_rows[sheet] = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet, warnings)
    for sheet in MAIN_CONTEXT_SHEETS:
        _read_optional_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, warnings)

    if not level_summary_rows or not level_definition_rows or not level_item_rows or not level_readiness_rows:
        prompt_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROMPT_DESIGN_SHEET, PROMPT_HEADERS)
        schema_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SCHEMA_SHEET, SCHEMA_HEADERS)
        guardrail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAILS_SHEET, GUARDRAIL_HEADERS)
        comparison_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARISON_SHEET, COMPARISON_HEADERS)
        summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROMPT_DESIGN_SHEET, prompt_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SCHEMA_SHEET, schema_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAILS_SHEET, guardrail_headers, [])
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARISON_SHEET, comparison_headers, [])
        summary = _blocked_summary_row(generated_ts, run_id, sorted(set(missing_required)))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary])
        registry = _upsert_registry_rows(service)
        return {
            "prompt_design_run_id": run_id,
            "build_status": summary["build_status"],
            "final_interpretation": summary["final_interpretation"],
            "sheets_written": {
                OUTPUT_PROMPT_DESIGN_SHEET: 0,
                OUTPUT_SCHEMA_SHEET: 0,
                OUTPUT_GUARDRAILS_SHEET: 0,
                OUTPUT_COMPARISON_SHEET: 0,
                OUTPUT_SUMMARY_SHEET: 1,
            },
            "registry": registry,
            "summary": summary,
            "warnings": sorted(set(warnings)),
            "missing_required": sorted(set(missing_required)),
        }

    level_summary = level_summary_rows[-1]
    if _upper(level_summary.get("final_interpretation")) not in {
        "PACK_LEVEL_DESIGN_READY",
        "PACK_LEVEL_DESIGN_READY_WITH_WARNINGS",
    }:
        warnings.append(
            "Latest Phase 8C pack-level design final_interpretation is not ready: "
            + _norm(level_summary.get("final_interpretation"))
        )

    definitions = _pack_level_definitions(level_definition_rows, latest_level_run_id)
    items_by_level = _pack_level_items(level_item_rows, latest_level_run_id)
    readiness_by_level = {
        _norm(row.get("pack_level")): _norm(row.get("phase9_readiness_status"))
        for row in level_readiness_rows
        if not latest_level_run_id or _norm(row.get("pack_design_run_id")) == latest_level_run_id
    }
    missing_active_levels = [level for level in ACTIVE_PACK_LEVELS if level not in definitions]
    if missing_active_levels:
        missing_required.extend(f"{INPUT_LEVEL_DEFINITION_SHEET}:{level}" for level in missing_active_levels)

    providers = _infer_providers(
        context_rows.get("Session_Forecasts", []),
        context_rows.get("Session_Attention_Map_History", []),
    )
    prompt_rows = _prompt_rows(generated_ts, run_id, definitions, items_by_level, providers, readiness_by_level)
    schema_rows = _schema_rows(generated_ts, run_id)
    guardrail_rows = _guardrail_rows(generated_ts, run_id)
    comparison_rows = _comparison_rows(generated_ts, run_id)
    summary = _summary_row(
        generated_ts,
        run_id,
        prompt_rows,
        schema_rows,
        guardrail_rows,
        comparison_rows,
        sorted(set(missing_required)),
        sorted(set(warnings)),
    )

    prompt_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROMPT_DESIGN_SHEET, PROMPT_HEADERS)
    schema_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SCHEMA_SHEET, SCHEMA_HEADERS)
    guardrail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAILS_SHEET, GUARDRAIL_HEADERS)
    comparison_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARISON_SHEET, COMPARISON_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROMPT_DESIGN_SHEET, prompt_headers, prompt_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SCHEMA_SHEET, schema_headers, schema_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_GUARDRAILS_SHEET, guardrail_headers, guardrail_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARISON_SHEET, comparison_headers, comparison_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary])
    registry = _upsert_registry_rows(service)

    return {
        "prompt_design_run_id": run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "sheets_written": {
            OUTPUT_PROMPT_DESIGN_SHEET: len(prompt_rows),
            OUTPUT_SCHEMA_SHEET: len(schema_rows),
            OUTPUT_GUARDRAILS_SHEET: len(guardrail_rows),
            OUTPUT_COMPARISON_SHEET: len(comparison_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "pack_levels_designed": summary["pack_levels_designed"],
        "providers_designed": summary["providers_designed"],
        "prompt_rows_written": summary["prompt_rows_written"],
        "output_schema_rows_written": summary["output_schema_rows_written"],
        "guardrail_rows_written": summary["guardrail_rows_written"],
        "comparison_rows_written": summary["comparison_rows_written"],
        "feature_freeze_active": summary["feature_freeze_active"],
        "pack_q_included_count": summary["pack_q_included_count"],
        "fed_expectations_included_count": summary["fed_expectations_included_count"],
        "upcoming_event_risk_label_included_count": summary["upcoming_event_risk_label_included_count"],
        "lane_b_included_count": summary["lane_b_included_count"],
        "lane_c_included_count": summary["lane_c_included_count"],
        "external_browsing_allowed_count": summary["external_browsing_allowed_count"],
        "accuracy_coaching_count": summary["accuracy_coaching_count"],
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
    result = build_pack_exposure_prompt_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
