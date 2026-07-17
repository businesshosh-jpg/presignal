import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_label_metric_design_0.1"
DESIGN_VERSION = "predictive_mechanism_label_metric_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6B"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_LABEL_METRIC_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Design",
    "Predictive_Mechanism_Framework",
    "Predictive_Mechanism_Hypotheses",
    "Predictive_Mechanism_Test_Framework",
    "Predictive_Mechanism_Observables",
    "Predictive_Mechanism_Evidence_Model",
    "Predictive_Mechanism_Experiment_Map",
    "Predictive_Mechanism_Data_Requirements",
    "Predictive_Mechanism_Priority",
    "Predictive_Mechanism_Test_Plan",
    "Predictive_Mechanism_Label_Definitions",
    "Predictive_Mechanism_Control_Definition",
    "Predictive_Mechanism_Metric_Definition",
    "Predictive_Mechanism_Falsification_Rules",
    "Predictive_Mechanism_PreRegistration",
    "Predictive_Mechanism_Test_Readiness",
]

OUTPUT_LABEL_MODEL = "Predictive_Mechanism_Label_Model"
OUTPUT_LABEL_ASSIGNMENT = "Predictive_Mechanism_Label_Assignment"
OUTPUT_METRIC_MODEL = "Predictive_Mechanism_Metric_Model"
OUTPUT_CONFIDENCE = "Predictive_Mechanism_Confidence_Framework"
OUTPUT_CONFLICT = "Predictive_Mechanism_Label_Conflict_Rules"
OUTPUT_AUDIT = "Predictive_Mechanism_Audit_Framework"
OUTPUT_READINESS = "Predictive_Mechanism_Label_Readiness"
OUTPUT_SUMMARY = "Predictive_Mechanism_Label_Metric_Summary"

LABEL_MODEL_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "label_name",
    "observable_inputs",
    "required_behavior_evidence",
    "required_context",
    "minimum_evidence",
    "insufficient_evidence_rule",
    "exclusion_rule",
    "unknown_rule",
    "outcome_independence_rule",
    "notes",
]

LABEL_ASSIGNMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "positive_assignment_rule",
    "negative_assignment_rule",
    "unknown_assignment_rule",
    "insufficient_evidence_assignment_rule",
    "conflict_resolution_rule",
    "tie_breaking_rule",
    "auditability_requirement",
    "deterministic_assignment_status",
    "notes",
]

METRIC_MODEL_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "primary_mechanism_metric",
    "linked_frozen_test_metric",
    "secondary_metrics",
    "supporting_indicators",
    "numerator_definition",
    "denominator_definition",
    "interpretation_scale",
    "expected_range",
    "notes",
]

CONFIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "label_confidence_source",
    "evidence_completeness",
    "evidence_consistency",
    "ambiguity_level",
    "confidence_category",
    "confidence_assignment_rule",
    "notes",
]

CONFLICT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "conflicting_observables",
    "conflicting_mechanism_evidence",
    "conflicting_labels",
    "precedence_hierarchy",
    "unresolved_conflict_handling",
    "manual_interpretation_required",
    "notes",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "audit_checkpoints",
    "traceability_requirements",
    "reproducibility_requirements",
    "label_review_trigger",
    "metric_review_trigger",
    "governance_trigger",
    "audit_ready",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "label_ready",
    "metric_ready",
    "audit_ready",
    "classification_ready",
    "readiness_status",
    "readiness_reason",
    "blocking_issue",
    "recommended_next_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "build_status",
    "final_interpretation",
    "mechanism_label_models_designed",
    "assignment_rules_defined",
    "metric_models_defined",
    "confidence_framework_defined",
    "conflict_rules_defined",
    "audit_framework_defined",
    "highest_priority_mechanism",
    "highest_label_ambiguity",
    "highest_metric_risk",
    "provider_calls_performed",
    "forecast_generation_performed",
    "evaluation_rerun_count",
    "production_behavior_change_count",
    "ready_for_mechanism_classification",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

MECHANISM_ORDER = [
    "MECH_INFORMATION_VALUE",
    "MECH_SIGNAL_DISCIPLINE",
    "MECH_CONDITIONAL_PREDICTIVENESS",
    "MECH_INFORMATION_FILTERING",
    "MECH_FORECAST_STABILITY",
    "MECH_CAUSAL_ROBUSTNESS",
]

EXPECTED_LABELS = {
    "mechanism_positive",
    "mechanism_negative",
    "mechanism_unknown",
    "insufficient_evidence",
    "excluded_case",
}

COMMON_OUTCOME_RULE = (
    "Mechanism labels and label-support metrics must be assigned from pre-outcome behavior, "
    "market-state, context-pack, and schema-valid trace fields only. Realized direction, "
    "realized pips, overall_ok, corrected outcomes, evaluation results, and hindsight "
    "interpretation are forbidden."
)

COMMON_PRECEDENCE = (
    "excluded_case > insufficient_evidence > mechanism_negative when a direct contradiction "
    "exists > mechanism_positive when minimum evidence is satisfied without contradiction > "
    "mechanism_unknown"
)

COMMON_AUDIT = (
    "record rule version; source sheet names; source row ids or prediction keys; boolean state "
    "for every observable check; applied conflict rule; final label; final confidence category"
)

MECH_RULES = {
    "MECH_INFORMATION_VALUE": {
        "label_name": "information_value_operational_label",
        "observable_inputs": (
            "feature exposure trace; field-influence signal; reasoning delta vs matched baseline; "
            "explicit feature citation; irrelevant-reference penalty"
        ),
        "required_context": (
            "matched baseline or paired comparison row; same session/event family context; "
            "feature-exposed row with stable pre-outcome pack identity"
        ),
        "minimum_evidence": (
            "explicit feature citation + reasoning delta present + matched baseline availability"
        ),
        "positive_rule": (
            "Assign mechanism_positive when the new feature is explicitly cited, changes the "
            "causal explanation relative to baseline, and no irrelevant-reference penalty is active."
        ),
        "negative_rule": (
            "Assign mechanism_negative when feature exposure exists but the feature is not cited, "
            "does not change reasoning, or the added feature only expands irrelevant reasoning."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when feature citation and reasoning delta disagree or when "
            "baseline context exists but the incremental role of the feature remains mixed."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when matched baseline, field-influence trace, or "
            "reasoning delta trace is missing."
        ),
        "conflicts": (
            "feature cited but reasoning delta absent; reasoning delta present but no matched "
            "baseline; feature cited while irrelevant-reference penalty is active"
        ),
        "tie_break": (
            "If positive and negative evidence counts tie after precedence, downgrade to "
            "mechanism_unknown with LOW confidence."
        ),
        "primary_metric": "information_value_evidence_score",
        "secondary_metrics": "feature_citation_specificity_rate; reasoning_delta_rate",
        "supporting_indicators": (
            "baseline_available_flag; field_influence_present_flag; irrelevant_reference_penalty"
        ),
        "numerator": (
            "eligible feature-exposed rows satisfying the full minimum-evidence bundle without "
            "contradiction"
        ),
        "denominator": "all label-eligible feature-exposed rows with matched baseline context",
        "scale": "0.00-1.00, where higher means stronger evidence that new information adds value",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of feature-exposure trace, reasoning delta trace, and matched baseline trace"
        ),
        "ambiguity": "HIGH when feature citation is present but incremental role cannot be isolated",
        "label_review_trigger": (
            "unknown or insufficient_evidence exceeds 20% of eligible rows or baseline-match "
            "availability drops below pre-registered minimum"
        ),
        "metric_review_trigger": (
            "information_value_evidence_score collapses around the midpoint because reasoning-delta "
            "instrumentation is too coarse"
        ),
        "metric_risk": "HIGH",
    },
    "MECH_SIGNAL_DISCIPLINE": {
        "label_name": "signal_discipline_operational_label",
        "observable_inputs": (
            "low-signal context flag; no-signal declaration; unsupported-direction avoidance trace; "
            "confidence moderation trace; evidence-scarcity flag"
        ),
        "required_context": (
            "pre-registered low-signal session or family slice; valid prompt/pack identity; "
            "directional-output eligibility state"
        ),
        "minimum_evidence": (
            "low-signal context present + unsupported-direction avoidance or explicit no-signal + "
            "confidence aligned with sparse evidence"
        ),
        "positive_rule": (
            "Assign mechanism_positive when the row is low-signal, directional overreach is avoided, "
            "and confidence is reduced or no-signal is explicitly chosen."
        ),
        "negative_rule": (
            "Assign mechanism_negative when low-signal context is present but the row still emits "
            "unsupported directional conviction or inflated confidence."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when low-signal context is only partially established or when "
            "confidence moderation and directional restraint disagree."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when low-signal markers, no-signal trace, or confidence "
            "trace is missing."
        ),
        "conflicts": (
            "no-signal flag set but aggressive directional wording remains; low-signal context absent "
            "while unsupported-direction avoidance is claimed"
        ),
        "tie_break": (
            "If low-signal evidence and unsupported-direction evidence conflict symmetrically, "
            "downgrade to mechanism_unknown rather than forcing positive classification."
        ),
        "primary_metric": "signal_discipline_evidence_score",
        "secondary_metrics": "unsupported_direction_avoidance_rate; low_confidence_alignment_rate",
        "supporting_indicators": "no_signal_flag; evidence_scarcity_flag; confidence_reduction_flag",
        "numerator": (
            "eligible low-signal rows that avoid unsupported direction and align confidence with "
            "weak pre-outcome evidence"
        ),
        "denominator": "all label-eligible low-signal rows",
        "scale": "0.00-1.00, where higher means stronger pre-outcome signal-discipline evidence",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of low-signal markers, confidence trace, and no-signal or restraint trace"
        ),
        "ambiguity": "MEDIUM when low-signal context is clear but confidence and direction restraint diverge",
        "label_review_trigger": (
            "negative labels exceed positive labels in rows that supposedly show restraint or "
            "confidence moderation fields are missing in more than 15% of eligible rows"
        ),
        "metric_review_trigger": (
            "signal_discipline_evidence_score cannot separate explicit no-signal from weak but still "
            "supported directional rows"
        ),
        "metric_risk": "HIGHEST",
    },
    "MECH_CONDITIONAL_PREDICTIVENESS": {
        "label_name": "conditional_predictiveness_operational_label",
        "observable_inputs": (
            "pre-registered regime marker; feature-usage gate; outside-regime suppression trace; "
            "context-slice membership"
        ),
        "required_context": (
            "deterministic regime slice assigned before outcome review; stable event family/session "
            "linkage; feature availability trace"
        ),
        "minimum_evidence": (
            "regime marker present + feature usage explicitly gated to the regime + outside-regime "
            "suppression or non-application documented"
        ),
        "positive_rule": (
            "Assign mechanism_positive when the feature is used only inside a pre-registered regime "
            "slice and is explicitly withheld outside that slice."
        ),
        "negative_rule": (
            "Assign mechanism_negative when the feature is applied regardless of regime or when a "
            "claimed regime marker does not change feature use."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when regime membership is partial, overlapping, or insufficient "
            "to determine whether feature use is truly conditional."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when regime markers or regime-gating traces are missing."
        ),
        "conflicts": (
            "regime marker present but feature use not gated; feature gated but regime slice not "
            "deterministically assigned"
        ),
        "tie_break": (
            "If multiple regime cues point to different slices, prefer insufficient_evidence when the "
            "slice cannot be frozen deterministically; otherwise fall back to mechanism_unknown."
        ),
        "primary_metric": "conditional_predictiveness_evidence_score",
        "secondary_metrics": "regime_gate_explicit_rate; outside_regime_suppression_rate",
        "supporting_indicators": "regime_marker_flag; slice_overlap_flag; feature_gate_present_flag",
        "numerator": (
            "eligible rows where regime membership and feature gating are both explicit and "
            "consistent"
        ),
        "denominator": "all label-eligible rows in pre-registered regime slices",
        "scale": "0.00-1.00, where higher means clearer regime-conditioned mechanism evidence",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of regime markers, slice membership trace, and feature gating trace"
        ),
        "ambiguity": "MEDIUM when regime slices overlap or when gating is explicit in only one branch",
        "label_review_trigger": (
            "regime overlap or unknown labels exceed 15% of slice-eligible rows"
        ),
        "metric_review_trigger": (
            "conditional_predictiveness_evidence_score depends on regime tags that are too coarse to "
            "separate pre-registered slices"
        ),
        "metric_risk": "MEDIUM",
    },
    "MECH_INFORMATION_FILTERING": {
        "label_name": "information_filtering_operational_label",
        "observable_inputs": (
            "irrelevant-reference count; retained-signal count; causal simplification trace; "
            "noise-penalty flag; added-information exposure"
        ),
        "required_context": (
            "row exposed to additional information; pre-outcome relevance taxonomy frozen; stable "
            "event family or context-pack identity"
        ),
        "minimum_evidence": (
            "added information present + irrelevant references decline or remain suppressed + "
            "retained-signal set remains focused"
        ),
        "positive_rule": (
            "Assign mechanism_positive when added information narrows the active evidence set and "
            "does not introduce extra causal noise."
        ),
        "negative_rule": (
            "Assign mechanism_negative when added information increases irrelevant references, "
            "expands causal noise, or dilutes the active signal set."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when relevant and irrelevant reference signals move in opposite "
            "directions or when filtering cannot be separated from generic verbosity."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when reference counts, relevance tags, or simplification "
            "trace is missing."
        ),
        "conflicts": (
            "irrelevant references decline while causal noise rises; additional information cited but "
            "no selective-filtering evidence appears"
        ),
        "tie_break": (
            "If relevance and noise indicators split evenly, prefer mechanism_unknown unless the "
            "noise penalty is direct, in which case mechanism_negative wins."
        ),
        "primary_metric": "information_filtering_evidence_score",
        "secondary_metrics": "relevance_retention_rate; irrelevant_reference_suppression_rate",
        "supporting_indicators": "causal_noise_penalty; retained_signal_focus_flag; extra_info_flag",
        "numerator": (
            "eligible rows with added information that preserve relevant signals while suppressing "
            "irrelevant ones"
        ),
        "denominator": "all label-eligible rows exposed to additional information",
        "scale": "0.00-1.00, where higher means stronger evidence of selective filtering",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of relevance taxonomy, reference counts, and simplification trace"
        ),
        "ambiguity": "HIGH when shorter reasoning could mean filtering or simple omission",
        "label_review_trigger": (
            "unknown labels exceed 20% because relevance tags are not stable across providers or packs"
        ),
        "metric_review_trigger": (
            "information_filtering_evidence_score is dominated by proxy verbosity rather than true "
            "relevance filtering"
        ),
        "metric_risk": "MEDIUM",
    },
    "MECH_FORECAST_STABILITY": {
        "label_name": "forecast_stability_operational_label",
        "observable_inputs": (
            "paired context-perturbation rows; forecast flip trace; trigger classification; "
            "irrelevant-context stability flag"
        ),
        "required_context": (
            "paired or repeated rows with deterministic perturbation identity; trigger taxonomy frozen "
            "before outcome review"
        ),
        "minimum_evidence": (
            "paired row available + trigger class assigned + forecast stable under irrelevant context "
            "or changes only under high-value trigger"
        ),
        "positive_rule": (
            "Assign mechanism_positive when forecasts remain stable under irrelevant perturbations and "
            "change only when a pre-registered high-value trigger is present."
        ),
        "negative_rule": (
            "Assign mechanism_negative when forecasts flip without a valid trigger or remain inert "
            "despite a high-value trigger."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when paired rows exist but trigger quality or perturbation class "
            "cannot distinguish selective stability from randomness."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when paired rows, perturbation ids, or trigger classes are "
            "missing."
        ),
        "conflicts": (
            "forecast changes without valid trigger; forecast unchanged despite high-value trigger; "
            "paired context exists but perturbation type is not frozen"
        ),
        "tie_break": (
            "If paired stability and selective-change signals conflict, prefer mechanism_negative when "
            "an invalid flip is directly observed; otherwise fall back to mechanism_unknown."
        ),
        "primary_metric": "forecast_stability_evidence_score",
        "secondary_metrics": "irrelevant_context_stability_rate; valid_trigger_change_rate",
        "supporting_indicators": "paired_row_available_flag; trigger_quality_flag; flip_trace_flag",
        "numerator": (
            "eligible paired rows that remain stable under irrelevant context or change only with a "
            "high-value trigger"
        ),
        "denominator": "all label-eligible paired perturbation rows",
        "scale": "0.00-1.00, where higher means stronger selective-stability evidence",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of paired rows, perturbation identity, and trigger classification"
        ),
        "ambiguity": "MEDIUM when paired evidence exists but trigger quality is only partial",
        "label_review_trigger": (
            "paired-row coverage falls below planned minimum or perturbation classes drift across runs"
        ),
        "metric_review_trigger": (
            "forecast_stability_evidence_score cannot separate selective adaptation from simple inertia"
        ),
        "metric_risk": "MEDIUM",
    },
    "MECH_CAUSAL_ROBUSTNESS": {
        "label_name": "causal_robustness_operational_label",
        "observable_inputs": (
            "multi-context causal traces; premise-consistency checks; contradiction flags; "
            "scenario-consistency markers"
        ),
        "required_context": (
            "multiple pre-outcome context perturbations or scenario rewrites; stable premise-tracking "
            "schema; same forecast target across contexts"
        ),
        "minimum_evidence": (
            "at least two comparable causal traces + no direct premise contradiction + stable core "
            "causal chain across contexts"
        ),
        "positive_rule": (
            "Assign mechanism_positive when the core causal chain survives multiple pre-outcome "
            "contexts without contradiction and preserves the same premise ordering."
        ),
        "negative_rule": (
            "Assign mechanism_negative when context perturbations expose premise contradictions, "
            "causal reversals, or unsupported chain rewrites."
        ),
        "unknown_rule": (
            "Assign mechanism_unknown when multiple traces exist but only part of the chain is "
            "comparable or when context shifts produce mixed but non-contradictory edits."
        ),
        "insufficient_rule": (
            "Assign insufficient_evidence when fewer than two comparable causal traces exist or "
            "premise-tracking fields are missing."
        ),
        "conflicts": (
            "single-trace coherence present but cross-context contradiction exists; scenario language "
            "stable while premise ordering changes"
        ),
        "tie_break": (
            "Direct contradiction always overrides coherence claims; otherwise unresolved multi-context "
            "drift falls back to mechanism_unknown."
        ),
        "primary_metric": "causal_robustness_evidence_score",
        "secondary_metrics": "premise_consistency_rate; contradiction_free_trace_rate",
        "supporting_indicators": "multi_context_trace_count; contradiction_flag; scenario_consistency_flag",
        "numerator": (
            "eligible multi-context rows where premise-consistent causal chains remain contradiction-free"
        ),
        "denominator": "all label-eligible rows with comparable multi-context traces",
        "scale": "0.00-1.00, where higher means stronger causal-robustness evidence",
        "expected_range": "0.00-1.00",
        "confidence_source": (
            "completeness of multi-context traces, contradiction checks, and premise-order tracking"
        ),
        "ambiguity": "HIGHEST because coherence, consistency, and contradiction are easy to conflate without frozen trace structure",
        "label_review_trigger": (
            "unknown labels exceed 20% or contradiction checks differ across equivalent perturbations"
        ),
        "metric_review_trigger": (
            "causal_robustness_evidence_score still relies on subjective trace parsing rather than "
            "fully frozen contradiction markers"
        ),
        "metric_risk": "HIGH",
    },
}


def _run_id(generated_ts: str) -> str:
    return "predictive_mechanism_label_metric_design_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, design_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "design_run_id": design_run_id,
    }


def _sheet_titles_light(service, spreadsheet_id: str) -> set[str]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet_minimal_light(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    data_row_count: int,
) -> List[str]:
    titles = _sheet_titles_light(service, spreadsheet_id)
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                                "gridProperties": {
                                    "rowCount": max(1, data_row_count + 1),
                                    "columnCount": max(1, len(required_headers)),
                                },
                            }
                        }
                    }
                ]
            },
        ).execute()
        headers = list(required_headers)
    else:
        headers = _get_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in headers:
                headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing = [sheet for sheet in INPUT_SHEETS if sheet not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(sorted(missing))}")
    return {sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in INPUT_SHEETS}


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("PREDICTIVE_MECHANISM_LABEL_MODEL", OUTPUT_LABEL_MODEL, "predictive_mechanism_label_model"),
        (
            "PREDICTIVE_MECHANISM_LABEL_ASSIGNMENT",
            OUTPUT_LABEL_ASSIGNMENT,
            "predictive_mechanism_label_assignment",
        ),
        ("PREDICTIVE_MECHANISM_METRIC_MODEL", OUTPUT_METRIC_MODEL, "predictive_mechanism_metric_model"),
        (
            "PREDICTIVE_MECHANISM_CONFIDENCE_FRAMEWORK",
            OUTPUT_CONFIDENCE,
            "predictive_mechanism_confidence_framework",
        ),
        (
            "PREDICTIVE_MECHANISM_LABEL_CONFLICT_RULES",
            OUTPUT_CONFLICT,
            "predictive_mechanism_label_conflict_rules",
        ),
        (
            "PREDICTIVE_MECHANISM_AUDIT_FRAMEWORK",
            OUTPUT_AUDIT,
            "predictive_mechanism_audit_framework",
        ),
        (
            "PREDICTIVE_MECHANISM_LABEL_READINESS",
            OUTPUT_READINESS,
            "predictive_mechanism_label_readiness",
        ),
        (
            "PREDICTIVE_MECHANISM_LABEL_METRIC_SUMMARY",
            OUTPUT_SUMMARY,
            "predictive_mechanism_label_metric_summary",
        ),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in specs:
        key = logical_id.upper()
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
            "notes": "Phase 9A-6B predictive mechanism label and metric design; research-only diagnostic artifacts.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in REGISTRY_HEADERS]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(specs) - appended, "appended": appended}


def build_predictive_mechanism_label_metric_design_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
    inputs = _read_inputs(service)

    design_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Design"]}
    test_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Test_Framework"]}
    control_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Control_Definition"]}
    metric_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Metric_Definition"]}
    falsify_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Falsification_Rules"]}
    data_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Data_Requirements"]}
    priority_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Priority"]}
    prior_readiness_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Test_Readiness"]}

    labels_by_mech: Dict[str, set[str]] = {}
    for row in inputs["Predictive_Mechanism_Label_Definitions"]:
        mechanism_id = _norm(row.get("mechanism_id"))
        labels_by_mech.setdefault(mechanism_id, set()).add(_norm(row.get("label_name")))

    prereg_components_by_mech: Dict[str, set[str]] = {}
    for row in inputs["Predictive_Mechanism_PreRegistration"]:
        mechanism_id = _norm(row.get("mechanism_id"))
        prereg_components_by_mech.setdefault(mechanism_id, set()).add(_norm(row.get("freeze_component")))

    behavior_observable_by_mech: Dict[str, str] = {}
    predictive_observable_by_mech: Dict[str, str] = {}
    for row in inputs["Predictive_Mechanism_Observables"]:
        mechanism_id = _norm(row.get("mechanism_id"))
        observable_type = _norm(row.get("observable_type")).upper()
        definition = _norm(row.get("observable_definition"))
        if observable_type == "BEHAVIOR":
            behavior_observable_by_mech[mechanism_id] = definition
        elif observable_type == "PREDICTIVE":
            predictive_observable_by_mech[mechanism_id] = definition

    label_model_rows: List[Dict[str, Any]] = []
    assignment_rows: List[Dict[str, Any]] = []
    metric_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    readiness_rows: List[Dict[str, Any]] = []

    ready_count = 0
    blocked_count = 0

    for mechanism_id in MECHANISM_ORDER:
        design = design_by_id.get(mechanism_id, {})
        test = test_by_id.get(mechanism_id, {})
        control = control_by_id.get(mechanism_id, {})
        metric = metric_by_id.get(mechanism_id, {})
        falsify = falsify_by_id.get(mechanism_id, {})
        data = data_by_id.get(mechanism_id, {})
        priority = priority_by_id.get(mechanism_id, {})
        prior_readiness = prior_readiness_by_id.get(mechanism_id, {})
        rules = MECH_RULES[mechanism_id]

        frozen_labels = labels_by_mech.get(mechanism_id, set())
        missing_labels = sorted(EXPECTED_LABELS - frozen_labels)
        prereg_components = prereg_components_by_mech.get(mechanism_id, set())
        missing_prereg = sorted(
            {
                "mechanism_labels",
                "metric_definitions",
                "success_thresholds",
                "falsification_rules",
                "sample_requirements",
                "interpretation_boundaries",
            }
            - prereg_components
        )
        metric_dependency = _norm(test.get("metric_redesign_required_first")) or _norm(prior_readiness.get("metric_dependency"))
        blocking_issue = ""
        readiness_status = "READY_WITH_WARNINGS"
        if missing_labels:
            blocking_issue = f"missing_frozen_labels:{'|'.join(missing_labels)}"
            readiness_status = "BLOCKED"
        elif missing_prereg:
            blocking_issue = f"missing_pre_registration_components:{'|'.join(missing_prereg)}"
            readiness_status = "BLOCKED"

        if readiness_status == "BLOCKED":
            blocked_count += 1
        else:
            ready_count += 1

        required_behavior_evidence = _norm(control.get("required_evidence")) or behavior_observable_by_mech.get(mechanism_id) or _norm(design.get("observable_behavior"))
        observable_inputs = rules["observable_inputs"]
        label_model_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "label_name": rules["label_name"],
                "observable_inputs": observable_inputs,
                "required_behavior_evidence": required_behavior_evidence,
                "required_context": rules["required_context"],
                "minimum_evidence": rules["minimum_evidence"],
                "insufficient_evidence_rule": rules["insufficient_rule"],
                "exclusion_rule": (
                    "Exclude rows with invalid output, missing required pre-outcome trace fields, "
                    "schema mismatch, or any dependence on realized outcomes."
                ),
                "unknown_rule": rules["unknown_rule"],
                "outcome_independence_rule": COMMON_OUTCOME_RULE,
                "notes": json.dumps(
                    {
                        "frozen_labels_found": sorted(frozen_labels),
                        "predictive_observable_reference": predictive_observable_by_mech.get(mechanism_id, ""),
                        "priority": _norm(priority.get("final_execution_priority")),
                    },
                    sort_keys=True,
                ),
            }
        )
        assignment_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "positive_assignment_rule": rules["positive_rule"],
                "negative_assignment_rule": rules["negative_rule"],
                "unknown_assignment_rule": rules["unknown_rule"],
                "insufficient_evidence_assignment_rule": rules["insufficient_rule"],
                "conflict_resolution_rule": COMMON_PRECEDENCE,
                "tie_breaking_rule": rules["tie_break"],
                "auditability_requirement": COMMON_AUDIT,
                "deterministic_assignment_status": "TRUE" if readiness_status != "BLOCKED" else "FALSE",
                "notes": "Assignment rules are deterministic and must not inspect realized outcomes.",
            }
        )
        metric_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "primary_mechanism_metric": rules["primary_metric"],
                "linked_frozen_test_metric": _norm(metric.get("primary_metric")),
                "secondary_metrics": rules["secondary_metrics"],
                "supporting_indicators": rules["supporting_indicators"],
                "numerator_definition": rules["numerator"],
                "denominator_definition": rules["denominator"],
                "interpretation_scale": rules["scale"],
                "expected_range": rules["expected_range"],
                "notes": json.dumps(
                    {
                        "frozen_secondary_metric": _norm(metric.get("secondary_metric")),
                        "frozen_supporting_metrics": _norm(metric.get("supporting_metrics")),
                        "predictive_effect_reference": predictive_observable_by_mech.get(mechanism_id, ""),
                    },
                    sort_keys=True,
                ),
            }
        )
        confidence_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "label_confidence_source": rules["confidence_source"],
                "evidence_completeness": (
                    "COMPLETE if all required observable inputs and context fields are present; "
                    "PARTIAL if one helper trace is missing; SPARSE if two or more are missing"
                ),
                "evidence_consistency": (
                    "CONSISTENT if positive or negative evidence aligns without direct contradiction; "
                    "MIXED if positive and negative checks coexist; CONTRADICTORY if precedence must "
                    "resolve a direct clash"
                ),
                "ambiguity_level": rules["ambiguity"],
                "confidence_category": "HIGH | MODERATE | LOW | UNKNOWN",
                "confidence_assignment_rule": (
                    "HIGH=complete+consistent+low ambiguity; MODERATE=partial but non-contradictory; "
                    "LOW=mixed or high ambiguity; UNKNOWN=insufficient_evidence or excluded_case"
                ),
                "notes": "Label confidence applies to mechanism classification quality, not forecast confidence.",
            }
        )
        conflict_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "conflicting_observables": rules["conflicts"],
                "conflicting_mechanism_evidence": (
                    "behavior evidence suggests mechanism presence while context, gating, or "
                    "noise-control evidence suggests absence"
                ),
                "conflicting_labels": "mechanism_positive vs mechanism_negative; mechanism_positive vs insufficient_evidence",
                "precedence_hierarchy": COMMON_PRECEDENCE,
                "unresolved_conflict_handling": (
                    "Return mechanism_unknown with LOW confidence when conflict remains after "
                    "precedence and tie-breaking; no manual interpretation required."
                ),
                "manual_interpretation_required": "FALSE",
                "notes": "Conflict handling must stay deterministic and traceable.",
            }
        )
        audit_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "audit_checkpoints": (
                    "source presence; pre-outcome-only field check; label rule version; conflict rule "
                    "trace; confidence trace; metric formula reference"
                ),
                "traceability_requirements": COMMON_AUDIT,
                "reproducibility_requirements": (
                    "same source rows, same frozen rules, same normalized inputs, same classification "
                    "output on rerun"
                ),
                "label_review_trigger": rules["label_review_trigger"],
                "metric_review_trigger": rules["metric_review_trigger"],
                "governance_trigger": (
                    "any use of realized direction, realized pips, overall_ok, corrected evaluation "
                    "results, future market outcomes, or hindsight interpretation"
                ),
                "audit_ready": "TRUE" if readiness_status != "BLOCKED" else "FALSE",
                "notes": json.dumps(
                    {
                        "falsification_reference": _norm(falsify.get("falsification_criterion")),
                        "sample_reference": _norm(data.get("minimum_sample_size")),
                    },
                    sort_keys=True,
                ),
            }
        )

        label_ready = "TRUE" if not missing_labels else "FALSE"
        metric_ready = "TRUE" if readiness_status != "BLOCKED" else "FALSE"
        audit_ready = "TRUE" if readiness_status != "BLOCKED" else "FALSE"
        classification_ready = "TRUE" if readiness_status != "BLOCKED" else "FALSE"
        readiness_reason = (
            "Frozen labels, deterministic assignment rules, confidence mapping, and audit hooks are "
            "defined. Warnings remain because future mechanism testing still depends on frozen metric "
            "instrumentation and sample collection."
        )
        if readiness_status == "BLOCKED":
            readiness_reason = "Critical frozen inputs are missing, so mechanism classification design cannot proceed safely."
        readiness_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "label_ready": label_ready,
                "metric_ready": metric_ready,
                "audit_ready": audit_ready,
                "classification_ready": classification_ready,
                "readiness_status": readiness_status,
                "readiness_reason": readiness_reason,
                "blocking_issue": blocking_issue,
                "recommended_next_action": (
                    "PROCEED_TO_PHASE9A6C_MECHANISM_CLASSIFICATION_DESIGN"
                    if readiness_status != "BLOCKED"
                    else "PROCEED_TO_PHASE9A5M_METRIC_FRAMEWORK_REDESIGN"
                ),
                "notes": json.dumps(
                    {
                        "metric_dependency": metric_dependency or "UNKNOWN",
                        "previous_readiness_status": _norm(prior_readiness.get("readiness_status")),
                        "missing_labels": missing_labels,
                        "missing_pre_registration_components": missing_prereg,
                    },
                    sort_keys=True,
                ),
            }
        )

    overall_blocked = blocked_count > 0
    recommended_next = (
        "PROCEED_TO_PHASE9A5M_METRIC_FRAMEWORK_REDESIGN"
        if overall_blocked
        else "PROCEED_TO_PHASE9A6C_MECHANISM_CLASSIFICATION_DESIGN"
    )
    summary_rows = [
        {
            **_base(generated_ts, design_run_id),
            "build_status": "PASS_WITH_WARNINGS" if not overall_blocked else "NEEDS_REVIEW",
            "final_interpretation": (
                "PREDICTIVE_MECHANISM_LABEL_METRIC_DESIGN_READY_WITH_WARNINGS"
                if not overall_blocked
                else "PREDICTIVE_MECHANISM_LABEL_METRIC_DESIGN_NEEDS_REVIEW"
            ),
            "mechanism_label_models_designed": len(label_model_rows),
            "assignment_rules_defined": len(assignment_rows),
            "metric_models_defined": len(metric_rows),
            "confidence_framework_defined": len(confidence_rows),
            "conflict_rules_defined": len(conflict_rows),
            "audit_framework_defined": len(audit_rows),
            "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
            "highest_label_ambiguity": "MECH_CAUSAL_ROBUSTNESS",
            "highest_metric_risk": "MECH_SIGNAL_DISCIPLINE",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "evaluation_rerun_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_mechanism_classification": "TRUE" if not overall_blocked else "FALSE",
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": json.dumps(
                {
                    "ready_count": ready_count,
                    "blocked_count": blocked_count,
                    "highest_scientific_risk": "mechanism labels may become post-hoc proxies unless frozen before accuracy testing",
                    "classification_boundary": "design_only_no_execution",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_LABEL_MODEL, LABEL_MODEL_HEADERS, label_model_rows),
        (OUTPUT_LABEL_ASSIGNMENT, LABEL_ASSIGNMENT_HEADERS, assignment_rows),
        (OUTPUT_METRIC_MODEL, METRIC_MODEL_HEADERS, metric_rows),
        (OUTPUT_CONFIDENCE, CONFIDENCE_HEADERS, confidence_rows),
        (OUTPUT_CONFLICT, CONFLICT_HEADERS, conflict_rows),
        (OUTPUT_AUDIT, AUDIT_HEADERS, audit_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            headers,
            len(rows),
        )
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_rows[0]["build_status"],
        "final_interpretation": summary_rows[0]["final_interpretation"],
        "file_created": "automation/build_predictive_mechanism_label_metric_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanism_label_models_designed": len(label_model_rows),
        "assignment_rules_defined": len(assignment_rows),
        "metric_models_defined": len(metric_rows),
        "confidence_framework_defined": len(confidence_rows),
        "conflict_rules_defined": len(conflict_rows),
        "audit_framework_defined": len(audit_rows),
        "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
        "highest_label_ambiguity": "MECH_CAUSAL_ROBUSTNESS",
        "highest_metric_risk": "MECH_SIGNAL_DISCIPLINE",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "evaluation_rerun_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_mechanism_classification": not overall_blocked,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_label_metric_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
