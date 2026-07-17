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


SCHEMA_VERSION = "presignal_v2_accuracy_evaluation_plan_0.1"
PLAN_VERSION = "accuracy_evaluation_plan_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5B"
REGISTRY_CATEGORY = "PRESIGNAL_V2_ACCURACY_EVALUATION_PLAN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_5A_SHEETS = [
    "Behavior_To_Accuracy_Hypothesis_Design",
    "Behavior_To_Accuracy_Testable_Hypotheses",
    "Behavior_To_Accuracy_Eligible_Hypotheses",
    "Behavior_To_Accuracy_Excluded_Hypotheses",
    "Behavior_To_Accuracy_Evaluation_Design",
    "Behavior_To_Accuracy_Metric_Plan",
    "Behavior_To_Accuracy_Confounder_Audit",
    "Behavior_To_Accuracy_Governance_Check",
    "Behavior_To_Accuracy_Design_Summary",
]

REFERENCE_SHEETS = [
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Outcome_Ledger",
    "Session_Forecasts_With_Market_State_Evaluation",
    "Session_Market_State_Impact_Audit",
    "Provider_Pack_Sensitivity_Audit",
]

OUTPUT_PLAN = "Accuracy_Evaluation_Plan"
OUTPUT_EXPERIMENT = "Accuracy_Evaluation_Experiment_Definition"
OUTPUT_SESSION = "Accuracy_Evaluation_Session_Strategy"
OUTPUT_CONTROL = "Accuracy_Evaluation_Control_Groups"
OUTPUT_METRIC_EXECUTION = "Accuracy_Evaluation_Metric_Execution_Plan"
OUTPUT_INVALID = "Accuracy_Evaluation_Invalid_Output_Policy"
OUTPUT_STOP = "Accuracy_Evaluation_Stop_Rules"
OUTPUT_GOVERNANCE = "Accuracy_Evaluation_Governance_Check"
OUTPUT_READINESS = "Accuracy_Evaluation_Readiness_Audit"
OUTPUT_SUMMARY = "Accuracy_Evaluation_Plan_Summary"

APPROVED_ACCURACY_HYPOTHESES = [
    "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
    "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
    "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
]

APPROVED_METRICS = [
    "direction_match_rate",
    "false_signal_rate",
    "no_signal_correctness",
    "behavior_conditioned_accuracy_delta",
    "pack_vs_baseline_delta",
    "confidence_calibration_proxy",
    "scenario_alignment",
]

PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "plan_area",
    "plan_status",
    "source_phase",
    "approved_hypotheses_count",
    "experiments_defined",
    "control_groups_defined",
    "metrics_planned",
    "invalid_policies_defined",
    "accuracy_evaluation_performed",
    "provider_calls_performed",
    "forecast_generation_performed",
    "production_change_performed",
    "plan_conclusion",
    "recommended_next_action",
    "notes",
]

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "experiment_id",
    "hypothesis_id",
    "source_behavior_hypothesis_id",
    "comparison_groups",
    "provider_scope",
    "pack_scope",
    "session_scope",
    "inclusion_rules",
    "exclusion_rules",
    "outcome_source",
    "required_sample_size",
    "minimum_valid_rows",
    "invalid_output_handling",
    "control_conditions",
    "confounders",
    "primary_metric",
    "secondary_metrics",
    "interpretation_rules",
    "promotion_criteria",
    "rejection_criteria",
    "stop_rules",
    "ready_for_phase9a5c_design",
    "notes",
]

SESSION_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "strategy_id",
    "strategy_name",
    "hypotheses_supported",
    "session_source",
    "inclusion_rules",
    "exclusion_rules",
    "minimum_session_count",
    "minimum_valid_matched_cells",
    "cross_session_aggregation_rule",
    "stratification_dimensions",
    "sample_size_note",
    "notes",
]

CONTROL_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "control_group_id",
    "hypothesis_id",
    "baseline_group",
    "comparison_group",
    "provider_scope",
    "pack_scope",
    "session_matching_rule",
    "validity_requirement",
    "invalid_cell_policy",
    "aggregation_rule",
    "forbidden_interpretation",
    "notes",
]

METRIC_EXECUTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "metric_id",
    "metric_name",
    "applies_to_hypotheses",
    "metric_definition_reference",
    "required_input_columns",
    "calculation_allowed_in_this_phase",
    "future_execution_rule",
    "primary_or_secondary",
    "interpretation_limits",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "invalid_case_type",
    "case_description",
    "handling_policy",
    "rerun_policy",
    "archive_policy",
    "comparison_policy",
    "counts_as_valid_row",
    "counts_as_invalid_row",
    "requires_governance_review",
    "notes",
]

STOP_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "stop_rule_id",
    "rule_type",
    "trigger_condition",
    "threshold",
    "required_action",
    "blocking",
    "applies_to_future_phase",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "readiness_check_id",
    "readiness_area",
    "check_description",
    "check_status",
    "evidence_source",
    "evidence_value",
    "blocking",
    "recommended_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "plan_version",
    "plan_run_id",
    "build_status",
    "final_interpretation",
    "experiments_defined",
    "approved_hypotheses_planned",
    "metrics_planned",
    "control_groups_defined",
    "invalid_output_policies_defined",
    "stop_rules_defined",
    "governance_checks_defined",
    "readiness_checks_defined",
    "readiness_result",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "overall_ok_calculated",
    "direction_correctness_calculated",
    "production_behavior_change_count",
    "ready_for_phase9a5c_design",
    "ready_for_accuracy_evaluation_execution",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _truth(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "Y", "1"}


def _run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"accuracy_evaluation_plan_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str], required: bool = False) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        if required:
            missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _base(generated_ts: str, plan_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "plan_version": PLAN_VERSION,
        "plan_run_id": plan_run_id,
    }


def _hypothesis_index(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("accuracy_hypothesis_id")): row for row in rows if _norm(row.get("accuracy_hypothesis_id"))}


def _experiment_specs() -> List[Dict[str, str]]:
    return [
        {
            "experiment_id": "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "hypothesis_id": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "comparison_groups": "Pack A baseline vs Pack B|Pack A baseline vs Pack D|Pack A baseline vs Pack E",
            "provider_scope": "OpenAI|Gemini|Anthropic with invalid cells isolated",
            "pack_scope": "Pack A|Pack B|Pack D|Pack E",
            "session_scope": "matched controlled sessions with complete raw archive and outcome windows",
            "inclusion_rules": "valid raw archive|valid parsed output|complete Pack A baseline|complete treatment pack cell|outcome source available",
            "exclusion_rules": "invalid output cell|missing outcome window|missing Pack A baseline|provider rerun without new run_id",
            "outcome_source": "future evaluation rows/outcome ledger schema references: mr_real_dir|realized_pips|evaluation_window_metadata",
            "required_sample_size": ">=30 matched valid comparison cells recommended before interpretation",
            "minimum_valid_rows": ">=10 valid matched cells per comparison group; higher preferred",
            "invalid_output_handling": "preserve invalid cells; exclude only affected comparison; never infer",
            "control_conditions": "same session_id|same provider|Pack A baseline|same outcome window|invalid cells isolated",
            "confounders": "small_sample_size|provider_invalid_outputs|outcome_label_noise|session_selection_bias|market_regime_dependence",
            "primary_metric": "direction_match_rate",
            "secondary_metrics": "false_signal_rate|pack_vs_baseline_delta|behavior_conditioned_accuracy_delta",
            "interpretation_rules": "May compare matched future metric values only after Phase 9A-5C execution; no provider or pack ranking.",
            "promotion_criteria": "Proceed to execution only if outcome source and matched baseline/treatment coverage are available.",
            "rejection_criteria": "Hold if matched coverage is insufficient or outcome proxy is not stable.",
            "stop_rules": "raw_archive_missing|invalid_rate_exceeds_threshold|outcome_source_missing|governance_violation",
        },
        {
            "experiment_id": "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "hypothesis_id": "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "comparison_groups": "Pack A baseline vs Pack B",
            "provider_scope": "OpenAI|Gemini|Anthropic with provider-specific invalid risk controls",
            "pack_scope": "Pack A|Pack B",
            "session_scope": "matched Pack A and Pack B cells by session/provider",
            "inclusion_rules": "valid Pack A cell|valid Pack B cell|complete raw archive|no-signal proxy available",
            "exclusion_rules": "invalid A or B cell|missing no-signal proxy|missing outcome source|imputed response",
            "outcome_source": "future no_signal_outcome_proxy|mr_real_dir|realized_pips|evaluation_window_metadata",
            "required_sample_size": ">=30 matched A/B cells recommended before interpretation",
            "minimum_valid_rows": ">=15 matched A/B valid cells",
            "invalid_output_handling": "exclude only affected A/B comparison; preserve invalid row",
            "control_conditions": "same session_id|same provider|same forecast timestamp|same output schema",
            "confounders": "small_sample_size|event_cluster_complexity|confidence_not_accuracy|behavior_change_not_accuracy",
            "primary_metric": "false_signal_rate",
            "secondary_metrics": "no_signal_correctness|direction_match_rate|pack_vs_baseline_delta",
            "interpretation_rules": "Evaluate signal discipline only; do not claim Pack B is best.",
            "promotion_criteria": "Proceed if no-signal proxy is defined and matched A/B coverage is adequate.",
            "rejection_criteria": "Hold if no-signal proxy cannot be defined without outcome-label noise.",
            "stop_rules": "no_signal_proxy_missing|matched_baseline_missing|invalid_rate_exceeds_threshold|governance_violation",
        },
        {
            "experiment_id": "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "hypothesis_id": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "comparison_groups": "OpenAI Pack A vs OpenAI Pack B|OpenAI Pack A vs OpenAI Pack D",
            "provider_scope": "OpenAI only",
            "pack_scope": "Pack A|Pack B|Pack D",
            "session_scope": "OpenAI matched cells across controlled sessions",
            "inclusion_rules": "OpenAI valid output|complete raw archive|matched Pack A/treatment cells|outcome source available",
            "exclusion_rules": "invalid output|missing Pack A baseline|missing outcome source|provider comparison/ranking intent",
            "outcome_source": "future evaluation rows/outcome ledger schema references",
            "required_sample_size": ">=20 OpenAI matched valid cells recommended before interpretation",
            "minimum_valid_rows": ">=10 OpenAI matched valid treatment cells",
            "invalid_output_handling": "preserve invalid cells; do not replace or rerun",
            "control_conditions": "OpenAI-only|same session_id|same outcome window|Pack A baseline",
            "confounders": "provider_specific_prompt_behavior|session_selection_bias|confidence_not_accuracy|outcome_label_noise",
            "primary_metric": "behavior_conditioned_accuracy_delta",
            "secondary_metrics": "direction_match_rate|confidence_calibration_proxy|provider_stability_control",
            "interpretation_rules": "OpenAI can be used as a clean test bed; do not infer provider superiority.",
            "promotion_criteria": "Proceed if evaluation plan preserves provider-testbed framing and forbids ranking.",
            "rejection_criteria": "Hold if plan language implies OpenAI is more accurate or production-preferred.",
            "stop_rules": "provider_ranking_detected|matched_baseline_missing|outcome_source_missing|governance_violation",
        },
    ]


def _invalid_cases() -> List[Dict[str, str]]:
    cases = [
        ("malformed_json", "Provider response cannot be parsed as valid JSON."),
        ("provider_timeout", "Provider response did not return within execution limits."),
        ("provider_503", "Provider returned transient 503 or availability error."),
        ("missing_response", "No provider response body was archived."),
        ("schema_failure", "Response parsed but failed required output schema."),
    ]
    rows: List[Dict[str, str]] = []
    for case_type, description in cases:
        rows.append(
            {
                "invalid_case_type": case_type,
                "case_description": description,
                "handling_policy": "TREAT_AS_INVALID_CELL",
                "rerun_policy": "NEVER_RERUN_AUTOMATICALLY",
                "archive_policy": "PRESERVE_RAW_ARCHIVE",
                "comparison_policy": "EXCLUDE_ONLY_AFFECTED_COMPARISON",
                "counts_as_valid_row": "FALSE",
                "counts_as_invalid_row": "TRUE",
                "requires_governance_review": "TRUE" if case_type in {"missing_response"} else "FALSE",
                "notes": "Invalid outputs remain evidence of execution quality; no inference or imputation.",
            }
        )
    return rows


def _stop_rules() -> List[Dict[str, str]]:
    return [
        ("STOP_RAW_ARCHIVE_MISSING", "STOP", "any raw archive row missing", "any", "STOP_AND_HOLD_GOVERNANCE_REVIEW", "TRUE"),
        ("STOP_PROVIDER_CALL_DETECTED", "STOP", "provider call occurs during planning/evaluation analysis phase", "any", "STOP_AND_HOLD_GOVERNANCE_REVIEW", "TRUE"),
        ("STOP_ACCURACY_PREMATURE", "STOP", "accuracy metric calculated before approved execution phase", "any", "STOP_AND_HOLD_GOVERNANCE_REVIEW", "TRUE"),
        ("STOP_PRODUCTION_WRITE", "STOP", "production sheet write detected", "any", "STOP_AND_HOLD_GOVERNANCE_REVIEW", "TRUE"),
        ("HOLD_INVALID_RATE", "HOLD", "invalid output rate exceeds threshold", ">20%", "HOLD_FOR_REVIEW", "FALSE"),
        ("HOLD_OUTCOME_SOURCE", "HOLD", "required outcome source unavailable or ambiguous", "any", "HOLD_FOR_REPAIR", "FALSE"),
        ("HOLD_BASELINE_MISSING", "HOLD", "Pack A baseline missing for matched comparison", "any affected group", "HOLD_AFFECTED_COMPARISON", "FALSE"),
        ("HOLD_SAMPLE_SIZE", "HOLD", "minimum valid matched rows not met", "below planned threshold", "DESCRIBE_ONLY_NO_INTERPRETATION", "FALSE"),
    ]


def _governance_specs() -> List[Dict[str, str]]:
    return [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_ACCURACY_EVAL", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OVERALL_OK", "overall_ok_calculated", "0", "0"),
        ("GOV_DIRECTION_CORRECTNESS", "direction_correctness_calculated", "0", "0"),
        ("GOV_PRODUCTION_CHANGE", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_SCORING", "scoring_changes", "FALSE", "FALSE"),
    ]


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("ACCURACY_EVALUATION_PLAN", OUTPUT_PLAN, "accuracy_evaluation_plan"),
        ("ACCURACY_EVALUATION_EXPERIMENT_DEFINITION", OUTPUT_EXPERIMENT, "accuracy_evaluation_experiment_definition"),
        ("ACCURACY_EVALUATION_SESSION_STRATEGY", OUTPUT_SESSION, "accuracy_evaluation_session_strategy"),
        ("ACCURACY_EVALUATION_CONTROL_GROUPS", OUTPUT_CONTROL, "accuracy_evaluation_control_groups"),
        ("ACCURACY_EVALUATION_METRIC_EXECUTION_PLAN", OUTPUT_METRIC_EXECUTION, "accuracy_evaluation_metric_execution_plan"),
        ("ACCURACY_EVALUATION_INVALID_OUTPUT_POLICY", OUTPUT_INVALID, "accuracy_evaluation_invalid_output_policy"),
        ("ACCURACY_EVALUATION_STOP_RULES", OUTPUT_STOP, "accuracy_evaluation_stop_rules"),
        ("ACCURACY_EVALUATION_GOVERNANCE_CHECK", OUTPUT_GOVERNANCE, "accuracy_evaluation_governance_check"),
        ("ACCURACY_EVALUATION_READINESS_AUDIT", OUTPUT_READINESS, "accuracy_evaluation_readiness_audit"),
        ("ACCURACY_EVALUATION_PLAN_SUMMARY", OUTPUT_SUMMARY, "accuracy_evaluation_plan_summary"),
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
            "notes": "Phase 9A-5B accuracy evaluation plan; planning-only, no accuracy evaluation.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5B accuracy evaluation plan.")
    return parser.parse_args(argv)


def build_accuracy_evaluation_plan_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    plan_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_reference: List[str] = []
    input_rows = {
        sheet: _safe_rows(service, titles, sheet, missing_required, required=True)
        for sheet in INPUT_5A_SHEETS
    }
    for sheet in REFERENCE_SHEETS:
        _safe_rows(service, titles, sheet, missing_reference)
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5A inputs: {missing_required}")

    testable = input_rows["Behavior_To_Accuracy_Testable_Hypotheses"]
    testable_by_id = _hypothesis_index(testable)
    missing_hypotheses = [hyp for hyp in APPROVED_ACCURACY_HYPOTHESES if hyp not in testable_by_id]
    if missing_hypotheses:
        raise RuntimeError(f"Missing approved accuracy hypotheses from Phase 9A-5A: {missing_hypotheses}")

    experiments: List[Dict[str, Any]] = []
    for spec in _experiment_specs():
        source = testable_by_id[spec["hypothesis_id"]]
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "experiment_id": spec["experiment_id"],
                "hypothesis_id": spec["hypothesis_id"],
                "source_behavior_hypothesis_id": _norm(source.get("source_behavior_hypothesis_id")),
                "comparison_groups": spec["comparison_groups"],
                "provider_scope": spec["provider_scope"],
                "pack_scope": spec["pack_scope"],
                "session_scope": spec["session_scope"],
                "inclusion_rules": spec["inclusion_rules"],
                "exclusion_rules": spec["exclusion_rules"],
                "outcome_source": spec["outcome_source"],
                "required_sample_size": spec["required_sample_size"],
                "minimum_valid_rows": spec["minimum_valid_rows"],
                "invalid_output_handling": spec["invalid_output_handling"],
                "control_conditions": spec["control_conditions"],
                "confounders": spec["confounders"],
                "primary_metric": spec["primary_metric"],
                "secondary_metrics": spec["secondary_metrics"],
                "interpretation_rules": spec["interpretation_rules"],
                "promotion_criteria": spec["promotion_criteria"],
                "rejection_criteria": spec["rejection_criteria"],
                "stop_rules": spec["stop_rules"],
                "ready_for_phase9a5c_design": "TRUE",
                "notes": "Planning-only experiment definition; no metric values calculated.",
            }
        )
        experiments.append(row)

    session_rows = []
    for strategy_id, name, hypotheses, note in [
        ("SESSION_STRATEGY_MATCHED_ALL", "Matched controlled sessions", "|".join(APPROVED_ACCURACY_HYPOTHESES), "Primary strategy for all approved hypotheses."),
        ("SESSION_STRATEGY_OPENAI_TESTBED", "OpenAI clean test-bed slice", "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED", "Provider-specific scope for test-bed cleanliness only."),
        ("SESSION_STRATEGY_NO_SIGNAL_DISCIPLINE", "No-signal discipline slice", "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE", "Requires future no-signal outcome proxy."),
    ]:
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "strategy_id": strategy_id,
                "strategy_name": name,
                "hypotheses_supported": hypotheses,
                "session_source": "future matched Phase 9A behavior/evaluation evidence",
                "inclusion_rules": "complete raw archive|valid baseline/treatment cells|outcome source available|same session/provider matching",
                "exclusion_rules": "invalid output cell|missing outcome|missing baseline|rerun without new run_id",
                "minimum_session_count": ">=8 existing behavior sessions plus future execution-plan threshold",
                "minimum_valid_matched_cells": ">=10 per comparison; >=30 preferred for primary hypotheses",
                "cross_session_aggregation_rule": "aggregate only matched valid cells; report invalid coverage separately",
                "stratification_dimensions": "provider|pack_level|transition|event_cluster|market_regime_if_available",
                "sample_size_note": "Thresholds are recommended only and are not calculated in this phase.",
                "notes": note,
            }
        )
        session_rows.append(row)

    control_rows = []
    for exp in experiments:
        comparisons = [part.strip() for part in _norm(exp.get("comparison_groups")).split("|") if part.strip()]
        for idx, comparison in enumerate(comparisons, start=1):
            baseline = comparison.split(" vs ")[0] if " vs " in comparison else "Pack A baseline"
            treatment = comparison.split(" vs ")[1] if " vs " in comparison else comparison
            row = _base(generated_ts, plan_run_id)
            row.update(
                {
                    "control_group_id": f"CTRL_{exp['experiment_id']}_{idx}",
                    "hypothesis_id": exp["hypothesis_id"],
                    "baseline_group": baseline,
                    "comparison_group": treatment,
                    "provider_scope": exp["provider_scope"],
                    "pack_scope": exp["pack_scope"],
                    "session_matching_rule": "same session_id and provider unless provider-specific experiment narrows scope",
                    "validity_requirement": "both baseline and treatment cells valid; raw archive complete",
                    "invalid_cell_policy": "exclude only affected comparison and preserve invalid row",
                    "aggregation_rule": "cross-session matched-cell aggregation; no provider/pack ranking",
                    "forbidden_interpretation": "production routing|provider ranking|pack ranking|accuracy claim before execution",
                    "notes": "Control group definition only.",
                }
            )
            control_rows.append(row)

    metric_rows = []
    for metric in APPROVED_METRICS:
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "metric_id": f"METRIC_EXEC_{metric.upper()}",
                "metric_name": metric,
                "applies_to_hypotheses": "|".join(APPROVED_ACCURACY_HYPOTHESES),
                "metric_definition_reference": "Behavior_To_Accuracy_Metric_Plan",
                "required_input_columns": "session_id|provider|pack_level|forecast_direction|no_signal_flag|forecast_confidence|outcome_proxy|valid_output_flag",
                "calculation_allowed_in_this_phase": "FALSE",
                "future_execution_rule": "Only Phase 9A-5C may calculate after governance approval.",
                "primary_or_secondary": "PRIMARY" if metric in {"direction_match_rate", "false_signal_rate", "behavior_conditioned_accuracy_delta"} else "SECONDARY",
                "interpretation_limits": "Metric values must not imply provider ranking, pack ranking, or production readiness.",
                "notes": "Metric planned only; no values calculated.",
            }
        )
        metric_rows.append(row)

    invalid_rows = []
    for spec in _invalid_cases():
        row = _base(generated_ts, plan_run_id)
        row.update(spec)
        invalid_rows.append(row)

    stop_rows = []
    for rule_id, rule_type, trigger, threshold, action, blocking in _stop_rules():
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "stop_rule_id": rule_id,
                "rule_type": rule_type,
                "trigger_condition": trigger,
                "threshold": threshold,
                "required_action": action,
                "blocking": blocking,
                "applies_to_future_phase": "Phase 9A-5C",
                "notes": "Defined only; no evaluation executed.",
            }
        )
        stop_rows.append(row)

    governance_rows = []
    for check_id, check_name, expected, actual in _governance_specs():
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": check_name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Planning phase governance check.",
            }
        )
        governance_rows.append(row)

    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    readiness_rows = []
    readiness_specs = [
        ("READ_INPUTS", "phase9a5a_inputs_available", "Phase 9A-5A design sheets are available.", "PASS", "Behavior_To_Accuracy_Design_Summary", "available", False, "Proceed"),
        ("READ_EXPERIMENTS", "experiments_defined", "Approved hypotheses have experiment definitions.", "PASS" if len(experiments) == 3 else "BLOCKED", OUTPUT_EXPERIMENT, len(experiments), len(experiments) != 3, "Repair experiment definitions if count mismatches."),
        ("READ_CONTROLS", "control_groups_defined", "Control groups include Pack A baselines and required pack/provider scopes.", "PASS", OUTPUT_CONTROL, len(control_rows), False, "Proceed"),
        ("READ_METRICS", "metrics_defined_not_calculated", "Approved metrics are planned but not calculated.", "PASS", OUTPUT_METRIC_EXECUTION, len(metric_rows), False, "Proceed"),
        ("READ_INVALID_POLICY", "invalid_output_policy_defined", "Invalid-output handling is explicit.", "PASS", OUTPUT_INVALID, len(invalid_rows), False, "Proceed"),
        ("READ_GOVERNANCE", "governance_clean", "No provider calls, forecasts, scoring, or production changes occurred.", "PASS" if not governance_failed else "BLOCKED", OUTPUT_GOVERNANCE, "PASS" if not governance_failed else "FAIL", governance_failed, "Hold if any governance check fails."),
        ("READ_PHASE9A5C", "ready_for_phase9a5c_design", "Plan is ready for Phase 9A-5C design, not execution.", "PASS", OUTPUT_SUMMARY, "READY_FOR_PHASE9A5C_DESIGN", False, "Proceed to Phase 9A-5C design."),
    ]
    for check_id, area, desc, status, source, value, blocking, action in readiness_specs:
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "readiness_check_id": check_id,
                "readiness_area": area,
                "check_description": desc,
                "check_status": status,
                "evidence_source": source,
                "evidence_value": value,
                "blocking": "TRUE" if blocking else "FALSE",
                "recommended_action": action,
                "notes": "Ready for design does not mean accuracy evaluation may execute.",
            }
        )
        readiness_rows.append(row)

    plan_rows = []
    for area, conclusion, action in [
        ("scope", "Accuracy evaluation protocol is defined for three approved hypotheses only.", "PROCEED"),
        ("experiments", "Three future experiments are defined and mapped to hypotheses.", "PROCEED"),
        ("controls", "Pack A baseline and required treatment groups are explicit.", "PROCEED"),
        ("invalid_policy", "Invalid outputs remain archived, isolated, and never inferred.", "PROCEED"),
        ("metrics", "Metrics are planned but not calculated.", "PROCEED"),
        ("governance", "Planning phase remained non-executing.", "PROCEED"),
    ]:
        row = _base(generated_ts, plan_run_id)
        row.update(
            {
                "plan_area": area,
                "plan_status": "PASS",
                "source_phase": "Phase 9A-5A",
                "approved_hypotheses_count": len(APPROVED_ACCURACY_HYPOTHESES),
                "experiments_defined": len(experiments),
                "control_groups_defined": len(control_rows),
                "metrics_planned": len(metric_rows),
                "invalid_policies_defined": len(invalid_rows),
                "accuracy_evaluation_performed": "FALSE",
                "provider_calls_performed": "FALSE",
                "forecast_generation_performed": "FALSE",
                "production_change_performed": "FALSE",
                "plan_conclusion": conclusion,
                "recommended_next_action": action,
                "notes": "Planning-only; no evaluation execution.",
            }
        )
        plan_rows.append(row)

    build_status = "FAIL" if governance_failed else "PASS_WITH_WARNINGS"
    final_interpretation = "ACCURACY_EVALUATION_PLAN_BLOCKED" if governance_failed else "ACCURACY_EVALUATION_PLAN_READY_WITH_WARNINGS"
    readiness_result = "BLOCKED" if governance_failed else "READY_FOR_PHASE9A5C_DESIGN"
    recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW" if governance_failed else "PROCEED_TO_PHASE9A5C_DESIGN"

    summary_row = _base(generated_ts, plan_run_id)
    summary_row.update(
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "experiments_defined": len(experiments),
            "approved_hypotheses_planned": len(APPROVED_ACCURACY_HYPOTHESES),
            "metrics_planned": len(metric_rows),
            "control_groups_defined": len(control_rows),
            "invalid_output_policies_defined": len(invalid_rows),
            "stop_rules_defined": len(stop_rows),
            "governance_checks_defined": len(governance_rows),
            "readiness_checks_defined": len(readiness_rows),
            "readiness_result": readiness_result,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "accuracy_evaluation_performed": 0,
            "overall_ok_calculated": 0,
            "direction_correctness_calculated": 0,
            "production_behavior_change_count": 0,
            "ready_for_phase9a5c_design": "TRUE" if not governance_failed else "FALSE",
            "ready_for_accuracy_evaluation_execution": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": _truncate_text(
                json.dumps(
                    {
                        "reference_sheets_missing_or_optional": [sheet for sheet in REFERENCE_SHEETS if sheet not in titles],
                        "input_5a_sheets_read": len(INPUT_5A_SHEETS),
                        "strict_note": "No accuracy metrics calculated.",
                    },
                    ensure_ascii=True,
                ),
                500,
            ),
        }
    )

    outputs = [
        (OUTPUT_PLAN, PLAN_HEADERS, plan_rows),
        (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, experiments),
        (OUTPUT_SESSION, SESSION_HEADERS, session_rows),
        (OUTPUT_CONTROL, CONTROL_HEADERS, control_rows),
        (OUTPUT_METRIC_EXECUTION, METRIC_EXECUTION_HEADERS, metric_rows),
        (OUTPUT_INVALID, INVALID_HEADERS, invalid_rows),
        (OUTPUT_STOP, STOP_HEADERS, stop_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]
    for sheet_name, headers, rows in outputs:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, sheet_headers, rows)
    registry = _upsert_registry_rows(service)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_accuracy_evaluation_plan_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_defined": len(experiments),
        "approved_hypotheses_planned": len(APPROVED_ACCURACY_HYPOTHESES),
        "metrics_planned": len(metric_rows),
        "control_groups_defined": len(control_rows),
        "invalid_output_policies_defined": len(invalid_rows),
        "governance_checks": len(governance_rows),
        "readiness_result": readiness_result,
        "recommended_next_step": recommended_next_step,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "overall_ok_calculated": 0,
        "direction_correctness_calculated": 0,
        "production_behavior_change_count": 0,
        "registry": registry,
    }


def main() -> None:
    result = build_accuracy_evaluation_plan_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
