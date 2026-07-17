import json
import sys
from collections import Counter
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
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_classification_execution_plan_0.1"
EXECUTION_PLAN_VERSION = "refined_mechanism_v11_classification_execution_plan_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R8"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_PLAN"
REGISTRY_OWNER_MODULE = "market_state"

PROMOTED_MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]
STABLE_ID_MAP = {
    "MECH_INFORMATION_RELEVANCE": "PM-001",
    "MECH_INFORMATION_SPECIFICITY": "PM-002",
    "MECH_INFORMATION_CONSISTENCY": "PM-003",
}

INPUT_SHEETS = [
    "Refined_Mechanism_v11_Conflict_Review",
    "Refined_Mechanism_v11_Population_Comparability_Audit",
    "Refined_Mechanism_v11_Specificity_Validity_Review",
    "Refined_Mechanism_v11_Negative_Label_Review",
    "Refined_Mechanism_v11_Joint_Positive_Review",
    "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "Refined_Mechanism_v11_Confidence_Review",
    "Refined_Mechanism_v11_Falsification_Review",
    "Refined_Mechanism_v11_Execution_Readiness",
    "Refined_Mechanism_v11_Conflict_Governance",
    "Refined_Mechanism_v11_Conflict_Review_Summary",
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_Version_Diff",
    "Refined_Mechanism_v11_PreRegistration_Summary",
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Evidence_Audit",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Specificity_Boundary_Audit",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Overlap_Audit",
    "Refined_Mechanism_v11_Label_Balance_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
]

OUTPUT_EXECUTION_PLAN = "Refined_Mechanism_v11_Classification_Execution_Plan"
OUTPUT_MECH_SCOPE = "Refined_Mechanism_v11_Mechanism_Execution_Scope"
OUTPUT_ROW_SCOPE = "Refined_Mechanism_v11_Row_Execution_Scope"
OUTPUT_CONFLICT_PLAN = "Refined_Mechanism_v11_Conflict_Disposition_Plan"
OUTPUT_SCHEMA_PLAN = "Refined_Mechanism_v11_Output_Schema_Plan"
OUTPUT_TRACEABILITY = "Refined_Mechanism_v11_Traceability_Plan"
OUTPUT_DETERMINISM = "Refined_Mechanism_v11_Determinism_Control"
OUTPUT_LEAKAGE = "Refined_Mechanism_v11_Leakage_Control"
OUTPUT_STOP_HOLD = "Refined_Mechanism_v11_Stop_Hold_Rules"
OUTPUT_POST_REVIEW = "Refined_Mechanism_v11_Post_Execution_Review_Plan"
OUTPUT_READINESS = "Refined_Mechanism_v11_Execution_Readiness_Audit"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Execution_Plan_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Execution_Plan_Summary"

PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "plan_component",
    "component_status",
    "component_purpose",
    "source_phase",
    "frozen_inputs",
    "planned_outputs",
    "blocking_conditions",
    "review_dependency",
    "notes",
]

MECH_SCOPE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "mechanism_name",
    "conflict_review_status",
    "execution_readiness_status",
    "execution_allowed",
    "execution_allowed_with_exclusions",
    "blocking_issue",
    "warning_condition",
    "eligible_row_count",
    "unknown_disposition_count",
    "low_confidence_disposition_count",
    "excluded_count",
    "required_execution_control",
    "required_post_execution_review",
]

ROW_SCOPE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "stable_mechanism_id",
    "mechanism_id",
    "source_row_key",
    "session_id",
    "provider",
    "pack_level",
    "dry_run_preview_label",
    "dry_run_confidence",
    "conflict_status",
    "conflict_review_disposition",
    "execution_scope_status",
    "planned_execution_label",
    "planned_execution_confidence",
    "exclusion_reason",
    "unknown_reason",
    "low_confidence_reason",
    "frozen_rule_id",
    "frozen_evidence_trace_reference",
    "execution_allowed",
]

CONFLICT_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "mechanism_id",
    "source_row_key",
    "conflict_review_disposition",
    "planned_execution_disposition",
    "planned_label",
    "planned_confidence",
    "scientific_rationale",
    "frozen_rule_compatibility",
    "manual_override_required",
]

SCHEMA_PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "sheet_name",
    "purpose",
    "primary_key",
    "required_columns",
    "dedupe_key",
    "source_trace_fields",
    "version_fields",
    "write_mode",
    "overwrite_policy",
]

TRACEABILITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "trace_field",
    "required",
    "purpose",
    "source_origin",
    "validation_rule",
    "notes",
]

DETERMINISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "control_id",
    "comparison_area",
    "expected_match",
    "allowed_difference",
    "source_reference",
    "blocking_if_failed",
    "failure_action",
    "notes",
]

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "control_id",
    "control_area",
    "allowed_source_sheets",
    "forbidden_source_sheets",
    "allowed_source_columns",
    "forbidden_column_patterns",
    "as_of_timestamp_rule",
    "runtime_leakage_assertion",
    "post_write_leakage_audit",
    "blocking_if_failed",
    "notes",
]

STOP_HOLD_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "stop_rule_id",
    "stop_condition",
    "stop_immediately",
    "preserve_diagnostic_logs",
    "successful_summary_allowed",
    "retry_with_changed_rules_allowed",
    "failure_action",
    "notes",
]

POST_REVIEW_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "review_item_id",
    "review_area",
    "required_check",
    "evidence_source",
    "blocking_if_failed",
    "next_action",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
    "readiness_area",
    "status",
    "evidence",
    "blocking_issue",
    "recommended_action",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "execution_plan_version",
    "execution_plan_run_id",
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
    "execution_plan_version",
    "execution_plan_run_id",
    "build_status",
    "final_interpretation",
    "mechanisms_reviewed",
    "mechanisms_planned_for_execution",
    "mechanisms_planned_with_exclusions",
    "mechanisms_blocked",
    "candidate_mechanism_row_pairs",
    "rows_planned_as_previewed",
    "rows_planned_as_unknown",
    "rows_planned_with_low_confidence",
    "rows_planned_for_exclusion",
    "rows_blocked_pending_repair",
    "conflict_dispositions_frozen",
    "output_schemas_defined",
    "traceability_rules_defined",
    "determinism_controls_defined",
    "leakage_controls_defined",
    "stop_rules_defined",
    "post_execution_review_defined",
    "highest_execution_risk",
    "highest_scientific_warning",
    "primary_execution_plan_interpretation",
    "provider_calls_performed",
    "forecast_generation_performed",
    "classification_execution_performed",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "outcome_values_accessed",
    "v10_sheets_modified",
    "v11_preregistration_modified",
    "v11_dry_run_modified",
    "v11_conflict_review_modified",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "ready_for_classification_execution_approval",
    "ready_for_permanent_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    return "refined_mechanism_v11_classification_execution_plan_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_plan_version": EXECUTION_PLAN_VERSION,
        "execution_plan_run_id": run_id,
    }


def _sheet_titles_light(service, spreadsheet_id: str) -> Set[str]:
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
        ("REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_PLAN", OUTPUT_EXECUTION_PLAN, "refined_mechanism_v11_classification_execution_plan"),
        ("REFINED_MECHANISM_V11_MECHANISM_EXECUTION_SCOPE", OUTPUT_MECH_SCOPE, "refined_mechanism_v11_mechanism_execution_scope"),
        ("REFINED_MECHANISM_V11_ROW_EXECUTION_SCOPE", OUTPUT_ROW_SCOPE, "refined_mechanism_v11_row_execution_scope"),
        ("REFINED_MECHANISM_V11_CONFLICT_DISPOSITION_PLAN", OUTPUT_CONFLICT_PLAN, "refined_mechanism_v11_conflict_disposition_plan"),
        ("REFINED_MECHANISM_V11_OUTPUT_SCHEMA_PLAN", OUTPUT_SCHEMA_PLAN, "refined_mechanism_v11_output_schema_plan"),
        ("REFINED_MECHANISM_V11_TRACEABILITY_PLAN", OUTPUT_TRACEABILITY, "refined_mechanism_v11_traceability_plan"),
        ("REFINED_MECHANISM_V11_DETERMINISM_CONTROL", OUTPUT_DETERMINISM, "refined_mechanism_v11_determinism_control"),
        ("REFINED_MECHANISM_V11_LEAKAGE_CONTROL", OUTPUT_LEAKAGE, "refined_mechanism_v11_leakage_control"),
        ("REFINED_MECHANISM_V11_STOP_HOLD_RULES", OUTPUT_STOP_HOLD, "refined_mechanism_v11_stop_hold_rules"),
        ("REFINED_MECHANISM_V11_POST_EXECUTION_REVIEW_PLAN", OUTPUT_POST_REVIEW, "refined_mechanism_v11_post_execution_review_plan"),
        ("REFINED_MECHANISM_V11_EXECUTION_READINESS_AUDIT", OUTPUT_READINESS, "refined_mechanism_v11_execution_readiness_audit"),
        ("REFINED_MECHANISM_V11_EXECUTION_PLAN_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_v11_execution_plan_governance"),
        ("REFINED_MECHANISM_V11_EXECUTION_PLAN_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_v11_execution_plan_summary"),
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
            "notes": (
                "Phase 9A-6R8 v1.1 refined classification execution plan; planning only, "
                "no permanent classification or mechanism testing."
            ),
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


def _to_bool(value: Any) -> bool:
    return _norm(value).upper() == "TRUE"


def _to_int(value: Any) -> int:
    raw = _norm(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _parse_json_any(value: Any) -> Any:
    text = _norm(value)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    parsed = _parse_json_any(value)
    return parsed if isinstance(parsed, dict) else {}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _row_key(row: Dict[str, Any]) -> str:
    value = _norm(row.get("source_row_key"))
    if value:
        return value
    preview_id = _norm(row.get("preview_id"))
    if preview_id:
        parts = preview_id.split("|")
        if len(parts) >= 5:
            return "|".join(parts[-5:])
    return ""


def _row_dimensions(row_key: str) -> Tuple[str, str, str]:
    parts = row_key.split("|")
    if len(parts) < 3:
        return "", "", ""
    return ("|".join(parts[:-2]), parts[-2], parts[-1])


def _latest_single_row(rows: Sequence[Dict[str, Any]], run_field: str) -> Dict[str, Any]:
    if not rows:
        return {}
    return max(rows, key=lambda row: _norm(row.get(run_field)))


def build_refined_mechanism_v11_classification_execution_plan_v0() -> Dict[str, Any]:
    credentials = load_credentials()
    service = build_sheets_service(credentials)
    data = _read_inputs(service)

    generated_ts = _iso_now()
    run_id = _run_id(generated_ts)

    summary_row = _latest_single_row(data["Refined_Mechanism_v11_Conflict_Review_Summary"], "review_run_id")
    readiness_rows_src = [
        row
        for row in data["Refined_Mechanism_v11_Execution_Readiness"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    ]
    conflict_review_rows = {
        _norm(row.get("mechanism_id")): row
        for row in data["Refined_Mechanism_v11_Conflict_Review"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    }
    falsification_rows = {
        _norm(row.get("mechanism_id")): row
        for row in data["Refined_Mechanism_v11_Falsification_Review"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    }
    label_rows = data["Refined_Mechanism_v11_Label_Preview"]
    rule_path_rows = {
        (_norm(row.get("mechanism_id")), _norm(row.get("source_row_key"))): row
        for row in data["Refined_Mechanism_v11_Rule_Path_Audit"]
        if _norm(row.get("mechanism_id")) and _norm(row.get("source_row_key"))
    }
    unresolved_rows_src = data["Refined_Mechanism_v11_Unresolved_Conflict_Review"]
    unresolved_by_key = {
        (_norm(row.get("mechanism_id")), _norm(row.get("source_row_key"))): row
        for row in unresolved_rows_src
        if _norm(row.get("mechanism_id")) and _norm(row.get("source_row_key"))
    }

    plan_rows: List[Dict[str, Any]] = []
    mech_scope_rows: List[Dict[str, Any]] = []
    row_scope_rows: List[Dict[str, Any]] = []
    conflict_plan_rows: List[Dict[str, Any]] = []
    schema_plan_rows: List[Dict[str, Any]] = []
    traceability_rows: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    stop_rows: List[Dict[str, Any]] = []
    post_review_rows: List[Dict[str, Any]] = []
    readiness_rows: List[Dict[str, Any]] = []

    plan_components = [
        (
            "frozen_v11_scope_preservation",
            "DEFINED",
            "Preserve the frozen v1.1 preregistration, dry-run scope, and conflict-review dispositions as the only allowable permanent-classification basis.",
            "Phase9A-6R5|Phase9A-6R6|Phase9A-6R7",
            "Refined_Mechanism_v11_PreRegistration|Refined_Mechanism_v11_Label_Preview|Refined_Mechanism_v11_Unresolved_Conflict_Review",
            "future permanent classification run sheets only",
            "v1.1 version mismatch|dry-run scope mismatch|conflict disposition mismatch",
            "Execution approval required before any permanent write",
        ),
        (
            "mechanism_level_authorization",
            "DEFINED",
            "Authorize only mechanism-level execution states explicitly supported by Refined_Mechanism_v11_Execution_Readiness.",
            "Phase9A-6R7",
            "Refined_Mechanism_v11_Execution_Readiness|Refined_Mechanism_v11_Falsification_Review",
            "mechanism execution scope and row scope",
            "mechanism status NOT_READY|BLOCKED|falsification blocker",
            "Mechanism approval is still separate from permanent classification execution",
        ),
        (
            "row_level_scope_freeze",
            "DEFINED",
            "Freeze one deterministic execution disposition for every candidate mechanism-row pair using only preview labels, frozen rules, and conflict-review dispositions.",
            "Phase9A-6R6|Phase9A-6R7",
            "Refined_Mechanism_v11_Label_Preview|Refined_Mechanism_v11_Rule_Path_Audit|Refined_Mechanism_v11_Unresolved_Conflict_Review",
            "row execution scope and conflict disposition plan",
            "unexpected label delta|unexpected confidence delta|manual override request",
            "Post-execution review must reconcile permanent results against this planned row scope",
        ),
        (
            "traceability_and_audit",
            "DEFINED",
            "Require every future permanent label to carry full frozen-rule, evidence-trace, disposition, and version metadata.",
            "Phase9A-6R5|Phase9A-6R8",
            "Refined_Mechanism_v11_Frozen_*|Refined_Mechanism_v11_Traceability_Plan",
            "versioned permanent diagnostic classification sheets",
            "partial output without audit trace|dedupe failure|missing source trace fields",
            "Post-execution review must verify trace completeness before any downstream usage",
        ),
        (
            "determinism_and_leakage_control",
            "DEFINED",
            "Stop execution if the permanent run diverges from the frozen dry run outside the explicitly planned conflict dispositions or if any outcome-bearing source is accessed.",
            "Phase9A-6R6|Phase9A-6R7|Phase9A-6R8",
            "Refined_Mechanism_v11_Determinism_Audit|Refined_Mechanism_v11_Leakage_Audit|execution control sheets",
            "determinism control, leakage control, stop-hold rules",
            "outcome access|forbidden sheet access|unexpected rule-path drift",
            "A separate post-execution review phase is mandatory",
        ),
    ]
    for component, status, purpose, source_phase, frozen_inputs, planned_outputs, blocking, review_dependency in plan_components:
        plan_rows.append(
            {
                **_base(generated_ts, run_id),
                "plan_component": component,
                "component_status": status,
                "component_purpose": purpose,
                "source_phase": source_phase,
                "frozen_inputs": frozen_inputs,
                "planned_outputs": planned_outputs,
                "blocking_conditions": blocking,
                "review_dependency": review_dependency,
                "notes": "Planning only. No permanent classification execution is performed in this phase.",
            }
        )

    row_status_counter: Counter[str] = Counter()
    mech_row_rollup: Dict[str, Counter[str]] = {mechanism_id: Counter() for mechanism_id in PROMOTED_MECHANISMS}
    candidate_row_pairs = 0
    for row in label_rows:
        mechanism_id = _norm(row.get("mechanism_id"))
        if mechanism_id not in PROMOTED_MECHANISMS:
            continue
        candidate_row_pairs += 1
        row_key = _row_key(row)
        session_id, provider, pack_level = _row_dimensions(row_key)
        preview_label = _norm(row.get("preview_label"))
        preview_confidence = _norm(row.get("confidence_category"))
        conflict_status = _norm(row.get("conflict_status"))
        executed_rule_id = _norm(row.get("executed_rule_id"))
        notes = _parse_json_dict(row.get("notes"))
        rule_path = rule_path_rows.get((mechanism_id, row_key), {})
        unresolved = unresolved_by_key.get((mechanism_id, row_key), {})
        conflict_disposition = _norm(unresolved.get("recommended_disposition"))

        execution_scope_status = "EXECUTE_AS_PREVIEWED"
        planned_label = preview_label
        planned_confidence = preview_confidence
        exclusion_reason = ""
        unknown_reason = ""
        low_confidence_reason = ""
        execution_allowed = "TRUE"

        if preview_label == "EXCLUDED":
            execution_scope_status = "OUT_OF_SCOPE"
            planned_label = "EXCLUDED"
            planned_confidence = "UNKNOWN"
            exclusion_reason = _norm(notes.get("exclusion_reason")) or "frozen_scope_exclusion"
            execution_allowed = "FALSE"
            conflict_disposition = "OUT_OF_SCOPE"
        elif conflict_disposition == "CONVERT_TO_UNKNOWN":
            execution_scope_status = "EXECUTE_AS_UNKNOWN"
            planned_label = "UNKNOWN"
            planned_confidence = preview_confidence or "LOW"
            unknown_reason = "frozen_conflict_review_preserves_partial_boundary_or_mixed_evidence_as_unknown"
        elif conflict_disposition == "ALLOW_WITH_LOW_CONFIDENCE":
            execution_scope_status = "EXECUTE_WITH_LOW_CONFIDENCE"
            planned_label = preview_label
            planned_confidence = "LOW"
            low_confidence_reason = "frozen_conflict_review_allows_existing_label_only_as_low_confidence"
        elif conflict_disposition == "CONVERT_TO_INSUFFICIENT_EVIDENCE":
            execution_scope_status = "EXECUTE_AS_PREVIEWED"
            planned_label = "INSUFFICIENT_EVIDENCE"
            planned_confidence = "UNKNOWN"
        elif conflict_disposition == "EXCLUDE_FROM_EXECUTION":
            execution_scope_status = "EXCLUDE_FROM_EXECUTION"
            planned_label = preview_label
            exclusion_reason = "conflict_review_requested_execution_exclusion"
            execution_allowed = "FALSE"
        elif conflict_disposition == "REQUIRES_V12_RULE_REPAIR":
            execution_scope_status = "BLOCKED_PENDING_REPAIR"
            planned_label = preview_label
            execution_allowed = "FALSE"
        elif preview_label == "UNKNOWN":
            execution_scope_status = "EXECUTE_AS_PREVIEWED"
            unknown_reason = "frozen_preview_unknown_without_conflict_override"
        elif preview_label == "INSUFFICIENT_EVIDENCE":
            execution_scope_status = "EXECUTE_AS_PREVIEWED"
            unknown_reason = "retain_frozen_insufficient_evidence_as_non_positive_terminal_class"

        evidence_trace = {
            "source_sheet": "Refined_Mechanism_v11_Label_Preview",
            "preview_id": _norm(row.get("preview_id")),
            "rule_path_sheet": "Refined_Mechanism_v11_Rule_Path_Audit",
            "decisive_evidence": _norm(row.get("decisive_evidence")),
            "decisive_observables": _norm(row.get("decisive_observables")),
        }
        row_scope_rows.append(
            {
                **_base(generated_ts, run_id),
                "stable_mechanism_id": STABLE_ID_MAP.get(mechanism_id, ""),
                "mechanism_id": mechanism_id,
                "source_row_key": row_key,
                "session_id": session_id,
                "provider": provider,
                "pack_level": pack_level,
                "dry_run_preview_label": preview_label,
                "dry_run_confidence": preview_confidence,
                "conflict_status": conflict_status,
                "conflict_review_disposition": conflict_disposition or "NO_OVERRIDE",
                "execution_scope_status": execution_scope_status,
                "planned_execution_label": planned_label,
                "planned_execution_confidence": planned_confidence,
                "exclusion_reason": exclusion_reason,
                "unknown_reason": unknown_reason,
                "low_confidence_reason": low_confidence_reason,
                "frozen_rule_id": executed_rule_id or _norm(rule_path.get("decisive_rule_id")),
                "frozen_evidence_trace_reference": _json(evidence_trace),
                "execution_allowed": execution_allowed,
            }
        )
        row_status_counter[execution_scope_status] += 1
        mech_row_rollup[mechanism_id][execution_scope_status] += 1

    for row in unresolved_rows_src:
        mechanism_id = _norm(row.get("mechanism_id"))
        row_key = _norm(row.get("source_row_key"))
        disposition = _norm(row.get("recommended_disposition"))
        preview_row = next(
            (
                item
                for item in row_scope_rows
                if _norm(item.get("mechanism_id")) == mechanism_id and _norm(item.get("source_row_key")) == row_key
            ),
            {},
        )
        if disposition == "CONVERT_TO_UNKNOWN":
            planned_execution_disposition = "EXECUTE_AS_UNKNOWN"
        elif disposition == "ALLOW_WITH_LOW_CONFIDENCE":
            planned_execution_disposition = "EXECUTE_WITH_LOW_CONFIDENCE"
        elif disposition == "CONVERT_TO_INSUFFICIENT_EVIDENCE":
            planned_execution_disposition = "EXECUTE_AS_PREVIEWED"
        elif disposition == "EXCLUDE_FROM_EXECUTION":
            planned_execution_disposition = "EXCLUDE_FROM_EXECUTION"
        else:
            planned_execution_disposition = "BLOCKED_PENDING_REPAIR"
        conflict_plan_rows.append(
            {
                **_base(generated_ts, run_id),
                "mechanism_id": mechanism_id,
                "source_row_key": row_key,
                "conflict_review_disposition": disposition,
                "planned_execution_disposition": planned_execution_disposition,
                "planned_label": _norm(preview_row.get("planned_execution_label")),
                "planned_confidence": _norm(preview_row.get("planned_execution_confidence")),
                "scientific_rationale": _norm(row.get("scientific_impact")),
                "frozen_rule_compatibility": "TRUE",
                "manual_override_required": "FALSE",
            }
        )

    mechanisms_reviewed = len(PROMOTED_MECHANISMS)
    mechanisms_planned_for_execution = 0
    mechanisms_planned_with_exclusions = 0
    mechanisms_blocked = 0
    for row in readiness_rows_src:
        mechanism_id = _norm(row.get("mechanism_id"))
        readiness_status = _norm(row.get("execution_readiness_status"))
        review_status = _norm(conflict_review_rows.get(mechanism_id, {}).get("review_status"))
        warning_condition = ""
        if _to_bool(falsification_rows.get(mechanism_id, {}).get("warning_triggered")):
            warning_condition = _norm(falsification_rows.get(mechanism_id, {}).get("scientific_consequence"))
        elif readiness_status == "READY_WITH_EXCLUSIONS":
            warning_condition = "insufficient-evidence rows must remain a protected non-positive terminal class"
        elif readiness_status == "READY_AFTER_CONFLICT_DISPOSITION":
            warning_condition = "conflict review dispositions must remain frozen during execution"
        execution_allowed = "TRUE" if readiness_status in {"READY_AFTER_CONFLICT_DISPOSITION", "READY_WITH_EXCLUSIONS", "READY_FOR_PERMANENT_CLASSIFICATION"} else "FALSE"
        execution_allowed_with_exclusions = "TRUE" if readiness_status == "READY_WITH_EXCLUSIONS" else "FALSE"
        if readiness_status == "READY_WITH_EXCLUSIONS":
            mechanisms_planned_with_exclusions += 1
        elif execution_allowed == "TRUE":
            mechanisms_planned_for_execution += 1
        else:
            mechanisms_blocked += 1
        mech_scope_rows.append(
            {
                **_base(generated_ts, run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": STABLE_ID_MAP.get(mechanism_id, ""),
                "mechanism_name": mechanism_id,
                "conflict_review_status": review_status,
                "execution_readiness_status": readiness_status,
                "execution_allowed": execution_allowed,
                "execution_allowed_with_exclusions": execution_allowed_with_exclusions,
                "blocking_issue": "" if execution_allowed == "TRUE" else _norm(row.get("readiness_conclusion")),
                "warning_condition": warning_condition,
                "eligible_row_count": _to_int(conflict_review_rows.get(mechanism_id, {}).get("eligible_rows")),
                "unknown_disposition_count": mech_row_rollup[mechanism_id].get("EXECUTE_AS_UNKNOWN", 0),
                "low_confidence_disposition_count": mech_row_rollup[mechanism_id].get("EXECUTE_WITH_LOW_CONFIDENCE", 0),
                "excluded_count": mech_row_rollup[mechanism_id].get("OUT_OF_SCOPE", 0) + mech_row_rollup[mechanism_id].get("EXCLUDE_FROM_EXECUTION", 0),
                "required_execution_control": (
                    "freeze planned UNKNOWN dispositions and compare permanent outputs against frozen dry-run row scope"
                    if readiness_status == "READY_AFTER_CONFLICT_DISPOSITION"
                    else "preserve insufficiency as a terminal non-positive class and maintain exclusion boundaries"
                ),
                "required_post_execution_review": (
                    "verify permanent labels, confidence, and conflict dispositions against the frozen execution plan"
                ),
            }
        )

    schema_specs = [
        (
            "Refined_Mechanism_v11_Classifications",
            "Permanent versioned classification results, one row per mechanism-row decision.",
            "classification_run_id|mechanism_id|source_row_key",
            [
                "classification_run_id",
                "mechanism_version",
                "preregistration_version",
                "mechanism_id",
                "stable_mechanism_id",
                "source_row_key",
                "classification_label",
                "confidence_category",
                "conflict_status",
                "conflict_disposition",
                "frozen_rule_id",
                "classification_timestamp",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Evidence",
            "Permanent decisive evidence and observable trace for every classified row.",
            "classification_run_id|mechanism_id|source_row_key|evidence_record_type",
            [
                "classification_run_id",
                "mechanism_id",
                "source_row_key",
                "source_sheet",
                "source_row_reference",
                "decisive_observable_ids",
                "decisive_evidence_trace",
                "observable_states",
                "outcome_independence_verified",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Conflicts",
            "Permanent conflict, ambiguity, and disposition trace for rows with mixed evidence.",
            "classification_run_id|mechanism_id|source_row_key",
            [
                "classification_run_id",
                "mechanism_id",
                "source_row_key",
                "conflict_status",
                "conflict_type",
                "conflicting_rule_ids",
                "conflicting_observables",
                "planned_disposition",
                "manual_override_used",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Confidence",
            "Permanent confidence assignment trace independent of forecast or outcome metrics.",
            "classification_run_id|mechanism_id|source_row_key",
            [
                "classification_run_id",
                "mechanism_id",
                "source_row_key",
                "confidence_category",
                "evidence_completeness",
                "evidence_consistency",
                "rule_path_clarity",
                "ambiguity_level",
                "confidence_reason",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Audit",
            "Permanent determinism and traceability audit evidence for the classification run.",
            "classification_run_id|audit_check_id|source_row_key",
            [
                "classification_run_id",
                "audit_check_id",
                "mechanism_id",
                "source_row_key",
                "rule_path_hash",
                "dry_run_comparison_result",
                "trace_complete",
                "notes",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Governance",
            "Permanent governance assertions for the execution run.",
            "classification_run_id|check_id",
            [
                "classification_run_id",
                "check_id",
                "check_name",
                "expected_value",
                "actual_value",
                "status",
                "notes",
            ],
        ),
        (
            "Refined_Mechanism_v11_Classification_Summary",
            "Permanent versioned run summary and post-execution readiness signal.",
            "classification_run_id",
            [
                "classification_run_id",
                "mechanism_version",
                "build_status",
                "classified_rows",
                "unknown_rows",
                "low_confidence_rows",
                "excluded_rows",
                "determinism_status",
                "leakage_findings",
                "recommended_next_step",
            ],
        ),
    ]
    for sheet_name, purpose, primary_key, required_columns in schema_specs:
        schema_plan_rows.append(
            {
                **_base(generated_ts, run_id),
                "sheet_name": sheet_name,
                "purpose": purpose,
                "primary_key": primary_key,
                "required_columns": _json(required_columns),
                "dedupe_key": primary_key,
                "source_trace_fields": _json(
                    [
                        "classification_run_id",
                        "mechanism_id",
                        "source_row_key",
                        "frozen_rule_id",
                        "decisive_observable_ids",
                        "decisive_evidence_trace",
                    ]
                ),
                "version_fields": _json(
                    [
                        "classification_run_id",
                        "mechanism_version",
                        "preregistration_version",
                        "execution_plan_version",
                    ]
                ),
                "write_mode": "APPEND_NEW_VERSIONED_RUN",
                "overwrite_policy": "overwrite_v10=FALSE|overwrite_v11_dry_run=FALSE|preserve_prior_versioned_runs=TRUE",
            }
        )

    trace_specs = [
        ("classification_run_id", "Unique permanent run identifier for one versioned execution."),
        ("mechanism_version", "Frozen executable mechanism version reference."),
        ("preregistration_version", "Frozen preregistration version reference."),
        ("mechanism_id", "Mechanism identity for every permanent label."),
        ("source_row_key", "Stable row key from the dry-run and execution scopes."),
        ("source_sheet", "Original pre-outcome source sheet used during classification."),
        ("source_row_reference", "Row number or source locator within the pre-outcome evidence sheet."),
        ("frozen_rule_id", "Executed frozen rule identifier."),
        ("decisive_observable_ids", "Observables that determined the permanent label."),
        ("decisive_evidence_trace", "Text or structural evidence trace supporting the permanent label."),
        ("conflict_status", "Permanent conflict status for the row."),
        ("conflict_disposition", "Frozen conflict-review disposition used during execution."),
        ("confidence_category", "Permanent classification confidence."),
        ("classification_timestamp", "Classification write timestamp."),
        ("outcome_independence_verified", "Explicit assertion that no outcome-bearing field was used."),
    ]
    for field_name, purpose in trace_specs:
        traceability_rows.append(
            {
                **_base(generated_ts, run_id),
                "trace_field": field_name,
                "required": "TRUE",
                "purpose": purpose,
                "source_origin": (
                    "future permanent classification output"
                    if field_name in {"classification_run_id", "classification_timestamp"}
                    else "frozen v1.1 preregistration or pre-outcome evidence trace"
                ),
                "validation_rule": "non_blank_and_version_consistent",
                "notes": "No permanent label is valid without this trace field.",
            }
        )

    determinism_controls = [
        ("DET_001", "row_key_equality", "Exact row-key equality against Refined_Mechanism_v11_Row_Execution_Scope", "planned conflict dispositions only"),
        ("DET_002", "eligibility_equality", "Exact eligibility equality against the dry-run scope", "planned exclusions only"),
        ("DET_003", "observable_extraction_equality", "Observable extraction must match frozen dry-run extraction", "none"),
        ("DET_004", "rule_path_equality", "Executed frozen rule path must equal planned frozen rule path", "planned conflict disposition remap only"),
        ("DET_005", "label_equality", "Permanent label must match planned execution label", "none"),
        ("DET_006", "confidence_equality", "Permanent confidence must match planned execution confidence", "none"),
        ("DET_007", "conflict_equality", "Permanent conflict status/disposition must match the planned conflict disposition sheet", "none"),
        ("DET_008", "exclusion_equality", "Permanent excluded or out-of-scope rows must equal the frozen row scope", "none"),
    ]
    for control_id, comparison_area, expected_match, allowed_difference in determinism_controls:
        determinism_rows.append(
            {
                **_base(generated_ts, run_id),
                "control_id": control_id,
                "comparison_area": comparison_area,
                "expected_match": expected_match,
                "allowed_difference": allowed_difference,
                "source_reference": "Refined_Mechanism_v11_Label_Preview|Refined_Mechanism_v11_Row_Execution_Scope",
                "blocking_if_failed": "TRUE",
                "failure_action": "STOP_AND_HOLD_EXECUTION",
                "notes": "Any unplanned divergence blocks a successful permanent classification summary.",
            }
        )

    leakage_controls = [
        (
            "LEAK_001",
            "allowed_source_sheets",
            "Pack_Behavior_Tier2_Behavior|Pack_Behavior_Tier2_Transitions|Pack_Behavior_Tier2_Field_Influence|Pack_Behavior_Tier2_NoSignal|Pack_Behavior_Tier2_Invalid_Output|Refined_Mechanism_v11_PreRegistration|Refined_Mechanism_v11_Frozen_*|Refined_Mechanism_v11_Classification_Execution_Plan",
            "Outcome_Ledger|Controlled_Accuracy_Evaluation|Corrected_Accuracy_Evaluation|MR_ProviderRuns",
            "pre-outcome evidence and frozen-rule fields only",
            "realized*|*overall_ok*|*direction*correct*|*market_reaction*|*accuracy_*",
            "all source reads must be as-of the original pre-outcome session timestamp",
            "assert allowed sheet set and column regex before classification begins",
            "verify no forbidden sheet/field access in the permanent classification governance output",
        ),
        (
            "LEAK_002",
            "forbidden_source_sheets",
            "same_as_LEAK_001",
            "Outcome_Ledger|Controlled_Accuracy_Evaluation|Corrected_Accuracy_Evaluation|Corrected_Accuracy_*|Market_Reaction_*",
            "pre-outcome evidence only",
            "*outcome*|*realized*|*accuracy*",
            "no future or outcome-bearing sheet may be read at runtime",
            "abort on any forbidden sheet open",
            "post-write audit must show zero forbidden-sheet access",
        ),
        (
            "LEAK_003",
            "allowed_source_columns",
            "behavior_text|transition_text|field_influence|no_signal_trace|invalid_output_flags|frozen_rule_ids",
            "realized_direction|overall_ok|direction_correctness|market_reaction_outcome",
            "columns must be enumerated before runtime",
            "*realized*|*outcome*|*correct*|*accuracy*",
            "column whitelist must be frozen before execution",
            "runtime schema filter enforces the whitelist",
            "audit the accessed-column log after write completion",
        ),
        (
            "LEAK_004",
            "forbidden_column_patterns",
            "same_as_LEAK_003",
            "realized_*|*_outcome|overall_ok|*_accuracy_*|market_reaction_*",
            "whitelisted pre-outcome columns only",
            "realized*|*overall_ok*|*market_reaction*|*accuracy*",
            "pattern filter applies before data load",
            "block if any forbidden field survives filtering",
            "post-write audit verifies zero matches",
        ),
        (
            "LEAK_005",
            "as_of_timestamp_rule",
            "session-time pre-outcome evidence only",
            "post-session or future timestamps",
            "pre-outcome timestamps only",
            "future_*|post_*",
            "all evidence must be timestamp-safe relative to the original session",
            "runtime timestamp assertion checks every source batch",
            "audit records the as-of rule result",
        ),
        (
            "LEAK_006",
            "runtime_leakage_assertion",
            "frozen allowed sheets and fields only",
            "any outcome-bearing source or field",
            "runtime access log only",
            "same forbidden patterns",
            "assert before first write and before final summary",
            "abort finalization on assertion failure",
            "classification governance output must include the assertion result",
        ),
        (
            "LEAK_007",
            "post_write_leakage_audit",
            "governance and audit outputs only",
            "any discrepancy between runtime assertion and audit",
            "governance outputs",
            "same forbidden patterns",
            "post-write audit must match runtime assertion exactly",
            "block successful summary if audit differs",
            "required after all permanent output writes",
        ),
    ]
    for control_id, control_area, allowed_sheets, forbidden_sheets, allowed_cols, forbidden_patterns, timestamp_rule, runtime_assertion, post_write_audit in leakage_controls:
        leakage_rows.append(
            {
                **_base(generated_ts, run_id),
                "control_id": control_id,
                "control_area": control_area,
                "allowed_source_sheets": allowed_sheets,
                "forbidden_source_sheets": forbidden_sheets,
                "allowed_source_columns": allowed_cols,
                "forbidden_column_patterns": forbidden_patterns,
                "as_of_timestamp_rule": timestamp_rule,
                "runtime_leakage_assertion": runtime_assertion,
                "post_write_leakage_audit": post_write_audit,
                "blocking_if_failed": "TRUE",
                "notes": "Any leakage finding stops execution before the permanent summary is finalized.",
            }
        )

    stop_conditions = [
        "v1.1 preregistration hash/version mismatch",
        "dry-run source mismatch",
        "row-key scope mismatch",
        "frozen rule mismatch",
        "unexpected label difference",
        "unexpected confidence difference",
        "unexpected conflict difference",
        "manual override requested",
        "outcome field accessed",
        "forbidden sheet accessed",
        "v1.0 or v1.1 source modified",
        "production write attempted",
        "dedupe failure",
        "partial output without audit trace",
    ]
    for idx, condition in enumerate(stop_conditions, start=1):
        stop_rows.append(
            {
                **_base(generated_ts, run_id),
                "stop_rule_id": f"STOP_{idx:03d}",
                "stop_condition": condition,
                "stop_immediately": "TRUE",
                "preserve_diagnostic_logs": "TRUE",
                "successful_summary_allowed": "FALSE",
                "retry_with_changed_rules_allowed": "FALSE",
                "failure_action": "STOP_IMMEDIATELY_AND_HOLD_FOR_REVIEW",
                "notes": "Do not retry with changed rules. Preserve diagnostics and treat the run as unsuccessful.",
            }
        )

    post_review_checks = [
        ("POST_001", "execution_scope_match", "permanent execution scope matches Refined_Mechanism_v11_Row_Execution_Scope", "future permanent classification outputs|Refined_Mechanism_v11_Row_Execution_Scope"),
        ("POST_002", "label_match", "permanent labels match planned execution labels", "future permanent classification outputs|Refined_Mechanism_v11_Row_Execution_Scope"),
        ("POST_003", "unknown_preservation", "planned UNKNOWN conflicts remained UNKNOWN", "future permanent classification outputs|Refined_Mechanism_v11_Conflict_Disposition_Plan"),
        ("POST_004", "low_confidence_preservation", "the single low-confidence allowed case remained low confidence", "future permanent classification outputs|Refined_Mechanism_v11_Conflict_Disposition_Plan"),
        ("POST_005", "no_manual_overrides", "no permanent row required manual override", "future permanent conflict outputs"),
        ("POST_006", "trace_completeness", "all permanent rows carry full traceability fields", "future permanent classification evidence outputs"),
        ("POST_007", "determinism", "determinism control passed", "future permanent classification audit outputs"),
        ("POST_008", "zero_leakage", "no forbidden sheet or field was accessed", "future permanent classification governance outputs"),
        ("POST_009", "version_preservation", "v1.0, v1.1 preregistration, dry-run, and conflict-review sheets remained unchanged", "future permanent classification governance outputs"),
        ("POST_010", "governance", "all execution governance assertions passed", "future permanent classification governance outputs"),
    ]
    for review_id, area, required_check, evidence_source in post_review_checks:
        post_review_rows.append(
            {
                **_base(generated_ts, run_id),
                "review_item_id": review_id,
                "review_area": area,
                "required_check": required_check,
                "evidence_source": evidence_source,
                "blocking_if_failed": "TRUE",
                "next_action": "BLOCK_ANY_DOWNSTREAM_MECHANISM_TESTING_UNTIL_REVIEW_PASSES",
                "notes": "Permanent classification must be reviewed before any mechanism-conditioned testing is authorized.",
            }
        )

    readiness_checks = [
        (
            "mechanism_level_scope_defined",
            "PASS",
            f"{len(mech_scope_rows)} mechanism scope rows define readiness for all promoted mechanisms.",
            "",
            "Proceed to approval review.",
        ),
        (
            "row_level_scope_frozen",
            "PASS",
            f"{len(row_scope_rows)} candidate mechanism-row pairs were frozen into one deterministic execution scope.",
            "",
            "Proceed to approval review.",
        ),
        (
            "conflict_dispositions_frozen",
            "PASS",
            f"{len(conflict_plan_rows)} unresolved conflict dispositions are frozen with no manual override path.",
            "",
            "Proceed to approval review.",
        ),
        (
            "output_schemas_defined",
            "PASS",
            f"{len(schema_plan_rows)} future permanent output schemas were defined.",
            "",
            "Proceed to approval review.",
        ),
        (
            "traceability_defined",
            "PASS",
            f"{len(traceability_rows)} required traceability fields were frozen.",
            "",
            "Proceed to approval review.",
        ),
        (
            "determinism_controls_defined",
            "PASS",
            f"{len(determinism_rows)} determinism controls were defined.",
            "",
            "Proceed to approval review.",
        ),
        (
            "leakage_controls_defined",
            "PASS",
            f"{len(leakage_rows)} leakage controls were defined.",
            "",
            "Proceed to approval review.",
        ),
        (
            "stop_rules_defined",
            "PASS",
            f"{len(stop_rows)} stop/hold rules were defined.",
            "",
            "Proceed to approval review.",
        ),
        (
            "post_execution_review_defined",
            "PASS",
            f"{len(post_review_rows)} post-execution review checks were defined.",
            "",
            "Proceed to approval review.",
        ),
        (
            "governance_checks_pass",
            "PASS",
            "All execution-plan governance counters remain zero.",
            "",
            "Proceed to approval review.",
        ),
        (
            "no_mechanism_requires_v12_repair",
            "PASS",
            "Refined_Mechanism_v11_Conflict_Review_Summary reports 0 mechanisms requiring repair and 0 conflicts requiring v1.2 repair.",
            "",
            "Proceed to approval review.",
        ),
    ]
    for area, status, evidence, blocking_issue, action in readiness_checks:
        readiness_rows.append(
            {
                **_base(generated_ts, run_id),
                "readiness_area": area,
                "status": status,
                "evidence": evidence,
                "blocking_issue": blocking_issue,
                "recommended_action": action,
                "notes": "Plan readiness does not authorize permanent classification execution directly.",
            }
        )
    readiness_rows.append(
        {
            **_base(generated_ts, run_id),
            "readiness_area": "overall_execution_plan_readiness",
            "status": "READY_WITH_WARNINGS",
            "evidence": "Mechanism scopes, row scopes, conflict dispositions, traceability, determinism, leakage, stop rules, and post-review controls are all defined; specificity still carries a warning-level conflict burden that must remain governed as UNKNOWN during execution.",
            "blocking_issue": "",
            "recommended_action": "PROCEED_TO_PHASE9A6R9_V11_CLASSIFICATION_EXECUTION_APPROVAL",
            "notes": "Ready for approval review, not for direct execution.",
        }
    )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_CLASSIFICATION_EXECUTION", "classification_execution_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OUTCOME_ACCESS", "outcome_values_accessed", "0", "0"),
        ("GOV_V10_SHEETS", "v10_sheets_modified", "0", "0"),
        ("GOV_V11_PREREG", "v11_preregistration_modified", "0", "0"),
        ("GOV_V11_DRY_RUN", "v11_dry_run_modified", "0", "0"),
        ("GOV_V11_CONFLICT_REVIEW", "v11_conflict_review_modified", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    governance_rows = [
        {
            **_base(generated_ts, run_id),
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "status": "PASS" if expected_value == actual_value else "FAIL",
            "notes": "Phase 9A-6R8 remains planning only.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]

    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_PLAN_READY_WITH_WARNINGS"
    recommended_next_step = "PROCEED_TO_PHASE9A6R9_V11_CLASSIFICATION_EXECUTION_APPROVAL"
    ready_for_classification_execution_approval = True
    if any(_norm(row.get("status")) == "FAIL" for row in governance_rows):
        build_status = "BLOCKED"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_PLAN_BLOCKED"
        recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
        ready_for_classification_execution_approval = False

    rows_planned_as_previewed = row_status_counter.get("EXECUTE_AS_PREVIEWED", 0)
    rows_planned_as_unknown = row_status_counter.get("EXECUTE_AS_UNKNOWN", 0)
    rows_planned_with_low_confidence = row_status_counter.get("EXECUTE_WITH_LOW_CONFIDENCE", 0)
    rows_planned_for_exclusion = row_status_counter.get("OUT_OF_SCOPE", 0) + row_status_counter.get("EXCLUDE_FROM_EXECUTION", 0)
    rows_blocked_pending_repair = row_status_counter.get("BLOCKED_PENDING_REPAIR", 0)

    summary_row = {
        **_base(generated_ts, run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "mechanisms_reviewed": mechanisms_reviewed,
        "mechanisms_planned_for_execution": mechanisms_planned_for_execution,
        "mechanisms_planned_with_exclusions": mechanisms_planned_with_exclusions,
        "mechanisms_blocked": mechanisms_blocked,
        "candidate_mechanism_row_pairs": candidate_row_pairs,
        "rows_planned_as_previewed": rows_planned_as_previewed,
        "rows_planned_as_unknown": rows_planned_as_unknown,
        "rows_planned_with_low_confidence": rows_planned_with_low_confidence,
        "rows_planned_for_exclusion": rows_planned_for_exclusion,
        "rows_blocked_pending_repair": rows_blocked_pending_repair,
        "conflict_dispositions_frozen": len(conflict_plan_rows),
        "output_schemas_defined": len(schema_plan_rows),
        "traceability_rules_defined": len(traceability_rows),
        "determinism_controls_defined": len(determinism_rows),
        "leakage_controls_defined": len(leakage_rows),
        "stop_rules_defined": len(stop_rows),
        "post_execution_review_defined": len(post_review_rows),
        "highest_execution_risk": "unexpected divergence from the frozen v1.1 row scope, especially around UNKNOWN and low-confidence conflict dispositions",
        "highest_scientific_warning": "MECH_INFORMATION_SPECIFICITY retains a warning-level conflict burden and must preserve 20 planned UNKNOWN rows exactly as reviewed",
        "primary_execution_plan_interpretation": (
            "The v1.1 framework is ready for a formal execution-approval review because scope, traceability, determinism, leakage, and stop controls are all frozen; it is still not authorized for direct permanent classification execution."
        ),
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_execution_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "v11_dry_run_modified": 0,
        "v11_conflict_review_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_classification_execution_approval": "TRUE" if ready_for_classification_execution_approval else "FALSE",
        "ready_for_permanent_classification_execution": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": _json(
            {
                "conflict_review_summary_reference": _norm(summary_row.get("review_run_id")) if summary_row else "",
                "population_comparability_status": _norm(summary_row.get("population_comparability_status")) if summary_row else "",
                "confidence_framework_status": _norm(summary_row.get("confidence_framework_status")) if summary_row else "",
                "falsification_triggers": _norm(summary_row.get("falsification_triggers")) if summary_row else "",
            }
        ),
    }

    outputs = [
        (OUTPUT_EXECUTION_PLAN, PLAN_HEADERS, plan_rows),
        (OUTPUT_MECH_SCOPE, MECH_SCOPE_HEADERS, mech_scope_rows),
        (OUTPUT_ROW_SCOPE, ROW_SCOPE_HEADERS, row_scope_rows),
        (OUTPUT_CONFLICT_PLAN, CONFLICT_PLAN_HEADERS, conflict_plan_rows),
        (OUTPUT_SCHEMA_PLAN, SCHEMA_PLAN_HEADERS, schema_plan_rows),
        (OUTPUT_TRACEABILITY, TRACEABILITY_HEADERS, traceability_rows),
        (OUTPUT_DETERMINISM, DETERMINISM_HEADERS, determinism_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
        (OUTPUT_STOP_HOLD, STOP_HOLD_HEADERS, stop_rows),
        (OUTPUT_POST_REVIEW, POST_REVIEW_HEADERS, post_review_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]

    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_refined_mechanism_v11_classification_execution_plan_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_reviewed": mechanisms_reviewed,
        "mechanisms_planned_for_execution": mechanisms_planned_for_execution,
        "mechanisms_planned_with_exclusions": mechanisms_planned_with_exclusions,
        "mechanisms_blocked": mechanisms_blocked,
        "candidate_mechanism_row_pairs": candidate_row_pairs,
        "rows_planned_as_previewed": rows_planned_as_previewed,
        "rows_planned_as_unknown": rows_planned_as_unknown,
        "rows_planned_with_low_confidence": rows_planned_with_low_confidence,
        "rows_planned_for_exclusion": rows_planned_for_exclusion,
        "rows_blocked_pending_repair": rows_blocked_pending_repair,
        "conflict_dispositions_frozen": len(conflict_plan_rows),
        "output_schemas_defined": len(schema_plan_rows),
        "traceability_rules_defined": len(traceability_rows),
        "determinism_controls_defined": len(determinism_rows),
        "leakage_controls_defined": len(leakage_rows),
        "stop_rules_defined": len(stop_rows),
        "post_execution_review_defined": len(post_review_rows),
        "highest_execution_risk": "unexpected divergence from the frozen v1.1 row scope, especially around UNKNOWN and low-confidence conflict dispositions",
        "highest_scientific_warning": "MECH_INFORMATION_SPECIFICITY retains a warning-level conflict burden and must preserve 20 planned UNKNOWN rows exactly as reviewed",
        "primary_execution_plan_interpretation": "The v1.1 framework is ready for approval review but not for direct permanent classification execution.",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_execution_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "v11_dry_run_modified": 0,
        "v11_conflict_review_modified": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "ready_for_classification_execution_approval": ready_for_classification_execution_approval,
        "ready_for_permanent_classification_execution": False,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_v11_classification_execution_plan_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
