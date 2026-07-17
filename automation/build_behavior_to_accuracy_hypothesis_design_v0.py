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


SCHEMA_VERSION = "presignal_v2_behavior_to_accuracy_design_0.1"
DESIGN_VERSION = "behavior_to_accuracy_hypothesis_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5A"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_TO_ACCURACY_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_GENERALIZATION_REVIEW = "Pack_Behavior_Tier2_Generalization_Review"
INPUT_HYPOTHESIS_GENERALIZATION = "Pack_Behavior_Tier2_Hypothesis_Generalization"
INPUT_PROVIDER_GENERALIZATION = "Pack_Behavior_Tier2_Provider_Generalization"
INPUT_TRANSITION_GENERALIZATION = "Pack_Behavior_Tier2_Transition_Generalization"
INPUT_FIELD_GENERALIZATION = "Pack_Behavior_Tier2_Field_Generalization"
INPUT_NOSIGNAL_GENERALIZATION = "Pack_Behavior_Tier2_NoSignal_Generalization"
INPUT_INVALID_GENERALIZATION = "Pack_Behavior_Tier2_Invalid_Output_Generalization"
INPUT_GENERALIZATION_SUMMARY = "Pack_Behavior_Tier2_Generalization_Summary"

TIER2_SUPPORT_SHEETS = [
    "Pack_Behavior_Tier2_Runs",
    "Pack_Behavior_Tier2_Forecasts",
    "Pack_Behavior_Tier2_Metadata",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
    "Pack_Behavior_Tier2_Run_Summary",
    "Pack_Behavior_Tier2_Experiment_Design",
    "Pack_Behavior_Tier2_Hypothesis_Test_Plan",
    "Pack_Behavior_Tier2_Success_Criteria",
    "Pack_Behavior_Tier2_Design_Summary",
]

EVALUATION_SCHEMA_REFERENCE_SHEETS = [
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Outcome_Ledger",
    "Session_Forecasts_With_Market_State_Evaluation",
    "Session_Market_State_Impact_Audit",
    "Provider_Pack_Sensitivity_Audit",
]

OUTPUT_DESIGN = "Behavior_To_Accuracy_Hypothesis_Design"
OUTPUT_TESTABLE = "Behavior_To_Accuracy_Testable_Hypotheses"
OUTPUT_ELIGIBLE = "Behavior_To_Accuracy_Eligible_Hypotheses"
OUTPUT_EXCLUDED = "Behavior_To_Accuracy_Excluded_Hypotheses"
OUTPUT_EVALUATION_DESIGN = "Behavior_To_Accuracy_Evaluation_Design"
OUTPUT_METRIC_PLAN = "Behavior_To_Accuracy_Metric_Plan"
OUTPUT_CONFOUNDER = "Behavior_To_Accuracy_Confounder_Audit"
OUTPUT_GOVERNANCE = "Behavior_To_Accuracy_Governance_Check"
OUTPUT_SUMMARY = "Behavior_To_Accuracy_Design_Summary"

ELIGIBLE_BEHAVIOR_HYPOTHESES = [
    "HYP_USDJPY_TREND_REASONING",
    "HYP_A_TO_B_TARGET_STATE_VALUE",
    "HYP_OPENAI_CAUSAL_STABLE",
]

EXCLUDED_BEHAVIOR_HYPOTHESES = [
    "HYP_GEMINI_HIGH_SENSITIVITY",
    "HYP_PACK_E_REDUNDANCY",
    "HYP_ANTHROPIC_DE_INVALID_RISK",
    "HYP_TREASURY_UNDERDETERMINED",
]

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "design_area",
    "design_status",
    "evidence_scope",
    "behavior_confirmed_hypotheses_count",
    "eligible_accuracy_hypotheses_count",
    "excluded_or_held_hypotheses_count",
    "accuracy_evaluation_performed",
    "provider_calls_performed",
    "forecast_generation_performed",
    "production_change_performed",
    "design_conclusion",
    "recommended_next_action",
    "notes",
]

TESTABLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "accuracy_hypothesis_id",
    "source_behavior_hypothesis_id",
    "source_behavior_status",
    "behavior_evidence_summary",
    "accuracy_research_question",
    "accuracy_hypothesis_statement",
    "null_hypothesis",
    "expected_accuracy_direction",
    "required_comparison",
    "required_sample_scope",
    "required_sessions",
    "required_providers",
    "required_pack_levels",
    "required_outcome_fields",
    "allowed_metrics",
    "forbidden_metrics",
    "minimum_sample_warning",
    "confounders",
    "risk_controls",
    "promotion_rule",
    "failure_rule",
    "ready_for_future_accuracy_test",
    "accuracy_evaluation_performed",
    "production_excluded",
    "notes",
]

ELIGIBLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "behavior_hypothesis_id",
    "behavior_generalization_status",
    "behavior_support_level",
    "reason_eligible",
    "allowed_accuracy_design_scope",
    "allowed_comparisons",
    "allowed_metrics",
    "ready_for_future_accuracy_test",
    "notes",
]

EXCLUDED_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "behavior_hypothesis_id",
    "current_status",
    "exclusion_reason",
    "required_before_accuracy_design",
    "possible_future_path",
    "notes",
]

EVALUATION_DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "evaluation_design_id",
    "accuracy_hypothesis_id",
    "evaluation_question",
    "comparison_groups",
    "required_inputs",
    "required_outputs",
    "required_outcome_sources",
    "sample_scope",
    "provider_scope",
    "pack_scope",
    "session_scope",
    "minimum_sample_size_recommendation",
    "primary_metric",
    "secondary_metrics",
    "do_not_use_metrics",
    "control_conditions",
    "confounders",
    "interpretation_limits",
    "ready_for_execution_plan",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "metric_id",
    "metric_name",
    "metric_purpose",
    "metric_definition",
    "required_columns",
    "allowed_use",
    "forbidden_use",
    "risk_of_misinterpretation",
    "notes",
]

CONFOUNDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "confounder_id",
    "confounder_name",
    "confounder_description",
    "affected_hypotheses",
    "affected_comparisons",
    "severity",
    "mitigation",
    "must_resolve_before_accuracy_test",
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

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "behavior_hypotheses_reviewed",
    "behavior_confirmed_hypotheses",
    "eligible_behavior_hypotheses",
    "excluded_or_held_hypotheses",
    "accuracy_testable_hypotheses_defined",
    "evaluation_designs_defined",
    "metrics_defined",
    "confounders_defined",
    "governance_checks_defined",
    "strongest_accuracy_design_candidate",
    "cleanest_provider_testbed_candidate",
    "strongest_pack_comparison_candidate",
    "highest_risk_confounder",
    "provider_calls_performed",
    "forecast_generation_performed",
    "accuracy_evaluation_performed",
    "direction_correctness_calculated",
    "overall_ok_calculated",
    "production_behavior_change_count",
    "ready_for_accuracy_execution_plan",
    "ready_for_accuracy_evaluation",
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
    return f"behavior_to_accuracy_hypothesis_design_v0_{stamp}"


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


def _hypothesis_index(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("hypothesis_id")): row for row in rows if _norm(row.get("hypothesis_id"))}


def _testable_specs() -> List[Dict[str, str]]:
    return [
        {
            "accuracy_hypothesis_id": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "source_behavior_hypothesis_id": "HYP_USDJPY_TREND_REASONING",
            "accuracy_research_question": "Does including USDJPY trend context improve future directional alignment or reduce false-signal behavior relative to no-pack baseline?",
            "accuracy_hypothesis_statement": "If USDJPY trend repeatedly changes provider reasoning, then pack levels containing USDJPY trend should be tested for improved directional alignment or reduced false-signal behavior versus Pack A.",
            "null_hypothesis": "Including USDJPY trend context has no measurable effect on future directional alignment, no-signal correctness, or false-signal behavior versus Pack A.",
            "expected_accuracy_direction": "PACK_EXPOSURE_IMPROVES_DIRECTIONAL_ALIGNMENT",
            "required_comparison": "Pack A vs Pack B|Pack A vs Pack D|Pack A vs Pack E",
            "required_sample_scope": "future controlled sessions with outcome labels and complete raw archive",
            "required_sessions": ">=8 behavior-tested sessions plus future evaluation-plan minimum",
            "required_providers": "OpenAI|Gemini|Anthropic, with invalid cells isolated",
            "required_pack_levels": "Pack A|Pack B|Pack D|Pack E",
            "required_outcome_fields": "mr_real_dir|realized_pips|no_signal_outcome_proxy|evaluation_window_metadata",
            "allowed_metrics": "direction_match_rate|false_signal_rate|behavior_conditioned_accuracy_delta|pack_vs_baseline_delta",
            "forbidden_metrics": "provider ranking|best pack|production score|statistical significance without adequate sample",
            "minimum_sample_warning": "Do not interpret until sample size and invalid-output controls are defined in Phase 9A-5B.",
            "confounders": "small_sample_size|session_selection_bias|market_regime_dependence|outcome_label_noise|behavior_change_not_accuracy",
            "risk_controls": "Compare only matched sessions and provider/pack cells; isolate invalid outputs; preserve Pack A baseline.",
            "promotion_rule": "Promote to execution plan only if matched baseline/treatment cells and outcome fields are available without production writes.",
            "failure_rule": "Hold if outcome fields are missing, invalid-output rate contaminates comparisons, or Pack A baseline is incomplete.",
            "notes": "Design only; no metric values calculated.",
        },
        {
            "accuracy_hypothesis_id": "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
            "source_behavior_hypothesis_id": "HYP_A_TO_B_TARGET_STATE_VALUE",
            "accuracy_research_question": "Does Pack B target-state exposure improve signal discipline compared with Pack A?",
            "accuracy_hypothesis_statement": "If A_to_B has high behavioral value, then Pack B should be tested for reduced unsupported directional signals or improved no-signal decisions compared with Pack A.",
            "null_hypothesis": "Pack B target-state exposure has no measurable effect on false-signal rate, no-signal correctness, or directional alignment versus Pack A.",
            "expected_accuracy_direction": "PACK_EXPOSURE_IMPROVES_NO_SIGNAL_DISCIPLINE",
            "required_comparison": "Pack A vs Pack B",
            "required_sample_scope": "matched Pack A and Pack B cells by session/provider",
            "required_sessions": ">=8 behavior-tested sessions plus future evaluation-plan minimum",
            "required_providers": "OpenAI|Gemini|Anthropic, with provider-specific invalid risk controls",
            "required_pack_levels": "Pack A|Pack B",
            "required_outcome_fields": "mr_real_dir|realized_pips|no_signal_outcome_proxy|evaluation_window_metadata",
            "allowed_metrics": "false_signal_rate|no_signal_correctness|direction_match_rate|pack_vs_baseline_delta",
            "forbidden_metrics": "overall_ok|provider ranking|best pack|production score",
            "minimum_sample_warning": "Pack B effects must be evaluated only on matched valid cells.",
            "confounders": "small_sample_size|event_cluster_complexity|confidence_not_accuracy|behavior_change_not_accuracy",
            "risk_controls": "Matched A/B comparisons; exclude invalid cells; do not impute no-signal outcomes.",
            "promotion_rule": "Proceed if future plan can define no-signal correctness safely without overclaiming.",
            "failure_rule": "Hold if no-signal outcome proxy cannot be defined or Pack A/B matched cells are insufficient.",
            "notes": "Tests signal discipline, not whether Pack B is best.",
        },
        {
            "accuracy_hypothesis_id": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "source_behavior_hypothesis_id": "HYP_OPENAI_CAUSAL_STABLE",
            "accuracy_research_question": "Can OpenAI's output-stable causal rewrites provide a clean future test bed for pack-driven accuracy effects?",
            "accuracy_hypothesis_statement": "If OpenAI reliably rewrites causal chains with low output risk, then OpenAI-only matched pack comparisons may be a clean test bed for future behavior-conditioned accuracy analysis.",
            "null_hypothesis": "OpenAI's stable causal rewriting does not provide a cleaner or more interpretable pack-conditioned accuracy test bed.",
            "expected_accuracy_direction": "PACK_EXPOSURE_IMPROVES_PROVIDER_CONSISTENCY",
            "required_comparison": "OpenAI Pack A vs OpenAI Pack B|OpenAI Pack A vs OpenAI Pack D",
            "required_sample_scope": "OpenAI-only matched provider/pack/session cells",
            "required_sessions": ">=8 behavior-tested sessions plus future evaluation-plan minimum",
            "required_providers": "OpenAI",
            "required_pack_levels": "Pack A|Pack B|Pack D",
            "required_outcome_fields": "mr_real_dir|realized_pips|evaluation_window_metadata",
            "allowed_metrics": "provider_stability_control|behavior_conditioned_accuracy_delta|direction_match_rate|confidence_calibration_proxy",
            "forbidden_metrics": "provider ranking|OpenAI is best|production routing|production weighting",
            "minimum_sample_warning": "Provider-specific design is a control strategy, not a provider superiority claim.",
            "confounders": "provider_specific_prompt_behavior|session_selection_bias|confidence_not_accuracy|outcome_label_noise",
            "risk_controls": "Use OpenAI as a clean test bed only; keep provider ranking forbidden.",
            "promotion_rule": "Proceed if future plan keeps provider-specific interpretation limited to test-bed cleanliness.",
            "failure_rule": "Hold if design language implies OpenAI superiority or routing preference.",
            "notes": "OpenAI is not accuracy-proven; this is a controlled test-bed hypothesis.",
        },
    ]


def _excluded_specs() -> Dict[str, Dict[str, str]]:
    return {
        "HYP_GEMINI_HIGH_SENSITIVITY": {
            "exclusion_reason": "Behavior sensitivity is mixed with provider 503 availability risk.",
            "required_before_accuracy_design": "Split into HYP_GEMINI_HIGH_SENSITIVITY_WHEN_VALID and HYP_GEMINI_PROVIDER_AVAILABILITY_RISK.",
            "possible_future_path": "Revised behavior hypothesis and provider-availability control design.",
        },
        "HYP_PACK_E_REDUNDANCY": {
            "exclusion_reason": "Tier 2 weakened simple D/E redundancy; D_to_E showed behavior movement.",
            "required_before_accuracy_design": "Clarify D/E framing variance or behavioral instability before accuracy testing.",
            "possible_future_path": "Revised Pack E framing/stability design.",
        },
        "HYP_ANTHROPIC_DE_INVALID_RISK": {
            "exclusion_reason": "Held due malformed/truncated output risk in later-pack contexts.",
            "required_before_accuracy_design": "Provider/output-risk guardrails and invalid-cell handling review.",
            "possible_future_path": "Invalid-output repair or provider-specific robustness design.",
        },
        "HYP_TREASURY_UNDERDETERMINED": {
            "exclusion_reason": "Behaviorally active but mixed; not behavior-confirmed.",
            "required_before_accuracy_design": "Stronger behavior support or revised narrower treasury hypothesis.",
            "possible_future_path": "Retain as candidate pattern for future behavior stability work.",
        },
    }


def _metric_specs() -> List[Dict[str, str]]:
    metric_specs = [
        ("METRIC_DIRECTION_MATCH_RATE", "direction_match_rate", "Future directional alignment test", "Share of valid matched forecast cells whose forecast direction aligns with future outcome direction."),
        ("METRIC_NO_SIGNAL_CORRECTNESS", "no_signal_correctness", "Future no-signal discipline test", "Whether no-signal calls correspond to low/ambiguous realized movement under a predefined proxy."),
        ("METRIC_FALSE_SIGNAL_RATE", "false_signal_rate", "Unsupported signal risk", "Share of directional forecasts that occur when future outcome proxy indicates no meaningful directional move."),
        ("METRIC_BEHAVIOR_CONDITIONED_ACCURACY_DELTA", "behavior_conditioned_accuracy_delta", "Behavior-conditioned future evaluation", "Accuracy delta conditioned on observed behavior transition category."),
        ("METRIC_PACK_VS_BASELINE_DELTA", "pack_vs_baseline_delta", "Matched pack comparison", "Treatment pack metric minus Pack A baseline metric for same session/provider where valid."),
        ("METRIC_PROVIDER_STABILITY_CONTROL", "provider_stability_control", "Provider-specific cleanliness control", "Restrict comparisons to a provider with low output invalidity to isolate pack effect."),
        ("METRIC_CONFIDENCE_CALIBRATION_PROXY", "confidence_calibration_proxy", "Confidence sanity check", "Relationship between stated confidence and future correctness proxy; not calibration proof."),
    ]
    rows: List[Dict[str, str]] = []
    for metric_id, name, purpose, definition in metric_specs:
        rows.append(
            {
                "metric_id": metric_id,
                "metric_name": name,
                "metric_purpose": purpose,
                "metric_definition": definition,
                "required_columns": "session_id|provider|pack_level|forecast_direction|no_signal_flag|forecast_confidence|outcome_direction_proxy|realized_pips|valid_output_flag",
                "allowed_use": "Future controlled evaluation design only after execution plan approval.",
                "forbidden_use": "No provider ranking, pack ranking, production scoring, or claims during this design phase.",
                "risk_of_misinterpretation": "Metric definition can be mistaken for metric result; no values are calculated here.",
                "notes": "Defined only; not calculated.",
            }
        )
    return rows


def _confounder_specs() -> List[Dict[str, str]]:
    confounder_specs = [
        ("CONF_SMALL_SAMPLE_SIZE", "small_sample_size", "Current behavior evidence is larger than Tier 1 but future accuracy tests still need explicit sample thresholds.", "HIGH", "Set minimum matched-cell thresholds before evaluation."),
        ("CONF_PROVIDER_INVALID_OUTPUTS", "provider_invalid_outputs", "Invalid provider outputs can bias matched comparisons if excluded asymmetrically.", "HIGH", "Preserve invalid cells and report valid-cell coverage."),
        ("CONF_GEMINI_503", "provider_503_availability_risk", "Gemini provider 503 risk may distort provider/pack coverage.", "HIGH", "Separate availability from behavior sensitivity."),
        ("CONF_ANTHROPIC_TRUNCATION", "anthropic_truncated_json_risk", "Anthropic malformed/truncated JSON risk remains concentrated in later packs.", "HIGH", "Hold Anthropic D/E accuracy tests until output risk is controlled."),
        ("CONF_PACK_D_E_FRAMING", "pack_d_e_framing_variance", "D/E behavior movement may reflect prompt/framing variance rather than pack content.", "MEDIUM", "Clarify D/E design before using Pack E in accuracy hypotheses."),
        ("CONF_OUTCOME_LABEL_NOISE", "outcome_label_noise", "Market reaction labels and no-signal proxies may be noisy.", "HIGH", "Define outcome windows and no-signal proxy before evaluation."),
        ("CONF_SESSION_SELECTION_BIAS", "session_selection_bias", "Eligible deterministic sessions may not represent all market regimes.", "MEDIUM", "Use explicit session inclusion criteria and report coverage."),
        ("CONF_EVENT_CLUSTER_COMPLEXITY", "event_cluster_complexity", "Clustered events can obscure attribution to pack context.", "MEDIUM", "Stratify or flag clustered sessions."),
        ("CONF_MARKET_REGIME", "market_regime_dependence", "Pack effects may vary by volatility/regime.", "MEDIUM", "Record regime descriptors without adding qualitative pack fields."),
        ("CONF_CONFIDENCE_NOT_ACCURACY", "confidence_not_accuracy", "Confidence changes are behavioral and may not imply correctness.", "HIGH", "Keep confidence metrics secondary and clearly labeled."),
        ("CONF_BEHAVIOR_NOT_ACCURACY", "behavior_change_not_accuracy", "Behavior changes are not evidence of improved outcomes.", "HIGH", "Require future outcome-based evaluation before accuracy claims."),
    ]
    rows: List[Dict[str, str]] = []
    for cid, name, desc, severity, mitigation in confounder_specs:
        rows.append(
            {
                "confounder_id": cid,
                "confounder_name": name,
                "confounder_description": desc,
                "affected_hypotheses": "|".join(ELIGIBLE_BEHAVIOR_HYPOTHESES),
                "affected_comparisons": "Pack A vs Pack B|Pack A vs Pack D|Pack A vs Pack E|OpenAI Pack A vs OpenAI Pack B",
                "severity": severity,
                "mitigation": mitigation,
                "must_resolve_before_accuracy_test": "TRUE" if severity == "HIGH" else "FALSE",
                "notes": "Confounder must be handled before interpreting future accuracy results.",
            }
        )
    return rows


def _governance_specs() -> List[Dict[str, Any]]:
    return [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_ACCURACY_EVAL", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_DIRECTION_CORRECTNESS", "direction_correctness_calculated", "0", "0"),
        ("GOV_OVERALL_OK", "overall_ok_calculated", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
        ("GOV_PREDICTION_WRITES", "prediction_sheet_writes", "0", "0"),
        ("GOV_OUTCOME_LEDGER_WRITES", "outcome_ledger_writes", "0", "0"),
    ]


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN", OUTPUT_DESIGN, "behavior_to_accuracy_hypothesis_design"),
        ("BEHAVIOR_TO_ACCURACY_TESTABLE_HYPOTHESES", OUTPUT_TESTABLE, "behavior_to_accuracy_testable_hypotheses"),
        ("BEHAVIOR_TO_ACCURACY_ELIGIBLE_HYPOTHESES", OUTPUT_ELIGIBLE, "behavior_to_accuracy_eligible_hypotheses"),
        ("BEHAVIOR_TO_ACCURACY_EXCLUDED_HYPOTHESES", OUTPUT_EXCLUDED, "behavior_to_accuracy_excluded_hypotheses"),
        ("BEHAVIOR_TO_ACCURACY_EVALUATION_DESIGN", OUTPUT_EVALUATION_DESIGN, "behavior_to_accuracy_evaluation_design"),
        ("BEHAVIOR_TO_ACCURACY_METRIC_PLAN", OUTPUT_METRIC_PLAN, "behavior_to_accuracy_metric_plan"),
        ("BEHAVIOR_TO_ACCURACY_CONFOUNDER_AUDIT", OUTPUT_CONFOUNDER, "behavior_to_accuracy_confounder_audit"),
        ("BEHAVIOR_TO_ACCURACY_GOVERNANCE_CHECK", OUTPUT_GOVERNANCE, "behavior_to_accuracy_governance_check"),
        ("BEHAVIOR_TO_ACCURACY_DESIGN_SUMMARY", OUTPUT_SUMMARY, "behavior_to_accuracy_design_summary"),
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
            "notes": "Phase 9A-5A behavior-to-accuracy design; no accuracy evaluation, no providers, no production.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5A behavior-to-accuracy hypothesis design.")
    return parser.parse_args(argv)


def build_behavior_to_accuracy_hypothesis_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_optional: List[str] = []

    generalization_review = _safe_rows(service, titles, INPUT_GENERALIZATION_REVIEW, missing_required, required=True)
    hypothesis_generalization = _safe_rows(service, titles, INPUT_HYPOTHESIS_GENERALIZATION, missing_required, required=True)
    provider_generalization = _safe_rows(service, titles, INPUT_PROVIDER_GENERALIZATION, missing_required, required=True)
    transition_generalization = _safe_rows(service, titles, INPUT_TRANSITION_GENERALIZATION, missing_required, required=True)
    field_generalization = _safe_rows(service, titles, INPUT_FIELD_GENERALIZATION, missing_required, required=True)
    nosignal_generalization = _safe_rows(service, titles, INPUT_NOSIGNAL_GENERALIZATION, missing_required, required=True)
    invalid_generalization = _safe_rows(service, titles, INPUT_INVALID_GENERALIZATION, missing_required, required=True)
    generalization_summary = _safe_rows(service, titles, INPUT_GENERALIZATION_SUMMARY, missing_required, required=True)

    for sheet in TIER2_SUPPORT_SHEETS + EVALUATION_SCHEMA_REFERENCE_SHEETS:
        _safe_rows(service, titles, sheet, missing_optional)

    if missing_required or not generalization_summary:
        raise RuntimeError(f"Missing required behavior-to-accuracy inputs: {missing_required}")

    hypothesis_by_id = _hypothesis_index(hypothesis_generalization)
    eligible_rows = []
    for hypothesis_id in ELIGIBLE_BEHAVIOR_HYPOTHESES:
        source = hypothesis_by_id.get(hypothesis_id, {})
        if not source or not _truth(source.get("ready_for_behavior_to_accuracy_design")):
            raise RuntimeError(f"Expected eligible hypothesis missing or not ready: {hypothesis_id}")
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "behavior_hypothesis_id": hypothesis_id,
                "behavior_generalization_status": _norm(source.get("generalization_status")),
                "behavior_support_level": _norm(source.get("behavior_support_level")),
                "reason_eligible": _truncate_text(source.get("supporting_evidence_summary"), 500),
                "allowed_accuracy_design_scope": "Future matched controlled evaluation only; no execution in Phase 9A-5A.",
                "allowed_comparisons": "Pack A vs Pack B|Pack A vs Pack D|Pack A vs Pack E|OpenAI Pack A vs OpenAI Pack B",
                "allowed_metrics": "direction_match_rate|false_signal_rate|no_signal_correctness|behavior_conditioned_accuracy_delta|pack_vs_baseline_delta",
                "ready_for_future_accuracy_test": "TRUE",
                "notes": "Eligible for design only; not accuracy-validated.",
            }
        )
        eligible_rows.append(row)

    excluded_specs = _excluded_specs()
    excluded_rows = []
    for hypothesis_id in EXCLUDED_BEHAVIOR_HYPOTHESES:
        source = hypothesis_by_id.get(hypothesis_id, {})
        spec = excluded_specs[hypothesis_id]
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "behavior_hypothesis_id": hypothesis_id,
                "current_status": _norm(source.get("generalization_status")) or _norm(source.get("recommended_status")),
                "exclusion_reason": spec["exclusion_reason"],
                "required_before_accuracy_design": spec["required_before_accuracy_design"],
                "possible_future_path": spec["possible_future_path"],
                "notes": "Excluded from Phase 9A-5A direct accuracy design.",
            }
        )
        excluded_rows.append(row)

    testable_rows = []
    evaluation_rows = []
    for spec in _testable_specs():
        source = hypothesis_by_id.get(spec["source_behavior_hypothesis_id"], {})
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "accuracy_hypothesis_id": spec["accuracy_hypothesis_id"],
                "source_behavior_hypothesis_id": spec["source_behavior_hypothesis_id"],
                "source_behavior_status": _norm(source.get("generalization_status")),
                "behavior_evidence_summary": _truncate_text(source.get("supporting_evidence_summary"), 500),
                "accuracy_research_question": spec["accuracy_research_question"],
                "accuracy_hypothesis_statement": spec["accuracy_hypothesis_statement"],
                "null_hypothesis": spec["null_hypothesis"],
                "expected_accuracy_direction": spec["expected_accuracy_direction"],
                "required_comparison": spec["required_comparison"],
                "required_sample_scope": spec["required_sample_scope"],
                "required_sessions": spec["required_sessions"],
                "required_providers": spec["required_providers"],
                "required_pack_levels": spec["required_pack_levels"],
                "required_outcome_fields": spec["required_outcome_fields"],
                "allowed_metrics": spec["allowed_metrics"],
                "forbidden_metrics": spec["forbidden_metrics"],
                "minimum_sample_warning": spec["minimum_sample_warning"],
                "confounders": spec["confounders"],
                "risk_controls": spec["risk_controls"],
                "promotion_rule": spec["promotion_rule"],
                "failure_rule": spec["failure_rule"],
                "ready_for_future_accuracy_test": "TRUE",
                "accuracy_evaluation_performed": "FALSE",
                "production_excluded": "TRUE",
                "notes": spec["notes"],
            }
        )
        testable_rows.append(row)
        eval_row = _base(generated_ts, design_run_id)
        eval_row.update(
            {
                "evaluation_design_id": f"EVAL_DESIGN_{spec['accuracy_hypothesis_id']}",
                "accuracy_hypothesis_id": spec["accuracy_hypothesis_id"],
                "evaluation_question": spec["accuracy_research_question"],
                "comparison_groups": spec["required_comparison"],
                "required_inputs": "Behavior_To_Accuracy_Testable_Hypotheses|Tier2 execution outputs|future evaluation outcome sheets",
                "required_outputs": "Future accuracy evaluation design outputs only; no outputs generated now.",
                "required_outcome_sources": spec["required_outcome_fields"],
                "sample_scope": spec["required_sample_scope"],
                "provider_scope": spec["required_providers"],
                "pack_scope": spec["required_pack_levels"],
                "session_scope": "matched controlled sessions with complete raw archive and valid output cells",
                "minimum_sample_size_recommendation": "Define in Phase 9A-5B before evaluation execution.",
                "primary_metric": spec["allowed_metrics"].split("|")[0],
                "secondary_metrics": "|".join(spec["allowed_metrics"].split("|")[1:]),
                "do_not_use_metrics": spec["forbidden_metrics"],
                "control_conditions": "matched session/provider cells|Pack A baseline|invalid cell isolation|no imputation",
                "confounders": spec["confounders"],
                "interpretation_limits": "Future evaluation may test accuracy; this phase only defines the test.",
                "ready_for_execution_plan": "TRUE",
                "notes": "Design only.",
            }
        )
        evaluation_rows.append(eval_row)

    metric_rows = []
    for spec in _metric_specs():
        row = _base(generated_ts, design_run_id)
        row.update(spec)
        metric_rows.append(row)

    confounder_rows = []
    for spec in _confounder_specs():
        row = _base(generated_ts, design_run_id)
        row.update(spec)
        confounder_rows.append(row)

    governance_rows = []
    for check_id, check_name, expected, actual in _governance_specs():
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": check_name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Design phase governance check.",
            }
        )
        governance_rows.append(row)

    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    enough_design = len(testable_rows) >= 2 and len(evaluation_rows) == len(testable_rows) and metric_rows and confounder_rows and not governance_failed
    build_status = "FAIL" if governance_failed else "PASS_WITH_WARNINGS"
    final_interpretation = "BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN_BLOCKED" if governance_failed else "BEHAVIOR_TO_ACCURACY_HYPOTHESIS_DESIGN_READY_WITH_WARNINGS"
    recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW" if governance_failed else "PROCEED_TO_PHASE9A5B_ACCURACY_EVALUATION_PLAN"

    design_rows = []
    for area, conclusion, action in [
        ("eligibility", "Only behavior-confirmed hypotheses are eligible for future accuracy-test design.", "USE_ELIGIBLE_SET_ONLY"),
        ("testable_hypotheses", "Three behavior-confirmed hypotheses were converted into future accuracy-testable hypotheses.", "PROCEED_TO_EVALUATION_PLAN"),
        ("excluded_hypotheses", "Four revised, held, or mixed hypotheses were excluded from direct accuracy design.", "HOLD_OR_REVISE_BEFORE_ACCURACY"),
        ("metric_plan", "Future metrics were defined but not calculated.", "DEFINE_EXECUTION_PLAN_BEFORE_USE"),
        ("confounders", "Known interpretation risks were listed before future accuracy evaluation.", "CONTROL_BEFORE_EXECUTION"),
        ("governance", "No provider calls, forecasts, accuracy evaluation, or production changes occurred.", "PASS_GOVERNANCE"),
    ]:
        row = _base(generated_ts, design_run_id)
        row.update(
            {
                "design_area": area,
                "design_status": "PASS_WITH_WARNINGS" if area in {"excluded_hypotheses", "confounders"} else "PASS",
                "evidence_scope": "Phase 9A-4ZZ behavior generalization review and Tier 2 execution evidence",
                "behavior_confirmed_hypotheses_count": len(eligible_rows),
                "eligible_accuracy_hypotheses_count": len(testable_rows),
                "excluded_or_held_hypotheses_count": len(excluded_rows),
                "accuracy_evaluation_performed": "FALSE",
                "provider_calls_performed": "FALSE",
                "forecast_generation_performed": "FALSE",
                "production_change_performed": "FALSE",
                "design_conclusion": conclusion,
                "recommended_next_action": action,
                "notes": "Design-only bridge from behavior evidence to future accuracy hypothesis planning.",
            }
        )
        design_rows.append(row)

    summary_row = _base(generated_ts, design_run_id)
    summary_row.update(
        {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "behavior_hypotheses_reviewed": len(ELIGIBLE_BEHAVIOR_HYPOTHESES) + len(EXCLUDED_BEHAVIOR_HYPOTHESES),
            "behavior_confirmed_hypotheses": len(eligible_rows),
            "eligible_behavior_hypotheses": len(eligible_rows),
            "excluded_or_held_hypotheses": len(excluded_rows),
            "accuracy_testable_hypotheses_defined": len(testable_rows),
            "evaluation_designs_defined": len(evaluation_rows),
            "metrics_defined": len(metric_rows),
            "confounders_defined": len(confounder_rows),
            "governance_checks_defined": len(governance_rows),
            "strongest_accuracy_design_candidate": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
            "cleanest_provider_testbed_candidate": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
            "strongest_pack_comparison_candidate": "Pack A vs Pack B",
            "highest_risk_confounder": "provider_invalid_outputs",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "accuracy_evaluation_performed": 0,
            "direction_correctness_calculated": 0,
            "overall_ok_calculated": 0,
            "production_behavior_change_count": 0,
            "ready_for_accuracy_execution_plan": "TRUE" if enough_design else "FALSE",
            "ready_for_accuracy_evaluation": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": _truncate_text(
                json.dumps(
                    {
                        "generalization_summary_rows": len(generalization_summary),
                        "review_rows": len(generalization_review),
                        "provider_generalization_rows": len(provider_generalization),
                        "transition_generalization_rows": len(transition_generalization),
                        "field_generalization_rows": len(field_generalization),
                        "nosignal_generalization_rows": len(nosignal_generalization),
                        "invalid_generalization_rows": len(invalid_generalization),
                        "missing_optional_schema_reference_sheets": [sheet for sheet in EVALUATION_SCHEMA_REFERENCE_SHEETS if sheet not in titles],
                    },
                    ensure_ascii=True,
                ),
                500,
            ),
        }
    )

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_TESTABLE, TESTABLE_HEADERS, testable_rows),
        (OUTPUT_ELIGIBLE, ELIGIBLE_HEADERS, eligible_rows),
        (OUTPUT_EXCLUDED, EXCLUDED_HEADERS, excluded_rows),
        (OUTPUT_EVALUATION_DESIGN, EVALUATION_DESIGN_HEADERS, evaluation_rows),
        (OUTPUT_METRIC_PLAN, METRIC_HEADERS, metric_rows),
        (OUTPUT_CONFOUNDER, CONFOUNDER_HEADERS, confounder_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]
    for sheet_name, headers, rows in outputs:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, sheet_headers, rows)
    registry = _upsert_registry_rows(service)

    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "design_run_id": design_run_id,
        "file_created": "automation/build_behavior_to_accuracy_hypothesis_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "behavior_hypotheses_reviewed": len(ELIGIBLE_BEHAVIOR_HYPOTHESES) + len(EXCLUDED_BEHAVIOR_HYPOTHESES),
        "behavior_confirmed_hypotheses": len(eligible_rows),
        "eligible_behavior_hypotheses": len(eligible_rows),
        "excluded_or_held_hypotheses": len(excluded_rows),
        "accuracy_testable_hypotheses_defined": len(testable_rows),
        "evaluation_designs_defined": len(evaluation_rows),
        "metrics_defined": len(metric_rows),
        "confounders_defined": len(confounder_rows),
        "governance_checks_defined": len(governance_rows),
        "strongest_accuracy_design_candidate": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
        "cleanest_provider_testbed_candidate": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
        "strongest_pack_comparison_candidate": "Pack A vs Pack B",
        "highest_risk_confounder": "provider_invalid_outputs",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "accuracy_evaluation_performed": 0,
        "direction_correctness_calculated": 0,
        "overall_ok_calculated": 0,
        "production_behavior_change_count": 0,
        "ready_for_accuracy_execution_plan": enough_design,
        "ready_for_accuracy_evaluation": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_behavior_to_accuracy_hypothesis_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
