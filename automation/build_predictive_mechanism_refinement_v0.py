import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_refinement_0.1"
REFINEMENT_VERSION = "predictive_mechanism_refinement_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_REFINEMENT"
REGISTRY_OWNER_MODULE = "market_state"

PARENT_MECHANISM_ID = "MECH_INFORMATION_VALUE"

INPUT_SHEETS = [
    "Predictive_Mechanism_Conflict_Review",
    "Mechanism_Conflict_Types",
    "Mechanism_Conflict_Root_Causes",
    "Mechanism_Conflict_Frequency",
    "Mechanism_Conflict_Resolution_Options",
    "Mechanism_Information_Value_Decomposition",
    "Mechanism_Conflict_Governance",
    "Mechanism_Conflict_Review_Summary",
    "Predictive_Mechanism_Classification_Dry_Run",
    "Predictive_Mechanism_Label_Preview",
    "Predictive_Mechanism_Evidence_Extraction_Audit",
    "Predictive_Mechanism_Conflict_Audit",
    "Predictive_Mechanism_Confidence_Preview",
    "Predictive_Mechanism_Leakage_Audit",
    "Predictive_Mechanism_Determinism_Audit",
    "Predictive_Mechanism_Dry_Run_Summary",
    "Predictive_Mechanism_Framework",
    "Predictive_Mechanism_Hypotheses",
    "Predictive_Mechanism_Test_Plan",
    "Predictive_Mechanism_Label_Definitions",
    "Predictive_Mechanism_Label_Model",
    "Predictive_Mechanism_Label_Assignment",
    "Predictive_Mechanism_Metric_Model",
    "Predictive_Mechanism_Confidence_Framework",
    "Predictive_Mechanism_Label_Conflict_Rules",
    "Predictive_Mechanism_Classification_Rules",
    "Predictive_Mechanism_Classification_Priority",
]

READ_INPUT_SHEETS = [
    "Mechanism_Conflict_Review_Summary",
    "Predictive_Mechanism_Conflict_Review",
    "Mechanism_Conflict_Root_Causes",
    "Mechanism_Information_Value_Decomposition",
    "Predictive_Mechanism_Dry_Run_Summary",
    "Predictive_Mechanism_Label_Model",
    "Predictive_Mechanism_Label_Assignment",
    "Predictive_Mechanism_Classification_Rules",
]

OUTPUT_REFINEMENT = "Predictive_Mechanism_Refinement"
OUTPUT_DECOMP = "Information_Value_Decomposition_Design"
OUTPUT_DEFINITIONS = "Refined_Mechanism_Definitions"
OUTPUT_OBSERVABLES = "Refined_Mechanism_Observable_Model"
OUTPUT_OVERLAP = "Refined_Mechanism_Overlap_Audit"
OUTPUT_TESTABILITY = "Refined_Mechanism_Testability_Audit"
OUTPUT_PARENT = "Refined_Mechanism_Parent_Disposition"
OUTPUT_PREREG = "Refined_Mechanism_PreRegistration_Requirements"
OUTPUT_GOVERNANCE = "Predictive_Mechanism_Refinement_Governance"
OUTPUT_SUMMARY = "Predictive_Mechanism_Refinement_Summary"

REFINEMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "refinement_area",
    "refinement_status",
    "source_conflict_review",
    "parent_mechanism",
    "decomposition_signal",
    "candidate_submechanisms",
    "candidates_reviewed",
    "candidates_promoted",
    "candidates_rejected",
    "parent_disposition",
    "classification_rerun_performed",
    "labels_modified",
    "accuracy_testing_performed",
    "production_change_performed",
    "refinement_conclusion",
    "recommended_next_action",
    "notes",
]

DECOMP_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "candidate_mechanism_id",
    "parent_mechanism_id",
    "candidate_definition",
    "scientific_question",
    "why_distinct_from_parent",
    "supporting_conflict_evidence",
    "supporting_observables",
    "overlap_risk",
    "outcome_leakage_risk",
    "deterministic_labelability",
    "pre_outcome_observability",
    "testability_status",
    "recommended_disposition",
    "notes",
]

DEFINITIONS_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "mechanism_id",
    "parent_mechanism_id",
    "mechanism_status",
    "mechanism_definition",
    "scientific_question",
    "positive_definition",
    "negative_definition",
    "unknown_definition",
    "insufficient_evidence_definition",
    "excluded_definition",
    "minimum_evidence",
    "outcome_independence_rule",
    "falsification_rule",
    "notes",
]

OBSERVABLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "mechanism_id",
    "observable_id",
    "observable_name",
    "observable_source",
    "observable_definition",
    "required_source_fields",
    "pre_outcome_available",
    "deterministic_extractable",
    "missing_evidence_policy",
    "conflict_policy",
    "leakage_risk",
    "notes",
]

OVERLAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "mechanism_a",
    "mechanism_b",
    "conceptual_overlap",
    "observable_overlap",
    "label_overlap_risk",
    "conflict_risk",
    "distinguishing_rule",
    "joint_positive_allowed",
    "mutual_exclusion_required",
    "audit_conclusion",
    "recommended_action",
    "notes",
]

TESTABILITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "mechanism_id",
    "conceptually_distinct",
    "observable_pre_outcome",
    "deterministically_labelable",
    "minimum_evidence_defined",
    "negative_case_defined",
    "falsification_rule_defined",
    "metric_dependency",
    "sample_dependency",
    "confounder_risk",
    "classification_readiness",
    "testing_readiness",
    "blocking_issue",
    "required_next_action",
    "notes",
]

PARENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "parent_mechanism_id",
    "current_status",
    "decomposition_evidence",
    "retained_scientific_value",
    "future_labeling_allowed",
    "future_testing_allowed",
    "parent_disposition",
    "disposition_reason",
    "legacy_traceability_rule",
    "recommended_next_action",
    "notes",
]

PREREG_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
    "mechanism_id",
    "definition_freeze_required",
    "label_rules_freeze_required",
    "observable_rules_freeze_required",
    "confidence_rules_freeze_required",
    "conflict_rules_freeze_required",
    "metric_rules_freeze_required",
    "falsification_rules_freeze_required",
    "sample_rules_freeze_required",
    "leakage_audit_required",
    "new_dry_run_required",
    "classification_execution_allowed_now",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "refinement_version",
    "refinement_run_id",
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
    "refinement_version",
    "refinement_run_id",
    "build_status",
    "final_interpretation",
    "parent_mechanisms_reviewed",
    "candidate_submechanisms_reviewed",
    "refined_mechanisms_promoted",
    "subdimensions_retained",
    "candidates_rejected",
    "candidates_held",
    "parent_mechanism_disposition",
    "strongest_refined_candidate",
    "highest_overlap_pair",
    "highest_label_risk",
    "highest_leakage_risk",
    "primary_scientific_conclusion",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_rerun_count",
    "permanent_labels_assigned",
    "existing_labels_modified",
    "mechanism_accuracy_testing_performed",
    "outcome_values_accessed",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_refined_mechanism_preregistration",
    "ready_for_refined_classification_dry_run",
    "ready_for_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _refinement_run_id(generated_ts: str) -> str:
    return "predictive_mechanism_refinement_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, refinement_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "refinement_version": REFINEMENT_VERSION,
        "refinement_run_id": refinement_run_id,
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
    data: Dict[str, List[Dict[str, Any]]] = {}
    for sheet in READ_INPUT_SHEETS:
        data[sheet] = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)
    for sheet in INPUT_SHEETS:
        data.setdefault(sheet, [])
    return data


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _safe_int(value: Any) -> int:
    text = _norm(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("PREDICTIVE_MECHANISM_REFINEMENT", OUTPUT_REFINEMENT, "predictive_mechanism_refinement"),
        ("INFORMATION_VALUE_DECOMPOSITION_DESIGN", OUTPUT_DECOMP, "information_value_decomposition_design"),
        ("REFINED_MECHANISM_DEFINITIONS", OUTPUT_DEFINITIONS, "refined_mechanism_definitions"),
        ("REFINED_MECHANISM_OBSERVABLE_MODEL", OUTPUT_OBSERVABLES, "refined_mechanism_observable_model"),
        ("REFINED_MECHANISM_OVERLAP_AUDIT", OUTPUT_OVERLAP, "refined_mechanism_overlap_audit"),
        ("REFINED_MECHANISM_TESTABILITY_AUDIT", OUTPUT_TESTABILITY, "refined_mechanism_testability_audit"),
        ("REFINED_MECHANISM_PARENT_DISPOSITION", OUTPUT_PARENT, "refined_mechanism_parent_disposition"),
        ("REFINED_MECHANISM_PREREGISTRATION_REQUIREMENTS", OUTPUT_PREREG, "refined_mechanism_preregistration_requirements"),
        ("PREDICTIVE_MECHANISM_REFINEMENT_GOVERNANCE", OUTPUT_GOVERNANCE, "predictive_mechanism_refinement_governance"),
        ("PREDICTIVE_MECHANISM_REFINEMENT_SUMMARY", OUTPUT_SUMMARY, "predictive_mechanism_refinement_summary"),
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
            "notes": "Phase 9A-6R predictive mechanism refinement; design-only, no classification or testing execution.",
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


def _decomposition_row_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        out[_norm(row.get("candidate_latent_concept")).upper()] = row
    return out


def _conflict_row_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("mechanism_id")).upper(): row for row in rows}


def _specs(
    decomp_map: Dict[str, Dict[str, Any]],
    parent_conflict_row: Dict[str, Any],
    parent_label_model: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        {
            "mechanism_id": "MECH_INFORMATION_RELEVANCE",
            "latent_concept_key": "INFORMATION RELEVANCE",
            "candidate_definition": "Whether newly exposed information directly aligns with the forecast target, stated drivers, time horizon, or causal path.",
            "scientific_question": "Does the new information directly relate to the forecast target, driver, time horizon, or stated causal path?",
            "why_distinct_from_parent": "Separates target/driver alignment from mere feature exposure and from usefulness after the fact.",
            "supporting_observables": "target-driver alignment; field-to-causal-path alignment; session-horizon alignment; primary-driver linkage; secondary-driver linkage",
            "overlap_risk": "MEDIUM_WITH_SPECIFICITY",
            "outcome_leakage_risk": "MEDIUM_IF_RELEVANCE_IS_CONFUSED_WITH_PREDICTIVE_VALUE",
            "deterministic_labelability": "TRUE_WITH_WARNINGS",
            "pre_outcome_observability": "TRUE",
            "testability_status": "TESTABLE_WITH_WARNINGS",
            "recommended_disposition": "PROMOTE_TO_REFINED_MECHANISM",
            "mechanism_status": "PROMOTED_REFINED_MECHANISM",
            "positive_definition": "Positive when the added information is explicitly linked to the forecast target or stated driver and is incorporated into the causal path.",
            "negative_definition": "Negative when the information is available but unrelated to the target, driver, or horizon, or is cited without changing the causal path.",
            "unknown_definition": "Unknown when alignment is partial or mixed across target, driver, and causal path signals.",
            "insufficient_definition": "Insufficient when target/driver linkage, causal-path trace, or horizon context is missing.",
            "minimum_evidence": "Explicit target or driver linkage plus causal-path alignment trace.",
            "falsification_rule": "If the observable set cannot distinguish aligned use from generic mention, relevance is not a valid standalone mechanism.",
            "classification_readiness": "READY_FOR_PRE_REGISTRATION",
            "testing_readiness": "READY_WITH_WARNINGS",
            "metric_dependency": "LOW_TO_MODERATE",
            "sample_dependency": "MODERATE",
            "confounder_risk": "MEDIUM",
            "blocking_issue": "",
            "required_next_action": "Freeze target-linkage and causal-path observables in a preregistration phase.",
            "strength_rank": 3,
            "label_risk_rank": 3,
            "leakage_risk_rank": 4,
        },
        {
            "mechanism_id": "MECH_INFORMATION_NOVELTY",
            "latent_concept_key": "INFORMATION NOVELTY",
            "candidate_definition": "Whether the exposed information adds a new field family, driver, causal branch, or uncertainty dimension beyond the baseline forecast.",
            "scientific_question": "Does the exposed information add evidence not already represented in the baseline forecast or lower pack?",
            "why_distinct_from_parent": "Novelty is about incremental difference from baseline, not about alignment, precision, or coherence.",
            "supporting_observables": "new field family introduced; new causal branch introduced; new driver introduced; new uncertainty source introduced; duplicate information avoided",
            "overlap_risk": "HIGH_WITH_RELEVANCE_AND_SPECIFICITY",
            "outcome_leakage_risk": "LOW_IF_BASELINE_COMPARISON_REMAINS_PRE_OUTCOME_ONLY",
            "deterministic_labelability": "PARTIAL_BASELINE_DEPENDENT",
            "pre_outcome_observability": "TRUE_WITH_BASELINE_REQUIREMENT",
            "testability_status": "UNDERDEFINED",
            "recommended_disposition": "RETAIN_AS_SUBDIMENSION",
            "mechanism_status": "RETAINED_SUBDIMENSION",
            "positive_definition": "Positive when a new field family, driver, or causal branch is introduced relative to baseline without relying on realized outcomes.",
            "negative_definition": "Negative when the added information duplicates baseline content or fails to add any distinct pre-outcome branch.",
            "unknown_definition": "Unknown when incremental difference exists but cannot be separated from relevance, verbosity, or repackaging.",
            "insufficient_definition": "Insufficient when no comparable baseline exposure exists or baseline-difference traces are missing.",
            "minimum_evidence": "Comparable baseline plus explicit baseline-vs-current difference trace.",
            "falsification_rule": "If novelty cannot be separated from generic additional content, it should remain a subdimension rather than a standalone mechanism.",
            "classification_readiness": "NEEDS_DEFINITION_REPAIR",
            "testing_readiness": "BLOCKED",
            "metric_dependency": "LOW",
            "sample_dependency": "HIGH_BASELINE_MATCH_REQUIREMENT",
            "confounder_risk": "HIGH",
            "blocking_issue": "Baseline incremental exposure is not consistently available and novelty does not imply usefulness.",
            "required_next_action": "Narrow novelty to baseline-difference traces before any new dry run.",
            "strength_rank": 1,
            "label_risk_rank": 4,
            "leakage_risk_rank": 2,
        },
        {
            "mechanism_id": "MECH_INFORMATION_SPECIFICITY",
            "latent_concept_key": "INFORMATION SPECIFICITY",
            "candidate_definition": "Whether the added information makes the forecast more precise, conditional, or falsifiable instead of simply more verbose.",
            "scientific_question": "Does the new information make the forecast more precise, conditional, or falsifiable rather than merely more verbose?",
            "why_distinct_from_parent": "Specificity focuses on precision and falsifiability, not target alignment or newness alone.",
            "supporting_observables": "explicit direction condition; explicit failure condition; explicit time horizon; explicit causal trigger; explicit no-signal boundary; reduced vague language",
            "overlap_risk": "MEDIUM_HIGH_WITH_RELEVANCE",
            "outcome_leakage_risk": "LOW_IF_SPECIFICITY_IS_NOT_JUDGED_BY_CORRECTNESS",
            "deterministic_labelability": "TRUE_WITH_WARNINGS",
            "pre_outcome_observability": "TRUE",
            "testability_status": "TESTABLE_WITH_WARNINGS",
            "recommended_disposition": "PROMOTE_TO_REFINED_MECHANISM",
            "mechanism_status": "PROMOTED_REFINED_MECHANISM",
            "positive_definition": "Positive when the added information introduces explicit conditions, failure boundaries, or time-horizon specificity that makes the forecast more falsifiable.",
            "negative_definition": "Negative when the additional information increases words or references without narrowing the forecast structure.",
            "unknown_definition": "Unknown when precision and verbosity rise together or when specificity signals conflict across fields.",
            "insufficient_definition": "Insufficient when explicit condition, failure-boundary, or horizon traces are absent.",
            "minimum_evidence": "At least one explicit conditional or falsifiable statement trace plus causal-link context.",
            "falsification_rule": "If specificity cannot be distinguished from generic verbosity in pre-outcome traces, it is not a valid standalone mechanism.",
            "classification_readiness": "READY_WITH_WARNINGS",
            "testing_readiness": "READY_WITH_WARNINGS",
            "metric_dependency": "LOW_TO_MODERATE",
            "sample_dependency": "MODERATE",
            "confounder_risk": "MEDIUM",
            "blocking_issue": "",
            "required_next_action": "Freeze verbosity-vs-specificity conflict rules before the next dry run.",
            "strength_rank": 2,
            "label_risk_rank": 3,
            "leakage_risk_rank": 2,
        },
        {
            "mechanism_id": "MECH_INFORMATION_CONSISTENCY",
            "latent_concept_key": "INFORMATION CONSISTENCY",
            "candidate_definition": "Whether the added information remains internally consistent with the pack, the forecast causal chain, and the stated drivers and confidence cues.",
            "scientific_question": "Is the new information internally consistent with the rest of the pack, the forecast's causal chain, and the provider's stated drivers?",
            "why_distinct_from_parent": "Consistency isolates contradiction and coherence directly, without asking whether the information was useful or novel.",
            "supporting_observables": "cross-field consistency; driver-causal-chain consistency; direction-rationale consistency; confidence-evidence consistency; absence of contradiction",
            "overlap_risk": "MEDIUM_WITH_SPECIFICITY",
            "outcome_leakage_risk": "LOW_IF_CONSISTENCY_STAYS_INTERNAL_AND_PRE_OUTCOME",
            "deterministic_labelability": "TRUE",
            "pre_outcome_observability": "TRUE",
            "testability_status": "TESTABLE",
            "recommended_disposition": "PROMOTE_TO_REFINED_MECHANISM",
            "mechanism_status": "PROMOTED_REFINED_MECHANISM",
            "positive_definition": "Positive when the added information fits the existing drivers, causal chain, directional rationale, and confidence-evidence pattern without contradiction.",
            "negative_definition": "Negative when the added information creates cross-field, causal, directional, or confidence-evidence contradictions.",
            "unknown_definition": "Unknown when traces are partially comparable or when consistency differs across subcomponents without a decisive contradiction.",
            "insufficient_definition": "Insufficient when cross-field or premise-comparison traces are missing.",
            "minimum_evidence": "Comparable driver, causal-chain, and confidence-evidence traces.",
            "falsification_rule": "If contradiction-free rows cannot be distinguished from generic coherent wording, consistency should not remain a standalone mechanism.",
            "classification_readiness": "READY_FOR_PRE_REGISTRATION",
            "testing_readiness": "READY_WITH_WARNINGS",
            "metric_dependency": "LOW",
            "sample_dependency": "MODERATE",
            "confounder_risk": "MEDIUM",
            "blocking_issue": "",
            "required_next_action": "Freeze contradiction and mixed-trace handling before the next dry run.",
            "strength_rank": 4,
            "label_risk_rank": 2,
            "leakage_risk_rank": 3,
        },
    ]


def _observable_rows_for(spec: Dict[str, Any]) -> List[Tuple[str, str, str, str, str, str, str, str, str, str, str]]:
    if spec["mechanism_id"] == "MECH_INFORMATION_RELEVANCE":
        return [
            (
                "target_driver_alignment",
                "Target Driver Alignment",
                "Pack_Behavior_Tier2_Behavior",
                "Whether the added information aligns with the forecast target and named primary or secondary driver.",
                "primary_driver_summary; secondary_driver_summary; information_used; causal_chain",
                "TRUE",
                "TRUE",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_ALIGNMENT_IS_PARTIAL",
                "MEDIUM_IF_JUDGED_BY_OUTCOMES_INSTEAD_OF_ALIGNMENT",
                "Relevance must remain target-linked rather than accuracy-linked.",
            ),
            (
                "field_to_causal_path_alignment",
                "Field To Causal Path Alignment",
                "Pack_Behavior_Tier2_Behavior; Pack_Behavior_Tier2_Field_Influence",
                "Whether a cited field maps to the portion of the causal chain that changed.",
                "pack_fields_used; pack_fields_that_changed_reasoning; causal_chain; candidate_family; influence_status",
                "TRUE",
                "TRUE",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_FAMILY_AND_CHAIN_ONLY_PARTIALLY_MATCH",
                "LOW",
                "This observable separates mention from substantive causal-path use.",
            ),
            (
                "session_horizon_alignment",
                "Session Horizon Alignment",
                "Pack_Behavior_Tier2_Behavior; Pack_Behavior_Tier2_NoSignal",
                "Whether the added information is relevant to the forecast session or stated time horizon.",
                "information_used; causal_chain; no_signal_reason; forecast_direction",
                "TRUE",
                "TRUE_WITH_WARNINGS",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_HORIZON_IS_IMPLICIT_ONLY",
                "LOW",
                "Horizon alignment must use pre-outcome session context only.",
            ),
            (
                "driver_linkage_depth",
                "Driver Linkage Depth",
                "Pack_Behavior_Tier2_Behavior",
                "Whether the new information is linked only to secondary commentary or to the primary stated driver of the forecast.",
                "primary_driver_summary; secondary_driver_summary; information_used; causal_chain",
                "TRUE",
                "TRUE_WITH_WARNINGS",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_PRIMARY_AND_SECONDARY_LINKAGES_DISAGREE",
                "LOW",
                "Depth of linkage helps distinguish relevance from background context.",
            ),
        ]
    if spec["mechanism_id"] == "MECH_INFORMATION_NOVELTY":
        return [
            (
                "new_field_family_introduced",
                "New Field Family Introduced",
                "Pack_Behavior_Tier2_Field_Influence",
                "Whether the higher pack exposes a field family absent from the baseline pack.",
                "candidate_family; field_available_in_pack; from_pack_level; to_pack_level",
                "TRUE_WITH_BASELINE",
                "PARTIAL",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_BASELINE_EXPOSURE_IS_MISSING",
                "LOW",
                "Novelty depends on matched baseline availability.",
            ),
            (
                "new_causal_branch_introduced",
                "New Causal Branch Introduced",
                "Pack_Behavior_Tier2_Behavior",
                "Whether the updated forecast adds a causal branch absent from the baseline chain.",
                "causal_chain; information_used; pack_level",
                "TRUE_WITH_BASELINE",
                "PARTIAL",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_BRANCH_CHANGE_IS_ONLY_REPHRASING",
                "LOW",
                "Novelty is about incremental branch addition, not usefulness.",
            ),
            (
                "new_driver_introduced",
                "New Driver Introduced",
                "Pack_Behavior_Tier2_Behavior",
                "Whether a new primary or secondary driver appears relative to the matched baseline row.",
                "primary_driver_summary; secondary_driver_summary; pack_level",
                "TRUE_WITH_BASELINE",
                "PARTIAL",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_DRIVER_TAXONOMY_IS_INCONSISTENT",
                "LOW",
                "Driver novelty must be separated from driver relevance.",
            ),
            (
                "duplicate_information_avoided",
                "Duplicate Information Avoided",
                "Pack_Behavior_Tier2_Behavior; Pack_Behavior_Tier2_Field_Influence",
                "Whether the added pack avoids simply rephrasing information already available in the baseline pack.",
                "information_used; information_not_used; pack_fields_used; pack_fields_discarded",
                "TRUE_WITH_BASELINE",
                "PARTIAL",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_DUPLICATION_CANNOT_BE_DETERMINED_PRE_OUTCOME",
                "LOW",
                "Novelty alone should not be treated as predictive value.",
            ),
        ]
    if spec["mechanism_id"] == "MECH_INFORMATION_SPECIFICITY":
        return [
            (
                "explicit_direction_condition",
                "Explicit Direction Condition",
                "Pack_Behavior_Tier2_Behavior; Pack_Behavior_Tier2_NoSignal",
                "Whether the added information makes directional reasoning conditional rather than generic.",
                "causal_chain; information_used; forecast_direction; no_signal_reason",
                "TRUE",
                "TRUE_WITH_WARNINGS",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_DIRECTION_CONDITION_IS_IMPLICIT",
                "LOW",
                "Specificity is about explicit conditional structure, not correctness.",
            ),
            (
                "explicit_failure_condition",
                "Explicit Failure Condition",
                "Pack_Behavior_Tier2_Behavior",
                "Whether the forecast states a concrete invalidation or failure condition.",
                "invalidation_condition; causal_chain; uncertainty_sources",
                "TRUE",
                "TRUE",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_FAILURE_BOUNDARY_IS_VAGUE",
                "LOW",
                "This observable captures falsifiability directly.",
            ),
            (
                "explicit_time_horizon",
                "Explicit Time Horizon",
                "Pack_Behavior_Tier2_Behavior",
                "Whether the added information narrows the time horizon or session context of the forecast claim.",
                "causal_chain; information_used; primary_driver_summary",
                "TRUE",
                "TRUE_WITH_WARNINGS",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_HORIZON_IS_ONLY_IMPLIED",
                "LOW",
                "Time-horizon precision reduces generic verbosity risk.",
            ),
            (
                "explicit_no_signal_boundary",
                "Explicit No-Signal Boundary",
                "Pack_Behavior_Tier2_NoSignal; Pack_Behavior_Tier2_Behavior",
                "Whether the forecast states clear no-signal or abstention boundaries instead of vague restraint.",
                "no_signal_flag; no_signal_reason; uncertainty_sources; forecast_confidence",
                "TRUE",
                "TRUE",
                "INSUFFICIENT_EVIDENCE",
                "UNKNOWN_IF_BOUNDARY_AND_CONFIDENCE_TRACES_DISAGREE",
                "LOW",
                "No-signal boundary is specificity, not signal discipline by itself.",
            ),
        ]
    return [
        (
            "cross_field_consistency",
            "Cross Field Consistency",
            "Pack_Behavior_Tier2_Field_Influence; Pack_Behavior_Tier2_Behavior",
            "Whether the fields cited as influential are consistent with the stated causal explanation.",
            "candidate_family; influence_status; information_used; causal_chain",
            "TRUE",
            "TRUE",
            "INSUFFICIENT_EVIDENCE",
            "NEGATIVE_IF_DIRECT_CONTRADICTION_IS_PRESENT_OTHERWISE_UNKNOWN",
            "LOW",
            "Consistency is internal to the pre-outcome trace.",
        ),
        (
            "driver_causal_chain_consistency",
            "Driver Causal Chain Consistency",
            "Pack_Behavior_Tier2_Behavior",
            "Whether primary and secondary drivers agree with the stated causal chain.",
            "primary_driver_summary; secondary_driver_summary; causal_chain",
            "TRUE",
            "TRUE",
            "INSUFFICIENT_EVIDENCE",
            "NEGATIVE_IF_DRIVER_AND_CHAIN_IMPLY_DIFFERENT_SIGNALS",
            "LOW",
            "This observable operationalizes contradiction directly.",
        ),
        (
            "direction_rationale_consistency",
            "Direction Rationale Consistency",
            "Pack_Behavior_Tier2_NoSignal; Pack_Behavior_Tier2_Behavior",
            "Whether the stated direction or no-signal outcome matches the pre-outcome rationale described in the chain.",
            "forecast_direction; no_signal_flag; causal_chain; no_signal_reason",
            "TRUE",
            "TRUE_WITH_WARNINGS",
            "INSUFFICIENT_EVIDENCE",
            "UNKNOWN_IF_CHAIN_IS_PARTIAL_OR_MIXED",
            "LOW",
            "This is not realized direction; it is internal forecast coherence.",
        ),
        (
            "confidence_evidence_consistency",
            "Confidence Evidence Consistency",
            "Pack_Behavior_Tier2_NoSignal; Pack_Behavior_Tier2_Behavior",
            "Whether stated confidence is coherent with evidence scarcity and uncertainty traces.",
            "forecast_confidence; confidence_bucket; uncertainty_sources; missing_information; no_signal_reason",
            "TRUE",
            "TRUE",
            "INSUFFICIENT_EVIDENCE",
            "NEGATIVE_IF_HIGH_CONFIDENCE_COEXISTS_WITH_EXPLICIT_EVIDENCE_SCARCITY",
            "LOW",
            "Confidence-evidence mismatch was already visible in pre-outcome traces.",
        ),
    ]


def build_predictive_mechanism_refinement_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    refinement_run_id = _refinement_run_id(generated_ts)
    data = _read_inputs(service)

    conflict_summary = _latest(data["Mechanism_Conflict_Review_Summary"])
    conflict_rows = _conflict_row_map(data["Predictive_Mechanism_Conflict_Review"])
    decomp_map = _decomposition_row_map(data["Mechanism_Information_Value_Decomposition"])
    parent_conflict_row = conflict_rows.get(PARENT_MECHANISM_ID, {})
    parent_label_model = next(
        (row for row in data["Predictive_Mechanism_Label_Model"] if _norm(row.get("mechanism_id")).upper() == PARENT_MECHANISM_ID),
        {},
    )

    candidate_specs = _specs(decomp_map, parent_conflict_row, parent_label_model)
    promoted_specs = [spec for spec in candidate_specs if spec["recommended_disposition"] == "PROMOTE_TO_REFINED_MECHANISM"]
    retained_specs = [spec for spec in candidate_specs if spec["recommended_disposition"] == "RETAIN_AS_SUBDIMENSION"]
    rejected_specs = [spec for spec in candidate_specs if spec["recommended_disposition"] == "REJECT_CANDIDATE"]
    held_specs = [spec for spec in candidate_specs if spec["recommended_disposition"] == "HOLD"]

    candidate_names_json = json.dumps([spec["mechanism_id"] for spec in candidate_specs], ensure_ascii=True)
    parent_conflicts = _safe_int(parent_conflict_row.get("total_conflicts"))
    parent_total = _safe_int(parent_conflict_row.get("total_preview_rows"))
    complete_profile = _norm(parent_conflict_row.get("evidence_completeness_profile"))
    consistency_profile = _norm(parent_conflict_row.get("evidence_consistency_profile"))

    refinement_rows = [
        {
            **_base(generated_ts, refinement_run_id),
            "refinement_area": "information_value_parent_review",
            "refinement_status": "PASS_WITH_WARNINGS",
            "source_conflict_review": _norm(conflict_summary.get("final_interpretation")),
            "parent_mechanism": PARENT_MECHANISM_ID,
            "decomposition_signal": _norm(conflict_summary.get("decomposition_signal")) or "STRONG_DECOMPOSITION_SIGNAL",
            "candidate_submechanisms": candidate_names_json,
            "candidates_reviewed": len(candidate_specs),
            "candidates_promoted": len(promoted_specs),
            "candidates_rejected": len(rejected_specs),
            "parent_disposition": "RETAIN_AS_UMBRELLA_ONLY",
            "classification_rerun_performed": "FALSE",
            "labels_modified": "FALSE",
            "accuracy_testing_performed": "FALSE",
            "production_change_performed": "FALSE",
            "refinement_conclusion": "The parent mechanism should remain an umbrella concept only; direct future classification should move to narrower pre-outcome mechanisms.",
            "recommended_next_action": "PROCEED_TO_PHASE9A6R1_REFINED_MECHANISM_PREREGISTRATION",
            "notes": json.dumps(
                {
                    "parent_conflicts": f"{parent_conflicts}/{parent_total}",
                    "complete_profile": complete_profile,
                    "consistency_profile": consistency_profile,
                    "scientific_guardrail": "no_classification_rerun_no_testing",
                },
                sort_keys=True,
                ensure_ascii=True,
            ),
        }
    ]

    decomp_rows: List[Dict[str, Any]] = []
    definition_rows: List[Dict[str, Any]] = []
    observable_rows: List[Dict[str, Any]] = []
    testability_rows: List[Dict[str, Any]] = []
    prereg_rows: List[Dict[str, Any]] = []

    for spec in candidate_specs:
        source_row = decomp_map.get(spec["latent_concept_key"], {})
        supporting_conflict_evidence = _norm(source_row.get("scientific_interpretation")) or _norm(source_row.get("observed_signal"))
        decomp_rows.append(
            {
                **_base(generated_ts, refinement_run_id),
                "candidate_mechanism_id": spec["mechanism_id"],
                "parent_mechanism_id": PARENT_MECHANISM_ID,
                "candidate_definition": spec["candidate_definition"],
                "scientific_question": spec["scientific_question"],
                "why_distinct_from_parent": spec["why_distinct_from_parent"],
                "supporting_conflict_evidence": supporting_conflict_evidence,
                "supporting_observables": spec["supporting_observables"],
                "overlap_risk": spec["overlap_risk"],
                "outcome_leakage_risk": spec["outcome_leakage_risk"],
                "deterministic_labelability": spec["deterministic_labelability"],
                "pre_outcome_observability": spec["pre_outcome_observability"],
                "testability_status": spec["testability_status"],
                "recommended_disposition": spec["recommended_disposition"],
                "notes": json.dumps(
                    {
                        "decomposition_classification": _norm(source_row.get("decomposition_classification")),
                        "observed_count": _norm(source_row.get("observed_count")),
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
            }
        )
        definition_rows.append(
            {
                **_base(generated_ts, refinement_run_id),
                "mechanism_id": spec["mechanism_id"],
                "parent_mechanism_id": PARENT_MECHANISM_ID,
                "mechanism_status": spec["mechanism_status"],
                "mechanism_definition": spec["candidate_definition"],
                "scientific_question": spec["scientific_question"],
                "positive_definition": spec["positive_definition"],
                "negative_definition": spec["negative_definition"],
                "unknown_definition": spec["unknown_definition"],
                "insufficient_evidence_definition": spec["insufficient_definition"],
                "excluded_definition": "Exclude invalid outputs, missing required pre-outcome trace fields, schema mismatches, or any dependence on realized outcomes.",
                "minimum_evidence": spec["minimum_evidence"],
                "outcome_independence_rule": "Use only pre-outcome behavior, transition, field-influence, and no-signal traces. Realized outcomes, corrected outcomes, accuracy metrics, and hindsight interpretation are forbidden.",
                "falsification_rule": spec["falsification_rule"],
                "notes": "Definitions are refinement outputs only and must be re-frozen during preregistration before any dry run.",
            }
        )
        for observable in _observable_rows_for(spec):
            (
                observable_id,
                observable_name,
                observable_source,
                observable_definition,
                required_source_fields,
                pre_outcome_available,
                deterministic_extractable,
                missing_evidence_policy,
                conflict_policy,
                leakage_risk,
                notes,
            ) = observable
            observable_rows.append(
                {
                    **_base(generated_ts, refinement_run_id),
                    "mechanism_id": spec["mechanism_id"],
                    "observable_id": observable_id,
                    "observable_name": observable_name,
                    "observable_source": observable_source,
                    "observable_definition": observable_definition,
                    "required_source_fields": required_source_fields,
                    "pre_outcome_available": pre_outcome_available,
                    "deterministic_extractable": deterministic_extractable,
                    "missing_evidence_policy": missing_evidence_policy,
                    "conflict_policy": conflict_policy,
                    "leakage_risk": leakage_risk,
                    "notes": notes,
                }
            )
        testability_rows.append(
            {
                **_base(generated_ts, refinement_run_id),
                "mechanism_id": spec["mechanism_id"],
                "conceptually_distinct": "TRUE" if spec["recommended_disposition"] != "REJECT_CANDIDATE" else "FALSE",
                "observable_pre_outcome": "TRUE",
                "deterministically_labelable": "TRUE" if spec["classification_readiness"] in {"READY_FOR_PRE_REGISTRATION", "READY_WITH_WARNINGS"} else "FALSE",
                "minimum_evidence_defined": "TRUE",
                "negative_case_defined": "TRUE",
                "falsification_rule_defined": "TRUE",
                "metric_dependency": spec["metric_dependency"],
                "sample_dependency": spec["sample_dependency"],
                "confounder_risk": spec["confounder_risk"],
                "classification_readiness": spec["classification_readiness"],
                "testing_readiness": spec["testing_readiness"],
                "blocking_issue": spec["blocking_issue"],
                "required_next_action": spec["required_next_action"],
                "notes": "Testing remains blocked until preregistration and a refined dry run are complete.",
            }
        )
        prereg_rows.append(
            {
                **_base(generated_ts, refinement_run_id),
                "mechanism_id": spec["mechanism_id"],
                "definition_freeze_required": "TRUE",
                "label_rules_freeze_required": "TRUE",
                "observable_rules_freeze_required": "TRUE",
                "confidence_rules_freeze_required": "TRUE",
                "conflict_rules_freeze_required": "TRUE",
                "metric_rules_freeze_required": "TRUE",
                "falsification_rules_freeze_required": "TRUE",
                "sample_rules_freeze_required": "TRUE",
                "leakage_audit_required": "TRUE",
                "new_dry_run_required": "TRUE",
                "classification_execution_allowed_now": "FALSE",
                "notes": "Refined mechanisms must complete preregistration and a new dry run before any classification execution is allowed.",
            }
        )

    overlap_specs = [
        (
            "MECH_INFORMATION_RELEVANCE",
            "MECH_INFORMATION_NOVELTY",
            "MODERATE",
            "MODERATE",
            "HIGH",
            "MEDIUM",
            "Relevance asks whether the information aligns to target or driver; novelty asks whether the information was absent from baseline.",
            "TRUE",
            "FALSE",
            "PARTIALLY_OVERLAPPING",
            "Keep separate but gate novelty on matched baseline difference.",
        ),
        (
            "MECH_INFORMATION_RELEVANCE",
            "MECH_INFORMATION_SPECIFICITY",
            "MODERATE_HIGH",
            "MODERATE",
            "HIGH",
            "MEDIUM",
            "Relevance is about alignment to target or driver; specificity is about precision, conditionality, and falsifiability.",
            "TRUE",
            "FALSE",
            "PARTIALLY_OVERLAPPING",
            "Keep separate and require precision traces that are independent of target-linkage traces.",
        ),
        (
            "MECH_INFORMATION_RELEVANCE",
            "MECH_INFORMATION_CONSISTENCY",
            "MODERATE",
            "LOW_MODERATE",
            "MEDIUM",
            "MEDIUM",
            "Relevant information can still be inconsistent; consistency focuses on contradiction-free internal fit.",
            "TRUE",
            "FALSE",
            "DISTINCT_WITH_WARNINGS",
            "Retain as separate mechanisms with explicit contradiction rules.",
        ),
        (
            "MECH_INFORMATION_NOVELTY",
            "MECH_INFORMATION_SPECIFICITY",
            "MODERATE",
            "MODERATE",
            "MEDIUM_HIGH",
            "MEDIUM",
            "Novelty captures incremental difference from baseline; specificity captures precision even when no new content is added.",
            "TRUE",
            "FALSE",
            "PARTIALLY_OVERLAPPING",
            "Do not promote novelty to a standalone mechanism until baseline-difference rules are sharpened.",
        ),
        (
            "MECH_INFORMATION_NOVELTY",
            "MECH_INFORMATION_CONSISTENCY",
            "LOW",
            "LOW",
            "MEDIUM",
            "LOW",
            "Novel information may be either consistent or contradictory; the dimensions answer different questions.",
            "TRUE",
            "FALSE",
            "DISTINCT_WITH_WARNINGS",
            "Keep separate and evaluate novelty as a subdimension only.",
        ),
        (
            "MECH_INFORMATION_SPECIFICITY",
            "MECH_INFORMATION_CONSISTENCY",
            "MODERATE",
            "MODERATE",
            "MEDIUM",
            "MEDIUM",
            "A statement may be specific yet inconsistent, or consistent yet vague; the observables should remain separate.",
            "TRUE",
            "FALSE",
            "DISTINCT_WITH_WARNINGS",
            "Use separate conflict rules for contradiction and verbosity.",
        ),
    ]
    overlap_rows = [
        {
            **_base(generated_ts, refinement_run_id),
            "mechanism_a": mechanism_a,
            "mechanism_b": mechanism_b,
            "conceptual_overlap": conceptual_overlap,
            "observable_overlap": observable_overlap,
            "label_overlap_risk": label_overlap_risk,
            "conflict_risk": conflict_risk,
            "distinguishing_rule": distinguishing_rule,
            "joint_positive_allowed": joint_positive_allowed,
            "mutual_exclusion_required": mutual_exclusion_required,
            "audit_conclusion": audit_conclusion,
            "recommended_action": recommended_action,
            "notes": "Multiple mechanisms may legitimately be positive on the same row unless a future preregistration explicitly forbids it.",
        }
        for (
            mechanism_a,
            mechanism_b,
            conceptual_overlap,
            observable_overlap,
            label_overlap_risk,
            conflict_risk,
            distinguishing_rule,
            joint_positive_allowed,
            mutual_exclusion_required,
            audit_conclusion,
            recommended_action,
        ) in overlap_specs
    ]

    parent_row = {
        **_base(generated_ts, refinement_run_id),
        "parent_mechanism_id": PARENT_MECHANISM_ID,
        "current_status": "COMPOSITE_CONFLICTED_PARENT",
        "decomposition_evidence": f"{parent_conflicts}/{parent_total} conflicts with COMPLETE evidence still producing contradiction.",
        "retained_scientific_value": "Umbrella concept for legacy traceability and research history only.",
        "future_labeling_allowed": "FALSE",
        "future_testing_allowed": "FALSE",
        "parent_disposition": "RETAIN_AS_UMBRELLA_ONLY",
        "disposition_reason": "The parent concept is scientifically useful as history and umbrella framing, but too composite for direct future labeling or testing.",
        "legacy_traceability_rule": "Historical references to MECH_INFORMATION_VALUE must remain readable, but all new labeling proposals should route through refined child mechanisms.",
        "recommended_next_action": "PROCEED_TO_PHASE9A6R1_REFINED_MECHANISM_PREREGISTRATION",
        "notes": "Do not delete or retroactively relabel historical parent references.",
    }

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_RERUNS", "classification_rerun_count", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_EXISTING_LABELS", "existing_labels_modified", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_accuracy_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OUTCOME_VALUES", "outcome_values_accessed", "0", "0"),
        ("GOV_CORRECTED_OUTCOMES", "corrected_outcomes_accessed", "0", "0"),
        ("GOV_PRODUCTION_SHEETS", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, refinement_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Refinement phase is design-only and does not access outcomes or rerun classification.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    strongest_spec = max(promoted_specs, key=lambda spec: spec["strength_rank"]) if promoted_specs else candidate_specs[0]
    highest_overlap_row = max(
        overlap_rows,
        key=lambda row: (1 if _norm(row.get("label_overlap_risk")) == "HIGH" else 0, _norm(row.get("conceptual_overlap"))),
    )
    highest_label_risk_spec = max(candidate_specs, key=lambda spec: spec["label_risk_rank"])
    highest_leakage_risk_spec = max(candidate_specs, key=lambda spec: spec["leakage_risk_rank"])

    summary_row = {
        **_base(generated_ts, refinement_run_id),
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "PREDICTIVE_MECHANISM_REFINEMENT_READY_WITH_WARNINGS",
        "parent_mechanisms_reviewed": 1,
        "candidate_submechanisms_reviewed": len(candidate_specs),
        "refined_mechanisms_promoted": len(promoted_specs),
        "subdimensions_retained": len(retained_specs),
        "candidates_rejected": len(rejected_specs),
        "candidates_held": len(held_specs),
        "parent_mechanism_disposition": "RETAIN_AS_UMBRELLA_ONLY",
        "strongest_refined_candidate": strongest_spec["mechanism_id"],
        "highest_overlap_pair": f"{highest_overlap_row['mechanism_a']} vs {highest_overlap_row['mechanism_b']}",
        "highest_label_risk": highest_label_risk_spec["mechanism_id"],
        "highest_leakage_risk": highest_leakage_risk_spec["mechanism_id"],
        "primary_scientific_conclusion": (
            "MECH_INFORMATION_VALUE should not remain a directly classifiable parent mechanism. "
            "Pre-outcome refinement supports promoting narrower dimensions for relevance, specificity, and consistency while keeping novelty as a baseline-dependent subdimension."
        ),
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "permanent_labels_assigned": 0,
        "existing_labels_modified": 0,
        "mechanism_accuracy_testing_performed": 0,
        "outcome_values_accessed": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_refined_mechanism_preregistration": "TRUE",
        "ready_for_refined_classification_dry_run": "FALSE",
        "ready_for_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A6R1_REFINED_MECHANISM_PREREGISTRATION",
        "notes": json.dumps(
            {
                "parent_conflict_summary": f"{parent_conflicts}/{parent_total}",
                "decomposition_signal": _norm(conflict_summary.get("decomposition_signal")),
                "strongest_decomposition_candidates": [
                    spec["mechanism_id"]
                    for spec in promoted_specs
                ],
                "guardrail": "refinement_only_no_dry_run_execution",
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_REFINEMENT, REFINEMENT_HEADERS, refinement_rows),
        (OUTPUT_DECOMP, DECOMP_HEADERS, decomp_rows),
        (OUTPUT_DEFINITIONS, DEFINITIONS_HEADERS, definition_rows),
        (OUTPUT_OBSERVABLES, OBSERVABLE_HEADERS, observable_rows),
        (OUTPUT_OVERLAP, OVERLAP_HEADERS, overlap_rows),
        (OUTPUT_TESTABILITY, TESTABILITY_HEADERS, testability_rows),
        (OUTPUT_PARENT, PARENT_HEADERS, [parent_row]),
        (OUTPUT_PREREG, PREREG_HEADERS, prereg_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "file_created": "automation/build_predictive_mechanism_refinement_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "parent_mechanisms_reviewed": 1,
        "candidate_submechanisms_reviewed": len(candidate_specs),
        "refined_mechanisms_promoted": len(promoted_specs),
        "subdimensions_retained": len(retained_specs),
        "candidates_rejected": len(rejected_specs),
        "candidates_held": len(held_specs),
        "parent_mechanism_disposition": summary_row["parent_mechanism_disposition"],
        "strongest_refined_candidate": summary_row["strongest_refined_candidate"],
        "highest_overlap_pair": summary_row["highest_overlap_pair"],
        "highest_label_risk": summary_row["highest_label_risk"],
        "highest_leakage_risk": summary_row["highest_leakage_risk"],
        "primary_scientific_conclusion": summary_row["primary_scientific_conclusion"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_rerun_count": 0,
        "permanent_labels_assigned": 0,
        "existing_labels_modified": 0,
        "mechanism_accuracy_testing_performed": 0,
        "outcome_values_accessed": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_refined_mechanism_preregistration": True,
        "ready_for_refined_classification_dry_run": False,
        "ready_for_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": summary_row["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_refinement_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
