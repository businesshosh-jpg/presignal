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
from automation.build_predictive_mechanism_label_metric_design_v0 import (
    COMMON_AUDIT,
    COMMON_OUTCOME_RULE,
    COMMON_PRECEDENCE,
    EXPECTED_LABELS,
    MECHANISM_ORDER,
    MECH_RULES,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_predictive_mechanism_classification_design_0.1"
DESIGN_VERSION = "predictive_mechanism_classification_design_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6C"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PREDICTIVE_MECHANISM_CLASSIFICATION_DESIGN"
REGISTRY_OWNER_MODULE = "market_state"

INPUT_SHEETS = [
    "Predictive_Mechanism_Design",
    "Predictive_Mechanism_Test_Framework",
    "Predictive_Mechanism_Observables",
    "Predictive_Mechanism_Evidence_Model",
    "Predictive_Mechanism_Label_Model",
    "Predictive_Mechanism_Label_Assignment",
    "Predictive_Mechanism_Metric_Model",
    "Predictive_Mechanism_Confidence_Framework",
    "Predictive_Mechanism_Label_Conflict_Rules",
    "Predictive_Mechanism_Audit_Framework",
    "Predictive_Mechanism_Label_Readiness",
    "Pack_Behavior_Tier2_Generalization_Review",
    "Pack_Behavior_Tier2_Field_Generalization",
    "Pack_Behavior_Tier2_Transition_Generalization",
    "Pack_Behavior_Tier2_NoSignal_Generalization",
]

OUTPUT_DESIGN = "Predictive_Mechanism_Classification_Design"
OUTPUT_WORKFLOW = "Predictive_Mechanism_Classification_Workflow"
OUTPUT_EVIDENCE = "Predictive_Mechanism_Evidence_Mapping"
OUTPUT_RULES = "Predictive_Mechanism_Classification_Rules"
OUTPUT_PRIORITY = "Predictive_Mechanism_Classification_Priority"
OUTPUT_CONFLICT = "Predictive_Mechanism_Classification_Conflict_Handling"
OUTPUT_DRY_RUN = "Predictive_Mechanism_Classification_Dry_Run"
OUTPUT_GOVERNANCE = "Predictive_Mechanism_Classification_Governance"
OUTPUT_SUMMARY = "Predictive_Mechanism_Classification_Summary"

DESIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "classification_design_status",
    "eligible_evidence",
    "observable_mapping_summary",
    "evidence_extraction_order",
    "deterministic_rule_order",
    "minimum_evidence",
    "classification_output",
    "confidence_assignment",
    "exclusion_rules",
    "unknown_rules",
    "insufficient_evidence_rules",
    "outcome_leakage_check",
    "notes",
]

WORKFLOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "workflow_stage_1",
    "workflow_stage_2",
    "workflow_stage_3",
    "workflow_stage_4",
    "workflow_stage_5",
    "workflow_stage_6",
    "workflow_output",
    "manual_intervention_required",
    "notes",
]

EVIDENCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "source_sheet",
    "source_field_or_signal",
    "mapped_observable",
    "mapping_rule",
    "evidence_type",
    "extraction_priority",
    "outcome_leakage_check",
    "notes",
]

RULES_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "positive_classification_rule",
    "negative_classification_rule",
    "unknown_classification_rule",
    "excluded_classification_rule",
    "insufficient_evidence_classification_rule",
    "conflict_precedence",
    "tie_breaking_rule",
    "outcome_leakage_check",
    "notes",
]

PRIORITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "priority_rank",
    "stage_name",
    "stage_purpose",
    "applies_to_mechanisms",
    "deterministic_requirement",
    "notes",
]

CONFLICT_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "conflicting_observables",
    "conflicting_mechanism_candidates",
    "tie_breaking_hierarchy",
    "unresolved_conflict_handling",
    "audit_requirements",
    "manual_intervention_required",
    "notes",
]

DRY_RUN_HEADERS = [
    "generated_ts",
    "schema_version",
    "design_version",
    "design_run_id",
    "mechanism_id",
    "future_dry_run_scope",
    "expected_eligible_rows",
    "expected_excluded_rows",
    "expected_unknown_labels",
    "expected_insufficient_evidence_labels",
    "expected_confidence_distribution",
    "mechanism_labels_assigned",
    "mechanism_metrics_calculated",
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
    "classification_workflows_designed",
    "evidence_mappings_defined",
    "classification_rules_defined",
    "conflict_rules_defined",
    "dry_run_planned",
    "governance_checks_passed",
    "highest_priority_mechanism",
    "highest_classification_ambiguity",
    "highest_leakage_risk",
    "provider_calls_performed",
    "forecast_generation_performed",
    "mechanism_labels_assigned",
    "accuracy_evaluation_performed",
    "production_behavior_change_count",
    "ready_for_classification_dry_run",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]

FORBIDDEN_OUTCOME_TERMS = [
    "realized direction",
    "realized overall_ok",
    "corrected outcomes",
    "evaluation metrics",
    "future information",
]

DRY_RUN_EXPECTATIONS = {
    "MECH_INFORMATION_VALUE": {
        "eligible": "MEDIUM expected once matched-baseline evidence is present; approximately 40-80 candidate rows per first dry run slice",
        "excluded": "MODERATE due to missing matched baseline or incomplete field-influence trace",
        "unknown": "MODERATE while incremental value and irrelevant-reference penalties disagree",
        "insufficient": "MODERATE if baseline pairing or reasoning-delta trace is absent",
        "confidence": "HIGH 20-30%; MODERATE 40-50%; LOW/UNKNOWN remainder",
    },
    "MECH_SIGNAL_DISCIPLINE": {
        "eligible": "MEDIUM-HIGH expected in low-signal slices; approximately 50-90 candidate rows per first dry run slice",
        "excluded": "LOW-MODERATE if low-signal eligibility or schema-valid no-signal trace is missing",
        "unknown": "LOW-MODERATE when confidence moderation and no-signal behavior disagree",
        "insufficient": "MODERATE when low-signal markers are sparse",
        "confidence": "HIGH 25-35%; MODERATE 40-50%; LOW/UNKNOWN remainder",
    },
    "MECH_CONDITIONAL_PREDICTIVENESS": {
        "eligible": "MEDIUM expected only in pre-registered regime slices; approximately 30-70 candidate rows per first dry run slice",
        "excluded": "MODERATE when regime slice membership is not deterministically frozen",
        "unknown": "MODERATE if overlapping regime markers create mixed gating evidence",
        "insufficient": "LOW-MODERATE when regime gate traces are missing",
        "confidence": "HIGH 15-25%; MODERATE 45-55%; LOW/UNKNOWN remainder",
    },
    "MECH_INFORMATION_FILTERING": {
        "eligible": "MEDIUM expected where added-information exposure and relevance tags are both present; approximately 35-75 candidate rows",
        "excluded": "MODERATE if relevance taxonomy or discarded-field trace is absent",
        "unknown": "MODERATE-HIGH when brevity and filtering cannot yet be separated cleanly",
        "insufficient": "MODERATE when noise-penalty signals are incomplete",
        "confidence": "HIGH 15-25%; MODERATE 40-50%; LOW/UNKNOWN remainder",
    },
    "MECH_FORECAST_STABILITY": {
        "eligible": "LOW-MEDIUM expected because paired perturbation rows are required; approximately 25-55 candidate rows",
        "excluded": "MODERATE-HIGH when paired context or trigger taxonomy is missing",
        "unknown": "MODERATE when selective stability and simple inertia remain hard to separate",
        "insufficient": "MODERATE-HIGH if paired-row coverage is thin",
        "confidence": "HIGH 10-20%; MODERATE 35-45%; LOW/UNKNOWN remainder",
    },
    "MECH_CAUSAL_ROBUSTNESS": {
        "eligible": "LOW-MEDIUM expected because multi-context causal traces are required; approximately 20-45 candidate rows",
        "excluded": "MODERATE if comparable perturbation traces are unavailable",
        "unknown": "HIGH while contradiction-free stability and partial chain drift coexist",
        "insufficient": "MODERATE-HIGH when fewer than two comparable causal traces exist",
        "confidence": "HIGH 10-15%; MODERATE 35-45%; LOW/UNKNOWN remainder",
    },
}

EVIDENCE_MAPS = {
    "MECH_INFORMATION_VALUE": [
        {
            "source_sheet": "Pack_Behavior_Tier2_Field_Generalization",
            "source_field_or_signal": "used_count; changed_reasoning_count; available_not_mentioned_count",
            "mapped_observable": "feature_exposure_trace",
            "mapping_rule": "Treat non-zero use plus changed_reasoning as feature exposure; available_not_mentioned flags negative or missing incremental uptake.",
            "evidence_type": "FIELD_INFLUENCE",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "information_used_change_count; causal_chain_change_count",
            "mapped_observable": "reasoning_delta_trace",
            "mapping_rule": "Use information_used_change_count with causal_chain_change_count to establish whether the feature changed reasoning rather than only appearing.",
            "evidence_type": "REASONING_TRANSITION",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "valid_outputs_count; valid_transition_count",
            "mapped_observable": "evidence_validity_gate",
            "mapping_rule": "Require valid outputs and valid transitions before any information-value evidence is considered label-eligible.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
    "MECH_SIGNAL_DISCIPLINE": [
        {
            "source_sheet": "Pack_Behavior_Tier2_NoSignal_Generalization",
            "source_field_or_signal": "no_signal_change_count; no_signal_reduction_count; confidence_change_count",
            "mapped_observable": "no_signal_behavior_trace",
            "mapping_rule": "Use no-signal deltas and confidence shifts to identify pre-outcome restraint or overreach in low-signal contexts.",
            "evidence_type": "NO_SIGNAL_BEHAVIOR",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "no_signal_change_count; confidence_change_count",
            "mapped_observable": "unsupported_direction_avoidance_trace",
            "mapping_rule": "Map low-signal transitions and confidence changes to directional restraint proxies before any outcome review.",
            "evidence_type": "TRANSITION_PROXY",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "valid_outputs_count; invalid_outputs_count",
            "mapped_observable": "schema_validity_gate",
            "mapping_rule": "Rows are label-eligible only when underlying outputs are valid and no invalid-output exclusion rule is active.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
    "MECH_CONDITIONAL_PREDICTIVENESS": [
        {
            "source_sheet": "Pack_Behavior_Tier2_Field_Generalization",
            "source_field_or_signal": "candidate_family; sessions_with_use; providers_with_use",
            "mapped_observable": "regime_feature_use_trace",
            "mapping_rule": "Use candidate_family plus per-session/provider use counts to map whether a feature appears only inside a pre-registered market-state slice.",
            "evidence_type": "FIELD_REGIME_TRACE",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "pack_transition; information_used_change_count; next_phase_relevance",
            "mapped_observable": "regime_response_trace",
            "mapping_rule": "Treat pack-transition evidence as conditional only when information-used changes are aligned with a frozen regime slice.",
            "evidence_type": "TRANSITION_CONTEXT",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "evidence_scope; sessions_included",
            "mapped_observable": "slice_availability_gate",
            "mapping_rule": "Require that the relevant scope and sessions are present before a regime-conditioned label can be attempted.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
    "MECH_INFORMATION_FILTERING": [
        {
            "source_sheet": "Pack_Behavior_Tier2_Field_Generalization",
            "source_field_or_signal": "discarded_count; no_effect_count; available_not_mentioned_count",
            "mapped_observable": "irrelevant_signal_filtering_trace",
            "mapping_rule": "Discarded or available-but-not-mentioned fields map to pre-outcome filtering behavior when relevance taxonomy is frozen.",
            "evidence_type": "FIELD_FILTERING",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "information_used_change_count; mean_transition_complexity_score",
            "mapped_observable": "causal_noise_trace",
            "mapping_rule": "Use information-used changes plus transition complexity as a proxy for whether extra information simplified or noisified reasoning.",
            "evidence_type": "REASONING_COMPLEXITY",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "valid_transition_count; behavior_signal_classification",
            "mapped_observable": "filtering_eligibility_gate",
            "mapping_rule": "Require valid transitions and behavior-signal evidence before information-filtering classification is attempted.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
    "MECH_FORECAST_STABILITY": [
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "direction_change_count; confidence_change_count; mean_transition_complexity_score",
            "mapped_observable": "forecast_flip_trace",
            "mapping_rule": "Use transition-level direction and confidence changes to identify whether behavior moved under perturbation and how sharply.",
            "evidence_type": "TRANSITION_STABILITY",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_NoSignal_Generalization",
            "source_field_or_signal": "material_confidence_change_count; max_confidence_delta_abs",
            "mapped_observable": "selective_stability_trace",
            "mapping_rule": "Use material confidence deltas to separate selective adjustment from indiscriminate sensitivity.",
            "evidence_type": "CONFIDENCE_STABILITY",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "valid_transition_count; invalid_or_partial_transition_count",
            "mapped_observable": "paired_evidence_gate",
            "mapping_rule": "Require enough valid transitions and reject partial transitions before paired-stability evidence becomes label-eligible.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
    "MECH_CAUSAL_ROBUSTNESS": [
        {
            "source_sheet": "Pack_Behavior_Tier2_Transition_Generalization",
            "source_field_or_signal": "causal_chain_change_count; mean_transition_complexity_score",
            "mapped_observable": "causal_chain_consistency_trace",
            "mapping_rule": "Use causal-chain change counts and transition complexity to detect whether the same core chain survives controlled perturbations.",
            "evidence_type": "CAUSAL_TRANSITION",
            "extraction_priority": "2",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Field_Generalization",
            "source_field_or_signal": "changed_reasoning_count; discarded_count",
            "mapped_observable": "premise_consistency_support",
            "mapping_rule": "Use changed reasoning with discarded-field context to detect whether premise order stays stable while non-core details shift.",
            "evidence_type": "FIELD_REASONING_SUPPORT",
            "extraction_priority": "3",
        },
        {
            "source_sheet": "Pack_Behavior_Tier2_Generalization_Review",
            "source_field_or_signal": "valid_transition_count; behavior_signal_classification",
            "mapped_observable": "multi_context_trace_gate",
            "mapping_rule": "Require valid transition evidence and stable behavior-signal support before any causal-robustness label is attempted.",
            "evidence_type": "ELIGIBILITY_GATE",
            "extraction_priority": "1",
        },
    ],
}


def _run_id(generated_ts: str) -> str:
    return "predictive_mechanism_classification_design_v0_" + generated_ts.replace("-", "").replace(":", "")


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
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_DESIGN", OUTPUT_DESIGN, "predictive_mechanism_classification_design"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_WORKFLOW", OUTPUT_WORKFLOW, "predictive_mechanism_classification_workflow"),
        ("PREDICTIVE_MECHANISM_EVIDENCE_MAPPING", OUTPUT_EVIDENCE, "predictive_mechanism_evidence_mapping"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_RULES", OUTPUT_RULES, "predictive_mechanism_classification_rules"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_PRIORITY", OUTPUT_PRIORITY, "predictive_mechanism_classification_priority"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_CONFLICT_HANDLING", OUTPUT_CONFLICT, "predictive_mechanism_classification_conflict_handling"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_DRY_RUN", OUTPUT_DRY_RUN, "predictive_mechanism_classification_dry_run"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_GOVERNANCE", OUTPUT_GOVERNANCE, "predictive_mechanism_classification_governance"),
        ("PREDICTIVE_MECHANISM_CLASSIFICATION_SUMMARY", OUTPUT_SUMMARY, "predictive_mechanism_classification_summary"),
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
            "notes": "Phase 9A-6C predictive mechanism classification design; deterministic pre-outcome classification architecture only.",
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


def _has_outcome_leakage(*texts: str) -> bool:
    merged = " ".join(texts).lower()
    return any(term in merged for term in FORBIDDEN_OUTCOME_TERMS)


def build_predictive_mechanism_classification_design_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    design_run_id = _run_id(generated_ts)
    inputs = _read_inputs(service)

    design_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Design"]}
    label_model_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Label_Model"]}
    assignment_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Label_Assignment"]}
    metric_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Metric_Model"]}
    confidence_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Confidence_Framework"]}
    conflict_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Label_Conflict_Rules"]}
    audit_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Audit_Framework"]}
    readiness_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Label_Readiness"]}
    test_framework_by_id = {_norm(row.get("mechanism_id")): row for row in inputs["Predictive_Mechanism_Test_Framework"]}

    design_rows: List[Dict[str, Any]] = []
    workflow_rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    rule_rows: List[Dict[str, Any]] = []
    priority_rows: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    dry_run_rows: List[Dict[str, Any]] = []

    ready_for_dry_run = True
    leakage_risk_mechanisms: List[str] = []

    for mechanism_id in MECHANISM_ORDER:
        design = design_by_id.get(mechanism_id, {})
        label_model = label_model_by_id.get(mechanism_id, {})
        assignment = assignment_by_id.get(mechanism_id, {})
        metric = metric_by_id.get(mechanism_id, {})
        confidence = confidence_by_id.get(mechanism_id, {})
        conflict = conflict_by_id.get(mechanism_id, {})
        audit = audit_by_id.get(mechanism_id, {})
        readiness = readiness_by_id.get(mechanism_id, {})
        test_framework = test_framework_by_id.get(mechanism_id, {})
        mech_rules = MECH_RULES[mechanism_id]

        leakage = _has_outcome_leakage(
            _norm(label_model.get("minimum_evidence")),
            _norm(assignment.get("positive_assignment_rule")),
            _norm(assignment.get("negative_assignment_rule")),
            _norm(metric.get("numerator_definition")),
            _norm(metric.get("denominator_definition")),
        )
        leakage_status = "OUTCOME_LEAKAGE_RISK" if leakage else "PASS_PRE_OUTCOME_ONLY"
        if leakage:
            leakage_risk_mechanisms.append(mechanism_id)
            ready_for_dry_run = False

        frozen_labels_present = set(EXPECTED_LABELS)
        missing_labels = sorted(EXPECTED_LABELS - frozen_labels_present)
        classification_status = "READY_WITH_WARNINGS"
        if _norm(readiness.get("classification_ready")) != "TRUE" or missing_labels or leakage:
            classification_status = "BLOCKED" if leakage or missing_labels else "READY_WITH_WARNINGS"
            if classification_status == "BLOCKED":
                ready_for_dry_run = False

        design_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "classification_design_status": classification_status,
                "eligible_evidence": (
                    "Tier 2 behavior generalization traces only: field influence, transitions, no-signal "
                    "changes, and generalization validity gates. No corrected outcome or evaluation fields."
                ),
                "observable_mapping_summary": _norm(label_model.get("observable_inputs")),
                "evidence_extraction_order": (
                    "1) Eligibility gate from generalization review -> 2) primary evidence source -> "
                    "3) corroborating evidence source -> 4) confidence scaffolding"
                ),
                "deterministic_rule_order": (
                    "validate pre-outcome fields -> apply exclusion rules -> apply insufficient evidence "
                    "rules -> evaluate negative contradiction rules -> evaluate positive rules -> fall "
                    "back to unknown -> assign confidence -> emit audit record"
                ),
                "minimum_evidence": _norm(label_model.get("minimum_evidence")),
                "classification_output": (
                    "mechanism_positive; mechanism_negative; mechanism_unknown; "
                    "insufficient_evidence; excluded_case"
                ),
                "confidence_assignment": _norm(confidence.get("confidence_assignment_rule")),
                "exclusion_rules": _norm(label_model.get("exclusion_rule")),
                "unknown_rules": _norm(label_model.get("unknown_rule")),
                "insufficient_evidence_rules": _norm(label_model.get("insufficient_evidence_rule")),
                "outcome_leakage_check": leakage_status,
                "notes": json.dumps(
                    {
                        "label_name": _norm(label_model.get("label_name")),
                        "metric_reference": _norm(metric.get("primary_mechanism_metric")),
                        "test_framework_status": _norm(test_framework.get("test_framework_status")),
                        "missing_frozen_labels": missing_labels,
                    },
                    sort_keys=True,
                ),
            }
        )

        workflow_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "workflow_stage_1": "extract eligible pre-outcome evidence from frozen Tier 2 generalization sources",
                "workflow_stage_2": "validate evidence completeness and schema eligibility",
                "workflow_stage_3": "detect observable conflicts and exclusion conditions",
                "workflow_stage_4": "apply deterministic mechanism classification rules",
                "workflow_stage_5": "assign label confidence from completeness, consistency, and ambiguity",
                "workflow_stage_6": "write audit-ready classification trace without calculating metrics",
                "workflow_output": "future deterministic mechanism label plus confidence plus audit trace",
                "manual_intervention_required": "FALSE",
                "notes": "Workflow remains design-only in this phase; no historical rows are classified.",
            }
        )

        for mapping in EVIDENCE_MAPS[mechanism_id]:
            evidence_rows.append(
                {
                    **_base(generated_ts, design_run_id),
                    "mechanism_id": mechanism_id,
                    "source_sheet": mapping["source_sheet"],
                    "source_field_or_signal": mapping["source_field_or_signal"],
                    "mapped_observable": mapping["mapped_observable"],
                    "mapping_rule": mapping["mapping_rule"],
                    "evidence_type": mapping["evidence_type"],
                    "extraction_priority": mapping["extraction_priority"],
                    "outcome_leakage_check": "PASS_PRE_OUTCOME_ONLY",
                    "notes": "Mapping uses frozen Tier 2 behavior evidence and does not inspect realized outcomes.",
                }
            )

        rule_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "positive_classification_rule": _norm(assignment.get("positive_assignment_rule")),
                "negative_classification_rule": _norm(assignment.get("negative_assignment_rule")),
                "unknown_classification_rule": _norm(assignment.get("unknown_assignment_rule")),
                "excluded_classification_rule": _norm(label_model.get("exclusion_rule")),
                "insufficient_evidence_classification_rule": _norm(assignment.get("insufficient_evidence_assignment_rule")),
                "conflict_precedence": _norm(assignment.get("conflict_resolution_rule")) or COMMON_PRECEDENCE,
                "tie_breaking_rule": _norm(assignment.get("tie_breaking_rule")),
                "outcome_leakage_check": leakage_status,
                "notes": "Rules remain frozen and cannot use realized direction, overall_ok, or future evaluation outputs.",
            }
        )

        conflict_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "conflicting_observables": _norm(conflict.get("conflicting_observables")),
                "conflicting_mechanism_candidates": _norm(conflict.get("conflicting_labels")),
                "tie_breaking_hierarchy": _norm(conflict.get("precedence_hierarchy")) or COMMON_PRECEDENCE,
                "unresolved_conflict_handling": _norm(conflict.get("unresolved_conflict_handling")),
                "audit_requirements": _norm(conflict.get("notes")) or COMMON_AUDIT,
                "manual_intervention_required": "FALSE",
                "notes": "Conflict handling is deterministic; unresolved cases fall to mechanism_unknown with low confidence.",
            }
        )

        expectation = DRY_RUN_EXPECTATIONS[mechanism_id]
        dry_run_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "mechanism_id": mechanism_id,
                "future_dry_run_scope": (
                    "Use frozen Tier 2 historical observations only; no provider reruns; no corrected "
                    "accuracy metrics; dry-run preview of labels and confidence distribution only."
                ),
                "expected_eligible_rows": expectation["eligible"],
                "expected_excluded_rows": expectation["excluded"],
                "expected_unknown_labels": expectation["unknown"],
                "expected_insufficient_evidence_labels": expectation["insufficient"],
                "expected_confidence_distribution": expectation["confidence"],
                "mechanism_labels_assigned": "FALSE",
                "mechanism_metrics_calculated": "FALSE",
                "notes": "Dry-run is designed only; no actual label assignment occurs in Phase 9A-6C.",
            }
        )

    for priority_rank, stage_name, stage_purpose in [
        (1, "observable_extraction", "Extract frozen pre-outcome evidence from approved Tier 2 source sheets."),
        (2, "evidence_validation", "Confirm schema validity, evidence completeness, and eligibility gates."),
        (3, "conflict_detection", "Detect contradictory observables before any label is assigned."),
        (4, "mechanism_assignment", "Apply deterministic positive/negative/unknown/excluded/insufficient rules."),
        (5, "confidence_assignment", "Assign HIGH/MODERATE/LOW/UNKNOWN label confidence from evidence quality."),
        (6, "audit_generation", "Emit traceable classification records and governance-safe dry-run outputs."),
    ]:
        priority_rows.append(
            {
                **_base(generated_ts, design_run_id),
                "priority_rank": priority_rank,
                "stage_name": stage_name,
                "stage_purpose": stage_purpose,
                "applies_to_mechanisms": "ALL",
                "deterministic_requirement": (
                    "No manual interpretation, no realized outcomes, and no future information may be used."
                ),
                "notes": "Global classification pipeline order frozen before any classification dry run.",
            }
        )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_EXECUTION", "mechanism_classification_executed", "0", "0"),
        ("GOV_LABELS_ASSIGNED", "mechanism_labels_assigned", "0", "0"),
        ("GOV_METRICS_CALCULATED", "mechanism_metrics_calculated", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_EVALUATION_RERUN", "evaluation_rerun_count", "0", "0"),
        ("GOV_PROMPT_MODIFICATION", "prompt_modification", "FALSE", "FALSE"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_WRITES", "production_writes", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, design_run_id),
            "check_id": check_id,
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "Classification architecture design only.",
        }
        for check_id, name, expected, actual in governance_specs
    ]
    governance_checks_passed = sum(1 for row in governance_rows if row["status"] == "PASS")

    highest_leakage_risk = (
        "MECH_CAUSAL_ROBUSTNESS_GUARDED_TRACE_COMPLEXITY"
        if not leakage_risk_mechanisms
        else "|".join(leakage_risk_mechanisms)
    )
    recommended_next = (
        "RUN_PHASE9A6C_CLASSIFICATION_DESIGN_REPAIR"
        if not ready_for_dry_run
        else "PROCEED_TO_PHASE9A6D_MECHANISM_CLASSIFICATION_DRY_RUN"
    )
    summary_rows = [
        {
            **_base(generated_ts, design_run_id),
            "build_status": "PASS_WITH_WARNINGS" if ready_for_dry_run else "NEEDS_REVIEW",
            "final_interpretation": (
                "PREDICTIVE_MECHANISM_CLASSIFICATION_DESIGN_READY_WITH_WARNINGS"
                if ready_for_dry_run
                else "PREDICTIVE_MECHANISM_CLASSIFICATION_DESIGN_NEEDS_REVIEW"
            ),
            "classification_workflows_designed": len(workflow_rows),
            "evidence_mappings_defined": len(evidence_rows),
            "classification_rules_defined": len(rule_rows),
            "conflict_rules_defined": len(conflict_rows),
            "dry_run_planned": "TRUE",
            "governance_checks_passed": governance_checks_passed,
            "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
            "highest_classification_ambiguity": "MECH_CAUSAL_ROBUSTNESS",
            "highest_leakage_risk": highest_leakage_risk,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "mechanism_labels_assigned": 0,
            "accuracy_evaluation_performed": 0,
            "production_behavior_change_count": 0,
            "ready_for_classification_dry_run": "TRUE" if ready_for_dry_run else "FALSE",
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": json.dumps(
                {
                    "leakage_risk_mechanisms": leakage_risk_mechanisms,
                    "frozen_labels_expected": sorted(EXPECTED_LABELS),
                    "classification_boundary": "design_only_no_assignment_no_metrics",
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_DESIGN, DESIGN_HEADERS, design_rows),
        (OUTPUT_WORKFLOW, WORKFLOW_HEADERS, workflow_rows),
        (OUTPUT_EVIDENCE, EVIDENCE_HEADERS, evidence_rows),
        (OUTPUT_RULES, RULES_HEADERS, rule_rows),
        (OUTPUT_PRIORITY, PRIORITY_HEADERS, priority_rows),
        (OUTPUT_CONFLICT, CONFLICT_HEADERS, conflict_rows),
        (OUTPUT_DRY_RUN, DRY_RUN_HEADERS, dry_run_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
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
        "file_created": "automation/build_predictive_mechanism_classification_design_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "classification_workflows_designed": len(workflow_rows),
        "evidence_mappings_defined": len(evidence_rows),
        "classification_rules_defined": len(rule_rows),
        "conflict_rules_defined": len(conflict_rows),
        "dry_run_planned": True,
        "governance_checks_passed": governance_checks_passed,
        "highest_priority_mechanism": "MECH_INFORMATION_VALUE",
        "highest_classification_ambiguity": "MECH_CAUSAL_ROBUSTNESS",
        "highest_leakage_risk": highest_leakage_risk,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "mechanism_labels_assigned": 0,
        "accuracy_evaluation_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_classification_dry_run": ready_for_dry_run,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_predictive_mechanism_classification_design_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
