import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

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


SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_second_preregistration_0.1"
PREREGISTRATION_VERSION = "refined_mechanism_v11_second_preregistration_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R5"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_PREREGISTRATION"
REGISTRY_OWNER_MODULE = "market_state"

BASELINE_VERSION = "1.0"
REFINED_MECHANISM_VERSION = "1.1"
SOURCE_CANDIDATE_VERSION = "1.1-candidate"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
SUBDIMENSION_MECHANISMS = ["MECH_INFORMATION_NOVELTY"]
UMBRELLA_MECHANISMS = ["MECH_INFORMATION_VALUE"]
ALL_MECHANISMS = PROMOTED_MECHANISMS + SUBDIMENSION_MECHANISMS + UMBRELLA_MECHANISMS

STABLE_ID_MAP = {
    "MECH_INFORMATION_RELEVANCE": "PM-001",
    "MECH_INFORMATION_SPECIFICITY": "PM-002",
    "MECH_INFORMATION_CONSISTENCY": "PM-003",
    "MECH_INFORMATION_NOVELTY": "PM-S01",
    "MECH_INFORMATION_VALUE": "PM-L01",
}

INPUT_SHEETS = [
    "Refined_Mechanism_Repair",
    "Refined_Mechanism_v11_Candidate_Definitions",
    "Refined_Mechanism_v11_Candidate_Observables",
    "Refined_Mechanism_v11_Candidate_Label_Rules",
    "Refined_Mechanism_Specificity_Repair_Design",
    "Refined_Mechanism_Overlap_Repair_Design",
    "Refined_Mechanism_Exclusion_Rule_Review",
    "Refined_Mechanism_v11_Change_Log",
    "Refined_Mechanism_Second_Preregistration_Readiness",
    "Refined_Mechanism_Repair_Governance",
    "Refined_Mechanism_Repair_Summary",
    "Refined_Mechanism_PreRegistration",
    "Refined_Mechanism_Frozen_Definitions",
    "Refined_Mechanism_Frozen_Observables",
    "Refined_Mechanism_Frozen_Label_Rules",
    "Refined_Mechanism_Frozen_Confidence_Rules",
    "Refined_Mechanism_Frozen_Falsification_Rules",
    "Refined_Mechanism_Frozen_Governance",
    "Refined_Mechanism_PreRegistration_Summary",
]

OUTPUT_PREREG = "Refined_Mechanism_v11_PreRegistration"
OUTPUT_DEFINITIONS = "Refined_Mechanism_v11_Frozen_Definitions"
OUTPUT_OBSERVABLES = "Refined_Mechanism_v11_Frozen_Observables"
OUTPUT_LABEL_RULES = "Refined_Mechanism_v11_Frozen_Label_Rules"
OUTPUT_CONFIDENCE_RULES = "Refined_Mechanism_v11_Frozen_Confidence_Rules"
OUTPUT_CONFLICT_RULES = "Refined_Mechanism_v11_Frozen_Conflict_Rules"
OUTPUT_FALSIFICATION_RULES = "Refined_Mechanism_v11_Frozen_Falsification_Rules"
OUTPUT_SEPARATION_RULES = "Refined_Mechanism_v11_Separation_Rules"
OUTPUT_VERSION_DIFF = "Refined_Mechanism_v11_Version_Diff"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_PreRegistration_Summary"

NEXT_STEP = "PROCEED_TO_PHASE9A6R6_V11_REFINED_CLASSIFICATION_DRY_RUN"

PREREG_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "baseline_version_reference",
    "source_candidate_version",
    "parent_mechanism_id",
    "freeze_timestamp",
    "preregistration_status",
    "change_allowed_during_dry_run",
    "change_allowed_before_conflict_review",
    "historical_traceability_preserved",
    "future_classification_allowed",
    "future_testing_allowed",
    "independent_classification_allowed",
    "independent_testing_allowed",
    "supporting_evidence_allowed",
    "definitions_frozen",
    "observables_frozen",
    "label_rules_frozen",
    "confidence_rules_frozen",
    "conflict_rules_frozen",
    "separation_rules_frozen",
    "falsification_rules_frozen",
    "leakage_protections_frozen",
    "dry_run_requirements_frozen",
    "notes",
]

DEFINITION_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "scientific_definition",
    "scientific_question",
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

OBSERVABLE_HEADERS = [
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
    "observable_source_sheet",
    "source_field_or_family",
    "extraction_rule",
    "positive_evidence_role",
    "negative_evidence_role",
    "supporting_only_status",
    "missing_evidence_handling",
    "conflict_handling",
    "pre_outcome_availability",
    "outcome_independence_statement",
    "observable_freeze_status",
    "notes",
]

LABEL_RULE_HEADERS = [
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
    "excluded_rule",
    "minimum_evidence",
    "required_observables",
    "prohibited_shortcuts",
    "conflict_handling",
    "tie_breaking_rule",
    "confidence_assignment_basis",
    "traceability_requirements",
    "direct_classification_allowed",
    "label_rule_freeze_status",
    "notes",
]

CONFIDENCE_RULE_HEADERS = [
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

CONFLICT_RULE_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "stable_mechanism_id",
    "mechanism_id",
    "mechanism_role",
    "conflict_sources",
    "conflict_precedence_rule",
    "unresolved_conflict_outcome",
    "tie_breaking_rule",
    "manual_override_allowed",
    "outcome_leakage_protection",
    "traceability_requirement",
    "conflict_rule_freeze_status",
    "notes",
]

FALSIFICATION_RULE_HEADERS = [
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
    "minimum_dry_run_evidence",
    "conflict_threshold_warning",
    "ambiguity_threshold_warning",
    "review_trigger",
    "classification_execution_blocker",
    "falsification_rule_freeze_status",
    "notes",
]

SEPARATION_RULE_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "mechanism_a",
    "mechanism_b",
    "mechanism_a_question",
    "mechanism_b_question",
    "joint_positive_allowed",
    "mechanism_a_does_not_imply_b",
    "mechanism_b_does_not_imply_a",
    "separation_rule",
    "negative_case_example",
    "supporting_only_cues",
    "separation_rule_freeze_status",
    "notes",
]

VERSION_DIFF_HEADERS = [
    "generated_ts",
    "schema_version",
    "preregistration_version",
    "preregistration_run_id",
    "refined_mechanism_version",
    "component_id",
    "mechanism_id",
    "component_type",
    "v1_0_rule",
    "v1_1_rule",
    "scientific_reason",
    "source_conflict_finding",
    "expected_classification_effect",
    "scientific_meaning_changed",
    "operational_clarity_changed",
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
    "stable_ids_preserved",
    "definitions_frozen",
    "observables_frozen",
    "label_rules_frozen",
    "confidence_rules_frozen",
    "conflict_rules_frozen",
    "separation_rules_frozen",
    "falsification_rules_frozen",
    "version_differences_recorded",
    "parent_mechanism_status",
    "novelty_subdimension_status",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_dry_run_performed",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "outcome_values_accessed",
    "v1_0_sheets_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_v11_refined_classification_dry_run",
    "ready_for_permanent_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _preregistration_run_id(generated_ts: str) -> str:
    return "refined_mechanism_v11_second_preregistration_v0_" + generated_ts.replace("-", "").replace(":", "")


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


def _parse_json_text(value: Any) -> Dict[str, Any]:
    text = _norm(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


def _by_key(rows: List[Dict[str, Any]], field: str) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get(field)): row for row in rows if _norm(row.get(field))}


def _group_by(rows: List[Dict[str, Any]], field: str) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = _norm(row.get(field))
        if key:
            out.setdefault(key, []).append(row)
    return out


def _counter_json(counter: Dict[str, Any]) -> str:
    return json.dumps(counter, sort_keys=True, ensure_ascii=True)


def _role_for(mechanism_id: str) -> str:
    if mechanism_id in PROMOTED_MECHANISMS:
        return "PROMOTED_REFINED_MECHANISM"
    if mechanism_id in SUBDIMENSION_MECHANISMS:
        return "SUBDIMENSION_ONLY"
    return "UMBRELLA_ONLY"


def _source_sheet_field_bundle(
    observable_rows_by_id: Dict[str, Dict[str, Any]],
    source_ids: Sequence[str],
) -> Tuple[str, str]:
    sheet_parts: List[str] = []
    field_parts: List[str] = []
    for source_id in source_ids:
        row = observable_rows_by_id.get(source_id, {})
        for part in _norm(row.get("observable_source")).split(";"):
            text = _norm(part)
            if text and text not in sheet_parts:
                sheet_parts.append(text)
        for part in _norm(row.get("required_source_fields")).split(";"):
            text = _norm(part)
            if text and text not in field_parts:
                field_parts.append(text)
    return "; ".join(sheet_parts), "; ".join(field_parts)


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_V11_PREREGISTRATION", OUTPUT_PREREG, "refined_mechanism_v11_preregistration"),
        ("REFINED_MECHANISM_V11_FROZEN_DEFINITIONS", OUTPUT_DEFINITIONS, "refined_mechanism_v11_frozen_definitions"),
        ("REFINED_MECHANISM_V11_FROZEN_OBSERVABLES", OUTPUT_OBSERVABLES, "refined_mechanism_v11_frozen_observables"),
        ("REFINED_MECHANISM_V11_FROZEN_LABEL_RULES", OUTPUT_LABEL_RULES, "refined_mechanism_v11_frozen_label_rules"),
        ("REFINED_MECHANISM_V11_FROZEN_CONFIDENCE_RULES", OUTPUT_CONFIDENCE_RULES, "refined_mechanism_v11_frozen_confidence_rules"),
        ("REFINED_MECHANISM_V11_FROZEN_CONFLICT_RULES", OUTPUT_CONFLICT_RULES, "refined_mechanism_v11_frozen_conflict_rules"),
        ("REFINED_MECHANISM_V11_FROZEN_FALSIFICATION_RULES", OUTPUT_FALSIFICATION_RULES, "refined_mechanism_v11_frozen_falsification_rules"),
        ("REFINED_MECHANISM_V11_SEPARATION_RULES", OUTPUT_SEPARATION_RULES, "refined_mechanism_v11_separation_rules"),
        ("REFINED_MECHANISM_V11_VERSION_DIFF", OUTPUT_VERSION_DIFF, "refined_mechanism_v11_version_diff"),
        ("REFINED_MECHANISM_V11_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_v11_governance"),
        ("REFINED_MECHANISM_V11_PREREGISTRATION_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_v11_preregistration_summary"),
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
            "notes": "Phase 9A-6R5 refined mechanism v1.1 second preregistration; freeze-only, no dry run or testing execution.",
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


def _build_prereg_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    repair_summary = data["Refined_Mechanism_Repair_Summary"][0]
    rows: List[Dict[str, Any]] = []
    freeze_timestamp = generated_ts
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        future_classification_allowed = "TRUE_FOR_DRY_RUN_ONLY" if role == "PROMOTED_REFINED_MECHANISM" else "FALSE"
        future_testing_allowed = "FALSE"
        independent_classification_allowed = "TRUE" if role == "PROMOTED_REFINED_MECHANISM" else "FALSE"
        independent_testing_allowed = "FALSE"
        supporting_evidence_allowed = "TRUE" if role == "SUBDIMENSION_ONLY" else "FALSE"
        historical_traceability_preserved = "TRUE"
        if role == "PROMOTED_REFINED_MECHANISM":
            status = "FROZEN_READY_FOR_V11_DRY_RUN_ONLY"
            parent_id = "MECH_INFORMATION_VALUE"
        elif role == "SUBDIMENSION_ONLY":
            status = "FROZEN_SUBDIMENSION_ONLY"
            parent_id = "MECH_INFORMATION_VALUE"
        else:
            status = "FROZEN_UMBRELLA_ONLY"
            parent_id = ""
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "baseline_version_reference": BASELINE_VERSION,
                "source_candidate_version": SOURCE_CANDIDATE_VERSION,
                "parent_mechanism_id": parent_id,
                "freeze_timestamp": freeze_timestamp,
                "preregistration_status": "FROZEN",
                "change_allowed_during_dry_run": "FALSE",
                "change_allowed_before_conflict_review": "FALSE",
                "historical_traceability_preserved": historical_traceability_preserved,
                "future_classification_allowed": future_classification_allowed,
                "future_testing_allowed": future_testing_allowed,
                "independent_classification_allowed": independent_classification_allowed,
                "independent_testing_allowed": independent_testing_allowed,
                "supporting_evidence_allowed": supporting_evidence_allowed,
                "definitions_frozen": "TRUE",
                "observables_frozen": "TRUE" if role != "UMBRELLA_ONLY" else "FALSE",
                "label_rules_frozen": "TRUE",
                "confidence_rules_frozen": "TRUE",
                "conflict_rules_frozen": "TRUE",
                "separation_rules_frozen": "TRUE" if role == "PROMOTED_REFINED_MECHANISM" else "TRUE",
                "falsification_rules_frozen": "TRUE",
                "leakage_protections_frozen": "TRUE",
                "dry_run_requirements_frozen": "TRUE",
                "notes": json.dumps(
                    {
                        "source_repair_version": _norm(repair_summary.get("repair_version")),
                        "source_candidate_version": SOURCE_CANDIDATE_VERSION,
                        "status": status,
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                ),
            }
        )
    return rows


def _build_definition_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    candidates = _by_key(data["Refined_Mechanism_v11_Candidate_Definitions"], "mechanism_id")
    baseline_defs = _by_key(data["Refined_Mechanism_Frozen_Definitions"], "mechanism_id")
    scientific_questions = {
        "MECH_INFORMATION_RELEVANCE": "Does the added information directly change the forecast target-driver path or only accompany it?",
        "MECH_INFORMATION_SPECIFICITY": "Does the added information create a forecast-relevant, falsifiable boundary rather than simply adding detail?",
        "MECH_INFORMATION_CONSISTENCY": "Do the selected drivers, causal chain, forecast direction, confidence basis, and uncertainty cues remain in agreement?",
        "MECH_INFORMATION_NOVELTY": "Does the added information introduce a baseline-relative difference without implying direct classifiability?",
        "MECH_INFORMATION_VALUE": "How should the legacy umbrella concept be preserved for traceability without direct reactivation?",
    }
    rows: List[Dict[str, Any]] = []
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        candidate = candidates[mechanism_id]
        baseline = baseline_defs.get(mechanism_id, {})
        if role == "UMBRELLA_ONLY":
            min_evidence = _norm(baseline.get("minimum_evidence"))
            outcome_statement = _norm(baseline.get("outcome_independence_statement"))
            status = "FROZEN_UMBRELLA_ONLY"
        else:
            min_evidence = (
                "Explicit target-driver path trace plus causal-path alignment."
                if mechanism_id == "MECH_INFORMATION_RELEVANCE"
                else "At least one genuine boundary-forming cue with enough trace context to determine whether the boundary is explicit."
                if mechanism_id == "MECH_INFORMATION_SPECIFICITY"
                else "Comparable driver, causal-chain, rationale, or confidence-evidence traces across at least two comparison planes."
                if mechanism_id == "MECH_INFORMATION_CONSISTENCY"
                else _norm(baseline.get("minimum_evidence"))
            )
            outcome_statement = "Use only pre-outcome behavior, transition, field-influence, and no-signal traces. Realized outcomes, corrected outcomes, evaluation metrics, and hindsight interpretation are forbidden."
            status = "FROZEN_EXECUTABLE_V11" if role == "PROMOTED_REFINED_MECHANISM" else "FROZEN_SUBDIMENSION_ONLY"
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": STABLE_ID_MAP[mechanism_id],
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "scientific_definition": _norm(candidate.get("candidate_definition")),
                "scientific_question": scientific_questions[mechanism_id],
                "positive_label_definition": _norm(candidate.get("candidate_positive_definition")),
                "negative_label_definition": _norm(candidate.get("candidate_negative_definition")),
                "unknown_definition": _norm(candidate.get("candidate_unknown_definition")),
                "insufficient_evidence_definition": _norm(candidate.get("candidate_insufficient_evidence_definition")),
                "exclusion_definition": _norm(candidate.get("candidate_exclusion_definition")),
                "minimum_evidence": min_evidence,
                "outcome_independence_statement": outcome_statement,
                "definition_freeze_status": status,
                "notes": "v1.1 definition is frozen and must not change until the v1.1 dry-run and conflict-review cycle completes.",
            }
        )
    return rows


def _build_observable_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    baseline_obs_by_id = _by_key(data["Refined_Mechanism_Frozen_Observables"], "observable_id")
    candidate_obs_by_mech = _group_by(data["Refined_Mechanism_v11_Candidate_Observables"], "mechanism_id")

    specs = [
        {
            "mechanism_id": "MECH_INFORMATION_RELEVANCE",
            "observable_id": "rel_core_target_driver_path",
            "source_ids": ["target_driver_alignment", "field_to_causal_path_alignment", "driver_linkage_depth"],
            "extraction_rule": "Positive only when target-driver alignment and causal-path alignment are explicit and the path change is not merely secondary-only commentary.",
            "positive_role": "Core positive evidence for direct target-driver path change.",
            "negative_role": "Supports a negative label when the added information remains peripheral or secondary-only.",
            "supporting_only": "FALSE",
            "missing_policy": "INSUFFICIENT_EVIDENCE if path or driver linkage cannot be determined.",
            "conflict_handling": "UNKNOWN if target alignment and path alignment diverge without a decisive path-changing signal.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_RELEVANCE",
            "observable_id": "rel_horizon_support_only",
            "source_ids": ["session_horizon_alignment"],
            "extraction_rule": "Detect session or horizon alignment, but never let horizon text alone create a positive relevance label.",
            "positive_role": "Supporting-only context for relevance once path change is otherwise visible.",
            "negative_role": "None by itself; it is not a standalone negative cue.",
            "supporting_only": "TRUE",
            "missing_policy": "Treat as missing support, not as a negative case.",
            "conflict_handling": "If horizon evidence conflicts with path evidence, path evidence dominates.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_SPECIFICITY",
            "observable_id": "spec_falsifiable_boundary_present",
            "source_ids": ["explicit_direction_condition", "explicit_failure_condition", "explicit_no_signal_boundary"],
            "extraction_rule": "Positive only when the row contains a genuine falsifiable boundary: invalidation, abstention boundary, explicit conditional trigger, threshold, regime boundary, or equivalent decision-relevant constraint.",
            "positive_role": "Core positive evidence for specificity.",
            "negative_role": "None directly; absence of a boundary alone does not force negative.",
            "supporting_only": "FALSE",
            "missing_policy": "INSUFFICIENT_EVIDENCE only when the row lacks enough pre-outcome trace to evaluate whether any boundary exists.",
            "conflict_handling": "UNKNOWN when apparent boundaries are partial, pseudo-specific, or internally conflicting.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_SPECIFICITY",
            "observable_id": "spec_generic_direction_restatement",
            "source_ids": ["explicit_direction_condition"],
            "extraction_rule": "Identify rows where direction is restated without a trigger, invalidation rule, abstention boundary, or equivalent falsifiable condition.",
            "positive_role": "None.",
            "negative_role": "Affirmative negative evidence for non-specificity.",
            "supporting_only": "FALSE",
            "missing_policy": "If direction structure is absent, do not infer a negative case from absence alone.",
            "conflict_handling": "If a real boundary exists elsewhere, this cue cannot override it by itself.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_SPECIFICITY",
            "observable_id": "spec_time_horizon_support_only",
            "source_ids": ["explicit_time_horizon"],
            "extraction_rule": "Capture time-horizon narrowing only as supporting evidence; time text becomes positive specificity evidence only when paired with a decision-relevant condition.",
            "positive_role": "Supporting-only specificity cue.",
            "negative_role": "None by itself.",
            "supporting_only": "TRUE",
            "missing_policy": "Missing time detail is not negative evidence.",
            "conflict_handling": "Time-only evidence falls back to supporting status even when the language looks precise.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_SPECIFICITY",
            "observable_id": "spec_missing_invalidation_neutral",
            "source_ids": ["explicit_failure_condition"],
            "extraction_rule": "Treat missing invalidation text as neutral unless other evidence affirmatively shows the row is structurally generic or non-falsifiable.",
            "positive_role": "None.",
            "negative_role": "Can support negative only when paired with affirmative evidence of generic or tautological structure.",
            "supporting_only": "TRUE",
            "missing_policy": "Optional evidence gap only; do not force NEGATIVE from absence alone.",
            "conflict_handling": "Missing invalidation never wins a conflict against explicit boundary evidence.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_CONSISTENCY",
            "observable_id": "cons_decisive_contradiction_priority",
            "source_ids": ["driver_causal_chain_consistency", "direction_rationale_consistency", "confidence_evidence_consistency"],
            "extraction_rule": "Any decisive contradiction in a core comparison plane receives priority over weaker positive cues.",
            "positive_role": "None directly; coherence must still be established elsewhere.",
            "negative_role": "Core negative evidence for inconsistency.",
            "supporting_only": "FALSE",
            "missing_policy": "If comparison planes are absent, use INSUFFICIENT_EVIDENCE rather than inventing a contradiction.",
            "conflict_handling": "A decisive contradiction beats a soft coherence cue.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_CONSISTENCY",
            "observable_id": "cons_cross_field_supporting",
            "source_ids": ["cross_field_consistency", "driver_causal_chain_consistency"],
            "extraction_rule": "Cross-field coherence supports consistency only when it coexists with another coherent comparison plane or at least does not conflict with a decisive contradiction.",
            "positive_role": "Supporting coherence cue.",
            "negative_role": "Can contribute to negative consistency only when it captures a direct contradiction.",
            "supporting_only": "TRUE",
            "missing_policy": "Partial cross-field comparability remains UNKNOWN or INSUFFICIENT_EVIDENCE.",
            "conflict_handling": "Supporting coherence cannot override decisive contradiction priority.",
        },
        {
            "mechanism_id": "MECH_INFORMATION_NOVELTY",
            "observable_id": "nov_baseline_delta_supporting",
            "source_ids": ["new_field_family_introduced", "new_causal_branch_introduced", "new_driver_introduced", "duplicate_information_avoided"],
            "extraction_rule": "Baseline-relative novelty may be recorded as supporting evidence when a new field family, driver, branch, or uncertainty dimension appears without relying on outcomes.",
            "positive_role": "Supporting-only novelty evidence.",
            "negative_role": "None for standalone classification.",
            "supporting_only": "TRUE",
            "missing_policy": "If matched baseline evidence is unavailable, novelty remains INSUFFICIENT_EVIDENCE for supporting purposes only.",
            "conflict_handling": "Any novelty conflict remains supporting-only and cannot become a direct classifiable label.",
        },
    ]

    rows: List[Dict[str, Any]] = []
    for spec in specs:
        mechanism_id = spec["mechanism_id"]
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        candidate_row = next(
            (
                row
                for row in candidate_obs_by_mech.get(mechanism_id, [])
                if _norm(row.get("candidate_observable_id")) == spec["observable_id"]
            ),
            {},
        )
        source_sheet, source_fields = _source_sheet_field_bundle(baseline_obs_by_id, spec["source_ids"])
        if not source_sheet and mechanism_id == "MECH_INFORMATION_NOVELTY":
            source_sheet = "Pack_Behavior_Tier2_Field_Influence; Pack_Behavior_Tier2_Behavior"
            source_fields = "candidate_family; field_available_in_pack; from_pack_level; to_pack_level; causal_chain; primary_driver_summary; secondary_driver_summary; information_used; information_not_used"
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "observable_id": spec["observable_id"],
                "observable_name": _norm(candidate_row.get("candidate_observable_name")) or spec["observable_id"],
                "observable_source_sheet": source_sheet,
                "source_field_or_family": source_fields,
                "extraction_rule": spec["extraction_rule"],
                "positive_evidence_role": spec["positive_role"],
                "negative_evidence_role": spec["negative_role"],
                "supporting_only_status": spec["supporting_only"],
                "missing_evidence_handling": spec["missing_policy"],
                "conflict_handling": spec["conflict_handling"],
                "pre_outcome_availability": "TRUE_WITH_BASELINE" if mechanism_id == "MECH_INFORMATION_NOVELTY" else "TRUE",
                "outcome_independence_statement": "Observable may use only pre-outcome traces. Realized direction, corrected outcomes, market-reaction labels, evaluation metrics, and future information are forbidden.",
                "observable_freeze_status": "FROZEN_EXECUTABLE_V11" if role == "PROMOTED_REFINED_MECHANISM" else "FROZEN_SUPPORTING_ONLY_V11",
                "notes": _norm(candidate_row.get("candidate_definition")) or "v1.1 observable frozen from repaired candidate framework.",
            }
        )
    return rows


def _build_label_rule_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    candidate_rules = _by_key(data["Refined_Mechanism_v11_Candidate_Label_Rules"], "mechanism_id")
    candidate_defs = _by_key(data["Refined_Mechanism_v11_Candidate_Definitions"], "mechanism_id")
    required_obs = {
        "MECH_INFORMATION_RELEVANCE": "rel_core_target_driver_path; rel_horizon_support_only",
        "MECH_INFORMATION_SPECIFICITY": "spec_falsifiable_boundary_present; spec_generic_direction_restatement; spec_time_horizon_support_only; spec_missing_invalidation_neutral",
        "MECH_INFORMATION_CONSISTENCY": "cons_decisive_contradiction_priority; cons_cross_field_supporting",
        "MECH_INFORMATION_NOVELTY": "nov_baseline_delta_supporting",
        "MECH_INFORMATION_VALUE": "NOT_APPLICABLE",
    }
    prohibited = {
        "MECH_INFORMATION_RELEVANCE": "Do not infer relevance from mere verbosity, confidence level, or generic time framing.",
        "MECH_INFORMATION_SPECIFICITY": "Do not infer specificity from generic time-horizon wording, longer rationale, descriptive precision, repeated source data, or absence of invalidation text alone.",
        "MECH_INFORMATION_CONSISTENCY": "Do not infer consistency from repeated wording, duplicated evidence, or mere absence of explicit contradiction when coherence is not comparable.",
        "MECH_INFORMATION_NOVELTY": "Do not convert supporting-only novelty evidence into a standalone classifiable label.",
        "MECH_INFORMATION_VALUE": "Direct umbrella classification is prohibited.",
    }
    confidence_basis = {
        "MECH_INFORMATION_RELEVANCE": "Evidence completeness, rule-path clarity, observable coverage, and unresolved ambiguity only.",
        "MECH_INFORMATION_SPECIFICITY": "Evidence completeness, explicit boundary-cue coverage, rule-path clarity, and unresolved ambiguity only.",
        "MECH_INFORMATION_CONSISTENCY": "Evidence completeness, comparison-plane coverage, rule-path clarity, and unresolved ambiguity only.",
        "MECH_INFORMATION_NOVELTY": "Supporting-only evidence quality relative to matched baseline traces.",
        "MECH_INFORMATION_VALUE": "Not applicable because direct classification is disabled.",
    }
    traceability = {
        "MECH_INFORMATION_RELEVANCE": "Must cite the target-driver path observable trace and any supporting horizon cue used.",
        "MECH_INFORMATION_SPECIFICITY": "Must cite the exact boundary-forming cue or the affirmative non-specificity evidence used.",
        "MECH_INFORMATION_CONSISTENCY": "Must cite which comparison planes produced coherence or contradiction.",
        "MECH_INFORMATION_NOVELTY": "Must cite the baseline-difference trace if supporting-only evidence is recorded.",
        "MECH_INFORMATION_VALUE": "Historical traceability only.",
    }

    rows: List[Dict[str, Any]] = []
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        candidate = candidate_rules.get(mechanism_id, {})
        definition = candidate_defs.get(mechanism_id, {})
        if role == "PROMOTED_REFINED_MECHANISM":
            direct_allowed = "TRUE_FOR_V11_DRY_RUN_ONLY"
            freeze_status = "FROZEN_EXECUTABLE_V11"
            positive_rule = _norm(candidate.get("candidate_positive_rule"))
            negative_rule = _norm(candidate.get("candidate_negative_rule"))
            unknown_rule = _norm(candidate.get("candidate_unknown_rule"))
            insufficient_rule = _norm(candidate.get("candidate_insufficient_evidence_rule"))
            excluded_rule = _norm(candidate.get("candidate_exclusion_rule"))
            conflict_handling = _norm(candidate.get("candidate_conflict_precedence_rule"))
            tie_breaking = _norm(candidate.get("candidate_tie_breaking_rule"))
        elif role == "SUBDIMENSION_ONLY":
            direct_allowed = "FALSE"
            freeze_status = "FROZEN_SUPPORTING_ONLY_V11"
            positive_rule = "Supporting evidence only. Novelty may be recorded relative to baseline but cannot become a standalone positive label."
            negative_rule = "Supporting evidence only. Lack of novelty may be recorded but cannot become a standalone negative label."
            unknown_rule = "Supporting-only UNKNOWN when baseline-relative novelty cannot be separated from repackaging or overlap."
            insufficient_rule = "Supporting-only INSUFFICIENT_EVIDENCE when baseline traces are incomplete."
            excluded_rule = "Direct novelty classification is excluded in v1.1."
            conflict_handling = "SUBDIMENSION_ONLY_SUPPORTING_EVIDENCE"
            tie_breaking = "Not applicable because independent novelty classification is disabled."
        else:
            direct_allowed = "FALSE"
            freeze_status = "FROZEN_UMBRELLA_ONLY"
            positive_rule = "Not applicable. Direct umbrella classification is disabled."
            negative_rule = "Not applicable. Direct umbrella classification is disabled."
            unknown_rule = "Not applicable. Direct umbrella classification is disabled."
            insufficient_rule = "Not applicable. Direct umbrella classification is disabled."
            excluded_rule = "Direct umbrella classification is permanently excluded in v1.1."
            conflict_handling = "UMBRELLA_ONLY_NO_DIRECT_LABELING"
            tie_breaking = "Not applicable because direct classification is disabled."
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "positive_label_rule": positive_rule,
                "negative_label_rule": negative_rule,
                "unknown_label_rule": unknown_rule,
                "insufficient_evidence_rule": insufficient_rule,
                "excluded_rule": excluded_rule,
                "minimum_evidence": _norm(definition.get("minimum_evidence")) or "Not applicable.",
                "required_observables": required_obs[mechanism_id],
                "prohibited_shortcuts": prohibited[mechanism_id],
                "conflict_handling": conflict_handling,
                "tie_breaking_rule": tie_breaking,
                "confidence_assignment_basis": confidence_basis[mechanism_id],
                "traceability_requirements": traceability[mechanism_id],
                "direct_classification_allowed": direct_allowed,
                "label_rule_freeze_status": freeze_status,
                "notes": "v1.1 label rules are frozen and may not change until the v1.1 dry-run and conflict-review cycle complete.",
            }
        )
    return rows


def _build_confidence_rule_rows(
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        if role == "PROMOTED_REFINED_MECHANISM":
            if mechanism_id == "MECH_INFORMATION_SPECIFICITY":
                inputs = "Evidence completeness; explicit boundary-cue coverage; rule-path clarity; unresolved ambiguity; observable coverage. Forecast confidence and realized outcomes are forbidden."
            elif mechanism_id == "MECH_INFORMATION_RELEVANCE":
                inputs = "Evidence completeness; target-driver path clarity; rule-path clarity; unresolved ambiguity; observable coverage. Forecast confidence and realized outcomes are forbidden."
            else:
                inputs = "Evidence completeness; comparison-plane coverage; rule-path clarity; unresolved ambiguity; observable coverage. Forecast confidence and realized outcomes are forbidden."
            high = "HIGH when minimum evidence is complete, the decisive rule path is explicit, no unresolved ambiguity remains, and no conflict downgrade is triggered."
            moderate = "MODERATE when the mechanism is labelable but still carries supporting-only cues, warning-level ambiguity, or partial observable coverage."
            low = "LOW when a label is still assignable but evidence is partial, conflict-sensitive, or overlap-prone."
            unknown = "UNKNOWN when minimum evidence is not met, the row is excluded, or unresolved ambiguity prevents stable confidence assignment."
            levels = "HIGH|MODERATE|LOW|UNKNOWN"
            status = "FROZEN_EXECUTABLE_V11_CONFIDENCE_RULES"
        elif role == "SUBDIMENSION_ONLY":
            levels = "SUPPORTING_ONLY"
            inputs = "Baseline availability; explicit baseline-vs-current difference trace; novelty supporting observables only."
            high = "Not applicable for standalone classification because novelty remains supporting-only."
            moderate = "Supporting-only evidence may be recorded when baseline difference is visible but still cannot become a direct label."
            low = "Assign low support when baseline-difference evidence is partial or confounded by overlap."
            unknown = "UNKNOWN when baseline difference cannot be isolated deterministically."
            status = "FROZEN_SUBDIMENSION_ONLY"
        else:
            levels = "NOT_APPLICABLE"
            inputs = "No direct confidence inputs because umbrella-only classification is disabled."
            high = "Not applicable."
            moderate = "Not applicable."
            low = "Not applicable."
            unknown = "Always not applicable because direct classification is disabled."
            status = "FROZEN_UMBRELLA_ONLY"
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "confidence_levels_allowed": levels,
                "confidence_inputs": inputs,
                "high_confidence_rule": high,
                "moderate_confidence_rule": moderate,
                "low_confidence_rule": low,
                "unknown_confidence_rule": unknown,
                "confidence_rule_freeze_status": status,
                "notes": "Confidence refers only to classification evidence quality and remains outcome-independent.",
            }
        )
    return rows


def _build_conflict_rule_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    candidate_rules = _by_key(data["Refined_Mechanism_v11_Candidate_Label_Rules"], "mechanism_id")
    conflict_sources = {
        "MECH_INFORMATION_RELEVANCE": "Target-driver alignment disagreements; causal-path disagreements; secondary-only driver linkage; supporting-only horizon cues.",
        "MECH_INFORMATION_SPECIFICITY": "Boundary cue disagreements; pseudo-specific time framing; generic direction restatement; missing optional invalidation trace; abstention-boundary ambiguity.",
        "MECH_INFORMATION_CONSISTENCY": "Driver-vs-chain mismatch; rationale-vs-direction mismatch; confidence-vs-evidence mismatch; cross-field comparability gaps.",
        "MECH_INFORMATION_NOVELTY": "Baseline availability gaps; baseline-difference ambiguity; overlap with relevance or specificity.",
        "MECH_INFORMATION_VALUE": "Not applicable because direct umbrella classification is disabled.",
    }
    unresolved_outcome = {
        "MECH_INFORMATION_RELEVANCE": "UNKNOWN",
        "MECH_INFORMATION_SPECIFICITY": "UNKNOWN",
        "MECH_INFORMATION_CONSISTENCY": "UNKNOWN",
        "MECH_INFORMATION_NOVELTY": "SUPPORTING_ONLY_UNKNOWN",
        "MECH_INFORMATION_VALUE": "NOT_APPLICABLE",
    }
    rows: List[Dict[str, Any]] = []
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        candidate = candidate_rules.get(mechanism_id, {})
        if role == "PROMOTED_REFINED_MECHANISM":
            precedence = _norm(candidate.get("candidate_conflict_precedence_rule"))
            tie_break = _norm(candidate.get("candidate_tie_breaking_rule"))
            status = "FROZEN_EXECUTABLE_V11_CONFLICT_RULES"
        elif role == "SUBDIMENSION_ONLY":
            precedence = "SUPPORTING_ONLY_EVIDENCE > UNKNOWN_IF_BASELINE_GAP > EXCLUDED_FOR_DIRECT_CLASSIFICATION"
            tie_break = "Any unresolved novelty conflict remains supporting-only UNKNOWN."
            status = "FROZEN_SUBDIMENSION_ONLY"
        else:
            precedence = "UMBRELLA_ONLY_NO_DIRECT_LABELING"
            tie_break = "Not applicable because direct classification is disabled."
            status = "FROZEN_UMBRELLA_ONLY"
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "conflict_sources": conflict_sources[mechanism_id],
                "conflict_precedence_rule": precedence,
                "unresolved_conflict_outcome": unresolved_outcome[mechanism_id],
                "tie_breaking_rule": tie_break,
                "manual_override_allowed": "FALSE",
                "outcome_leakage_protection": "Conflict resolution may not access realized direction, corrected outcomes, evaluation metrics, or future information.",
                "traceability_requirement": "Every conflict path must cite the observable states and the precedence rule that resolved or preserved the conflict.",
                "conflict_rule_freeze_status": status,
                "notes": "v1.1 conflict rules are frozen and deterministic.",
            }
        )
    return rows


def _build_falsification_rows(
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    spec = {
        "MECH_INFORMATION_RELEVANCE": {
            "rule": "The classifier fails if it cannot distinguish direct target-driver path alignment from general contextual mention or peripheral detail.",
            "contradiction": "Rows that mention related context without changing the target-driver path are still labeled positive relevance.",
            "minimum": "At least 60 non-excluded dry-run rows with explicit target-driver or causal-path trace coverage.",
            "conflict_warning": ">0.15 of previewed rows",
            "ambiguity_warning": ">0.25 of previewed rows",
            "trigger": "Review if peripheral-detail negatives fail to appear or if relevance remains overly positive despite mixed path evidence.",
        },
        "MECH_INFORMATION_SPECIFICITY": {
            "rule": "The classifier fails if it labels generic detail, time framing, or descriptive precision as boundary-forming specificity.",
            "contradiction": "Rows without a genuine falsifiable boundary are labeled positive specificity, or absence of invalidation text alone generates negatives.",
            "minimum": "At least 60 non-excluded dry-run rows with reviewable boundary-cue coverage.",
            "conflict_warning": ">0.15 of previewed rows",
            "ambiguity_warning": ">0.30 of previewed rows",
            "trigger": "Review if time-only or relevance-only rows still dominate specificity ambiguity or if optional evidence gaps recreate auto-negative behavior.",
        },
        "MECH_INFORMATION_CONSISTENCY": {
            "rule": "The classifier fails if it cannot distinguish genuine agreement from repeated wording, duplicated evidence, or unresolved contradiction.",
            "contradiction": "Rows with decisive contradiction remain positive or rows with only repeated wording are treated as coherent evidence.",
            "minimum": "At least 60 non-excluded dry-run rows with at least two comparison planes observable across a material subset.",
            "conflict_warning": ">0.15 of previewed rows",
            "ambiguity_warning": ">0.25 of previewed rows",
            "trigger": "Review if decisive contradictions do not produce negative labels or if cross-field repetition is mistaken for consistency.",
        },
        "MECH_INFORMATION_NOVELTY": {
            "rule": "Novelty remains supporting-only unless a future phase separately promotes it after new evidence and preregistration.",
            "contradiction": "Any attempt to turn novelty supporting evidence into a standalone executable label violates the v1.1 preregistration.",
            "minimum": "Matched baseline evidence must be available before supporting novelty evidence is recorded.",
            "conflict_warning": "NOT_APPLICABLE_FOR_DIRECT_CLASSIFICATION",
            "ambiguity_warning": "NOT_APPLICABLE_FOR_DIRECT_CLASSIFICATION",
            "trigger": "Review if baseline-difference support cannot be isolated deterministically.",
        },
        "MECH_INFORMATION_VALUE": {
            "rule": "The umbrella mechanism remains non-executable and non-testable.",
            "contradiction": "Any attempt to restore direct umbrella classification or testing violates v1.1.",
            "minimum": "Not applicable.",
            "conflict_warning": "NOT_APPLICABLE",
            "ambiguity_warning": "NOT_APPLICABLE",
            "trigger": "Any attempt to re-enable direct umbrella execution requires a new refinement branch.",
        },
    }
    rows: List[Dict[str, Any]] = []
    for mechanism_id in ALL_MECHANISMS:
        role = _role_for(mechanism_id)
        stable_id = STABLE_ID_MAP[mechanism_id]
        item = spec[mechanism_id]
        status = (
            "FROZEN_EXECUTABLE_V11_FALSIFICATION_RULES"
            if role == "PROMOTED_REFINED_MECHANISM"
            else "FROZEN_SUPPORTING_ONLY"
            if role == "SUBDIMENSION_ONLY"
            else "FROZEN_UMBRELLA_ONLY"
        )
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "stable_mechanism_id": stable_id,
                "mechanism_id": mechanism_id,
                "mechanism_role": role,
                "falsification_rule": item["rule"],
                "contradictory_evidence_definition": item["contradiction"],
                "minimum_dry_run_evidence": item["minimum"],
                "conflict_threshold_warning": item["conflict_warning"],
                "ambiguity_threshold_warning": item["ambiguity_warning"],
                "review_trigger": item["trigger"],
                "classification_execution_blocker": "TRUE",
                "falsification_rule_freeze_status": status,
                "notes": "Falsification rules are frozen before the v1.1 dry run and remain outcome-independent.",
            }
        )
    return rows


def _build_separation_rows(
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    rows = [
        {
            **_base(generated_ts, preregistration_run_id),
            "refined_mechanism_version": REFINED_MECHANISM_VERSION,
            "mechanism_a": "MECH_INFORMATION_RELEVANCE",
            "mechanism_b": "MECH_INFORMATION_SPECIFICITY",
            "mechanism_a_question": "Does the information pertain directly to the forecast target, stated driver, causal path, or evaluation horizon?",
            "mechanism_b_question": "Does the information create a falsifiable boundary that constrains when, why, or under what condition the forecast applies or fails?",
            "joint_positive_allowed": "TRUE",
            "mechanism_a_does_not_imply_b": "TRUE",
            "mechanism_b_does_not_imply_a": "TRUE",
            "separation_rule": "Relevance alone must never imply specificity. Specificity-positive classification requires a boundary-forming cue, not just target alignment.",
            "negative_case_example": "A row can be relevance-positive and specificity-negative when it adds target-relevant detail without narrowing the claim.",
            "supporting_only_cues": "Generic time framing and contextual elaboration remain supporting-only unless paired with a boundary-forming cue.",
            "separation_rule_freeze_status": "FROZEN_V11",
            "notes": "Joint positive is allowed when information is both target-aligned and boundary-forming.",
        },
        {
            **_base(generated_ts, preregistration_run_id),
            "refined_mechanism_version": REFINED_MECHANISM_VERSION,
            "mechanism_a": "MECH_INFORMATION_SPECIFICITY",
            "mechanism_b": "MECH_INFORMATION_CONSISTENCY",
            "mechanism_a_question": "Does the information create a falsifiable boundary?",
            "mechanism_b_question": "Do the selected drivers, causal chain, forecast direction, confidence basis, and uncertainty cues remain in agreement?",
            "joint_positive_allowed": "TRUE",
            "mechanism_a_does_not_imply_b": "TRUE",
            "mechanism_b_does_not_imply_a": "TRUE",
            "separation_rule": "Consistency concerns internal agreement; specificity concerns boundary formation. A coherent but vague row may be consistent and non-specific, and a specific row may still be inconsistent.",
            "negative_case_example": "A row can be consistency-positive and specificity-negative when it is coherent but structurally generic.",
            "supporting_only_cues": "Coherence cues may support interpretation but cannot substitute for a falsifiable boundary.",
            "separation_rule_freeze_status": "FROZEN_V11",
            "notes": "This rule directly addresses the repaired specificity-consistency overlap.",
        },
        {
            **_base(generated_ts, preregistration_run_id),
            "refined_mechanism_version": REFINED_MECHANISM_VERSION,
            "mechanism_a": "MECH_INFORMATION_RELEVANCE",
            "mechanism_b": "MECH_INFORMATION_CONSISTENCY",
            "mechanism_a_question": "Does the information belong on the target-driver path?",
            "mechanism_b_question": "Does the information agree internally with the chosen forecast logic?",
            "joint_positive_allowed": "TRUE",
            "mechanism_a_does_not_imply_b": "TRUE",
            "mechanism_b_does_not_imply_a": "TRUE",
            "separation_rule": "Relevant evidence may contradict the forecast, and consistent evidence may remain peripheral to the primary target.",
            "negative_case_example": "A row can be relevance-positive and consistency-negative when it introduces target-relevant but contradictory evidence.",
            "supporting_only_cues": "Peripheral coherence does not make information relevant to the primary target.",
            "separation_rule_freeze_status": "FROZEN_V11",
            "notes": "This pair already had acceptable overlap, but the v1.1 rule freezes its boundary explicitly.",
        },
    ]
    return rows


def _build_version_diff_rows(
    data: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
    preregistration_run_id: str,
) -> List[Dict[str, Any]]:
    change_log_rows = data["Refined_Mechanism_v11_Change_Log"]
    baseline_defs = _by_key(data["Refined_Mechanism_Frozen_Definitions"], "mechanism_id")
    baseline_rules = _by_key(data["Refined_Mechanism_Frozen_Label_Rules"], "mechanism_id")
    candidate_defs = _by_key(data["Refined_Mechanism_v11_Candidate_Definitions"], "mechanism_id")
    candidate_rules = _by_key(data["Refined_Mechanism_v11_Candidate_Label_Rules"], "mechanism_id")

    meaning_flags = {
        "RMR-001": ("TRUE", "FALSE"),
        "RMR-002": ("TRUE", "FALSE"),
        "RMR-003": ("TRUE", "FALSE"),
        "RMR-004": ("FALSE", "TRUE"),
        "RMR-005": ("TRUE", "FALSE"),
        "RMR-006": ("TRUE", "FALSE"),
        "RMR-007": ("TRUE", "FALSE"),
        "RMR-008": ("FALSE", "TRUE"),
        "RMR-009": ("TRUE", "FALSE"),
        "RMR-010": ("TRUE", "FALSE"),
        "RMR-011": ("FALSE", "TRUE"),
        "RMR-012": ("FALSE", "TRUE"),
    }

    rows: List[Dict[str, Any]] = []
    for row in change_log_rows:
        change_id = _norm(row.get("change_id"))
        mechanism_id = _norm(row.get("mechanism_id"))
        component_type = _norm(row.get("change_area"))
        baseline_def = baseline_defs.get(mechanism_id, {})
        baseline_rule = baseline_rules.get(mechanism_id, {})
        candidate_def = candidate_defs.get(mechanism_id, {})
        candidate_rule = candidate_rules.get(mechanism_id, {})
        if component_type == "DEFINITION":
            v1_0_rule = _norm(baseline_def.get("scientific_definition"))
            v1_1_rule = _norm(candidate_def.get("candidate_definition"))
        elif component_type == "POSITIVE_RULE":
            v1_0_rule = _norm(baseline_rule.get("positive_label_rule"))
            v1_1_rule = _norm(candidate_rule.get("candidate_positive_rule"))
        elif component_type == "NEGATIVE_RULE":
            v1_0_rule = _norm(baseline_rule.get("negative_label_rule"))
            v1_1_rule = _norm(candidate_rule.get("candidate_negative_rule"))
        elif component_type == "FAILURE_OBSERVABLE":
            v1_0_rule = "Missing invalidation could push explicit_failure_condition toward negative pressure."
            v1_1_rule = "Missing invalidation is neutral unless affirmative genericity evidence is present."
        elif component_type == "SUPPORTING_CUES":
            v1_0_rule = "Horizon alignment could contribute too directly to positive classification."
            v1_1_rule = "Horizon alignment is supporting-only unless core evidence is present."
        elif component_type.startswith("OVERLAP_GATE"):
            v1_0_rule = "Pairwise boundary was insufficiently frozen in v1.0."
            v1_1_rule = _norm(row.get("candidate_element"))
        elif component_type == "EXCLUSION_RULES":
            v1_0_rule = "Hard exclusions and optional evidence gaps were not sharply distinguished."
            v1_1_rule = "Hard exclusions stay fixed; optional evidence gaps become neutral/insufficient/negative depending on affirmative evidence."
        elif component_type == "PROCESS_GATE":
            v1_0_rule = "v1.0 freeze existed only for the earlier cycle."
            v1_1_rule = "v1.1 must be frozen before any second dry-run cycle."
        else:
            v1_0_rule = _norm(row.get("baseline_element"))
            v1_1_rule = _norm(row.get("candidate_element"))
        scientific_meaning_changed, operational_clarity_changed = meaning_flags.get(change_id, ("TRUE", "FALSE"))
        rows.append(
            {
                **_base(generated_ts, preregistration_run_id),
                "refined_mechanism_version": REFINED_MECHANISM_VERSION,
                "component_id": change_id,
                "mechanism_id": mechanism_id,
                "component_type": component_type,
                "v1_0_rule": v1_0_rule,
                "v1_1_rule": v1_1_rule,
                "scientific_reason": _norm(row.get("why_change_exists")),
                "source_conflict_finding": _norm(row.get("source_evidence")),
                "expected_classification_effect": _norm(row.get("expected_effect")),
                "scientific_meaning_changed": scientific_meaning_changed,
                "operational_clarity_changed": operational_clarity_changed,
                "notes": "This diff row is descriptive only; it does not claim that ambiguity has improved before the next dry run.",
            }
        )
    return rows


def build_refined_mechanism_v11_second_preregistration_v0() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials())
    generated_ts = _iso_now()
    preregistration_run_id = _preregistration_run_id(generated_ts)
    data = _read_inputs(service)

    prereg_rows = _build_prereg_rows(data, generated_ts, preregistration_run_id)
    definition_rows = _build_definition_rows(data, generated_ts, preregistration_run_id)
    observable_rows = _build_observable_rows(data, generated_ts, preregistration_run_id)
    label_rule_rows = _build_label_rule_rows(data, generated_ts, preregistration_run_id)
    confidence_rule_rows = _build_confidence_rule_rows(generated_ts, preregistration_run_id)
    conflict_rule_rows = _build_conflict_rule_rows(data, generated_ts, preregistration_run_id)
    falsification_rows = _build_falsification_rows(generated_ts, preregistration_run_id)
    separation_rows = _build_separation_rows(generated_ts, preregistration_run_id)
    version_diff_rows = _build_version_diff_rows(data, generated_ts, preregistration_run_id)

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_DRY_RUN", "classification_dry_run_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_REALIZED_OUTCOMES", "realized_outcomes_accessed", "0", "0"),
        ("GOV_CORRECTED_OUTCOMES", "corrected_outcomes_accessed", "0", "0"),
        ("GOV_V10_MODIFIED", "v1_0_sheets_modified", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, preregistration_run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "v1.1 second preregistration is freeze-only and non-executing.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    summary_row = {
        **_base(generated_ts, preregistration_run_id),
        "refined_mechanism_version": REFINED_MECHANISM_VERSION,
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "REFINED_MECHANISM_V11_PREREGISTRATION_READY_WITH_WARNINGS",
        "refined_mechanisms_frozen": len(PROMOTED_MECHANISMS),
        "stable_ids_preserved": len(ALL_MECHANISMS),
        "definitions_frozen": len(definition_rows),
        "observables_frozen": len(observable_rows),
        "label_rules_frozen": len(label_rule_rows),
        "confidence_rules_frozen": len(confidence_rule_rows),
        "conflict_rules_frozen": len(conflict_rule_rows),
        "separation_rules_frozen": len(separation_rows),
        "falsification_rules_frozen": len(falsification_rows),
        "version_differences_recorded": len(version_diff_rows),
        "parent_mechanism_status": "UMBRELLA_ONLY",
        "novelty_subdimension_status": "SUBDIMENSION_ONLY",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_dry_run_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v1_0_sheets_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_refined_classification_dry_run": "TRUE",
        "ready_for_permanent_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": NEXT_STEP,
        "notes": json.dumps(
            {
                "baseline_version_reference": BASELINE_VERSION,
                "source_candidate_version": SOURCE_CANDIDATE_VERSION,
                "specificity_primary_change": "falsifiable_boundary_gate",
                "v1_0_preregistration_preserved": True,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
    }

    outputs = [
        (OUTPUT_PREREG, PREREG_HEADERS, prereg_rows),
        (OUTPUT_DEFINITIONS, DEFINITION_HEADERS, definition_rows),
        (OUTPUT_OBSERVABLES, OBSERVABLE_HEADERS, observable_rows),
        (OUTPUT_LABEL_RULES, LABEL_RULE_HEADERS, label_rule_rows),
        (OUTPUT_CONFIDENCE_RULES, CONFIDENCE_RULE_HEADERS, confidence_rule_rows),
        (OUTPUT_CONFLICT_RULES, CONFLICT_RULE_HEADERS, conflict_rule_rows),
        (OUTPUT_FALSIFICATION_RULES, FALSIFICATION_RULE_HEADERS, falsification_rows),
        (OUTPUT_SEPARATION_RULES, SEPARATION_RULE_HEADERS, separation_rows),
        (OUTPUT_VERSION_DIFF, VERSION_DIFF_HEADERS, version_diff_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]

    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": "PASS_WITH_WARNINGS",
        "final_interpretation": "REFINED_MECHANISM_V11_PREREGISTRATION_READY_WITH_WARNINGS",
        "file_created": "automation/build_refined_mechanism_v11_second_preregistration_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "preregistration_version": REFINED_MECHANISM_VERSION,
        "refined_mechanisms_frozen": len(PROMOTED_MECHANISMS),
        "stable_ids_preserved": len(ALL_MECHANISMS),
        "definitions_frozen": len(definition_rows),
        "observables_frozen": len(observable_rows),
        "label_rules_frozen": len(label_rule_rows),
        "confidence_rules_frozen": len(confidence_rule_rows),
        "conflict_rules_frozen": len(conflict_rule_rows),
        "separation_rules_frozen": len(separation_rows),
        "falsification_rules_frozen": len(falsification_rows),
        "version_differences_recorded": len(version_diff_rows),
        "parent_mechanism_status": "UMBRELLA_ONLY",
        "subdimension_status": "SUBDIMENSION_ONLY",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_dry_run_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v1_0_sheets_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_v11_refined_classification_dry_run": True,
        "ready_for_permanent_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_replication": False,
        "ready_for_production": False,
        "recommended_next_step": NEXT_STEP,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_v11_second_preregistration_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
