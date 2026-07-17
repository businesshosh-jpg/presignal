import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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
from automation.build_pack_exposure_behavior_compare_v0 import (
    COMPARISONS,
    TRANSITIONS,
    _as_float,
    _confidence_bucket,
    _confidence_percent,
    _confidence_transition,
    _direction_transition,
    _field_mentioned,
    _fmt_num,
    _missing_reduced,
    _move_bucket,
    _new_fields,
    _no_signal_changed,
    _no_signal_pair_status,
    _score_and_label,
    _text_tokens,
    _transition_interpretation,
    _transition_label,
    normalize_no_signal_flag,
)
from automation.build_pack_exposure_pilot_run_v0 import (
    AUTOMATION_PROVIDER_FUNCTION,
    BEHAVIOR_HEADERS as PILOT_BEHAVIOR_HEADERS,
    FORECAST_HEADERS as PILOT_FORECAST_HEADERS,
    METADATA_HEADERS as PILOT_METADATA_HEADERS,
    PROVIDER_ORDER,
    RAW_ARCHIVE_HEADERS as PILOT_RAW_ARCHIVE_HEADERS,
    RUN_LOG_HEADERS as PILOT_RUN_LOG_HEADERS,
    _base_metadata,
    _build_provider_prompt,
    _call_live_provider_raw,
    _config_map,
    _jsonish,
    _parse_provider_json,
    _provider_map,
)
from automation.build_pack_exposure_prompt_validation_v0 import (
    ACTIVE_PACK_LEVELS,
    EXPECTED_FIELDS_BY_LEVEL,
    _attention_history_index,
    _build_event_context,
    _build_market_state_context,
    _event_index,
    _filter_by_run,
    _get_sheet_titles,
    _group_prompt_rows,
    _guardrail_payload,
    _latest_run_id,
    _member_index,
    _read_optional_rows,
    _schema_payload,
    _sha256_text,
    _shadow_index,
    _split_pipe,
)
from automation.build_session_forecasts_v0 import (
    _normalize_confidence,
    _normalize_forecast_direction,
    _normalize_holding_minutes,
    _normalize_numeric_value,
)
from automation.build_session_information_requests_v0 import _iso_now, _normalize_provider_name, _truncate_text
from automation.collect_mechanism_evaluation_population_shadow_v0 import collect_tier2_preoutcome_record
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
)


INPUT_TIER2_EXPERIMENT_DESIGN = "Pack_Behavior_Tier2_Experiment_Design"
INPUT_TIER2_HYPOTHESIS_PLAN = "Pack_Behavior_Tier2_Hypothesis_Test_Plan"
INPUT_TIER2_SESSION_STRATEGY = "Pack_Behavior_Tier2_Session_Strategy"
INPUT_TIER2_CALL_BUDGET = "Pack_Behavior_Tier2_Call_Budget"
INPUT_TIER2_STOP_RULES = "Pack_Behavior_Tier2_Stop_Rules"
INPUT_TIER2_SUCCESS_CRITERIA = "Pack_Behavior_Tier2_Success_Criteria"
INPUT_TIER2_READINESS = "Pack_Behavior_Tier2_Readiness_Audit"
INPUT_TIER2_DESIGN_SUMMARY = "Pack_Behavior_Tier2_Design_Summary"
INPUT_EXEC_PLAN_SUMMARY = "Pack_Behavior_Tier2_Execution_Plan_Summary"
INPUT_SESSION_EXECUTION_ORDER = "Pack_Behavior_Tier2_Session_Execution_Order"
INPUT_EXECUTION_READINESS = "Pack_Behavior_Tier2_Execution_Readiness"
INPUT_SESSION_ELIGIBILITY_AUDIT = "Pack_Behavior_Tier2_Session_Eligibility_Audit"
INPUT_PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
INPUT_OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
INPUT_GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
INPUT_PROMPT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Design_Summary"
INPUT_VALIDATION_SUMMARY_SHEET = "Pack_Exposure_Prompt_Validation_Summary"
INPUT_LEVEL_ITEMS_SHEET = "Market_State_Pack_Level_Items"
INPUT_LEVEL_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
INPUT_SHADOW_SHEET = "Market_State_Pack_Shadow"
INPUT_SHADOW_SUMMARY_SHEET = "Market_State_Pack_Shadow_Summary"
INPUT_SESSIONS_SHEET = "Market_Sessions"
INPUT_MEMBERS_SHEET = "Market_Session_Members"
INPUT_ATTENTION_HISTORY_SHEET = "Session_Attention_Map_History"
INPUT_PILOT_SUMMARY_SHEET = "Pack_Exposure_Run_Summary"
MAIN_EVENT_SHEET = "Event"
MAIN_CONFIG_SHEET = "Config"

OUTPUT_RUNS_SHEET = "Pack_Behavior_Tier2_Runs"
OUTPUT_FORECASTS_SHEET = "Pack_Behavior_Tier2_Forecasts"
OUTPUT_METADATA_SHEET = "Pack_Behavior_Tier2_Metadata"
OUTPUT_BEHAVIOR_SHEET = "Pack_Behavior_Tier2_Behavior"
OUTPUT_RAW_ARCHIVE_SHEET = "Pack_Behavior_Tier2_Raw_Response_Archive"
OUTPUT_TRANSITIONS_SHEET = "Pack_Behavior_Tier2_Transitions"
OUTPUT_FIELD_INFLUENCE_SHEET = "Pack_Behavior_Tier2_Field_Influence"
OUTPUT_NO_SIGNAL_SHEET = "Pack_Behavior_Tier2_NoSignal"
OUTPUT_INVALID_SHEET = "Pack_Behavior_Tier2_Invalid_Output"
OUTPUT_CHECKPOINT_SHEET = "Pack_Behavior_Tier2_Checkpoint_Log"
OUTPUT_RUN_LOG_SHEET = "Pack_Behavior_Tier2_Run_Log"
OUTPUT_SUMMARY_SHEET = "Pack_Behavior_Tier2_Run_Summary"

SCHEMA_VERSION = "presignal_v2_behavior_tier2_execution_0.1"
EXECUTION_VERSION = "behavior_tier2_execution_v0"
EXPERIMENT_ID = "pack_behavior_tier2"
RUN_TYPE = "behavior_pattern_expansion_tier2"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4ZY"
EXECUTION_PHASE = "Phase 9A-4ZY"
EXECUTION_MODE = "TIER2_BEHAVIOR_PATTERN_EXPANSION"
GOVERNANCE_APPROVAL_PHASE = "Phase 9A-4ZX"
EXECUTION_TIER = "TIER_2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_TIER2_BEHAVIOR_PATTERN_EXECUTION"
REGISTRY_OWNER_MODULE = "market_state"
MAX_PROVIDER_CALLS = 120
TARGET_SESSION_COUNT = 8

FORECAST_HEADERS = [
    h if h != "pilot_run_id" else "discovery_run_id" for h in PILOT_FORECAST_HEADERS
] + ["execution_run_id", "execution_phase", "execution_mode", "execution_tier", "governance_approval_phase", "approved_provider_call_cap", "provider_retry_count_allowed", "accuracy_evaluation_allowed", "production_visible", "shadow_only", "campaign_tier", "source_execution_plan_sheet", "hypothesis_coverage"]
METADATA_HEADERS = [
    h if h != "pilot_run_id" else "discovery_run_id" for h in PILOT_METADATA_HEADERS
] + ["execution_run_id", "execution_phase", "execution_mode", "execution_tier", "governance_approval_phase", "approved_provider_call_cap", "provider_retry_count_allowed", "accuracy_evaluation_allowed", "production_visible", "shadow_only", "campaign_tier", "source_execution_plan_sheet", "hypothesis_coverage"]
BEHAVIOR_HEADERS = [
    h if h != "pilot_run_id" else "discovery_run_id" for h in PILOT_BEHAVIOR_HEADERS
] + ["execution_run_id", "execution_phase", "execution_mode", "execution_tier", "governance_approval_phase", "approved_provider_call_cap", "provider_retry_count_allowed", "accuracy_evaluation_allowed", "production_visible", "shadow_only", "output_valid", "invalid_reason", "campaign_tier", "source_execution_plan_sheet", "hypothesis_coverage"]
RAW_ARCHIVE_HEADERS = [
    h if h != "pilot_run_id" else "discovery_run_id" for h in PILOT_RAW_ARCHIVE_HEADERS
] + ["execution_run_id", "execution_phase", "execution_mode", "execution_tier", "governance_approval_phase", "approved_provider_call_cap", "provider_retry_count_allowed", "accuracy_evaluation_allowed", "production_visible", "shadow_only", "raw_response_archive_key", "raw_response_hash", "archive_write_status", "recommended_handling"]
RUN_LOG_HEADERS = [
    h if h != "pilot_run_id" else "discovery_run_id" for h in PILOT_RUN_LOG_HEADERS
] + ["execution_run_id", "execution_phase", "execution_mode", "execution_tier", "governance_approval_phase", "approved_provider_call_cap", "provider_retry_count_allowed", "accuracy_evaluation_allowed", "production_visible", "shadow_only", "campaign_tier", "call_sequence", "provider_call_made"]

RUNS_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "execution_phase",
    "execution_mode",
    "execution_tier",
    "governance_approval_phase",
    "approved_provider_call_cap",
    "provider_retry_count_allowed",
    "accuracy_evaluation_allowed",
    "production_visible",
    "shadow_only",
    "campaign_tier",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "session_selection_status",
    "pack_levels_executed",
    "providers_executed",
    "planned_provider_calls",
    "provider_calls_attempted",
    "provider_calls_succeeded",
    "provider_calls_failed",
    "raw_responses_archived",
    "invalid_outputs",
    "status",
    "notes",
]

TRANSITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "campaign_tier",
    "session_id",
    "provider",
    "transition",
    "from_pack_level",
    "to_pack_level",
    "from_output_valid",
    "to_output_valid",
    "transition_status",
    "direction_from",
    "direction_to",
    "direction_transition",
    "confidence_from",
    "confidence_to",
    "confidence_delta",
    "confidence_transition",
    "no_signal_from",
    "no_signal_to",
    "no_signal_transition",
    "no_signal_normalization_status",
    "primary_driver_transition",
    "secondary_driver_transition",
    "used_information_transition",
    "ignored_information_transition",
    "missing_information_transition",
    "causal_chain_transition",
    "pack_fields_newly_available",
    "pack_fields_newly_used",
    "pack_fields_newly_discarded",
    "pack_fields_newly_changed_reasoning",
    "pack_fields_newly_no_effect",
    "new_reasoning_elements",
    "removed_reasoning_elements",
    "persistent_reasoning_elements",
    "behavior_change_score",
    "transition_complexity_score",
    "reasoning_transition_label",
    "transition_interpretation",
    "notes",
]

FIELD_INFLUENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "campaign_tier",
    "session_id",
    "provider",
    "pack_level",
    "candidate_family",
    "candidate_field",
    "field_available_in_pack",
    "field_reported_used",
    "field_reported_discarded",
    "field_reported_changed_reasoning",
    "field_reported_no_effect",
    "influence_status",
    "evidence_text",
    "notes",
]

NO_SIGNAL_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "campaign_tier",
    "session_id",
    "provider",
    "pack_level",
    "output_valid",
    "forecast_direction",
    "forecast_confidence",
    "no_signal_flag",
    "no_signal_reason",
    "no_signal_source",
    "no_signal_normalization_status",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "confidence_bucket",
    "expected_move_bucket",
    "uncertainty_sources",
    "missing_information",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "campaign_tier",
    "session_id",
    "provider",
    "pack_level",
    "raw_response_archived",
    "json_parse_success",
    "json_validation_success",
    "invalid_reason",
    "raw_response_hash",
    "repair_attempted",
    "provider_rerun_attempted",
    "recommended_handling",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "build_status",
    "final_interpretation",
    "execution_phase",
    "execution_mode",
    "execution_tier",
    "governance_approval_phase",
    "approved_session_count",
    "approved_provider_call_cap",
    "provider_retry_count_allowed",
    "accuracy_evaluation_allowed",
    "production_visible",
    "shadow_only",
    "campaign_tier",
    "sessions_planned",
    "sessions_executed",
    "session_ids_executed",
    "providers_executed",
    "pack_levels_executed",
    "expected_provider_calls",
    "maximum_provider_calls",
    "provider_call_cap",
    "provider_calls_attempted",
    "provider_calls_succeeded",
    "provider_calls_failed",
    "raw_responses_archived",
    "raw_archive_append_failure_count",
    "raw_archive_dedupe_count",
    "raw_archive_created_before_calls",
    "invalid_outputs",
    "invalid_output_count",
    "invalid_output_rate",
    "hold_rule_trigger_count",
    "stop_rule_trigger_count",
    "json_validation_success_count",
    "json_validation_failure_count",
    "forecast_rows_captured",
    "behavior_rows_captured",
    "transition_rows_captured",
    "field_influence_rows_captured",
    "no_signal_rows_captured",
    "metadata_rows_written",
    "checkpoint_rows_captured",
    "run_log_rows_written",
    "accuracy_evaluation_count",
    "provider_call_count",
    "provider_rerun_count",
    "forecast_generation_count",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "routing_changes",
    "weight_changes",
    "ensemble_changes",
    "predictions_write_count",
    "evaluation_write_count",
    "outcome_ledger_write_count",
    "mr_provider_runs_write_count",
    "recommended_next_step",
    "hypothesis_coverage_summary",
    "notes",
]

CHECKPOINT_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_version",
    "discovery_run_id",
    "execution_run_id",
    "checkpoint_id",
    "checkpoint_name",
    "checkpoint_sequence",
    "provider_calls_attempted_so_far",
    "raw_responses_archived_so_far",
    "forecast_rows_so_far",
    "behavior_rows_so_far",
    "invalid_outputs_so_far",
    "archive_completeness",
    "provider_call_cap_remaining",
    "stop_rules_triggered",
    "hold_rules_triggered",
    "production_write_count",
    "accuracy_evaluation_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _execution_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_tier2_execution_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _filter_existing_run_rows(rows: Sequence[Dict[str, Any]], run_id: str) -> List[Dict[str, Any]]:
    return [row for row in rows if _norm(row.get("discovery_run_id")) == run_id]


def _existing_discovery_sessions(rows: Sequence[Dict[str, Any]]) -> Set[str]:
    sessions: Set[str] = set()
    for row in rows:
        for session_id in _norm(row.get("session_ids_executed")).split("|"):
            if session_id:
                sessions.add(session_id)
        if _norm(row.get("session_id")):
            sessions.add(_norm(row.get("session_id")))
    return sessions


def _complete_shadow_sessions(shadow_rows: Sequence[Dict[str, Any]]) -> List[Tuple[str, str]]:
    required = set(EXPECTED_FIELDS_BY_LEVEL["E"])
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = {}
    session_dates: Dict[str, str] = {}
    for row in shadow_rows:
        session_id = _norm(row.get("session_id"))
        field = _norm(row.get("candidate_field"))
        if not session_id or field not in required:
            continue
        by_session.setdefault(session_id, {})[field] = row
        session_dates.setdefault(session_id, _norm(row.get("session_date")))
    candidates: List[Tuple[str, str]] = []
    for session_id, fields in by_session.items():
        if set(fields) != required:
            continue
        if all(
            _upper(row.get("data_available_flag")) == "TRUE"
            and _upper(row.get("leakage_check_status")) != "FAIL"
            and _upper(row.get("provider_visible")) != "TRUE"
            and _upper(row.get("used_in_forecast")) != "TRUE"
            for row in fields.values()
        ):
            candidates.append((session_dates.get(session_id, ""), session_id))
    candidates.sort()
    return candidates


def _select_tier2_sessions(
    shadow_rows: Sequence[Dict[str, Any]],
    execution_order_rows: Sequence[Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    planned = [
        _norm(row.get("session_id"))
        for row in sorted(execution_order_rows, key=lambda row: int(_norm(row.get("execution_sequence")) or "999999"))
        if _norm(row.get("session_id"))
    ]
    planned_set = set(planned)
    complete = {session_id for _, session_id in _complete_shadow_sessions(shadow_rows)}
    notes: List[str] = []
    missing_complete = sorted(planned_set - complete)
    if missing_complete:
        notes.append(f"planned_sessions_missing_complete_shadow={ '|'.join(missing_complete) }")
    selected = [session_id for session_id in planned if session_id in complete]
    return selected[:TARGET_SESSION_COUNT], notes


def _json_value(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True)
    return _norm(value)


def _row_key(row: Dict[str, Any]) -> Tuple[str, str, str]:
    return (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider")), _norm(row.get("pack_level")))


def _valid(row: Optional[Dict[str, Any]]) -> bool:
    return bool(row) and _upper(row.get("json_validation_success")) == "TRUE"


def _field_family_map(level_items: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {_norm(row.get("candidate_field")): _norm(row.get("candidate_family")) for row in level_items if _norm(row.get("candidate_field"))}


def _invalid_reason(raw_row: Dict[str, Any]) -> str:
    err = _norm(raw_row.get("parse_error"))
    if "unterminated" in err.lower() or "truncated" in err.lower() or "no_json_object_candidate" in _norm(raw_row.get("notes")):
        return "MALFORMED_OR_TRUNCATED_JSON"
    return err or "INVALID_PROVIDER_OUTPUT"


def _execution_fields(
    discovery_run_id: str,
    hypothesis_coverage: str = "",
    provider_call_cap: int = MAX_PROVIDER_CALLS,
) -> Dict[str, Any]:
    return {
        "execution_run_id": discovery_run_id,
        "execution_phase": EXECUTION_PHASE,
        "execution_mode": EXECUTION_MODE,
        "execution_tier": EXECUTION_TIER,
        "governance_approval_phase": GOVERNANCE_APPROVAL_PHASE,
        "approved_provider_call_cap": provider_call_cap,
        "provider_retry_count_allowed": 0,
        "accuracy_evaluation_allowed": "FALSE",
        "production_visible": "FALSE",
        "shadow_only": "TRUE",
        "campaign_tier": "TIER_2_BEHAVIOR_PATTERN_EXPANSION",
        "source_execution_plan_sheet": INPUT_EXEC_PLAN_SUMMARY,
        "hypothesis_coverage": hypothesis_coverage,
    }


def _capture_prospective_mechanism_evidence(
    *,
    discovery_run_id: str,
    session_meta: Dict[str, Any],
    forecast_row: Dict[str, Any],
    behavior_row: Dict[str, Any],
    raw_response_archive_key: str,
    capture_timestamp: str,
    eligible_session: bool = True,
    collection_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the non-blocking prospective collector at the Tier 2 persistence edge.

    Tier 2 remains the authoritative producer of mechanism-relevant Pack A-E
    observations. Collector failures are fail-closed for research evidence but
    never alter the already-produced shadow forecast or provider result.
    """

    if not eligible_session:
        return {
            "collection_status": "SKIPPED_INELIGIBLE_SESSION",
            "failure_code": "SESSION_NOT_ELIGIBLE_FOR_PROSPECTIVE_COLLECTION",
            "record_written": False,
        }
    kwargs: Dict[str, Any] = {
        "collection_run_id": discovery_run_id,
        "session_meta": session_meta,
        "forecast_row": forecast_row,
        "behavior_row": behavior_row,
        "raw_provider_output_reference": raw_response_archive_key,
        "capture_timestamp": capture_timestamp,
    }
    if collection_root is not None:
        kwargs["output_root"] = collection_root
    try:
        return collect_tier2_preoutcome_record(**kwargs)
    except Exception as exc:
        return {
            "collection_status": "COLLECTOR_FAILED_ISOLATED",
            "failure_code": f"COLLECTOR_RUNTIME_FAILURE:{type(exc).__name__}",
            "failure_detail": _truncate_text(str(exc), 500),
            "record_written": False,
        }


def _merge_session_timing_metadata(
    session_meta_by_id: Dict[str, Dict[str, Any]], session_rows: Sequence[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """Carry frozen Market_Sessions timing into the Tier 2 collector context.

    Market_State_Pack_Shadow deliberately contains prompt-facing metadata only.
    The prospective collector also needs the frozen session window timestamps to
    prove that capture is pre-outcome, so this exact-session-ID merge preserves
    those source fields without changing any prompt or classification input.
    """

    timing_fields = (
        "session_start_ts",
        "session_end_ts",
        "primary_release_ts",
        "last_release_ts",
    )
    timing_by_session: Dict[str, Dict[str, str]] = {}
    for row in session_rows:
        session_id = _norm(row.get("session_id"))
        if not session_id:
            continue
        candidate = {field: _norm(row.get(field)) for field in timing_fields}
        existing = timing_by_session.get(session_id)
        if existing is not None and existing != candidate:
            raise RuntimeError(
                "SESSION_TIMING_IDENTITY_AMBIGUOUS:"
                f"session_id={session_id}; exact Market_Sessions timing rows disagree"
            )
        timing_by_session[session_id] = candidate

    merged: Dict[str, Dict[str, Any]] = {}
    for session_id, metadata in session_meta_by_id.items():
        target = dict(metadata)
        for field, value in timing_by_session.get(session_id, {}).items():
            if value:
                target[field] = value
        merged[session_id] = target
    return merged


def _build_transitions(
    generated_ts: str,
    discovery_run_id: str,
    forecast_rows: Sequence[Dict[str, Any]],
    behavior_rows: Sequence[Dict[str, Any]],
    providers: Sequence[str] = PROVIDER_ORDER,
) -> List[Dict[str, Any]]:
    forecast_by_key = {_row_key(row): row for row in forecast_rows}
    behavior_by_key = {_row_key(row): row for row in behavior_rows}
    rows: List[Dict[str, Any]] = []
    sessions = sorted({_norm(row.get("session_id")) for row in forecast_rows if _norm(row.get("session_id"))})
    for session_id in sessions:
        for provider in providers:
            for transition, from_level, to_level in TRANSITIONS:
                from_f = forecast_by_key.get((session_id, provider, from_level), {})
                to_f = forecast_by_key.get((session_id, provider, to_level), {})
                from_b = behavior_by_key.get((session_id, provider, from_level), {})
                to_b = behavior_by_key.get((session_id, provider, to_level), {})
                from_valid = _valid(from_f)
                to_valid = _valid(to_f)
                if not from_f or not to_f:
                    status = "MISSING_OUTPUT"
                elif not from_valid and not to_valid:
                    status = "PARTIAL_INVALID_OUTPUT"
                elif not from_valid:
                    status = "INVALID_FROM_OUTPUT"
                elif not to_valid:
                    status = "INVALID_TO_OUTPUT"
                else:
                    status = "PASS"
                from_ns = normalize_no_signal_flag(from_f, from_b)
                to_ns = normalize_no_signal_flag(to_f, to_b)
                conf_delta = None
                direction_changed = no_signal_changed = primary_changed = secondary_changed = causal_changed = used_changed = ignored_changed = missing_reduced = False
                newly_used: List[str] = []
                newly_discarded: List[str] = []
                newly_changed: List[str] = []
                newly_no_effect: List[str] = []
                behavior_score = 0
                complexity = 0
                label = "INVALID_OR_INCOMPLETE"
                interpretation = "INVALID_OR_INCOMPLETE"
                if from_valid and to_valid:
                    from_conf = _confidence_percent(from_f.get("forecast_confidence"))
                    to_conf = _confidence_percent(to_f.get("forecast_confidence"))
                    conf_delta = None if from_conf is None or to_conf is None else to_conf - from_conf
                    direction_changed = _norm(from_f.get("forecast_direction")).lower() != _norm(to_f.get("forecast_direction")).lower()
                    no_signal_changed = _no_signal_changed(from_ns, to_ns)
                    primary_changed = _norm(from_b.get("primary_driver_summary")).lower() != _norm(to_b.get("primary_driver_summary")).lower()
                    secondary_changed = _norm(from_b.get("secondary_driver_summary")).lower() != _norm(to_b.get("secondary_driver_summary")).lower()
                    causal_changed = _norm(from_b.get("causal_chain")).lower() != _norm(to_b.get("causal_chain")).lower()
                    used_changed = _norm(from_b.get("information_used")).lower() != _norm(to_b.get("information_used")).lower()
                    ignored_changed = _norm(from_b.get("ignored_event_summary")).lower() != _norm(to_b.get("ignored_event_summary")).lower()
                    missing_reduced = _missing_reduced(from_b.get("missing_information"), to_b.get("missing_information"))
                    new_fields = _new_fields(from_level, to_level)
                    newly_used = [field for field in new_fields if _field_mentioned(field, to_b.get("pack_fields_used"))]
                    newly_discarded = [field for field in new_fields if _field_mentioned(field, to_b.get("pack_fields_discarded"))]
                    newly_changed = [field for field in new_fields if _field_mentioned(field, to_b.get("pack_fields_that_changed_reasoning"))]
                    newly_no_effect = [field for field in new_fields if _field_mentioned(field, to_b.get("pack_fields_that_did_not_change_reasoning"))]
                    behavior_score, _ = _score_and_label(direction_changed, no_signal_changed, causal_changed, conf_delta, primary_changed, secondary_changed, used_changed, missing_reduced)
                    material_conf = conf_delta is not None and abs(conf_delta) >= 10
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
                    label = _transition_label(direction_changed, no_signal_changed, causal_changed, conf_delta, primary_changed, used_changed, missing_reduced, newly_changed, complexity)
                    interpretation = _transition_interpretation(direction_changed, no_signal_changed, conf_delta, causal_changed, primary_changed, newly_used)
                from_tokens = _text_tokens(from_b.get("causal_chain")) | _text_tokens(from_b.get("primary_driver_summary"))
                to_tokens = _text_tokens(to_b.get("causal_chain")) | _text_tokens(to_b.get("primary_driver_summary"))
                rows.append(
                    {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "execution_version": EXECUTION_VERSION,
                        "discovery_run_id": discovery_run_id,
                        "execution_run_id": discovery_run_id,
                        "campaign_tier": "TIER_2_BEHAVIOR_PATTERN_EXPANSION",
                        "session_id": session_id,
                        "provider": provider,
                        "transition": transition,
                        "from_pack_level": from_level,
                        "to_pack_level": to_level,
                        "from_output_valid": "TRUE" if from_valid else "FALSE",
                        "to_output_valid": "TRUE" if to_valid else "FALSE",
                        "transition_status": status,
                        "direction_from": _norm(from_f.get("forecast_direction")),
                        "direction_to": _norm(to_f.get("forecast_direction")),
                        "direction_transition": _direction_transition(from_f.get("forecast_direction"), to_f.get("forecast_direction")),
                        "confidence_from": _fmt_num(_confidence_percent(from_f.get("forecast_confidence"))),
                        "confidence_to": _fmt_num(_confidence_percent(to_f.get("forecast_confidence"))),
                        "confidence_delta": _fmt_num(conf_delta),
                        "confidence_transition": _confidence_transition(conf_delta),
                        "no_signal_from": from_ns["value"],
                        "no_signal_to": to_ns["value"],
                        "no_signal_transition": "CHANGED" if no_signal_changed else "UNCHANGED",
                        "no_signal_normalization_status": _no_signal_pair_status(from_ns, to_ns),
                        "primary_driver_transition": "CHANGED" if primary_changed else "UNCHANGED",
                        "secondary_driver_transition": "CHANGED" if secondary_changed else "UNCHANGED",
                        "used_information_transition": "CHANGED" if used_changed else "UNCHANGED",
                        "ignored_information_transition": "CHANGED" if ignored_changed else "UNCHANGED",
                        "missing_information_transition": "REDUCED" if missing_reduced else "UNCHANGED",
                        "causal_chain_transition": "CHANGED" if causal_changed else "UNCHANGED",
                        "pack_fields_newly_available": "|".join(_new_fields(from_level, to_level)),
                        "pack_fields_newly_used": "|".join(newly_used),
                        "pack_fields_newly_discarded": "|".join(newly_discarded),
                        "pack_fields_newly_changed_reasoning": "|".join(newly_changed),
                        "pack_fields_newly_no_effect": "|".join(newly_no_effect),
                        "new_reasoning_elements": "|".join(sorted(to_tokens - from_tokens)[:20]),
                        "removed_reasoning_elements": "|".join(sorted(from_tokens - to_tokens)[:20]),
                        "persistent_reasoning_elements": "|".join(sorted(from_tokens & to_tokens)[:20]),
                        "behavior_change_score": behavior_score,
                        "transition_complexity_score": complexity,
                        "reasoning_transition_label": label,
                        "transition_interpretation": interpretation,
                        "notes": "invalid output included as explicit cell" if status != "PASS" else "",
                    }
                )
    return rows


def _build_field_influence(
    generated_ts: str,
    discovery_run_id: str,
    forecast_rows: Sequence[Dict[str, Any]],
    behavior_rows: Sequence[Dict[str, Any]],
    family_map: Dict[str, str],
) -> List[Dict[str, Any]]:
    forecast_by_key = {_row_key(row): row for row in forecast_rows}
    behavior_by_key = {_row_key(row): row for row in behavior_rows}
    rows: List[Dict[str, Any]] = []
    for session_id, provider, pack_level in sorted(forecast_by_key):
        forecast = forecast_by_key[(session_id, provider, pack_level)]
        behavior = behavior_by_key.get((session_id, provider, pack_level), {})
        valid = _valid(forecast)
        for field in EXPECTED_FIELDS_BY_LEVEL.get(pack_level, []):
            used = valid and _field_mentioned(field, behavior.get("pack_fields_used"))
            discarded = valid and _field_mentioned(field, behavior.get("pack_fields_discarded"))
            changed = valid and _field_mentioned(field, behavior.get("pack_fields_that_changed_reasoning"))
            no_effect = valid and _field_mentioned(field, behavior.get("pack_fields_that_did_not_change_reasoning"))
            if not valid:
                status = "INVALID_OUTPUT"
            elif used and changed:
                status = "USED_AND_CHANGED_REASONING"
            elif used:
                status = "USED_NO_CLEAR_CHANGE"
            elif discarded:
                status = "EXPLICITLY_DISCARDED"
            elif no_effect:
                status = "EXPLICITLY_NO_EFFECT"
            else:
                status = "AVAILABLE_NOT_MENTIONED"
            rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "execution_version": EXECUTION_VERSION,
                    "discovery_run_id": discovery_run_id,
                    "execution_run_id": discovery_run_id,
                    "campaign_tier": "TIER_2_BEHAVIOR_PATTERN_EXPANSION",
                    "session_id": session_id,
                    "provider": provider,
                    "pack_level": pack_level,
                    "candidate_family": family_map.get(field, ""),
                    "candidate_field": field,
                    "field_available_in_pack": "TRUE",
                    "field_reported_used": "TRUE" if used else "FALSE",
                    "field_reported_discarded": "TRUE" if discarded else "FALSE",
                    "field_reported_changed_reasoning": "TRUE" if changed else "FALSE",
                    "field_reported_no_effect": "TRUE" if no_effect else "FALSE",
                    "influence_status": status,
                    "evidence_text": "|".join([label for label, flag in [("used", used), ("discarded", discarded), ("changed_reasoning", changed), ("no_effect", no_effect)] if flag]),
                    "notes": "exact field-name matching only; no vague family-level over-attribution",
                }
            )
    return rows


def _build_no_signal_rows(
    generated_ts: str,
    discovery_run_id: str,
    forecast_rows: Sequence[Dict[str, Any]],
    behavior_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    behavior_by_key = {_row_key(row): row for row in behavior_rows}
    rows: List[Dict[str, Any]] = []
    for forecast in forecast_rows:
        key = _row_key(forecast)
        behavior = behavior_by_key.get(key, {})
        ns = normalize_no_signal_flag(forecast, behavior)
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_version": EXECUTION_VERSION,
                "discovery_run_id": discovery_run_id,
                "execution_run_id": discovery_run_id,
                "campaign_tier": "TIER_2_BEHAVIOR_PATTERN_EXPANSION",
                "session_id": key[0],
                "provider": key[1],
                "pack_level": key[2],
                "output_valid": "TRUE" if _valid(forecast) else "FALSE",
                "forecast_direction": _norm(forecast.get("forecast_direction")),
                "forecast_confidence": _fmt_num(_confidence_percent(forecast.get("forecast_confidence"))),
                "no_signal_flag": ns["value"],
                "no_signal_reason": _truncate_text(behavior.get("no_signal_reason"), 500),
                "no_signal_source": ns["source"],
                "no_signal_normalization_status": ns["status"],
                "expected_move_pips_min": _norm(forecast.get("expected_move_pips_min")),
                "expected_move_pips_max": _norm(forecast.get("expected_move_pips_max")),
                "confidence_bucket": _confidence_bucket(forecast.get("forecast_confidence")) if _valid(forecast) else "UNKNOWN",
                "expected_move_bucket": _move_bucket(forecast.get("expected_move_pips_min"), forecast.get("expected_move_pips_max")) if _valid(forecast) else "UNKNOWN",
                "uncertainty_sources": _truncate_text(behavior.get("uncertainty_sources"), 500),
                "missing_information": _truncate_text(behavior.get("missing_information"), 500),
                "notes": "",
            }
        )
    return rows


def _build_invalid_rows(
    generated_ts: str,
    discovery_run_id: str,
    raw_rows: Sequence[Dict[str, Any]],
    forecast_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    forecast_by_key = {_row_key(row): row for row in forecast_rows}
    rows: List[Dict[str, Any]] = []
    for raw in raw_rows:
        key = _row_key(raw)
        forecast = forecast_by_key.get(key, {})
        if _valid(forecast):
            continue
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_version": EXECUTION_VERSION,
                "discovery_run_id": discovery_run_id,
                "execution_run_id": discovery_run_id,
                "campaign_tier": "TIER_2_BEHAVIOR_PATTERN_EXPANSION",
                "session_id": key[0],
                "provider": key[1],
                "pack_level": key[2],
                "raw_response_archived": "TRUE" if _norm(raw.get("raw_response")) or _norm(raw.get("response_hash")) else "FALSE",
                "json_parse_success": _norm(raw.get("json_parse_success")),
                "json_validation_success": _norm(raw.get("json_validation_success")),
                "invalid_reason": _invalid_reason(raw),
                "raw_response_hash": _norm(raw.get("response_hash")),
                "repair_attempted": "FALSE",
                "provider_rerun_attempted": "FALSE",
                "recommended_handling": "TREAT_AS_INVALID_CELL",
                "notes": _truncate_text(raw.get("parse_error"), 500),
            }
        )
    return rows


def _checkpoint_row(
    generated_ts: str,
    discovery_run_id: str,
    checkpoint_id: str,
    checkpoint_name: str,
    checkpoint_sequence: int,
    provider_calls_attempted: int,
    raw_responses_archived: int,
    forecast_rows_count: int,
    behavior_rows_count: int,
    invalid_outputs_count: int,
    stop_rules: Sequence[str],
    hold_rules: Sequence[str],
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_version": EXECUTION_VERSION,
        "discovery_run_id": discovery_run_id,
        "execution_run_id": discovery_run_id,
        "checkpoint_id": checkpoint_id,
        "checkpoint_name": checkpoint_name,
        "checkpoint_sequence": checkpoint_sequence,
        "provider_calls_attempted_so_far": provider_calls_attempted,
        "raw_responses_archived_so_far": raw_responses_archived,
        "forecast_rows_so_far": forecast_rows_count,
        "behavior_rows_so_far": behavior_rows_count,
        "invalid_outputs_so_far": invalid_outputs_count,
        "archive_completeness": "TRUE" if raw_responses_archived == provider_calls_attempted else "FALSE",
        "provider_call_cap_remaining": MAX_PROVIDER_CALLS - provider_calls_attempted,
        "stop_rules_triggered": "|".join(stop_rules),
        "hold_rules_triggered": "|".join(hold_rules),
        "production_write_count": 0,
        "accuracy_evaluation_count": 0,
        "notes": _truncate_text(notes, 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_TIER2_RUNS", OUTPUT_RUNS_SHEET, "behavior_tier2_runs"),
        ("PACK_BEHAVIOR_TIER2_FORECASTS", OUTPUT_FORECASTS_SHEET, "behavior_tier2_forecasts"),
        ("PACK_BEHAVIOR_TIER2_METADATA", OUTPUT_METADATA_SHEET, "behavior_tier2_metadata"),
        ("PACK_BEHAVIOR_TIER2_BEHAVIOR", OUTPUT_BEHAVIOR_SHEET, "behavior_tier2_behavior"),
        ("PACK_BEHAVIOR_TIER2_RAW_RESPONSE_ARCHIVE", OUTPUT_RAW_ARCHIVE_SHEET, "behavior_tier2_raw_response_archive"),
        ("PACK_BEHAVIOR_TIER2_TRANSITIONS", OUTPUT_TRANSITIONS_SHEET, "behavior_tier2_transitions"),
        ("PACK_BEHAVIOR_TIER2_FIELD_INFLUENCE", OUTPUT_FIELD_INFLUENCE_SHEET, "behavior_tier2_field_influence"),
        ("PACK_BEHAVIOR_TIER2_NOSIGNAL", OUTPUT_NO_SIGNAL_SHEET, "behavior_tier2_no_signal"),
        ("PACK_BEHAVIOR_TIER2_INVALID_OUTPUT", OUTPUT_INVALID_SHEET, "behavior_tier2_invalid_output"),
        ("PACK_BEHAVIOR_TIER2_CHECKPOINT_LOG", OUTPUT_CHECKPOINT_SHEET, "behavior_tier2_checkpoint_log"),
        ("PACK_BEHAVIOR_TIER2_RUN_LOG", OUTPUT_RUN_LOG_SHEET, "behavior_tier2_run_log"),
        ("PACK_BEHAVIOR_TIER2_RUN_SUMMARY", OUTPUT_SUMMARY_SHEET, "behavior_tier2_run_summary"),
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
            "notes": "Phase 9A-4ZY Tier 2 behavior discovery execution; shadow-only, behavior-only, no accuracy evaluation.",
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


def _append_unique_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    headers: Sequence[str],
    rows: Sequence[Dict[str, Any]],
    key_name: str,
    existing_keys: Optional[Set[str]] = None,
) -> int:
    if not rows:
        return 0
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            if existing_keys is None:
                existing = _sheet_to_rows(service, spreadsheet_id, sheet_name)
                current_keys = {_norm(row.get(key_name)) for row in existing if _norm(row.get(key_name))}
            else:
                current_keys = existing_keys
            new_rows = [row for row in rows if not _norm(row.get(key_name)) or _norm(row.get(key_name)) not in current_keys]
            if not new_rows:
                return 0
            values = [[row.get(header, "") for header in headers] for row in new_rows]
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()
            if existing_keys is not None:
                existing_keys.update(_norm(row.get(key_name)) for row in new_rows if _norm(row.get(key_name)))
            return len(new_rows)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to append raw archive rows after retries: {last_error}") from last_error


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute PreSignal v2.0 Phase 9A-4ZY Tier 2 behavior pattern expansion.")
    parser.add_argument(
        "--prospective-session-id",
        action="append",
        default=[],
        help="Exact future Market_Sessions identity for one shadow-only scheduled execution.",
    )
    parser.add_argument(
        "--prospective-provider",
        action="append",
        default=[],
        help="Exact enabled provider to execute for the prospective session.",
    )
    parser.add_argument(
        "--prospective-pack-level",
        action="append",
        default=[],
        help="Remaining exact Pack level(s) for a provider retry; defaults to frozen Pack A-E.",
    )
    parser.add_argument(
        "--prospective-scheduled-execution-id",
        default="",
        help="Scheduler provenance identity; no scientific classification or outcome rule is changed.",
    )
    return parser.parse_args(argv)


def build_pack_behavior_tier2_execution_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    discovery_run_id = _execution_run_id(generated_ts)
    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)
    script_id = default_script_id()
    diagnostics_titles = _sheet_titles(sheets_service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _sheet_titles(sheets_service, MAIN_SPREADSHEET_ID)
    missing_required: List[str] = []
    warnings: List[str] = []

    hypothesis_plan_rows: List[Dict[str, Any]] = []
    for sheet in [
        INPUT_TIER2_EXPERIMENT_DESIGN,
        INPUT_TIER2_HYPOTHESIS_PLAN,
        INPUT_TIER2_SESSION_STRATEGY,
        INPUT_TIER2_CALL_BUDGET,
        INPUT_TIER2_STOP_RULES,
        INPUT_TIER2_SUCCESS_CRITERIA,
        INPUT_TIER2_READINESS,
        INPUT_TIER2_DESIGN_SUMMARY,
        INPUT_EXECUTION_READINESS,
        INPUT_SESSION_ELIGIBILITY_AUDIT,
    ]:
        rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, sheet, missing_required)
        if sheet == INPUT_TIER2_HYPOTHESIS_PLAN:
            hypothesis_plan_rows = rows
    hypothesis_ids = [
        _norm(row.get("hypothesis_id"))
        for row in hypothesis_plan_rows
        if _norm(row.get("hypothesis_id"))
    ]
    hypothesis_coverage_summary = "|".join(hypothesis_ids)
    prospective_session_ids = [
        _norm(value) for value in getattr(args, "prospective_session_id", []) if _norm(value)
    ]
    prospective_provider_names = [
        _normalize_provider_name(value)
        for value in getattr(args, "prospective_provider", [])
        if _normalize_provider_name(value)
    ]
    prospective_pack_levels = [
        _upper(value) for value in getattr(args, "prospective_pack_level", []) if _upper(value)
    ]
    prospective_execution_id = _norm(getattr(args, "prospective_scheduled_execution_id", ""))
    prospective_mode = bool(prospective_session_ids)
    if (prospective_provider_names or prospective_pack_levels or prospective_execution_id) and not prospective_mode:
        raise RuntimeError("PROSPECTIVE_SCHEDULER_ARGUMENTS_REQUIRE_PROSPECTIVE_SESSION")
    if prospective_mode and len(set(prospective_session_ids)) != 1:
        raise RuntimeError("PROSPECTIVE_EXECUTION_REQUIRES_EXACTLY_ONE_SESSION")
    if prospective_pack_levels and any(level not in ACTIVE_PACK_LEVELS for level in prospective_pack_levels):
        raise RuntimeError("PROSPECTIVE_EXECUTION_PACK_LEVEL_NOT_FROZEN_A_TO_E")

    exec_plan_summary = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_EXEC_PLAN_SUMMARY, missing_required)
    latest_plan = exec_plan_summary[-1] if exec_plan_summary else {}
    if _upper(latest_plan.get("ready_for_tier2_execution")) != "TRUE":
        raise RuntimeError("Phase 9A-4ZX execution plan is not ready for Tier 2 execution.")
    if not prospective_mode and int(_norm(latest_plan.get("provider_calls_planned")) or "0") != MAX_PROVIDER_CALLS:
        raise RuntimeError("Tier 2 execution-plan provider call budget does not match runner cap.")
    execution_order_rows = _read_optional_rows(
        sheets_service,
        DIAGNOSTICS_SPREADSHEET_ID,
        diagnostics_titles,
        INPUT_SESSION_EXECUTION_ORDER,
        missing_required,
    )
    prompt_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_SUMMARY_SHEET, missing_required)
    prompt_design_run_id = _latest_run_id(prompt_summary_rows, "prompt_design_run_id")
    prompt_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_DESIGN_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    schema_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_OUTPUT_SCHEMA_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    guardrail_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_GUARDRAILS_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    validation_summary = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_VALIDATION_SUMMARY_SHEET, missing_required)
    level_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_SUMMARY_SHEET, missing_required)
    pack_design_run_id = _latest_run_id(level_summary_rows, "pack_design_run_id")
    level_items = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_ITEMS_SHEET, missing_required),
        "pack_design_run_id",
        pack_design_run_id,
    )
    shadow_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SUMMARY_SHEET, missing_required)
    shadow_run_id = _latest_run_id(shadow_summary_rows, "shadow_pack_run_id")
    shadow_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SHEET, missing_required),
        "shadow_pack_run_id",
        shadow_run_id,
    )
    session_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SESSIONS_SHEET, warnings)
    member_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_MEMBERS_SHEET, warnings)
    attention_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_ATTENTION_HISTORY_SHEET, warnings)
    event_rows = _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, MAIN_EVENT_SHEET, warnings)
    config_rows = _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, MAIN_CONFIG_SHEET, warnings)

    if not prompt_rows or not schema_rows or not guardrail_rows or not level_items or not shadow_rows or not validation_summary:
        raise RuntimeError(f"Missing required Phase 9A inputs: {missing_required}")

    if prospective_mode:
        complete_sessions = {session_id for _, session_id in _complete_shadow_sessions(shadow_rows)}
        selected_sessions = prospective_session_ids
        missing_complete = sorted(set(selected_sessions) - complete_sessions)
        if missing_complete:
            raise RuntimeError(
                "PROSPECTIVE_SESSION_NOT_COMPLETE_OR_NOT_PREOUTCOME_SAFE:"
                + "|".join(missing_complete)
            )
        selection_notes = [
            "prospective_scheduler_execution_id=" + prospective_execution_id,
            "prospective_session_selection=exact_complete_market_state_pack_shadow",
        ]
    else:
        selected_sessions, selection_notes = _select_tier2_sessions(shadow_rows, execution_order_rows)
        if len(selected_sessions) != TARGET_SESSION_COUNT:
            raise RuntimeError(f"Expected exactly {TARGET_SESSION_COUNT} eligible sessions, found {len(selected_sessions)}: {selected_sessions}")

    session_meta_by_id, shadow_field_rows = _shadow_index(shadow_rows)
    session_meta_by_id = _merge_session_timing_metadata(session_meta_by_id, session_rows)
    prompt_by_key = _group_prompt_rows(prompt_rows, prompt_design_run_id)
    provider_models = _provider_map(prompt_rows)
    selected_provider_names = prospective_provider_names or list(PROVIDER_ORDER)
    if len(set(selected_provider_names)) != len(selected_provider_names):
        raise RuntimeError("PROSPECTIVE_PROVIDER_DUPLICATE")
    providers = [(provider, provider_models.get(provider, "")) for provider in selected_provider_names if provider in provider_models]
    missing_providers = sorted(set(selected_provider_names) - {provider for provider, _ in providers})
    if missing_providers:
        raise RuntimeError("PROSPECTIVE_PROVIDER_NOT_CONFIGURED:" + "|".join(missing_providers))
    if not prospective_mode and len(providers) != 3:
        raise RuntimeError(f"Expected exactly three providers, resolved={providers}")
    active_pack_levels = prospective_pack_levels or list(ACTIVE_PACK_LEVELS)
    provider_call_cap = len(selected_sessions) * len(active_pack_levels) * len(providers)
    if prospective_mode:
        if provider_call_cap < 1 or provider_call_cap > len(ACTIVE_PACK_LEVELS):
            raise RuntimeError("PROSPECTIVE_EXECUTION_CALL_CAP_INVALID")
    elif provider_call_cap != MAX_PROVIDER_CALLS:
        raise RuntimeError(f"Planned call count {provider_call_cap} does not equal approved maximum {MAX_PROVIDER_CALLS}.")
    execution_fields = _execution_fields(
        discovery_run_id,
        hypothesis_coverage_summary,
        provider_call_cap=provider_call_cap,
    )
    config = _config_map(config_rows)
    temperature = config.get("PREDICTION_TEMPERATURE") or config.get("prediction_temperature") or ""
    config_version = _sha256_text(json.dumps(config, sort_keys=True, ensure_ascii=True))[:16] if config else "config_unavailable"
    schema_payload = _schema_payload(schema_rows)
    guardrail_payload = _guardrail_payload(guardrail_rows)
    member_idx = _member_index(member_rows)
    attention_idx = _attention_history_index(attention_rows)
    event_idx = _event_index(event_rows)
    family_map = _field_family_map(level_items)

    forecast_rows: List[Dict[str, Any]] = []
    metadata_rows: List[Dict[str, Any]] = []
    behavior_rows: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []
    log_rows: List[Dict[str, Any]] = []
    runs_rows: List[Dict[str, Any]] = []
    checkpoint_rows: List[Dict[str, Any]] = []
    provider_pack_status: List[Dict[str, Any]] = []
    call_sequence = 0
    raw_rows_archived = 0
    notes = list(selection_notes)
    raw_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS)
    existing_raw_archive_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_RAW_ARCHIVE_SHEET)
    existing_raw_keys = {
        _norm(row.get("raw_response_archive_key"))
        for row in existing_raw_archive_rows
        if _norm(row.get("raw_response_archive_key"))
    }
    raw_archive_created_before_calls = "TRUE"
    checkpoint_rows.append(
        _checkpoint_row(
            generated_ts,
            discovery_run_id,
            "PRE_EXECUTION",
            "Pre-execution raw archive and call-cap check",
            0,
            0,
            0,
            0,
            0,
            0,
            [],
            [],
            "Raw archive sheet verified writable before provider calls.",
        )
    )

    for session_index, session_id in enumerate(selected_sessions, start=1):
        session_meta = session_meta_by_id.get(session_id, {"session_id": session_id})
        event_context, _, event_notes = _build_event_context(session_id, session_meta, member_idx, attention_idx, event_idx)
        notes.extend(event_notes)
        session_call_start = len(log_rows)
        for pack_level in active_pack_levels:
            for provider, default_model in providers:
                if call_sequence >= provider_call_cap:
                    raise RuntimeError("Provider call budget exceeded before call dispatch.")
                call_sequence += 1
                started = _iso_now()
                design_row = prompt_by_key.get((pack_level, provider), {})
                pack_level_name = _norm(design_row.get("pack_level_name")) or pack_level
                allowed_fields = _split_pipe(design_row.get("allowed_pack_fields")) or list(EXPECTED_FIELDS_BY_LEVEL[pack_level])
                market_state_context, market_state_entries, _ = _build_market_state_context(pack_level, allowed_fields, shadow_field_rows[session_id])
                prompt, prompt_hash, full_prompt_text = _build_provider_prompt(design_row, event_context, market_state_context, schema_payload, guardrail_payload)
                response = _call_live_provider_raw(script_service, script_id, provider, default_model, prompt)
                completed = _iso_now()
                raw_output = response.get("raw_output", "")
                model = response.get("model") or default_model
                parse = _parse_provider_json(raw_output, session_id, provider, pack_level, schema_rows) if response.get("status") == "ok" else {
                    "parse_success": False,
                    "validation_success": False,
                    "parsed": {},
                    "parse_error": response.get("error") or "provider_call_failed",
                    "notes": "",
                }
                parsed = parse.get("parsed", {})
                response_hash = _sha256_text(raw_output)
                raw_key = f"{discovery_run_id}|{session_id}|{provider}|{pack_level}|{prompt_hash}"
                raw_row = {
                    "generated_ts": generated_ts,
                    "experiment_id": EXPERIMENT_ID,
                    "discovery_run_id": discovery_run_id,
                    **execution_fields,
                    "provider": provider,
                    "model": model,
                    "session_id": session_id,
                    "pack_level": pack_level,
                    "prompt_hash": prompt_hash,
                    "raw_response": raw_output,
                    "response_hash": response_hash,
                    "raw_response_hash": response_hash,
                    "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                    "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                    "parse_error": _truncate_text(parse.get("parse_error", ""), 500),
                    "notes": _truncate_text(parse.get("notes", ""), 500),
                    "raw_response_archive_key": raw_key,
                    "archive_write_status": "APPENDED",
                    "recommended_handling": "" if parse.get("validation_success") else "TREAT_AS_INVALID_CELL",
                }
                raw_rows_archived += _append_unique_rows(
                    sheets_service,
                    DIAGNOSTICS_SPREADSHEET_ID,
                    OUTPUT_RAW_ARCHIVE_SHEET,
                    raw_headers,
                    [raw_row],
                    "raw_response_archive_key",
                    existing_raw_keys,
                )
                raw_rows.append(raw_row)
                base = _base_metadata(
                    generated_ts,
                    discovery_run_id,
                    prompt_design_run_id,
                    prompt_hash,
                    provider,
                    model,
                    session_meta,
                    pack_level,
                    pack_level_name,
                    temperature,
                    config_version,
                )
                base["discovery_run_id"] = base.pop("pilot_run_id")
                base.update(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "experiment_id": EXPERIMENT_ID,
                        "experiment_version": EXECUTION_VERSION,
                        "run_type": RUN_TYPE,
                        **execution_fields,
                    }
                )
                direction, _ = _normalize_forecast_direction(parsed.get("forecast_direction"))
                confidence, _ = _normalize_confidence(parsed.get("forecast_confidence"))
                move_min, _ = _normalize_numeric_value(parsed.get("expected_move_pips_min"))
                move_max, _ = _normalize_numeric_value(parsed.get("expected_move_pips_max"))
                holding, _ = _normalize_holding_minutes(parsed.get("expected_holding_minutes"))
                row_status = "parsed" if parse.get("validation_success") else ("parse_failed" if not parse.get("parse_success") else "validation_failed")
                forecast_row = dict(base)
                forecast_row.update(
                    {
                        "forecast_direction": direction if parse.get("parse_success") else "",
                        "forecast_confidence": confidence,
                        "expected_move_pips_min": move_min,
                        "expected_move_pips_max": move_max,
                        "expected_holding_minutes": holding,
                        "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                        "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                        "raw_response_archive_key": raw_key,
                        "status": row_status,
                        "error_message": _truncate_text(parse.get("parse_error", ""), 500),
                        "notes": _truncate_text(f"response_hash={response_hash}", 500),
                        **execution_fields,
                    }
                )
                forecast_rows.append(forecast_row)
                metadata_row = dict(base)
                metadata_row.update(
                    {
                        "allowed_pack_fields": "|".join(allowed_fields),
                        "actual_pack_fields_in_prompt": "|".join([entry.get("field_name", "") for entry in market_state_entries if entry.get("field_name")]),
                        "prompt_token_estimate": int(len(full_prompt_text) / 4),
                        "provider_prompt_tokens": response.get("prompt_tokens", ""),
                        "provider_completion_tokens": response.get("completion_tokens", ""),
                        "request_status": response.get("request_status", ""),
                        "response_status": response.get("response_status", ""),
                        "json_parse_success": forecast_row["json_parse_success"],
                        "json_validation_success": forecast_row["json_validation_success"],
                        "source_prompt_design_sheet": INPUT_PROMPT_DESIGN_SHEET,
                        "source_shadow_sheet": INPUT_SHADOW_SHEET,
                        "notes": _truncate_text(response.get("error", ""), 500),
                        **execution_fields,
                    }
                )
                metadata_rows.append(metadata_row)
                behavior_row = {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "experiment_id": EXPERIMENT_ID,
                        "experiment_version": EXECUTION_VERSION,
                        "discovery_run_id": discovery_run_id,
                        **execution_fields,
                        "prompt_version": prompt_design_run_id,
                        "prompt_hash": prompt_hash,
                        "provider": provider,
                        "model": model,
                        "session_id": session_id,
                        "pack_level": pack_level,
                        "pack_level_name": pack_level_name,
                        "primary_driver_summary": _truncate_text(_norm(parsed.get("primary_driver_summary")), 500),
                        "secondary_driver_summary": _truncate_text(_norm(parsed.get("secondary_driver_summary")), 500),
                        "ignored_event_summary": _truncate_text(_norm(parsed.get("ignored_event_summary")), 500),
                        "information_used": _truncate_text(_json_value(parsed.get("information_used")), 500),
                        "information_not_used": _truncate_text(_json_value(parsed.get("information_not_used")), 500),
                        "pack_fields_used": _truncate_text(_json_value(parsed.get("pack_fields_used")), 500),
                        "pack_fields_discarded": _truncate_text(_json_value(parsed.get("pack_fields_discarded")), 500),
                        "pack_fields_that_changed_reasoning": _truncate_text(_json_value(parsed.get("pack_fields_that_changed_reasoning")), 500),
                        "pack_fields_that_did_not_change_reasoning": _truncate_text(_json_value(parsed.get("pack_fields_that_did_not_change_reasoning")), 500),
                        "causal_chain": _truncate_text(_norm(parsed.get("causal_chain")), 800),
                        "invalidation_condition": _truncate_text(_norm(parsed.get("invalidation_condition")), 500),
                        "uncertainty_sources": _truncate_text(_json_value(parsed.get("uncertainty_sources")), 500),
                        "missing_information": _truncate_text(_json_value(parsed.get("missing_information")), 500),
                        "no_signal_flag": "TRUE" if parse.get("parse_success") and (_as_bool(parsed.get("no_signal_flag")) or direction == "no_clear_direction") else ("FALSE" if parse.get("parse_success") else ""),
                        "no_signal_reason": _truncate_text(_norm(parsed.get("no_signal_reason")), 500),
                        "reasoning_summary": _truncate_text(_norm(parsed.get("session_narrative")) or _norm(parsed.get("reasoning_summary")) or _norm(parsed.get("causal_chain")), 800),
                        "json_validation_success": forecast_row["json_validation_success"],
                        "status": row_status,
                        "error_message": forecast_row["error_message"],
                        "notes": "",
                        "output_valid": "TRUE" if parse.get("validation_success") else "FALSE",
                        "invalid_reason": "" if parse.get("validation_success") else _invalid_reason(raw_row),
                }
                behavior_rows.append(behavior_row)
                collector_result = _capture_prospective_mechanism_evidence(
                    discovery_run_id=discovery_run_id,
                    session_meta=session_meta,
                    forecast_row=forecast_row,
                    behavior_row=behavior_row,
                    raw_response_archive_key=raw_key,
                    capture_timestamp=completed,
                )
                provider_pack_status.append(
                    {
                        "session_id": session_id,
                        "provider": provider,
                        "pack_level": pack_level,
                        "response_status": _norm(response.get("response_status")),
                        "json_validation_success": forecast_row["json_validation_success"],
                        "collector_status": _norm(collector_result.get("collection_status")),
                        "collector_failure_code": _norm(collector_result.get("failure_code")),
                    }
                )
                log_rows.append(
                    {
                        "generated_ts": generated_ts,
                        "schema_version": SCHEMA_VERSION,
                        "experiment_id": EXPERIMENT_ID,
                        "experiment_version": EXECUTION_VERSION,
                        "discovery_run_id": discovery_run_id,
                        **execution_fields,
                        "session_id": session_id,
                        "provider": provider,
                        "model": model,
                        "pack_level": pack_level,
                        "pack_level_name": pack_level_name,
                        "prompt_hash": prompt_hash,
                        "request_status": response.get("request_status", ""),
                        "response_status": response.get("response_status", ""),
                        "json_parse_success": forecast_row["json_parse_success"],
                        "json_validation_success": forecast_row["json_validation_success"],
                        "status": row_status,
                        "error_message": forecast_row["error_message"] or _truncate_text(response.get("error", ""), 500),
                        "elapsed_seconds": "",
                        "notes": (
                            f"started_ts={started}; completed_ts={completed}; raw_response_archive_key={raw_key}; "
                            f"prospective_collector_status={_norm(collector_result.get('collection_status'))}; "
                            f"prospective_collector_failure={_norm(collector_result.get('failure_code'))}"
                        ),
                        "call_sequence": call_sequence,
                        "provider_call_made": "TRUE",
                    }
                )
        session_logs = log_rows[session_call_start:]
        runs_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "execution_version": EXECUTION_VERSION,
                "discovery_run_id": discovery_run_id,
                **execution_fields,
                "session_id": session_id,
                "session_date": session_meta.get("session_date", ""),
                "country": session_meta.get("country", ""),
                "session_window_name": session_meta.get("session_window_name", ""),
                "session_selection_status": "SELECTED",
                "pack_levels_executed": "|".join(active_pack_levels),
                "providers_executed": "|".join(provider for provider, _ in providers),
                "planned_provider_calls": len(active_pack_levels) * len(providers),
                "provider_calls_attempted": len(session_logs),
                "provider_calls_succeeded": sum(1 for row in session_logs if _norm(row.get("response_status")) == "ok"),
                "provider_calls_failed": sum(1 for row in session_logs if _norm(row.get("response_status")) != "ok"),
                "raw_responses_archived": sum(1 for row in raw_rows if _norm(row.get("session_id")) == session_id),
                "invalid_outputs": sum(1 for row in raw_rows if _norm(row.get("session_id")) == session_id and _upper(row.get("json_validation_success")) != "TRUE"),
                "status": "COMPLETED",
                "notes": "Tier 2 selected by complete deterministic pack coverage and not previously executed.",
            }
        )
        checkpoint_rows.append(
            _checkpoint_row(
                generated_ts,
                discovery_run_id,
                f"AFTER_SESSION_{session_index}",
                f"After session {session_index}",
                session_index,
                len(log_rows),
                raw_rows_archived,
                len(forecast_rows),
                len(behavior_rows),
                sum(1 for row in raw_rows if _upper(row.get("json_validation_success")) != "TRUE"),
                [],
                [],
                f"Completed session_id={session_id}.",
            )
        )

    transitions = (
        _build_transitions(
            generated_ts,
            discovery_run_id,
            forecast_rows,
            behavior_rows,
            providers=[provider for provider, _ in providers],
        )
        if set(active_pack_levels) == set(ACTIVE_PACK_LEVELS)
        else []
    )
    field_rows = _build_field_influence(generated_ts, discovery_run_id, forecast_rows, behavior_rows, family_map)
    no_signal_rows = _build_no_signal_rows(generated_ts, discovery_run_id, forecast_rows, behavior_rows)
    invalid_rows = _build_invalid_rows(generated_ts, discovery_run_id, raw_rows, forecast_rows)
    success_calls = sum(1 for row in log_rows if _norm(row.get("response_status")) == "ok")
    failed_calls = len(log_rows) - success_calls
    raw_archive_dedupe_count = len(raw_rows) - raw_rows_archived
    raw_archive_append_failure_count = 0
    invalid_output_rate = (len(invalid_rows) / len(raw_rows)) if raw_rows else 0
    hold_rules_triggered: List[str] = []
    stop_rules_triggered: List[str] = []
    if invalid_output_rate > 0.20:
        hold_rules_triggered.append("invalid_output_rate_exceeds_threshold")
    if raw_rows_archived < len(log_rows):
        stop_rules_triggered.append("raw_archive_incomplete")
    checkpoint_rows.append(
        _checkpoint_row(
            generated_ts,
            discovery_run_id,
            "POST_EXECUTION",
            "Post-execution summary check",
            len(selected_sessions) + 1,
            len(log_rows),
            raw_rows_archived,
            len(forecast_rows),
            len(behavior_rows),
            len(invalid_rows),
            stop_rules_triggered,
            hold_rules_triggered,
            "Final row-count and governance checkpoint.",
        )
    )
    safety = {
        "accuracy_evaluation_count": 0,
        "provider_rerun_count": 0,
        "forecast_generation_count": len(forecast_rows),
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "routing_changes": "FALSE",
        "weight_changes": "FALSE",
        "ensemble_changes": "FALSE",
        "predictions_write_count": 0,
        "evaluation_write_count": 0,
        "outcome_ledger_write_count": 0,
        "mr_provider_runs_write_count": 0,
    }
    blocking_safety_values = {
        key: value
        for key, value in safety.items()
        if key not in {"forecast_generation_count"} and value not in (0, "FALSE")
    }
    if raw_rows_archived < len(log_rows):
        build_status = "FAIL"
        interpretation = "BEHAVIOR_TIER2_EXECUTION_INCOMPLETE_RAW_ARCHIVE"
        recommended_next_step = "HOLD_PHASE9A4ZY_PENDING_GOVERNANCE_REVIEW"
    elif len(log_rows) > provider_call_cap or blocking_safety_values:
        build_status = "FAIL"
        interpretation = "BEHAVIOR_TIER2_EXECUTION_BLOCKED"
        recommended_next_step = "HOLD_PHASE9A4ZY_PENDING_GOVERNANCE_REVIEW"
    elif invalid_output_rate > 0.20:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "BEHAVIOR_TIER2_EXECUTION_NEEDS_REVIEW"
        recommended_next_step = "HOLD_PHASE9A4ZY_PENDING_GOVERNANCE_REVIEW"
    elif failed_calls or invalid_rows:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "BEHAVIOR_TIER2_EXECUTION_READY_WITH_WARNINGS"
        recommended_next_step = "PROCEED_TO_PHASE9A4ZY_TIER2_EXECUTION_REVIEW"
    else:
        build_status = "PASS"
        interpretation = "BEHAVIOR_TIER2_EXECUTION_READY"
        recommended_next_step = "PROCEED_TO_PHASE9A4ZY_TIER2_EXECUTION_REVIEW"
    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_version": EXECUTION_VERSION,
        "discovery_run_id": discovery_run_id,
        "build_status": build_status,
        "final_interpretation": interpretation,
        **execution_fields,
        "approved_session_count": len(selected_sessions),
        "sessions_planned": len(selected_sessions),
        "sessions_executed": len(selected_sessions),
        "session_ids_executed": "|".join(selected_sessions),
        "providers_executed": "|".join(provider for provider, _ in providers),
        "pack_levels_executed": "|".join(active_pack_levels),
        "expected_provider_calls": provider_call_cap,
        "maximum_provider_calls": provider_call_cap,
        "provider_call_cap": provider_call_cap,
        "provider_calls_attempted": len(log_rows),
        "provider_calls_succeeded": success_calls,
        "provider_calls_failed": failed_calls,
        "raw_responses_archived": raw_rows_archived,
        "raw_archive_append_failure_count": raw_archive_append_failure_count,
        "raw_archive_dedupe_count": raw_archive_dedupe_count,
        "raw_archive_created_before_calls": raw_archive_created_before_calls,
        "invalid_outputs": len(invalid_rows),
        "invalid_output_count": len(invalid_rows),
        "invalid_output_rate": _fmt_num(invalid_output_rate),
        "hold_rule_trigger_count": len(hold_rules_triggered),
        "stop_rule_trigger_count": len(stop_rules_triggered),
        "json_validation_success_count": sum(1 for row in raw_rows if _upper(row.get("json_validation_success")) == "TRUE"),
        "json_validation_failure_count": sum(1 for row in raw_rows if _upper(row.get("json_validation_success")) != "TRUE"),
        "forecast_rows_captured": len(forecast_rows),
        "behavior_rows_captured": len(behavior_rows),
        "transition_rows_captured": len(transitions),
        "field_influence_rows_captured": len(field_rows),
        "no_signal_rows_captured": len(no_signal_rows),
        "metadata_rows_written": len(metadata_rows),
        "checkpoint_rows_captured": len(checkpoint_rows),
        "run_log_rows_written": len(log_rows),
        "provider_call_count": len(log_rows),
        **safety,
        "recommended_next_step": recommended_next_step,
        "hypothesis_coverage_summary": hypothesis_coverage_summary,
        "notes": _truncate_text(json.dumps({"selection_notes": notes, "warnings": warnings, "invalid_output_rate": invalid_output_rate}, ensure_ascii=True), 500),
    }

    for sheet, headers, rows in [
        (OUTPUT_RUNS_SHEET, RUNS_HEADERS, runs_rows),
        (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, forecast_rows),
        (OUTPUT_METADATA_SHEET, METADATA_HEADERS, metadata_rows),
        (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, behavior_rows),
        (OUTPUT_TRANSITIONS_SHEET, TRANSITION_HEADERS, transitions),
        (OUTPUT_FIELD_INFLUENCE_SHEET, FIELD_INFLUENCE_HEADERS, field_rows),
        (OUTPUT_NO_SIGNAL_SHEET, NO_SIGNAL_HEADERS, no_signal_rows),
        (OUTPUT_INVALID_SHEET, INVALID_HEADERS, invalid_rows),
        (OUTPUT_CHECKPOINT_SHEET, CHECKPOINT_HEADERS, checkpoint_rows),
        (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, log_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry = _upsert_registry_rows(sheets_service)
    return {
        "build_status": build_status,
        "final_interpretation": interpretation,
        "discovery_run_id": discovery_run_id,
        "sessions_executed": selected_sessions,
        "providers_executed": [provider for provider, _ in providers],
        "pack_levels_executed": active_pack_levels,
        "provider_calls_attempted": len(log_rows),
        "provider_calls_succeeded": success_calls,
        "provider_calls_failed": failed_calls,
        "provider_call_cap": provider_call_cap,
        "prospective_scheduler_execution_id": prospective_execution_id,
        "prospective_mode": prospective_mode,
        "provider_pack_status": provider_pack_status,
        "provider_rerun_count": 0,
        "raw_responses_archived": raw_rows_archived,
        "raw_archive_append_failure_count": raw_archive_append_failure_count,
        "raw_archive_dedupe_count": raw_archive_dedupe_count,
        "invalid_outputs": len(invalid_rows),
        "forecast_rows_captured": len(forecast_rows),
        "behavior_rows_captured": len(behavior_rows),
        "transition_rows_captured": len(transitions),
        "field_influence_rows_captured": len(field_rows),
        "no_signal_rows_captured": len(no_signal_rows),
        "accuracy_evaluation_count": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "safety": safety,
        "sheets_written": {
            OUTPUT_RUNS_SHEET: len(runs_rows),
            OUTPUT_FORECASTS_SHEET: len(forecast_rows),
            OUTPUT_METADATA_SHEET: len(metadata_rows),
            OUTPUT_BEHAVIOR_SHEET: len(behavior_rows),
            OUTPUT_RAW_ARCHIVE_SHEET: raw_rows_archived,
            OUTPUT_TRANSITIONS_SHEET: len(transitions),
            OUTPUT_FIELD_INFLUENCE_SHEET: len(field_rows),
            OUTPUT_NO_SIGNAL_SHEET: len(no_signal_rows),
            OUTPUT_INVALID_SHEET: len(invalid_rows),
            OUTPUT_CHECKPOINT_SHEET: len(checkpoint_rows),
            OUTPUT_RUN_LOG_SHEET: len(log_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_pack_behavior_tier2_execution_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
