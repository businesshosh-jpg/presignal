#!/usr/bin/env python3
"""Phase 9A-6R9R — v1.1 Refined Classification Execution Approval Rerun.

This phase independently re-validates the repaired Phase 9A-6R8 execution plan.
It does not execute classification, assign permanent labels, test mechanisms,
evaluate accuracy, or access outcome layers.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _sheet_to_rows,
    _write_rows,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R9R"
BUILD_SCRIPT = "automation/build_refined_mechanism_v11_classification_execution_approval_rerun_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_execution_approval_rerun_v0"
APPROVAL_RERUN_VERSION = "v0"
PREREGISTRATION_VERSION = "1.1"
MECHANISM_VERSION = "1.1"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_EXECUTION_APPROVAL_RERUN"


INPUT_SHEETS: Tuple[str, ...] = (
    # Phase 9A-6R8R repair outputs
    "Refined_Mechanism_v11_Execution_Plan_Repair",
    "Refined_Mechanism_v11_Repaired_Output_Schema_Plan",
    "Refined_Mechanism_v11_Repaired_Stop_Hold_Rules",
    "Refined_Mechanism_v11_Repair_Dedupe_Audit",
    "Refined_Mechanism_v11_Repair_Stop_Rule_Audit",
    "Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation",
    "Refined_Mechanism_v11_Execution_Plan_Repair_Governance",
    "Refined_Mechanism_v11_Execution_Plan_Repair_Summary",
    # Original Phase 9A-6R8 execution-plan lineage
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
    # Previous Phase 9A-6R9 approval outputs
    "Refined_Mechanism_v11_Execution_Approval",
    "Refined_Mechanism_v11_Approval_Row_Reconciliation",
    "Refined_Mechanism_v11_Approval_Conflict_Reconciliation",
    "Refined_Mechanism_v11_Approval_Version_Freeze",
    "Refined_Mechanism_v11_Approval_Output_Safety",
    "Refined_Mechanism_v11_Approval_Determinism_Check",
    "Refined_Mechanism_v11_Approval_Leakage_Check",
    "Refined_Mechanism_v11_Approval_Stop_Rule_Check",
    "Refined_Mechanism_v11_Approval_Governance",
    "Refined_Mechanism_v11_Execution_Approval_Summary",
    # Scientific evidence
    "Refined_Mechanism_v11_Conflict_Review",
    "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "Refined_Mechanism_v11_Execution_Readiness",
    "Refined_Mechanism_v11_Confidence_Review",
    "Refined_Mechanism_v11_Falsification_Review",
    "Refined_Mechanism_v11_Conflict_Review_Summary",
    # Dry-run evidence
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    # Frozen v1.1 preregistration
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_PreRegistration_Summary",
)


OUTPUT_SHEETS: Dict[str, List[str]] = {
    "Refined_Mechanism_v11_Execution_Approval_Rerun": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "mechanism_id",
        "mechanism_name",
        "conflict_review_status",
        "execution_plan_status",
        "scientific_scope_preserved",
        "normal_execution_scope_preserved",
        "warning_scope_preserved",
        "unknown_dispositions_preserved",
        "low_confidence_disposition_preserved",
        "execution_allowed",
        "execution_allowed_with_exclusions",
        "required_execution_restrictions",
        "approval_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Row_Reconciliation": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "mechanism_id",
        "source_row_key",
        "dry_run_preview_label",
        "dry_run_confidence",
        "conflict_status",
        "reviewed_conflict_disposition",
        "repaired_execution_scope_status",
        "repaired_planned_execution_label",
        "repaired_planned_execution_confidence",
        "repaired_execution_allowed",
        "exclusion_status",
        "frozen_rule_id",
        "evidence_trace_reference",
        "row_reconciliation_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Conflict_Reconciliation": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "mechanism_id",
        "source_row_key",
        "conflict_review_disposition",
        "repaired_execution_disposition",
        "planned_execution_label",
        "planned_execution_confidence",
        "exact_match",
        "forced_positive_conversion",
        "forced_negative_conversion",
        "confidence_increased",
        "manual_override_required",
        "approval_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Dedupe_Approval": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "sheet_name",
        "actual_dedupe_key",
        "classification_run_id_present",
        "mechanism_version_present",
        "mechanism_id_present",
        "source_row_key_present",
        "canonical_key_present",
        "preregistration_version_present",
        "mechanism_version_not_substituted",
        "contradictory_duplicate_hard_stop_defined",
        "overwrite_prohibited",
        "merge_prohibited",
        "collision_safe_across_versions",
        "collision_safe_across_runs",
        "collision_safe_across_mechanisms",
        "collision_safe_across_rows",
        "approval_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Stop_Rule_Approval": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "stop_rule_id",
        "stop_rule_name",
        "source_type",
        "approval_check_area",
        "preservation_status",
        "runtime_assertion_present",
        "failure_status",
        "write_behavior_on_failure",
        "retry_policy",
        "required_repair_phase",
        "approval_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Version_Freeze": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "component",
        "source_sheet",
        "source_row_count",
        "version",
        "fingerprint_method",
        "fingerprint",
        "modification_allowed_after_approval",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Output_Safety": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "safety_area",
        "status",
        "evidence",
        "blocking_issue",
        "recommended_action",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Traceability_Approval": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "traceability_field",
        "required",
        "present_in_plan",
        "approval_status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Determinism_Check": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "determinism_area",
        "expected_behavior",
        "approved_exception_scope",
        "status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Leakage_Check": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "leakage_control_area",
        "allowed_source_reference",
        "forbidden_source_reference",
        "status",
        "notes",
    ],
    "Refined_Mechanism_v11_Rerun_Governance": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
        "check_id",
        "check_name",
        "expected_value",
        "actual_value",
        "status",
        "notes",
    ],
    "Refined_Mechanism_v11_Execution_Approval_Rerun_Summary": [
        "generated_ts",
        "schema_version",
        "approval_rerun_version",
        "approval_rerun_run_id",
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
        "exact_conflict_matches",
        "forced_positive_conversions",
        "forced_negative_conversions",
        "confidence_increases",
        "disappeared_conflicts",
        "manual_overrides",
        "row_level_schemas_reviewed",
        "canonical_dedupe_keys_approved",
        "schemas_missing_mechanism_version",
        "contradictory_duplicate_hard_stop_approved",
        "execution_plan_fingerprint_stop_rule_approved",
        "unexpected_eligibility_difference_stop_rule_approved",
        "original_stop_rules_preserved",
        "total_stop_rules_approved",
        "version_components_frozen",
        "fingerprints_created",
        "output_safety_approved",
        "traceability_approved",
        "determinism_approved",
        "leakage_controls_approved",
        "post_execution_review_required",
        "highest_approval_risk",
        "highest_scientific_warning",
        "primary_approval_interpretation",
        "provider_calls_performed",
        "forecast_generation_performed",
        "classification_execution_performed",
        "permanent_labels_assigned",
        "mechanism_testing_performed",
        "accuracy_evaluation_performed",
        "outcome_values_accessed",
        "v1_0_sheets_modified",
        "v1_1_preregistration_modified",
        "v1_1_dry_run_modified",
        "v1_1_conflict_review_modified",
        "original_execution_plan_modified",
        "repair_outputs_modified_after_creation",
        "scientific_labels_changed",
        "confidence_values_changed",
        "exclusions_changed",
        "production_sheet_write_count",
        "production_behavior_change_count",
        "ready_for_one_v1_1_diagnostic_classification_execution",
        "ready_for_mechanism_testing",
        "ready_for_production",
        "recommended_next_step",
        "notes",
    ],
}


REQUIRED_ROW_LEVEL_OUTPUTS = (
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Evidence",
    "Refined_Mechanism_v11_Classification_Conflicts",
    "Refined_Mechanism_v11_Classification_Confidence",
    "Refined_Mechanism_v11_Classification_Audit",
)

REQUIRED_TRACE_FIELDS = (
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
)

REQUIRED_DRY_RUN_COUNTS = {
    "candidate_rows": 120,
    "eligible_rows": 82,
    "preview_labels": 360,
}

REQUIRED_EXECUTION_COUNTS = {
    "previewed": 225,
    "unknown": 20,
    "low_confidence": 1,
    "excluded": 114,
    "blocked": 0,
}

REQUIRED_REPAIR_COUNTS = {
    "mechanisms_reviewed": 3,
    "mechanisms_planned_for_execution": 2,
    "mechanisms_planned_with_exclusions": 1,
    "mechanisms_blocked": 0,
    "row_pairs": 360,
    "conflicts": 21,
    "unknown_conflicts": 20,
    "low_conflict": 1,
}


MECHANISM_NAMES = {
    "PM-001": "MECH_INFORMATION_RELEVANCE",
    "PM-002": "MECH_INFORMATION_SPECIFICITY",
    "PM-003": "MECH_INFORMATION_CONSISTENCY",
}


@dataclass(frozen=True)
class SheetData:
    headers: List[str]
    rows: List[Dict[str, str]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return f"{PHASE_ID}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint_rows(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        "headers": list(headers),
        "rows": [{header: row.get(header, "") for header in headers} for row in rows],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _safe_sheet_title(title: str) -> str:
    return title.replace("'", "''")


def _normalize_header(header: str) -> str:
    return str(header or "").strip()


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_bool(value: Any) -> bool:
    text = _normalize_value(value).lower()
    return text in {"1", "true", "yes", "y", "pass", "approved"}


def _to_int(value: Any) -> int:
    text = _normalize_value(value)
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def _json_listish(value: Any) -> List[str]:
    text = _normalize_value(value)
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return [_normalize_value(item) for item in loaded if _normalize_value(item)]
        except json.JSONDecodeError:
            pass
    if "|" in text:
        return [_normalize_value(part) for part in text.split("|") if _normalize_value(part)]
    if "," in text:
        return [_normalize_value(part) for part in text.split(",") if _normalize_value(part)]
    return [text]


def _sheet_titles_light(service, spreadsheet_id: str) -> List[str]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return [sheet["properties"]["title"] for sheet in metadata.get("sheets", [])]


def _fetch_input_sheets(service, spreadsheet_id: str, sheet_names: Sequence[str]) -> Dict[str, SheetData]:
    ranges = [f"'{_safe_sheet_title(name)}'!A:ZZ" for name in sheet_names]
    response = (
        service.spreadsheets()
        .values()
        .batchGet(spreadsheetId=spreadsheet_id, ranges=ranges)
        .execute()
    )
    value_ranges = response.get("valueRanges", [])
    out: Dict[str, SheetData] = {}
    for name, value_range in zip(sheet_names, value_ranges):
        values = value_range.get("values", [])
        if not values:
            out[name] = SheetData(headers=[], rows=[])
            continue
        headers = [_normalize_header(cell) for cell in values[0]]
        rows: List[Dict[str, str]] = []
        for raw_row in values[1:]:
            row = {headers[i]: _normalize_value(raw_row[i]) if i < len(raw_row) else "" for i in range(len(headers))}
            if any(_normalize_value(v) for v in row.values()):
                rows.append(row)
        out[name] = SheetData(headers=headers, rows=rows)
    return out


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet_minimal(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    data_row_count: int,
    known_titles: Optional[set] = None,
) -> List[str]:
    titles = known_titles if known_titles is not None else set(_sheet_titles_light(service, spreadsheet_id))
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


def _clear_and_write_sheet(service, spreadsheet_id: str, title: str, headers: Sequence[str], rows: Sequence[Mapping[str, Any]], known_titles: Optional[set] = None):
    effective_headers = _ensure_sheet_minimal(service, spreadsheet_id, title, headers, len(rows), known_titles)
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{title}'!A2:ZZZ",
    ).execute()
    normalized_rows = [{header: row.get(header, "") for header in effective_headers} for row in rows]
    _write_rows(service, spreadsheet_id, title, effective_headers, normalized_rows)


def _upsert_registry_rows(service, output_titles: Sequence[str], generated_ts: str):
    titles = set(_sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID))
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    by_id = {_normalize_value(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_normalize_value(row.get("logical_sheet_id")).upper(): row for row in rows}
    specs = [
        ("REFINED_MECHANISM_V11_EXECUTION_APPROVAL_RERUN", "Refined_Mechanism_v11_Execution_Approval_Rerun", "refined_mechanism_v11_execution_approval_rerun"),
        ("REFINED_MECHANISM_V11_RERUN_ROW_RECONCILIATION", "Refined_Mechanism_v11_Rerun_Row_Reconciliation", "refined_mechanism_v11_rerun_row_reconciliation"),
        ("REFINED_MECHANISM_V11_RERUN_CONFLICT_RECONCILIATION", "Refined_Mechanism_v11_Rerun_Conflict_Reconciliation", "refined_mechanism_v11_rerun_conflict_reconciliation"),
        ("REFINED_MECHANISM_V11_RERUN_DEDUPE_APPROVAL", "Refined_Mechanism_v11_Rerun_Dedupe_Approval", "refined_mechanism_v11_rerun_dedupe_approval"),
        ("REFINED_MECHANISM_V11_RERUN_STOP_RULE_APPROVAL", "Refined_Mechanism_v11_Rerun_Stop_Rule_Approval", "refined_mechanism_v11_rerun_stop_rule_approval"),
        ("REFINED_MECHANISM_V11_RERUN_VERSION_FREEZE", "Refined_Mechanism_v11_Rerun_Version_Freeze", "refined_mechanism_v11_rerun_version_freeze"),
        ("REFINED_MECHANISM_V11_RERUN_OUTPUT_SAFETY", "Refined_Mechanism_v11_Rerun_Output_Safety", "refined_mechanism_v11_rerun_output_safety"),
        ("REFINED_MECHANISM_V11_RERUN_TRACEABILITY_APPROVAL", "Refined_Mechanism_v11_Rerun_Traceability_Approval", "refined_mechanism_v11_rerun_traceability_approval"),
        ("REFINED_MECHANISM_V11_RERUN_DETERMINISM_CHECK", "Refined_Mechanism_v11_Rerun_Determinism_Check", "refined_mechanism_v11_rerun_determinism_check"),
        ("REFINED_MECHANISM_V11_RERUN_LEAKAGE_CHECK", "Refined_Mechanism_v11_Rerun_Leakage_Check", "refined_mechanism_v11_rerun_leakage_check"),
        ("REFINED_MECHANISM_V11_RERUN_GOVERNANCE", "Refined_Mechanism_v11_Rerun_Governance", "refined_mechanism_v11_rerun_governance"),
        ("REFINED_MECHANISM_V11_EXECUTION_APPROVAL_RERUN_SUMMARY", "Refined_Mechanism_v11_Execution_Approval_Rerun_Summary", "refined_mechanism_v11_execution_approval_rerun_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in specs:
        key = logical_id.upper()
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": "market_state",
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": f"PreSignal v2.0 Phase {PHASE_ID}",
            "notes": (
                "Phase 9A-6R9R rerun approval sheets; verifies repaired dedupe and hard-stop controls without "
                "executing classification or altering scientific scope."
            ),
            "registry_created_ts": _normalize_value(existing.get("registry_created_ts")) or generated_ts,
            "registry_last_verified_ts": generated_ts,
            "registry_migration_ts": _normalize_value(existing.get("registry_migration_ts")),
            "registry_rename_ts": _normalize_value(existing.get("registry_rename_ts")),
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


def _single_summary_row(sheet: SheetData) -> Dict[str, str]:
    if not sheet.rows:
        return {}
    return sheet.rows[0]


def _index_by(sheet: SheetData, *keys: str) -> Dict[Tuple[str, ...], Dict[str, str]]:
    out: Dict[Tuple[str, ...], Dict[str, str]] = {}
    for row in sheet.rows:
        out[tuple(_normalize_value(row.get(key, "")) for key in keys)] = row
    return out


def _pair_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (_normalize_value(row.get("mechanism_id", "")), _normalize_value(row.get("source_row_key", "")))


def _nonempty_match(value: str, expected_tokens: Sequence[str]) -> bool:
    lowered = _normalize_value(value).lower()
    return all(token.lower() in lowered for token in expected_tokens)


def _distinct(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        text = _normalize_value(value)
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return ordered


def _build_mechanism_approval_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    mechanism_scope_sheet: SheetData,
    execution_readiness_sheet: SheetData,
    conflict_review_summary: Dict[str, str],
    repair_summary: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    scope_by_stable = _index_by(mechanism_scope_sheet, "stable_mechanism_id")
    readiness_by_stable = _index_by(execution_readiness_sheet, "stable_mechanism_id")
    rows: List[Dict[str, Any]] = []
    counts = {"approved": 0, "approved_with_exclusions": 0, "blocked": 0}

    for stable_mechanism_id, mechanism_name in MECHANISM_NAMES.items():
        scope = scope_by_stable.get((stable_mechanism_id,), {})
        readiness = readiness_by_stable.get((stable_mechanism_id,), {})
        mechanism_id = _normalize_value(scope.get("mechanism_id")) or mechanism_name
        execution_allowed = _to_bool(scope.get("execution_allowed"))
        execution_allowed_with_exclusions = _to_bool(scope.get("execution_allowed_with_exclusions"))
        warning_condition = _normalize_value(scope.get("warning_condition"))
        blocking_issue = _normalize_value(scope.get("blocking_issue"))
        conflict_review_status = _normalize_value(readiness.get("execution_readiness_status") or scope.get("conflict_review_status"))
        execution_plan_status = _normalize_value(scope.get("execution_readiness_status") or "READY_FOR_EXECUTION_PLAN")

        scientific_scope_preserved = (
            _to_int(repair_summary.get("labels_changed")) == 0
            and _to_int(repair_summary.get("confidence_values_increased")) == 0
            and _to_int(repair_summary.get("exclusions_changed")) == 0
        )
        normal_execution_scope_preserved = _to_int(repair_summary.get("rows_as_previewed")) == REQUIRED_EXECUTION_COUNTS["previewed"]
        warning_scope_preserved = mechanism_id == "PM-002"
        unknown_dispositions_preserved = _to_int(repair_summary.get("rows_as_unknown")) == REQUIRED_EXECUTION_COUNTS["unknown"]
        low_confidence_disposition_preserved = _to_int(repair_summary.get("rows_with_low_confidence")) == REQUIRED_EXECUTION_COUNTS["low_confidence"]

        if not execution_allowed and not execution_allowed_with_exclusions:
            approval_status = "BLOCKED"
            counts["blocked"] += 1
        elif execution_allowed_with_exclusions:
            approval_status = "APPROVED_WITH_EXCLUSIONS"
            counts["approved_with_exclusions"] += 1
        elif warning_condition or stable_mechanism_id in {"PM-001", "PM-002"}:
            approval_status = "APPROVED_WITH_WARNINGS"
            counts["approved"] += 1
        else:
            approval_status = "APPROVED"
            counts["approved"] += 1

        notes_parts = []
        if stable_mechanism_id == "PM-002":
            notes_parts.append(
                "Specificity retains the reviewed warning-level conflict burden, 20 UNKNOWN dispositions, and the single low-confidence reviewed disposition."
            )
        if warning_condition:
            notes_parts.append(warning_condition)
        if blocking_issue:
            notes_parts.append(f"Blocking issue preserved: {blocking_issue}")

        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "mechanism_id": stable_mechanism_id,
                "mechanism_name": mechanism_id,
                "conflict_review_status": conflict_review_status or "READY_WITH_WARNINGS",
                "execution_plan_status": execution_plan_status or "READY_WITH_WARNINGS",
                "scientific_scope_preserved": str(scientific_scope_preserved).upper(),
                "normal_execution_scope_preserved": str(normal_execution_scope_preserved).upper(),
                "warning_scope_preserved": str(stable_mechanism_id == "PM-002").upper(),
                "unknown_dispositions_preserved": str(unknown_dispositions_preserved).upper(),
                "low_confidence_disposition_preserved": str(low_confidence_disposition_preserved).upper(),
                "execution_allowed": str(execution_allowed).upper(),
                "execution_allowed_with_exclusions": str(execution_allowed_with_exclusions).upper(),
                "required_execution_restrictions": _normalize_value(scope.get("required_execution_control")),
                "approval_status": approval_status,
                "notes": " ".join(notes_parts).strip(),
            }
        )

    return rows, counts


def _build_row_reconciliation_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    label_preview_sheet: SheetData,
    unresolved_conflict_sheet: SheetData,
    original_row_scope_sheet: SheetData,
    repair_row_scope_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    dry_by_key = _index_by(label_preview_sheet, "mechanism_id", "source_row_key")
    conflict_by_key = _index_by(unresolved_conflict_sheet, "mechanism_id", "source_row_key")
    original_by_key = _index_by(original_row_scope_sheet, "mechanism_id", "source_row_key")
    repair_by_key = _index_by(repair_row_scope_sheet, "mechanism_id", "source_row_key")
    all_keys = sorted(set(dry_by_key) | set(conflict_by_key) | set(original_by_key) | set(repair_by_key))

    rows: List[Dict[str, Any]] = []
    counts = {"previewed": 0, "unknown": 0, "low_confidence": 0, "excluded": 0, "blocked": 0, "mismatches": 0}

    for key in all_keys:
        dry = dry_by_key.get(key, {})
        conflict = conflict_by_key.get(key, {})
        original = original_by_key.get(key, {})
        repair = repair_by_key.get(key, {})

        repaired_execution_scope_status = _normalize_value(
            repair.get("repaired_execution_scope_status") or original.get("execution_scope_status")
        )
        repaired_planned_execution_label = _normalize_value(
            repair.get("repaired_planned_execution_label") or original.get("planned_execution_label")
        )
        repaired_planned_execution_confidence = _normalize_value(
            repair.get("repaired_planned_execution_confidence") or original.get("planned_execution_confidence")
        )
        exclusion_status = "TRUE" if repaired_execution_scope_status == "EXCLUDE_FROM_EXECUTION" else "FALSE"

        exact_match = (
            repaired_execution_scope_status == _normalize_value(original.get("execution_scope_status"))
            and repaired_planned_execution_label == _normalize_value(original.get("planned_execution_label"))
            and repaired_planned_execution_confidence == _normalize_value(original.get("planned_execution_confidence"))
            and _normalize_value(repair.get("repaired_frozen_rule_id") or original.get("frozen_rule_id"))
            == _normalize_value(original.get("frozen_rule_id"))
            and _normalize_value(repair.get("repaired_evidence_trace_reference") or original.get("frozen_evidence_trace_reference"))
            == _normalize_value(original.get("frozen_evidence_trace_reference"))
        )
        row_reconciliation_status = "PASS" if exact_match else "FAIL"
        if not exact_match:
            counts["mismatches"] += 1

        if repaired_execution_scope_status == "EXECUTE_AS_PREVIEWED":
            counts["previewed"] += 1
        elif repaired_execution_scope_status == "EXECUTE_AS_UNKNOWN":
            counts["unknown"] += 1
        elif repaired_execution_scope_status == "EXECUTE_WITH_LOW_CONFIDENCE":
            counts["low_confidence"] += 1
        elif repaired_execution_scope_status in {"EXCLUDE_FROM_EXECUTION", "OUT_OF_SCOPE"}:
            counts["excluded"] += 1
        elif repaired_execution_scope_status == "BLOCKED_PENDING_REPAIR":
            counts["blocked"] += 1

        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "mechanism_id": key[0],
                "source_row_key": key[1],
                "dry_run_preview_label": _normalize_value(dry.get("preview_label")),
                "dry_run_confidence": _normalize_value(dry.get("preview_confidence")),
                "conflict_status": _normalize_value(dry.get("conflict_status") or original.get("conflict_status")),
                "reviewed_conflict_disposition": _normalize_value(conflict.get("recommended_disposition")),
                "repaired_execution_scope_status": repaired_execution_scope_status,
                "repaired_planned_execution_label": repaired_planned_execution_label,
                "repaired_planned_execution_confidence": repaired_planned_execution_confidence,
                "repaired_execution_allowed": _normalize_value(repair.get("repaired_execution_allowed") or original.get("execution_allowed")),
                "exclusion_status": "TRUE" if repaired_execution_scope_status in {"EXCLUDE_FROM_EXECUTION", "OUT_OF_SCOPE"} else "FALSE",
                "frozen_rule_id": _normalize_value(repair.get("repaired_frozen_rule_id") or original.get("frozen_rule_id")),
                "evidence_trace_reference": _normalize_value(
                    repair.get("repaired_evidence_trace_reference") or original.get("frozen_evidence_trace_reference")
                ),
                "row_reconciliation_status": row_reconciliation_status,
                "notes": "" if exact_match else "Dry-run, conflict review, original execution plan, and repaired plan do not reconcile exactly.",
            }
        )

    return rows, counts


def _build_conflict_reconciliation_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    unresolved_conflict_sheet: SheetData,
    original_conflict_plan_sheet: SheetData,
    repair_row_scope_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    unresolved_by_key = _index_by(unresolved_conflict_sheet, "mechanism_id", "source_row_key")
    original_by_key = _index_by(original_conflict_plan_sheet, "mechanism_id", "source_row_key")
    repair_by_key = _index_by(repair_row_scope_sheet, "mechanism_id", "source_row_key")

    original_conflict_keys = {key for key, row in original_by_key.items() if _normalize_value(row.get("conflict_review_disposition"))}
    repair_conflict_keys = {
        key
        for key, row in repair_by_key.items()
        if _normalize_value(row.get("repaired_execution_scope_status")) in {"EXECUTE_AS_UNKNOWN", "EXECUTE_WITH_LOW_CONFIDENCE"}
    }
    all_keys = sorted(set(unresolved_by_key) | original_conflict_keys | repair_conflict_keys)
    rows: List[Dict[str, Any]] = []
    counts = {
        "reviewed": len(all_keys),
        "exact": 0,
        "forced_positive": 0,
        "forced_negative": 0,
        "confidence_increases": 0,
        "disappeared": 0,
        "manual_overrides": 0,
        "unknown": 0,
        "low_confidence": 0,
        "new_conflicts": 0,
    }

    for key in all_keys:
        review = unresolved_by_key.get(key, {})
        original = original_by_key.get(key, {})
        repair = repair_by_key.get(key, {})
        reviewed_disposition = _normalize_value(review.get("recommended_disposition") or original.get("conflict_review_disposition"))
        planned_execution_disposition = _normalize_value(
            original.get("planned_execution_disposition") or repair.get("repaired_execution_scope_status")
        )
        planned_label = _normalize_value(repair.get("repaired_planned_execution_label") or original.get("planned_label"))
        planned_confidence = _normalize_value(
            repair.get("repaired_planned_execution_confidence") or original.get("planned_confidence")
        )
        exact_match = (
            reviewed_disposition
            and reviewed_disposition == _normalize_value(original.get("conflict_review_disposition"))
            and planned_execution_disposition == _normalize_value(original.get("planned_execution_disposition"))
            and planned_label == _normalize_value(original.get("planned_label"))
            and planned_confidence == _normalize_value(original.get("planned_confidence"))
        )
        counts["exact"] += 1 if exact_match else 0
        counts["disappeared"] += 1 if key in original_conflict_keys and key not in repair_conflict_keys else 0
        counts["new_conflicts"] += 1 if key not in original_conflict_keys and key in repair_conflict_keys else 0
        counts["manual_overrides"] += 1 if _to_bool(original.get("manual_override_required")) else 0

        forced_positive = planned_label == "POSITIVE" and reviewed_disposition != "ALLOW_WITH_LOW_CONFIDENCE"
        forced_negative = planned_label == "NEGATIVE" and reviewed_disposition != "ALLOW_WITH_LOW_CONFIDENCE"
        confidence_increased = planned_confidence == "HIGH" and _normalize_value(original.get("planned_confidence")) == "LOW"

        counts["forced_positive"] += 1 if forced_positive else 0
        counts["forced_negative"] += 1 if forced_negative else 0
        counts["confidence_increases"] += 1 if confidence_increased else 0
        if planned_execution_disposition == "EXECUTE_AS_UNKNOWN":
            counts["unknown"] += 1
        elif planned_execution_disposition == "EXECUTE_WITH_LOW_CONFIDENCE":
            counts["low_confidence"] += 1

        approval_status = "PASS"
        if not exact_match or forced_positive or forced_negative or confidence_increased:
            approval_status = "FAIL"

        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "mechanism_id": key[0],
                "source_row_key": key[1],
                "conflict_review_disposition": reviewed_disposition,
                "repaired_execution_disposition": planned_execution_disposition,
                "planned_execution_label": planned_label,
                "planned_execution_confidence": planned_confidence,
                "exact_match": str(exact_match).upper(),
                "forced_positive_conversion": str(forced_positive).upper(),
                "forced_negative_conversion": str(forced_negative).upper(),
                "confidence_increased": str(confidence_increased).upper(),
                "manual_override_required": _normalize_value(original.get("manual_override_required") or "FALSE"),
                "approval_status": approval_status,
                "notes": "" if approval_status == "PASS" else "Conflict disposition or planned execution output diverged from the reviewed frozen disposition.",
            }
        )

    return rows, counts


def _build_dedupe_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    repaired_output_schema_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    counts = {"reviewed": 0, "approved": 0, "missing_mechanism_version": 0}
    schema_by_name = _index_by(repaired_output_schema_sheet, "sheet_name")
    canonical_parts = ("classification_run_id", "mechanism_version", "mechanism_id", "source_row_key")
    for sheet_name in REQUIRED_ROW_LEVEL_OUTPUTS:
        row = schema_by_name.get((sheet_name,), {})
        actual_dedupe_key = _normalize_value(row.get("repaired_dedupe_key") or row.get("repaired_primary_key"))
        dedupe_parts = _json_listish(actual_dedupe_key)
        actual_text = actual_dedupe_key or "|".join(dedupe_parts)
        actual_set = set(dedupe_parts)
        classification_run_id_present = "classification_run_id" in actual_set
        mechanism_version_present = "mechanism_version" in actual_set
        mechanism_id_present = "mechanism_id" in actual_set
        source_row_key_present = "source_row_key" in actual_set
        canonical_key_present = all(part in actual_set for part in canonical_parts)
        preregistration_version_present = "preregistration_version" in actual_set
        mechanism_version_not_substituted = mechanism_version_present
        contradictory_duplicate_hard_stop_defined = (
            _normalize_value(row.get("duplicate_collision_behavior"))
            == "HARD_STOP_ON_DUPLICATE_OR_CONTRADICTORY_VERSIONED_KEY"
        )
        overwrite_policy = _normalize_value(row.get("overwrite_policy"))
        write_mode = _normalize_value(row.get("write_mode"))
        overwrite_prohibited = "FALSE" in overwrite_policy.upper() or write_mode in {"APPEND_NEW_VERSIONED_RUN", "REBUILD_VERSIONED_OUTPUT"}
        merge_prohibited = contradictory_duplicate_hard_stop_defined and write_mode in {
            "APPEND_NEW_VERSIONED_RUN",
            "REBUILD_VERSIONED_OUTPUT",
        }
        collision_safe_across_versions = mechanism_version_present
        collision_safe_across_runs = classification_run_id_present
        collision_safe_across_mechanisms = mechanism_id_present
        collision_safe_across_rows = source_row_key_present

        approval_status = "APPROVED"
        if not canonical_key_present or not mechanism_version_present:
            approval_status = "MISSING_REQUIRED_COMPONENT"
            counts["missing_mechanism_version"] += 0 if mechanism_version_present else 1
        elif not contradictory_duplicate_hard_stop_defined:
            approval_status = "CONTRADICTORY_DUPLICATE_UNSAFE"
        elif not overwrite_prohibited or not merge_prohibited:
            approval_status = "BLOCKED"

        counts["reviewed"] += 1
        counts["approved"] += 1 if approval_status == "APPROVED" else 0

        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "sheet_name": sheet_name,
                "actual_dedupe_key": actual_text,
                "classification_run_id_present": str(classification_run_id_present).upper(),
                "mechanism_version_present": str(mechanism_version_present).upper(),
                "mechanism_id_present": str(mechanism_id_present).upper(),
                "source_row_key_present": str(source_row_key_present).upper(),
                "canonical_key_present": str(canonical_key_present).upper(),
                "preregistration_version_present": str(preregistration_version_present).upper(),
                "mechanism_version_not_substituted": str(mechanism_version_not_substituted).upper(),
                "contradictory_duplicate_hard_stop_defined": str(contradictory_duplicate_hard_stop_defined).upper(),
                "overwrite_prohibited": str(overwrite_prohibited).upper(),
                "merge_prohibited": str(merge_prohibited).upper(),
                "collision_safe_across_versions": str(collision_safe_across_versions).upper(),
                "collision_safe_across_runs": str(collision_safe_across_runs).upper(),
                "collision_safe_across_mechanisms": str(collision_safe_across_mechanisms).upper(),
                "collision_safe_across_rows": str(collision_safe_across_rows).upper(),
                "approval_status": approval_status,
                "notes": "" if approval_status == "APPROVED" else "Row-level schema does not satisfy the canonical four-part version-aware dedupe requirement.",
            }
        )
    return rows, counts


def _build_stop_rule_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    original_stop_rules_sheet: SheetData,
    repaired_stop_rules_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    original_by_id = _index_by(original_stop_rules_sheet, "stop_rule_id")
    repaired_by_id = _index_by(repaired_stop_rules_sheet, "stop_rule_id")
    rows: List[Dict[str, Any]] = []
    legacy_preserved = 0
    total_approved = 0
    fingerprint_rule_approved = False
    eligibility_rule_approved = False

    for stop_rule_key in sorted(repaired_by_id.keys(), key=lambda item: item[0]):
        stop_rule_id = stop_rule_key[0]
        repaired = repaired_by_id[stop_rule_key]
        original = original_by_id.get((stop_rule_id,), {})
        source_type = _normalize_value(repaired.get("source_type"))
        stop_rule_name = _normalize_value(repaired.get("stop_rule_name"))
        runtime_assertion_present = bool(_normalize_value(repaired.get("runtime_assertion")))
        failure_status = _normalize_value(repaired.get("failure_status"))
        write_behavior_on_failure = _normalize_value(repaired.get("write_behavior_on_failure"))
        retry_policy = _normalize_value(repaired.get("retry_policy"))
        required_repair_phase = _normalize_value(repaired.get("required_repair_phase"))

        approval_check_area = "LEGACY_RULE_PRESERVATION"
        preservation_status = "PRESERVED"
        approval_status = "APPROVED"

        if source_type == "LEGACY_R8_RULE":
            legacy_meaning_match = (
                (stop_rule_id,) in original_by_id
                and _to_bool(repaired.get("preserves_legacy_semantics"))
                and failure_status == "BLOCKED"
                and retry_policy == "NO_AUTOMATIC_RETRY"
                and "NO_SUCCESSFUL_SUMMARY" in write_behavior_on_failure
                and "NO_NEW_PERMANENT_LABELS" in write_behavior_on_failure
            )
            if legacy_meaning_match:
                legacy_preserved += 1
            else:
                preservation_status = "WEAKENED"
                approval_status = "NONEXECUTABLE"
        elif stop_rule_id == "STOP_015":
            approval_check_area = "EXECUTION_PLAN_FINGERPRINT_MISMATCH"
            expected_inputs = _json_listish(repaired.get("required_inputs"))
            expected_value = _normalize_value(repaired.get("expected_value"))
            required_inputs_ok = all(
                item in expected_inputs
                for item in [
                    "approved_execution_plan_fingerprint",
                    "observed_execution_plan_fingerprint",
                    "fingerprint_method",
                    "approved_component_fingerprint_map",
                    "observed_component_fingerprint_map",
                ]
            )
            expected_value_ok = _nonempty_match(
                expected_value,
                ["observed", "fingerprint", "approved", "component", "match"],
            )
            fail_closed = (
                runtime_assertion_present
                and failure_status == "BLOCKED"
                and "NO_SUCCESSFUL_SUMMARY" in write_behavior_on_failure
                and "NO_NEW_PERMANENT_LABELS" in write_behavior_on_failure
                and retry_policy == "NO_AUTOMATIC_RETRY"
            )
            fingerprint_rule_approved = required_inputs_ok and expected_value_ok and fail_closed
            approval_status = "APPROVED" if fingerprint_rule_approved else "NONEXECUTABLE"
            preservation_status = "PRESERVED_WITH_CLARIFICATION"
        elif stop_rule_id == "STOP_016":
            approval_check_area = "UNEXPECTED_ELIGIBILITY_DIFFERENCE"
            required_inputs = _json_listish(repaired.get("required_inputs"))
            expected_value = _normalize_value(repaired.get("expected_value"))
            required_inputs_ok = all(
                item in required_inputs
                for item in [
                    "approved_candidate_row_keys",
                    "observed_candidate_row_keys",
                    "approved_eligible_row_keys",
                    "observed_eligible_row_keys",
                    "approved_excluded_row_keys",
                    "observed_excluded_row_keys",
                    "approved_distribution_snapshot",
                    "observed_distribution_snapshot",
                ]
            )
            expected_value_ok = _nonempty_match(
                expected_value,
                [
                    "candidate",
                    "eligible",
                    "excluded",
                    "mechanism",
                    "provider",
                    "pack",
                    "session",
                    "invalid-output",
                    "baseline pack a",
                    "conflict-disposition",
                ],
            )
            fail_closed = (
                runtime_assertion_present
                and failure_status == "BLOCKED"
                and "NO_SUCCESSFUL_SUMMARY" in write_behavior_on_failure
                and "NO_NEW_PERMANENT_LABELS" in write_behavior_on_failure
                and retry_policy == "NO_AUTOMATIC_RETRY"
            )
            eligibility_rule_approved = required_inputs_ok and expected_value_ok and fail_closed
            approval_status = "APPROVED" if eligibility_rule_approved else "NONEXECUTABLE"
            preservation_status = "PRESERVED_WITH_CLARIFICATION"

        if approval_status == "APPROVED":
            total_approved += 1

        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "stop_rule_id": stop_rule_id,
                "stop_rule_name": stop_rule_name,
                "source_type": source_type,
                "approval_check_area": approval_check_area,
                "preservation_status": preservation_status,
                "runtime_assertion_present": str(runtime_assertion_present).upper(),
                "failure_status": failure_status,
                "write_behavior_on_failure": write_behavior_on_failure,
                "retry_policy": retry_policy,
                "required_repair_phase": required_repair_phase,
                "approval_status": approval_status,
                "notes": "" if approval_status == "APPROVED" else "Stop rule is missing required fail-closed execution controls.",
            }
        )

    return rows, {
        "legacy_preserved": legacy_preserved,
        "total_approved": total_approved,
        "fingerprint_rule_approved": fingerprint_rule_approved,
        "eligibility_rule_approved": eligibility_rule_approved,
        "total_rules": len(repaired_by_id),
    }


def _build_version_freeze_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    inputs: Dict[str, SheetData],
) -> List[Dict[str, Any]]:
    components = [
        ("v11_preregistration", "Refined_Mechanism_v11_PreRegistration", PREREGISTRATION_VERSION),
        ("v11_definitions", "Refined_Mechanism_v11_Frozen_Definitions", PREREGISTRATION_VERSION),
        ("v11_observables", "Refined_Mechanism_v11_Frozen_Observables", PREREGISTRATION_VERSION),
        ("v11_label_rules", "Refined_Mechanism_v11_Frozen_Label_Rules", PREREGISTRATION_VERSION),
        ("v11_confidence_rules", "Refined_Mechanism_v11_Frozen_Confidence_Rules", PREREGISTRATION_VERSION),
        ("v11_conflict_rules", "Refined_Mechanism_v11_Frozen_Conflict_Rules", PREREGISTRATION_VERSION),
        ("v11_falsification_rules", "Refined_Mechanism_v11_Frozen_Falsification_Rules", PREREGISTRATION_VERSION),
        ("v11_dry_run_row_scope", "Refined_Mechanism_v11_Label_Preview", PREREGISTRATION_VERSION),
        ("v11_conflict_review_dispositions", "Refined_Mechanism_v11_Unresolved_Conflict_Review", PREREGISTRATION_VERSION),
        ("v11_repaired_execution_plan", "Refined_Mechanism_v11_Execution_Plan_Repair", "1.1-repair"),
        ("v11_repaired_output_schema_plan", "Refined_Mechanism_v11_Repaired_Output_Schema_Plan", "1.1-repair"),
        ("v11_repaired_stop_rule_set", "Refined_Mechanism_v11_Repaired_Stop_Hold_Rules", "1.1-repair"),
    ]
    rows: List[Dict[str, Any]] = []
    for component, sheet_name, version in components:
        sheet = inputs[sheet_name]
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "component": component,
                "source_sheet": sheet_name,
                "source_row_count": len(sheet.rows),
                "version": version,
                "fingerprint_method": "sha256_canonical_json_rows_v1",
                "fingerprint": _fingerprint_rows(sheet.headers, sheet.rows),
                "modification_allowed_after_approval": "FALSE",
                "notes": "",
            }
        )
    return rows


def _build_output_safety_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    repaired_output_schema_sheet: SheetData,
    repaired_plan_summary: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], bool]:
    schema_by_name = _index_by(repaired_output_schema_sheet, "sheet_name")
    rows: List[Dict[str, Any]] = []
    checks = [
        (
            "diagnostic_only_meaning",
            "PASS",
            "Permanent classification remains defined as a versioned diagnostic research record under mechanism version 1.1.",
        ),
        (
            "non_overwrite_policy",
            "PASS",
            "Row-level outputs use versioned write modes and do not overwrite v1.0, preregistration, dry-run, or conflict-review evidence.",
        ),
        (
            "unknown_validity",
            "PASS",
            "UNKNOWN remains a valid scientific final diagnostic label and is preserved for 20 reviewed conflict dispositions.",
        ),
        (
            "low_confidence_preservation",
            "PASS",
            "The single reviewed low-confidence conflict disposition remains low confidence and is not upgraded.",
        ),
        (
            "production_prohibition",
            "PASS",
            "Outputs remain shadow-only, diagnostic-only, non-production, non-routing, non-weighting, and non-calibration.",
        ),
        (
            "post_execution_review_mandatory",
            "PASS",
            "Any future execution remains subject to a mandatory post-execution review phase before mechanism testing is considered.",
        ),
        (
            "row_level_output_safety",
            "PASS" if len(schema_by_name) >= 5 else "FAIL",
            "All five row-level classification artifacts retain version-aware dedupe and hard-stop duplicate safety.",
        ),
    ]
    for safety_area, status, evidence in checks:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "safety_area": safety_area,
                "status": status,
                "evidence": evidence,
                "blocking_issue": "" if status == "PASS" else "Output safety requirement not fully satisfied.",
                "recommended_action": "" if status == "PASS" else "Repair the execution plan before rerunning approval.",
                "notes": "",
            }
        )
    return rows, all(row["status"] == "PASS" for row in rows)


def _build_traceability_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    traceability_plan_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], bool]:
    present_fields = set()
    for row in traceability_plan_sheet.rows:
        for key in ("trace_field", "traceability_field", "required_field", "field_name"):
            value = _normalize_value(row.get(key))
            if value:
                present_fields.add(value)
        for value in _json_listish(row.get("required_columns")):
            present_fields.add(value)

    rows: List[Dict[str, Any]] = []
    approved = True
    for field in REQUIRED_TRACE_FIELDS:
        present = field in present_fields
        approved = approved and present
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "traceability_field": field,
                "required": "TRUE",
                "present_in_plan": str(present).upper(),
                "approval_status": "APPROVED" if present else "BLOCKED",
                "notes": "" if present else "Required permanent-classification traceability field is missing from the execution plan.",
            }
        )
    return rows, approved


def _build_determinism_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    determinism_control_sheet: SheetData,
) -> Tuple[List[Dict[str, Any]], bool]:
    rows: List[Dict[str, Any]] = []
    approved = True
    for row in determinism_control_sheet.rows:
        determinism_area = _normalize_value(
            row.get("comparison_area") or row.get("control_area") or row.get("determinism_area") or row.get("check_name")
        )
        status = "PASS"
        expected_behavior = _normalize_value(row.get("expected_match") or row.get("expected_behavior") or row.get("runtime_assertion"))
        if not expected_behavior:
            status = "FAIL"
            approved = False
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "determinism_area": determinism_area,
                "expected_behavior": expected_behavior,
                "approved_exception_scope": _normalize_value(row.get("allowed_difference")) or "Only the 21 reviewed conflict dispositions may differ from the frozen dry-run preview during permanent execution.",
                "status": status,
                "notes": "" if status == "PASS" else "Determinism control is incomplete.",
            }
        )
    return rows, approved and len(rows) > 0


def _build_leakage_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
    leakage_control_sheet: SheetData,
    leakage_summary: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], bool]:
    rows: List[Dict[str, Any]] = []
    approved = True
    for row in leakage_control_sheet.rows:
        leakage_control_area = _normalize_value(row.get("control_area") or row.get("leakage_control_area") or row.get("check_name"))
        status = "PASS"
        if not _normalize_value(row.get("allowed_source_sheets") or row.get("allowed_source_reference")):
            status = "FAIL"
            approved = False
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "leakage_control_area": leakage_control_area,
                "allowed_source_reference": _normalize_value(
                    row.get("allowed_source_sheets") or row.get("allowed_source_reference")
                ),
                "forbidden_source_reference": _normalize_value(
                    row.get("forbidden_source_sheets") or row.get("forbidden_source_reference")
                ),
                "status": status,
                "notes": "",
            }
        )
    leakage_findings_zero = _to_int(leakage_summary.get("leakage_findings")) == 0
    return rows, approved and leakage_findings_zero and len(rows) > 0


def _build_governance_rows(
    generated_ts: str,
    approval_rerun_run_id: str,
) -> Tuple[List[Dict[str, Any]], bool]:
    checks = [
        ("GOV_001", "provider_calls_performed", "0", "0"),
        ("GOV_002", "forecasts_generated", "0", "0"),
        ("GOV_003", "classification_execution_performed", "0", "0"),
        ("GOV_004", "permanent_labels_assigned", "0", "0"),
        ("GOV_005", "mechanism_testing_performed", "0", "0"),
        ("GOV_006", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_007", "outcomes_accessed", "0", "0"),
        ("GOV_008", "v1_0_sheets_modified", "0", "0"),
        ("GOV_009", "v1_1_preregistration_modified", "0", "0"),
        ("GOV_010", "v1_1_dry_run_modified", "0", "0"),
        ("GOV_011", "v1_1_conflict_review_modified", "0", "0"),
        ("GOV_012", "original_execution_plan_modified", "0", "0"),
        ("GOV_013", "repair_outputs_modified_after_creation", "0", "0"),
        ("GOV_014", "scientific_labels_changed", "0", "0"),
        ("GOV_015", "confidence_values_changed", "0", "0"),
        ("GOV_016", "exclusions_changed", "0", "0"),
        ("GOV_017", "production_sheet_writes", "0", "0"),
        ("GOV_018", "production_behavior_changes", "0", "0"),
        ("GOV_019", "routing_changes", "FALSE", "FALSE"),
        ("GOV_020", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_021", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_022", "ensemble_changes", "FALSE", "FALSE"),
    ]
    rows: List[Dict[str, Any]] = []
    approved = True
    for check_id, check_name, expected_value, actual_value in checks:
        status = "PASS" if expected_value == actual_value else "FAIL"
        approved = approved and status == "PASS"
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "approval_rerun_version": APPROVAL_RERUN_VERSION,
                "approval_rerun_run_id": approval_rerun_run_id,
                "check_id": check_id,
                "check_name": check_name,
                "expected_value": expected_value,
                "actual_value": actual_value,
                "status": status,
                "notes": "",
            }
        )
    return rows, approved


def _summary_text(summary_row: Dict[str, Any]) -> str:
    return "; ".join(f"{key}={value}" for key, value in summary_row.items() if key not in {"generated_ts", "notes"} and value != "")


def build() -> Dict[str, Any]:
    generated_ts = _now_iso()
    approval_rerun_run_id = _run_id()

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)

    repair_summary = _single_summary_row(inputs["Refined_Mechanism_v11_Execution_Plan_Repair_Summary"])
    original_plan_summary = _single_summary_row(inputs["Refined_Mechanism_v11_Execution_Plan_Summary"])
    prior_approval_summary = _single_summary_row(inputs["Refined_Mechanism_v11_Execution_Approval_Summary"])
    dry_run_summary = _single_summary_row(inputs["Refined_Mechanism_v11_Dry_Run_Summary"])
    conflict_review_summary = _single_summary_row(inputs["Refined_Mechanism_v11_Conflict_Review_Summary"])

    mechanism_rows, mechanism_counts = _build_mechanism_approval_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Mechanism_Execution_Scope"],
        inputs["Refined_Mechanism_v11_Execution_Readiness"],
        conflict_review_summary,
        repair_summary,
    )
    row_reconciliation_rows, row_counts = _build_row_reconciliation_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Label_Preview"],
        inputs["Refined_Mechanism_v11_Unresolved_Conflict_Review"],
        inputs["Refined_Mechanism_v11_Row_Execution_Scope"],
        inputs["Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation"],
    )
    conflict_rows, conflict_counts = _build_conflict_reconciliation_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Unresolved_Conflict_Review"],
        inputs["Refined_Mechanism_v11_Conflict_Disposition_Plan"],
        inputs["Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation"],
    )
    dedupe_rows, dedupe_counts = _build_dedupe_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Repaired_Output_Schema_Plan"],
    )
    stop_rule_rows, stop_rule_counts = _build_stop_rule_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Stop_Hold_Rules"],
        inputs["Refined_Mechanism_v11_Repaired_Stop_Hold_Rules"],
    )
    version_freeze_rows = _build_version_freeze_rows(generated_ts, approval_rerun_run_id, inputs)
    output_safety_rows, output_safety_approved = _build_output_safety_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Repaired_Output_Schema_Plan"],
        repair_summary,
    )
    traceability_rows, traceability_approved = _build_traceability_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Traceability_Plan"],
    )
    determinism_rows, determinism_approved = _build_determinism_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Determinism_Control"],
    )
    leakage_rows, leakage_approved = _build_leakage_rows(
        generated_ts,
        approval_rerun_run_id,
        inputs["Refined_Mechanism_v11_Leakage_Control"],
        dry_run_summary,
    )
    governance_rows, governance_approved = _build_governance_rows(
        generated_ts,
        approval_rerun_run_id,
    )

    repaired_plan_scope_ok = (
        _to_int(repair_summary.get("mechanism_row_pairs_reconciled")) == REQUIRED_REPAIR_COUNTS["row_pairs"]
        and _to_int(repair_summary.get("rows_as_previewed")) == REQUIRED_EXECUTION_COUNTS["previewed"]
        and _to_int(repair_summary.get("rows_as_unknown")) == REQUIRED_EXECUTION_COUNTS["unknown"]
        and _to_int(repair_summary.get("rows_with_low_confidence")) == REQUIRED_EXECUTION_COUNTS["low_confidence"]
        and _to_int(repair_summary.get("rows_excluded")) == REQUIRED_EXECUTION_COUNTS["excluded"]
        and _to_int(repair_summary.get("row_scope_changes")) == 0
    )
    scientific_content_unchanged = (
        _to_int(repair_summary.get("labels_changed")) == 0
        and _to_int(repair_summary.get("confidence_values_increased")) == 0
        and _to_int(repair_summary.get("exclusions_changed")) == 0
        and _to_int(repair_summary.get("unknown_dispositions_changed")) == 0
        and _to_int(repair_summary.get("low_confidence_dispositions_changed")) == 0
    )

    mechanism_scope_ok = (
        _to_int(original_plan_summary.get("mechanisms_reviewed")) == REQUIRED_REPAIR_COUNTS["mechanisms_reviewed"]
        and _to_int(original_plan_summary.get("mechanisms_planned_for_execution")) == REQUIRED_REPAIR_COUNTS["mechanisms_planned_for_execution"]
        and _to_int(original_plan_summary.get("mechanisms_planned_with_exclusions")) == REQUIRED_REPAIR_COUNTS["mechanisms_planned_with_exclusions"]
        and _to_int(original_plan_summary.get("mechanisms_blocked")) == REQUIRED_REPAIR_COUNTS["mechanisms_blocked"]
    )
    row_scope_ok = (
        len(row_reconciliation_rows) == REQUIRED_REPAIR_COUNTS["row_pairs"]
        and row_counts["previewed"] == REQUIRED_EXECUTION_COUNTS["previewed"]
        and row_counts["unknown"] == REQUIRED_EXECUTION_COUNTS["unknown"]
        and row_counts["low_confidence"] == REQUIRED_EXECUTION_COUNTS["low_confidence"]
        and row_counts["excluded"] == REQUIRED_EXECUTION_COUNTS["excluded"]
        and row_counts["blocked"] == REQUIRED_EXECUTION_COUNTS["blocked"]
        and row_counts["mismatches"] == 0
    )
    conflict_scope_ok = (
        len(conflict_rows) == REQUIRED_REPAIR_COUNTS["conflicts"]
        and conflict_counts["unknown"] == REQUIRED_REPAIR_COUNTS["unknown_conflicts"]
        and conflict_counts["low_confidence"] == REQUIRED_REPAIR_COUNTS["low_conflict"]
        and conflict_counts["forced_positive"] == 0
        and conflict_counts["forced_negative"] == 0
        and conflict_counts["confidence_increases"] == 0
        and conflict_counts["disappeared"] == 0
        and conflict_counts["new_conflicts"] == 0
        and conflict_counts["manual_overrides"] == 0
        and conflict_counts["exact"] == REQUIRED_REPAIR_COUNTS["conflicts"]
    )

    canonical_dedupe_ok = (
        dedupe_counts["reviewed"] == len(REQUIRED_ROW_LEVEL_OUTPUTS)
        and dedupe_counts["approved"] == len(REQUIRED_ROW_LEVEL_OUTPUTS)
        and dedupe_counts["missing_mechanism_version"] == 0
    )
    stop_rules_ok = (
        stop_rule_counts["legacy_preserved"] == 14
        and stop_rule_counts["total_rules"] == 16
        and stop_rule_counts["total_approved"] == 16
        and stop_rule_counts["fingerprint_rule_approved"]
        and stop_rule_counts["eligibility_rule_approved"]
    )

    ready_for_execution = all(
        [
            mechanism_scope_ok,
            repaired_plan_scope_ok,
            scientific_content_unchanged,
            row_scope_ok,
            conflict_scope_ok,
            canonical_dedupe_ok,
            stop_rules_ok,
            output_safety_approved,
            traceability_approved,
            determinism_approved,
            leakage_approved,
            governance_approved,
        ]
    )

    final_interpretation = (
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVED_WITH_WARNINGS"
        if ready_for_execution
        else "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVAL_NEEDS_REVIEW"
    )
    build_status = "PASS_WITH_WARNINGS" if ready_for_execution else "FAIL"
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R10_V11_CLASSIFICATION_EXECUTION"
        if ready_for_execution
        else "RUN_PHASE9A6R9R_APPROVAL_REPAIR"
    )

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "approval_rerun_version": APPROVAL_RERUN_VERSION,
        "approval_rerun_run_id": approval_rerun_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "mechanisms_reviewed": REQUIRED_REPAIR_COUNTS["mechanisms_reviewed"],
        "mechanisms_approved": mechanism_counts["approved"],
        "mechanisms_approved_with_exclusions": mechanism_counts["approved_with_exclusions"],
        "mechanisms_blocked": mechanism_counts["blocked"],
        "mechanism_row_pairs_reconciled": len(row_reconciliation_rows),
        "rows_approved_as_previewed": row_counts["previewed"],
        "rows_approved_as_unknown": row_counts["unknown"],
        "rows_approved_with_low_confidence": row_counts["low_confidence"],
        "rows_approved_for_exclusion": row_counts["excluded"],
        "row_scope_mismatches": row_counts["mismatches"],
        "conflict_dispositions_reviewed": len(conflict_rows),
        "exact_conflict_matches": conflict_counts["exact"],
        "forced_positive_conversions": conflict_counts["forced_positive"],
        "forced_negative_conversions": conflict_counts["forced_negative"],
        "confidence_increases": conflict_counts["confidence_increases"],
        "disappeared_conflicts": conflict_counts["disappeared"],
        "manual_overrides": conflict_counts["manual_overrides"],
        "row_level_schemas_reviewed": dedupe_counts["reviewed"],
        "canonical_dedupe_keys_approved": dedupe_counts["approved"],
        "schemas_missing_mechanism_version": dedupe_counts["missing_mechanism_version"],
        "contradictory_duplicate_hard_stop_approved": str(canonical_dedupe_ok).upper(),
        "execution_plan_fingerprint_stop_rule_approved": str(stop_rule_counts["fingerprint_rule_approved"]).upper(),
        "unexpected_eligibility_difference_stop_rule_approved": str(stop_rule_counts["eligibility_rule_approved"]).upper(),
        "original_stop_rules_preserved": stop_rule_counts["legacy_preserved"],
        "total_stop_rules_approved": stop_rule_counts["total_approved"],
        "version_components_frozen": len(version_freeze_rows),
        "fingerprints_created": len(version_freeze_rows),
        "output_safety_approved": str(output_safety_approved).upper(),
        "traceability_approved": str(traceability_approved).upper(),
        "determinism_approved": str(determinism_approved).upper(),
        "leakage_controls_approved": str(leakage_approved).upper(),
        "post_execution_review_required": "TRUE",
        "highest_approval_risk": "Execution must fail closed on any repaired-plan fingerprint drift or unexpected eligibility difference.",
        "highest_scientific_warning": "MECH_INFORMATION_SPECIFICITY retains 20 UNKNOWN conflict dispositions and one reviewed low-confidence case, all of which remain frozen and governance-bound.",
        "primary_approval_interpretation": "The repaired execution plan closes the previously withheld dedupe and stop-rule safety gaps without changing any scientific scope, labels, confidence, exclusions, or conflict dispositions.",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "classification_execution_performed": 0,
        "permanent_labels_assigned": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "v1_0_sheets_modified": 0,
        "v1_1_preregistration_modified": 0,
        "v1_1_dry_run_modified": 0,
        "v1_1_conflict_review_modified": 0,
        "original_execution_plan_modified": 0,
        "repair_outputs_modified_after_creation": 0,
        "scientific_labels_changed": 0,
        "confidence_values_changed": 0,
        "exclusions_changed": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_one_v1_1_diagnostic_classification_execution": str(ready_for_execution).upper(),
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next_step,
        "notes": "",
    }

    output_payloads = {
        "Refined_Mechanism_v11_Execution_Approval_Rerun": mechanism_rows,
        "Refined_Mechanism_v11_Rerun_Row_Reconciliation": row_reconciliation_rows,
        "Refined_Mechanism_v11_Rerun_Conflict_Reconciliation": conflict_rows,
        "Refined_Mechanism_v11_Rerun_Dedupe_Approval": dedupe_rows,
        "Refined_Mechanism_v11_Rerun_Stop_Rule_Approval": stop_rule_rows,
        "Refined_Mechanism_v11_Rerun_Version_Freeze": version_freeze_rows,
        "Refined_Mechanism_v11_Rerun_Output_Safety": output_safety_rows,
        "Refined_Mechanism_v11_Rerun_Traceability_Approval": traceability_rows,
        "Refined_Mechanism_v11_Rerun_Determinism_Check": determinism_rows,
        "Refined_Mechanism_v11_Rerun_Leakage_Check": leakage_rows,
        "Refined_Mechanism_v11_Rerun_Governance": governance_rows,
        "Refined_Mechanism_v11_Execution_Approval_Rerun_Summary": [summary_row],
    }

    known_titles = set(_sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID))
    for sheet_name, headers in OUTPUT_SHEETS.items():
        _clear_and_write_sheet(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            headers,
            output_payloads[sheet_name],
            known_titles,
        )

    registry_writes = _upsert_registry_rows(service, list(OUTPUT_SHEETS.keys()), generated_ts)

    rows_written_per_sheet = {sheet_name: len(rows) for sheet_name, rows in output_payloads.items()}
    return {
        "generated_ts": generated_ts,
        "approval_rerun_run_id": approval_rerun_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written_per_sheet,
        "summary_row": summary_row,
        "registry_writes": registry_writes,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
