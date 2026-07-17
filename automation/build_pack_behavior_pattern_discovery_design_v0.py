import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

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


SCHEMA_VERSION = "presignal_v2_behavior_pattern_discovery_design_0.1"
DESIGN_VERSION = "behavior_pattern_discovery_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_PATTERN_DISCOVERY_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

OUTPUT_DESIGN_SHEET = "Pack_Behavior_Pattern_Discovery_Design"
OUTPUT_METRICS_SHEET = "Pack_Behavior_Pattern_Metrics_Definition"
OUTPUT_GROUPING_SHEET = "Pack_Behavior_Pattern_Grouping_Rules"
OUTPUT_INVALID_RULES_SHEET = "Pack_Behavior_Pattern_Invalid_Output_Rules"
OUTPUT_READINESS_SHEET = "Pack_Behavior_Pattern_Readiness_Audit"
OUTPUT_SUMMARY_SHEET = "Pack_Behavior_Pattern_Discovery_Summary"

PHASE9A_OUTPUT_SHEETS = [
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
OPTIONAL_SHEETS = [
    "Session_Attention_Map_History",
    "Session_Information_Requests_History",
    "Market_State_Pack_Candidates_History",
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Item_Audit",
    "Market_State_Pack_Coverage_Audit",
    "Sheet_Registry",
    "Workbook_Migration_Control",
    "Workbook_Migration_Log",
]

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_id",
    "design_component",
    "component_status",
    "component_purpose",
    "input_sheets_required",
    "output_sheets_expected_later",
    "aggregation_unit",
    "grouping_dimensions",
    "minimum_sample_requirement",
    "invalid_output_handling",
    "accuracy_excluded",
    "provider_calls_excluded",
    "production_excluded",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "metric_id",
    "metric_name",
    "metric_family",
    "metric_description",
    "calculation_source",
    "calculation_rule",
    "allowed_grouping_dimensions",
    "minimum_valid_rows",
    "invalid_output_policy",
    "interpretation",
    "non_interpretation",
    "accuracy_related",
    "ready_for_phase9a5_gate",
    "notes",
]

GROUPING_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "grouping_rule_id",
    "grouping_name",
    "grouping_purpose",
    "primary_dimensions",
    "secondary_dimensions",
    "allowed_metrics",
    "minimum_sample_size",
    "minimum_provider_coverage",
    "minimum_pack_coverage",
    "invalid_output_policy",
    "interpretation_allowed",
    "interpretation_forbidden",
    "notes",
]

INVALID_RULE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "invalid_rule_id",
    "invalid_case_type",
    "example",
    "affected_tables",
    "handling_rule",
    "count_as_valid_observation",
    "count_as_invalid_observation",
    "count_as_partial_comparison",
    "allow_imputation",
    "allow_provider_rerun",
    "allow_accuracy_evaluation",
    "recommended_label",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
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
    "design_version",
    "build_status",
    "final_interpretation",
    "design_components_defined",
    "metrics_defined",
    "grouping_rules_defined",
    "invalid_output_rules_defined",
    "readiness_checks_defined",
    "phase9a3_build_status",
    "phase9a3_final_interpretation",
    "phase9a3r_repair_confirmed",
    "session_count_current",
    "provider_count_current",
    "pack_level_count_current",
    "valid_outputs_current",
    "invalid_outputs_current",
    "behavior_signal_classification_current",
    "single_session_generalization_allowed",
    "accuracy_evaluation_count",
    "provider_call_count",
    "forecast_generation_count",
    "production_behavior_change_count",
    "ready_for_phase9a4_execution_design",
    "ready_for_phase9a5_accuracy_evaluation",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(ts: str) -> str:
    stamp = ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"behavior_pattern_discovery_design_v0_{stamp}"


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


def _read_rows_if_exists(service, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
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


def _behavior_signal(summary: Dict[str, Any]) -> str:
    reasoning = _as_int(summary.get("reasoning_change_count"))
    causal = _as_int(summary.get("causal_chain_change_count"))
    direction = _as_int(summary.get("direction_change_count"))
    confidence = _as_int(summary.get("confidence_change_count"))
    no_signal = _as_int(summary.get("no_signal_change_count"))
    field_changed = _as_int(summary.get("field_changed_reasoning_count"))
    if reasoning >= 12 and causal >= 12 and (direction + confidence + no_signal + field_changed) >= 25:
        return "STRONG_BEHAVIOR_SIGNAL"
    if reasoning >= 6 or causal >= 6:
        return "MODERATE_BEHAVIOR_SIGNAL"
    if reasoning or causal or direction or confidence or no_signal:
        return "WEAK_BEHAVIOR_SIGNAL"
    return "NO_OBSERVABLE_BEHAVIOR_SIGNAL"


def _sheet_list(values: Sequence[str]) -> str:
    return "|".join(values)


def _common_design_row(
    generated_ts: str,
    design_id: str,
    component: str,
    purpose: str,
    aggregation_unit: str,
    grouping_dimensions: str,
    minimum_sample_requirement: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "design_id": design_id,
        "design_component": component,
        "component_status": "DEFINED",
        "component_purpose": purpose,
        "input_sheets_required": _sheet_list(PHASE9A_OUTPUT_SHEETS),
        "output_sheets_expected_later": "Pack_Behavior_Pattern_Summary|Pack_Behavior_Pattern_Provider_Profile|Pack_Behavior_Pattern_Field_Profile",
        "aggregation_unit": aggregation_unit,
        "grouping_dimensions": grouping_dimensions,
        "minimum_sample_requirement": minimum_sample_requirement,
        "invalid_output_handling": "Exclude invalid cells from valid-rate denominators; count invalid cells separately; never impute.",
        "accuracy_excluded": "TRUE",
        "provider_calls_excluded": "TRUE",
        "production_excluded": "TRUE",
        "notes": notes,
    }


def _build_design_rows(generated_ts: str, design_id: str) -> List[Dict[str, Any]]:
    components = [
        ("provider_pack_sensitivity", "Measure whether each provider repeatedly changes behavior when pack exposure changes.", "provider x transition x session", "provider|pack_transition|session_id", "candidate_pattern requires n>=10 valid transitions across >=3 sessions"),
        ("pack_transition_behavior_value", "Measure which pack transitions repeatedly produce observable behavior changes.", "transition x session x provider", "pack_transition|provider|session_id", "weak_pattern requires n>=5 valid transitions across >=2 sessions"),
        ("reasoning_transition_stability", "Track recurring causal-chain, driver, and information-use transitions.", "reasoning transition", "provider|pack_transition|reasoning_transition_label", "stable_pattern_candidate requires n>=20 valid transitions across >=5 sessions"),
        ("field_influence_recurrence", "Detect fields repeatedly used, discarded, changed reasoning, or marked no-effect.", "field x provider x pack_level", "candidate_field|provider|pack_level|session_id", "candidate_pattern requires n>=10 field observations across >=3 sessions"),
        ("field_family_influence_recurrence", "Aggregate conservative field-level evidence into family-level recurrence without over-attribution.", "field_family x provider x pack_level", "candidate_family|provider|pack_transition", "family claims require >=10 observations and field-level support"),
        ("no_signal_transition_pattern", "Measure recurring no-signal state changes under pack exposure.", "provider x transition", "provider|pack_transition|no_signal_state", "candidate_pattern requires n>=10 valid no-signal transition observations"),
        ("confidence_transition_pattern", "Measure recurring confidence increases/decreases without treating confidence as accuracy.", "provider x transition", "provider|pack_transition|confidence_bucket", "material confidence patterns require >=10 valid transitions"),
        ("causal_chain_rewrite_pattern", "Identify transitions that repeatedly rewrite causal-chain text.", "provider x transition", "provider|pack_transition|reasoning_transition_label", "stable pattern requires >=20 valid transitions across >=5 sessions"),
        ("pack_redundancy_detection", "Detect pack levels with repeated low incremental behavior value.", "pack transition", "pack_transition|provider|session_id", "redundancy claims require >=20 valid comparisons across >=5 sessions"),
        ("invalid_output_resilience", "Define invalid outputs as analyzable reliability evidence while preserving raw archives.", "invalid cell", "provider|pack_level|invalid_case_type", "invalid-output rates are descriptive until >=10 attempted cells"),
        ("single_session_to_multi_session_expansion", "Prevent one-session evidence from becoming generalized claims.", "session", "session_id|provider|pack_level", "single-session observations remain descriptive only"),
        ("readiness_for_accuracy_phase_gate", "Gate future accuracy analysis until behavior patterns are stable and governance remains clean.", "research gate", "pattern_status|governance_status", "accuracy phase remains blocked until stable behavior candidates exist"),
    ]
    return [
        _common_design_row(
            generated_ts,
            design_id,
            component,
            purpose,
            unit,
            dimensions,
            minimum,
            "Behavior before accuracy; pattern discovery before scoring.",
        )
        for component, purpose, unit, dimensions, minimum in components
    ]


def _metric(
    generated_ts: str,
    metric_id: str,
    name: str,
    family: str,
    description: str,
    source: str,
    rule: str,
    dimensions: str,
    minimum_rows: int,
    interpretation: str,
    non_interpretation: str,
    phase9a5_gate: str = "FALSE",
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "metric_id": metric_id,
        "metric_name": name,
        "metric_family": family,
        "metric_description": description,
        "calculation_source": source,
        "calculation_rule": rule,
        "allowed_grouping_dimensions": dimensions,
        "minimum_valid_rows": minimum_rows,
        "invalid_output_policy": "Exclude invalid/missing cells from valid numerator and denominator; count separately.",
        "interpretation": interpretation,
        "non_interpretation": non_interpretation,
        "accuracy_related": "FALSE",
        "ready_for_phase9a5_gate": phase9a5_gate,
        "notes": "Metric is diagnostic behavior evidence only, not an outcome score.",
    }


def _build_metric_rows(generated_ts: str) -> List[Dict[str, Any]]:
    specs = [
        ("behavior_change_rate", "Behavior Change Rate", "behavior_change", "Share of valid comparisons with any behavior_change_score > 0.", "Pack_Exposure_Behavior_Compare", "count(score>0)/valid comparison count", "provider|pack_transition|session_id", 5),
        ("direction_change_rate", "Direction Change Rate", "behavior_change", "Share of valid comparisons where forecast direction changed.", "Pack_Exposure_Behavior_Compare", "count(forecast_direction_changed=TRUE)/valid comparison count", "provider|pack_transition|session_id", 5),
        ("confidence_change_rate", "Confidence Change Rate", "confidence_behavior", "Share of valid comparisons with any confidence delta.", "Pack_Exposure_Behavior_Compare", "count(confidence_delta not blank and !=0)/valid comparison count", "provider|pack_transition|confidence_bucket", 5),
        ("material_confidence_change_rate", "Material Confidence Change Rate", "confidence_behavior", "Share of valid comparisons with absolute confidence delta >= 10.", "Pack_Exposure_Behavior_Compare", "count(abs(confidence_delta)>=10)/valid comparison count", "provider|pack_transition|confidence_bucket", 5),
        ("reasoning_change_rate", "Reasoning Change Rate", "reasoning_transition", "Share of transitions with a non-empty reasoning transition label other than no-change.", "Pack_Exposure_Reasoning_Transitions", "count(reasoning_transition_label not no-change)/valid transition count", "provider|pack_transition|session_id", 5),
        ("causal_chain_change_rate", "Causal Chain Change Rate", "causal_chain_behavior", "Share of valid transitions where causal_chain changed.", "Pack_Exposure_Reasoning_Transitions", "count(causal_chain_transition=CHANGED)/valid transition count", "provider|pack_transition|session_id", 5),
        ("no_signal_change_rate", "No-Signal Change Rate", "no_signal_behavior", "Share of valid transitions where normalized no-signal state changed.", "Pack_Exposure_Reasoning_Transitions", "count(no_signal_transition=CHANGED)/valid transition count", "provider|pack_transition|no_signal_state", 5),
        ("missing_information_reduction_rate", "Missing Information Reduction Rate", "behavior_change", "Share of comparisons where missing_information was reduced.", "Pack_Exposure_Behavior_Compare", "count(missing_information_reduced=TRUE)/valid comparison count", "provider|pack_transition|session_id", 5),
        ("mean_behavior_change_score", "Mean Behavior Change Score", "behavior_change", "Mean diagnostic behavior-change index.", "Pack_Exposure_Behavior_Compare", "mean(behavior_change_score) over valid comparisons", "provider|pack_transition|session_id", 5),
        ("mean_transition_complexity_score", "Mean Transition Complexity Score", "reasoning_transition", "Mean diagnostic reasoning-transition complexity.", "Pack_Exposure_Reasoning_Transitions", "mean(transition_complexity_score) over valid transitions", "provider|pack_transition|session_id", 5),
        ("max_transition_complexity_score", "Max Transition Complexity Score", "reasoning_transition", "Maximum observed reasoning-transition complexity.", "Pack_Exposure_Reasoning_Transitions", "max(transition_complexity_score) over valid transitions", "provider|pack_transition|session_id", 5),
        ("provider_pack_sensitivity_score", "Provider Pack Sensitivity Score", "provider_sensitivity", "Composite descriptive index of direction/confidence/reasoning/no-signal changes.", "Pack_Exposure_Provider_Transition_Audit", "weighted count of behavior dimensions changed per provider", "provider|pack_transition|session_id", 10),
        ("provider_no_signal_sensitivity_score", "Provider No-Signal Sensitivity Score", "provider_sensitivity", "Frequency of provider no-signal state changes under pack exposure.", "Pack_Exposure_Provider_Transition_Audit", "count(no_signal_changed=TRUE)/valid transitions", "provider|pack_transition|session_id", 10),
        ("provider_confidence_sensitivity_score", "Provider Confidence Sensitivity Score", "provider_sensitivity", "Average absolute confidence delta by provider and transition.", "Pack_Exposure_Provider_Transition_Audit", "mean(abs(confidence_delta)) over valid transitions", "provider|pack_transition|session_id", 10),
        ("provider_causal_chain_sensitivity_score", "Provider Causal Chain Sensitivity Score", "provider_sensitivity", "Frequency of causal-chain changes by provider.", "Pack_Exposure_Provider_Transition_Audit", "count(causal_chain_changed=TRUE)/valid transitions", "provider|pack_transition|session_id", 10),
        ("pack_transition_behavior_value_score", "Pack Transition Behavior Value Score", "pack_transition_value", "Composite behavior-movement score by transition.", "Pack_Exposure_Behavior_Compare", "mean behavior_change_score by transition", "pack_transition|provider|session_id", 10),
        ("pack_transition_redundancy_score", "Pack Transition Redundancy Score", "pack_redundancy", "Low incremental movement score used to flag possible redundancy.", "Pack_Exposure_Behavior_Compare", "1 - normalized mean behavior_change_score", "pack_transition|provider|session_id", 20),
        ("field_used_rate", "Field Used Rate", "field_influence", "Share of available field observations explicitly used.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_used=TRUE)/available field rows", "candidate_field|provider|pack_level", 10),
        ("field_discarded_rate", "Field Discarded Rate", "field_influence", "Share of available field observations explicitly discarded.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_discarded=TRUE)/available field rows", "candidate_field|provider|pack_level", 10),
        ("field_changed_reasoning_rate", "Field Changed Reasoning Rate", "field_influence", "Share of available field observations explicitly marked as changing reasoning.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_changed_reasoning=TRUE)/available field rows", "candidate_field|provider|pack_level", 10),
        ("field_no_effect_rate", "Field No Effect Rate", "field_influence", "Share of available field observations explicitly marked no-effect.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_no_effect=TRUE)/available field rows", "candidate_field|provider|pack_level", 10),
        ("field_family_used_rate", "Field Family Used Rate", "field_family_influence", "Family-level rollup of conservative field-used evidence.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_used=TRUE)/available rows by family", "candidate_family|provider|pack_level", 10),
        ("field_family_changed_reasoning_rate", "Field Family Changed Reasoning Rate", "field_family_influence", "Family-level rollup of field-changed-reasoning evidence.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_changed_reasoning=TRUE)/available rows by family", "candidate_family|provider|pack_level", 10),
        ("field_family_no_effect_rate", "Field Family No Effect Rate", "field_family_influence", "Family-level rollup of no-effect evidence.", "Pack_Exposure_Field_Influence_Audit", "count(field_reported_no_effect=TRUE)/available rows by family", "candidate_family|provider|pack_level", 10),
        ("invalid_output_rate", "Invalid Output Rate", "invalid_output_resilience", "Provider/pack invalid output frequency.", "Pack_Exposure_Invalid_Output_Audit", "invalid output count / attempted output count", "provider|pack_level|invalid_case_type", 10),
        ("partial_comparison_rate", "Partial Comparison Rate", "invalid_output_resilience", "Share of comparisons affected by invalid cells.", "Pack_Exposure_Behavior_Compare", "count(comparison_status contains invalid)/comparison count", "provider|pack_transition|session_id", 10),
        ("valid_transition_rate", "Valid Transition Rate", "invalid_output_resilience", "Share of transitions with valid from/to outputs.", "Pack_Exposure_Reasoning_Transitions", "count(transition_status=PASS)/transition count", "provider|pack_transition|session_id", 10),
    ]
    return [
        _metric(
            generated_ts,
            metric_id,
            name,
            family,
            desc,
            source,
            rule,
            dims,
            minimum,
            "Supports descriptive behavior-pattern evidence after sample thresholds are met.",
            "Does not measure correctness, accuracy, provider quality, or production fitness.",
        )
        for metric_id, name, family, desc, source, rule, dims, minimum in specs
    ]


def _grouping(
    generated_ts: str,
    rule_id: str,
    name: str,
    purpose: str,
    primary: str,
    secondary: str,
    metrics: str,
    minimum_sample: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "grouping_rule_id": rule_id,
        "grouping_name": name,
        "grouping_purpose": purpose,
        "primary_dimensions": primary,
        "secondary_dimensions": secondary,
        "allowed_metrics": metrics,
        "minimum_sample_size": minimum_sample,
        "minimum_provider_coverage": "At least 2 providers for cross-provider claims; 1 provider only for provider-specific descriptive claims.",
        "minimum_pack_coverage": "Pack A-E coverage required for full transition pattern claims; partial coverage must be labeled.",
        "invalid_output_policy": "Invalid outputs remain counted as invalid observations and excluded from valid transition denominators.",
        "interpretation_allowed": "Descriptive pattern labels only after threshold is met.",
        "interpretation_forbidden": "No accuracy, ranking, calibration, routing, weighting, or production claims.",
        "notes": "Thresholds are provisional design assumptions: descriptive_only n<5; weak_pattern n>=5 across >=2 sessions; candidate_pattern n>=10 across >=3 sessions; stable_pattern_candidate n>=20 across >=5 sessions.",
    }


def _build_grouping_rows(generated_ts: str) -> List[Dict[str, Any]]:
    metrics_all = "behavior_change_rate|reasoning_change_rate|no_signal_change_rate|field_used_rate|invalid_output_rate"
    specs = [
        ("grp_provider", "by_provider", "Profile each provider's sensitivity to controlled pack exposure.", "provider", "pack_transition|session_id", metrics_all, "descriptive_only n<5; candidate_pattern n>=10 valid transitions"),
        ("grp_pack_transition", "by_pack_transition", "Identify pack transitions with repeated behavior movement.", "pack_transition", "provider|session_id", metrics_all, "weak_pattern n>=5 valid transitions across >=2 sessions"),
        ("grp_provider_pack_transition", "by_provider_and_pack_transition", "Find provider-specific transition signatures.", "provider|pack_transition", "session_id", metrics_all, "candidate_pattern n>=10 valid transitions across >=3 sessions"),
        ("grp_pack_level", "by_pack_level", "Compare behavior states by pack level without choosing winners.", "pack_level", "provider|session_id", "field_used_rate|confidence_change_rate|invalid_output_rate", "candidate_pattern n>=10 observations"),
        ("grp_field", "by_field", "Track field-level usage, discard, no-effect, and changed-reasoning recurrence.", "candidate_field", "provider|pack_level|session_id", "field_used_rate|field_discarded_rate|field_changed_reasoning_rate|field_no_effect_rate", "candidate_pattern n>=10 field observations"),
        ("grp_field_family", "by_field_family", "Roll up conservative field observations into family-level behavior.", "candidate_family", "provider|pack_level|session_id", "field_family_used_rate|field_family_changed_reasoning_rate|field_family_no_effect_rate", "candidate_pattern n>=10 family observations"),
        ("grp_session", "by_session", "Keep session-level context visible and avoid premature generalization.", "session_id", "provider|pack_level|pack_transition", metrics_all, "single-session observations descriptive only"),
        ("grp_event_family", "by_event_family", "Later associate behavior patterns with event families when session metadata supports it.", "event_family", "session_id|provider|pack_transition", "behavior_change_rate|reasoning_change_rate", "candidate_pattern n>=10 transitions with event-family metadata"),
        ("grp_market_session_type", "by_market_session_type", "Later compare behavior across session types without production implications.", "market_session_type", "provider|pack_transition", "behavior_change_rate|no_signal_change_rate", "candidate_pattern n>=10 transitions"),
        ("grp_no_signal_state", "by_no_signal_state", "Track transitions into or out of no-signal states.", "no_signal_state", "provider|pack_transition|session_id", "no_signal_change_rate|provider_no_signal_sensitivity_score", "candidate_pattern n>=10 no-signal observations"),
        ("grp_confidence_bucket", "by_confidence_bucket", "Track confidence behavior without treating confidence as correctness.", "confidence_bucket", "provider|pack_transition|session_id", "confidence_change_rate|material_confidence_change_rate", "candidate_pattern n>=10 confidence observations"),
        ("grp_validity_status", "by_validity_status", "Track invalid and partial outputs as reliability evidence.", "validity_status", "provider|pack_level|invalid_case_type", "invalid_output_rate|partial_comparison_rate|valid_transition_rate", "descriptive at any n; pattern claims require >=10 attempted cells"),
    ]
    return [_grouping(generated_ts, *spec) for spec in specs]


def _invalid_rule(
    generated_ts: str,
    rule_id: str,
    case_type: str,
    example: str,
    affected: str,
    handling: str,
    valid: str,
    invalid: str,
    partial: str,
    label: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "invalid_rule_id": rule_id,
        "invalid_case_type": case_type,
        "example": example,
        "affected_tables": affected,
        "handling_rule": handling,
        "count_as_valid_observation": valid,
        "count_as_invalid_observation": invalid,
        "count_as_partial_comparison": partial,
        "allow_imputation": "FALSE",
        "allow_provider_rerun": "FALSE",
        "allow_accuracy_evaluation": "FALSE",
        "recommended_label": label,
        "notes": "If future execution reruns a provider, it must create a new run_id and never silently replace the original observation.",
    }


def _build_invalid_rows(generated_ts: str) -> List[Dict[str, Any]]:
    affected = "Pack_Exposure_Raw_Response_Archive|Pack_Exposure_Forecasts|Pack_Exposure_Behavior_Compare|Pack_Exposure_Reasoning_Transitions"
    specs = [
        ("invalid_malformed_json", "malformed_json", "Anthropic Pack D malformed/truncated JSON from Phase 9A-2 pilot.", affected, "Preserve raw response; mark output invalid; do not infer missing behavior fields.", "FALSE", "TRUE", "TRUE", "TREAT_AS_INVALID_CELL"),
        ("invalid_truncated_json", "truncated_json", "Provider response ends before valid JSON object closes.", affected, "Preserve raw response; classify as truncated; exclude from valid transition denominators.", "FALSE", "TRUE", "TRUE", "TREAT_AS_INVALID_CELL"),
        ("invalid_schema_validation_failure", "schema_validation_failure", "JSON parses but required behavior fields or allowed values fail schema.", affected, "Preserve parsed/raw data; mark schema invalid; do not coerce into valid output.", "FALSE", "TRUE", "TRUE", "SCHEMA_INVALID_CELL"),
        ("invalid_missing_provider_response", "missing_provider_response", "No provider response returned for a scheduled provider/pack cell.", affected, "Record missing cell; do not impute or rerun inside analysis phase.", "FALSE", "TRUE", "TRUE", "MISSING_PROVIDER_RESPONSE"),
        ("invalid_timeout", "timeout", "Provider call timeout in future execution phase.", affected, "Record timeout as invalid execution observation; raw archive may contain error only.", "FALSE", "TRUE", "TRUE", "PROVIDER_TIMEOUT"),
        ("invalid_empty_response", "empty_response", "Provider returns blank content.", affected, "Archive blank response metadata; mark invalid.", "FALSE", "TRUE", "TRUE", "EMPTY_PROVIDER_RESPONSE"),
        ("invalid_partial_pack_output", "partial_pack_output", "Response contains forecast fields but omits behavior fields.", affected, "Use available validated fields only if schema permits; otherwise mark partial invalid.", "FALSE", "TRUE", "TRUE", "PARTIAL_PACK_OUTPUT"),
        ("invalid_missing_behavior_fields", "missing_behavior_fields", "Forecast direction present but causal_chain or pack field usage missing.", affected, "Mark behavior component invalid for behavior-pattern metrics; do not fill from prose.", "FALSE", "TRUE", "TRUE", "MISSING_BEHAVIOR_FIELDS"),
        ("invalid_pack_level", "invalid_pack_level", "Output references Pack Q or unknown pack level during A-E experiment.", affected, "Exclude from controlled A-E analysis and flag governance review.", "FALSE", "TRUE", "TRUE", "INVALID_PACK_LEVEL"),
        ("invalid_provider", "invalid_provider", "Output provider not in approved provider set for run.", affected, "Exclude from controlled provider analysis and flag execution issue.", "FALSE", "TRUE", "TRUE", "INVALID_PROVIDER"),
        ("invalid_raw_response_missing", "raw_response_missing", "Parsed output exists but raw response archive is missing.", affected, "Block source-of-truth-dependent analysis for that cell.", "FALSE", "TRUE", "TRUE", "RAW_RESPONSE_MISSING"),
    ]
    return [_invalid_rule(generated_ts, *spec) for spec in specs]


def _readiness_row(
    generated_ts: str,
    check_id: str,
    area: str,
    description: str,
    status: str,
    sheet: str,
    value: Any,
    blocking: bool,
    action: str,
    notes: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "readiness_check_id": check_id,
        "readiness_area": area,
        "check_description": description,
        "check_status": status,
        "evidence_sheet": sheet,
        "evidence_value": value,
        "blocking": _bool_text(blocking),
        "recommended_action": action,
        "notes": notes,
    }


def _build_readiness_rows(
    generated_ts: str,
    titles: Set[str],
    summary: Dict[str, Any],
    compare_rows: Sequence[Dict[str, Any]],
    reasoning_rows: Sequence[Dict[str, Any]],
    field_rows: Sequence[Dict[str, Any]],
    invalid_rows: Sequence[Dict[str, Any]],
    raw_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    missing_outputs = [sheet for sheet in PHASE9A_OUTPUT_SHEETS if sheet not in titles]
    repair_confirmed = _norm(summary.get("final_interpretation")) == "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY_WITH_WARNINGS"
    no_signal_summary = _as_int(summary.get("no_signal_change_count"))
    no_signal_compare = sum(1 for row in compare_rows if _upper(row.get("no_signal_changed")) == "TRUE")
    no_signal_transition = sum(1 for row in reasoning_rows if _norm(row.get("no_signal_transition")) == "CHANGED")
    invalid_isolated = bool(invalid_rows) and all(_upper(row.get("repair_attempted")) == "FALSE" and _upper(row.get("provider_rerun_attempted")) == "FALSE" for row in invalid_rows)
    safety_clean = all(
        _as_int(summary.get(key)) == 0
        for key in [
            "accuracy_evaluation_count",
            "provider_call_count",
            "forecast_generation_count",
            "production_behavior_change_count",
        ]
    )
    return [
        _readiness_row(generated_ts, "ready_phase9a3_outputs_exist", "phase9a3_outputs_exist", "All repaired Phase 9A-3 output sheets exist.", "PASS" if not missing_outputs else "BLOCKED", "Sheet titles", _sheet_list(missing_outputs) if missing_outputs else "all_present", bool(missing_outputs), "Create missing output sheets before execution design.", "Required for design and later execution."),
        _readiness_row(generated_ts, "ready_phase9a3r_repair_confirmed", "phase9a3r_repair_confirmed", "Phase 9A-3R final interpretation confirms repair-ready state.", "PASS" if repair_confirmed else "NEEDS_REVIEW", "Pack_Exposure_Behavior_Compare_Summary", summary.get("final_interpretation", ""), not repair_confirmed, "Review repair output if not confirmed.", "Repair confirmation is required before multi-session design execution."),
        _readiness_row(generated_ts, "ready_no_signal_normalization_consistent", "no_signal_normalization_consistent", "Summary no-signal count matches comparison and transition rows.", "PASS" if no_signal_summary == no_signal_compare == no_signal_transition else "BLOCKED", "Pack_Exposure_Behavior_Compare|Pack_Exposure_Reasoning_Transitions", f"summary={no_signal_summary};compare={no_signal_compare};transition={no_signal_transition}", not (no_signal_summary == no_signal_compare == no_signal_transition), "Repair no-signal normalization before execution.", "This was the Phase 9A-3R repair target."),
        _readiness_row(generated_ts, "ready_invalid_output_isolated", "invalid_output_isolated", "Invalid outputs are explicit and not repaired or rerun.", "PASS_WITH_WARNINGS" if invalid_isolated else "BLOCKED", "Pack_Exposure_Invalid_Output_Audit", len(invalid_rows), not invalid_isolated, "Keep invalid outputs as missingness; do not infer.", "Warnings remain because one invalid Anthropic Pack D cell exists."),
        _readiness_row(generated_ts, "ready_raw_response_archive_available", "raw_response_archive_available", "Raw provider response archive is available as source of truth.", "PASS" if raw_rows else "BLOCKED", "Pack_Exposure_Raw_Response_Archive", len(raw_rows), not bool(raw_rows), "Require raw archive before pattern discovery.", "Raw archives support future parser repair without overwriting evidence."),
        _readiness_row(generated_ts, "ready_field_influence_available", "field_influence_available", "Field influence rows exist for future recurrence analysis.", "PASS" if field_rows else "BLOCKED", "Pack_Exposure_Field_Influence_Audit", len(field_rows), not bool(field_rows), "Rebuild field influence audit if missing.", "Field influence must remain conservative."),
        _readiness_row(generated_ts, "ready_reasoning_transition_available", "reasoning_transition_available", "Reasoning transition rows exist for future stability analysis.", "PASS" if reasoning_rows else "BLOCKED", "Pack_Exposure_Reasoning_Transitions", len(reasoning_rows), not bool(reasoning_rows), "Rebuild reasoning transitions if missing.", "Reasoning transition is the core Phase 9A-4 input."),
        _readiness_row(generated_ts, "ready_summary_counters_consistent", "summary_counters_consistent", "Summary row counts align with detail table counts.", "PASS" if _as_int(summary.get("comparison_rows_written")) == len(compare_rows) and _as_int(summary.get("reasoning_transition_rows_written")) == len(reasoning_rows) else "NEEDS_REVIEW", "Pack_Exposure_Behavior_Compare_Summary", f"compare={len(compare_rows)};reasoning={len(reasoning_rows)}", False, "Review counts if detail rows diverge.", "Non-blocking unless row counts are missing."),
        _readiness_row(generated_ts, "ready_accuracy_excluded", "accuracy_excluded", "No accuracy evaluation was performed.", "PASS" if _as_int(summary.get("accuracy_evaluation_count")) == 0 else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", summary.get("accuracy_evaluation_count", ""), _as_int(summary.get("accuracy_evaluation_count")) != 0, "Hold Phase 9 if accuracy was introduced.", "Behavior before accuracy."),
        _readiness_row(generated_ts, "ready_provider_calls_excluded", "provider_calls_excluded", "No provider calls occurred during design/repair analysis.", "PASS" if _as_int(summary.get("provider_call_count")) == 0 else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", summary.get("provider_call_count", ""), _as_int(summary.get("provider_call_count")) != 0, "Hold if provider calls occurred unexpectedly.", "No reruns in analysis phases."),
        _readiness_row(generated_ts, "ready_production_changes_excluded", "production_changes_excluded", "No production behavior changes occurred.", "PASS" if safety_clean else "BLOCKED", "Pack_Exposure_Behavior_Compare_Summary", "safety_counters_zero" if safety_clean else "safety_counter_nonzero", not safety_clean, "Hold for governance review if any safety counter is nonzero.", "Shadow-only governance."),
        _readiness_row(generated_ts, "ready_minimum_evidence_for_design", "minimum_evidence_for_design", "Current pilot evidence is enough to design multi-session pattern discovery.", "PASS" if compare_rows and reasoning_rows else "BLOCKED", "Pack_Exposure_Behavior_Compare", len(compare_rows), not bool(compare_rows and reasoning_rows), "Need one valid pilot before design.", "Ready for design does not imply generalization."),
        _readiness_row(generated_ts, "ready_minimum_evidence_for_execution", "minimum_evidence_for_execution", "Single session is insufficient for pattern claims but sufficient to plan execution.", "PASS_WITH_WARNINGS", "Pack_Exposure_Behavior_Compare_Summary", "session_count_current=1", False, "Proceed to execution planning with sample thresholds.", "Ready for design does not mean ready for accuracy evaluation or production."),
    ]


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_PATTERN_DISCOVERY_DESIGN", OUTPUT_DESIGN_SHEET, "behavior_pattern_discovery_design"),
        ("PACK_BEHAVIOR_PATTERN_METRICS_DEFINITION", OUTPUT_METRICS_SHEET, "behavior_pattern_metrics_definition"),
        ("PACK_BEHAVIOR_PATTERN_GROUPING_RULES", OUTPUT_GROUPING_SHEET, "behavior_pattern_grouping_rules"),
        ("PACK_BEHAVIOR_PATTERN_INVALID_OUTPUT_RULES", OUTPUT_INVALID_RULES_SHEET, "behavior_pattern_invalid_output_rules"),
        ("PACK_BEHAVIOR_PATTERN_READINESS_AUDIT", OUTPUT_READINESS_SHEET, "behavior_pattern_readiness_audit"),
        ("PACK_BEHAVIOR_PATTERN_DISCOVERY_SUMMARY", OUTPUT_SUMMARY_SHEET, "behavior_pattern_discovery_summary"),
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
            "notes": "Phase 9A-4 design only; no provider calls, forecasts, accuracy evaluation, or production behavior changes.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-4 behavior pattern discovery design.")
    return parser.parse_args(argv)


def build_pack_behavior_pattern_discovery_design_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    design_id = _run_id(generated_ts)
    creds = load_credentials()
    service = build_sheets_service(creds)
    titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_required: List[str] = []
    missing_optional: List[str] = []

    for sheet in PHASE9A_OUTPUT_SHEETS + PHASE9A2_SOURCE_SHEETS + PACK_DESIGN_SHEETS:
        if sheet not in titles:
            missing_required.append(sheet)
    for sheet in OPTIONAL_SHEETS:
        if sheet not in titles:
            missing_optional.append(sheet)

    summary_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Behavior_Compare_Summary", missing_required)
    compare_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Behavior_Compare", missing_required)
    reasoning_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Reasoning_Transitions", missing_required)
    field_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Field_Influence_Audit", missing_required)
    invalid_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Invalid_Output_Audit", missing_required)
    raw_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Raw_Response_Archive", missing_required)
    forecast_rows = _read_rows_if_exists(service, titles, "Pack_Exposure_Forecasts", missing_required)
    latest_summary = _latest(summary_rows)

    design_rows = _build_design_rows(generated_ts, design_id)
    metric_rows = _build_metric_rows(generated_ts)
    grouping_rows = _build_grouping_rows(generated_ts)
    invalid_rule_rows = _build_invalid_rows(generated_ts)
    readiness_rows = _build_readiness_rows(
        generated_ts,
        titles,
        latest_summary,
        compare_rows,
        reasoning_rows,
        field_rows,
        invalid_rows,
        raw_rows,
    )

    blocking_checks = [row for row in readiness_rows if _upper(row.get("blocking")) == "TRUE"]
    warning_checks = [row for row in readiness_rows if _upper(row.get("check_status")) == "PASS_WITH_WARNINGS"]
    safety = {
        "accuracy_evaluation_count": 0,
        "provider_call_count": 0,
        "forecast_generation_count": 0,
        "production_behavior_change_count": 0,
    }
    safety_clean = all(_as_int(latest_summary.get(key)) == 0 for key in safety)
    repair_confirmed = _norm(latest_summary.get("final_interpretation")) == "PACK_EXPOSURE_BEHAVIOR_COMPARE_REPAIR_READY_WITH_WARNINGS"
    session_ids = {row.get("session_id") for row in compare_rows if _norm(row.get("session_id"))}
    providers = {row.get("provider") for row in forecast_rows if _norm(row.get("provider"))}
    pack_levels = {row.get("pack_level") for row in forecast_rows if _norm(row.get("pack_level"))}
    behavior_signal = _behavior_signal(latest_summary)
    ready_for_execution = not blocking_checks and repair_confirmed and safety_clean and bool(compare_rows and reasoning_rows)

    if not safety_clean or blocking_checks:
        build_status = "FAIL"
        interpretation = "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_BLOCKED"
        recommended_next = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
    elif warning_checks or missing_optional or _as_int(latest_summary.get("invalid_outputs_count")) > 0 or len(session_ids) < 2:
        build_status = "PASS_WITH_WARNINGS"
        interpretation = "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY_WITH_WARNINGS"
        recommended_next = "PROCEED_TO_PHASE9A4_EXECUTION_PLAN"
    else:
        build_status = "PASS"
        interpretation = "BEHAVIOR_PATTERN_DISCOVERY_DESIGN_READY"
        recommended_next = "PROCEED_TO_PHASE9A4_EXECUTION_PLAN"

    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "build_status": build_status,
        "final_interpretation": interpretation,
        "design_components_defined": len(design_rows),
        "metrics_defined": len(metric_rows),
        "grouping_rules_defined": len(grouping_rows),
        "invalid_output_rules_defined": len(invalid_rule_rows),
        "readiness_checks_defined": len(readiness_rows),
        "phase9a3_build_status": latest_summary.get("build_status", ""),
        "phase9a3_final_interpretation": latest_summary.get("final_interpretation", ""),
        "phase9a3r_repair_confirmed": _bool_text(repair_confirmed),
        "session_count_current": len(session_ids) or (1 if _norm(latest_summary.get("session_id")) else 0),
        "provider_count_current": len(providers) or _as_int(latest_summary.get("providers_analyzed")),
        "pack_level_count_current": len(pack_levels) or _as_int(latest_summary.get("pack_levels_analyzed")),
        "valid_outputs_current": latest_summary.get("valid_outputs_count", ""),
        "invalid_outputs_current": latest_summary.get("invalid_outputs_count", ""),
        "behavior_signal_classification_current": behavior_signal,
        "single_session_generalization_allowed": "FALSE",
        **safety,
        "ready_for_phase9a4_execution_design": _bool_text(ready_for_execution),
        "ready_for_phase9a5_accuracy_evaluation": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next,
        "notes": _truncate_text(
            json.dumps(
                {
                    "missing_required": sorted(set(missing_required)),
                    "missing_optional": sorted(set(missing_optional)),
                    "invalid_outputs_current": latest_summary.get("invalid_outputs_count", ""),
                    "single_session_generalization": "blocked_by_design",
                    "design_principle": "Behavior before accuracy; pattern discovery before scoring.",
                },
                ensure_ascii=True,
            ),
            500,
        ),
    }

    for sheet, headers, rows in [
        (OUTPUT_DESIGN_SHEET, DESIGN_HEADERS, design_rows),
        (OUTPUT_METRICS_SHEET, METRIC_HEADERS, metric_rows),
        (OUTPUT_GROUPING_SHEET, GROUPING_HEADERS, grouping_rows),
        (OUTPUT_INVALID_RULES_SHEET, INVALID_RULE_HEADERS, invalid_rule_rows),
        (OUTPUT_READINESS_SHEET, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": interpretation,
        "file_created": "automation/build_pack_behavior_pattern_discovery_design_v0.py",
        "sheets_written": {
            OUTPUT_DESIGN_SHEET: len(design_rows),
            OUTPUT_METRICS_SHEET: len(metric_rows),
            OUTPUT_GROUPING_SHEET: len(grouping_rows),
            OUTPUT_INVALID_RULES_SHEET: len(invalid_rule_rows),
            OUTPUT_READINESS_SHEET: len(readiness_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "design_components_defined": len(design_rows),
        "metrics_defined": len(metric_rows),
        "grouping_rules_defined": len(grouping_rows),
        "invalid_output_rules_defined": len(invalid_rule_rows),
        "readiness_checks_defined": len(readiness_rows),
        "phase9a3r_repair_confirmed": summary["phase9a3r_repair_confirmed"],
        "behavior_signal_classification_current": behavior_signal,
        "single_session_generalization_allowed": summary["single_session_generalization_allowed"],
        "ready_for_phase9a4_execution_design": summary["ready_for_phase9a4_execution_design"],
        "ready_for_phase9a5_accuracy_evaluation": summary["ready_for_phase9a5_accuracy_evaluation"],
        "ready_for_production": summary["ready_for_production"],
        "accuracy_evaluation_count": summary["accuracy_evaluation_count"],
        "provider_call_count": summary["provider_call_count"],
        "forecast_generation_count": summary["forecast_generation_count"],
        "production_behavior_change_count": summary["production_behavior_change_count"],
        "recommended_next_step": recommended_next,
        "registry": registry,
        "missing_required": sorted(set(missing_required)),
        "missing_optional": sorted(set(missing_optional)),
    }


def main() -> None:
    result = build_pack_behavior_pattern_discovery_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
