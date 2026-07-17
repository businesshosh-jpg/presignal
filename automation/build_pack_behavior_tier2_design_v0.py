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


SCHEMA_VERSION = "presignal_v2_behavior_tier2_design_0.1"
TIER2_DESIGN_VERSION = "behavior_tier2_expansion_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4Z"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_TIER2_EXPERIMENT_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_GENERALIZATION_AUDIT = "Pack_Behavior_Generalization_Audit"
INPUT_PROVIDER_CONSISTENCY = "Pack_Behavior_Provider_Consistency_Audit"
INPUT_TRANSITION_REPRO = "Pack_Behavior_Transition_Reproducibility_Audit"
INPUT_FIELD_STABILITY = "Pack_Behavior_Field_Stability_Audit"
INPUT_NOSIGNAL_STABILITY = "Pack_Behavior_NoSignal_Stability_Audit"
INPUT_INVALID_GENERALIZATION = "Pack_Behavior_Invalid_Output_Generalization_Audit"
INPUT_HYPOTHESES = "Pack_Behavior_Generalization_Hypotheses"
INPUT_GENERALIZATION_SUMMARY = "Pack_Behavior_Generalization_Summary"

PLANNING_INPUTS = [
    "Pack_Behavior_Pattern_Discovery_Design",
    "Pack_Behavior_Pattern_Metrics_Definition",
    "Pack_Behavior_Pattern_Grouping_Rules",
    "Pack_Behavior_Pattern_Invalid_Output_Rules",
    "Pack_Behavior_Pattern_Readiness_Audit",
    "Pack_Behavior_Pattern_Discovery_Summary",
    "Pack_Behavior_Pattern_Execution_Plan",
    "Pack_Behavior_Pattern_Session_Selection_Plan",
    "Pack_Behavior_Pattern_Call_Budget",
    "Pack_Behavior_Pattern_Batch_Strategy",
    "Pack_Behavior_Pattern_Stop_Hold_Rules",
    "Pack_Behavior_Pattern_Execution_Readiness_Audit",
    "Pack_Behavior_Pattern_Execution_Plan_Summary",
]

OUTPUT_EXPERIMENT_DESIGN = "Pack_Behavior_Tier2_Experiment_Design"
OUTPUT_HYPOTHESIS_PLAN = "Pack_Behavior_Tier2_Hypothesis_Test_Plan"
OUTPUT_SESSION_STRATEGY = "Pack_Behavior_Tier2_Session_Strategy"
OUTPUT_CALL_BUDGET = "Pack_Behavior_Tier2_Call_Budget"
OUTPUT_STOP_RULES = "Pack_Behavior_Tier2_Stop_Rules"
OUTPUT_SUCCESS_CRITERIA = "Pack_Behavior_Tier2_Success_Criteria"
OUTPUT_READINESS_AUDIT = "Pack_Behavior_Tier2_Readiness_Audit"
OUTPUT_SUMMARY = "Pack_Behavior_Tier2_Design_Summary"

PROVIDERS = "OpenAI|Gemini|Anthropic"
PACK_LEVELS = "Pack A|Pack B|Pack C|Pack D|Pack E"
PACK_LEVEL_COUNT = 5
PROVIDER_COUNT = 3

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "hypothesis_id",
    "priority",
    "research_question",
    "expected_behavior",
    "required_pack_transitions",
    "required_field_families",
    "required_providers",
    "minimum_sessions",
    "minimum_valid_observations",
    "maximum_invalid_rate",
    "success_criteria",
    "failure_criteria",
    "promotion_rule",
    "tier2_priority",
    "tier3_candidate",
    "accuracy_excluded",
    "production_excluded",
    "notes",
]

HYPOTHESIS_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "hypothesis_id",
    "hypothesis_type",
    "current_evidence_status",
    "source_pattern_ids",
    "observable_metrics",
    "primary_grouping_dimensions",
    "required_output_sheets_future",
    "minimum_session_coverage",
    "minimum_provider_coverage",
    "minimum_pack_transition_coverage",
    "invalid_output_policy",
    "analysis_exclusions",
    "tier2_test_design_hint",
    "notes",
]

SESSION_STRATEGY_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "strategy_id",
    "strategy_name",
    "strategy_purpose",
    "target_session_min",
    "target_session_max",
    "selection_priority",
    "inclusion_criteria",
    "exclusion_criteria",
    "diversity_dimension",
    "required_pack_coverage",
    "required_prompt_validation",
    "hypotheses_supported",
    "notes",
]

CALL_BUDGET_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "budget_tier",
    "session_count",
    "pack_levels_per_session",
    "providers_per_pack",
    "expected_provider_calls",
    "allowed_provider_retries",
    "maximum_provider_calls",
    "approval_required_before_execution",
    "execution_allowed_in_this_phase",
    "cost_risk_level",
    "quota_risk_level",
    "notes",
]

STOP_RULE_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "stop_rule_id",
    "rule_type",
    "rule_name",
    "trigger_condition",
    "threshold",
    "blocking",
    "required_action",
    "applies_to",
    "notes",
]

SUCCESS_CRITERIA_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
    "hypothesis_id",
    "success_metric",
    "minimum_threshold",
    "failure_threshold",
    "promotion_threshold",
    "confidence_interpretation",
    "forbidden_interpretation",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "tier2_design_version",
    "tier2_design_id",
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
    "tier2_design_version",
    "tier2_design_id",
    "build_status",
    "final_interpretation",
    "hypotheses_planned",
    "high_priority_hypotheses_planned",
    "medium_priority_hypotheses_planned",
    "hold_hypotheses_planned",
    "sessions_min_planned",
    "sessions_max_planned",
    "provider_calls_min_planned",
    "provider_calls_max_planned",
    "providers_included",
    "pack_levels_included",
    "stop_rules_defined",
    "success_criteria_defined",
    "readiness_checks_defined",
    "tier2_design_complete",
    "tier2_execution_started",
    "accuracy_evaluation_count",
    "provider_call_count",
    "forecast_generation_count",
    "production_behavior_change_count",
    "ready_for_tier2_execution_planning",
    "ready_for_tier2_execution",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _design_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_tier2_design_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _priority(row: Dict[str, Any]) -> str:
    return _upper(row.get("tier2_test_priority")) or "MEDIUM"


def _min_sessions(priority: str, status: str) -> int:
    if priority == "HIGH":
        return 5
    if priority == "HOLD" or status == "INVALID_OUTPUT_LIMITED":
        return 5
    return 5


def _min_valid_observations(priority: str, status: str) -> int:
    if priority == "HIGH":
        return 12
    if priority == "HOLD" or status == "INVALID_OUTPUT_LIMITED":
        return 5
    return 8


def _max_invalid_rate(priority: str, status: str) -> str:
    if priority == "HOLD" or status == "INVALID_OUTPUT_LIMITED":
        return "0.20_MONITORING_THRESHOLD"
    return "0.20"


def _transitions_for(row: Dict[str, Any]) -> str:
    value = _norm(row.get("pack_transitions_supporting"))
    return value or "A_to_B|B_to_C|C_to_D|D_to_E|A_to_D|A_to_E"


def _families_for(row: Dict[str, Any]) -> str:
    value = _norm(row.get("fields_or_families_involved"))
    return value or "usdjpy_trend|upcoming_larger_events|treasury_yields|dxy"


def _providers_for(row: Dict[str, Any]) -> str:
    value = _norm(row.get("providers_supporting"))
    if _priority(row) == "HOLD":
        return value or "Anthropic"
    return value or PROVIDERS


def _success_criteria(row: Dict[str, Any]) -> str:
    hid = _norm(row.get("hypothesis_id"))
    if hid == "HYP_USDJPY_TREND_REASONING":
        return "USDJPY trend family is explicitly used or changes reasoning in >=50% of valid observations across >=3 sessions and >=2 providers."
    if hid == "HYP_A_TO_B_TARGET_STATE_VALUE":
        return "A_to_B shows behavior transition in >=60% of valid comparisons across >=3 sessions."
    if hid == "HYP_GEMINI_HIGH_SENSITIVITY":
        return "Gemini shows material direction/confidence/no-signal/causal movement in >=60% of valid transitions across >=3 sessions."
    if hid == "HYP_OPENAI_CAUSAL_STABLE":
        return "OpenAI causal chains change in >=60% of valid transitions while no-signal remains stable in >=70% of valid transitions."
    if hid == "HYP_PACK_E_REDUNDANCY":
        return "D_to_E has lower behavior-change and transition-complexity rates than A_to_B and A_to_D across >=5 sessions."
    if hid == "HYP_ANTHROPIC_DE_INVALID_RISK":
        return "Anthropic D/E invalid output rate stays <=20%; if above threshold, keep D/E Anthropic cells invalid-output-limited."
    if hid == "HYP_TREASURY_UNDERDETERMINED":
        return "Treasury fields reach explicit use or changed-reasoning in >=25% of valid D/E observations, otherwise remain underdetermined."
    return "Pattern repeats across >=3 sessions with >=8 valid observations and no governance violations."


def _failure_criteria(row: Dict[str, Any]) -> str:
    hid = _norm(row.get("hypothesis_id"))
    if hid == "HYP_ANTHROPIC_DE_INVALID_RISK":
        return "Invalid output rate >20% or raw archive missing for any attempted call."
    if hid == "HYP_PACK_E_REDUNDANCY":
        return "D_to_E consistently produces distinct behavior-change rates comparable to A_to_B/A_to_D."
    return "Pattern is not repeated across at least 2 sessions or valid observations fall below minimum due to invalid outputs."


def _promotion_rule(row: Dict[str, Any]) -> str:
    hid = _norm(row.get("hypothesis_id"))
    if hid == "HYP_ANTHROPIC_DE_INVALID_RISK":
        return "Promote to provider-output-risk mitigation design only; do not promote as behavior pattern."
    if hid == "HYP_TREASURY_UNDERDETERMINED":
        return "Promote from underdetermined to candidate behavior pattern only if explicit family influence crosses success threshold."
    return "Promote to Tier 3 stability-check candidate only after Tier 2 repeats across >=5 sessions and >=12 valid observations."


def _confidence_interpretation(row: Dict[str, Any]) -> str:
    return "Behavioral confidence only; no forecast accuracy or correctness interpretation."


def _experiment_rows(generated_ts: str, design_id: str, hypotheses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in hypotheses:
        priority = _priority(row)
        status = _upper(row.get("current_evidence_status"))
        hid = _norm(row.get("hypothesis_id"))
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "hypothesis_id": hid,
                "priority": priority,
                "research_question": f"Does Tier 2 reproduce this behavior hypothesis: {_norm(row.get('hypothesis_statement'))}",
                "expected_behavior": _norm(row.get("hypothesis_statement")),
                "required_pack_transitions": _transitions_for(row),
                "required_field_families": _families_for(row),
                "required_providers": _providers_for(row),
                "minimum_sessions": _min_sessions(priority, status),
                "minimum_valid_observations": _min_valid_observations(priority, status),
                "maximum_invalid_rate": _max_invalid_rate(priority, status),
                "success_criteria": _success_criteria(row),
                "failure_criteria": _failure_criteria(row),
                "promotion_rule": _promotion_rule(row),
                "tier2_priority": priority,
                "tier3_candidate": "FALSE" if priority == "HOLD" else "TRUE",
                "accuracy_excluded": "TRUE",
                "production_excluded": "TRUE",
                "notes": _truncate_text(_norm(row.get("tier2_test_design_hint")) or _norm(row.get("notes")), 500),
            }
        )
    return rows


def _hypothesis_plan_rows(generated_ts: str, design_id: str, hypotheses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in hypotheses:
        hid = _norm(row.get("hypothesis_id"))
        metrics = [
            "behavior_change_rate",
            "mean_transition_complexity_score",
            "causal_chain_change_rate",
            "field_used_rate",
            "field_changed_reasoning_rate",
            "no_signal_change_rate",
            "material_confidence_change_rate",
            "invalid_output_rate",
        ]
        if "INVALID" in _upper(row.get("current_evidence_status")):
            metrics = ["invalid_output_rate", "malformed_or_truncated_count", "raw_archive_missing_count", "valid_transition_rate"]
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "hypothesis_id": hid,
                "hypothesis_type": _norm(row.get("hypothesis_type")),
                "current_evidence_status": _norm(row.get("current_evidence_status")),
                "source_pattern_ids": _norm(row.get("supporting_pattern_ids")),
                "observable_metrics": "|".join(metrics),
                "primary_grouping_dimensions": "session_id|provider|pack_transition|candidate_family|candidate_field|pack_level",
                "required_output_sheets_future": "Pack_Behavior_Discovery_Transitions|Pack_Behavior_Discovery_Field_Influence|Pack_Behavior_Discovery_NoSignal|Pack_Behavior_Discovery_Invalid_Output",
                "minimum_session_coverage": _min_sessions(_priority(row), _upper(row.get("current_evidence_status"))),
                "minimum_provider_coverage": 3 if _priority(row) != "HOLD" else 1,
                "minimum_pack_transition_coverage": _transitions_for(row),
                "invalid_output_policy": "preserve_and_isolate_invalid_cells; no silent reruns; no imputation",
                "analysis_exclusions": "accuracy|direction_correctness|provider_ranking|pack_ranking|production",
                "tier2_test_design_hint": _truncate_text(_norm(row.get("tier2_test_design_hint")), 500),
                "notes": "Every provider call must map to at least one explicit hypothesis.",
            }
        )
    return rows


def _session_strategy_rows(generated_ts: str, design_id: str, hypotheses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_h = "|".join(_norm(row.get("hypothesis_id")) for row in hypotheses if _norm(row.get("hypothesis_id")))
    high_h = "|".join(_norm(row.get("hypothesis_id")) for row in hypotheses if _priority(row) == "HIGH")
    rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "tier2_design_version": TIER2_DESIGN_VERSION,
            "tier2_design_id": design_id,
            "strategy_id": "T2_SESSION_001",
            "strategy_name": "target_5_to_10_sessions",
            "strategy_purpose": "Expand from 4 analyzed sessions to a behavior-pattern candidate sample without launching accuracy evaluation.",
            "target_session_min": 5,
            "target_session_max": 10,
            "selection_priority": "HIGH",
            "inclusion_criteria": "complete deterministic pack coverage|successful shadow acquisition|usable event/session context|valid prompt dry-run coverage|no unresolved source-mapping blockers",
            "exclusion_criteria": "incomplete deterministic pack|weekend-boundary USDJPY gaps unless deliberately sampled|blocked pack readiness|unresolved prompt-validation issue|known production contamination risk",
            "diversity_dimension": "macro_event_family|event_importance|calendar_density|USDJPY_state|rates_dollar_context|session_date",
            "required_pack_coverage": "Pack A-E available for all selected sessions",
            "required_prompt_validation": "latest prompt validation ready or ready_with_warnings",
            "hypotheses_supported": all_h,
            "notes": "Select sessions to maximize diversity rather than repeat a single macro structure.",
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "tier2_design_version": TIER2_DESIGN_VERSION,
            "tier2_design_id": design_id,
            "strategy_id": "T2_SESSION_002",
            "strategy_name": "high_priority_hypothesis_coverage",
            "strategy_purpose": "Ensure each high-priority hypothesis receives sufficient transition and provider observations.",
            "target_session_min": 5,
            "target_session_max": 10,
            "selection_priority": "HIGH",
            "inclusion_criteria": "sessions with full USDJPY trend fields and valid A_to_B/A_to_D/A_to_E comparisons possible",
            "exclusion_criteria": "sessions where target-state fields are missing or prompt validation fails",
            "diversity_dimension": "USDJPY trend direction|volatility|event cluster density",
            "required_pack_coverage": "A|B|D|E",
            "required_prompt_validation": "required",
            "hypotheses_supported": high_h,
            "notes": "Prioritize HYP_USDJPY_TREND_REASONING, HYP_A_TO_B_TARGET_STATE_VALUE, HYP_GEMINI_HIGH_SENSITIVITY.",
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "tier2_design_version": TIER2_DESIGN_VERSION,
            "tier2_design_id": design_id,
            "strategy_id": "T2_SESSION_003",
            "strategy_name": "invalid_output_risk_monitoring",
            "strategy_purpose": "Preserve visibility into Anthropic D/E truncation and provider-error risks without silent retries.",
            "target_session_min": 5,
            "target_session_max": 10,
            "selection_priority": "MEDIUM",
            "inclusion_criteria": "sessions with Pack D/E prompt payloads representative of Tier 1",
            "exclusion_criteria": "sessions requiring prompt/schema repair before execution",
            "diversity_dimension": "provider_output_validity|pack_level|prompt_payload_size",
            "required_pack_coverage": "D|E",
            "required_prompt_validation": "required",
            "hypotheses_supported": "HYP_ANTHROPIC_DE_INVALID_RISK|HYP_PACK_E_REDUNDANCY",
            "notes": "Invalid outputs remain evidence and must not be silently repaired or replaced.",
        },
    ]
    return rows


def _call_budget_rows(generated_ts: str, design_id: str) -> List[Dict[str, Any]]:
    rows = []
    for tier, session_count, risk in [
        ("TIER2_MINIMUM", 5, "MEDIUM"),
        ("TIER2_RECOMMENDED", 7, "MEDIUM"),
        ("TIER2_MAXIMUM", 10, "HIGH"),
    ]:
        calls = session_count * PACK_LEVEL_COUNT * PROVIDER_COUNT
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "budget_tier": tier,
                "session_count": session_count,
                "pack_levels_per_session": PACK_LEVEL_COUNT,
                "providers_per_pack": PROVIDER_COUNT,
                "expected_provider_calls": calls,
                "allowed_provider_retries": 0,
                "maximum_provider_calls": calls,
                "approval_required_before_execution": "TRUE",
                "execution_allowed_in_this_phase": "FALSE",
                "cost_risk_level": risk,
                "quota_risk_level": risk,
                "notes": "Execution phase may define reruns only as new run_id observations; no silent replacements.",
            }
        )
    return rows


def _stop_rule_rows(generated_ts: str, design_id: str) -> List[Dict[str, Any]]:
    rules = [
        ("T2_STOP_001", "STOP", "raw_archive_failure", "raw archive cannot be created or append fails after retries", "any", "STOP_EXECUTION_IMMEDIATELY"),
        ("T2_STOP_002", "STOP", "provider_call_cap_exceeded", "provider call count would exceed approved cap", "any excess call", "STOP_BEFORE_EXCESS_CALL"),
        ("T2_STOP_003", "HOLD", "invalid_output_rate_threshold", "invalid output rate exceeds threshold", ">20% batch invalid", "HOLD_FOR_REVIEW"),
        ("T2_STOP_004", "HOLD", "json_validation_failure_rate_threshold", "json validation failure rate exceeds threshold", ">20% batch invalid", "HOLD_FOR_REVIEW"),
        ("T2_STOP_005", "STOP", "provider_outage", "provider outage prevents planned cells", "provider failure cluster", "STOP_OR_HOLD_FOR_REVIEW"),
        ("T2_STOP_006", "STOP", "pack_contamination", "Pack Q, fed_expectations, UPCOMING_EVENT_RISK_LABEL, Lane B, or Lane C fields appear", "any contamination", "STOP_EXECUTION_IMMEDIATELY"),
        ("T2_STOP_007", "STOP", "accuracy_evaluation_detected", "accuracy or direction correctness evaluation occurs", "any", "STOP_EXECUTION_IMMEDIATELY"),
        ("T2_STOP_008", "STOP", "production_write_detected", "production or v1 write occurs", "any", "STOP_EXECUTION_IMMEDIATELY"),
        ("T2_STOP_009", "HOLD", "summary_counter_mismatch", "summary counters disagree with row-level outputs", "any mismatch", "HOLD_FOR_REVIEW"),
        ("T2_STOP_010", "HOLD", "no_signal_normalization_inconsistent", "no-signal source logic becomes inconsistent", "any inconsistency", "HOLD_FOR_REVIEW"),
        ("T2_STOP_011", "HOLD", "anthropic_de_invalid_cluster", "Anthropic D/E truncation risk exceeds expected monitor band", ">20% Anthropic D/E invalid", "HOLD_FOR_PROMPT_SCHEMA_REVIEW"),
        ("T2_STOP_012", "REVIEW", "tier2_hypothesis_coverage_gap", "high-priority hypotheses lack minimum valid observations", "post-batch", "REVIEW_BEFORE_TIER3"),
    ]
    rows = []
    for rid, rule_type, name, trigger, threshold, action in rules:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "stop_rule_id": rid,
                "rule_type": rule_type,
                "rule_name": name,
                "trigger_condition": trigger,
                "threshold": threshold,
                "blocking": "TRUE" if rule_type == "STOP" else "FALSE",
                "required_action": action,
                "applies_to": "Phase 9A-4Z execution planning and future Tier 2 execution",
                "notes": "No production stop/routing behavior is created by this design.",
            }
        )
    return rows


def _success_rows(generated_ts: str, design_id: str, hypotheses: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in hypotheses:
        hid = _norm(row.get("hypothesis_id"))
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "hypothesis_id": hid,
                "success_metric": "behavioral_recurrence_without_accuracy",
                "minimum_threshold": _success_criteria(row),
                "failure_threshold": _failure_criteria(row),
                "promotion_threshold": _promotion_rule(row),
                "confidence_interpretation": _confidence_interpretation(row),
                "forbidden_interpretation": "forecast accuracy|direction correctness|provider ranking|best pack|production readiness",
                "notes": "Success criteria are behavior-only and hypothesis-specific.",
            }
        )
    return rows


def _readiness_rows(
    generated_ts: str,
    design_id: str,
    hypotheses: Sequence[Dict[str, Any]],
    generalization_summary: Dict[str, Any],
    missing_inputs: Sequence[str],
) -> List[Dict[str, Any]]:
    checks = [
        ("T2_READY_001", "generalization_audit_exists", "Phase 9A-4Y generalization audit exists", bool(generalization_summary), INPUT_GENERALIZATION_SUMMARY, _norm(generalization_summary.get("final_interpretation")), True, "continue"),
        ("T2_READY_002", "tier2_design_input_ready", "ready_for_tier2_design is TRUE", _upper(generalization_summary.get("ready_for_tier2_design")) == "TRUE", INPUT_GENERALIZATION_SUMMARY, _norm(generalization_summary.get("ready_for_tier2_design")), True, "repair if not ready"),
        ("T2_READY_003", "hypotheses_available", "Hypotheses exist for Tier 2 planning", len(hypotheses) > 0, INPUT_HYPOTHESES, len(hypotheses), True, "repair if missing"),
        ("T2_READY_004", "high_priority_hypotheses_available", "High-priority hypotheses are present", any(_priority(row) == "HIGH" for row in hypotheses), INPUT_HYPOTHESES, sum(1 for row in hypotheses if _priority(row) == "HIGH"), True, "repair if missing"),
        ("T2_READY_005", "session_strategy_defined", "Session strategy defines 5-10 sessions", True, OUTPUT_SESSION_STRATEGY, "5-10", True, "continue"),
        ("T2_READY_006", "call_budget_defined", "Call budget defines 75-150 calls", True, OUTPUT_CALL_BUDGET, "75-150", True, "continue"),
        ("T2_READY_007", "stop_rules_defined", "Stop rules protect raw archive and governance", True, OUTPUT_STOP_RULES, "12 rules", True, "continue"),
        ("T2_READY_008", "accuracy_excluded", "Accuracy evaluation remains excluded", True, OUTPUT_SUMMARY, "0", True, "continue"),
        ("T2_READY_009", "production_excluded", "Production behavior remains excluded", True, OUTPUT_SUMMARY, "0", True, "continue"),
        ("T2_READY_010", "tier2_execution_not_started", "Tier 2 is not executed by this phase", True, OUTPUT_SUMMARY, "FALSE", True, "continue"),
        ("T2_READY_011", "missing_input_check", "Required input sheets available", not missing_inputs, "input_sheet_scan", "|".join(missing_inputs), False, "review limitations"),
        ("T2_READY_012", "ready_for_execution_planning", "Ready for Tier 2 execution plan, not execution", True, OUTPUT_SUMMARY, "TRUE", True, "proceed to execution plan"),
    ]
    rows = []
    for cid, area, description, ok, sheet, value, blocking, action in checks:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "tier2_design_version": TIER2_DESIGN_VERSION,
                "tier2_design_id": design_id,
                "readiness_check_id": cid,
                "readiness_area": area,
                "check_description": description,
                "check_status": "PASS" if ok else ("BLOCKED" if blocking else "PASS_WITH_WARNINGS"),
                "evidence_sheet": sheet,
                "evidence_value": value,
                "blocking": "TRUE" if blocking else "FALSE",
                "recommended_action": action,
                "notes": "Ready for execution planning does not mean ready for execution, accuracy, or production.",
            }
        )
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_TIER2_EXPERIMENT_DESIGN", OUTPUT_EXPERIMENT_DESIGN, "behavior_tier2_experiment_design"),
        ("PACK_BEHAVIOR_TIER2_HYPOTHESIS_TEST_PLAN", OUTPUT_HYPOTHESIS_PLAN, "behavior_tier2_hypothesis_test_plan"),
        ("PACK_BEHAVIOR_TIER2_SESSION_STRATEGY", OUTPUT_SESSION_STRATEGY, "behavior_tier2_session_strategy"),
        ("PACK_BEHAVIOR_TIER2_CALL_BUDGET", OUTPUT_CALL_BUDGET, "behavior_tier2_call_budget"),
        ("PACK_BEHAVIOR_TIER2_STOP_RULES", OUTPUT_STOP_RULES, "behavior_tier2_stop_rules"),
        ("PACK_BEHAVIOR_TIER2_SUCCESS_CRITERIA", OUTPUT_SUCCESS_CRITERIA, "behavior_tier2_success_criteria"),
        ("PACK_BEHAVIOR_TIER2_READINESS_AUDIT", OUTPUT_READINESS_AUDIT, "behavior_tier2_readiness_audit"),
        ("PACK_BEHAVIOR_TIER2_DESIGN_SUMMARY", OUTPUT_SUMMARY, "behavior_tier2_design_summary"),
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
            "notes": "Phase 9A-4Z Tier 2 behavior-pattern expansion design; no execution.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        row_number = by_id.get(key)
        if not row_number:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4Z Tier 2 behavior experiment design.")
    return parser.parse_args(argv)


def build_pack_behavior_tier2_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    design_id = _design_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing: List[str] = []

    hypotheses = _safe_rows(service, titles, INPUT_HYPOTHESES, missing)
    generalization_summary_rows = _safe_rows(service, titles, INPUT_GENERALIZATION_SUMMARY, missing)
    generalization_summary = generalization_summary_rows[-1] if generalization_summary_rows else {}
    for sheet in [
        INPUT_GENERALIZATION_AUDIT,
        INPUT_PROVIDER_CONSISTENCY,
        INPUT_TRANSITION_REPRO,
        INPUT_FIELD_STABILITY,
        INPUT_NOSIGNAL_STABILITY,
        INPUT_INVALID_GENERALIZATION,
        *PLANNING_INPUTS,
    ]:
        _safe_rows(service, titles, sheet, missing)

    if not hypotheses:
        raise RuntimeError("Missing Pack_Behavior_Generalization_Hypotheses; cannot build Tier 2 design.")
    if _upper(generalization_summary.get("ready_for_tier2_design")) != "TRUE":
        raise RuntimeError("Generalization audit does not mark ready_for_tier2_design TRUE.")

    experiment_rows = _experiment_rows(generated_ts, design_id, hypotheses)
    hypothesis_plan_rows = _hypothesis_plan_rows(generated_ts, design_id, hypotheses)
    session_rows = _session_strategy_rows(generated_ts, design_id, hypotheses)
    budget_rows = _call_budget_rows(generated_ts, design_id)
    stop_rows = _stop_rule_rows(generated_ts, design_id)
    success_rows = _success_rows(generated_ts, design_id, hypotheses)
    readiness_rows = _readiness_rows(generated_ts, design_id, hypotheses, generalization_summary, missing)

    high_count = sum(1 for row in hypotheses if _priority(row) == "HIGH")
    medium_count = sum(1 for row in hypotheses if _priority(row) == "MEDIUM")
    hold_count = sum(1 for row in hypotheses if _priority(row) == "HOLD")
    blocked = any(_upper(row.get("check_status")) == "BLOCKED" for row in readiness_rows)
    build_status = "FAIL" if blocked else ("PASS_WITH_WARNINGS" if hold_count or missing else "PASS")
    final_interpretation = (
        "BEHAVIOR_TIER2_EXPERIMENT_DESIGN_BLOCKED"
        if blocked
        else ("BEHAVIOR_TIER2_EXPERIMENT_DESIGN_READY_WITH_WARNINGS" if hold_count or missing else "BEHAVIOR_TIER2_EXPERIMENT_DESIGN_READY")
    )
    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "tier2_design_version": TIER2_DESIGN_VERSION,
        "tier2_design_id": design_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "hypotheses_planned": len(hypotheses),
        "high_priority_hypotheses_planned": high_count,
        "medium_priority_hypotheses_planned": medium_count,
        "hold_hypotheses_planned": hold_count,
        "sessions_min_planned": 5,
        "sessions_max_planned": 10,
        "provider_calls_min_planned": 75,
        "provider_calls_max_planned": 150,
        "providers_included": PROVIDERS,
        "pack_levels_included": PACK_LEVELS,
        "stop_rules_defined": len(stop_rows),
        "success_criteria_defined": len(success_rows),
        "readiness_checks_defined": len(readiness_rows),
        "tier2_design_complete": "TRUE" if not blocked else "FALSE",
        "tier2_execution_started": "FALSE",
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_tier2_execution_planning": "TRUE" if not blocked else "FALSE",
        "ready_for_tier2_execution": "FALSE",
        "ready_for_accuracy_evaluation": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A4ZX_TIER2_EXECUTION_PLAN" if not blocked else "RUN_PHASE9A4Z_DESIGN_REPAIR",
        "notes": _truncate_text(json.dumps({"missing_inputs": sorted(set(missing)), "hold_hypotheses": hold_count}, ensure_ascii=True), 500),
    }

    for sheet, headers, rows in [
        (OUTPUT_EXPERIMENT_DESIGN, EXPERIMENT_HEADERS, experiment_rows),
        (OUTPUT_HYPOTHESIS_PLAN, HYPOTHESIS_PLAN_HEADERS, hypothesis_plan_rows),
        (OUTPUT_SESSION_STRATEGY, SESSION_STRATEGY_HEADERS, session_rows),
        (OUTPUT_CALL_BUDGET, CALL_BUDGET_HEADERS, budget_rows),
        (OUTPUT_STOP_RULES, STOP_RULE_HEADERS, stop_rows),
        (OUTPUT_SUCCESS_CRITERIA, SUCCESS_CRITERIA_HEADERS, success_rows),
        (OUTPUT_READINESS_AUDIT, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "tier2_design_id": design_id,
        "hypotheses_planned": len(hypotheses),
        "sessions_planned": "5-10",
        "planned_provider_calls": "75-150",
        "stop_rules_defined": len(stop_rows),
        "success_criteria_defined": len(success_rows),
        "readiness_audit_result": "PASS" if not blocked else "BLOCKED",
        "recommended_next_step": summary["recommended_next_step"],
        "sheets_written": {
            OUTPUT_EXPERIMENT_DESIGN: len(experiment_rows),
            OUTPUT_HYPOTHESIS_PLAN: len(hypothesis_plan_rows),
            OUTPUT_SESSION_STRATEGY: len(session_rows),
            OUTPUT_CALL_BUDGET: len(budget_rows),
            OUTPUT_STOP_RULES: len(stop_rows),
            OUTPUT_SUCCESS_CRITERIA: len(success_rows),
            OUTPUT_READINESS_AUDIT: len(readiness_rows),
            OUTPUT_SUMMARY: 1,
        },
        "safety": {
            "provider_call_count": 0,
            "forecast_generation_count": 0,
            "accuracy_evaluation_count": 0,
            "production_behavior_change_count": 0,
        },
        "registry": registry,
    }


def main() -> None:
    result = build_pack_behavior_tier2_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
