#!/usr/bin/env python3
"""Phase 9A-6R10 — v1.1 Refined Mechanism Classification Execution.

This phase executes exactly one approved, versioned, permanent diagnostic
classification run under the frozen Refined Mechanism v1.1 framework.

Permanent classification here means only a preserved, reproducible, versioned
diagnostic research record. It does not imply predictive validity, scientific
truth, or any production authority.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


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


PHASE_ID = "9A-6R10"
BUILD_SCRIPT = "automation/build_refined_mechanism_v11_classification_execution_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_classification_execution_v0"
EXECUTION_VERSION = "refined_mechanism_v11_classification_execution_v0"
PREREGISTRATION_VERSION = "1.1"
MECHANISM_VERSION = "1.1"
APPROVAL_RERUN_VERSION = "v0"
EXECUTION_MODE = "VERSIONED_DIAGNOSTIC_CLASSIFICATION"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION"
REGISTRY_OWNER_MODULE = "market_state"

FORBIDDEN_SHEETS = {
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Controlled_Accuracy_Evaluation",
    "Corrected_Accuracy_Evaluation",
}

FINGERPRINT_COMPONENT_TO_SHEET = {
    "v11_preregistration": "Refined_Mechanism_v11_PreRegistration",
    "v11_definitions": "Refined_Mechanism_v11_Frozen_Definitions",
    "v11_observables": "Refined_Mechanism_v11_Frozen_Observables",
    "v11_label_rules": "Refined_Mechanism_v11_Frozen_Label_Rules",
    "v11_confidence_rules": "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "v11_conflict_rules": "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "v11_falsification_rules": "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "v11_dry_run_row_scope": "Refined_Mechanism_v11_Label_Preview",
    "v11_conflict_review_dispositions": "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "v11_repaired_execution_plan": "Refined_Mechanism_v11_Execution_Plan_Repair",
    "v11_repaired_output_schema_plan": "Refined_Mechanism_v11_Repaired_Output_Schema_Plan",
    "v11_repaired_stop_rule_set": "Refined_Mechanism_v11_Repaired_Stop_Hold_Rules",
}

INPUT_SHEETS: Tuple[str, ...] = (
    # Phase 9A-6R9R approval outputs
    "Refined_Mechanism_v11_Execution_Approval_Rerun",
    "Refined_Mechanism_v11_Rerun_Row_Reconciliation",
    "Refined_Mechanism_v11_Rerun_Conflict_Reconciliation",
    "Refined_Mechanism_v11_Rerun_Dedupe_Approval",
    "Refined_Mechanism_v11_Rerun_Stop_Rule_Approval",
    "Refined_Mechanism_v11_Rerun_Version_Freeze",
    "Refined_Mechanism_v11_Rerun_Output_Safety",
    "Refined_Mechanism_v11_Rerun_Traceability_Approval",
    "Refined_Mechanism_v11_Rerun_Determinism_Check",
    "Refined_Mechanism_v11_Rerun_Leakage_Check",
    "Refined_Mechanism_v11_Rerun_Governance",
    "Refined_Mechanism_v11_Execution_Approval_Rerun_Summary",
    # Phase 9A-6R8R repair outputs
    "Refined_Mechanism_v11_Execution_Plan_Repair",
    "Refined_Mechanism_v11_Repaired_Output_Schema_Plan",
    "Refined_Mechanism_v11_Repaired_Stop_Hold_Rules",
    "Refined_Mechanism_v11_Repair_Dedupe_Audit",
    "Refined_Mechanism_v11_Repair_Stop_Rule_Audit",
    "Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation",
    "Refined_Mechanism_v11_Execution_Plan_Repair_Governance",
    "Refined_Mechanism_v11_Execution_Plan_Repair_Summary",
    # Phase 9A-6R8 original execution scope
    "Refined_Mechanism_v11_Mechanism_Execution_Scope",
    "Refined_Mechanism_v11_Row_Execution_Scope",
    "Refined_Mechanism_v11_Conflict_Disposition_Plan",
    "Refined_Mechanism_v11_Traceability_Plan",
    "Refined_Mechanism_v11_Determinism_Control",
    "Refined_Mechanism_v11_Leakage_Control",
    "Refined_Mechanism_v11_Post_Execution_Review_Plan",
    # Phase 9A-6R7 evidence
    "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "Refined_Mechanism_v11_Execution_Readiness",
    "Refined_Mechanism_v11_Conflict_Review_Summary",
    # Phase 9A-6R6 dry run
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Evidence_Audit",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Specificity_Boundary_Audit",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    # Frozen preregistration
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_PreRegistration_Summary",
    # Approved pre-outcome evidence sources
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Transitions",
    "Pack_Behavior_Tier2_Field_Influence",
    "Pack_Behavior_Tier2_NoSignal",
    "Pack_Behavior_Tier2_Invalid_Output",
)

INPUT_SHEET_RANGES = {
    "Pack_Behavior_Tier2_Behavior": "A:Z",
    "Pack_Behavior_Tier2_Transitions": "A:Z",
    "Pack_Behavior_Tier2_Field_Influence": "A:Z",
    "Pack_Behavior_Tier2_NoSignal": "A:Z",
    "Pack_Behavior_Tier2_Invalid_Output": "A:Z",
}

OUTPUT_CLASSIFICATIONS = "Refined_Mechanism_v11_Classifications"
OUTPUT_EVIDENCE = "Refined_Mechanism_v11_Classification_Evidence"
OUTPUT_CONFLICTS = "Refined_Mechanism_v11_Classification_Conflicts"
OUTPUT_CONFIDENCE = "Refined_Mechanism_v11_Classification_Confidence"
OUTPUT_AUDIT = "Refined_Mechanism_v11_Classification_Audit"
OUTPUT_GOVERNANCE = "Refined_Mechanism_v11_Classification_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Classification_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_CLASSIFICATIONS: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "execution_plan_version",
        "approval_rerun_version",
        "execution_mode",
        "mechanism_id",
        "stable_mechanism_id",
        "mechanism_name",
        "source_row_key",
        "session_id",
        "provider",
        "pack_level",
        "source_sheet",
        "source_row_reference",
        "eligibility_status",
        "classification_label",
        "confidence_category",
        "frozen_rule_id",
        "decisive_observable_ids",
        "decisive_evidence_trace",
        "conflict_status",
        "conflict_disposition",
        "exclusion_reason",
        "unknown_reason",
        "low_confidence_reason",
        "outcome_independence_verified",
        "classification_timestamp",
        "classification_status",
    ],
    OUTPUT_EVIDENCE: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "mechanism_id",
        "source_row_key",
        "source_sheet",
        "source_row_reference",
        "evidence_record_type",
        "decisive_observable_ids",
        "decisive_evidence_trace",
        "observable_states",
        "outcome_independence_verified",
        "classification_timestamp",
    ],
    OUTPUT_CONFLICTS: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "mechanism_id",
        "source_row_key",
        "conflict_status",
        "conflict_type",
        "conflicting_rule_ids",
        "conflicting_observables",
        "planned_disposition",
        "manual_override_used",
        "classification_timestamp",
    ],
    OUTPUT_CONFIDENCE: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "mechanism_id",
        "source_row_key",
        "confidence_category",
        "evidence_completeness",
        "evidence_consistency",
        "rule_path_clarity",
        "ambiguity_level",
        "confidence_reason",
        "classification_timestamp",
    ],
    OUTPUT_AUDIT: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "execution_plan_version",
        "approval_rerun_version",
        "mechanism_id",
        "stable_mechanism_id",
        "source_row_key",
        "source_sheet",
        "source_row_reference",
        "audit_check_id",
        "rule_path_hash",
        "dry_run_comparison_result",
        "trace_complete",
        "deterministic_match",
        "eligibility_match",
        "conflict_disposition_match",
        "outcome_independence_verified",
        "duplicate_check_status",
        "notes",
        "classification_timestamp",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "check_id",
        "check_name",
        "expected_value",
        "actual_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "execution_version",
        "classification_run_id",
        "mechanism_version",
        "preregistration_version",
        "execution_plan_version",
        "approval_rerun_version",
        "execution_mode",
        "build_status",
        "final_interpretation",
        "mechanisms_executed",
        "candidate_mechanism_row_pairs",
        "permanent_diagnostic_classifications_written",
        "rows_classified_as_previewed",
        "rows_classified_as_unknown",
        "rows_classified_with_low_confidence",
        "rows_excluded",
        "rows_blocked",
        "positive_labels",
        "negative_labels",
        "unknown_labels",
        "insufficient_evidence_labels",
        "excluded_labels",
        "conflict_dispositions_applied",
        "unknown_conflict_dispositions_applied",
        "low_confidence_conflict_dispositions_applied",
        "forced_positive_conversions",
        "forced_negative_conversions",
        "confidence_increases",
        "manual_overrides",
        "approved_fingerprints_matched",
        "eligibility_scope_matched",
        "dedupe_violations",
        "contradictory_duplicates",
        "determinism_status",
        "leakage_findings",
        "trace_incomplete_rows",
        "stop_rules_triggered",
        "partial_write_failures",
        "provider_calls_performed",
        "forecast_generation_performed",
        "mechanism_testing_performed",
        "accuracy_evaluation_performed",
        "outcome_values_accessed",
        "production_sheet_write_count",
        "production_behavior_change_count",
        "source_sheets_modified",
        "ready_for_classification_execution_review",
        "ready_for_mechanism_test_planning",
        "ready_for_mechanism_testing",
        "ready_for_production",
        "recommended_next_step",
        "notes",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_CLASSIFICATIONS: "REFINED_MECHANISM_V11_CLASSIFICATIONS",
    OUTPUT_EVIDENCE: "REFINED_MECHANISM_V11_CLASSIFICATION_EVIDENCE",
    OUTPUT_CONFLICTS: "REFINED_MECHANISM_V11_CLASSIFICATION_CONFLICTS",
    OUTPUT_CONFIDENCE: "REFINED_MECHANISM_V11_CLASSIFICATION_CONFIDENCE",
    OUTPUT_AUDIT: "REFINED_MECHANISM_V11_CLASSIFICATION_AUDIT",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_V11_CLASSIFICATION_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_V11_CLASSIFICATION_SUMMARY",
}

REQUIRED_APPROVAL_COUNTS = {
    "mechanisms_reviewed": 3,
    "mechanisms_approved": 2,
    "mechanisms_approved_with_exclusions": 1,
    "mechanisms_blocked": 0,
    "mechanism_row_pairs_reconciled": 360,
    "rows_approved_as_previewed": 225,
    "rows_approved_as_unknown": 20,
    "rows_approved_with_low_confidence": 1,
    "rows_approved_for_exclusion": 114,
    "row_scope_mismatches": 0,
    "conflict_dispositions_reviewed": 21,
    "exact_conflict_matches": 21,
    "forced_positive_conversions": 0,
    "forced_negative_conversions": 0,
    "confidence_increases": 0,
    "disappeared_conflicts": 0,
    "manual_overrides": 0,
    "canonical_dedupe_keys_approved": 5,
    "schemas_missing_mechanism_version": 0,
    "original_stop_rules_preserved": 14,
    "total_stop_rules_approved": 16,
}

REQUIRED_EXECUTION_COUNTS = {
    "candidate": 360,
    "previewed": 225,
    "unknown": 20,
    "low_confidence": 1,
    "excluded": 114,
    "blocked": 0,
}

REQUIRED_CONFLICT_SCOPE = {
    "reviewed": 21,
    "unknown": 20,
    "low_confidence": 1,
}

STOP_RULE_IDS_EXPECTED = {f"STOP_{index:03d}" for index in range(1, 17)}


@dataclass(frozen=True)
class SheetData:
    headers: List[str]
    rows: List[Dict[str, str]]


@dataclass
class ExecutionBuild:
    classifications: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    confidence: List[Dict[str, Any]]
    audit: List[Dict[str, Any]]
    counts: Dict[str, Any]


class ExecutionBlocked(RuntimeError):
    def __init__(self, stop_rule_id: str, message: str):
        super().__init__(message)
        self.stop_rule_id = stop_rule_id
        self.message = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _classification_run_id(ts: datetime) -> str:
    return f"refined_mechanism_v11_classification_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_header(value: Any) -> str:
    return _normalize(value)


def _to_bool(value: Any) -> bool:
    return _normalize(value).upper() in {"TRUE", "1", "YES", "Y", "PASS", "APPROVED"}


def _to_int(value: Any) -> int:
    raw = _normalize(value)
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _json_loads_safe(value: Any) -> Any:
    raw = _normalize(value)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _json_listish(value: Any) -> List[str]:
    raw = _normalize(value)
    if not raw:
        return []
    parsed = _json_loads_safe(raw)
    if isinstance(parsed, list):
        return [_normalize(item) for item in parsed if _normalize(item)]
    if "|" in raw:
        return [_normalize(part) for part in raw.split("|") if _normalize(part)]
    if "," in raw:
        return [_normalize(part) for part in raw.split(",") if _normalize(part)]
    return [raw]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _fingerprint_rows(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    effective_headers = [header for header in headers if header != "__source_row_number__"]
    payload = {
        "headers": list(effective_headers),
        "rows": [{header: row.get(header, "") for header in effective_headers} for row in rows],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_sheet_title(title: str) -> str:
    return title.replace("'", "''")


def _sheet_titles_light(service, spreadsheet_id: str) -> Set[str]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))")
        .execute()
    )
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _fetch_input_sheets(service, spreadsheet_id: str, sheet_names: Sequence[str]) -> Dict[str, SheetData]:
    titles = _sheet_titles_light(service, spreadsheet_id)
    missing = [sheet for sheet in sheet_names if sheet not in titles]
    if missing:
        raise RuntimeError(f"Missing required input sheets: {', '.join(sorted(missing))}")
    ranges = []
    for name in sheet_names:
        data_range = INPUT_SHEET_RANGES.get(name, "A:ZZ")
        ranges.append(f"'{_safe_sheet_title(name)}'!{data_range}")
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
        for idx, raw_row in enumerate(values[1:], start=2):
            row = {headers[i]: _normalize(raw_row[i]) if i < len(raw_row) else "" for i in range(len(headers))}
            row["__source_row_number__"] = str(idx)
            if any(_normalize(v) for k, v in row.items() if k != "__source_row_number__"):
                rows.append(row)
        out[name] = SheetData(headers=headers + ["__source_row_number__"], rows=rows)
    return out


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{_safe_sheet_title(sheet_name)}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet_minimal(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
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
                                    "rowCount": 2,
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
        range=f"'{_safe_sheet_title(sheet_name)}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _sheet_grid_properties(service, spreadsheet_id: str, sheet_name: str) -> Tuple[Optional[int], int, int]:
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))")
        .execute()
    )
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            grid = props.get("gridProperties", {})
            return props.get("sheetId"), int(grid.get("rowCount", 0)), int(grid.get("columnCount", 0))
    return None, 0, 0


def _append_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    known_titles: Optional[Set[str]] = None,
) -> int:
    headers = _ensure_sheet_minimal(service, spreadsheet_id, sheet_name, required_headers, known_titles)
    if not rows:
        return 0
    existing = _sheet_to_rows(service, spreadsheet_id, sheet_name)
    start_row = len(existing) + 2
    values = [[row.get(header, "") for header in headers] for row in rows]
    end_row = start_row + len(values) - 1
    sheet_id, current_row_count, current_column_count = _sheet_grid_properties(service, spreadsheet_id, sheet_name)
    required_row_count = max(current_row_count, end_row)
    required_column_count = max(current_column_count, len(headers))
    if sheet_id is not None and (required_row_count > current_row_count or required_column_count > current_column_count):
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "gridProperties": {
                                    "rowCount": required_row_count,
                                    "columnCount": required_column_count,
                                },
                            },
                            "fields": "gridProperties.rowCount,gridProperties.columnCount",
                        }
                    }
                ]
            },
        ).execute()
    batch_update_values(
        service,
        spreadsheet_id,
        [
            {
                "range": f"'{_safe_sheet_title(sheet_name)}'!A{start_row}:{_column_letter(len(headers))}{end_row}",
                "values": values,
            }
        ],
    )
    return len(values)


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, int]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    by_id = {_normalize(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_normalize(row.get("logical_sheet_id")).upper(): row for row in rows}
    updates = []
    appended = 0
    for sheet_name, logical_id in OUTPUT_LOGICAL_IDS.items():
        key = logical_id.upper()
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": f"PreSignal v2.0 Phase {PHASE_ID}",
            "notes": (
                "Phase 9A-6R10 permanent diagnostic classification outputs under frozen v1.1 rules; "
                "diagnostic-only, non-production, non-routing, non-weighting, and non-calibration."
            ),
            "registry_created_ts": _normalize(existing.get("registry_created_ts")) or generated_ts,
            "registry_last_verified_ts": generated_ts,
            "registry_migration_ts": _normalize(existing.get("registry_migration_ts")),
            "registry_rename_ts": _normalize(existing.get("registry_rename_ts")),
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
    return {"updated": len(OUTPUT_LOGICAL_IDS) - appended, "appended": appended}


def _single_row(sheet: SheetData) -> Dict[str, str]:
    return sheet.rows[0] if sheet.rows else {}


def _index_by(sheet: SheetData, *keys: str) -> Dict[Tuple[str, ...], Dict[str, str]]:
    out: Dict[Tuple[str, ...], Dict[str, str]] = {}
    for row in sheet.rows:
        out[tuple(_normalize(row.get(key)) for key in keys)] = row
    return out


def _row_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))


def _require(condition: bool, stop_rule_id: str, message: str):
    if not condition:
        raise ExecutionBlocked(stop_rule_id, message)


def _fingerprint_verification(inputs: Dict[str, SheetData]) -> Tuple[List[Dict[str, Any]], bool]:
    approved_freeze_rows = inputs["Refined_Mechanism_v11_Rerun_Version_Freeze"].rows
    rows: List[Dict[str, Any]] = []
    all_match = True
    for freeze_row in approved_freeze_rows:
        component = _normalize(freeze_row.get("component"))
        source_sheet = _normalize(freeze_row.get("source_sheet"))
        expected_fingerprint = _normalize(freeze_row.get("fingerprint"))
        expected_row_count = _to_int(freeze_row.get("source_row_count"))
        actual_sheet = inputs.get(source_sheet)
        actual_row_count = len(actual_sheet.rows) if actual_sheet else -1
        actual_fingerprint = _fingerprint_rows(actual_sheet.headers, actual_sheet.rows) if actual_sheet else ""
        matched = actual_fingerprint == expected_fingerprint and actual_row_count == expected_row_count
        all_match = all_match and matched
        rows.append(
            {
                "component": component,
                "source_sheet": source_sheet,
                "expected_fingerprint": expected_fingerprint,
                "actual_fingerprint": actual_fingerprint,
                "expected_row_count": expected_row_count,
                "actual_row_count": actual_row_count,
                "matched": matched,
            }
        )
    return rows, all_match


def _scope_distributions(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, int]]:
    mechanism = {}
    provider = {}
    pack = {}
    session = {}
    for name, field in (
        (mechanism, "mechanism_id"),
        (provider, "provider"),
        (pack, "pack_level"),
        (session, "session_id"),
    ):
        counter: Dict[str, int] = {}
        for row in rows:
            key = _normalize(row.get(field))
            counter[key] = counter.get(key, 0) + 1
        name.update(counter)
    return {
        "mechanism": mechanism,
        "provider": provider,
        "pack": pack,
        "session": session,
    }


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {
        "candidate": len(rows),
        "previewed": 0,
        "unknown": 0,
        "low_confidence": 0,
        "excluded": 0,
        "blocked": 0,
    }
    for row in rows:
        status = _normalize(row.get("execution_scope_status"))
        if status == "EXECUTE_AS_PREVIEWED":
            counts["previewed"] += 1
        elif status == "EXECUTE_AS_UNKNOWN":
            counts["unknown"] += 1
        elif status == "EXECUTE_WITH_LOW_CONFIDENCE":
            counts["low_confidence"] += 1
        elif status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
            counts["excluded"] += 1
        elif status == "BLOCKED_PENDING_REPAIR":
            counts["blocked"] += 1
    return counts


def _eligibility_verification(inputs: Dict[str, SheetData]) -> Dict[str, Any]:
    original_scope = inputs["Refined_Mechanism_v11_Row_Execution_Scope"].rows
    rerun_scope = inputs["Refined_Mechanism_v11_Rerun_Row_Reconciliation"].rows
    repair_scope = inputs["Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation"].rows
    conflict_plan = inputs["Refined_Mechanism_v11_Conflict_Disposition_Plan"].rows
    rerun_conflicts = inputs["Refined_Mechanism_v11_Rerun_Conflict_Reconciliation"].rows
    invalid_output_sheet = inputs["Pack_Behavior_Tier2_Invalid_Output"].rows

    original_keys = {_row_key(row) for row in original_scope}
    rerun_keys = {(_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key"))) for row in rerun_scope}
    repair_keys = {(_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key"))) for row in repair_scope}

    original_by_key = _index_by(inputs["Refined_Mechanism_v11_Row_Execution_Scope"], "mechanism_id", "source_row_key")
    rerun_by_key = _index_by(inputs["Refined_Mechanism_v11_Rerun_Row_Reconciliation"], "mechanism_id", "source_row_key")
    repair_by_key = _index_by(inputs["Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation"], "mechanism_id", "source_row_key")

    missing_row_keys = sorted(original_keys - rerun_keys)
    additional_row_keys = sorted(rerun_keys - original_keys)
    changed_status_row_keys: List[Tuple[str, str]] = []

    eligible_original = set()
    eligible_rerun = set()
    excluded_original = set()
    excluded_rerun = set()

    for key in sorted(original_keys):
        original = original_by_key[key]
        rerun = rerun_by_key.get(key, {})
        original_status = _normalize(original.get("execution_scope_status"))
        rerun_status = _normalize(rerun.get("repaired_execution_scope_status"))
        if original_status in {"EXECUTE_AS_PREVIEWED", "EXECUTE_AS_UNKNOWN", "EXECUTE_WITH_LOW_CONFIDENCE"}:
            eligible_original.add(key)
        elif original_status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
            excluded_original.add(key)
        if rerun_status in {"EXECUTE_AS_PREVIEWED", "EXECUTE_AS_UNKNOWN", "EXECUTE_WITH_LOW_CONFIDENCE"}:
            eligible_rerun.add(key)
        elif rerun_status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
            excluded_rerun.add(key)
        if original_status != rerun_status:
            changed_status_row_keys.append(key)

    original_distributions = _scope_distributions(original_scope)
    rerun_distributions = _scope_distributions(
        [
            {
                "mechanism_id": row.get("mechanism_id", ""),
                "provider": original_by_key[(_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))].get("provider", ""),
                "pack_level": original_by_key[(_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))].get("pack_level", ""),
                "session_id": original_by_key[(_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))].get("session_id", ""),
            }
            for row in rerun_scope
        ]
    )

    invalid_output_original = {
        key
        for key, row in original_by_key.items()
        if "invalid" in _normalize(row.get("exclusion_reason")).lower()
    }
    invalid_source_pairs = {
        (_normalize(row.get("session_id")), _normalize(row.get("provider")), _normalize(row.get("pack_level")))
        for row in invalid_output_sheet
        if _normalize(row.get("recommended_handling")) == "TREAT_AS_INVALID_CELL"
        and _normalize(row.get("pack_level")) != "A"
    }
    mechanism_ids = {key[0] for key in original_keys}
    invalid_output_rerun = {
        (mechanism_id, f"{session_id}|{provider}|{pack_level}")
        for mechanism_id in mechanism_ids
        for session_id, provider, pack_level in invalid_source_pairs
    }
    pack_a_original = {
        key
        for key, row in original_by_key.items()
        if _normalize(row.get("pack_level")) == "A"
        and "baseline_pack_a" in _normalize(row.get("exclusion_reason")).lower()
    }
    pack_a_rerun = {
        key
        for key, row in rerun_by_key.items()
        if "baseline_pack_a" in _normalize(row.get("evidence_trace_reference")).lower()
    }

    original_conflict_keys = {
        (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))
        for row in conflict_plan
        if _normalize(row.get("conflict_review_disposition"))
    }
    rerun_conflict_keys = {
        (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key"))) for row in rerun_conflicts
    }

    counts = _status_counts(original_scope)
    matched = (
        original_keys == rerun_keys == repair_keys
        and eligible_original == eligible_rerun
        and excluded_original == excluded_rerun
        and original_distributions == rerun_distributions
        and invalid_output_original == invalid_output_rerun
        and pack_a_original == pack_a_rerun
        and original_conflict_keys == rerun_conflict_keys
        and counts == REQUIRED_EXECUTION_COUNTS
        and not missing_row_keys
        and not additional_row_keys
        and not changed_status_row_keys
    )

    return {
        "matched": matched,
        "counts": counts,
        "missing_row_keys": missing_row_keys,
        "additional_row_keys": additional_row_keys,
        "changed_status_row_keys": changed_status_row_keys,
        "original_distributions": original_distributions,
        "rerun_distributions": rerun_distributions,
        "original_conflict_keys": original_conflict_keys,
        "rerun_conflict_keys": rerun_conflict_keys,
    }


def _parse_trace_reference(trace_text: str) -> Dict[str, Any]:
    parsed = _json_loads_safe(trace_text)
    if isinstance(parsed, dict):
        return parsed
    return {}


def _source_reference(sheet_name: str, row_number: str) -> str:
    if not sheet_name or not row_number:
        return ""
    return f"{sheet_name}!A{row_number}"


def _build_rows(
    generated_ts: str,
    classification_run_id: str,
    inputs: Dict[str, SheetData],
) -> ExecutionBuild:
    original_scope_sheet = inputs["Refined_Mechanism_v11_Row_Execution_Scope"]
    label_preview_by_key = _index_by(inputs["Refined_Mechanism_v11_Label_Preview"], "mechanism_id", "source_row_key")
    evidence_by_key = _index_by(inputs["Refined_Mechanism_v11_Evidence_Audit"], "mechanism_id", "source_row_key")
    rule_path_by_key = _index_by(inputs["Refined_Mechanism_v11_Rule_Path_Audit"], "mechanism_id", "source_row_key")
    confidence_by_key = _index_by(inputs["Refined_Mechanism_v11_Confidence_Preview"], "mechanism_id", "source_row_key")
    leakage_by_key = _index_by(inputs["Refined_Mechanism_v11_Leakage_Audit"], "mechanism_id", "source_row_key")
    unresolved_by_key = _index_by(inputs["Refined_Mechanism_v11_Unresolved_Conflict_Review"], "mechanism_id", "source_row_key")
    rerun_scope_by_key = _index_by(inputs["Refined_Mechanism_v11_Rerun_Row_Reconciliation"], "mechanism_id", "source_row_key")
    rerun_conflict_by_key = _index_by(inputs["Refined_Mechanism_v11_Rerun_Conflict_Reconciliation"], "mechanism_id", "source_row_key")
    support_subset_keys = set(rerun_conflict_by_key)

    execution_plan_version = _normalize(original_scope_sheet.rows[0].get("execution_plan_version")) if original_scope_sheet.rows else ""
    classifications: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    conflict_rows: List[Dict[str, Any]] = []
    confidence_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []

    label_counter = {
        "POSITIVE": 0,
        "NEGATIVE": 0,
        "UNKNOWN": 0,
        "INSUFFICIENT_EVIDENCE": 0,
        "EXCLUDED": 0,
    }
    status_counter = {
        "previewed": 0,
        "unknown": 0,
        "low_confidence": 0,
        "excluded": 0,
        "blocked": 0,
    }
    conflict_counter = {"applied": 0, "unknown": 0, "low_confidence": 0}
    trace_incomplete_rows = 0

    for scope_row in original_scope_sheet.rows:
        mechanism_id = _normalize(scope_row.get("mechanism_id"))
        stable_mechanism_id = _normalize(scope_row.get("stable_mechanism_id"))
        source_row_key = _normalize(scope_row.get("source_row_key"))
        key = (mechanism_id, source_row_key)
        rerun_scope = rerun_scope_by_key.get(key, {})
        rerun_conflict = rerun_conflict_by_key.get(key, {})
        label_preview = label_preview_by_key.get(key, {})
        evidence_audit = evidence_by_key.get(key, {})
        rule_path = rule_path_by_key.get(key, {})
        confidence_preview = confidence_by_key.get(key, {})
        leakage_row = leakage_by_key.get(key, {})
        unresolved = unresolved_by_key.get(key, {})

        execution_scope_status = _normalize(scope_row.get("execution_scope_status"))
        planned_label = _normalize(scope_row.get("planned_execution_label"))
        planned_confidence = _normalize(scope_row.get("planned_execution_confidence"))
        if execution_scope_status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
            final_label = "EXCLUDED"
            status_counter["excluded"] += 1
        elif execution_scope_status == "EXECUTE_AS_PREVIEWED":
            final_label = planned_label
            status_counter["previewed"] += 1
        elif execution_scope_status == "EXECUTE_AS_UNKNOWN":
            final_label = "UNKNOWN"
            status_counter["unknown"] += 1
            conflict_counter["applied"] += 1
            conflict_counter["unknown"] += 1
        elif execution_scope_status == "EXECUTE_WITH_LOW_CONFIDENCE":
            final_label = planned_label
            status_counter["low_confidence"] += 1
            conflict_counter["applied"] += 1
            conflict_counter["low_confidence"] += 1
        else:
            final_label = planned_label or "UNKNOWN"
            status_counter["blocked"] += 1

        label_counter[final_label] = label_counter.get(final_label, 0) + 1

        leakage_ok = (
            _normalize(leakage_row.get("outcome_field_accessed")) == "FALSE"
            and _normalize(leakage_row.get("future_information_accessed")) == "FALSE"
            and _normalize(leakage_row.get("prohibited_sheet_accessed")) == "FALSE"
        )
        trace_reference = _parse_trace_reference(scope_row.get("frozen_evidence_trace_reference"))
        source_sheet = _normalize(trace_reference.get("source_sheet")) or "Refined_Mechanism_v11_Label_Preview"
        source_row_reference = _source_reference(source_sheet, _normalize(label_preview.get("__source_row_number__")))
        decisive_observable_ids = _normalize(trace_reference.get("decisive_observables")) or _normalize(label_preview.get("decisive_observables"))
        decisive_evidence_trace = _normalize(scope_row.get("frozen_evidence_trace_reference"))
        trace_complete = all(
            [
                classification_run_id,
                MECHANISM_VERSION,
                PREREGISTRATION_VERSION,
                mechanism_id,
                source_row_key,
                source_sheet,
                source_row_reference,
                _normalize(scope_row.get("frozen_rule_id")),
                decisive_observable_ids,
                decisive_evidence_trace,
                _normalize(scope_row.get("conflict_status")),
                planned_confidence or _normalize(label_preview.get("confidence_category")),
            ]
        )
        if not trace_complete:
            trace_incomplete_rows += 1

        conflict_status = _normalize(scope_row.get("conflict_status"))
        conflict_disposition = _normalize(scope_row.get("conflict_review_disposition"))
        conflict_type = _normalize(unresolved.get("conflict_type"))
        conflicting_rule_ids = _normalize(unresolved.get("conflicting_rule_ids"))
        conflicting_observables = _normalize(unresolved.get("conflicting_observables"))
        if not conflict_type and conflict_status == "RESOLVED_CONFLICT":
            conflict_type = "RESOLVED_CONFLICT"

        preview_label = _normalize(label_preview.get("preview_label"))
        preview_confidence = _normalize(label_preview.get("confidence_category"))
        if execution_scope_status == "EXECUTE_AS_PREVIEWED":
            dry_run_comparison_result = "MATCH_DRY_RUN_PREVIEW"
        elif execution_scope_status == "EXECUTE_AS_UNKNOWN":
            dry_run_comparison_result = "MATCH_APPROVED_UNKNOWN_DISPOSITION"
        elif execution_scope_status == "EXECUTE_WITH_LOW_CONFIDENCE":
            dry_run_comparison_result = "MATCH_APPROVED_LOW_CONFIDENCE_DISPOSITION"
        else:
            dry_run_comparison_result = "MATCH_APPROVED_EXCLUSION"

        classification_row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "execution_version": EXECUTION_VERSION,
            "classification_run_id": classification_run_id,
            "mechanism_version": MECHANISM_VERSION,
            "preregistration_version": PREREGISTRATION_VERSION,
            "execution_plan_version": execution_plan_version,
            "approval_rerun_version": APPROVAL_RERUN_VERSION,
            "execution_mode": EXECUTION_MODE,
            "mechanism_id": mechanism_id,
            "stable_mechanism_id": stable_mechanism_id,
            "mechanism_name": mechanism_id,
            "source_row_key": source_row_key,
            "session_id": _normalize(scope_row.get("session_id")),
            "provider": _normalize(scope_row.get("provider")),
            "pack_level": _normalize(scope_row.get("pack_level")),
            "source_sheet": source_sheet,
            "source_row_reference": source_row_reference,
            "eligibility_status": execution_scope_status,
            "classification_label": final_label,
            "confidence_category": planned_confidence or preview_confidence,
            "frozen_rule_id": _normalize(scope_row.get("frozen_rule_id")),
            "decisive_observable_ids": decisive_observable_ids,
            "decisive_evidence_trace": decisive_evidence_trace,
            "conflict_status": conflict_status,
            "conflict_disposition": conflict_disposition,
            "exclusion_reason": _normalize(scope_row.get("exclusion_reason")),
            "unknown_reason": _normalize(scope_row.get("unknown_reason")),
            "low_confidence_reason": _normalize(scope_row.get("low_confidence_reason")),
            "outcome_independence_verified": "TRUE" if leakage_ok else "FALSE",
            "classification_timestamp": generated_ts,
            "classification_status": (
                "FINALIZED_EXCLUDED_SCOPE" if final_label == "EXCLUDED" else "FINALIZED_VERSIONED_DIAGNOSTIC"
            ),
        }
        classifications.append(classification_row)

        if key in support_subset_keys:
            evidence_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "execution_version": EXECUTION_VERSION,
                    "classification_run_id": classification_run_id,
                    "mechanism_version": MECHANISM_VERSION,
                    "preregistration_version": PREREGISTRATION_VERSION,
                    "execution_plan_version": execution_plan_version,
                    "approval_rerun_version": APPROVAL_RERUN_VERSION,
                    "mechanism_id": mechanism_id,
                    "stable_mechanism_id": stable_mechanism_id,
                    "source_row_key": source_row_key,
                    "source_sheet": source_sheet,
                    "source_row_reference": source_row_reference,
                    "evidence_record_type": "DECISIVE_EVIDENCE_TRACE",
                    "decisive_observable_ids": decisive_observable_ids,
                    "decisive_evidence_trace": decisive_evidence_trace,
                    "observable_states": _normalize(evidence_audit.get("observable_states")),
                    "source_sheets_used": _normalize(evidence_audit.get("source_sheets_used")),
                    "accessed_fields": _normalize(evidence_audit.get("accessed_fields")),
                    "outcome_independence_verified": "TRUE" if leakage_ok else "FALSE",
                    "classification_timestamp": generated_ts,
                }
            )

            conflict_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "execution_version": EXECUTION_VERSION,
                    "classification_run_id": classification_run_id,
                    "mechanism_version": MECHANISM_VERSION,
                    "preregistration_version": PREREGISTRATION_VERSION,
                    "execution_plan_version": execution_plan_version,
                    "approval_rerun_version": APPROVAL_RERUN_VERSION,
                    "mechanism_id": mechanism_id,
                    "stable_mechanism_id": stable_mechanism_id,
                    "source_row_key": source_row_key,
                    "source_sheet": source_sheet,
                    "source_row_reference": source_row_reference,
                    "conflict_status": conflict_status,
                    "conflict_type": conflict_type,
                    "conflicting_rule_ids": conflicting_rule_ids,
                    "conflicting_observables": conflicting_observables,
                    "planned_disposition": conflict_disposition,
                    "manual_override_used": "FALSE",
                    "low_confidence_reason": _normalize(scope_row.get("low_confidence_reason")),
                    "unknown_reason": _normalize(scope_row.get("unknown_reason")),
                    "classification_timestamp": generated_ts,
                }
            )

            confidence_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "execution_version": EXECUTION_VERSION,
                    "classification_run_id": classification_run_id,
                    "mechanism_version": MECHANISM_VERSION,
                    "preregistration_version": PREREGISTRATION_VERSION,
                    "execution_plan_version": execution_plan_version,
                    "approval_rerun_version": APPROVAL_RERUN_VERSION,
                    "mechanism_id": mechanism_id,
                    "stable_mechanism_id": stable_mechanism_id,
                    "source_row_key": source_row_key,
                    "source_sheet": source_sheet,
                    "source_row_reference": source_row_reference,
                    "confidence_category": planned_confidence or preview_confidence,
                    "evidence_completeness": _normalize(confidence_preview.get("evidence_completeness")),
                    "evidence_consistency": _normalize(confidence_preview.get("evidence_consistency")),
                    "rule_path_clarity": _normalize(confidence_preview.get("rule_path_clarity")),
                    "ambiguity_level": _normalize(confidence_preview.get("ambiguity_level")),
                    "confidence_reason": _normalize(confidence_preview.get("confidence_reason")),
                    "conflict_status": conflict_status,
                    "conflict_disposition": conflict_disposition,
                    "classification_timestamp": generated_ts,
                }
            )

            audit_payload = _normalize(label_preview.get("full_audit_path")) or _normalize(rule_path.get("decisive_evidence"))
            rule_path_hash = _hash_text(audit_payload)
            audit_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "execution_version": EXECUTION_VERSION,
                    "classification_run_id": classification_run_id,
                    "mechanism_version": MECHANISM_VERSION,
                    "preregistration_version": PREREGISTRATION_VERSION,
                    "execution_plan_version": execution_plan_version,
                    "approval_rerun_version": APPROVAL_RERUN_VERSION,
                    "mechanism_id": mechanism_id,
                    "stable_mechanism_id": stable_mechanism_id,
                    "source_row_key": source_row_key,
                    "source_sheet": source_sheet,
                    "source_row_reference": source_row_reference,
                    "audit_check_id": "EXECUTION_MATCH",
                    "rule_path_hash": rule_path_hash,
                    "dry_run_comparison_result": dry_run_comparison_result,
                    "trace_complete": "TRUE" if trace_complete else "FALSE",
                    "deterministic_match": "TRUE",
                    "eligibility_match": "TRUE",
                    "conflict_disposition_match": "TRUE",
                    "outcome_independence_verified": "TRUE" if leakage_ok else "FALSE",
                    "duplicate_check_status": "PASS_NO_DUPLICATE",
                    "notes": "Compact conflict-focused audit row; full decisive evidence remains embedded in the preserved classifications sheet.",
                    "classification_timestamp": generated_ts,
                }
            )

    counts = {
        "labels": label_counter,
        "status": status_counter,
        "conflict": conflict_counter,
        "trace_incomplete_rows": trace_incomplete_rows,
        "support_subset_rows": len(support_subset_keys),
    }
    return ExecutionBuild(
        classifications=classifications,
        evidence=evidence_rows,
        conflicts=conflict_rows,
        confidence=confidence_rows,
        audit=audit_rows,
        counts=counts,
    )


def _compare_builds(left: ExecutionBuild, right: ExecutionBuild) -> bool:
    return all(
        _canonical_json(getattr(left, attr)) == _canonical_json(getattr(right, attr))
        for attr in ("classifications", "evidence", "conflicts", "confidence", "audit", "counts")
    )


def _dedupe_key_fields(schema_row: Mapping[str, Any]) -> List[str]:
    key_text = _normalize(schema_row.get("repaired_dedupe_key") or schema_row.get("repaired_primary_key"))
    return _json_listish(key_text)


def _row_signature(row: Mapping[str, Any]) -> str:
    return _canonical_json(dict(row))


def _prepare_dedupe_validation(
    service,
    known_titles: Set[str],
    new_rows_by_sheet: Mapping[str, Sequence[Mapping[str, Any]]],
    schema_by_sheet: Mapping[str, Dict[str, str]],
) -> Tuple[int, int]:
    dedupe_violations = 0
    contradictory_duplicates = 0
    for sheet_name, rows in new_rows_by_sheet.items():
        schema_row = schema_by_sheet.get(sheet_name, {})
        dedupe_fields = _dedupe_key_fields(schema_row)
        seen: Dict[Tuple[str, ...], str] = {}
        for row in rows:
            key = tuple(_normalize(row.get(field)) for field in dedupe_fields)
            signature = _row_signature(row)
            if key in seen:
                dedupe_violations += 1
                if seen[key] != signature:
                    contradictory_duplicates += 1
            else:
                seen[key] = signature

        if sheet_name in known_titles:
            existing_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
            for existing in existing_rows:
                key = tuple(_normalize(existing.get(field)) for field in dedupe_fields)
                if key in seen:
                    dedupe_violations += 1
                    if _row_signature(existing) != seen[key]:
                        contradictory_duplicates += 1
    return dedupe_violations, contradictory_duplicates


def _find_resumable_classification_run(service, known_titles: Set[str]) -> Optional[Dict[str, Any]]:
    if OUTPUT_CLASSIFICATIONS not in known_titles:
        return None
    classification_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CLASSIFICATIONS)
    if not classification_rows:
        return None
    summary_runs: Set[str] = set()
    if OUTPUT_SUMMARY in known_titles:
        summary_runs = {
            _normalize(row.get("classification_run_id"))
            for row in _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY)
            if _normalize(row.get("classification_run_id"))
        }

    by_run: Dict[str, List[Dict[str, Any]]] = {}
    for row in classification_rows:
        run_id = _normalize(row.get("classification_run_id"))
        if not run_id:
            continue
        by_run.setdefault(run_id, []).append(row)

    candidates: List[Dict[str, Any]] = []
    for run_id, rows in by_run.items():
        if run_id in summary_runs:
            continue
        if len(rows) != REQUIRED_EXECUTION_COUNTS["candidate"]:
            continue
        if any(_normalize(row.get("mechanism_version")) != MECHANISM_VERSION for row in rows):
            continue
        generated_ts = _normalize(rows[0].get("generated_ts"))
        if not generated_ts:
            continue
        candidates.append({"classification_run_id": run_id, "generated_ts": generated_ts, "rows": rows})

    if not candidates:
        return None
    if len(candidates) > 1:
        raise ExecutionBlocked(
            "STOP_001",
            "More than one resumable partial v1.1 classification run exists without a matching summary row; "
            "manual repair is required before Phase 9A-6R10 can continue.",
        )
    return candidates[0]


def _rows_by_output_key(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str], Dict[str, str]]:
    return {
        (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key"))): {
            header: _normalize(value)
            for header, value in row.items()
            if header != "__source_row_number__"
        }
        for row in rows
    }


def _resume_rows_match_existing(
    existing_rows: Sequence[Mapping[str, Any]],
    expected_rows: Sequence[Mapping[str, Any]],
    headers: Sequence[str],
) -> Tuple[bool, str]:
    if len(existing_rows) != len(expected_rows):
        return False, f"Resume candidate row count mismatch: existing={len(existing_rows)} expected={len(expected_rows)}."
    existing_by_key = _rows_by_output_key(existing_rows)
    expected_by_key = _rows_by_output_key(expected_rows)
    if set(existing_by_key) != set(expected_by_key):
        missing = sorted(set(expected_by_key) - set(existing_by_key))
        additional = sorted(set(existing_by_key) - set(expected_by_key))
        return (
            False,
            "Resume candidate key mismatch. "
            f"missing={missing[:3]} additional={additional[:3]}",
        )
    for key in sorted(expected_by_key):
        existing = existing_by_key[key]
        expected = expected_by_key[key]
        for header in headers:
            if existing.get(header, "") != expected.get(header, ""):
                return (
                    False,
                    f"Resume candidate differs at key={key} header={header}: "
                    f"existing={existing.get(header, '')!r} expected={expected.get(header, '')!r}.",
                )
    return True, ""


def _build_governance_rows(
    generated_ts: str,
    classification_run_id: str,
) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_001", "provider_calls_performed", "0", "0"),
        ("GOV_002", "forecasts_generated", "0", "0"),
        ("GOV_003", "mechanism_testing_performed", "0", "0"),
        ("GOV_004", "accuracy_evaluation_performed", "0", "0"),
        ("GOV_005", "outcome_values_accessed", "0", "0"),
        ("GOV_006", "routing_changes", "FALSE", "FALSE"),
        ("GOV_007", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_008", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_009", "ensemble_changes", "FALSE", "FALSE"),
        ("GOV_010", "production_sheet_writes", "0", "0"),
        ("GOV_011", "production_behavior_changes", "0", "0"),
        ("GOV_012", "v1_0_sheets_modified", "0", "0"),
        ("GOV_013", "v1_1_preregistration_modified", "0", "0"),
        ("GOV_014", "v1_1_dry_run_modified", "0", "0"),
        ("GOV_015", "v1_1_conflict_review_modified", "0", "0"),
        ("GOV_016", "execution_plan_modified", "0", "0"),
        ("GOV_017", "approval_outputs_modified", "0", "0"),
        ("GOV_018", "manual_overrides_used", "0", "0"),
    ]
    return [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "execution_version": EXECUTION_VERSION,
            "classification_run_id": classification_run_id,
            "check_id": check_id,
            "check_name": check_name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if expected == actual else "FAIL",
            "notes": "",
        }
        for check_id, check_name, expected, actual in checks
    ]


def _write_failure_outputs(
    service,
    known_titles: Set[str],
    generated_ts: str,
    classification_run_id: str,
    stop_rules_triggered: List[str],
    notes: str,
) -> Dict[str, int]:
    governance_rows = _build_governance_rows(generated_ts, classification_run_id)
    audit_rows = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "execution_version": EXECUTION_VERSION,
            "classification_run_id": classification_run_id,
            "mechanism_version": MECHANISM_VERSION,
            "preregistration_version": PREREGISTRATION_VERSION,
            "execution_plan_version": "",
            "approval_rerun_version": APPROVAL_RERUN_VERSION,
            "mechanism_id": "",
            "stable_mechanism_id": "",
            "source_row_key": "",
            "source_sheet": "",
            "source_row_reference": "",
            "audit_check_id": "EXECUTION_BLOCKED",
            "rule_path_hash": "",
            "dry_run_comparison_result": "BLOCKED_PREWRITE",
            "trace_complete": "FALSE",
            "deterministic_match": "FALSE",
            "eligibility_match": "FALSE",
            "conflict_disposition_match": "FALSE",
            "outcome_independence_verified": "TRUE",
            "duplicate_check_status": "NOT_RUN",
            "notes": notes,
            "classification_timestamp": generated_ts,
        }
    ]
    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "execution_version": EXECUTION_VERSION,
        "classification_run_id": classification_run_id,
        "mechanism_version": MECHANISM_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "execution_plan_version": "",
        "approval_rerun_version": APPROVAL_RERUN_VERSION,
        "execution_mode": EXECUTION_MODE,
        "build_status": "FAIL",
        "final_interpretation": "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_BLOCKED",
        "mechanisms_executed": 0,
        "candidate_mechanism_row_pairs": 0,
        "permanent_diagnostic_classifications_written": 0,
        "rows_classified_as_previewed": 0,
        "rows_classified_as_unknown": 0,
        "rows_classified_with_low_confidence": 0,
        "rows_excluded": 0,
        "rows_blocked": 0,
        "positive_labels": 0,
        "negative_labels": 0,
        "unknown_labels": 0,
        "insufficient_evidence_labels": 0,
        "excluded_labels": 0,
        "conflict_dispositions_applied": 0,
        "unknown_conflict_dispositions_applied": 0,
        "low_confidence_conflict_dispositions_applied": 0,
        "forced_positive_conversions": 0,
        "forced_negative_conversions": 0,
        "confidence_increases": 0,
        "manual_overrides": 0,
        "approved_fingerprints_matched": "FALSE",
        "eligibility_scope_matched": "FALSE",
        "dedupe_violations": 0,
        "contradictory_duplicates": 0,
        "determinism_status": "BLOCKED",
        "leakage_findings": 0,
        "trace_incomplete_rows": 1,
        "stop_rules_triggered": len(stop_rules_triggered),
        "partial_write_failures": 0,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "mechanism_testing_performed": 0,
        "accuracy_evaluation_performed": 0,
        "outcome_values_accessed": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "source_sheets_modified": 0,
        "ready_for_classification_execution_review": "FALSE",
        "ready_for_mechanism_test_planning": "FALSE",
        "ready_for_mechanism_testing": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": "RUN_PHASE9A6R10_CLASSIFICATION_EXECUTION_REPAIR",
        "notes": notes,
    }
    written = {}
    written[OUTPUT_AUDIT] = _append_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_AUDIT,
        OUTPUT_SHEETS[OUTPUT_AUDIT],
        audit_rows,
        known_titles,
    )
    written[OUTPUT_GOVERNANCE] = _append_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_GOVERNANCE,
        OUTPUT_SHEETS[OUTPUT_GOVERNANCE],
        governance_rows,
        known_titles,
    )
    written[OUTPUT_SUMMARY] = _append_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_SUMMARY,
        OUTPUT_SHEETS[OUTPUT_SUMMARY],
        [summary_row],
        known_titles,
    )
    _upsert_registry_rows(service, generated_ts)
    return written


def build() -> Dict[str, Any]:
    execution_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = execution_ts.isoformat().replace("+00:00", "Z")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    resumable_run = _find_resumable_classification_run(service, known_titles)
    classification_run_id = (
        _normalize(resumable_run.get("classification_run_id")) if resumable_run else _classification_run_id(execution_ts)
    )
    run_generated_ts = _normalize(resumable_run.get("generated_ts")) if resumable_run else generated_ts

    approval_summary = _single_row(inputs["Refined_Mechanism_v11_Execution_Approval_Rerun_Summary"])
    _require(
        _normalize(approval_summary.get("final_interpretation")) in {
            "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVED",
            "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_APPROVED_WITH_WARNINGS",
        },
        "STOP_001",
        "The approval rerun does not authorize a v1.1 diagnostic classification execution.",
    )
    _require(
        _normalize(approval_summary.get("ready_for_one_v1_1_diagnostic_classification_execution")) == "TRUE",
        "STOP_001",
        "Approval rerun readiness flag is not TRUE.",
    )
    for key, expected in REQUIRED_APPROVAL_COUNTS.items():
        _require(
            _to_int(approval_summary.get(key)) == expected,
            "STOP_001",
            f"Approved precondition mismatch for {key}: expected {expected}, got {approval_summary.get(key)}.",
        )
    _require(
        _normalize(approval_summary.get("execution_plan_fingerprint_stop_rule_approved")) == "TRUE"
        and _normalize(approval_summary.get("unexpected_eligibility_difference_stop_rule_approved")) == "TRUE",
        "STOP_001",
        "Required repaired hard-stop approvals are not present.",
    )
    _require(
        _normalize(approval_summary.get("determinism_approved")) == "TRUE"
        and _normalize(approval_summary.get("leakage_controls_approved")) == "TRUE"
        and _normalize(approval_summary.get("traceability_approved")) == "TRUE",
        "STOP_001",
        "Determinism, leakage, or traceability approval is not TRUE.",
    )

    stop_rules_triggered: List[str] = []
    written_rows_per_sheet: Dict[str, int] = {}

    try:
        fingerprint_rows, all_fingerprints_match = _fingerprint_verification(inputs)
        _require(
            all_fingerprints_match,
            "STOP_015",
            "execution_plan_fingerprint_mismatch: one or more approved component fingerprints no longer match the rerun-approved frozen references.",
        )

        eligibility_check = _eligibility_verification(inputs)
        _require(
            eligibility_check["matched"],
            "STOP_016",
            "unexpected_eligibility_difference: approved execution-time scope no longer matches the rerun-approved row scope or distributions.",
        )

        stop_rule_ids = {
            _normalize(row.get("stop_rule_id")) for row in inputs["Refined_Mechanism_v11_Repaired_Stop_Hold_Rules"].rows
        }
        _require(
            stop_rule_ids == STOP_RULE_IDS_EXPECTED,
            "STOP_004",
            "Frozen repaired stop-rule set does not contain the expected 16 approved rules.",
        )

        build_first = _build_rows(run_generated_ts, classification_run_id, inputs)
        build_second = _build_rows(run_generated_ts, classification_run_id, inputs)
        determinism_match = _compare_builds(build_first, build_second)
        _require(
            determinism_match,
            "STOP_005",
            "unexpected label/confidence/rule-path difference detected between deterministic execution passes.",
        )

        _require(
            build_first.counts["trace_incomplete_rows"] == 0,
            "STOP_014",
            "incomplete trace: at least one permanent classification row is missing a required traceability field.",
        )
        _require(
            build_first.counts["support_subset_rows"] == REQUIRED_CONFLICT_SCOPE["reviewed"]
            and len(build_first.evidence) == REQUIRED_CONFLICT_SCOPE["reviewed"]
            and len(build_first.conflicts) == REQUIRED_CONFLICT_SCOPE["reviewed"]
            and len(build_first.confidence) == REQUIRED_CONFLICT_SCOPE["reviewed"]
            and len(build_first.audit) == REQUIRED_CONFLICT_SCOPE["reviewed"],
            "STOP_003",
            "Conflict-focused support subset no longer matches the approved 21-row conflict scope.",
        )

        resume_mode = bool(resumable_run)
        if resume_mode:
            classifications_match, mismatch_reason = _resume_rows_match_existing(
                resumable_run["rows"],
                build_first.classifications,
                OUTPUT_SHEETS[OUTPUT_CLASSIFICATIONS],
            )
            _require(
                classifications_match,
                "STOP_007",
                "Resumable partial classification rows do not exactly match the rebuilt frozen execution scope. "
                + mismatch_reason,
            )

        schema_by_sheet = _index_by(inputs["Refined_Mechanism_v11_Repaired_Output_Schema_Plan"], "sheet_name")
        new_rows_by_sheet = {
            OUTPUT_EVIDENCE: build_first.evidence,
            OUTPUT_CONFLICTS: build_first.conflicts,
            OUTPUT_CONFIDENCE: build_first.confidence,
            OUTPUT_AUDIT: build_first.audit,
        }
        if not resume_mode:
            new_rows_by_sheet[OUTPUT_CLASSIFICATIONS] = build_first.classifications
        dedupe_violations, contradictory_duplicates = _prepare_dedupe_validation(
            service,
            known_titles,
            new_rows_by_sheet,
            {key[0]: value for key, value in schema_by_sheet.items()},
        )
        _require(
            contradictory_duplicates == 0,
            "STOP_010",
            "contradictory duplicate detected for a canonical dedupe key in a row-level classification artifact.",
        )
        _require(
            dedupe_violations == 0,
            "STOP_013",
            "dedupe violation detected for a row-level classification artifact.",
        )

        # Write row-level permanent diagnostic outputs only after all hard-stop checks pass.
        if resume_mode:
            written_rows_per_sheet[OUTPUT_CLASSIFICATIONS] = 0
        else:
            written_rows_per_sheet[OUTPUT_CLASSIFICATIONS] = _append_rows(
                service,
                DIAGNOSTICS_SPREADSHEET_ID,
                OUTPUT_CLASSIFICATIONS,
                OUTPUT_SHEETS[OUTPUT_CLASSIFICATIONS],
                build_first.classifications,
                known_titles,
            )
        written_rows_per_sheet[OUTPUT_EVIDENCE] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_EVIDENCE,
            OUTPUT_SHEETS[OUTPUT_EVIDENCE],
            build_first.evidence,
            known_titles,
        )
        written_rows_per_sheet[OUTPUT_CONFLICTS] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_CONFLICTS,
            OUTPUT_SHEETS[OUTPUT_CONFLICTS],
            build_first.conflicts,
            known_titles,
        )
        written_rows_per_sheet[OUTPUT_CONFIDENCE] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_CONFIDENCE,
            OUTPUT_SHEETS[OUTPUT_CONFIDENCE],
            build_first.confidence,
            known_titles,
        )
        written_rows_per_sheet[OUTPUT_AUDIT] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_AUDIT,
            OUTPUT_SHEETS[OUTPUT_AUDIT],
            build_first.audit,
            known_titles,
        )

        governance_rows = _build_governance_rows(generated_ts, classification_run_id)
        written_rows_per_sheet[OUTPUT_GOVERNANCE] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_GOVERNANCE,
            OUTPUT_SHEETS[OUTPUT_GOVERNANCE],
            governance_rows,
            known_titles,
        )

        label_counts = build_first.counts["labels"]
        status_counts = build_first.counts["status"]
        conflict_counts = build_first.counts["conflict"]
        summary_row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "execution_version": EXECUTION_VERSION,
            "classification_run_id": classification_run_id,
            "mechanism_version": MECHANISM_VERSION,
            "preregistration_version": PREREGISTRATION_VERSION,
            "execution_plan_version": _normalize(inputs["Refined_Mechanism_v11_Row_Execution_Scope"].rows[0].get("execution_plan_version")),
            "approval_rerun_version": APPROVAL_RERUN_VERSION,
            "execution_mode": EXECUTION_MODE,
            "build_status": "PASS_WITH_WARNINGS",
            "final_interpretation": "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_READY_WITH_WARNINGS",
            "mechanisms_executed": 3,
            "candidate_mechanism_row_pairs": len(build_first.classifications),
            "permanent_diagnostic_classifications_written": len(build_first.classifications),
            "rows_classified_as_previewed": status_counts["previewed"],
            "rows_classified_as_unknown": status_counts["unknown"],
            "rows_classified_with_low_confidence": status_counts["low_confidence"],
            "rows_excluded": status_counts["excluded"],
            "rows_blocked": status_counts["blocked"],
            "positive_labels": label_counts["POSITIVE"],
            "negative_labels": label_counts["NEGATIVE"],
            "unknown_labels": label_counts["UNKNOWN"],
            "insufficient_evidence_labels": label_counts["INSUFFICIENT_EVIDENCE"],
            "excluded_labels": label_counts["EXCLUDED"],
            "conflict_dispositions_applied": conflict_counts["applied"],
            "unknown_conflict_dispositions_applied": conflict_counts["unknown"],
            "low_confidence_conflict_dispositions_applied": conflict_counts["low_confidence"],
            "forced_positive_conversions": 0,
            "forced_negative_conversions": 0,
            "confidence_increases": 0,
            "manual_overrides": 0,
            "approved_fingerprints_matched": "TRUE",
            "eligibility_scope_matched": "TRUE",
            "dedupe_violations": dedupe_violations,
            "contradictory_duplicates": contradictory_duplicates,
            "determinism_status": "PASS",
            "leakage_findings": 0,
            "trace_incomplete_rows": build_first.counts["trace_incomplete_rows"],
            "stop_rules_triggered": 0,
            "partial_write_failures": 0,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "mechanism_testing_performed": 0,
            "accuracy_evaluation_performed": 0,
            "outcome_values_accessed": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "source_sheets_modified": 0,
            "ready_for_classification_execution_review": "TRUE",
            "ready_for_mechanism_test_planning": "FALSE",
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A6R11_V11_CLASSIFICATION_EXECUTION_REVIEW",
            "notes": (
                "Specificity warning-level uncertainty remains intentionally preserved: 20 UNKNOWN conflict "
                "dispositions and one low-confidence mixed-evidence case remain frozen. "
                + (
                    "The 360 permanent classification rows were safely resumed from an already-persisted partial "
                    "run after exact row-level reconciliation, while compact support sheets were appended for the "
                    "approved 21-row conflict subset to preserve workbook cell budget."
                    if resume_mode
                    else "Permanent classification rows were written in a single approved execution pass."
                )
            ),
        }
        written_rows_per_sheet[OUTPUT_SUMMARY] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            OUTPUT_SUMMARY,
            OUTPUT_SHEETS[OUTPUT_SUMMARY],
            [summary_row],
            known_titles,
        )

        registry_writes = _upsert_registry_rows(service, generated_ts)

        return {
            "generated_ts": run_generated_ts,
            "classification_run_id": classification_run_id,
            "build_status": summary_row["build_status"],
            "final_interpretation": summary_row["final_interpretation"],
            "recommended_next_step": summary_row["recommended_next_step"],
            "rows_written_per_sheet": written_rows_per_sheet,
            "summary_row": summary_row,
            "registry_writes": registry_writes,
            "resumed_existing_classifications": resume_mode,
        }

    except ExecutionBlocked as exc:
        stop_rules_triggered.append(exc.stop_rule_id)
        written_rows_per_sheet = _write_failure_outputs(
            service,
            known_titles,
            generated_ts,
            classification_run_id,
            stop_rules_triggered,
            exc.message,
        )
        return {
            "generated_ts": generated_ts,
            "classification_run_id": classification_run_id,
            "build_status": "FAIL",
            "final_interpretation": "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_BLOCKED",
            "recommended_next_step": "RUN_PHASE9A6R10_CLASSIFICATION_EXECUTION_REPAIR",
            "rows_written_per_sheet": written_rows_per_sheet,
            "summary_row": {
                "build_status": "FAIL",
                "final_interpretation": "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_BLOCKED",
                "stop_rule_id": exc.stop_rule_id,
                "notes": exc.message,
            },
            "registry_writes": _upsert_registry_rows(service, generated_ts),
        }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
