import argparse
import json
import re
import sys
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


INPUT_FORECASTS_SHEET = "Pack_Exposure_Forecasts"
INPUT_METADATA_SHEET = "Pack_Exposure_Forecast_Metadata"
INPUT_BEHAVIOR_SHEET = "Pack_Exposure_Behavior_Capture"
INPUT_RAW_ARCHIVE_SHEET = "Pack_Exposure_Raw_Response_Archive"
INPUT_RUN_LOG_SHEET = "Pack_Exposure_Run_Log"
INPUT_RUN_SUMMARY_SHEET = "Pack_Exposure_Run_Summary"
INPUT_COMPARISON_DESIGN_SHEET = "Pack_Exposure_Comparison_Design"
INPUT_PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
INPUT_OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
INPUT_GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
INPUT_PROMPT_DRY_RUN_SHEET = "Pack_Exposure_Prompt_Dry_Run"
INPUT_PROMPT_VALIDATION_AUDIT_SHEET = "Pack_Exposure_Prompt_Validation_Audit"
INPUT_PROMPT_VALIDATION_SUMMARY_SHEET = "Pack_Exposure_Prompt_Validation_Summary"
INPUT_LEVEL_DEFINITION_SHEET = "Market_State_Pack_Level_Definition"
INPUT_LEVEL_ITEMS_SHEET = "Market_State_Pack_Level_Items"
INPUT_LEVEL_READINESS_SHEET = "Market_State_Pack_Level_Readiness_Audit"
INPUT_LEVEL_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
OPTIONAL_INPUT_SHEETS = [
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Item_Audit",
    "Market_State_Pack_Coverage_Audit",
    "Session_Attention_Map_History",
    "Session_Information_Requests_History",
    "Session_Forecasts",
    "Session_Evaluation",
    "Session_vs_Event_Baseline_Compare",
]

OUTPUT_COMPARE_SHEET = "Pack_Exposure_Behavior_Compare"
OUTPUT_REASONING_SHEET = "Pack_Exposure_Reasoning_Transitions"
OUTPUT_PROVIDER_AUDIT_SHEET = "Pack_Exposure_Provider_Transition_Audit"
OUTPUT_FIELD_INFLUENCE_SHEET = "Pack_Exposure_Field_Influence_Audit"
OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET = "Pack_Exposure_NoSignal_Confidence_Audit"
OUTPUT_INVALID_AUDIT_SHEET = "Pack_Exposure_Invalid_Output_Audit"
OUTPUT_SUMMARY_SHEET = "Pack_Exposure_Behavior_Compare_Summary"

SCHEMA_VERSION = "presignal_v2_pack_exposure_behavior_compare_0.1"
BEHAVIOR_COMPARE_VERSION = "pack_exposure_behavior_compare_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-3R"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PACK_EXPOSURE_BEHAVIOR_COMPARE"
REGISTRY_OWNER_MODULE = "market_state"

PACK_LEVELS = ["A", "B", "C", "D", "E"]
PROVIDERS = ["OpenAI", "Gemini", "Anthropic"]
COMPARISONS = [
    ("A_vs_B", "A", "B"),
    ("B_vs_C", "B", "C"),
    ("C_vs_D", "C", "D"),
    ("D_vs_E", "D", "E"),
    ("A_vs_D", "A", "D"),
    ("A_vs_E", "A", "E"),
]
TRANSITIONS = [
    ("A_to_B", "A", "B"),
    ("B_to_C", "B", "C"),
    ("C_to_D", "C", "D"),
    ("D_to_E", "D", "E"),
    ("A_to_D", "A", "D"),
    ("A_to_E", "A", "E"),
]
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

COMPARE_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "baseline_pack_level",
    "treatment_pack_level", "comparison_pair", "baseline_output_valid", "treatment_output_valid",
    "comparison_status", "forecast_direction_baseline", "forecast_direction_treatment",
    "forecast_direction_changed", "forecast_confidence_baseline", "forecast_confidence_treatment",
    "forecast_confidence_delta", "forecast_confidence_changed", "expected_move_min_baseline",
    "expected_move_min_treatment", "expected_move_min_delta", "expected_move_max_baseline",
    "expected_move_max_treatment", "expected_move_max_delta", "no_signal_baseline",
    "no_signal_treatment", "no_signal_changed", "primary_driver_baseline",
    "primary_driver_treatment", "primary_driver_changed", "secondary_driver_baseline",
    "secondary_driver_treatment", "secondary_driver_changed", "causal_chain_baseline",
    "causal_chain_treatment", "causal_chain_changed", "information_used_baseline",
    "information_used_treatment", "information_used_changed", "pack_fields_used_treatment",
    "pack_fields_changed_reasoning_treatment", "pack_fields_no_effect_treatment",
    "missing_information_baseline", "missing_information_treatment", "missing_information_reduced",
    "behavior_change_score", "behavior_change_label", "notes", "no_signal_source_baseline",
    "no_signal_source_treatment", "no_signal_normalized_baseline", "no_signal_normalized_treatment",
    "no_signal_normalization_status",
]

REASONING_HEADERS = [
    "generated_ts", "schema_version", "reasoning_transition_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "transition", "from_pack_level",
    "to_pack_level", "from_output_valid", "to_output_valid", "transition_status", "direction_from",
    "direction_to", "direction_transition", "confidence_from", "confidence_to", "confidence_delta",
    "confidence_transition", "no_signal_from", "no_signal_to", "no_signal_transition",
    "primary_driver_from", "primary_driver_to", "primary_driver_transition", "secondary_driver_from",
    "secondary_driver_to", "secondary_driver_transition", "ignored_information_from",
    "ignored_information_to", "ignored_information_transition", "used_information_from",
    "used_information_to", "used_information_transition", "missing_information_from",
    "missing_information_to", "missing_information_transition", "causal_chain_from",
    "causal_chain_to", "causal_chain_transition", "pack_fields_newly_available",
    "pack_fields_newly_used", "pack_fields_newly_ignored", "pack_fields_newly_changed_reasoning",
    "pack_fields_newly_no_effect", "new_reasoning_elements", "removed_reasoning_elements",
    "persistent_reasoning_elements", "transition_complexity_score", "reasoning_transition_label",
    "transition_summary", "notes", "no_signal_source_from", "no_signal_source_to",
    "no_signal_normalized_from", "no_signal_normalized_to", "no_signal_normalization_status",
]

PROVIDER_AUDIT_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "transition", "from_pack_level",
    "to_pack_level", "from_output_valid", "to_output_valid", "transition_status",
    "direction_changed", "confidence_delta", "confidence_delta_abs", "no_signal_changed",
    "primary_driver_changed", "secondary_driver_changed", "causal_chain_changed",
    "information_used_changed", "missing_information_reduced", "new_pack_fields_available",
    "new_pack_fields_used", "new_pack_fields_discarded", "new_pack_fields_changed_reasoning",
    "new_pack_fields_no_effect", "transition_interpretation", "notes",
]

FIELD_INFLUENCE_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "pack_level",
    "candidate_family", "candidate_field", "field_available_in_pack", "field_reported_used",
    "field_reported_discarded", "field_reported_changed_reasoning", "field_reported_no_effect",
    "influence_status", "evidence_text", "notes",
]

NO_SIGNAL_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "pack_level", "output_valid",
    "forecast_direction", "forecast_confidence", "no_signal_flag", "no_signal_reason",
    "expected_move_pips_min", "expected_move_pips_max", "confidence_bucket",
    "expected_move_bucket", "uncertainty_sources", "missing_information", "notes",
    "no_signal_source", "no_signal_normalized", "no_signal_normalization_status",
]

INVALID_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "experiment_id", "pilot_run_id", "session_id", "provider", "pack_level",
    "raw_response_archived", "json_parse_success", "json_validation_success", "invalid_reason",
    "affected_comparisons", "raw_response_hash", "repair_attempted", "provider_rerun_attempted",
    "recommended_handling", "notes",
]

SUMMARY_HEADERS = [
    "generated_ts", "schema_version", "behavior_compare_version", "behavior_compare_run_id",
    "build_status", "final_interpretation", "experiment_id", "pilot_run_id", "session_id",
    "providers_analyzed", "pack_levels_analyzed", "forecast_rows_read", "behavior_rows_read",
    "raw_response_rows_read", "valid_outputs_count", "invalid_outputs_count",
    "comparison_rows_written", "reasoning_transition_rows_written", "transition_rows_written",
    "field_influence_rows_written", "no_signal_confidence_rows_written", "invalid_output_rows_written",
    "direction_change_count", "confidence_change_count", "reasoning_change_count",
    "causal_chain_change_count", "no_signal_change_count", "missing_information_reduced_count",
    "available_field_mentions_count", "field_used_count", "field_discarded_count",
    "field_changed_reasoning_count", "field_no_effect_count", "max_transition_complexity_score",
    "highest_transition_complexity_provider", "highest_transition_complexity_transition",
    "largest_confidence_delta_provider", "largest_confidence_delta_transition",
    "accuracy_evaluation_count", "provider_rerun_count", "provider_call_count",
    "forecast_generation_count", "production_behavior_change_count", "notes",
    "no_signal_unknown_count", "no_signal_invalid_count", "no_signal_normalization_pass_count",
    "no_signal_normalization_fallback_count", "no_signal_normalization_unknown_count",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _as_float(value: Any) -> Optional[float]:
    try:
        raw = _norm(value)
        if raw == "":
            return None
        return float(raw)
    except Exception:
        return None


def _confidence_percent(value: Any) -> Optional[float]:
    val = _as_float(value)
    if val is None:
        return None
    if abs(val) <= 1:
        return val * 100
    return val


def _fmt_num(value: Optional[float]) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _changed(a: Any, b: Any) -> bool:
    return _norm(a).strip().lower() != _norm(b).strip().lower()


def _bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_exposure_behavior_compare_repair_v0_{stamp}"


def _previous_no_signal_change_count(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    latest = rows[-1]
    notes = _norm(latest.get("notes"))
    if notes:
        try:
            payload = json.loads(notes)
            preserved = _norm(payload.get("previous_no_signal_change_count"))
            if preserved:
                return preserved
        except Exception:
            pass
    return _norm(latest.get("no_signal_change_count"))


def _get_sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _read_optional_rows(service, spreadsheet_id: str, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _latest_run_id(rows: Sequence[Dict[str, Any]], key: str) -> str:
    return _norm(rows[-1].get(key)) if rows else ""


def _filter_run(rows: Sequence[Dict[str, Any]], key: str, run_id: str) -> List[Dict[str, Any]]:
    if not run_id:
        return list(rows)
    return [row for row in rows if _norm(row.get(key)) == run_id]


def _pack_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (_norm(row.get("provider")), _norm(row.get("pack_level")))


def _output_valid(row: Optional[Dict[str, Any]]) -> bool:
    return bool(row) and _upper(row.get("json_validation_success")) == "TRUE"


def _normalize_bool_token(value: Any) -> str:
    token = _upper(value)
    if token in {"TRUE", "T", "YES", "Y", "1"}:
        return "TRUE"
    if token in {"FALSE", "F", "NO", "N", "0"}:
        return "FALSE"
    return ""


def normalize_no_signal_flag(
    forecast_row: Optional[Dict[str, Any]],
    behavior_row: Optional[Dict[str, Any]],
    audit_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Return TRUE/FALSE/UNKNOWN/INVALID with source traceability.

    No-signal is a behavior field, not an accuracy field. Missing valid output
    should never silently become FALSE.
    """
    if not forecast_row or not _output_valid(forecast_row):
        return {"value": "INVALID", "source": "invalid_output", "status": "INVALID_OUTPUT"}

    behavior_row = behavior_row or {}
    forecast_row = forecast_row or {}
    audit_row = audit_row or {}

    for field in ("no_signal_flag", "no_signal", "is_no_signal"):
        val = _normalize_bool_token(behavior_row.get(field))
        if val:
            return {"value": val, "source": f"behavior_capture.{field}", "status": "PASS"}

    for field in ("no_signal", "no_signal_flag", "is_no_signal"):
        val = _normalize_bool_token(forecast_row.get(field))
        if val:
            return {"value": val, "source": f"forecast_output.{field}", "status": "PASS"}

    val = _normalize_bool_token(audit_row.get("no_signal_flag"))
    if val:
        return {"value": val, "source": "no_signal_confidence_audit.no_signal_flag", "status": "PASS_WITH_FALLBACK"}

    direction = _norm(forecast_row.get("forecast_direction")).lower()
    if direction in {"no_signal", "no_clear_direction"}:
        return {"value": "TRUE", "source": "forecast_direction_fallback", "status": "PASS_WITH_FALLBACK"}
    if direction in {"up", "down", "flat"}:
        return {"value": "FALSE", "source": "forecast_direction_fallback", "status": "PASS_WITH_FALLBACK"}

    if _norm(behavior_row.get("no_signal_reason")):
        return {"value": "TRUE", "source": "behavior_capture.no_signal_reason", "status": "PASS_WITH_FALLBACK"}

    return {"value": "UNKNOWN", "source": "missing_no_signal_source", "status": "UNKNOWN_SOURCE"}


def _no_signal_changed(a: Dict[str, str], b: Dict[str, str]) -> bool:
    if a.get("value") in {"UNKNOWN", "INVALID"} or b.get("value") in {"UNKNOWN", "INVALID"}:
        return False
    return a.get("value") != b.get("value")


def _no_signal_pair_status(a: Dict[str, str], b: Dict[str, str]) -> str:
    statuses = {a.get("status", ""), b.get("status", "")}
    if "INVALID_OUTPUT" in statuses:
        return "INVALID_OUTPUT"
    if "UNKNOWN_SOURCE" in statuses:
        return "UNKNOWN_SOURCE"
    if "PASS_WITH_FALLBACK" in statuses:
        return "PASS_WITH_FALLBACK"
    return "PASS"


def _invalid_reason(raw_row: Dict[str, Any]) -> str:
    error = _norm(raw_row.get("parse_error"))
    if "Unterminated string" in error or "truncated" in error.lower() or "no_json_object_candidate" in _norm(raw_row.get("notes")):
        return "MALFORMED_OR_TRUNCATED_JSON"
    if error:
        return error
    return "INVALID_PROVIDER_OUTPUT"


def _comparison_status(base: Optional[Dict[str, Any]], treat: Optional[Dict[str, Any]]) -> str:
    if not base:
        return "MISSING_BASELINE"
    if not treat:
        return "MISSING_TREATMENT"
    base_valid = _output_valid(base)
    treat_valid = _output_valid(treat)
    if base_valid and treat_valid:
        return "PASS"
    if not base_valid and not treat_valid:
        return "BLOCKED_INVALID_OUTPUT"
    return "PARTIAL_INVALID_OUTPUT"


def _direction_transition(a: str, b: str) -> str:
    aa = _norm(a).lower()
    bb = _norm(b).lower()
    if not aa or not bb:
        return "UNKNOWN"
    if aa == bb:
        return "UNCHANGED"
    return f"{aa.upper()}_TO_{bb.upper()}"


def _confidence_transition(delta: Optional[float]) -> str:
    if delta is None:
        return "UNKNOWN"
    if abs(delta) < 0.0001:
        return "UNCHANGED"
    if delta >= 10:
        return "MATERIAL_INCREASE"
    if delta <= -10:
        return "MATERIAL_DECREASE"
    return "INCREASED" if delta > 0 else "DECREASED"


def _missing_reduced(a: Any, b: Any) -> bool:
    aa = _norm(a)
    bb = _norm(b)
    if not aa:
        return False
    if not bb:
        return True
    return len(bb) < len(aa) * 0.75


def _text_tokens(value: Any) -> Set[str]:
    text = _norm(value).lower()
    return {token for token in re.findall(r"[a-z0-9_]{4,}", text) if token not in {"with", "from", "that", "this", "market", "session", "forecast", "information"}}


def _list_text(value: Any) -> str:
    return _norm(value)


def _field_mentioned(field: str, text: str) -> bool:
    field_l = field.lower()
    text_l = _norm(text).lower()
    if field_l in text_l:
        return True
    compact_field = field_l.replace("_", " ")
    return compact_field in text_l


def _new_fields(from_level: str, to_level: str) -> List[str]:
    return [field for field in EXPECTED_FIELDS_BY_LEVEL[to_level] if field not in set(EXPECTED_FIELDS_BY_LEVEL[from_level])]


def _confidence_bucket(value: Any) -> str:
    val = _confidence_percent(value)
    if val is None:
        return "UNKNOWN"
    if val < 40:
        return "LOW"
    if val < 70:
        return "MEDIUM"
    return "HIGH"


def _move_bucket(min_value: Any, max_value: Any) -> str:
    mx = _as_float(max_value)
    if mx is None:
        return "UNKNOWN"
    if mx < 15:
        return "LOW"
    if mx < 40:
        return "MEDIUM"
    return "HIGH"


def _score_and_label(
    direction_changed: bool,
    no_signal_changed: bool,
    causal_changed: bool,
    confidence_delta: Optional[float],
    primary_changed: bool,
    secondary_changed: bool,
    info_changed: bool,
    missing_reduced: bool,
) -> Tuple[int, str]:
    material_conf = confidence_delta is not None and abs(confidence_delta) >= 10
    score = 0
    score += 3 if direction_changed else 0
    score += 2 if no_signal_changed else 0
    score += 2 if causal_changed else 0
    score += 1 if material_conf else 0
    score += 1 if primary_changed else 0
    score += 1 if secondary_changed else 0
    score += 1 if info_changed else 0
    score += 1 if missing_reduced else 0
    if direction_changed:
        label = "DIRECTION_CHANGE"
    elif no_signal_changed:
        label = "NO_SIGNAL_CHANGE"
    elif score >= 4:
        label = "MATERIAL_MULTI_DIMENSION_CHANGE"
    elif causal_changed or primary_changed or secondary_changed or info_changed:
        label = "REASONING_ONLY_CHANGE"
    elif material_conf:
        label = "CONFIDENCE_ONLY_CHANGE"
    else:
        label = "NO_CHANGE"
    return score, label


def _transition_label(
    direction_changed: bool,
    no_signal_changed: bool,
    causal_changed: bool,
    confidence_delta: Optional[float],
    primary_changed: bool,
    used_changed: bool,
    missing_reduced: bool,
    fields_changed_reasoning: Sequence[str],
    complexity: int,
) -> str:
    material_conf = confidence_delta is not None and abs(confidence_delta) >= 10
    if direction_changed and (causal_changed or primary_changed):
        return "DIRECTION_AND_REASONING_SHIFT"
    if no_signal_changed:
        return "NO_SIGNAL_TRANSITION"
    if complexity >= 5:
        return "MATERIAL_REASONING_TRANSITION"
    if causal_changed:
        return "CAUSAL_CHAIN_REWRITE"
    if primary_changed:
        return "DRIVER_REASSIGNMENT"
    if used_changed or fields_changed_reasoning:
        return "INFORMATION_USE_EXPANSION"
    if missing_reduced:
        return "INFORMATION_USE_CONTRACTION"
    if material_conf:
        return "CONFIDENCE_ONLY_TRANSITION"
    return "NO_OBSERVABLE_REASONING_CHANGE"


def _transition_interpretation(
    direction_changed: bool,
    no_signal_changed: bool,
    confidence_delta: Optional[float],
    causal_changed: bool,
    primary_changed: bool,
    fields_used: Sequence[str],
) -> str:
    if direction_changed:
        return "DIRECTION_CHANGED"
    if no_signal_changed:
        return "NO_SIGNAL_CHANGED"
    if causal_changed or primary_changed:
        return "REASONING_CHANGED_WITH_SAME_DIRECTION"
    if confidence_delta is not None and abs(confidence_delta) >= 10:
        return "CONFIDENCE_CHANGED_ONLY"
    if fields_used:
        return "REASONING_CHANGED_WITH_SAME_DIRECTION"
    return "NO_OBSERVABLE_EFFECT"


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_EXPOSURE_BEHAVIOR_COMPARE", OUTPUT_COMPARE_SHEET, "pack_exposure_behavior_compare"),
        ("PACK_EXPOSURE_REASONING_TRANSITIONS", OUTPUT_REASONING_SHEET, "pack_exposure_reasoning_transitions"),
        ("PACK_EXPOSURE_PROVIDER_TRANSITION_AUDIT", OUTPUT_PROVIDER_AUDIT_SHEET, "pack_exposure_provider_transition_audit"),
        ("PACK_EXPOSURE_FIELD_INFLUENCE_AUDIT", OUTPUT_FIELD_INFLUENCE_SHEET, "pack_exposure_field_influence_audit"),
        ("PACK_EXPOSURE_NO_SIGNAL_CONFIDENCE_AUDIT", OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET, "pack_exposure_no_signal_confidence_audit"),
        ("PACK_EXPOSURE_INVALID_OUTPUT_AUDIT", OUTPUT_INVALID_AUDIT_SHEET, "pack_exposure_invalid_output_audit"),
        ("PACK_EXPOSURE_BEHAVIOR_COMPARE_SUMMARY", OUTPUT_SUMMARY_SHEET, "pack_exposure_behavior_compare_summary"),
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
            "notes": "Phase 9A-3R no-signal normalization repair; no accuracy evaluation or provider calls.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-3 pack exposure behavior comparison.")
    return parser.parse_args(argv)


def build_pack_exposure_behavior_compare_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    run_id = _run_id(generated_ts)
    creds = load_credentials()
    service = build_sheets_service(creds)
    titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    warnings: List[str] = []

    summary_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_RUN_SUMMARY_SHEET, missing_required)
    pilot_run_id = _latest_run_id(summary_rows, "pilot_run_id")
    previous_compare_summary_rows = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, OUTPUT_SUMMARY_SHEET, warnings)
    previous_no_signal_change_count = _previous_no_signal_change_count(previous_compare_summary_rows)
    forecast_rows = _filter_run(
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_FORECASTS_SHEET, missing_required),
        "pilot_run_id",
        pilot_run_id,
    )
    metadata_rows = _filter_run(
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_METADATA_SHEET, missing_required),
        "pilot_run_id",
        pilot_run_id,
    )
    behavior_rows = _filter_run(
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_BEHAVIOR_SHEET, missing_required),
        "pilot_run_id",
        pilot_run_id,
    )
    raw_rows = _filter_run(
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_RAW_ARCHIVE_SHEET, missing_required),
        "pilot_run_id",
        pilot_run_id,
    )
    previous_no_signal_rows = _filter_run(
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET, warnings),
        "pilot_run_id",
        pilot_run_id,
    )
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_RUN_LOG_SHEET, missing_required)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_COMPARISON_DESIGN_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_PROMPT_DESIGN_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_OUTPUT_SCHEMA_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_GUARDRAILS_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_PROMPT_DRY_RUN_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_PROMPT_VALIDATION_AUDIT_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_PROMPT_VALIDATION_SUMMARY_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_LEVEL_DEFINITION_SHEET, warnings)
    level_items = _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_LEVEL_ITEMS_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_LEVEL_READINESS_SHEET, warnings)
    _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, INPUT_LEVEL_SUMMARY_SHEET, warnings)
    for sheet in OPTIONAL_INPUT_SHEETS:
        _read_optional_rows(service, DIAGNOSTICS_SPREADSHEET_ID, titles, sheet, warnings)

    if not forecast_rows or not behavior_rows or not raw_rows:
        empty_summary = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
            "behavior_compare_run_id": run_id,
            "build_status": "FAIL",
            "final_interpretation": "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_BLOCKED",
            "experiment_id": "",
            "pilot_run_id": pilot_run_id,
            "session_id": "",
            "providers_analyzed": 0,
            "pack_levels_analyzed": 0,
            "forecast_rows_read": len(forecast_rows),
            "behavior_rows_read": len(behavior_rows),
            "raw_response_rows_read": len(raw_rows),
            "valid_outputs_count": 0,
            "invalid_outputs_count": 0,
            "comparison_rows_written": 0,
            "reasoning_transition_rows_written": 0,
            "transition_rows_written": 0,
            "field_influence_rows_written": 0,
            "no_signal_confidence_rows_written": 0,
            "invalid_output_rows_written": 0,
            "direction_change_count": 0,
            "confidence_change_count": 0,
            "reasoning_change_count": 0,
            "causal_chain_change_count": 0,
            "no_signal_change_count": 0,
            "missing_information_reduced_count": 0,
            "available_field_mentions_count": 0,
            "field_used_count": 0,
            "field_discarded_count": 0,
            "field_changed_reasoning_count": 0,
            "field_no_effect_count": 0,
            "max_transition_complexity_score": 0,
            "highest_transition_complexity_provider": "",
            "highest_transition_complexity_transition": "",
            "largest_confidence_delta_provider": "",
            "largest_confidence_delta_transition": "",
            "accuracy_evaluation_count": 0,
            "provider_rerun_count": 0,
            "provider_call_count": 0,
            "forecast_generation_count": 0,
            "production_behavior_change_count": 0,
            "no_signal_unknown_count": 0,
            "no_signal_invalid_count": 0,
            "no_signal_normalization_pass_count": 0,
            "no_signal_normalization_fallback_count": 0,
            "no_signal_normalization_unknown_count": 0,
            "notes": _truncate_text(json.dumps({"missing_required": missing_required}, ensure_ascii=True), 500),
        }
        for sheet, headers, rows in [
            (OUTPUT_COMPARE_SHEET, COMPARE_HEADERS, []),
            (OUTPUT_REASONING_SHEET, REASONING_HEADERS, []),
            (OUTPUT_PROVIDER_AUDIT_SHEET, PROVIDER_AUDIT_HEADERS, []),
            (OUTPUT_FIELD_INFLUENCE_SHEET, FIELD_INFLUENCE_HEADERS, []),
            (OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET, NO_SIGNAL_HEADERS, []),
            (OUTPUT_INVALID_AUDIT_SHEET, INVALID_HEADERS, []),
            (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [empty_summary]),
        ]:
            sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
            _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
        registry = _upsert_registry_rows(service)
        return {"build_status": "FAIL", "final_interpretation": "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_BLOCKED", "registry": registry}

    experiment_id = _norm(forecast_rows[0].get("experiment_id"))
    session_id = _norm(forecast_rows[0].get("session_id"))
    forecast_by_key = {_pack_key(row): row for row in forecast_rows}
    behavior_by_key = {_pack_key(row): row for row in behavior_rows}
    raw_by_key = {_pack_key(row): row for row in raw_rows}
    meta_by_key = {_pack_key(row): row for row in metadata_rows}
    previous_no_signal_by_key = {_pack_key(row): row for row in previous_no_signal_rows}
    field_family = {row.get("candidate_field"): row.get("candidate_family") for row in level_items if _norm(row.get("candidate_field"))}

    compare_rows: List[Dict[str, Any]] = []
    reasoning_rows: List[Dict[str, Any]] = []
    provider_audit_rows: List[Dict[str, Any]] = []
    field_rows: List[Dict[str, Any]] = []
    no_signal_rows: List[Dict[str, Any]] = []
    invalid_rows: List[Dict[str, Any]] = []

    for provider in PROVIDERS:
        for pack_level in PACK_LEVELS:
            forecast = forecast_by_key.get((provider, pack_level), {})
            behavior = behavior_by_key.get((provider, pack_level), {})
            valid = _output_valid(forecast)
            conf = _confidence_percent(forecast.get("forecast_confidence"))
            ns = normalize_no_signal_flag(forecast, behavior, previous_no_signal_by_key.get((provider, pack_level)))
            no_signal_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
                    "behavior_compare_run_id": run_id,
                    "experiment_id": experiment_id,
                    "pilot_run_id": pilot_run_id,
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "output_valid": _bool_text(valid),
                    "forecast_direction": _norm(forecast.get("forecast_direction")),
                    "forecast_confidence": _fmt_num(conf),
                    "no_signal_flag": ns["value"],
                    "no_signal_reason": _truncate_text(_norm(behavior.get("no_signal_reason")), 500),
                    "expected_move_pips_min": _norm(forecast.get("expected_move_pips_min")),
                    "expected_move_pips_max": _norm(forecast.get("expected_move_pips_max")),
                    "confidence_bucket": _confidence_bucket(forecast.get("forecast_confidence")) if valid else "UNKNOWN",
                    "expected_move_bucket": _move_bucket(forecast.get("expected_move_pips_min"), forecast.get("expected_move_pips_max")) if valid else "UNKNOWN",
                    "uncertainty_sources": _truncate_text(_norm(behavior.get("uncertainty_sources")), 500),
                    "missing_information": _truncate_text(_norm(behavior.get("missing_information")), 500),
                    "notes": "" if valid else "invalid provider output",
                    "no_signal_source": ns["source"],
                    "no_signal_normalized": ns["value"],
                    "no_signal_normalization_status": ns["status"],
                }
            )

        for comparison, base_level, treat_level in COMPARISONS:
            base_f = forecast_by_key.get((provider, base_level))
            treat_f = forecast_by_key.get((provider, treat_level))
            base_b = behavior_by_key.get((provider, base_level), {})
            treat_b = behavior_by_key.get((provider, treat_level), {})
            status = _comparison_status(base_f, treat_f)
            base_valid = _output_valid(base_f)
            treat_valid = _output_valid(treat_f)
            base_ns = normalize_no_signal_flag(base_f, base_b, previous_no_signal_by_key.get((provider, base_level)))
            treat_ns = normalize_no_signal_flag(treat_f, treat_b, previous_no_signal_by_key.get((provider, treat_level)))
            if not (base_valid and treat_valid):
                score = 0
                label = "INVALID_OR_MISSING"
                conf_delta = None
                direction_changed = False
                no_signal_changed = False
                primary_changed = False
                secondary_changed = False
                causal_changed = False
                info_changed = False
                missing_reduced = False
            else:
                base_conf = _confidence_percent(base_f.get("forecast_confidence"))
                treat_conf = _confidence_percent(treat_f.get("forecast_confidence"))
                conf_delta = None if base_conf is None or treat_conf is None else treat_conf - base_conf
                direction_changed = _changed(base_f.get("forecast_direction"), treat_f.get("forecast_direction"))
                no_signal_changed = _no_signal_changed(base_ns, treat_ns)
                primary_changed = _changed(base_b.get("primary_driver_summary"), treat_b.get("primary_driver_summary"))
                secondary_changed = _changed(base_b.get("secondary_driver_summary"), treat_b.get("secondary_driver_summary"))
                causal_changed = _changed(base_b.get("causal_chain"), treat_b.get("causal_chain"))
                info_changed = _changed(base_b.get("information_used"), treat_b.get("information_used"))
                missing_reduced = _missing_reduced(base_b.get("missing_information"), treat_b.get("missing_information"))
                score, label = _score_and_label(
                    direction_changed,
                    no_signal_changed,
                    causal_changed,
                    conf_delta,
                    primary_changed,
                    secondary_changed,
                    info_changed,
                    missing_reduced,
                )
            base_move_min = _as_float(base_f.get("expected_move_pips_min") if base_f else "")
            treat_move_min = _as_float(treat_f.get("expected_move_pips_min") if treat_f else "")
            base_move_max = _as_float(base_f.get("expected_move_pips_max") if base_f else "")
            treat_move_max = _as_float(treat_f.get("expected_move_pips_max") if treat_f else "")
            compare_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
                    "behavior_compare_run_id": run_id,
                    "experiment_id": experiment_id,
                    "pilot_run_id": pilot_run_id,
                    "session_id": session_id,
                    "provider": provider,
                    "baseline_pack_level": base_level,
                    "treatment_pack_level": treat_level,
                    "comparison_pair": comparison,
                    "baseline_output_valid": _bool_text(base_valid),
                    "treatment_output_valid": _bool_text(treat_valid),
                    "comparison_status": status,
                    "forecast_direction_baseline": _norm(base_f.get("forecast_direction") if base_f else ""),
                    "forecast_direction_treatment": _norm(treat_f.get("forecast_direction") if treat_f else ""),
                    "forecast_direction_changed": _bool_text(direction_changed),
                    "forecast_confidence_baseline": _fmt_num(_confidence_percent(base_f.get("forecast_confidence") if base_f else "")),
                    "forecast_confidence_treatment": _fmt_num(_confidence_percent(treat_f.get("forecast_confidence") if treat_f else "")),
                    "forecast_confidence_delta": _fmt_num(conf_delta),
                    "forecast_confidence_changed": _bool_text(conf_delta is not None and abs(conf_delta) >= 10),
                    "expected_move_min_baseline": _norm(base_f.get("expected_move_pips_min") if base_f else ""),
                    "expected_move_min_treatment": _norm(treat_f.get("expected_move_pips_min") if treat_f else ""),
                    "expected_move_min_delta": _fmt_num(None if base_move_min is None or treat_move_min is None else treat_move_min - base_move_min),
                    "expected_move_max_baseline": _norm(base_f.get("expected_move_pips_max") if base_f else ""),
                    "expected_move_max_treatment": _norm(treat_f.get("expected_move_pips_max") if treat_f else ""),
                    "expected_move_max_delta": _fmt_num(None if base_move_max is None or treat_move_max is None else treat_move_max - base_move_max),
                    "no_signal_baseline": base_ns["value"],
                    "no_signal_treatment": treat_ns["value"],
                    "no_signal_changed": _bool_text(no_signal_changed),
                    "primary_driver_baseline": _truncate_text(_norm(base_b.get("primary_driver_summary")), 500),
                    "primary_driver_treatment": _truncate_text(_norm(treat_b.get("primary_driver_summary")), 500),
                    "primary_driver_changed": _bool_text(primary_changed),
                    "secondary_driver_baseline": _truncate_text(_norm(base_b.get("secondary_driver_summary")), 500),
                    "secondary_driver_treatment": _truncate_text(_norm(treat_b.get("secondary_driver_summary")), 500),
                    "secondary_driver_changed": _bool_text(secondary_changed),
                    "causal_chain_baseline": _truncate_text(_norm(base_b.get("causal_chain")), 700),
                    "causal_chain_treatment": _truncate_text(_norm(treat_b.get("causal_chain")), 700),
                    "causal_chain_changed": _bool_text(causal_changed),
                    "information_used_baseline": _truncate_text(_norm(base_b.get("information_used")), 500),
                    "information_used_treatment": _truncate_text(_norm(treat_b.get("information_used")), 500),
                    "information_used_changed": _bool_text(info_changed),
                    "pack_fields_used_treatment": _truncate_text(_norm(treat_b.get("pack_fields_used")), 500),
                    "pack_fields_changed_reasoning_treatment": _truncate_text(_norm(treat_b.get("pack_fields_that_changed_reasoning")), 500),
                    "pack_fields_no_effect_treatment": _truncate_text(_norm(treat_b.get("pack_fields_that_did_not_change_reasoning")), 500),
                    "missing_information_baseline": _truncate_text(_norm(base_b.get("missing_information")), 500),
                    "missing_information_treatment": _truncate_text(_norm(treat_b.get("missing_information")), 500),
                    "missing_information_reduced": _bool_text(missing_reduced),
                    "behavior_change_score": score,
                    "behavior_change_label": label,
                    "notes": "invalid output included as explicit comparison cell" if status != "PASS" else "",
                    "no_signal_source_baseline": base_ns["source"],
                    "no_signal_source_treatment": treat_ns["source"],
                    "no_signal_normalized_baseline": base_ns["value"],
                    "no_signal_normalized_treatment": treat_ns["value"],
                    "no_signal_normalization_status": _no_signal_pair_status(base_ns, treat_ns),
                }
            )

        for transition, from_level, to_level in TRANSITIONS:
            from_f = forecast_by_key.get((provider, from_level))
            to_f = forecast_by_key.get((provider, to_level))
            from_b = behavior_by_key.get((provider, from_level), {})
            to_b = behavior_by_key.get((provider, to_level), {})
            from_valid = _output_valid(from_f)
            to_valid = _output_valid(to_f)
            from_ns = normalize_no_signal_flag(from_f, from_b, previous_no_signal_by_key.get((provider, from_level)))
            to_ns = normalize_no_signal_flag(to_f, to_b, previous_no_signal_by_key.get((provider, to_level)))
            if not from_f or not to_f:
                transition_status = "MISSING_OUTPUT"
            elif not from_valid and not to_valid:
                transition_status = "PARTIAL_INVALID_OUTPUT"
            elif not from_valid:
                transition_status = "INVALID_FROM_OUTPUT"
            elif not to_valid:
                transition_status = "INVALID_TO_OUTPUT"
            else:
                transition_status = "PASS"

            if not (from_valid and to_valid):
                conf_delta = None
                direction_changed = no_signal_changed = primary_changed = secondary_changed = causal_changed = used_changed = ignored_changed = missing_reduced = False
                newly_used: List[str] = []
                newly_ignored: List[str] = []
                newly_changed: List[str] = []
                newly_no_effect: List[str] = []
                complexity = 0
                reasoning_label = "INVALID_OR_INCOMPLETE"
            else:
                from_conf = _confidence_percent(from_f.get("forecast_confidence"))
                to_conf = _confidence_percent(to_f.get("forecast_confidence"))
                conf_delta = None if from_conf is None or to_conf is None else to_conf - from_conf
                direction_changed = _changed(from_f.get("forecast_direction"), to_f.get("forecast_direction"))
                no_signal_changed = _no_signal_changed(from_ns, to_ns)
                primary_changed = _changed(from_b.get("primary_driver_summary"), to_b.get("primary_driver_summary"))
                secondary_changed = _changed(from_b.get("secondary_driver_summary"), to_b.get("secondary_driver_summary"))
                causal_changed = _changed(from_b.get("causal_chain"), to_b.get("causal_chain"))
                used_changed = _changed(from_b.get("information_used"), to_b.get("information_used"))
                ignored_changed = _changed(from_b.get("ignored_event_summary"), to_b.get("ignored_event_summary"))
                missing_reduced = _missing_reduced(from_b.get("missing_information"), to_b.get("missing_information"))
                new_fields = _new_fields(from_level, to_level)
                used_text = _norm(to_b.get("pack_fields_used"))
                discarded_text = _norm(to_b.get("pack_fields_discarded"))
                changed_text = _norm(to_b.get("pack_fields_that_changed_reasoning"))
                no_effect_text = _norm(to_b.get("pack_fields_that_did_not_change_reasoning"))
                newly_used = [field for field in new_fields if _field_mentioned(field, used_text)]
                newly_ignored = [field for field in new_fields if _field_mentioned(field, discarded_text)]
                newly_changed = [field for field in new_fields if _field_mentioned(field, changed_text)]
                newly_no_effect = [field for field in new_fields if _field_mentioned(field, no_effect_text)]
                material_conf = conf_delta is not None and abs(conf_delta) >= 10
                complexity = 0
                complexity += 3 if direction_changed else 0
                complexity += 3 if causal_changed else 0
                complexity += 2 if primary_changed else 0
                complexity += 2 if no_signal_changed else 0
                complexity += 1 if material_conf else 0
                complexity += 1 if secondary_changed else 0
                complexity += 1 if used_changed else 0
                complexity += 1 if ignored_changed else 0
                complexity += 1 if missing_reduced else 0
                complexity += 1 if newly_changed else 0
                reasoning_label = _transition_label(
                    direction_changed,
                    no_signal_changed,
                    causal_changed,
                    conf_delta,
                    primary_changed,
                    used_changed,
                    missing_reduced,
                    newly_changed,
                    complexity,
                )
            from_tokens = _text_tokens(from_b.get("causal_chain")) | _text_tokens(from_b.get("primary_driver_summary"))
            to_tokens = _text_tokens(to_b.get("causal_chain")) | _text_tokens(to_b.get("primary_driver_summary"))
            transition_summary = (
                f"{provider} {transition}: direction {_norm(from_f.get('forecast_direction') if from_f else '')} -> "
                f"{_norm(to_f.get('forecast_direction') if to_f else '')}; confidence_delta={_fmt_num(conf_delta)}; "
                f"complexity={complexity}"
            )
            reasoning_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "reasoning_transition_version": BEHAVIOR_COMPARE_VERSION,
                    "behavior_compare_run_id": run_id,
                    "experiment_id": experiment_id,
                    "pilot_run_id": pilot_run_id,
                    "session_id": session_id,
                    "provider": provider,
                    "transition": transition,
                    "from_pack_level": from_level,
                    "to_pack_level": to_level,
                    "from_output_valid": _bool_text(from_valid),
                    "to_output_valid": _bool_text(to_valid),
                    "transition_status": transition_status,
                    "direction_from": _norm(from_f.get("forecast_direction") if from_f else ""),
                    "direction_to": _norm(to_f.get("forecast_direction") if to_f else ""),
                    "direction_transition": _direction_transition(_norm(from_f.get("forecast_direction") if from_f else ""), _norm(to_f.get("forecast_direction") if to_f else "")),
                    "confidence_from": _fmt_num(_confidence_percent(from_f.get("forecast_confidence") if from_f else "")),
                    "confidence_to": _fmt_num(_confidence_percent(to_f.get("forecast_confidence") if to_f else "")),
                    "confidence_delta": _fmt_num(conf_delta),
                    "confidence_transition": _confidence_transition(conf_delta),
                    "no_signal_from": from_ns["value"],
                    "no_signal_to": to_ns["value"],
                    "no_signal_transition": "CHANGED" if no_signal_changed else "UNCHANGED",
                    "primary_driver_from": _truncate_text(_norm(from_b.get("primary_driver_summary")), 500),
                    "primary_driver_to": _truncate_text(_norm(to_b.get("primary_driver_summary")), 500),
                    "primary_driver_transition": "CHANGED" if primary_changed else "UNCHANGED",
                    "secondary_driver_from": _truncate_text(_norm(from_b.get("secondary_driver_summary")), 500),
                    "secondary_driver_to": _truncate_text(_norm(to_b.get("secondary_driver_summary")), 500),
                    "secondary_driver_transition": "CHANGED" if secondary_changed else "UNCHANGED",
                    "ignored_information_from": _truncate_text(_norm(from_b.get("ignored_event_summary")), 500),
                    "ignored_information_to": _truncate_text(_norm(to_b.get("ignored_event_summary")), 500),
                    "ignored_information_transition": "CHANGED" if ignored_changed else "UNCHANGED",
                    "used_information_from": _truncate_text(_norm(from_b.get("information_used")), 500),
                    "used_information_to": _truncate_text(_norm(to_b.get("information_used")), 500),
                    "used_information_transition": "CHANGED" if used_changed else "UNCHANGED",
                    "missing_information_from": _truncate_text(_norm(from_b.get("missing_information")), 500),
                    "missing_information_to": _truncate_text(_norm(to_b.get("missing_information")), 500),
                    "missing_information_transition": "REDUCED" if missing_reduced else ("CHANGED" if _changed(from_b.get("missing_information"), to_b.get("missing_information")) else "UNCHANGED"),
                    "causal_chain_from": _truncate_text(_norm(from_b.get("causal_chain")), 700),
                    "causal_chain_to": _truncate_text(_norm(to_b.get("causal_chain")), 700),
                    "causal_chain_transition": "CHANGED" if causal_changed else "UNCHANGED",
                    "pack_fields_newly_available": "|".join(_new_fields(from_level, to_level)),
                    "pack_fields_newly_used": "|".join(newly_used),
                    "pack_fields_newly_ignored": "|".join(newly_ignored),
                    "pack_fields_newly_changed_reasoning": "|".join(newly_changed),
                    "pack_fields_newly_no_effect": "|".join(newly_no_effect),
                    "new_reasoning_elements": "|".join(sorted(to_tokens - from_tokens)[:20]),
                    "removed_reasoning_elements": "|".join(sorted(from_tokens - to_tokens)[:20]),
                    "persistent_reasoning_elements": "|".join(sorted(from_tokens & to_tokens)[:20]),
                    "transition_complexity_score": complexity,
                    "reasoning_transition_label": reasoning_label,
                    "transition_summary": _truncate_text(transition_summary, 500),
                    "notes": "invalid output included as explicit transition cell" if transition_status != "PASS" else "",
                    "no_signal_source_from": from_ns["source"],
                    "no_signal_source_to": to_ns["source"],
                    "no_signal_normalized_from": from_ns["value"],
                    "no_signal_normalized_to": to_ns["value"],
                    "no_signal_normalization_status": _no_signal_pair_status(from_ns, to_ns),
                }
            )
            provider_audit_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
                    "behavior_compare_run_id": run_id,
                    "experiment_id": experiment_id,
                    "pilot_run_id": pilot_run_id,
                    "session_id": session_id,
                    "provider": provider,
                    "transition": transition,
                    "from_pack_level": from_level,
                    "to_pack_level": to_level,
                    "from_output_valid": _bool_text(from_valid),
                    "to_output_valid": _bool_text(to_valid),
                    "transition_status": transition_status,
                    "direction_changed": _bool_text(direction_changed),
                    "confidence_delta": _fmt_num(conf_delta),
                    "confidence_delta_abs": _fmt_num(abs(conf_delta) if conf_delta is not None else None),
                    "no_signal_changed": _bool_text(no_signal_changed),
                    "primary_driver_changed": _bool_text(primary_changed),
                    "secondary_driver_changed": _bool_text(secondary_changed),
                    "causal_chain_changed": _bool_text(causal_changed),
                    "information_used_changed": _bool_text(used_changed),
                    "missing_information_reduced": _bool_text(missing_reduced),
                    "new_pack_fields_available": "|".join(_new_fields(from_level, to_level)),
                    "new_pack_fields_used": "|".join(newly_used),
                    "new_pack_fields_discarded": "|".join(newly_ignored),
                    "new_pack_fields_changed_reasoning": "|".join(newly_changed),
                    "new_pack_fields_no_effect": "|".join(newly_no_effect),
                    "transition_interpretation": "INVALID_OR_INCOMPLETE" if transition_status != "PASS" else _transition_interpretation(direction_changed, no_signal_changed, conf_delta, causal_changed, primary_changed, newly_used),
                    "notes": "",
                }
            )

    for provider in PROVIDERS:
        for pack_level in PACK_LEVELS:
            behavior = behavior_by_key.get((provider, pack_level), {})
            forecast = forecast_by_key.get((provider, pack_level), {})
            valid = _output_valid(forecast)
            used_text = _list_text(behavior.get("pack_fields_used"))
            discard_text = _list_text(behavior.get("pack_fields_discarded"))
            changed_text = _list_text(behavior.get("pack_fields_that_changed_reasoning"))
            no_effect_text = _list_text(behavior.get("pack_fields_that_did_not_change_reasoning"))
            for field in EXPECTED_FIELDS_BY_LEVEL[pack_level]:
                used = valid and _field_mentioned(field, used_text)
                discarded = valid and _field_mentioned(field, discard_text)
                changed_reasoning = valid and _field_mentioned(field, changed_text)
                no_effect = valid and _field_mentioned(field, no_effect_text)
                if not valid:
                    influence = "INVALID_OUTPUT"
                elif used and changed_reasoning:
                    influence = "USED_AND_CHANGED_REASONING"
                elif used:
                    influence = "USED_NO_CLEAR_CHANGE"
                elif discarded:
                    influence = "EXPLICITLY_DISCARDED"
                elif no_effect:
                    influence = "EXPLICITLY_NO_EFFECT"
                else:
                    influence = "AVAILABLE_NOT_MENTIONED"
                evidence = []
                if used:
                    evidence.append("used")
                if discarded:
                    evidence.append("discarded")
                if changed_reasoning:
                    evidence.append("changed_reasoning")
                if no_effect:
                    evidence.append("no_effect")
                field_rows.append(
                    {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
                        "behavior_compare_run_id": run_id,
                        "experiment_id": experiment_id,
                        "pilot_run_id": pilot_run_id,
                        "session_id": session_id,
                        "provider": provider,
                        "pack_level": pack_level,
                        "candidate_family": field_family.get(field, ""),
                        "candidate_field": field,
                        "field_available_in_pack": "TRUE",
                        "field_reported_used": _bool_text(used),
                        "field_reported_discarded": _bool_text(discarded),
                        "field_reported_changed_reasoning": _bool_text(changed_reasoning),
                        "field_reported_no_effect": _bool_text(no_effect),
                        "influence_status": influence,
                        "evidence_text": "|".join(evidence),
                        "notes": "exact field-name matching only; no vague family-level over-attribution",
                    }
                )

    affected_by_invalid: Dict[Tuple[str, str], List[str]] = {}
    for provider in PROVIDERS:
        for comparison, base_level, treat_level in COMPARISONS:
            for level in (base_level, treat_level):
                if not _output_valid(forecast_by_key.get((provider, level))):
                    affected_by_invalid.setdefault((provider, level), []).append(comparison)
    for raw in raw_rows:
        provider, level = _pack_key(raw)
        forecast = forecast_by_key.get((provider, level), {})
        if _output_valid(forecast):
            continue
        invalid_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
                "behavior_compare_run_id": run_id,
                "experiment_id": experiment_id,
                "pilot_run_id": pilot_run_id,
                "session_id": session_id,
                "provider": provider,
                "pack_level": level,
                "raw_response_archived": "TRUE",
                "json_parse_success": _norm(raw.get("json_parse_success")),
                "json_validation_success": _norm(raw.get("json_validation_success")),
                "invalid_reason": _invalid_reason(raw),
                "affected_comparisons": "|".join(sorted(set(affected_by_invalid.get((provider, level), [])))),
                "raw_response_hash": _norm(raw.get("response_hash")),
                "repair_attempted": "FALSE",
                "provider_rerun_attempted": "FALSE",
                "recommended_handling": "TREAT_AS_INVALID_CELL",
                "notes": _truncate_text(_norm(raw.get("parse_error")), 500),
            }
        )

    direction_change_count = sum(1 for row in compare_rows if _upper(row.get("forecast_direction_changed")) == "TRUE")
    confidence_change_count = sum(1 for row in compare_rows if _upper(row.get("forecast_confidence_changed")) == "TRUE")
    reasoning_change_count = sum(1 for row in reasoning_rows if _norm(row.get("reasoning_transition_label")) not in {"NO_OBSERVABLE_REASONING_CHANGE", "INVALID_OR_INCOMPLETE"})
    causal_chain_change_count = sum(1 for row in compare_rows if _upper(row.get("causal_chain_changed")) == "TRUE")
    no_signal_change_count = sum(1 for row in compare_rows if _upper(row.get("no_signal_changed")) == "TRUE")
    no_signal_unknown_count = sum(1 for row in no_signal_rows if _upper(row.get("no_signal_normalized")) == "UNKNOWN")
    no_signal_invalid_count = sum(1 for row in no_signal_rows if _upper(row.get("no_signal_normalized")) == "INVALID")
    no_signal_normalization_pass_count = sum(1 for row in no_signal_rows if _upper(row.get("no_signal_normalization_status")) == "PASS")
    no_signal_normalization_fallback_count = sum(1 for row in no_signal_rows if _upper(row.get("no_signal_normalization_status")) == "PASS_WITH_FALLBACK")
    no_signal_normalization_unknown_count = sum(1 for row in no_signal_rows if _upper(row.get("no_signal_normalization_status")) == "UNKNOWN_SOURCE")
    missing_information_reduced_count = sum(1 for row in compare_rows if _upper(row.get("missing_information_reduced")) == "TRUE")
    field_used_count = sum(1 for row in field_rows if _upper(row.get("field_reported_used")) == "TRUE")
    field_discarded_count = sum(1 for row in field_rows if _upper(row.get("field_reported_discarded")) == "TRUE")
    field_changed_reasoning_count = sum(1 for row in field_rows if _upper(row.get("field_reported_changed_reasoning")) == "TRUE")
    field_no_effect_count = sum(1 for row in field_rows if _upper(row.get("field_reported_no_effect")) == "TRUE")
    available_field_mentions_count = field_used_count + field_discarded_count + field_changed_reasoning_count + field_no_effect_count
    max_transition = max(reasoning_rows, key=lambda row: int(row.get("transition_complexity_score") or 0), default={})
    largest_conf = max(provider_audit_rows, key=lambda row: abs(_as_float(row.get("confidence_delta")) or 0), default={})
    safety = {
        "accuracy_evaluation_count": 0,
        "provider_rerun_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "production_behavior_change_count": 0,
    }
    if any(safety.values()):
        build_status = "FAIL"
        interpretation = "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_BLOCKED"
    elif invalid_rows:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY_WITH_WARNINGS"
    else:
        build_status = "PASS"
        interpretation = "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY"

    notes_payload = {
        "warnings": sorted(set(warnings)),
        "missing_required": sorted(set(missing_required)),
        "previous_no_signal_change_count": previous_no_signal_change_count,
        "repaired_no_signal_change_count": no_signal_change_count,
        "repair_reason": "NORMALIZED_NO_SIGNAL_SOURCE_ALIGNMENT",
    }

    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "behavior_compare_version": BEHAVIOR_COMPARE_VERSION,
        "behavior_compare_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": interpretation,
        "experiment_id": experiment_id,
        "pilot_run_id": pilot_run_id,
        "session_id": session_id,
        "providers_analyzed": len(PROVIDERS),
        "pack_levels_analyzed": len(PACK_LEVELS),
        "forecast_rows_read": len(forecast_rows),
        "behavior_rows_read": len(behavior_rows),
        "raw_response_rows_read": len(raw_rows),
        "valid_outputs_count": sum(1 for row in forecast_rows if _output_valid(row)),
        "invalid_outputs_count": len(invalid_rows),
        "comparison_rows_written": len(compare_rows),
        "reasoning_transition_rows_written": len(reasoning_rows),
        "transition_rows_written": len(provider_audit_rows),
        "field_influence_rows_written": len(field_rows),
        "no_signal_confidence_rows_written": len(no_signal_rows),
        "invalid_output_rows_written": len(invalid_rows),
        "direction_change_count": direction_change_count,
        "confidence_change_count": confidence_change_count,
        "reasoning_change_count": reasoning_change_count,
        "causal_chain_change_count": causal_chain_change_count,
        "no_signal_change_count": no_signal_change_count,
        "missing_information_reduced_count": missing_information_reduced_count,
        "available_field_mentions_count": available_field_mentions_count,
        "field_used_count": field_used_count,
        "field_discarded_count": field_discarded_count,
        "field_changed_reasoning_count": field_changed_reasoning_count,
        "field_no_effect_count": field_no_effect_count,
        "max_transition_complexity_score": max_transition.get("transition_complexity_score", 0),
        "highest_transition_complexity_provider": max_transition.get("provider", ""),
        "highest_transition_complexity_transition": max_transition.get("transition", ""),
        "largest_confidence_delta_provider": largest_conf.get("provider", ""),
        "largest_confidence_delta_transition": largest_conf.get("transition", ""),
        **safety,
        "notes": _truncate_text(json.dumps(notes_payload, ensure_ascii=True), 500),
        "no_signal_unknown_count": no_signal_unknown_count,
        "no_signal_invalid_count": no_signal_invalid_count,
        "no_signal_normalization_pass_count": no_signal_normalization_pass_count,
        "no_signal_normalization_fallback_count": no_signal_normalization_fallback_count,
        "no_signal_normalization_unknown_count": no_signal_normalization_unknown_count,
    }

    for sheet, headers, rows in [
        (OUTPUT_COMPARE_SHEET, COMPARE_HEADERS, compare_rows),
        (OUTPUT_REASONING_SHEET, REASONING_HEADERS, reasoning_rows),
        (OUTPUT_PROVIDER_AUDIT_SHEET, PROVIDER_AUDIT_HEADERS, provider_audit_rows),
        (OUTPUT_FIELD_INFLUENCE_SHEET, FIELD_INFLUENCE_HEADERS, field_rows),
        (OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET, NO_SIGNAL_HEADERS, no_signal_rows),
        (OUTPUT_INVALID_AUDIT_SHEET, INVALID_HEADERS, invalid_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "behavior_compare_run_id": run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "sheets_written": {
            OUTPUT_COMPARE_SHEET: len(compare_rows),
            OUTPUT_REASONING_SHEET: len(reasoning_rows),
            OUTPUT_PROVIDER_AUDIT_SHEET: len(provider_audit_rows),
            OUTPUT_FIELD_INFLUENCE_SHEET: len(field_rows),
            OUTPUT_NO_SIGNAL_CONFIDENCE_SHEET: len(no_signal_rows),
            OUTPUT_INVALID_AUDIT_SHEET: len(invalid_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "providers_analyzed": summary["providers_analyzed"],
        "pack_levels_analyzed": summary["pack_levels_analyzed"],
        "valid_outputs_count": summary["valid_outputs_count"],
        "invalid_outputs_count": summary["invalid_outputs_count"],
        "comparison_rows_written": summary["comparison_rows_written"],
        "reasoning_transition_rows_written": summary["reasoning_transition_rows_written"],
        "transition_rows_written": summary["transition_rows_written"],
        "field_influence_rows_written": summary["field_influence_rows_written"],
        "direction_change_count": direction_change_count,
        "confidence_change_count": confidence_change_count,
        "reasoning_change_count": reasoning_change_count,
        "causal_chain_change_count": causal_chain_change_count,
        "no_signal_change_count": no_signal_change_count,
        "previous_no_signal_change_count": previous_no_signal_change_count,
        "no_signal_unknown_count": summary["no_signal_unknown_count"],
        "no_signal_invalid_count": summary["no_signal_invalid_count"],
        "no_signal_normalization_pass_count": summary["no_signal_normalization_pass_count"],
        "no_signal_normalization_fallback_count": summary["no_signal_normalization_fallback_count"],
        "no_signal_normalization_unknown_count": summary["no_signal_normalization_unknown_count"],
        "missing_information_reduced_count": missing_information_reduced_count,
        "field_used_count": field_used_count,
        "field_discarded_count": field_discarded_count,
        "field_changed_reasoning_count": field_changed_reasoning_count,
        "field_no_effect_count": field_no_effect_count,
        "max_transition_complexity_score": summary["max_transition_complexity_score"],
        "highest_transition_complexity_provider": summary["highest_transition_complexity_provider"],
        "highest_transition_complexity_transition": summary["highest_transition_complexity_transition"],
        "accuracy_evaluation_count": summary["accuracy_evaluation_count"],
        "provider_rerun_count": summary["provider_rerun_count"],
        "provider_call_count": summary["provider_call_count"],
        "forecast_generation_count": summary["forecast_generation_count"],
        "production_behavior_change_count": summary["production_behavior_change_count"],
        "registry": registry,
        "warnings": sorted(set(warnings)),
        "missing_required": sorted(set(missing_required)),
        "summary": summary,
    }


def main() -> None:
    result = build_pack_exposure_behavior_compare_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
