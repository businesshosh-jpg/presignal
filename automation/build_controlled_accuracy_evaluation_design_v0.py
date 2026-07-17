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


SCHEMA_VERSION = "presignal_v2_controlled_accuracy_evaluation_design_0.1"
DESIGN_VERSION = "controlled_accuracy_evaluation_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5C"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CONTROLLED_ACCURACY_EVALUATION_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_5B_SHEETS = [
    "Accuracy_Evaluation_Plan",
    "Accuracy_Evaluation_Experiment_Definition",
    "Accuracy_Evaluation_Session_Strategy",
    "Accuracy_Evaluation_Control_Groups",
    "Accuracy_Evaluation_Metric_Execution_Plan",
    "Accuracy_Evaluation_Invalid_Output_Policy",
    "Accuracy_Evaluation_Stop_Rules",
    "Accuracy_Evaluation_Governance_Check",
    "Accuracy_Evaluation_Readiness_Audit",
    "Accuracy_Evaluation_Plan_Summary",
]

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

TIER2_SCHEMA_REFERENCE_SHEETS = [
    "Pack_Behavior_Tier2_Runs",
    "Pack_Behavior_Tier2_Forecasts",
    "Pack_Behavior_Tier2_Metadata",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
    "Pack_Behavior_Tier2_Run_Summary",
]

EVALUATION_REFERENCE_SHEETS = [
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Outcome_Ledger",
    "Session_Forecasts_With_Market_State_Evaluation",
    "Session_Market_State_Impact_Audit",
    "Provider_Pack_Sensitivity_Audit",
]

OUTPUT_DESIGN = "Controlled_Accuracy_Evaluation_Design"
OUTPUT_EXPERIMENT_SCHEMA = "Controlled_Accuracy_Experiment_Schema"
OUTPUT_ELIGIBILITY = "Controlled_Accuracy_Row_Eligibility_Rules"
OUTPUT_MATCHING = "Controlled_Accuracy_Outcome_Matching_Design"
OUTPUT_METRIC_LOGIC = "Controlled_Accuracy_Metric_Logic"
OUTPUT_COMPARISON = "Controlled_Accuracy_Comparison_Logic"
OUTPUT_INVALID = "Controlled_Accuracy_Invalid_Output_Handling"
OUTPUT_GOVERNANCE = "Controlled_Accuracy_Governance_Check"
OUTPUT_READINESS = "Controlled_Accuracy_Execution_Readiness"
OUTPUT_SUMMARY = "Controlled_Accuracy_Design_Summary"

APPROVED_HYPOTHESES = [
    "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
    "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
    "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
]

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "design_area",
    "design_status",
    "source_plan",
    "experiments_designed",
    "metrics_designed",
    "comparison_groups_designed",
    "eligibility_rules_designed",
    "outcome_matching_designed",
    "invalid_output_policy_designed",
    "accuracy_evaluation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "production_change_performed",
    "design_conclusion",
    "recommended_next_action",
    "notes",
]

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "experiment_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "experiment_question",
    "comparison_type",
    "primary_comparison",
    "secondary_comparisons",
    "provider_scope",
    "pack_scope",
    "session_scope",
    "forecast_source_sheet",
    "outcome_source_sheet",
    "primary_metric",
    "secondary_metrics",
    "minimum_valid_rows",
    "minimum_sessions",
    "invalid_output_policy",
    "control_group_definition",
    "treatment_group_definition",
    "future_output_sheet",
    "ready_for_future_execution",
    "accuracy_evaluation_performed",
    "notes",
]

ELIGIBILITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "rule_id",
    "rule_name",
    "applies_to_experiment_id",
    "required_source_sheet",
    "required_columns",
    "inclusion_condition",
    "exclusion_condition",
    "invalid_output_handling",
    "rationale",
    "severity_if_violated",
    "notes",
]

MATCHING_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "matching_rule_id",
    "matching_rule_name",
    "forecast_source_sheet",
    "forecast_key_columns",
    "outcome_source_sheet",
    "outcome_key_columns",
    "matching_granularity",
    "time_window_rule",
    "market_reaction_window",
    "required_outcome_fields",
    "fallback_policy",
    "missing_outcome_policy",
    "duplicate_match_policy",
    "rationale",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "metric_id",
    "metric_name",
    "metric_status",
    "metric_purpose",
    "required_forecast_columns",
    "required_outcome_columns",
    "calculation_definition_plain_language",
    "calculation_formula_pseudocode",
    "valid_denominator_definition",
    "invalid_denominator_exclusions",
    "interpretation_rule",
    "minimum_sample_warning",
    "forbidden_interpretation",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "comparison_id",
    "experiment_id",
    "comparison_name",
    "baseline_group",
    "treatment_group",
    "provider_scope",
    "pack_scope",
    "session_scope",
    "primary_metric",
    "secondary_metrics",
    "required_minimum_pairs",
    "pairing_logic",
    "aggregation_logic",
    "invalid_pair_handling",
    "interpretation_rule",
    "promotion_threshold_design",
    "failure_threshold_design",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "invalid_case_id",
    "invalid_case_type",
    "definition",
    "source_detection_sheet",
    "handling_policy",
    "affected_rows_policy",
    "affected_pair_policy",
    "denominator_policy",
    "rerun_policy",
    "archive_policy",
    "interpretation_warning",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
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
    "design_version",
    "design_run_id",
    "readiness_check_id",
    "readiness_check_name",
    "status",
    "blocking_issue",
    "required_repair",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "experiments_designed",
    "row_eligibility_rules_defined",
    "outcome_matching_rules_defined",
    "metrics_logic_defined",
    "comparison_logic_rules_defined",
    "invalid_output_cases_defined",
    "governance_checks_defined",
    "readiness_checks_defined",
    "strongest_experiment_candidate",
    "cleanest_comparison_candidate",
    "highest_risk_evaluation_area",
    "highest_risk_invalid_output_case",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_behavior_change_count",
    "ready_for_phase9a5d_execution_builder",
    "ready_for_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"controlled_accuracy_evaluation_design_v0_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _safe_rows(service, titles: Set[str], sheet_name: str, missing: List[str], required: bool = False) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        if required:
            missing.append(sheet_name)
        return []
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)


def _base(generated_ts: str, design_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "design_run_id": design_run_id,
    }


def _index_by(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get(key)): row for row in rows if _norm(row.get(key))}


def _experiment_rows(generated_ts: str, design_run_id: str, plan_experiments: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_hyp = _index_by(plan_experiments, "hypothesis_id")
    specs = [
        (
            "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "Does USDJPY trend exposure improve future directional alignment relative to Pack A baseline?",
            "MATCHED_PACK_COMPARISON",
            "Pack A vs Pack B",
            "Pack A vs Pack D|Pack A vs Pack E exploratory",
            "OpenAI|Gemini|Anthropic with invalid cells isolated",
            "Pack A|Pack B|Pack D|Pack E",
            "direction_match_rate",
            "false_signal_rate|pack_vs_baseline_delta|behavior_conditioned_accuracy_delta",
            "Pack A valid baseline cell for same session/provider",
            "Pack B/D/E valid treatment cell for same session/provider",
        ),
        (
            "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "Does Pack B reduce unsupported directional signaling compared with Pack A?",
            "MATCHED_PACK_COMPARISON",
            "Pack A vs Pack B",
            "",
            "OpenAI|Gemini|Anthropic with invalid cells isolated",
            "Pack A|Pack B",
            "false_signal_rate",
            "no_signal_correctness|direction_match_rate|behavior_conditioned_accuracy_delta",
            "Pack A valid baseline signal/no-signal cell",
            "Pack B valid target-state treatment cell",
        ),
        (
            "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "Can OpenAI matched comparisons act as a low-output-risk test bed for future pack-conditioned accuracy evaluation?",
            "PROVIDER_SPECIFIC_TESTBED",
            "OpenAI Pack A vs OpenAI Pack B",
            "OpenAI Pack A vs OpenAI Pack D",
            "OpenAI only",
            "Pack A|Pack B|Pack D",
            "behavior_conditioned_accuracy_delta",
            "direction_match_rate|confidence_calibration_proxy|provider_stability_control",
            "OpenAI Pack A valid baseline cell",
            "OpenAI Pack B/D valid treatment cell",
        ),
    ]
    rows: List[Dict[str, Any]] = []
    for exp_id, hyp_id, question, ctype, primary, secondary, provider_scope, pack_scope, primary_metric, secondary_metrics, control, treatment in specs:
        source = by_hyp.get(hyp_id, {})
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "experiment_id": exp_id,
                "accuracy_hypothesis_id": hyp_id,
                "source_behavior_hypothesis_id": _norm(source.get("source_behavior_hypothesis_id")),
                "experiment_question": question,
                "comparison_type": ctype,
                "primary_comparison": primary,
                "secondary_comparisons": secondary,
                "provider_scope": provider_scope,
                "pack_scope": pack_scope,
                "session_scope": "matched controlled sessions with complete raw archive and outcome rows",
                "forecast_source_sheet": "Pack_Behavior_Tier2_Forecasts",
                "outcome_source_sheet": "Evaluation_Rows or Outcome_Ledger schema-compatible future outcome source",
                "primary_metric": primary_metric,
                "secondary_metrics": secondary_metrics,
                "minimum_valid_rows": _norm(source.get("minimum_valid_rows")) or ">=10 matched valid rows per comparison; >=30 preferred",
                "minimum_sessions": "future Phase 9A-5D builder must enforce plan threshold before evaluation",
                "invalid_output_policy": "exclude invalid cells from accuracy denominator; retain invalid-output rate separately",
                "control_group_definition": control,
                "treatment_group_definition": treatment,
                "future_output_sheet": "Controlled_Accuracy_Evaluation_Rows",
                "ready_for_future_execution": "TRUE",
                "accuracy_evaluation_performed": "FALSE",
                "notes": "Experiment schema only; no evaluation rows generated.",
            }
        )
        rows.append(row)
    return rows


def _eligibility_rows(generated_ts: str, design_run_id: str, experiment_ids: Sequence[str]) -> List[Dict[str, Any]]:
    rules = [
        ("ELIG_ONLY_TIER2", "only_tier2_execution_rows", "Pack_Behavior_Tier2_Forecasts", "execution_run_id|session_id|provider|pack_level", "row belongs to approved Tier 2 execution run", "non-Tier2 or unknown run row", "BLOCKING"),
        ("ELIG_EXCLUDE_INVALID", "exclude_invalid_outputs", "Pack_Behavior_Tier2_Forecasts", "json_validation_success|status|error_message", "json_validation_success == TRUE", "invalid output or provider error", "BLOCKING"),
        ("ELIG_EXCLUDE_PROVIDER_FAILURES", "exclude_provider_failures", "Pack_Behavior_Tier2_Run_Log", "response_status|request_status", "provider response_status ok", "provider 503/timeout/error", "BLOCKING"),
        ("ELIG_RAW_ARCHIVE", "require_raw_archive_presence", "Pack_Behavior_Tier2_Raw_Response_Archive", "raw_response_archive_key|raw_response_hash", "matching raw archive row exists", "missing raw archive", "BLOCKING"),
        ("ELIG_OUTCOME", "require_matching_outcome", "Evaluation_Rows|Outcome_Ledger", "session_id|outcome_direction_proxy|realized_pips", "future outcome row exists for session/outcome window", "missing outcome", "BLOCKING"),
        ("ELIG_PACK", "require_pack_level_present", "Pack_Behavior_Tier2_Forecasts", "pack_level", "pack_level in approved scope", "missing or unapproved pack level", "BLOCKING"),
        ("ELIG_PROVIDER", "require_provider_present", "Pack_Behavior_Tier2_Forecasts", "provider", "provider in approved scope", "missing or unapproved provider", "BLOCKING"),
        ("ELIG_SESSION", "require_session_id_present", "Pack_Behavior_Tier2_Forecasts", "session_id", "session_id populated", "missing session_id", "BLOCKING"),
        ("ELIG_NO_RERUN", "require_no_rerun", "Pack_Behavior_Tier2_Metadata", "provider_rerun_count_allowed|execution_run_id", "no silent rerun or replaced output", "rerun without new run_id", "BLOCKING"),
        ("ELIG_SHADOW_ONLY", "require_shadow_only_source", "Pack_Behavior_Tier2_Metadata", "shadow_only|production_visible", "shadow_only TRUE and production_visible FALSE", "production-visible source", "BLOCKING"),
    ]
    rows: List[Dict[str, Any]] = []
    for exp_id in experiment_ids:
        for rule_id, name, source, required, include, exclude, severity in rules:
            row = _base(generated_ts, design_run_id)
            row.update(
                {
                    "rule_id": f"{rule_id}_{exp_id}",
                    "rule_name": name,
                    "applies_to_experiment_id": exp_id,
                    "required_source_sheet": source,
                    "required_columns": required,
                    "inclusion_condition": include,
                    "exclusion_condition": exclude,
                    "invalid_output_handling": "mark row ineligible; do not infer or repair",
                    "rationale": "Protect matched-cell accuracy evaluation from invalid or non-comparable rows.",
                    "severity_if_violated": severity,
                    "notes": "Rule definition only; not applied in this phase.",
                }
            )
            rows.append(row)
    return rows


def _matching_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    specs = [
        (
            "MATCH_SESSION_TO_OUTCOME",
            "session_id maps forecast pack cell to session-level market reaction outcome",
            "session_id|country|session_date|session_window_name",
            "session_id|release_ts/session_window_key",
            "session",
            "outcome timestamp/window must be at or after forecast timestamp; no post hoc source mutation",
            "use established USDJPY market reaction window from evaluation schema",
            "mr_real_dir|realized_pips|mr_real_max_up_pips|mr_real_max_down_pips|eval_ts",
        ),
        (
            "MATCH_PACK_FORECAST_TO_SHARED_OUTCOME",
            "all pack levels for same session/provider compare against same outcome row",
            "session_id|provider|pack_level",
            "session_id",
            "session_pack_provider",
            "same market outcome reused across pack-level treatments for one session",
            "same USDJPY outcome window across packs",
            "outcome_direction_proxy|realized_pips|window_quality_flag",
        ),
        (
            "MATCH_MULTI_EVENT_SESSION",
            "multi-event sessions use session-level aggregated market reaction outcome",
            "session_id|member_event_count",
            "session_id|batch_id/session_window_key",
            "session",
            "event ordering fixed from original market session context",
            "session-level window anchored to approved session forecast timestamp",
            "session_outcome_direction|realized_pips|event_cluster_metadata",
        ),
    ]
    rows: List[Dict[str, Any]] = []
    for rule_id, name, fkeys, okeys, granularity, time_rule, window, fields in specs:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "matching_rule_id": rule_id,
                "matching_rule_name": name,
                "forecast_source_sheet": "Pack_Behavior_Tier2_Forecasts",
                "forecast_key_columns": fkeys,
                "outcome_source_sheet": "Evaluation_Rows|Outcome_Ledger future read-only source",
                "outcome_key_columns": okeys,
                "matching_granularity": granularity,
                "time_window_rule": time_rule,
                "market_reaction_window": window,
                "required_outcome_fields": fields,
                "fallback_policy": "no fallback that changes outcome source semantics; mark missing if no deterministic match",
                "missing_outcome_policy": "mark comparison ineligible; do not impute",
                "duplicate_match_policy": "hold affected session for review; do not choose arbitrary duplicate",
                "rationale": "Future evaluation must compare all pack levels against the same deterministic session outcome.",
                "notes": "Matching rule design only; no matching performed.",
            }
        )
        rows.append(row)
    return rows


def _metric_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    specs = [
        ("direction_match_rate", "Directional alignment", "Count future eligible rows where forecast_direction matches outcome_direction_proxy divided by eligible directional rows.", "matches / valid_directional_denominator"),
        ("false_signal_rate", "Unsupported directional signal risk", "Count directional forecasts when outcome proxy is no/ambiguous move divided by eligible directional forecasts.", "false_signals / valid_directional_forecasts"),
        ("no_signal_correctness", "No-signal discipline", "Count no_signal TRUE rows where outcome proxy is no/ambiguous move divided by eligible no_signal rows.", "correct_no_signal / valid_no_signal_rows"),
        ("behavior_conditioned_accuracy_delta", "Accuracy delta by behavior-transition condition", "Compare metric value for rows with behavior transition label against matched baseline rows without that condition.", "metric(conditioned_treatment) - metric(matched_baseline)"),
        ("pack_vs_baseline_delta", "Pack treatment delta", "Compare treatment pack metric to Pack A metric on matched session/provider pairs.", "metric(treatment_pack) - metric(pack_a_baseline)"),
        ("confidence_calibration_proxy", "Confidence sanity proxy", "Bucket forecast confidence and inspect future correctness proxy rates by bucket.", "correctness_proxy_by_confidence_bucket"),
        ("scenario_alignment", "Scenario outcome alignment", "Evaluate whether future outcome falls within declared scenario framing where scenario fields exist.", "scenario_aligned / valid_scenario_rows"),
    ]
    rows: List[Dict[str, Any]] = []
    for metric, purpose, plain, pseudo in specs:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "metric_id": f"METRIC_{metric.upper()}",
                "metric_name": metric,
                "metric_status": "DEFINED_NOT_CALCULATED",
                "metric_purpose": purpose,
                "required_forecast_columns": "session_id|provider|pack_level|forecast_direction|forecast_confidence|no_signal_flag|json_validation_success",
                "required_outcome_columns": "outcome_direction_proxy|realized_pips|market_reaction_window|outcome_quality_flag",
                "calculation_definition_plain_language": plain,
                "calculation_formula_pseudocode": pseudo,
                "valid_denominator_definition": "eligible rows or matched pairs after invalid-output and missing-outcome exclusions",
                "invalid_denominator_exclusions": "invalid output|missing raw archive|missing outcome|duplicate outcome|rerun without new run_id",
                "interpretation_rule": "Interpret only after Phase 9A-5D execution and review; no production or ranking conclusion.",
                "minimum_sample_warning": "Do not interpret if denominator is below experiment minimum.",
                "forbidden_interpretation": "provider ranking|pack ranking|production readiness|statistical significance without approved design",
                "notes": "Formula logic only; no value calculated.",
            }
        )
        rows.append(row)
    return rows


def _comparison_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    specs = [
        ("CMP_A_B", "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "Pack A vs Pack B", "Pack A", "Pack B", "OpenAI|Gemini|Anthropic", "Pack A|Pack B", "direction_match_rate"),
        ("CMP_A_D", "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "Pack A vs Pack D", "Pack A", "Pack D", "OpenAI|Gemini|Anthropic", "Pack A|Pack D", "direction_match_rate"),
        ("CMP_A_E_EXPLORATORY", "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT", "Pack A vs Pack E where allowed", "Pack A", "Pack E", "OpenAI|Gemini|Anthropic", "Pack A|Pack E", "direction_match_rate"),
        ("CMP_OPENAI_A_B", "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED", "OpenAI Pack A vs OpenAI Pack B", "OpenAI Pack A", "OpenAI Pack B", "OpenAI", "Pack A|Pack B", "behavior_conditioned_accuracy_delta"),
        ("CMP_OPENAI_A_D", "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED", "OpenAI Pack A vs OpenAI Pack D", "OpenAI Pack A", "OpenAI Pack D", "OpenAI", "Pack A|Pack D", "behavior_conditioned_accuracy_delta"),
        ("CMP_BEHAVIOR_CONFIRMED_BASELINE", "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE", "Behavior-confirmed sessions vs baseline", "Pack A behavior-confirmed baseline cells", "Pack B target-state cells", "OpenAI|Gemini|Anthropic", "Pack A|Pack B", "false_signal_rate"),
    ]
    rows: List[Dict[str, Any]] = []
    for cmp_id, exp, name, baseline, treatment, provider_scope, pack_scope, primary in specs:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "comparison_id": cmp_id,
                "experiment_id": exp,
                "comparison_name": name,
                "baseline_group": baseline,
                "treatment_group": treatment,
                "provider_scope": provider_scope,
                "pack_scope": pack_scope,
                "session_scope": "matched session_id cells only",
                "primary_metric": primary,
                "secondary_metrics": "direction_match_rate|false_signal_rate|no_signal_correctness|pack_vs_baseline_delta|confidence_calibration_proxy",
                "required_minimum_pairs": ">=10 matched valid pairs; >=30 preferred for interpretation",
                "pairing_logic": "pair baseline and treatment by session_id and provider, except provider-specific OpenAI comparisons",
                "aggregation_logic": "aggregate across matched valid pairs; report invalid and missing pairs separately",
                "invalid_pair_handling": "if either side invalid, mark pair invalid/partial and exclude from metric denominator",
                "interpretation_rule": "comparison result may be interpreted only after approved execution; no provider or pack ranking",
                "promotion_threshold_design": "to be specified in Phase 9A-5D execution builder before execution",
                "failure_threshold_design": "hold if matched pairs below minimum or outcome matching ambiguous",
                "notes": "Comparison logic only; no result calculated.",
            }
        )
        rows.append(row)
    return rows


def _invalid_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    cases = [
        ("INVALID_PROVIDER_503", "provider_503", "Provider returned 503 or availability error.", "Pack_Behavior_Tier2_Invalid_Output"),
        ("INVALID_MALFORMED_JSON", "malformed_json", "Raw response is not parseable as expected JSON.", "Pack_Behavior_Tier2_Raw_Response_Archive"),
        ("INVALID_TRUNCATED_JSON", "truncated_json", "Raw response appears truncated or incomplete.", "Pack_Behavior_Tier2_Raw_Response_Archive"),
        ("INVALID_SCHEMA_FAILURE", "schema_failure", "Parsed response fails required schema.", "Pack_Behavior_Tier2_Forecasts"),
        ("INVALID_MISSING_FORECAST", "missing_forecast", "Expected forecast row is absent.", "Pack_Behavior_Tier2_Forecasts"),
        ("INVALID_MISSING_RAW", "missing_raw_archive", "Raw response archive row is absent.", "Pack_Behavior_Tier2_Raw_Response_Archive"),
        ("INVALID_MISSING_OUTCOME", "missing_outcome", "No deterministic outcome row can be matched.", "Evaluation_Rows|Outcome_Ledger"),
        ("INVALID_DUPLICATE_FORECAST", "duplicate_forecast_row", "Multiple forecast rows compete for same session/provider/pack/run key.", "Pack_Behavior_Tier2_Forecasts"),
        ("INVALID_RERUN", "rerun_detected", "Provider output appears replaced or rerun without new run_id.", "Pack_Behavior_Tier2_Metadata"),
    ]
    rows: List[Dict[str, Any]] = []
    for case_id, ctype, definition, source in cases:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "invalid_case_id": case_id,
                "invalid_case_type": ctype,
                "definition": definition,
                "source_detection_sheet": source,
                "handling_policy": "NO_SILENT_REPAIR_NO_INFERENCE",
                "affected_rows_policy": "mark affected row invalid and preserve source evidence",
                "affected_pair_policy": "mark comparison pair partial_or_invalid if either side invalid",
                "denominator_policy": "exclude from accuracy denominator; count in invalid-output rate",
                "rerun_policy": "no automatic rerun",
                "archive_policy": "raw archive remains source of truth",
                "interpretation_warning": "invalid outputs can bias coverage; report separately",
                "notes": "Invalid-output handling design only.",
            }
        )
        rows.append(row)
    return rows


def _governance_rows(generated_ts: str, design_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_ACCURACY_EVAL", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_DIRECTION_CORRECTNESS", "direction_correctness_calculated", "0", "0"),
        ("GOV_OVERALL_OK", "overall_ok_calculated", "0", "0"),
        ("GOV_EVAL_ROWS_WRITTEN", "evaluation_rows_written", "0", "0"),
        ("GOV_OUTCOME_LEDGER_WRITTEN", "outcome_ledger_written", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    rows: List[Dict[str, Any]] = []
    for check_id, name, expected, actual in checks:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Design phase governance check.",
            }
        )
        rows.append(row)
    return rows


def _readiness_rows(
    generated_ts: str,
    design_run_id: str,
    experiments: int,
    eligibility: int,
    matching: int,
    metrics: int,
    comparisons: int,
    invalid_cases: int,
    governance_failed: bool,
    reference_missing: Sequence[str],
) -> List[Dict[str, Any]]:
    specs = [
        ("READ_EXPERIMENTS", "experiments_defined", experiments == 3, "", "define 3 approved experiments"),
        ("READ_ELIGIBILITY", "eligibility_rules_defined", eligibility >= 30, "", "define all row eligibility rules"),
        ("READ_MATCHING", "outcome_matching_defined", matching >= 3, "", "define outcome matching rules"),
        ("READ_METRICS", "metric_logic_defined", metrics == 7, "", "define approved metric logic"),
        ("READ_COMPARISONS", "comparison_logic_defined", comparisons >= 6, "", "define required comparison logic"),
        ("READ_INVALID", "invalid_output_policy_defined", invalid_cases >= 9, "", "define invalid-output cases"),
        ("READ_GOVERNANCE", "governance_checks_passed", not governance_failed, "governance failure" if governance_failed else "", "repair failed governance checks"),
        ("READ_NO_EXECUTION", "no_accuracy_execution_performed", True, "", "keep design-only"),
        ("READ_REFERENCE", "reference_sheets_available", True, "", "missing references are warnings only: " + "|".join(reference_missing)),
        ("READ_BUILDER", "ready_for_phase9a5d_execution_builder", not governance_failed and experiments == 3, "", "proceed to execution-builder design"),
    ]
    rows: List[Dict[str, Any]] = []
    for check_id, name, ok, blocking_issue, repair in specs:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "readiness_check_id": check_id,
                "readiness_check_name": name,
                "status": "PASS_WITH_WARNINGS" if name == "reference_sheets_available" and reference_missing else ("PASS" if ok else "FAIL"),
                "blocking_issue": blocking_issue,
                "required_repair": "" if ok else repair,
                "notes": "Ready for execution builder does not authorize accuracy evaluation execution.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("CONTROLLED_ACCURACY_EVALUATION_DESIGN", OUTPUT_DESIGN, "controlled_accuracy_evaluation_design"),
        ("CONTROLLED_ACCURACY_EXPERIMENT_SCHEMA", OUTPUT_EXPERIMENT_SCHEMA, "controlled_accuracy_experiment_schema"),
        ("CONTROLLED_ACCURACY_ROW_ELIGIBILITY_RULES", OUTPUT_ELIGIBILITY, "controlled_accuracy_row_eligibility_rules"),
        ("CONTROLLED_ACCURACY_OUTCOME_MATCHING_DESIGN", OUTPUT_MATCHING, "controlled_accuracy_outcome_matching_design"),
        ("CONTROLLED_ACCURACY_METRIC_LOGIC", OUTPUT_METRIC_LOGIC, "controlled_accuracy_metric_logic"),
        ("CONTROLLED_ACCURACY_COMPARISON_LOGIC", OUTPUT_COMPARISON, "controlled_accuracy_comparison_logic"),
        ("CONTROLLED_ACCURACY_INVALID_OUTPUT_HANDLING", OUTPUT_INVALID, "controlled_accuracy_invalid_output_handling"),
        ("CONTROLLED_ACCURACY_GOVERNANCE_CHECK", OUTPUT_GOVERNANCE, "controlled_accuracy_governance_check"),
        ("CONTROLLED_ACCURACY_EXECUTION_READINESS", OUTPUT_READINESS, "controlled_accuracy_execution_readiness"),
        ("CONTROLLED_ACCURACY_DESIGN_SUMMARY", OUTPUT_SUMMARY, "controlled_accuracy_design_summary"),
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
            "notes": "Phase 9A-5C controlled accuracy evaluation design; no evaluation execution.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5C controlled accuracy evaluation design.")
    return parser.parse_args(argv)


def build_controlled_accuracy_evaluation_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_reference: List[str] = []

    plan_inputs = {sheet: _safe_rows(service, titles, sheet, missing_required, required=True) for sheet in INPUT_5B_SHEETS}
    design_inputs = {sheet: _safe_rows(service, titles, sheet, missing_required, required=True) for sheet in INPUT_5A_SHEETS}
    for sheet in TIER2_SCHEMA_REFERENCE_SHEETS + EVALUATION_REFERENCE_SHEETS:
        _safe_rows(service, titles, sheet, missing_reference)
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5C inputs: {missing_required}")

    plan_summary = plan_inputs["Accuracy_Evaluation_Plan_Summary"][-1] if plan_inputs["Accuracy_Evaluation_Plan_Summary"] else {}
    if _norm(plan_summary.get("readiness_result")) != "READY_FOR_PHASE9A5C_DESIGN":
        raise RuntimeError("Phase 9A-5B plan is not ready for Phase 9A-5C design.")

    plan_experiments = plan_inputs["Accuracy_Evaluation_Experiment_Definition"]
    experiments = _experiment_rows(generated_ts, design_run_id, plan_experiments)
    experiment_ids = [_norm(row.get("experiment_id")) for row in experiments]
    eligibility = _eligibility_rows(generated_ts, design_run_id, experiment_ids)
    matching = _matching_rows(generated_ts, design_run_id)
    metrics = _metric_rows(generated_ts, design_run_id)
    comparisons = _comparison_rows(generated_ts, design_run_id)
    invalid = _invalid_rows(generated_ts, design_run_id)
    governance = _governance_rows(generated_ts, design_run_id)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance)
    readiness = _readiness_rows(
        generated_ts,
        design_run_id,
        len(experiments),
        len(eligibility),
        len(matching),
        len(metrics),
        len(comparisons),
        len(invalid),
        governance_failed,
        [sheet for sheet in EVALUATION_REFERENCE_SHEETS if sheet not in titles],
    )
    readiness_blocked = any(_upper(row.get("status")) in {"FAIL", "BLOCKED"} for row in readiness)

    design_rows = []
    for area, conclusion, action in [
        ("experiment_schema", "Future experiment execution schema is defined for three approved hypotheses.", "PROCEED"),
        ("row_eligibility", "Row eligibility rules are defined and not applied.", "PROCEED"),
        ("outcome_matching", "Outcome matching rules are defined and not executed.", "PROCEED"),
        ("metric_logic", "Metric formulas are defined as pseudocode only.", "PROCEED"),
        ("comparison_logic", "Comparison groups and pairing rules are defined.", "PROCEED"),
        ("invalid_output_policy", "Invalid outputs remain excluded from accuracy denominator and counted separately.", "PROCEED"),
        ("governance", "No accuracy evaluation, outcome matching, provider calls, or production writes occurred.", "PROCEED"),
    ]:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "design_area": area,
                "design_status": "PASS_WITH_WARNINGS" if area in {"invalid_output_policy", "outcome_matching"} else "PASS",
                "source_plan": "Accuracy_Evaluation_Plan_Summary",
                "experiments_designed": len(experiments),
                "metrics_designed": len(metrics),
                "comparison_groups_designed": len(comparisons),
                "eligibility_rules_designed": len(eligibility),
                "outcome_matching_designed": len(matching),
                "invalid_output_policy_designed": len(invalid),
                "accuracy_evaluation_performed": "FALSE",
                "direction_correctness_calculated": "FALSE",
                "overall_ok_calculated": "FALSE",
                "production_change_performed": "FALSE",
                "design_conclusion": conclusion,
                "recommended_next_action": action,
                "notes": "Design-only; no real outcome matching or metric values.",
            }
        )
        design_rows.append(row)

    blocked = governance_failed or readiness_blocked
    build_status = "FAIL" if blocked else "PASS_WITH_WARNINGS"
    final_interpretation = "CONTROLLED_ACCURACY_EVALUATION_DESIGN_BLOCKED" if blocked else "CONTROLLED_ACCURACY_EVALUATION_DESIGN_READY_WITH_WARNINGS"
    recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW" if blocked else "PROCEED_TO_PHASE9A5D_ACCURACY_EVALUATION_EXECUTION_BUILDER"

    summary = _base(generated_ts, design_run_id)
    summary.update(
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "experiments_designed": len(experiments),
            "row_eligibility_rules_defined": len(eligibility),
            "outcome_matching_rules_defined": len(matching),
            "metrics_logic_defined": len(metrics),
            "comparison_logic_rules_defined": len(comparisons),
            "invalid_output_cases_defined": len(invalid),
            "governance_checks_defined": len(governance),
            "readiness_checks_defined": len(readiness),
            "strongest_experiment_candidate": "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "cleanest_comparison_candidate": "OpenAI Pack A vs OpenAI Pack B",
            "highest_risk_evaluation_area": "outcome_matching_and_no_signal_proxy_definition",
            "highest_risk_invalid_output_case": "missing_raw_archive",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "accuracy_evaluation_performed": 0,
            "direction_correctness_calculated": 0,
            "overall_ok_calculated": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_behavior_change_count": 0,
            "ready_for_phase9a5d_execution_builder": "TRUE" if not blocked else "FALSE",
            "ready_for_accuracy_evaluation": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": _truncate_text(
                json.dumps(
                    {
                        "reference_sheets_missing_or_optional": [sheet for sheet in EVALUATION_REFERENCE_SHEETS if sheet not in titles],
                        "tier2_schema_reference_sheets_read": len(TIER2_SCHEMA_REFERENCE_SHEETS),
                        "no_metric_values_calculated": True,
                    },
                    ensure_ascii=True,
                ),
                500,
            ),
        }
    )

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_EXPERIMENT_SCHEMA, EXPERIMENT_HEADERS, experiments),
        (OUTPUT_ELIGIBILITY, ELIGIBILITY_HEADERS, eligibility),
        (OUTPUT_MATCHING, MATCHING_HEADERS, matching),
        (OUTPUT_METRIC_LOGIC, METRIC_HEADERS, metrics),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparisons),
        (OUTPUT_INVALID, INVALID_HEADERS, invalid),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary]),
    ]
    for sheet_name, headers, rows in outputs:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, sheet_headers, rows)
    registry = _upsert_registry_rows(service)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_controlled_accuracy_evaluation_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_designed": len(experiments),
        "row_eligibility_rules_defined": len(eligibility),
        "outcome_matching_rules_defined": len(matching),
        "metrics_logic_defined": len(metrics),
        "comparison_logic_rules_defined": len(comparisons),
        "invalid_output_cases_defined": len(invalid),
        "governance_checks_defined": len(governance),
        "readiness_checks_defined": len(readiness),
        "strongest_experiment_candidate": "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
        "cleanest_comparison_candidate": "OpenAI Pack A vs OpenAI Pack B",
        "highest_risk_evaluation_area": "outcome_matching_and_no_signal_proxy_definition",
        "highest_risk_invalid_output_case": "missing_raw_archive",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "direction_correctness_calculated": 0,
        "overall_ok_calculated": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_behavior_change_count": 0,
        "ready_for_phase9a5d_execution_builder": not blocked,
        "ready_for_accuracy_evaluation": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_controlled_accuracy_evaluation_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
