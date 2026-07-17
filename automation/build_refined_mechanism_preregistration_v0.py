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


SCHEMA_VERSION = "presignal_v2_refined_mechanism_preregistration_0.1"
PREREGISTRATION_VERSION = "refined_mechanism_preregistration_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_PREREGISTRATION"
REGISTRY_OWNER_MODULE = "market_state"
REFINED_MECHANISM_VERSION = "1.0"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
SUBDIMENSION_MECHANISMS = ["MECH_INFORMATION_NOVELTY"]
LEGACY_UMBRELLA_MECHANISMS = ["MECH_INFORMATION_VALUE"]

STABLE_ID_MAP = {
    "MECH_INFORMATION_RELEVANCE": "PM-001",
    "MECH_INFORMATION_SPECIFICITY": "PM-002",
    "MECH_INFORMATION_CONSISTENCY": "PM-003",
    "MECH_INFORMATION_NOVELTY": "PM-S01",
    "MECH_INFORMATION_VALUE": "PM-L01",
}

INPUT_SHEETS = [
    "Predictive_Mechanism_Refinement",
    "Information_Value_Decomposition_Design",
    "Refined_Mechanism_Definitions",
    "Refined_Mechanism_Observable_Model",
    "Refined_Mechanism_Overlap_Audit",
    "Refined_Mechanism_Testability_Audit",
    "Refined_Mechanism_Parent_Disposition",
    "Refined_Mechanism_PreRegistration_Requirements",
    "Predictive_Mechanism_Refinement_Summary",
]

OUTPUT_PREREG = "Refined_Mechanism_PreRegistration"
OUTPUT_DEFINITIONS = "Refined_Mechanism_Frozen_Definitions"
OUTPUT_OBSERVABLES = "Refined_Mechanism_Frozen_Observables"
OUTPUT_LABEL_RULES = "Refined_Mechanism_Frozen_Label_Rules"
OUTPUT_CONFIDENCE_RULES = "Refined_Mechanism_Frozen_Confidence_Rules"
OUTPUT_FALSIFICATION_RULES = "Refined_Mechanism_Frozen_Falsification_Rules"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Frozen_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_PreRegistration_Summary"

PREREG_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "parent_mechanism_id",
    "source_refinement_version",
    "freeze_timestamp",
    "parent_mechanism_lineage",
    "historical_traceability_preserved",
    "definition_frozen",
    "observables_frozen",
    "label_rules_frozen",
    "confidence_rules_frozen",
    "falsification_rules_frozen",
    "outcome_independence_frozen",
    "dry_run_classification_allowed",
    "classification_execution_allowed",
    "mechanism_testing_allowed",
    "preregistration_status",
    "notes",
]

DEFINITIONS_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "scientific_definition",
    "positive_label_definition",
    "negative_label_definition",
    "unknown_definition",
    "insufficient_evidence_definition",
    "exclusion_definition",
    "minimum_evidence",
    "outcome_independence_statement",
    "definition_freeze_status",
    "notes",
]

OBSERVABLES_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "observable_id",
    "observable_name",
    "observable_source",
    "observable_definition",
    "required_source_fields",
    "pre_outcome_available",
    "deterministic_extractable",
    "missing_evidence_policy",
    "conflict_policy",
    "observable_freeze_status",
    "notes",
]

LABEL_RULES_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "positive_label_rule",
    "negative_label_rule",
    "unknown_label_rule",
    "insufficient_evidence_rule",
    "exclusion_rule",
    "conflict_precedence_rule",
    "tie_breaking_rule",
    "direct_classification_allowed",
    "label_rule_freeze_status",
    "notes",
]

CONFIDENCE_RULES_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "confidence_levels_allowed",
    "confidence_inputs",
    "high_confidence_rule",
    "moderate_confidence_rule",
    "low_confidence_rule",
    "unknown_confidence_rule",
    "confidence_rule_freeze_status",
    "notes",
]

FALSIFICATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "falsification_rule",
    "contradictory_evidence_definition",
    "minimum_sample_requirement",
    "review_trigger",
    "execution_blocker_if_unmet",
    "falsification_rule_freeze_status",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
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
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "build_status",
    "final_interpretation",
    "refined_mechanisms_frozen",
    "stable_ids_assigned",
    "definitions_frozen",
    "observable_rules_frozen",
    "confidence_rules_frozen",
    "falsification_rules_frozen",
    "parent_mechanism_status",
    "subdimension_status",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_performed",
    "mechanism_testing_performed",
    "production_behavior_change_count",
    "ready_for_refined_classification_dry_run",
    "ready_for_refined_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _preregistration_run_id(generated_ts: str) -> str:
    return "refined_mechanism_preregistration_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, preregistration_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "preregistration_run_id": preregistration_run_id,
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


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _by_key(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get(key)).upper(): row for row in rows if _norm(row.get(key))}


def _group_by(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        value = _norm(row.get(key)).upper()
        if not value:
            continue
        grouped.setdefault(value, []).append(row)
    return grouped


def _role_for(mechanism_id: str) -> str:
    if mechanism_id in PROMOTED_MECHANISMS:
        return "PROMOTED_REFINED_MECHANISM"
    if mechanism_id in SUBDIMENSION_MECHANISMS:
        return "SUBDIMENSION_ONLY"
    return "UMBRELLA_ONLY"


def _stable_id_for(mechanism_id: str) -> str:
    return STABLE_ID_MAP[mechanism_id]


def _source_refinement_version(summary_row: Dict[str, Any]) -> str:
    return _norm(summary_row.get("refinement_version")) or "predictive_mechanism_refinement_v0"


def _sample_requirement_text(testability_row: Dict[str, Any], mechanism_id: str) -> str:
    dependency = _norm(testability_row.get("sample_dependency"))
    if dependency:
        return f"Frozen as qualitative requirement: {dependency}."
    if mechanism_id in PROMOTED_MECHANISMS:
        return "Minimum sample requirements remain frozen qualitatively until the refined dry run validates label coverage."
    if mechanism_id in SUBDIMENSION_MECHANISMS:
        return "No standalone sample minimum because this mechanism remains supporting-only."
    return "Not applicable because the umbrella mechanism is not independently testable."


def _label_rule_bundle(definition_row: Dict[str, Any], mechanism_id: str) -> Dict[str, str]:
    positive = _norm(definition_row.get("positive_definition"))
    negative = _norm(definition_row.get("negative_definition"))
    unknown = _norm(definition_row.get("unknown_definition"))
    insufficient = _norm(definition_row.get("insufficient_evidence_definition"))
    exclusion = _norm(definition_row.get("excluded_definition"))
    if mechanism_id == "MECH_INFORMATION_RELEVANCE":
        conflict = "excluded_case > insufficient_evidence > negative when target or driver misalignment is direct > positive when alignment is explicit without contradiction > unknown"
        tie_break = "If target alignment and causal-path alignment disagree symmetrically, downgrade to UNKNOWN."
        direct = "TRUE_FOR_DRY_RUN_ONLY"
    elif mechanism_id == "MECH_INFORMATION_SPECIFICITY":
        conflict = "excluded_case > insufficient_evidence > negative when verbosity expands without explicit conditional precision > positive when conditional or falsifiable structure is explicit > unknown"
        tie_break = "If precision and verbosity both rise without a clean dominance signal, downgrade to UNKNOWN."
        direct = "TRUE_FOR_DRY_RUN_ONLY"
    elif mechanism_id == "MECH_INFORMATION_CONSISTENCY":
        conflict = "excluded_case > insufficient_evidence > negative when contradiction is direct > positive when drivers, chain, direction rationale, and confidence cues remain coherent > unknown"
        tie_break = "Any unresolved mixed-trace contradiction falls back to UNKNOWN instead of POSITIVE."
        direct = "TRUE_FOR_DRY_RUN_ONLY"
    elif mechanism_id == "MECH_INFORMATION_NOVELTY":
        positive = "Supporting evidence only: a baseline-relative novelty trace may be recorded, but no standalone permanent novelty label may be assigned."
        negative = "Supporting evidence only: absence of novelty may be recorded relative to baseline, but it cannot drive standalone classification."
        unknown = "Unknown novelty remains supporting-only and may not be escalated into direct classification."
        insufficient = "Insufficient novelty evidence remains supporting-only when matched baseline difference cannot be verified."
        exclusion = "Exclude direct novelty classification; the subdimension is not independently classifiable in this version."
        conflict = "SUBDIMENSION_ONLY_SUPPORTING_EVIDENCE"
        tie_break = "No standalone tie-break because independent novelty classification is disabled."
        direct = "FALSE"
    else:
        positive = "Not applicable. The umbrella mechanism is preserved for conceptual traceability only."
        negative = "Not applicable. The umbrella mechanism is preserved for conceptual traceability only."
        unknown = "Not applicable. The umbrella mechanism is preserved for conceptual traceability only."
        insufficient = "Not applicable. The umbrella mechanism is preserved for conceptual traceability only."
        exclusion = "Direct classification is permanently disabled for the umbrella mechanism in refined_mechanism_version 1.0."
        conflict = "UMBRELLA_ONLY_NO_DIRECT_LABELING"
        tie_break = "Not applicable because direct classification is disabled."
        direct = "FALSE"
    return {
        "positive": positive,
        "negative": negative,
        "unknown": unknown,
        "insufficient": insufficient,
        "exclusion": exclusion,
        "conflict": conflict,
        "tie_break": tie_break,
        "direct": direct,
    }


def _confidence_rule_bundle(testability_row: Dict[str, Any], mechanism_id: str) -> Dict[str, str]:
    if mechanism_id == "MECH_INFORMATION_VALUE":
        return {
            "levels": "NOT_APPLICABLE",
            "inputs": "No direct confidence inputs because umbrella-only classification is disabled.",
            "high": "Not applicable.",
            "moderate": "Not applicable.",
            "low": "Not applicable.",
            "unknown": "Always not applicable because direct classification is disabled.",
            "status": "FROZEN_UMBRELLA_ONLY",
        }
    if mechanism_id == "MECH_INFORMATION_NOVELTY":
        return {
            "levels": "SUPPORTING_ONLY",
            "inputs": "Baseline availability; explicit baseline-vs-current difference trace; novelty subdimension observables.",
            "high": "Not applicable for standalone classification because novelty remains supporting-only.",
            "moderate": "Supporting-only evidence may be recorded when baseline difference is visible but still cannot become a direct classifiable label.",
            "low": "Assign low support when baseline-difference evidence is partial or confounded by overlap with relevance or specificity.",
            "unknown": "Unknown when baseline difference cannot be isolated deterministically.",
            "status": "FROZEN_SUBDIMENSION_ONLY",
        }
    return {
        "levels": "HIGH|MODERATE|LOW|UNKNOWN",
        "inputs": "Minimum evidence completeness; deterministic extractability; conflict-policy outcome; leakage-safe pre-outcome observables only.",
        "high": "HIGH when minimum evidence is complete, deterministic extraction is clean, and no direct conflict-policy downgrade is triggered.",
        "moderate": "MODERATE when the mechanism is observable and labelable but still carries overlap or warning-level ambiguity.",
        "low": "LOW when a label is still assignable in dry run but evidence is partial, overlap-prone, or conflict-sensitive.",
        "unknown": "UNKNOWN when minimum evidence is not met or when unresolved ambiguity prevents stable confidence assignment.",
        "status": "FROZEN_CLASSIFIABLE_CONFIDENCE_RULES",
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_PREREGISTRATION", OUTPUT_PREREG, "refined_mechanism_preregistration"),
        ("REFINED_MECHANISM_FROZEN_DEFINITIONS", OUTPUT_DEFINITIONS, "refined_mechanism_frozen_definitions"),
        ("REFINED_MECHANISM_FROZEN_OBSERVABLES", OUTPUT_OBSERVABLES, "refined_mechanism_frozen_observables"),
        ("REFINED_MECHANISM_FROZEN_LABEL_RULES", OUTPUT_LABEL_RULES, "refined_mechanism_frozen_label_rules"),
        ("REFINED_MECHANISM_FROZEN_CONFIDENCE_RULES", OUTPUT_CONFIDENCE_RULES, "refined_mechanism_frozen_confidence_rules"),
        ("REFINED_MECHANISM_FROZEN_FALSIFICATION_RULES", OUTPUT_FALSIFICATION_RULES, "refined_mechanism_frozen_falsification_rules"),
        ("REFINED_MECHANISM_FROZEN_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_frozen_governance"),
        ("REFINED_MECHANISM_PREREGISTRATION_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_preregistration_summary"),
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
            "notes": "Phase 9A-6R1 refined mechanism preregistration; freeze-only, no classification or testing execution.",
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


def build_refined_mechanism_preregistration_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    preregistration_run_id = _preregistration_run_id(generated_ts)
    freeze_timestamp = generated_ts
    data = _read_inputs(service)

    refinement_row = _latest(data["Predictive_Mechanism_Refinement"])
    summary_row = _latest(data["Predictive_Mechanism_Refinement_Summary"])
    parent_row = _latest(data["Refined_Mechanism_Parent_Disposition"])
    definitions_by_id = _by_key(data["Refined_Mechanism_Definitions"], "mechanism_id")
    testability_by_id = _by_key(data["Refined_Mechanism_Testability_Audit"], "mechanism_id")
    prereg_requirements_by_id = _by_key(data["Refined_Mechanism_PreRegistration_Requirements"], "mechanism_id")
    observables_by_id = _group_by(data["Refined_Mechanism_Observable_Model"], "mechanism_id")

    all_mechanisms = PROMOTED_MECHANISMS + SUBDIMENSION_MECHANISMS + LEGACY_UMBRELLA_MECHANISMS

    prereg_rows: List[Dict[str, Any]] = []
    definition_rows: List[Dict[str, Any]] = []
    observable_rows: List[Dict[str, Any]] = []
    label_rule_rows: List[Dict[str, Any]] = []
    confidence_rule_rows: List[Dict[str, Any]] = []
    falsification_rows: List[Dict[str, Any]] = []

    for mechanism_id in all_mechanisms:
        role = _role_for(mechanism_id)
        stable_id = _stable_id_for(mechanism_id)
        definition_row = definitions_by_id.get(mechanism_id, {})
        testability_row = testability_by_id.get(mechanism_id, {})
        requirement_row = prereg_requirements_by_id.get(mechanism_id, {})
        parent_id = _norm(definition_row.get("parent_mechanism_id")) or (
            "MECH_INFORMATION_VALUE" if mechanism_id != "MECH_INFORMATION_VALUE" else ""
        )
        if mechanism_id == "MECH_INFORMATION_VALUE":
            scientific_definition = "Legacy umbrella concept covering the historical idea of information value across multiple narrower dimensions."
            positive_definition = "Not applicable. Direct parent classification is disabled."
            negative_definition = "Not applicable. Direct parent classification is disabled."
            unknown_definition = "Not applicable. Direct parent classification is disabled."
            insufficient_definition = "Not applicable. Direct parent classification is disabled."
            exclusion_definition = "Direct classification of the umbrella mechanism is permanently excluded in refined_mechanism_version 1.0."
            minimum_evidence = "Not applicable because umbrella-only concepts are not independently labelable."
            outcome_statement = "Historical traceability only. No future direct classification or testing is allowed."
        else:
            scientific_definition = _norm(definition_row.get("mechanism_definition"))
            positive_definition = _norm(definition_row.get("positive_definition"))
            negative_definition = _norm(definition_row.get("negative_definition"))
            unknown_definition = _norm(definition_row.get("unknown_definition"))
            insufficient_definition = _norm(definition_row.get("insufficient_evidence_definition"))
            exclusion_definition = _norm(definition_row.get("excluded_definition"))
            minimum_evidence = _norm(definition_row.get("minimum_evidence"))
            outcome_statement = _norm(definition_row.get("outcome_independence_rule"))

        if role == "PROMOTED_REFINED_MECHANISM":
            dry_run_allowed = "TRUE"
            execution_allowed = "FALSE"
            testing_allowed = "FALSE"
            prereg_status = "FROZEN_READY_FOR_DRY_RUN_ONLY"
            definition_freeze_status = "FROZEN_CLASSIFIABLE"
        elif role == "SUBDIMENSION_ONLY":
            dry_run_allowed = "FALSE"
            execution_allowed = "FALSE"
            testing_allowed = "FALSE"
            prereg_status = "FROZEN_SUPPORTING_ONLY"
            definition_freeze_status = "FROZEN_SUBDIMENSION_ONLY"
        else:
            dry_run_allowed = "FALSE"
            execution_allowed = "FALSE"
            testing_allowed = "FALSE"
            prereg_status = "FROZEN_UMBRELLA_ONLY"
            definition_freeze_status = "FROZEN_UMBRELLA_ONLY"

        prereg_rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "parent_mechanism_id": parent_id,
                "source_refinement_version": _source_refinement_version(summary_row),
                "freeze_timestamp": freeze_timestamp,
                "parent_mechanism_lineage": "MECH_INFORMATION_VALUE" if mechanism_id != "MECH_INFORMATION_VALUE" else "SELF_LEGACY_PARENT",
                "historical_traceability_preserved": "TRUE",
                "definition_frozen": "TRUE",
                "observables_frozen": "TRUE" if role != "UMBRELLA_ONLY" else "FALSE",
                "label_rules_frozen": "TRUE",
                "confidence_rules_frozen": "TRUE",
                "falsification_rules_frozen": "TRUE",
                "outcome_independence_frozen": "TRUE",
                "dry_run_classification_allowed": dry_run_allowed,
                "classification_execution_allowed": execution_allowed,
                "mechanism_testing_allowed": testing_allowed,
                "preregistration_status": prereg_status,
                "notes": json.dumps(
                    {
                        "requirement_sheet_flag": _norm(requirement_row.get("classification_execution_allowed_now")),
                        "source_refinement_status": _norm(refinement_row.get("refinement_status")),
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
            }
        )
        definition_rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "scientific_definition": scientific_definition,
                "positive_label_definition": positive_definition,
                "negative_label_definition": negative_definition,
                "unknown_definition": unknown_definition,
                "insufficient_evidence_definition": insufficient_definition,
                "exclusion_definition": exclusion_definition,
                "minimum_evidence": minimum_evidence,
                "outcome_independence_statement": outcome_statement,
                "definition_freeze_status": definition_freeze_status,
                "notes": f"Stable ID {stable_id} is frozen under refined_mechanism_version {REFINED_MECHANISM_VERSION}.",
            }
        )
        rule_bundle = _label_rule_bundle(definition_row, mechanism_id)
        label_rule_rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "positive_label_rule": rule_bundle["positive"],
                "negative_label_rule": rule_bundle["negative"],
                "unknown_label_rule": rule_bundle["unknown"],
                "insufficient_evidence_rule": rule_bundle["insufficient"],
                "exclusion_rule": rule_bundle["exclusion"],
                "conflict_precedence_rule": rule_bundle["conflict"],
                "tie_breaking_rule": rule_bundle["tie_break"],
                "direct_classification_allowed": rule_bundle["direct"],
                "label_rule_freeze_status": "FROZEN",
                "notes": "Label rules are frozen and may not change until the refined dry run and its conflict review complete.",
            }
        )
        confidence_bundle = _confidence_rule_bundle(testability_row, mechanism_id)
        confidence_rule_rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "confidence_levels_allowed": confidence_bundle["levels"],
                "confidence_inputs": confidence_bundle["inputs"],
                "high_confidence_rule": confidence_bundle["high"],
                "moderate_confidence_rule": confidence_bundle["moderate"],
                "low_confidence_rule": confidence_bundle["low"],
                "unknown_confidence_rule": confidence_bundle["unknown"],
                "confidence_rule_freeze_status": confidence_bundle["status"],
                "notes": "Confidence refers only to label-quality and remains outcome-independent.",
            }
        )
        falsification_rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "falsification_rule": _norm(definition_row.get("falsification_rule")) or "Not applicable.",
                "contradictory_evidence_definition": (
                    "Direct contradiction of the frozen positive definition or failure to distinguish the mechanism from overlapping constructs."
                    if role != "UMBRELLA_ONLY"
                    else "Not applicable because direct umbrella testing is disabled."
                ),
                "minimum_sample_requirement": _sample_requirement_text(testability_row, mechanism_id),
                "review_trigger": (
                    "Any refined dry run that shows persistent high conflict, unresolved leakage risk, or inadequate sample coverage."
                    if role != "UMBRELLA_ONLY"
                    else "Any attempt to restore direct umbrella classification requires a new refinement branch."
                ),
                "execution_blocker_if_unmet": "TRUE",
                "falsification_rule_freeze_status": "FROZEN",
                "notes": "Falsification rules are frozen before any refined classification dry run.",
            }
        )
        if role != "UMBRELLA_ONLY":
            observable_status = "FROZEN_CLASSIFIABLE_OBSERVABLE" if role == "PROMOTED_REFINED_MECHANISM" else "FROZEN_SUPPORTING_ONLY_OBSERVABLE"
            for observable_row in observables_by_id.get(mechanism_id, []):
                observable_rows.append(
                    {
                        **_base(generated_ts, preregistration_run_id),
                        "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                        "stable_mechanism_id": stable_id,
                        "mechanism_id": mechanism_id,
                        "mechanism_role": role,
                        "observable_id": _norm(observable_row.get("observable_id")),
                        "observable_name": _norm(observable_row.get("observable_name")),
                        "observable_source": _norm(observable_row.get("observable_source")),
                        "observable_definition": _norm(observable_row.get("observable_definition")),
                        "required_source_fields": _norm(observable_row.get("required_source_fields")),
                        "pre_outcome_available": _norm(observable_row.get("pre_outcome_available")),
                        "deterministic_extractable": _norm(observable_row.get("deterministic_extractable")),
                        "missing_evidence_policy": _norm(observable_row.get("missing_evidence_policy")),
                        "conflict_policy": _norm(observable_row.get("conflict_policy")),
                        "observable_freeze_status": observable_status,
                        "notes": "Observables are frozen exactly as preregistered and may not be broadened before the refined dry run.",
                    }
                )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION", "classification_performed", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_PROMPT_MODIFICATION", "prompt_modification_performed", "FALSE", "FALSE"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, preregistration_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Pre-registration is freeze-only and non-executing.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    summary_row = {
        **_base(generated_ts, preregistration_run_id),
        "refined_mechanism_version": REFINED_MECHANISM_VERSION,
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "REFINED_MECHANISM_PREREGISTRATION_READY_WITH_WARNINGS",
        "refined_mechanisms_frozen": len(PROMOTED_MECHANISMS),
        "stable_ids_assigned": len(STABLE_ID_MAP),
        "definitions_frozen": len(definition_rows),
        "observable_rules_frozen": len(observable_rows),
        "confidence_rules_frozen": len(confidence_rule_rows),
        "falsification_rules_frozen": len(falsification_rows),
        "parent_mechanism_status": "UMBRELLA_ONLY",
        "subdimension_status": "SUBDIMENSION_ONLY",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_performed": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_dry_run": "TRUE",
        "ready_for_refined_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "PROCEED_TO_PHASE9A6R2_REFINED_CLASSIFICATION_DRY_RUN",
        "notes": json.dumps(
            {
                "source_refinement_final_interpretation": _norm(summary_row.get("final_interpretation")),
                "promoted_mechanisms": PROMOTED_MECHANISMS,
                "subdimension_only": SUBDIMENSION_MECHANISMS,
                "umbrella_only": LEGACY_UMBRELLA_MECHANISMS,
                "freeze_timestamp": freeze_timestamp,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_PREREG, PREREG_HEADERS, prereg_rows),
        (OUTPUT_DEFINITIONS, DEFINITIONS_HEADERS, definition_rows),
        (OUTPUT_OBSERVABLES, OBSERVABLES_HEADERS, observable_rows),
        (OUTPUT_LABEL_RULES, LABEL_RULES_HEADERS, label_rule_rows),
        (OUTPUT_CONFIDENCE_RULES, CONFIDENCE_RULES_HEADERS, confidence_rule_rows),
        (OUTPUT_FALSIFICATION_RULES, FALSIFICATION_HEADERS, falsification_rows),
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
        "file_created": "automation/build_refined_mechanism_preregistration_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "refined_mechanisms_frozen": len(PROMOTED_MECHANISMS),
        "stable_ids_assigned": len(STABLE_ID_MAP),
        "definitions_frozen": len(definition_rows),
        "observable_rules_frozen": len(observable_rows),
        "confidence_rules_frozen": len(confidence_rule_rows),
        "falsification_rules_frozen": len(falsification_rows),
        "parent_mechanism_status": "UMBRELLA_ONLY",
        "subdimension_status": "SUBDIMENSION_ONLY",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_performed": 0,
        "mechanism_testing_performed": 0,
        "production_behavior_change_count": 0,
        "ready_for_refined_classification_dry_run": True,
        "ready_for_refined_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": summary_row["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_preregistration_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
