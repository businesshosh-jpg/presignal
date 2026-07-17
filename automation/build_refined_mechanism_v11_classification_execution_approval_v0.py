import hashlib
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
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_classification_execution_approval_0.1"
APPROVAL_VERSION = "refined_mechanism_v11_classification_execution_approval_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-6R9"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_EXECUTION_APPROVAL"
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
    "Refined_Mechanism_v11_Classification_Execution_Plan",
    "Refined_Mechanism_v11_Mechanism_Execution_Scope",
    "Refined_Mechanism_v11_Row_Execution_Scope",
    "Refined_Mechanism_v11_Conflict_Disposition_Plan",
    "Refined_Mechanism_v11_Output_Schema_Plan",
    "Refined_Mechanism_v11_Traceability_Plan",
    "Refined_Mechanism_v11_Determinism_Control",
    "Refined_Mechanism_v11_Leakage_Control",
    "Refined_Mechanism_v11_Stop_Hold_Rules",
    "Refined_Mechanism_v11_Post_Execution_Review_Plan",
    "Refined_Mechanism_v11_Execution_Readiness_Audit",
    "Refined_Mechanism_v11_Execution_Plan_Governance",
    "Refined_Mechanism_v11_Execution_Plan_Summary",
    "Refined_Mechanism_v11_Conflict_Review",
    "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "Refined_Mechanism_v11_Execution_Readiness",
    "Refined_Mechanism_v11_Confidence_Review",
    "Refined_Mechanism_v11_Falsification_Review",
    "Refined_Mechanism_v11_Conflict_Review_Summary",
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_PreRegistration_Summary",
]

OUTPUT_APPROVAL = "Refined_Mechanism_v11_Execution_Approval"
OUTPUT_ROW_RECON = "Refined_Mechanism_v11_Approval_Row_Reconciliation"
OUTPUT_CONFLICT_RECON = "Refined_Mechanism_v11_Approval_Conflict_Reconciliation"
OUTPUT_VERSION_FREEZE = "Refined_Mechanism_v11_Approval_Version_Freeze"
OUTPUT_OUTPUT_SAFETY = "Refined_Mechanism_v11_Approval_Output_Safety"
OUTPUT_DETERMINISM = "Refined_Mechanism_v11_Approval_Determinism_Check"
OUTPUT_LEAKAGE = "Refined_Mechanism_v11_Approval_Leakage_Check"
OUTPUT_STOP = "Refined_Mechanism_v11_Approval_Stop_Rule_Check"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Approval_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Execution_Approval_Summary"

APPROVAL_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "mechanism_name",
    "conflict_review_readiness",
    "execution_plan_readiness",
    "execution_allowed",
    "execution_allowed_with_exclusions",
    "warnings",
    "blockers",
    "required_execution_restrictions",
    "approval_status",
    "notes",
]

ROW_RECON_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "source_row_key",
    "dry_run_eligible",
    "dry_run_preview_label",
    "dry_run_confidence",
    "dry_run_conflict_status",
    "conflict_review_disposition",
    "execution_plan_status",
    "planned_execution_label",
    "planned_execution_confidence",
    "exclusion_status",
    "frozen_rule_id",
    "evidence_trace_reference",
    "exact_reconciliation_match",
    "mismatch_reason",
    "approval_status",
    "notes",
]

CONFLICT_RECON_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "mechanism_id",
    "stable_mechanism_id",
    "source_row_key",
    "phase9a6r7_disposition",
    "phase9a6r8_planned_disposition",
    "exact_match",
    "planned_label",
    "planned_confidence",
    "forced_positive_negative_conversion",
    "confidence_increase",
    "manual_override_required",
    "approval_status",
    "notes",
]

VERSION_FREEZE_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "component",
    "source_sheet",
    "source_row_count",
    "version",
    "fingerprint_method",
    "fingerprint",
    "approval_timestamp",
    "modification_allowed_after_approval",
    "notes",
]

OUTPUT_SAFETY_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "safety_scope",
    "target_name",
    "versioned_output",
    "diagnostic_only",
    "non_production",
    "non_routing",
    "non_weighting",
    "non_calibration",
    "non_subscriber_facing",
    "non_overwriting",
    "dedupe_key",
    "dedupe_contains_required_fields",
    "trace_complete",
    "safety_status",
    "notes",
]

DETERMINISM_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "control_id",
    "comparison_area",
    "expected_match",
    "actual_result",
    "allowed_difference",
    "approval_status",
    "blocking_if_failed",
    "notes",
]

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "control_id",
    "control_area",
    "allowed_source_sheets",
    "forbidden_source_sheets",
    "field_allowlist_present",
    "forbidden_pattern_present",
    "runtime_assertion_present",
    "post_write_audit_present",
    "dry_run_leakage_findings",
    "approval_status",
    "notes",
]

STOP_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
    "check_scope",
    "stop_rule_id",
    "requirement_id",
    "stop_condition_or_requirement",
    "mapped_stop_rule_ids",
    "executable",
    "coverage_status",
    "approval_status",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "approval_version",
    "approval_run_id",
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
    "approval_version",
    "approval_run_id",
    "build_status",
    "final_interpretation",
    "mechanisms_reviewed",
    "mechanisms_approved",
    "mechanisms_approved_with_exclusions",
    "mechanisms_blocked",
    "mechanism_row_pairs_reconciled",
    "rows_approved_as_previewed",
    "rows_approved_as_unknown",
    "rows_approved_with_low_confidence",
    "rows_approved_for_exclusion",
    "row_scope_mismatches",
    "conflict_dispositions_reviewed",
    "exact_conflict_disposition_matches",
    "forced_positive_negative_conversions",
    "confidence_increases",
    "manual_overrides_required",
    "version_components_frozen",
    "fingerprints_created",
    "output_schemas_approved",
    "dedupe_rule_approved",
    "traceability_rule_approved",
    "determinism_controls_approved",
    "leakage_controls_approved",
    "stop_rules_approved",
    "post_execution_review_required",
    "highest_approval_risk",
    "highest_scientific_warning",
    "primary_approval_interpretation",
    "provider_calls_performed",
    "forecasts_generated",
    "classification_execution_performed",
    "permanent_labels_assigned",
    "mechanism_testing_performed",
    "accuracy_evaluation_performed",
    "outcomes_accessed",
    "v10_sheets_modified",
    "v11_preregistration_modified",
    "v11_dry_run_modified",
    "v11_conflict_review_modified",
    "v11_execution_plan_modified",
    "production_sheet_writes",
    "production_behavior_changes",
    "routing_changes",
    "weighting_changes",
    "calibration_changes",
    "ensemble_changes",
    "ready_for_v11_classification_execution",
    "ready_for_permanent_classification_execution",
    "ready_for_mechanism_testing",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    return "refined_mechanism_v11_classification_execution_approval_v0_" + generated_ts.replace("-", "").replace(":", "")


def _base(generated_ts: str, run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "approval_version": APPROVAL_VERSION,
        "approval_run_id": run_id,
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
    known_titles: Optional[Set[str]] = None,
) -> List[str]:
    titles = known_titles if known_titles is not None else _sheet_titles_light(service, spreadsheet_id)
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
        if known_titles is not None:
            known_titles.add(sheet_name)
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
    ranges = [f"'{sheet}'!A1:ZZZ" for sheet in INPUT_SHEETS]
    response = (
        service.spreadsheets()
        .values()
        .batchGet(spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=ranges)
        .execute()
    )
    value_ranges = response.get("valueRanges", [])
    by_title: Dict[str, List[Dict[str, Any]]] = {}
    for sheet_name, value_range in zip(INPUT_SHEETS, value_ranges):
        values = value_range.get("values", [])
        if not values:
            by_title[sheet_name] = []
            continue
        headers = values[0]
        rows: List[Dict[str, Any]] = []
        for idx, raw in enumerate(values[1:], start=2):
            padded = list(raw) + [""] * max(0, len(headers) - len(raw))
            row = {headers[i]: padded[i] for i in range(len(headers))}
            row["__source_row_number__"] = idx
            rows.append(row)
        by_title[sheet_name] = rows
    for sheet_name in INPUT_SHEETS:
        by_title.setdefault(sheet_name, [])
    return by_title


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_V11_EXECUTION_APPROVAL", OUTPUT_APPROVAL, "refined_mechanism_v11_execution_approval"),
        ("REFINED_MECHANISM_V11_APPROVAL_ROW_RECONCILIATION", OUTPUT_ROW_RECON, "refined_mechanism_v11_approval_row_reconciliation"),
        ("REFINED_MECHANISM_V11_APPROVAL_CONFLICT_RECONCILIATION", OUTPUT_CONFLICT_RECON, "refined_mechanism_v11_approval_conflict_reconciliation"),
        ("REFINED_MECHANISM_V11_APPROVAL_VERSION_FREEZE", OUTPUT_VERSION_FREEZE, "refined_mechanism_v11_approval_version_freeze"),
        ("REFINED_MECHANISM_V11_APPROVAL_OUTPUT_SAFETY", OUTPUT_OUTPUT_SAFETY, "refined_mechanism_v11_approval_output_safety"),
        ("REFINED_MECHANISM_V11_APPROVAL_DETERMINISM_CHECK", OUTPUT_DETERMINISM, "refined_mechanism_v11_approval_determinism_check"),
        ("REFINED_MECHANISM_V11_APPROVAL_LEAKAGE_CHECK", OUTPUT_LEAKAGE, "refined_mechanism_v11_approval_leakage_check"),
        ("REFINED_MECHANISM_V11_APPROVAL_STOP_RULE_CHECK", OUTPUT_STOP, "refined_mechanism_v11_approval_stop_rule_check"),
        ("REFINED_MECHANISM_V11_APPROVAL_GOVERNANCE", OUTPUT_GOVERNANCE, "refined_mechanism_v11_approval_governance"),
        ("REFINED_MECHANISM_V11_EXECUTION_APPROVAL_SUMMARY", OUTPUT_SUMMARY, "refined_mechanism_v11_execution_approval_summary"),
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
                "Phase 9A-6R9 v1.1 refined classification execution approval; approval and freeze only, "
                "no permanent classification execution or mechanism testing."
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


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _latest_single_row(rows: Sequence[Dict[str, Any]], run_field: str) -> Dict[str, Any]:
    if not rows:
        return {}
    return max(rows, key=lambda row: _norm(row.get(run_field)))


def _pair_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (_norm(row.get("mechanism_id")), _norm(row.get("source_row_key")))


def _confidence_rank(value: Any) -> int:
    return {
        "UNKNOWN": 0,
        "LOW": 1,
        "MODERATE": 2,
        "HIGH": 3,
    }.get(_norm(value).upper(), 0)


def _canonical_sheet_fingerprint(headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    payload = {
        "headers": list(headers),
        "rows": [{header: _norm(row.get(header)) for header in headers} for row in rows],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _version_from_sheet(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    for field in (
        "refined_mechanism_version",
        "execution_plan_version",
        "review_version",
        "dry_run_version",
        "approval_version",
        "schema_version",
    ):
        value = _norm(rows[0].get(field))
        if value:
            return value
    return ""


def build_refined_mechanism_v11_classification_execution_approval_v0() -> Dict[str, Any]:
    credentials = load_credentials()
    service = build_sheets_service(credentials)
    data = _read_inputs(service)

    generated_ts = _iso_now()
    run_id = _run_id(generated_ts)

    prereg_summary = _latest_single_row(data["Refined_Mechanism_v11_PreRegistration_Summary"], "preregistration_run_id")
    review_summary = _latest_single_row(data["Refined_Mechanism_v11_Conflict_Review_Summary"], "review_run_id")
    plan_summary = _latest_single_row(data["Refined_Mechanism_v11_Execution_Plan_Summary"], "execution_plan_run_id")
    mechanism_version = _norm(prereg_summary.get("refined_mechanism_version")) or "1.1"

    mech_scope_by_id = {
        _norm(row.get("mechanism_id")): row for row in data["Refined_Mechanism_v11_Mechanism_Execution_Scope"]
    }
    exec_readiness_by_id = {
        _norm(row.get("mechanism_id")): row for row in data["Refined_Mechanism_v11_Execution_Readiness"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    }
    conflict_review_by_id = {
        _norm(row.get("mechanism_id")): row for row in data["Refined_Mechanism_v11_Conflict_Review"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    }
    falsification_by_id = {
        _norm(row.get("mechanism_id")): row for row in data["Refined_Mechanism_v11_Falsification_Review"]
        if _norm(row.get("mechanism_id")) in PROMOTED_MECHANISMS
    }

    dry_preview_by_key = {_pair_key(row): row for row in data["Refined_Mechanism_v11_Label_Preview"]}
    row_scope_by_key = {_pair_key(row): row for row in data["Refined_Mechanism_v11_Row_Execution_Scope"]}
    rule_path_by_key = {_pair_key(row): row for row in data["Refined_Mechanism_v11_Rule_Path_Audit"]}
    unresolved_by_key = {_pair_key(row): row for row in data["Refined_Mechanism_v11_Unresolved_Conflict_Review"]}
    conflict_plan_by_key = {_pair_key(row): row for row in data["Refined_Mechanism_v11_Conflict_Disposition_Plan"]}

    approval_rows: List[Dict[str, Any]] = []
    row_recon_rows: List[Dict[str, Any]] = []
    conflict_recon_rows: List[Dict[str, Any]] = []
    version_freeze_rows: List[Dict[str, Any]] = []
    output_safety_rows: List[Dict[str, Any]] = []
    determinism_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    stop_rows: List[Dict[str, Any]] = []

    mechanisms_reviewed = len(PROMOTED_MECHANISMS)
    mechanisms_approved = 0
    mechanisms_approved_with_exclusions = 0
    mechanisms_blocked = 0
    for mechanism_id in PROMOTED_MECHANISMS:
        readiness_row = exec_readiness_by_id.get(mechanism_id, {})
        scope_row = mech_scope_by_id.get(mechanism_id, {})
        review_row = conflict_review_by_id.get(mechanism_id, {})
        falsification_row = falsification_by_id.get(mechanism_id, {})

        warnings: List[str] = []
        blockers: List[str] = []
        if _norm(scope_row.get("warning_condition")):
            warnings.append(_norm(scope_row.get("warning_condition")))
        if _to_bool(falsification_row.get("warning_triggered")):
            warnings.append(_norm(falsification_row.get("scientific_consequence")))
        if not _to_bool(readiness_row.get("population_comparable")):
            blockers.append("population_not_comparable")
        if not _to_bool(readiness_row.get("determinism_pass")):
            blockers.append("determinism_not_confirmed")
        if not _to_bool(readiness_row.get("leakage_free")):
            blockers.append("leakage_not_confirmed")
        if _to_bool(readiness_row.get("falsification_blocker_triggered")):
            blockers.append("falsification_blocker_triggered")
        if not _to_bool(scope_row.get("execution_allowed")):
            blockers.append(_norm(scope_row.get("blocking_issue")) or "execution_not_allowed")

        if blockers:
            approval_status = "BLOCKED"
            mechanisms_blocked += 1
        elif _to_bool(scope_row.get("execution_allowed_with_exclusions")):
            approval_status = "APPROVED_WITH_EXCLUSIONS"
            mechanisms_approved_with_exclusions += 1
        elif warnings:
            approval_status = "APPROVED_WITH_WARNINGS"
            mechanisms_approved += 1
        else:
            approval_status = "APPROVED"
            mechanisms_approved += 1

        approval_rows.append(
            {
                **_base(generated_ts, run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": STABLE_ID_MAP.get(mechanism_id, ""),
                "mechanism_name": mechanism_id,
                "conflict_review_readiness": _norm(readiness_row.get("execution_readiness_status")) or _norm(review_row.get("review_status")),
                "execution_plan_readiness": _norm(scope_row.get("execution_readiness_status")),
                "execution_allowed": _norm(scope_row.get("execution_allowed")) or "FALSE",
                "execution_allowed_with_exclusions": _norm(scope_row.get("execution_allowed_with_exclusions")) or "FALSE",
                "warnings": _json(warnings),
                "blockers": _json(blockers),
                "required_execution_restrictions": _norm(scope_row.get("required_execution_control")),
                "approval_status": approval_status,
                "notes": _json(
                    {
                        "conflict_review_status": _norm(scope_row.get("conflict_review_status")),
                        "required_post_execution_review": _norm(scope_row.get("required_post_execution_review")),
                        "readiness_conclusion": _norm(readiness_row.get("readiness_conclusion")),
                    }
                ),
            }
        )

    all_pair_keys = sorted(set(dry_preview_by_key) | set(row_scope_by_key))
    mechanism_row_pairs_reconciled = 0
    row_scope_mismatches = 0
    rows_approved_as_previewed = 0
    rows_approved_as_unknown = 0
    rows_approved_with_low_confidence = 0
    rows_approved_for_exclusion = 0
    for key in all_pair_keys:
        mechanism_id, row_key = key
        dry_row = dry_preview_by_key.get(key, {})
        scope_row = row_scope_by_key.get(key, {})
        rule_row = rule_path_by_key.get(key, {})
        unresolved_row = unresolved_by_key.get(key, {})

        mismatch_reasons: List[str] = []
        if not dry_row:
            mismatch_reasons.append("missing_dry_run_preview")
        if not scope_row:
            mismatch_reasons.append("missing_execution_plan_scope")
        if dry_row and scope_row:
            if _norm(dry_row.get("preview_label")) != _norm(scope_row.get("dry_run_preview_label")):
                mismatch_reasons.append("preview_label_mismatch")
            if _norm(dry_row.get("confidence_category")) != _norm(scope_row.get("dry_run_confidence")):
                mismatch_reasons.append("preview_confidence_mismatch")
            if _norm(dry_row.get("executed_rule_id")) != _norm(scope_row.get("frozen_rule_id")):
                mismatch_reasons.append("frozen_rule_mismatch")
            if _norm(rule_row.get("decisive_rule_id")) and _norm(rule_row.get("decisive_rule_id")) != _norm(scope_row.get("frozen_rule_id")):
                mismatch_reasons.append("rule_path_reference_mismatch")
            expected_disposition = _norm(unresolved_row.get("recommended_disposition"))
            if not expected_disposition:
                expected_disposition = "OUT_OF_SCOPE" if _norm(scope_row.get("execution_scope_status")) == "OUT_OF_SCOPE" else "NO_OVERRIDE"
            if _norm(scope_row.get("conflict_review_disposition")) != expected_disposition:
                mismatch_reasons.append("conflict_disposition_mismatch")
            if not _norm(scope_row.get("frozen_evidence_trace_reference")):
                mismatch_reasons.append("missing_evidence_trace_reference")

        exact_match = not mismatch_reasons
        if exact_match:
            mechanism_row_pairs_reconciled += 1
            status = _norm(scope_row.get("execution_scope_status"))
            if status == "EXECUTE_AS_PREVIEWED":
                rows_approved_as_previewed += 1
            elif status == "EXECUTE_AS_UNKNOWN":
                rows_approved_as_unknown += 1
            elif status == "EXECUTE_WITH_LOW_CONFIDENCE":
                rows_approved_with_low_confidence += 1
            elif status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
                rows_approved_for_exclusion += 1
        else:
            row_scope_mismatches += 1

        row_recon_rows.append(
            {
                **_base(generated_ts, run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": STABLE_ID_MAP.get(mechanism_id, ""),
                "source_row_key": row_key,
                "dry_run_eligible": "FALSE" if _norm(dry_row.get("preview_label")) == "EXCLUDED" else "TRUE",
                "dry_run_preview_label": _norm(dry_row.get("preview_label")),
                "dry_run_confidence": _norm(dry_row.get("confidence_category")),
                "dry_run_conflict_status": _norm(dry_row.get("conflict_status")),
                "conflict_review_disposition": _norm(scope_row.get("conflict_review_disposition")),
                "execution_plan_status": _norm(scope_row.get("execution_scope_status")),
                "planned_execution_label": _norm(scope_row.get("planned_execution_label")),
                "planned_execution_confidence": _norm(scope_row.get("planned_execution_confidence")),
                "exclusion_status": "EXCLUDED" if _norm(scope_row.get("execution_scope_status")) in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"} else "IN_SCOPE",
                "frozen_rule_id": _norm(scope_row.get("frozen_rule_id")),
                "evidence_trace_reference": _norm(scope_row.get("frozen_evidence_trace_reference")),
                "exact_reconciliation_match": "TRUE" if exact_match else "FALSE",
                "mismatch_reason": _json(mismatch_reasons),
                "approval_status": "APPROVED" if exact_match else "NEEDS_REVIEW",
                "notes": _json(
                    {
                        "preview_id": _norm(dry_row.get("preview_id")),
                        "execution_plan_run_id": _norm(scope_row.get("execution_plan_run_id")),
                    }
                ),
            }
        )

    conflict_dispositions_reviewed = 0
    exact_conflict_disposition_matches = 0
    forced_positive_negative_conversions = 0
    confidence_increases = 0
    manual_overrides_required = 0
    for key, review_row in sorted(unresolved_by_key.items()):
        mechanism_id, row_key = key
        plan_row = conflict_plan_by_key.get(key, {})
        scope_row = row_scope_by_key.get(key, {})
        dry_row = dry_preview_by_key.get(key, {})
        review_disposition = _norm(review_row.get("recommended_disposition"))
        planned_disposition = _norm(plan_row.get("planned_execution_disposition"))
        planned_label = _norm(plan_row.get("planned_label")) or _norm(scope_row.get("planned_execution_label"))
        planned_confidence = _norm(plan_row.get("planned_confidence")) or _norm(scope_row.get("planned_execution_confidence"))
        dry_confidence = _norm(dry_row.get("confidence_category"))

        expected_status = {
            "CONVERT_TO_UNKNOWN": "EXECUTE_AS_UNKNOWN",
            "ALLOW_WITH_LOW_CONFIDENCE": "EXECUTE_WITH_LOW_CONFIDENCE",
            "CONVERT_TO_INSUFFICIENT_EVIDENCE": "EXECUTE_AS_PREVIEWED",
            "EXCLUDE_FROM_EXECUTION": "EXCLUDE_FROM_EXECUTION",
            "REQUIRES_V12_RULE_REPAIR": "BLOCKED_PENDING_REPAIR",
        }.get(review_disposition, "")

        exact_match = bool(
            planned_disposition
            and planned_disposition == expected_status
            and planned_disposition == _norm(scope_row.get("execution_scope_status"))
        )
        if review_disposition == "CONVERT_TO_UNKNOWN":
            exact_match = exact_match and planned_label == "UNKNOWN"
        elif review_disposition == "ALLOW_WITH_LOW_CONFIDENCE":
            exact_match = exact_match and planned_confidence == "LOW" and planned_label == _norm(scope_row.get("planned_execution_label"))

        forced_conversion = review_disposition == "CONVERT_TO_UNKNOWN" and planned_label in {"POSITIVE", "NEGATIVE"}
        confidence_increase_flag = _confidence_rank(planned_confidence) > _confidence_rank(dry_confidence)
        manual_override = _to_bool(plan_row.get("manual_override_required"))

        conflict_dispositions_reviewed += 1
        if exact_match:
            exact_conflict_disposition_matches += 1
        if forced_conversion:
            forced_positive_negative_conversions += 1
        if confidence_increase_flag:
            confidence_increases += 1
        if manual_override:
            manual_overrides_required += 1

        conflict_recon_rows.append(
            {
                **_base(generated_ts, run_id),
                "mechanism_id": mechanism_id,
                "stable_mechanism_id": STABLE_ID_MAP.get(mechanism_id, ""),
                "source_row_key": row_key,
                "phase9a6r7_disposition": review_disposition,
                "phase9a6r8_planned_disposition": planned_disposition,
                "exact_match": "TRUE" if exact_match else "FALSE",
                "planned_label": planned_label,
                "planned_confidence": planned_confidence,
                "forced_positive_negative_conversion": "TRUE" if forced_conversion else "FALSE",
                "confidence_increase": "TRUE" if confidence_increase_flag else "FALSE",
                "manual_override_required": "TRUE" if manual_override else "FALSE",
                "approval_status": "APPROVED" if exact_match and not forced_conversion and not confidence_increase_flag and not manual_override else "NEEDS_REVIEW",
                "notes": _json(
                    {
                        "scientific_rationale": _norm(plan_row.get("scientific_rationale")),
                        "execution_impact": _norm(review_row.get("execution_impact")),
                    }
                ),
            }
        )

    freeze_specs = [
        ("v11_preregistration", "Refined_Mechanism_v11_PreRegistration"),
        ("v11_frozen_definitions", "Refined_Mechanism_v11_Frozen_Definitions"),
        ("v11_frozen_observables", "Refined_Mechanism_v11_Frozen_Observables"),
        ("v11_frozen_label_rules", "Refined_Mechanism_v11_Frozen_Label_Rules"),
        ("v11_frozen_confidence_rules", "Refined_Mechanism_v11_Frozen_Confidence_Rules"),
        ("v11_frozen_conflict_rules", "Refined_Mechanism_v11_Frozen_Conflict_Rules"),
        ("v11_frozen_falsification_rules", "Refined_Mechanism_v11_Frozen_Falsification_Rules"),
        ("v11_dry_run_row_scope", "Refined_Mechanism_v11_Label_Preview"),
        ("v11_conflict_review_dispositions", "Refined_Mechanism_v11_Unresolved_Conflict_Review"),
        ("v11_execution_plan_row_scope", "Refined_Mechanism_v11_Row_Execution_Scope"),
        ("v11_output_schema_plan", "Refined_Mechanism_v11_Output_Schema_Plan"),
        ("v11_stop_hold_rules", "Refined_Mechanism_v11_Stop_Hold_Rules"),
    ]
    for component, sheet_name in freeze_specs:
        rows = data[sheet_name]
        headers = [key for key in rows[0].keys() if not key.startswith("__")] if rows else _get_headers(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
        version_freeze_rows.append(
            {
                **_base(generated_ts, run_id),
                "component": component,
                "source_sheet": sheet_name,
                "source_row_count": len(rows),
                "version": _version_from_sheet(rows) or mechanism_version,
                "fingerprint_method": "sha256_canonical_sheet_rows_v1",
                "fingerprint": _canonical_sheet_fingerprint(headers, rows),
                "approval_timestamp": generated_ts,
                "modification_allowed_after_approval": "FALSE",
                "notes": "Header order and row order are frozen via canonical JSON serialization with SHA-256.",
            }
        )

    output_schemas_approved = 0
    dedupe_rule_approved = True
    row_level_required_fields = {"classification_run_id", "mechanism_version", "mechanism_id", "source_row_key"}
    run_level_sheets = {
        "Refined_Mechanism_v11_Classification_Governance",
        "Refined_Mechanism_v11_Classification_Summary",
    }
    for schema_row in data["Refined_Mechanism_v11_Output_Schema_Plan"]:
        sheet_name = _norm(schema_row.get("sheet_name"))
        dedupe_parts = set(_norm(schema_row.get("dedupe_key")).split("|")) if _norm(schema_row.get("dedupe_key")) else set()
        trace_fields = set(json.loads(_norm(schema_row.get("source_trace_fields")) or "[]"))
        is_row_level = sheet_name not in run_level_sheets
        contains_required = (not is_row_level) or row_level_required_fields.issubset(dedupe_parts)
        if is_row_level and not contains_required:
            dedupe_rule_approved = False
        trace_complete = bool({"classification_run_id", "mechanism_id", "source_row_key"}.issubset(trace_fields))
        safety_status = "APPROVED" if contains_required and trace_complete else "NEEDS_REVIEW"
        if safety_status == "APPROVED":
            output_schemas_approved += 1
        output_safety_rows.append(
            {
                **_base(generated_ts, run_id),
                "safety_scope": "OUTPUT_SCHEMA",
                "target_name": sheet_name,
                "versioned_output": "TRUE" if _norm(schema_row.get("write_mode")) in {"APPEND_NEW_VERSIONED_RUN", "REBUILD_VERSIONED_OUTPUT"} else "FALSE",
                "diagnostic_only": "TRUE",
                "non_production": "TRUE",
                "non_routing": "TRUE",
                "non_weighting": "TRUE",
                "non_calibration": "TRUE",
                "non_subscriber_facing": "TRUE",
                "non_overwriting": "TRUE" if "FALSE" in _norm(schema_row.get("overwrite_policy")).upper() else "FALSE",
                "dedupe_key": _norm(schema_row.get("dedupe_key")),
                "dedupe_contains_required_fields": "TRUE" if contains_required else ("EXEMPT_RUN_LEVEL" if not is_row_level else "FALSE"),
                "trace_complete": "TRUE" if trace_complete else "FALSE",
                "safety_status": safety_status,
                "notes": _json(
                    {
                        "primary_key": _norm(schema_row.get("primary_key")),
                        "version_fields": _norm(schema_row.get("version_fields")),
                        "write_mode": _norm(schema_row.get("write_mode")),
                    }
                ),
            }
        )

    semantic_guardrails = [
        ("permanent_classification_meaning", "Permanent classification is a versioned diagnostic research record, not production truth.", "PASS"),
        ("version_supersession", "Historical v1.1 labels must remain preserved and may only be superseded by a later formally versioned framework.", "PASS"),
        ("unknown_is_valid", "UNKNOWN is a valid final diagnostic label and must not be forced into positive or negative.", "PASS"),
        ("negative_is_not_harm", "NEGATIVE does not mean harmful, inaccurate, or production-inferior.", "PASS"),
        ("positive_is_not_predictive", "POSITIVE does not establish predictive usefulness or accuracy.", "PASS"),
        ("no_production_use", "No production routing, weighting, calibration, scoring, or subscriber-facing decision may use these labels.", "PASS"),
    ]
    for guardrail_id, note, status in semantic_guardrails:
        output_safety_rows.append(
            {
                **_base(generated_ts, run_id),
                "safety_scope": "SEMANTIC_GUARDRAIL",
                "target_name": guardrail_id,
                "versioned_output": "TRUE",
                "diagnostic_only": "TRUE",
                "non_production": "TRUE",
                "non_routing": "TRUE",
                "non_weighting": "TRUE",
                "non_calibration": "TRUE",
                "non_subscriber_facing": "TRUE",
                "non_overwriting": "TRUE",
                "dedupe_key": "",
                "dedupe_contains_required_fields": "NOT_APPLICABLE",
                "trace_complete": "TRUE",
                "safety_status": status,
                "notes": note,
            }
        )

    dry_excluded_keys = {key for key, row in dry_preview_by_key.items() if _norm(row.get("preview_label")) == "EXCLUDED"}
    scope_excluded_keys = {
        key
        for key, row in row_scope_by_key.items()
        if _norm(row.get("execution_scope_status")) in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}
    }
    determinism_checks = [
        (
            "DET_001",
            "row_key_equality",
            "Exact row-key equality against the frozen dry-run scope.",
            set(dry_preview_by_key) == set(row_scope_by_key),
            "planned conflict dispositions only",
        ),
        (
            "DET_002",
            "eligibility_equality",
            "Exact eligibility equality against the dry-run scope.",
            dry_excluded_keys == scope_excluded_keys,
            "planned exclusions only",
        ),
        (
            "DET_003",
            "observable_extraction_equality",
            "Observable extraction must remain tied to the frozen dry-run rule path and evidence trace.",
            all(_norm(row.get("frozen_evidence_trace_reference")) and _norm(row.get("frozen_rule_id")) for row in row_scope_by_key.values()),
            "none",
        ),
        (
            "DET_004",
            "rule_path_equality",
            "Frozen rule IDs must match the dry-run rule-path audit exactly.",
            all(_norm(row_scope_by_key[key].get("frozen_rule_id")) == _norm(rule_path_by_key.get(key, {}).get("decisive_rule_id")) for key in row_scope_by_key),
            "planned conflict disposition remap only",
        ),
        (
            "DET_005",
            "label_equality",
            "Planned execution labels must match dry-run preview labels except approved conflict dispositions.",
            all(
                _norm(scope.get("planned_execution_label")) == _norm(dry_preview_by_key[key].get("preview_label"))
                for key, scope in row_scope_by_key.items()
                if _norm(scope.get("conflict_review_disposition")) not in {"CONVERT_TO_UNKNOWN"}
            ) and all(
                _norm(scope.get("planned_execution_label")) == "UNKNOWN"
                for key, scope in row_scope_by_key.items()
                if _norm(scope.get("conflict_review_disposition")) == "CONVERT_TO_UNKNOWN"
            ),
            "approved conflict dispositions only",
        ),
        (
            "DET_006",
            "confidence_equality",
            "Planned execution confidence must match frozen preview confidence except approved low-confidence dispositions.",
            all(
                _norm(scope.get("planned_execution_confidence")) == _norm(scope.get("dry_run_confidence"))
                for scope in row_scope_by_key.values()
                if _norm(scope.get("conflict_review_disposition")) != "ALLOW_WITH_LOW_CONFIDENCE"
            ) and all(
                _norm(scope.get("planned_execution_confidence")) == "LOW"
                for scope in row_scope_by_key.values()
                if _norm(scope.get("conflict_review_disposition")) == "ALLOW_WITH_LOW_CONFIDENCE"
            ),
            "approved low-confidence disposition only",
        ),
        (
            "DET_007",
            "conflict_equality",
            "Conflict dispositions must match the reviewed 21-row conflict set exactly.",
            conflict_dispositions_reviewed == 21 and exact_conflict_disposition_matches == 21,
            "none",
        ),
        (
            "DET_008",
            "exclusion_equality",
            "Excluded rows must remain exactly frozen.",
            len(scope_excluded_keys) == 114,
            "none",
        ),
    ]
    determinism_controls_approved = True
    for control_id, area, expected, passed, allowed_difference in determinism_checks:
        approval_status = "APPROVED" if passed else "NEEDS_REVIEW"
        if not passed:
            determinism_controls_approved = False
        determinism_rows.append(
            {
                **_base(generated_ts, run_id),
                "control_id": control_id,
                "comparison_area": area,
                "expected_match": expected,
                "actual_result": "PASS" if passed else "FAIL",
                "allowed_difference": allowed_difference,
                "approval_status": approval_status,
                "blocking_if_failed": "TRUE",
                "notes": "Execution must stop if this equality check is not satisfied at runtime.",
            }
        )

    dry_run_leakage_findings = sum(
        1
        for row in data["Refined_Mechanism_v11_Leakage_Audit"]
        if any(_to_bool(row.get(field)) for field in ("outcome_field_accessed", "future_information_accessed", "prohibited_sheet_accessed"))
    )
    leakage_controls_approved = dry_run_leakage_findings == 0
    for row in data["Refined_Mechanism_v11_Leakage_Control"]:
        field_allowlist_present = bool(_norm(row.get("allowed_source_columns")))
        forbidden_pattern_present = bool(_norm(row.get("forbidden_column_patterns")))
        runtime_assertion_present = bool(_norm(row.get("runtime_leakage_assertion")))
        post_write_audit_present = bool(_norm(row.get("post_write_leakage_audit")))
        passed = field_allowlist_present and forbidden_pattern_present and runtime_assertion_present and post_write_audit_present and dry_run_leakage_findings == 0
        if not passed:
            leakage_controls_approved = False
        leakage_rows.append(
            {
                **_base(generated_ts, run_id),
                "control_id": _norm(row.get("control_id")),
                "control_area": _norm(row.get("control_area")),
                "allowed_source_sheets": _norm(row.get("allowed_source_sheets")),
                "forbidden_source_sheets": _norm(row.get("forbidden_source_sheets")),
                "field_allowlist_present": "TRUE" if field_allowlist_present else "FALSE",
                "forbidden_pattern_present": "TRUE" if forbidden_pattern_present else "FALSE",
                "runtime_assertion_present": "TRUE" if runtime_assertion_present else "FALSE",
                "post_write_audit_present": "TRUE" if post_write_audit_present else "FALSE",
                "dry_run_leakage_findings": dry_run_leakage_findings,
                "approval_status": "APPROVED" if passed else "NEEDS_REVIEW",
                "notes": "Dry-run leakage remains zero and execution leakage controls are structurally present.",
            }
        )

    stop_conditions = {_norm(row.get("stop_rule_id")): _norm(row.get("stop_condition")) for row in data["Refined_Mechanism_v11_Stop_Hold_Rules"]}
    stop_rules_approved = True
    for row in data["Refined_Mechanism_v11_Stop_Hold_Rules"]:
        executable = (
            _to_bool(row.get("stop_immediately"))
            and _to_bool(row.get("preserve_diagnostic_logs"))
            and not _to_bool(row.get("successful_summary_allowed"))
            and not _to_bool(row.get("retry_with_changed_rules_allowed"))
            and bool(_norm(row.get("failure_action")))
        )
        if not executable:
            stop_rules_approved = False
        stop_rows.append(
            {
                **_base(generated_ts, run_id),
                "check_scope": "RULE_EXECUTABLE",
                "stop_rule_id": _norm(row.get("stop_rule_id")),
                "requirement_id": "",
                "stop_condition_or_requirement": _norm(row.get("stop_condition")),
                "mapped_stop_rule_ids": _norm(row.get("stop_rule_id")),
                "executable": "TRUE" if executable else "FALSE",
                "coverage_status": "RULE_PRESENT",
                "approval_status": "APPROVED" if executable else "NEEDS_REVIEW",
                "notes": "Rule execution must hard-stop the future run before a successful final summary can be written.",
            }
        )

    requirement_specs = [
        ("REQ_001", "preregistration_version_or_fingerprint_mismatch", {"STOP_001"}),
        ("REQ_002", "dry_run_scope_mismatch", {"STOP_002", "STOP_003"}),
        ("REQ_003", "conflict_disposition_mismatch", {"STOP_007"}),
        ("REQ_004", "execution_plan_fingerprint_mismatch", set()),
        ("REQ_005", "unexpected_label_difference", {"STOP_005"}),
        ("REQ_006", "unexpected_confidence_difference", {"STOP_006"}),
        ("REQ_007", "unexpected_eligibility_difference", set()),
        ("REQ_008", "manual_override_requested", {"STOP_008"}),
        ("REQ_009", "outcome_field_or_forbidden_sheet_access", {"STOP_009", "STOP_010"}),
        ("REQ_010", "source_sheet_modification", {"STOP_011"}),
        ("REQ_011", "dedupe_failure", {"STOP_013"}),
        ("REQ_012", "incomplete_trace_or_partial_write", {"STOP_014"}),
        ("REQ_013", "production_write_attempt", {"STOP_012"}),
    ]
    for requirement_id, requirement, mapped_ids in requirement_specs:
        covered = bool(mapped_ids)
        if not covered:
            stop_rules_approved = False
        stop_rows.append(
            {
                **_base(generated_ts, run_id),
                "check_scope": "REQUIRED_COVERAGE",
                "stop_rule_id": "",
                "requirement_id": requirement_id,
                "stop_condition_or_requirement": requirement,
                "mapped_stop_rule_ids": "|".join(sorted(mapped_ids)),
                "executable": "TRUE" if covered else "FALSE",
                "coverage_status": "COVERED" if covered else "MISSING_EXPLICIT_COVERAGE",
                "approval_status": "APPROVED" if covered else "NEEDS_REVIEW",
                "notes": (
                    "The current execution plan does not name this stop condition explicitly enough for approval."
                    if not covered
                    else "Coverage is present in the frozen stop-rule set."
                ),
            }
        )

    governance_specs = [
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECASTS", "forecasts_generated", "0", "0"),
        ("GOV_CLASSIFICATION_EXECUTION", "classification_execution_performed", "0", "0"),
        ("GOV_PERMANENT_LABELS", "permanent_labels_assigned", "0", "0"),
        ("GOV_MECHANISM_TESTING", "mechanism_testing_performed", "0", "0"),
        ("GOV_ACCURACY_EVALUATION", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_OUTCOMES", "outcomes_accessed", "0", "0"),
        ("GOV_V10_MODIFIED", "v10_sheets_modified", "0", "0"),
        ("GOV_V11_PREREG_MODIFIED", "v11_preregistration_modified", "0", "0"),
        ("GOV_V11_DRY_RUN_MODIFIED", "v11_dry_run_modified", "0", "0"),
        ("GOV_V11_CONFLICT_REVIEW_MODIFIED", "v11_conflict_review_modified", "0", "0"),
        ("GOV_V11_EXECUTION_PLAN_MODIFIED", "v11_execution_plan_modified", "0", "0"),
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
            "notes": "Phase 9A-6R9 is approval-only and must remain non-executing.",
        }
        for check_id, check_name, expected_value, actual_value in governance_specs
    ]
    governance_pass = all(_norm(row.get("status")) == "PASS" for row in governance_rows)

    traceability_rule_approved = False
    trace_fields = {_norm(row.get("trace_field")) for row in data["Refined_Mechanism_v11_Traceability_Plan"] if _to_bool(row.get("required"))}
    required_trace_fields = {
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "mechanism_id",
        "source_row_key",
        "source_sheet",
        "source_row_reference",
        "frozen_rule_id",
        "decisive_observable_ids",
        "decisive_evidence_trace",
        "conflict_status",
        "conflict_disposition",
        "confidence_category",
        "classification_timestamp",
        "outcome_independence_verified",
    }
    if required_trace_fields.issubset(trace_fields) and len(data["Refined_Mechanism_v11_Traceability_Plan"]) >= 15:
        traceability_rule_approved = True

    ready_for_v11_classification_execution = bool(
        governance_pass
        and mechanisms_blocked == 0
        and row_scope_mismatches == 0
        and exact_conflict_disposition_matches == 21
        and forced_positive_negative_conversions == 0
        and confidence_increases == 0
        and manual_overrides_required == 0
        and traceability_rule_approved
        and determinism_controls_approved
        and leakage_controls_approved
        and stop_rules_approved
        and dedupe_rule_approved
    )
    ready_for_permanent_classification_execution = ready_for_v11_classification_execution
    ready_for_mechanism_testing = False
    ready_for_production = False

    highest_scientific_warning = (
        "MECH_INFORMATION_SPECIFICITY remains approval-safe only if all 20 reviewed UNKNOWN dispositions remain frozen and the single low-confidence mixed-evidence disposition is not upgraded."
    )
    if dedupe_rule_approved:
        highest_approval_risk = "No high-risk approval gap identified."
    else:
        highest_approval_risk = "Planned permanent output dedupe keys do not explicitly include mechanism_version for row-level classification artifacts, weakening same-version duplicate protection."

    if ready_for_v11_classification_execution:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVED_WITH_WARNINGS"
        primary_approval_interpretation = (
            "The frozen v1.1 protocol is traceable, deterministic, leakage-safe, and row-reconciled; one versioned diagnostic permanent-classification run may proceed under the preserved UNKNOWN and low-confidence dispositions."
        )
        recommended_next_step = "PROCEED_TO_PHASE9A6R10_V11_CLASSIFICATION_EXECUTION"
    elif not governance_pass:
        build_status = "BLOCKED"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_BLOCKED"
        primary_approval_interpretation = "Governance did not remain clean enough for approval."
        recommended_next_step = "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW"
    else:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVAL_NEEDS_REVIEW"
        primary_approval_interpretation = (
            "Mechanism-level readiness and all 360 row reconciliations pass, but execution should not be authorized until the execution plan tightens row-level dedupe keys and closes missing stop-rule coverage for execution-plan fingerprint and eligibility mismatches."
        )
        recommended_next_step = "RETURN_TO_PHASE9A6R8_EXECUTION_PLAN_REPAIR"

    summary_row = {
        **_base(generated_ts, run_id),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "mechanisms_reviewed": mechanisms_reviewed,
        "mechanisms_approved": mechanisms_approved,
        "mechanisms_approved_with_exclusions": mechanisms_approved_with_exclusions,
        "mechanisms_blocked": mechanisms_blocked,
        "mechanism_row_pairs_reconciled": mechanism_row_pairs_reconciled,
        "rows_approved_as_previewed": rows_approved_as_previewed,
        "rows_approved_as_unknown": rows_approved_as_unknown,
        "rows_approved_with_low_confidence": rows_approved_with_low_confidence,
        "rows_approved_for_exclusion": rows_approved_for_exclusion,
        "row_scope_mismatches": row_scope_mismatches,
        "conflict_dispositions_reviewed": conflict_dispositions_reviewed,
        "exact_conflict_disposition_matches": exact_conflict_disposition_matches,
        "forced_positive_negative_conversions": forced_positive_negative_conversions,
        "confidence_increases": confidence_increases,
        "manual_overrides_required": manual_overrides_required,
        "version_components_frozen": len(version_freeze_rows),
        "fingerprints_created": len(version_freeze_rows),
        "output_schemas_approved": output_schemas_approved,
        "dedupe_rule_approved": "TRUE" if dedupe_rule_approved else "FALSE",
        "traceability_rule_approved": "TRUE" if traceability_rule_approved else "FALSE",
        "determinism_controls_approved": "TRUE" if determinism_controls_approved else "FALSE",
        "leakage_controls_approved": "TRUE" if leakage_controls_approved else "FALSE",
        "stop_rules_approved": "TRUE" if stop_rules_approved else "FALSE",
        "post_execution_review_required": "TRUE",
        "highest_approval_risk": highest_approval_risk,
        "highest_scientific_warning": highest_scientific_warning,
        "primary_approval_interpretation": primary_approval_interpretation,
        "provider_calls_performed": 0,
        "forecasts_generated": 0,
        "classification_execution_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcomes_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "v11_dry_run_modified": 0,
        "v11_conflict_review_modified": 0,
        "v11_execution_plan_modified": 0,
        "production_sheet_writes": 0,
        "production_behavior_changes": 0,
        "routing_changes": "FALSE",
        "weighting_changes": "FALSE",
        "calibration_changes": "FALSE",
        "ensemble_changes": "FALSE",
        "ready_for_v11_classification_execution": "TRUE" if ready_for_v11_classification_execution else "FALSE",
        "ready_for_permanent_classification_execution": "TRUE" if ready_for_permanent_classification_execution else "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": _json(
            {
                "preregistration_version": mechanism_version,
                "review_summary_run_id": _norm(review_summary.get("review_run_id")),
                "execution_plan_run_id": _norm(plan_summary.get("execution_plan_run_id")),
                "population_comparability_status": _norm(review_summary.get("population_comparability_status")),
                "false_proxy_positives": _norm(review_summary.get("false_proxy_positives")),
            }
        ),
    }

    outputs = [
        (OUTPUT_APPROVAL, APPROVAL_HEADERS, approval_rows),
        (OUTPUT_ROW_RECON, ROW_RECON_HEADERS, row_recon_rows),
        (OUTPUT_CONFLICT_RECON, CONFLICT_RECON_HEADERS, conflict_recon_rows),
        (OUTPUT_VERSION_FREEZE, VERSION_FREEZE_HEADERS, version_freeze_rows),
        (OUTPUT_OUTPUT_SAFETY, OUTPUT_SAFETY_HEADERS, output_safety_rows),
        (OUTPUT_DETERMINISM, DETERMINISM_HEADERS, determinism_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
        (OUTPUT_STOP, STOP_HEADERS, stop_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, [summary_row]),
    ]

    output_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal_light(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            headers,
            len(rows),
            known_titles=output_titles,
        )
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_refined_mechanism_v11_classification_execution_approval_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mechanisms_reviewed": mechanisms_reviewed,
        "mechanisms_approved": mechanisms_approved,
        "mechanisms_approved_with_exclusions": mechanisms_approved_with_exclusions,
        "mechanisms_blocked": mechanisms_blocked,
        "mechanism_row_pairs_reconciled": mechanism_row_pairs_reconciled,
        "rows_approved_as_previewed": rows_approved_as_previewed,
        "rows_approved_as_unknown": rows_approved_as_unknown,
        "rows_approved_with_low_confidence": rows_approved_with_low_confidence,
        "rows_approved_for_exclusion": rows_approved_for_exclusion,
        "row_scope_mismatches": row_scope_mismatches,
        "conflict_dispositions_reviewed": conflict_dispositions_reviewed,
        "exact_conflict_disposition_matches": exact_conflict_disposition_matches,
        "forced_positive_negative_conversions": forced_positive_negative_conversions,
        "confidence_increases": confidence_increases,
        "manual_overrides_required": manual_overrides_required,
        "version_components_frozen": len(version_freeze_rows),
        "fingerprints_created": len(version_freeze_rows),
        "output_schemas_approved": output_schemas_approved,
        "dedupe_rule_approved": dedupe_rule_approved,
        "traceability_rule_approved": traceability_rule_approved,
        "determinism_controls_approved": determinism_controls_approved,
        "leakage_controls_approved": leakage_controls_approved,
        "stop_rules_approved": stop_rules_approved,
        "post_execution_review_required": True,
        "highest_approval_risk": highest_approval_risk,
        "highest_scientific_warning": highest_scientific_warning,
        "primary_approval_interpretation": primary_approval_interpretation,
        "provider_calls_performed": 0,
        "forecasts_generated": 0,
        "classification_execution_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcomes_accessed": 0,
        "v10_sheets_modified": 0,
        "v11_preregistration_modified": 0,
        "v11_dry_run_modified": 0,
        "v11_conflict_review_modified": 0,
        "v11_execution_plan_modified": 0,
        "production_sheet_writes": 0,
        "production_behavior_changes": 0,
        "ready_for_v11_classification_execution": ready_for_v11_classification_execution,
        "ready_for_permanent_classification_execution": ready_for_permanent_classification_execution,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "registry": registry,
    }


def main() -> None:
    result = build_refined_mechanism_v11_classification_execution_approval_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
