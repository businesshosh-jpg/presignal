import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

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


SCHEMA_VERSION = "presignal_v2_behavior_pattern_execution_plan_0.1"
EXECUTION_PLAN_VERSION = "behavior_pattern_execution_plan_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4E"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_PATTERN_EXECUTION_PLAN"
REGISTRY_OWNER_MODULE = "market_state"

OUTPUT_EXECUTION_PLAN_SHEET = "Pack_Behavior_Pattern_Execution_Plan"
OUTPUT_SESSION_SELECTION_SHEET = "Pack_Behavior_Pattern_Session_Selection_Plan"
OUTPUT_CALL_BUDGET_SHEET = "Pack_Behavior_Pattern_Call_Budget"
OUTPUT_BATCH_STRATEGY_SHEET = "Pack_Behavior_Pattern_Batch_Strategy"
OUTPUT_STOP_HOLD_RULES_SHEET = "Pack_Behavior_Pattern_Stop_Hold_Rules"
OUTPUT_READINESS_AUDIT_SHEET = "Pack_Behavior_Pattern_Execution_Readiness_Audit"
OUTPUT_SUMMARY_SHEET = "Pack_Behavior_Pattern_Execution_Plan_Summary"

PHASE9A4_DESIGN_SHEETS = [
    "Pack_Behavior_Pattern_Discovery_Design",
    "Pack_Behavior_Pattern_Metrics_Definition",
    "Pack_Behavior_Pattern_Grouping_Rules",
    "Pack_Behavior_Pattern_Invalid_Output_Rules",
    "Pack_Behavior_Pattern_Readiness_Audit",
    "Pack_Behavior_Pattern_Discovery_Summary",
]
PHASE9A3R_SHEETS = [
    "Pack_Exposure_Behavior_Compare",
    "Pack_Exposure_Reasoning_Transitions",
    "Pack_Exposure_Provider_Transition_Audit",
    "Pack_Exposure_Field_Influence_Audit",
    "Pack_Exposure_NoSignal_Confidence_Audit",
    "Pack_Exposure_Invalid_Output_Audit",
    "Pack_Exposure_Behavior_Compare_Summary",
]
PHASE9A2_SOURCE_SHEETS = [
    "Pack_Exposure_Forecasts",
    "Pack_Exposure_Forecast_Metadata",
    "Pack_Exposure_Behavior_Capture",
    "Pack_Exposure_Raw_Response_Archive",
    "Pack_Exposure_Run_Log",
    "Pack_Exposure_Run_Summary",
]
PACK_DESIGN_SHEETS = [
    "Market_State_Pack_Level_Definition",
    "Market_State_Pack_Level_Items",
    "Market_State_Pack_Level_Readiness_Audit",
    "Market_State_Pack_Level_Summary",
]
SUPPORT_SHEETS = [
    "Market_Sessions",
    "Market_Session_Members",
    "Session_Attention_Map_History",
    "Session_Information_Requests_History",
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Item_Audit",
    "Market_State_Pack_Coverage_Audit",
    "Pack_Exposure_Prompt_Design",
    "Pack_Exposure_Prompt_Validation_Summary",
]
OPTIONAL_GOVERNANCE_SHEETS = [
    "Sheet_Registry",
    "Workbook_Migration_Control",
    "Workbook_Migration_Log",
]

PACK_LEVELS_PER_SESSION = 5
PROVIDERS_PER_PACK = 3
CALLS_PER_SESSION = PACK_LEVELS_PER_SESSION * PROVIDERS_PER_PACK


EXECUTION_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_id",
    "plan_component",
    "component_status",
    "component_purpose",
    "input_requirements",
    "future_output_requirements",
    "execution_scope",
    "allowed_actions",
    "forbidden_actions",
    "dependency_sheets",
    "blocking_conditions",
    "notes",
]

SESSION_SELECTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "selection_rule_id",
    "selection_rule_name",
    "selection_purpose",
    "eligible_session_source",
    "inclusion_criteria",
    "exclusion_criteria",
    "required_pack_coverage",
    "required_provider_coverage",
    "required_replay_status",
    "required_shadow_pack_status",
    "priority",
    "sample_tier",
    "target_session_count",
    "expected_provider_calls",
    "notes",
]

CALL_BUDGET_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "budget_id",
    "sample_tier",
    "session_count",
    "pack_levels_per_session",
    "providers_per_pack",
    "expected_provider_calls",
    "allowed_retries",
    "maximum_provider_calls",
    "cost_risk_level",
    "quota_risk_level",
    "recommended_execution_mode",
    "approval_required_before_execution",
    "notes",
]

BATCH_STRATEGY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "batch_strategy_id",
    "batch_name",
    "batch_sequence",
    "batch_session_count",
    "expected_provider_calls",
    "execution_goal",
    "required_preconditions",
    "required_post_batch_outputs",
    "post_batch_review_required",
    "continue_condition",
    "stop_condition",
    "notes",
]

STOP_HOLD_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "rule_id",
    "rule_type",
    "rule_name",
    "trigger_condition",
    "required_action",
    "blocking",
    "applies_to_phase",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "readiness_check_id",
    "readiness_area",
    "check_description",
    "check_status",
    "evidence_sheet",
    "evidence_value",
    "blocking",
    "recommended_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "build_status",
    "final_interpretation",
    "execution_components_defined",
    "session_selection_rules_defined",
    "call_budget_rows_defined",
    "batch_strategy_rows_defined",
    "stop_hold_rules_defined",
    "readiness_checks_defined",
    "phase9a4_design_confirmed",
    "phase9a3r_repair_confirmed",
    "recommended_first_execution_tier",
    "recommended_first_execution_session_count",
    "expected_provider_calls_first_execution",
    "maximum_provider_calls_first_execution",
    "single_session_generalization_allowed",
    "accuracy_evaluation_count",
    "provider_call_count",
    "forecast_generation_count",
    "production_behavior_change_count",
    "ready_for_phase9a4_small_expansion_execution",
    "ready_for_phase9a5_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(ts: str) -> str:
    stamp = ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"behavior_pattern_execution_plan_v0_{stamp}"


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_int(value: Any) -> int:
    try:
        raw = _norm(value)
        if raw == "":
            return 0
        return int(float(raw))
    except Exception:
        return 0


def _bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _get_sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _read_if_exists(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(rows[-1]) if rows else {}


def _join(values: Sequence[str]) -> str:
    return "|".join(values)


def _execution_component(
    generated_ts: str,
    plan_id: str,
    component: str,
    purpose: str,
    input_requirements: str,
    future_outputs: str,
    scope: str,
    dependencies: str,
    blockers: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "execution_plan_id": plan_id,
        "plan_component": component,
        "component_status": "DEFINED",
        "component_purpose": purpose,
        "input_requirements": input_requirements,
        "future_output_requirements": future_outputs,
        "execution_scope": scope,
        "allowed_actions": "execute approved Pack A-E prompt grid in future execution phase only; preserve raw responses; run validation and behavior capture",
        "forbidden_actions": "accuracy_evaluation|provider_ranking|pack_ranking|production_changes|routing_changes|weighting_changes|calibration_changes",
        "dependency_sheets": dependencies,
        "blocking_conditions": blockers,
        "notes": notes,
    }


def _build_execution_plan_rows(generated_ts: str, plan_id: str) -> List[Dict[str, Any]]:
    common_inputs = _join(PHASE9A4_DESIGN_SHEETS + PHASE9A3R_SHEETS + PACK_DESIGN_SHEETS)
    future_outputs = "Pack_Behavior_Pattern_Run_Log|Pack_Behavior_Pattern_Batch_Summary|Pack_Behavior_Pattern_Provider_Profile|Pack_Behavior_Pattern_Field_Profile"
    specs = [
        ("campaign_scope", "Define a small, controlled behavior-discovery expansion before larger replay.", "Phase 9A-4 design ready; prompt validation ready; pack levels A-E only", future_outputs, "Tiered multi-session behavior observation", common_inputs, "Phase 9A-4 design blocked or prompt validation unavailable"),
        ("session_selection", "Select sessions with complete deterministic pack coverage and usable context.", "Market_State_Pack_Shadow and coverage audits", "Pack_Behavior_Pattern_Selected_Sessions", "Session eligibility planning", "Market_State_Pack_Shadow|Market_State_Pack_Coverage_Audit|Market_Sessions", "Missing Lane A fields or prompt validation blockers"),
        ("pack_execution_grid", "Execute Pack A-E for each selected session in future execution phase.", "Pack levels A-E defined and prompt dry-run validated", "Pack_Behavior_Pattern_Execution_Grid", "5 pack levels per session", "Market_State_Pack_Level_Definition|Pack_Exposure_Prompt_Design", "Pack Q or excluded fields appear"),
        ("provider_execution_grid", "Execute OpenAI, Gemini, and Anthropic for each pack level in future execution phase.", "Approved provider set and model config frozen", "Pack_Behavior_Pattern_Provider_Run_Status", "3 providers per pack", "Pack_Exposure_Prompt_Design", "Provider set changes without new plan"),
        ("batch_execution_sequence", "Run small batches and review before expanding sample size.", "Batch 0 completed; Batch 1 approved before execution", "Pack_Behavior_Pattern_Batch_Summary", "Batch-gated execution", OUTPUT_BATCH_STRATEGY_SHEET, "Post-batch review not completed"),
        ("raw_response_archiving", "Archive every raw response before parsing.", "Raw archive table available and immutable metadata defined", "Pack_Behavior_Pattern_Raw_Response_Archive", "All future provider response cells", "Pack_Exposure_Raw_Response_Archive", "Any missing raw response"),
        ("json_validation", "Validate JSON contract without repairing source response.", "Output schema from prompt design", "Pack_Behavior_Pattern_JSON_Validation_Audit", "Every provider response", "Pack_Exposure_Output_Schema|Pack_Exposure_Raw_Response_Archive", "Schema changes or parser coercion"),
        ("behavior_capture", "Capture behavior fields without scoring accuracy.", "Valid parsed output or invalid cell label", "Pack_Behavior_Pattern_Behavior_Capture", "Provider x pack x session", "Pack_Exposure_Behavior_Capture", "Accuracy fields introduced"),
        ("reasoning_transition_comparison", "Compare reasoning transitions after future execution batches.", "Phase 9A-3R comparison logic", "Pack_Behavior_Pattern_Reasoning_Transitions", "Provider x transition x session", "Pack_Exposure_Reasoning_Transitions", "No-signal normalization mismatch"),
        ("field_influence_capture", "Capture field usage/discard/no-effect/changed-reasoning conservatively.", "Field influence exact matching policy", "Pack_Behavior_Pattern_Field_Influence", "Field x provider x pack x session", "Pack_Exposure_Field_Influence_Audit", "Over-attribution of vague field-family mentions"),
        ("no_signal_confidence_capture", "Track no-signal and confidence behavior without treating confidence as accuracy.", "Phase 9A-3R normalized no-signal logic", "Pack_Behavior_Pattern_NoSignal_Confidence", "Provider x pack x session", "Pack_Exposure_NoSignal_Confidence_Audit", "No-signal normalization inconsistent"),
        ("invalid_output_handling", "Preserve invalid outputs as evidence and never impute.", "Invalid output rules defined", "Pack_Behavior_Pattern_Invalid_Output_Audit", "Invalid response cells", OUTPUT_STOP_HOLD_RULES_SHEET, "Invalid outputs silently replaced"),
        ("post_batch_review", "Review behavior and governance after every batch before continuing.", "Batch outputs complete", "Pack_Behavior_Pattern_Post_Batch_Review", "Batch-level review", OUTPUT_BATCH_STRATEGY_SHEET, "Review omitted before expansion"),
        ("promotion_gate_to_accuracy_phase", "Block accuracy phase until behavior patterns stabilize and governance passes.", "Stable behavior-pattern candidate thresholds met", "Phase9A5_Readiness_Gate", "Future research gate only", OUTPUT_READINESS_AUDIT_SHEET, "Accuracy evaluation attempted before gate"),
        ("governance_safety", "Keep all outputs shadow-only and non-production.", "Safety counters zero", "Pack_Behavior_Pattern_Governance_Audit", "All batches and planning phases", OUTPUT_STOP_HOLD_RULES_SHEET, "Production write, routing, weighting, or calibration detected"),
    ]
    return [_execution_component(generated_ts, plan_id, *spec, notes="Behavior before accuracy; small batch before large replay.") for spec in specs]


def _session_rule(
    generated_ts: str,
    rule_id: str,
    name: str,
    purpose: str,
    source: str,
    include: str,
    exclude: str,
    priority: int,
    tier: str,
    sessions: int,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "selection_rule_id": rule_id,
        "selection_rule_name": name,
        "selection_purpose": purpose,
        "eligible_session_source": source,
        "inclusion_criteria": include,
        "exclusion_criteria": exclude,
        "required_pack_coverage": "Complete Pack A-E deterministic Lane A coverage; no missing eligible fields unless explicitly testing gaps.",
        "required_provider_coverage": "OpenAI|Gemini|Anthropic available for all Pack A-E cells.",
        "required_replay_status": "Replay/session context must be complete and linkage-safe.",
        "required_shadow_pack_status": "MARKET_STATE_PACK_SHADOW_REFINED_WITH_WARNINGS or stronger; no leakage or provider exposure.",
        "priority": priority,
        "sample_tier": tier,
        "target_session_count": sessions,
        "expected_provider_calls": sessions * CALLS_PER_SESSION,
        "notes": notes,
    }


def _build_session_selection_rows(generated_ts: str) -> List[Dict[str, Any]]:
    include = "complete deterministic pack coverage; no missing Lane A fields; successful shadow acquisition; usable event/session context; valid prompt dry-run coverage; no unresolved source-mapping blockers; not already used in same pilot run unless intentionally replayed"
    exclude = "missing deterministic pack fields; weekend-boundary USDJPY gaps unless specifically testing gap behavior; blocked pack-level readiness; missing raw event context; unresolved provider prompt validation issue; known production contamination risk"
    return [
        _session_rule(generated_ts, "sel_tier0_validated_pilot", "TIER_0_VALIDATED_PILOT", "Record the completed one-session pilot as baseline evidence; no new provider calls.", "Pack_Exposure_Run_Summary|Pack_Exposure_Behavior_Compare_Summary", "US|2024-05-08|CUSTOM_CONFIG_WINDOW already completed", "Do not rerun inside design phase.", 0, "TIER_0_VALIDATED_PILOT", 1, "Validated pilot exists; no new provider calls."),
        _session_rule(generated_ts, "sel_tier1_small_expansion", "TIER_1_SMALL_EXPANSION", "Select 3 additional sessions to test whether behavior signal repeats.", "Market_State_Pack_Shadow|Market_State_Pack_Coverage_Audit|Market_Sessions", include, exclude, 1, "TIER_1_SMALL_EXPANSION", 3, "Recommended first execution tier: 3 sessions x 5 packs x 3 providers = 45 calls."),
        _session_rule(generated_ts, "sel_tier2_pattern_candidate_min", "TIER_2_PATTERN_CANDIDATE_MIN", "Select 5 additional sessions after Tier 1 review for candidate pattern discovery.", "Market_State_Pack_Shadow|Replay history|Market_Sessions", include, exclude, 2, "TIER_2_PATTERN_CANDIDATE", 5, "Do not schedule until Tier 1 post-batch review passes."),
        _session_rule(generated_ts, "sel_tier2_pattern_candidate_max", "TIER_2_PATTERN_CANDIDATE_MAX", "Select up to 10 additional sessions for stronger candidate-pattern evidence.", "Market_State_Pack_Shadow|Replay history|Market_Sessions", include, exclude, 3, "TIER_2_PATTERN_CANDIDATE", 10, "Use only after Tier 1 review confirms behavior signal remains interpretable."),
        _session_rule(generated_ts, "sel_tier3_stability_check", "TIER_3_STABILITY_CHECK", "Plan 20+ valid sessions for stability candidates after Tier 1 and Tier 2 pass.", "Market_State_Pack_Shadow|Replay history|Market_Sessions", include, exclude, 4, "TIER_3_STABILITY_CHECK", 20, "Requires separate approval before scheduling."),
        _session_rule(generated_ts, "sel_exclusion_guardrail", "SESSION_EXCLUSION_GUARDRAIL", "Exclude sessions with contamination or unresolved structural issues.", "All session and pack support sheets", "Only include if governance checks pass.", exclude + "; excluded Lane B/C fields detected; fed expectations detected; upcoming event risk label detected", 99, "ALL_TIERS", 0, "Guardrail row; not a runnable sample tier."),
    ]


def _budget_row(
    generated_ts: str,
    budget_id: str,
    tier: str,
    sessions: int,
    risk: str,
    mode: str,
    approval: str,
    notes: str,
) -> Dict[str, Any]:
    expected = sessions * CALLS_PER_SESSION
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "budget_id": budget_id,
        "sample_tier": tier,
        "session_count": sessions,
        "pack_levels_per_session": PACK_LEVELS_PER_SESSION,
        "providers_per_pack": PROVIDERS_PER_PACK,
        "expected_provider_calls": expected,
        "allowed_retries": 0,
        "maximum_provider_calls": expected,
        "cost_risk_level": risk,
        "quota_risk_level": risk,
        "recommended_execution_mode": mode,
        "approval_required_before_execution": approval,
        "notes": notes + " Reruns, if approved in a future execution phase, must use a new run_id and preserve original invalid outputs.",
    }


def _build_budget_rows(generated_ts: str) -> List[Dict[str, Any]]:
    return [
        _budget_row(generated_ts, "budget_tier0_validated_pilot", "TIER_0_VALIDATED_PILOT", 1, "NONE", "already_completed_no_new_calls", "FALSE", "Completed pilot record only; no new calls."),
        _budget_row(generated_ts, "budget_tier1_small_expansion", "TIER_1_SMALL_EXPANSION", 3, "MEDIUM", "controlled_batch", "TRUE", "Recommended first expansion: 45 expected calls, 0 retries in analysis phase."),
        _budget_row(generated_ts, "budget_tier2_pattern_candidate_min", "TIER_2_PATTERN_CANDIDATE_MIN", 5, "MEDIUM", "controlled_batch_after_review", "TRUE", "Minimum candidate-pattern expansion: 75 expected calls."),
        _budget_row(generated_ts, "budget_tier2_pattern_candidate_max", "TIER_2_PATTERN_CANDIDATE_MAX", 10, "HIGH", "controlled_batch_after_review", "TRUE", "Maximum Tier 2 expansion: 150 expected calls."),
        _budget_row(generated_ts, "budget_tier3_stability_check", "TIER_3_STABILITY_CHECK", 20, "HIGH", "separate_approved_campaign", "TRUE", "Stability check: 300 expected calls and separate approval required."),
    ]


def _batch_row(
    generated_ts: str,
    strategy_id: str,
    name: str,
    sequence: int,
    sessions: int,
    goal: str,
    preconditions: str,
    continue_condition: str,
    stop_condition: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "batch_strategy_id": strategy_id,
        "batch_name": name,
        "batch_sequence": sequence,
        "batch_session_count": sessions,
        "expected_provider_calls": sessions * CALLS_PER_SESSION,
        "execution_goal": goal,
        "required_preconditions": preconditions,
        "required_post_batch_outputs": "batch_behavior_summary|provider_sensitivity_summary|pack_transition_value_summary|field_influence_summary|invalid_output_summary|no_signal_confidence_summary|governance_safety_summary",
        "post_batch_review_required": "TRUE",
        "continue_condition": continue_condition,
        "stop_condition": stop_condition,
        "notes": notes,
    }


def _build_batch_rows(generated_ts: str) -> List[Dict[str, Any]]:
    return [
        _batch_row(generated_ts, "batch0_validated_pilot", "Batch 0 - Validated Pilot", 0, 1, "Use completed pilot as design seed; no new calls.", "Phase 9A-3R repaired and reviewed.", "Proceed only to planning; no execution from this row.", "Any raw archive or governance mismatch.", "Already complete."),
        _batch_row(generated_ts, "batch1_small_expansion", "Batch 1 - 3 Session Small Expansion", 1, 3, "Confirm whether behavior signal repeats beyond one session.", "Phase 9A-4E review approved; 3 eligible sessions selected; prompt validation ready.", "Invalid output rate <=20%; raw archive complete; no production or accuracy counters.", "Any raw response missing, production write, accuracy evaluation, or excluded field contamination.", "Recommended first executable batch."),
        _batch_row(generated_ts, "batch2_candidate_pattern", "Batch 2 - 5 Session Candidate Pattern Expansion", 2, 5, "Identify candidate stable behavior patterns.", "Batch 1 post-batch review passes and behavior outputs remain interpretable.", "Candidate patterns emerge without governance violations.", "Invalid output rate >20% or no-signal normalization mismatch.", "Do not schedule until Batch 1 review."),
        _batch_row(generated_ts, "batch3_stability_expansion", "Batch 3 - 10+ Session Stability Expansion", 3, 10, "Check whether candidate patterns persist.", "Batch 2 review passes and separate approval granted.", "Stable pattern candidates meet n>=20 across >=5 sessions.", "Any governance stop condition or cost/quota hold.", "A 20-session stability check requires a separate campaign approval."),
    ]


def _stop_rule(
    generated_ts: str,
    rule_id: str,
    rule_type: str,
    name: str,
    trigger: str,
    action: str,
    blocking: bool,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "rule_id": rule_id,
        "rule_type": rule_type,
        "rule_name": name,
        "trigger_condition": trigger,
        "required_action": action,
        "blocking": _bool_text(blocking),
        "applies_to_phase": "Phase 9A-4X future execution and post-batch review",
        "notes": notes,
    }


def _build_stop_rows(generated_ts: str) -> List[Dict[str, Any]]:
    specs = [
        ("stop_provider_call_count_exceeds_plan", "STOP", "provider_call_count_exceeds_plan", "Provider calls exceed approved maximum for tier.", "Stop batch and require governance review.", True, "Maximum for Tier 1 is 45 calls."),
        ("stop_raw_response_archive_missing", "STOP", "raw_response_archive_missing", "Any provider response lacks raw archive row.", "Stop analysis until archive integrity is restored.", True, "Raw archive before parsing."),
        ("hold_json_validation_failure_rate", "HOLD", "json_validation_failure_rate_exceeds_threshold", ">20% JSON validation failure rate within a batch.", "Hold for parser/provider-contract review.", False, "Do not rerun inside analysis phase."),
        ("hold_invalid_output_rate", "HOLD", "invalid_output_rate_exceeds_threshold", ">20% invalid output rate within a batch.", "Hold for review before expanding.", False, "Invalid outputs are evidence, not noise."),
        ("stop_pack_field_contamination", "STOP", "pack_field_contamination_detected", "Prompt/output contains fields outside assigned pack level.", "Stop and run governance repair.", True, "Controlled exposure requires clean pack boundaries."),
        ("stop_lane_b_c_detected", "STOP", "excluded_lane_b_or_c_field_detected", "Lane B or Lane C field appears in deterministic A-E prompt.", "Stop and repair prompt/pack assembly.", True, "Pack Q is excluded."),
        ("stop_fed_expectations_detected", "STOP", "fed_expectations_field_detected", "Fed expectations field appears in pack exposure.", "Stop and repair source/prompt contamination.", True, "Fed expectations remain blocked."),
        ("stop_upcoming_event_risk_label", "STOP", "upcoming_event_risk_label_detected", "UPCOMING_EVENT_RISK_LABEL appears in Pack A-E prompt.", "Stop and repair pack-level eligibility.", True, "Risk label was downgraded from early Lane A."),
        ("stop_accuracy_evaluation", "STOP", "accuracy_evaluation_detected", "Any accuracy/direction_ok/overall_ok calculation before Phase 9A-5.", "Stop and hold Phase 9 for governance review.", True, "Behavior before accuracy."),
        ("stop_production_write", "STOP", "production_write_detected", "Any write to production/v1/Predictions/Evaluation/Outcome sheets.", "Stop immediately and audit workbook writes.", True, "Shadow-only governance."),
        ("stop_rerun_without_new_run_id", "STOP", "provider_rerun_without_new_run_id", "Provider rerun replaces original cell or run_id.", "Stop and restore append-only evidence identity.", True, "No silent reruns."),
        ("hold_pack_coverage_below_threshold", "HOLD", "session_pack_coverage_below_threshold", "Selected session lacks complete deterministic Pack A-E coverage.", "Exclude session or explicitly approve gap-test batch.", False, "No missing Lane A fields for standard expansion."),
        ("stop_no_signal_normalization", "STOP", "no_signal_normalization_inconsistent", "Summary no-signal count disagrees with row-level compare/transition outputs.", "Stop and repair comparison layer.", True, "Phase 9A-3R fixed this once; keep it guarded."),
        ("hold_summary_counter_mismatch", "HOLD", "summary_counter_mismatch", "Summary row counts disagree with detail rows.", "Hold for data-quality review.", False, "May be non-blocking if explained."),
        ("continue_batch_review_pass", "CONTINUE", "post_batch_review_passed", "Post-batch review confirms raw archive complete, invalid rate <=20%, no governance violations.", "Proceed to next planned batch only after explicit approval.", False, "Continue rule, not automatic execution."),
    ]
    return [_stop_rule(generated_ts, *spec) for spec in specs]


def _readiness_row(
    generated_ts: str,
    check_id: str,
    area: str,
    description: str,
    status: str,
    evidence_sheet: str,
    evidence_value: Any,
    blocking: bool,
    action: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "readiness_check_id": check_id,
        "readiness_area": area,
        "check_description": description,
        "check_status": status,
        "evidence_sheet": evidence_sheet,
        "evidence_value": evidence_value,
        "blocking": _bool_text(blocking),
        "recommended_action": action,
        "notes": notes,
    }


def _build_readiness_rows(
    generated_ts: str,
    titles: Set[str],
    phase9a4_summary: Dict[str, Any],
    phase9a3r_summary: Dict[str, Any],
    prompt_validation_summary: Dict[str, Any],
    plan_rows: Sequence[Dict[str, Any]],
    selection_rows: Sequence[Dict[str, Any]],
    budget_rows: Sequence[Dict[str, Any]],
    batch_rows: Sequence[Dict[str, Any]],
    stop_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    phase9a4_confirmed = _norm(phase9a4_summary.get("final_interpretation")) in {
        "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY",
        "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY_WITH_WARNINGS",
    }
    repair_confirmed = _norm(phase9a3r_summary.get("final_interpretation")) == "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY_WITH_WARNINGS"
    pack_levels_defined = "Market_State_Pack_Level_Definition" in titles and "Market_State_Pack_Level_Items" in titles
    prompt_validation_ready = _norm(prompt_validation_summary.get("final_interpretation")) in {
        "PACK_EXPOSURE_PROMPT_VALIDATION_READY",
        "PACK_EXPOSURE_PROMPT_VALIDATION_READY_WITH_WARNINGS",
    }
    raw_available = "Pack_Exposure_Raw_Response_Archive" in titles
    behavior_complete = "Pack_Exposure_Behavior_Compare" in titles and "Pack_Exposure_Reasoning_Transitions" in titles
    invalid_rules = bool(stop_rows)
    safety_clean = all(
        _as_int(phase9a3r_summary.get(key)) == 0
        for key in [
            "accuracy_evaluation_count",
            "provider_call_count",
            "forecast_generation_count",
            "production_behavior_change_count",
        ]
    )
    rows = [
        _readiness_row(generated_ts, "exec_ready_phase9a4_design_exists", "phase9a4_design_exists", "Phase 9A-4 design summary is ready.", "PASS" if phase9a4_confirmed else "BLOCKED", "Pack_Behavior_Pattern_Discovery_Summary", phase9a4_summary.get("final_interpretation", ""), not phase9a4_confirmed, "Review Phase 9A-4 design before execution planning.", "Ready for design does not mean ready for accuracy."),
        _readiness_row(generated_ts, "exec_ready_phase9a3r_repair_confirmed", "phase9a3r_repair_confirmed", "Phase 9A-3R repair remains confirmed.", "PASS" if repair_confirmed else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", phase9a3r_summary.get("final_interpretation", ""), not repair_confirmed, "Repair behavior comparison before execution planning.", "No-signal normalization must remain consistent."),
        _readiness_row(generated_ts, "exec_ready_pack_levels_defined", "pack_levels_defined", "Pack A-E definitions exist.", "PASS" if pack_levels_defined else "BLOCKED", "Market_State_Pack_Level_Definition|Market_State_Pack_Level_Items", "present" if pack_levels_defined else "missing", not pack_levels_defined, "Rebuild Phase 8C pack-level design.", "Pack Q is not active."),
        _readiness_row(generated_ts, "exec_ready_prompt_validation_complete", "prompt_validation_complete", "Prompt validation dry-run completed.", "PASS" if prompt_validation_ready else "NEEDS_REVIEW", "Pack_Exposure_Prompt_Validation_Summary", prompt_validation_summary.get("final_interpretation", ""), False, "Review prompt validation before execution.", "Non-blocking for planning; blocking before execution if not ready."),
        _readiness_row(generated_ts, "exec_ready_raw_archive", "pilot_raw_response_archive_available", "Pilot raw response archive exists.", "PASS" if raw_available else "BLOCKED", "Pack_Exposure_Raw_Response_Archive", "present" if raw_available else "missing", not raw_available, "Require raw archive before execution.", "Raw response is source of truth."),
        _readiness_row(generated_ts, "exec_ready_behavior_comparison", "pilot_behavior_comparison_complete", "Pilot behavior comparison outputs exist.", "PASS" if behavior_complete else "BLOCKED", "Pack_Exposure_Behavior_Compare|Pack_Exposure_Reasoning_Transitions", "present" if behavior_complete else "missing", not behavior_complete, "Rebuild Phase 9A-3R outputs.", "Behavior comparison seeds execution planning."),
        _readiness_row(generated_ts, "exec_ready_invalid_rules", "invalid_output_rules_defined", "Invalid output rules are defined.", "PASS" if invalid_rules else "BLOCKED", OUTPUT_STOP_HOLD_RULES_SHEET, len(stop_rows), not invalid_rules, "Define invalid-output rules.", "Anthropic Pack D remains canonical invalid example."),
        _readiness_row(generated_ts, "exec_ready_session_rules", "session_selection_rules_defined", "Session selection rules exist.", "PASS" if selection_rows else "BLOCKED", OUTPUT_SESSION_SELECTION_SHEET, len(selection_rows), not bool(selection_rows), "Define session selection rules.", "Complete deterministic pack coverage required."),
        _readiness_row(generated_ts, "exec_ready_call_budget", "call_budget_defined", "Call budgets exist.", "PASS" if budget_rows else "BLOCKED", OUTPUT_CALL_BUDGET_SHEET, len(budget_rows), not bool(budget_rows), "Define call budget.", "Tier 1 budget is 45 calls."),
        _readiness_row(generated_ts, "exec_ready_batch_strategy", "batch_strategy_defined", "Batch strategy exists.", "PASS" if batch_rows else "BLOCKED", OUTPUT_BATCH_STRATEGY_SHEET, len(batch_rows), not bool(batch_rows), "Define batch strategy.", "Small batch before large replay."),
        _readiness_row(generated_ts, "exec_ready_stop_hold_rules", "stop_hold_rules_defined", "Stop/hold rules exist.", "PASS" if stop_rows else "BLOCKED", OUTPUT_STOP_HOLD_RULES_SHEET, len(stop_rows), not bool(stop_rows), "Define stop/hold rules.", "Governance safety is explicit."),
        _readiness_row(generated_ts, "exec_ready_accuracy_excluded", "accuracy_excluded", "Accuracy remains excluded.", "PASS" if _as_int(phase9a3r_summary.get("accuracy_evaluation_count")) == 0 else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", phase9a3r_summary.get("accuracy_evaluation_count", ""), _as_int(phase9a3r_summary.get("accuracy_evaluation_count")) != 0, "Hold if accuracy was introduced.", "Phase 9A-5 remains blocked."),
        _readiness_row(generated_ts, "exec_ready_provider_calls_excluded_plan", "provider_calls_excluded_in_plan_phase", "This planning phase made no provider calls.", "PASS", OUTPUT_SUMMARY_SHEET, 0, False, "No action.", "Planning only."),
        _readiness_row(generated_ts, "exec_ready_production_excluded", "production_changes_excluded", "Production behavior remains unchanged.", "PASS" if safety_clean else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", "safety_counters_zero" if safety_clean else "safety_counter_nonzero", not safety_clean, "Hold for governance review.", "Shadow-only."),
        _readiness_row(generated_ts, "exec_ready_small_expansion", "ready_for_small_expansion_execution", "Tier 1 small expansion can be planned for execution review.", "PASS_WITH_WARNINGS" if phase9a4_confirmed and repair_confirmed and safety_clean else "BLOCKED", OUTPUT_SUMMARY_SHEET, "TIER_1_SMALL_EXPANSION", not (phase9a4_confirmed and repair_confirmed and safety_clean), "Proceed to Phase 9A-4E review before execution.", "Warnings remain because one-session evidence cannot generalize."),
        _readiness_row(generated_ts, "exec_ready_accuracy_eval", "ready_for_accuracy_evaluation", "Accuracy phase remains blocked.", "BLOCKED", OUTPUT_SUMMARY_SHEET, "FALSE", True, "Do not proceed to Phase 9A-5.", "Behavior patterns must stabilize first."),
        _readiness_row(generated_ts, "exec_ready_production", "ready_for_production", "Production remains blocked.", "BLOCKED", OUTPUT_SUMMARY_SHEET, "FALSE", True, "Do not proceed to production.", "No production behavior changes."),
    ]
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_PATTERN_EXECUTION_PLAN", OUTPUT_EXECUTION_PLAN_SHEET, "behavior_pattern_execution_plan"),
        ("PACK_BEHAVIOR_PATTERN_SESSION_SELECTION_PLAN", OUTPUT_SESSION_SELECTION_SHEET, "behavior_pattern_session_selection_plan"),
        ("PACK_BEHAVIOR_PATTERN_CALL_BUDGET", OUTPUT_CALL_BUDGET_SHEET, "behavior_pattern_call_budget"),
        ("PACK_BEHAVIOR_PATTERN_BATCH_STRATEGY", OUTPUT_BATCH_STRATEGY_SHEET, "behavior_pattern_batch_strategy"),
        ("PACK_BEHAVIOR_PATTERN_STOP_HOLD_RULES", OUTPUT_STOP_HOLD_RULES_SHEET, "behavior_pattern_stop_hold_rules"),
        ("PACK_BEHAVIOR_PATTERN_EXECUTION_READINESS_AUDIT", OUTPUT_READINESS_AUDIT_SHEET, "behavior_pattern_execution_readiness_audit"),
        ("PACK_BEHAVIOR_PATTERN_EXECUTION_PLAN_SUMMARY", OUTPUT_SUMMARY_SHEET, "behavior_pattern_execution_plan_summary"),
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
            "notes": "Phase 9A-4E execution plan only; no provider calls, forecasts, accuracy evaluation, or production behavior changes.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4E behavior pattern execution plan.")
    return parser.parse_args(argv)


def build_pack_behavior_pattern_execution_plan_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    plan_id = _run_id(generated_ts)
    creds = load_credentials()
    service = build_sheets_service(creds)
    titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_support: List[str] = []
    missing_governance: List[str] = []

    for sheet in PHASE9A4_DESIGN_SHEETS + PHASE9A3R_SHEETS + PHASE9A2_SOURCE_SHEETS + PACK_DESIGN_SHEETS:
        if sheet not in titles:
            missing_required.append(sheet)
    for sheet in SUPPORT_SHEETS:
        if sheet not in titles:
            missing_support.append(sheet)
    for sheet in OPTIONAL_GOVERNANCE_SHEETS:
        if sheet not in titles:
            missing_governance.append(sheet)

    phase9a4_summary = _latest(_read_if_exists(service, titles, "Pack_Behavior_Pattern_Discovery_Summary", missing_required))
    phase9a3r_summary = _latest(_read_if_exists(service, titles, "Pack_Exposure_Behavior_Compare_Summary", missing_required))
    prompt_validation_summary = _latest(_read_if_exists(service, titles, "Pack_Exposure_Prompt_Validation_Summary", missing_support))

    execution_rows = _build_execution_plan_rows(generated_ts, plan_id)
    selection_rows = _build_session_selection_rows(generated_ts)
    budget_rows = _build_budget_rows(generated_ts)
    batch_rows = _build_batch_rows(generated_ts)
    stop_rows = _build_stop_rows(generated_ts)
    readiness_rows = _build_readiness_rows(
        generated_ts,
        titles,
        phase9a4_summary,
        phase9a3r_summary,
        prompt_validation_summary,
        execution_rows,
        selection_rows,
        budget_rows,
        batch_rows,
        stop_rows,
    )

    phase9a4_confirmed = _norm(phase9a4_summary.get("final_interpretation")) in {
        "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY",
        "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY_WITH_WARNINGS",
    }
    repair_confirmed = _norm(phase9a3r_summary.get("final_interpretation")) == "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY_WITH_WARNINGS"
    safety = {
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "production_behavior_change_count": 0,
    }
    safety_clean = all(_as_int(phase9a3r_summary.get(key)) == 0 for key in safety)
    blocking_unexpected = [
        row
        for row in readiness_rows
        if _upper(row.get("blocking")) == "TRUE"
        and _norm(row.get("readiness_area")) not in {"ready_for_accuracy_evaluation", "ready_for_production"}
    ]
    warning_checks = [row for row in readiness_rows if _upper(row.get("check_status")) == "PASS_WITH_WARNINGS"]
    ready_small_expansion = phase9a4_confirmed and repair_confirmed and safety_clean and not blocking_unexpected

    if not safety_clean or blocking_unexpected:
        build_status = "FAIL"
        interpretation = "BEHAVIOR_PATTERN_EXECUTION_PLAN_BLOCKED"
        recommended_next = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
    elif warning_checks or missing_support or missing_governance:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "BEHAVIOR_PATTERN_EXECUTION_PLAN_READY_WITH_WARNINGS"
        recommended_next = "PROCEED_TO_PHASE9A4E_REVIEW"
    else:
        build_status = "PASS"
        interpretation = "BEHAVIOR_PATTERN_EXECUTION_PLAN_READY"
        recommended_next = "PROCEED_TO_PHASE9A4E_REVIEW"

    first_tier_sessions = 3
    first_expected_calls = first_tier_sessions * CALLS_PER_SESSION
    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "build_status": build_status,
        "final_interpretation": interpretation,
        "execution_components_defined": len(execution_rows),
        "session_selection_rules_defined": len(selection_rows),
        "call_budget_rows_defined": len(budget_rows),
        "batch_strategy_rows_defined": len(batch_rows),
        "stop_hold_rules_defined": len(stop_rows),
        "readiness_checks_defined": len(readiness_rows),
        "phase9a4_design_confirmed": _bool_text(phase9a4_confirmed),
        "phase9a3r_repair_confirmed": _bool_text(repair_confirmed),
        "recommended_first_execution_tier": "TIER_1_SMALL_EXPANSION",
        "recommended_first_execution_session_count": first_tier_sessions,
        "expected_provider_calls_first_execution": first_expected_calls,
        "maximum_provider_calls_first_execution": first_expected_calls,
        "single_session_generalization_allowed": "FALSE",
        **safety,
        "ready_for_phase9a4_small_expansion_execution": _bool_text(ready_small_expansion),
        "ready_for_phase9a5_accuracy_evaluation": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next,
        "notes": _truncate_text(
            json.dumps(
                {
                    "missing_required": sorted(set(missing_required)),
                    "missing_support": sorted(set(missing_support)),
                    "missing_governance_in_diagnostics": sorted(set(missing_governance)),
                    "first_execution_budget": "3 sessions x 5 packs x 3 providers = 45 calls",
                    "planning_only": True,
                },
                ensure_ascii=True,
            ),
            500,
        ),
    }

    for sheet, headers, rows in [
        (OUTPUT_EXECUTION_PLAN_SHEET, EXECUTION_PLAN_HEADERS, execution_rows),
        (OUTPUT_SESSION_SELECTION_SHEET, SESSION_SELECTION_HEADERS, selection_rows),
        (OUTPUT_CALL_BUDGET_SHEET, CALL_BUDGET_HEADERS, budget_rows),
        (OUTPUT_BATCH_STRATEGY_SHEET, BATCH_STRATEGY_HEADERS, batch_rows),
        (OUTPUT_STOP_HOLD_RULES_SHEET, STOP_HOLD_HEADERS, stop_rows),
        (OUTPUT_READINESS_AUDIT_SHEET, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": interpretation,
        "file_created": "automation/build_pack_behavior_pattern_execution_plan_v0.py",
        "sheets_written": {
            OUTPUT_EXECUTION_PLAN_SHEET: len(execution_rows),
            OUTPUT_SESSION_SELECTION_SHEET: len(selection_rows),
            OUTPUT_CALL_BUDGET_SHEET: len(budget_rows),
            OUTPUT_BATCH_STRATEGY_SHEET: len(batch_rows),
            OUTPUT_STOP_HOLD_RULES_SHEET: len(stop_rows),
            OUTPUT_READINESS_AUDIT_SHEET: len(readiness_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "execution_components_defined": len(execution_rows),
        "session_selection_rules_defined": len(selection_rows),
        "call_budget_rows_defined": len(budget_rows),
        "batch_strategy_rows_defined": len(batch_rows),
        "stop_hold_rules_defined": len(stop_rows),
        "readiness_checks_defined": len(readiness_rows),
        "recommended_first_execution_tier": summary["recommended_first_execution_tier"],
        "recommended_first_execution_session_count": summary["recommended_first_execution_session_count"],
        "expected_provider_calls_first_execution": summary["expected_provider_calls_first_execution"],
        "maximum_provider_calls_first_execution": summary["maximum_provider_calls_first_execution"],
        "ready_for_phase9a4_small_expansion_execution": summary["ready_for_phase9a4_small_expansion_execution"],
        "ready_for_phase9a5_accuracy_evaluation": summary["ready_for_phase9a5_accuracy_evaluation"],
        "ready_for_production": summary["ready_for_production"],
        "accuracy_evaluation_count": summary["accuracy_evaluation_count"],
        "provider_call_count": summary["provider_call_count"],
        "forecast_generation_count": summary["forecast_generation_count"],
        "production_behavior_change_count": summary["production_behavior_change_count"],
        "recommended_next_step": recommended_next,
        "registry": registry,
        "missing_required": sorted(set(missing_required)),
        "missing_support": sorted(set(missing_support)),
        "missing_governance_in_diagnostics": sorted(set(missing_governance)),
    }


def main() -> None:
    result = build_pack_behavior_pattern_execution_plan_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
