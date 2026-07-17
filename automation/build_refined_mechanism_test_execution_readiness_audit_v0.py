#!/usr/bin/env python3
"""Phase 9A-6R14S — Canonical Test Execution Readiness Audit.

This is the final read-only governance checkpoint before the first
outcome-bearing refined mechanism test execution. It verifies canonical
scientific authority, execution-environment freeze, blinding, determinism,
fail-closed behavior, and reproducibility without loading any outcome rows.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple


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
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore
from automation.build_refined_mechanism_v11_classification_execution_v0 import (  # type: ignore
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)


PHASE_ID = "9A-6R14S"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_readiness_audit_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_readiness_audit_v0"
READINESS_AUDIT_VERSION = "refined_mechanism_test_execution_readiness_audit_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION_READINESS"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
PARENT_CLEAN_VERSION = "1.0-clean"
PARENT_CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
ORIGINAL_VERSION = "1.0"
CLASSIFICATION_VERSION = "1.1"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"

PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"
PRIMARY_EXPOSURE = "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules"
PRIMARY_COMPARISON_GROUPS = "expanded consistency POSITIVE versus expanded consistency NEGATIVE"
BASELINE_ROLE = "same-provider same-session Pack A structural control used only for success-delta construction"
PRIMARY_ESTIMAND = (
    "difference in baseline-to-expanded corrected directional success deltas "
    "between expanded-state label groups"
)
PRIMARY_INTERPRETATION = "EXPLORATORY_PREREGISTERED_PRIMARY"
PRIMARY_METHOD_ID = "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta"

EXPECTED_COUNTS = {
    "structural_baseline_expanded_pairs": 96,
    "consistency_classified_pairs": 82,
    "high_moderate_confidence_pairs": 72,
    "primary_contrast_eligible_observations": 72,
    "positive_primary_observations": 57,
    "negative_primary_observations": 15,
    "mixed_label_provider_session_clusters": 12,
    "provider_count": 3,
    "session_count": 8,
    "cluster_count": 24,
}

EXPECTED_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_primary_contrast_observations": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
}

KNOWN_R1_RUN_IDS = {
    "9A-6R13R1_20260711T015443Z",
    "9A-6R13R1_20260711T015833Z",
    "9A-6R13R1_20260711T020141Z",
}

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}

EXECUTION_STOP_RULE_NAMES = {
    "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
    "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
    "CLASSIFICATION_FINGERPRINT_MISMATCH",
    "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
    "OUTCOME_VERSION_MISMATCH",
    "EVALUATION_WINDOW_MISMATCH",
    "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED",
    "AMBIGUOUS_JOIN",
    "DUPLICATE_JOIN",
    "PHYSICAL_ROW_NUMBER_JOIN_ATTEMPT",
    "FUZZY_JOIN_ATTEMPT",
    "MANUAL_JOIN_OVERRIDE_REQUESTED",
    "INVALID_SUCCESS_MAPPING",
    "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
    "POSITIVE_SAMPLE_GATE_FAILURE",
    "NEGATIVE_SAMPLE_GATE_FAILURE",
    "PRIMARY_CONTRAST_GATE_FAILURE",
    "CLUSTER_GATE_FAILURE",
    "PROVIDER_GATE_FAILURE",
    "SESSION_GATE_FAILURE",
    "UNKNOWN_CONVERTED_TO_NEGATIVE",
    "INSUFFICIENT_EVIDENCE_CONVERTED_TO_NEGATIVE",
    "LOW_CONFIDENCE_INCLUDED_IN_PRIMARY",
    "UNAPPROVED_STATISTICAL_FALLBACK",
    "PRIMARY_METHOD_COMPUTATION_FAILED",
    "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
    "DESIGN_CHANGE_AFTER_APPROVAL",
    "OUTCOME_ACCESS_BEFORE_APPROVAL",
    "PRODUCTION_WRITE_ATTEMPT",
}

AUTHORITY_STOP_RULE_NAMES = {
    "AUTHORITATIVE_RUN_ID_MISSING",
    "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT",
    "AUTHORITATIVE_COMPONENT_MISSING",
    "AUTHORITATIVE_COMPONENT_INCOMPLETE",
    "SUPERSEDED_ROW_SELECTED",
    "LATEST_ROW_SELECTION_ATTEMPT",
    "LATEST_TIMESTAMP_SELECTION_ATTEMPT",
    "MANUAL_AUTHORITY_OVERRIDE_REQUESTED",
    "AUTHORITATIVE_FINGERPRINT_MISMATCH",
    "FINGERPRINT_MANIFEST_INCOMPLETE",
    "PARTIAL_ROW_INCLUDED_IN_FINGERPRINT",
    "NONAUTHORITATIVE_RUN_USED_FOR_EXECUTION",
    "AUTHORITY_VERSION_MISMATCH",
    "AUTHORITY_RUN_ID_MISMATCH",
    "MIXED_RUN_CONTRACT_ASSEMBLY_ATTEMPT",
}

AUTHORITY_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Component_Authority",
    "Refined_Mechanism_Test_Clean_R1_Historical_Run_Disposition",
    "Refined_Mechanism_Test_Clean_R1_Scientific_Equivalence_Audit",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
    "Refined_Mechanism_Test_Clean_R1_Authority_Stop_Rules",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Governance",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Summary",
)

R1_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Preregistration_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1",
    "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1",
    "Refined_Mechanism_Test_Clean_R1_Design_Reconciliation",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Audit",
    "Refined_Mechanism_Test_Clean_R1_Blinding_Audit",
    "Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Clean_R1_Governance",
    "Refined_Mechanism_Test_Preregistration_Clean_R1_Summary",
)

PARENT_CLEAN_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Preregistration_Clean",
    "Refined_Mechanism_Test_Frozen_Hypotheses_Clean",
    "Refined_Mechanism_Test_Frozen_Population_Clean",
    "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis_Clean",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean",
    "Refined_Mechanism_Test_Frozen_Comparison_Design_Clean",
    "Refined_Mechanism_Test_Frozen_Cluster_Design_Clean",
    "Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Confidence_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Unknown_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Confounder_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Multiple_Testing_Clean",
    "Refined_Mechanism_Test_Frozen_Missing_Data_Clean",
    "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean",
    "Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean",
    "Refined_Mechanism_Test_Clean_Lineage_Audit",
    "Refined_Mechanism_Test_Clean_Blinding_Audit",
    "Refined_Mechanism_Test_Clean_Design_Reconciliation",
    "Refined_Mechanism_Test_Clean_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Preregistration_Clean_Governance",
    "Refined_Mechanism_Test_Preregistration_Clean_Summary",
)

ORIGINAL_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Preregistration",
    "Refined_Mechanism_Test_Frozen_Hypotheses",
    "Refined_Mechanism_Test_Frozen_Population",
    "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition",
    "Refined_Mechanism_Test_Frozen_Comparison_Design",
    "Refined_Mechanism_Test_Frozen_Cluster_Design",
    "Refined_Mechanism_Test_Frozen_Eligibility_Rules",
    "Refined_Mechanism_Test_Frozen_Confidence_Rules",
    "Refined_Mechanism_Test_Frozen_Unknown_Rules",
    "Refined_Mechanism_Test_Frozen_Confounder_Rules",
    "Refined_Mechanism_Test_Frozen_Multiple_Testing",
    "Refined_Mechanism_Test_Frozen_Missing_Data",
    "Refined_Mechanism_Test_Frozen_Stop_Rules",
    "Refined_Mechanism_Test_Frozen_Reporting_Plan",
    "Refined_Mechanism_Test_Preregistration_Governance",
    "Refined_Mechanism_Test_Preregistration_Summary",
)

CANONICAL_APPROVAL_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1",
    "Refined_Mechanism_Test_Canonical_R1_Authority_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Historical_Isolation_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Fingerprint_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Blinding_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Science_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Count_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Outcome_Contract_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Join_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Success_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Method_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Load_Order_Approval",
    "Refined_Mechanism_Test_Canonical_R1_Approval_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary",
)

SUPPORT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
)

INPUT_SHEETS: Tuple[str, ...] = (
    *AUTHORITY_SHEETS,
    *R1_SHEETS,
    *PARENT_CLEAN_SHEETS,
    *ORIGINAL_SHEETS,
    *CANONICAL_APPROVAL_SHEETS,
    *SUPPORT_SHEETS,
)

OUTPUT_SHEETS = [
    "Refined_Mechanism_Test_Execution_Readiness",
    "Refined_Mechanism_Test_Canonical_Authority_Audit",
    "Refined_Mechanism_Test_Environment_Freeze",
    "Refined_Mechanism_Test_Execution_Order_Audit",
    "Refined_Mechanism_Test_Stop_Rule_Verification",
    "Refined_Mechanism_Test_Determinism_Verification",
    "Refined_Mechanism_Test_Reproducibility_Audit",
    "Refined_Mechanism_Test_Blinding_Verification",
    "Refined_Mechanism_Test_Readiness_Governance",
    "Refined_Mechanism_Test_Readiness_Summary",
]

COMMON_HEADERS = ["generated_ts", "schema_version", "readiness_audit_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R14S_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _sheet_cell_total(service) -> int:
    meta = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        fields="sheets(properties(gridProperties(rowCount,columnCount)))",
    ).execute()
    total = 0
    for sheet in meta.get("sheets", []):
        grid = sheet["properties"].get("gridProperties", {})
        total += int(grid.get("rowCount", 0)) * int(grid.get("columnCount", 0))
    return total


def _ensure_cell_budget(service, known_titles: Set[str]) -> Dict[str, Any]:
    current = _sheet_cell_total(service)
    required = sum(2 * len(COMMON_HEADERS) for name in OUTPUT_SHEETS if name not in known_titles)
    if current + required > 10_000_000:
        raise RuntimeError(
            f"Insufficient workbook cell budget for Phase {PHASE_ID}: current={current}, required={required}."
        )
    return {"cells_before": current, "cells_after": current, "required_cells": required}


def _ensure_output_sheets(service, known_titles: Set[str]) -> None:
    missing = [name for name in OUTPUT_SHEETS if name not in known_titles]
    if missing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": name,
                                "gridProperties": {
                                    "rowCount": 4,
                                    "columnCount": len(COMMON_HEADERS),
                                },
                            }
                        }
                    }
                    for name in missing
                ]
            },
        ).execute()
        known_titles.update(missing)

    meta = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))",
    ).execute()
    resize_requests = []
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        title = props.get("title")
        if title not in OUTPUT_SHEETS:
            continue
        grid = props.get("gridProperties", {})
        target_rows = max(int(grid.get("rowCount", 0)), 10)
        target_cols = max(int(grid.get("columnCount", 0)), len(COMMON_HEADERS))
        if target_rows != int(grid.get("rowCount", 0)) or target_cols != int(grid.get("columnCount", 0)):
            resize_requests.append(
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": props["sheetId"],
                            "gridProperties": {
                                "rowCount": target_rows,
                                "columnCount": target_cols,
                            },
                        },
                        "fields": "gridProperties.rowCount,gridProperties.columnCount",
                    }
                }
            )
    if resize_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": resize_requests},
        ).execute()

    batch_update_values(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        [
            {
                "range": f"'{name}'!A1:{_column_letter(len(COMMON_HEADERS))}1",
                "values": [COMMON_HEADERS],
            }
            for name in OUTPUT_SHEETS
        ],
    )


def _latest_payload(rows: Sequence[Mapping[str, Any]], run_key: str) -> Dict[str, Any]:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            _normalize(row.get("generated_ts")),
            _normalize(row.get(run_key)),
            int(row.get("__source_row_number__", 0) or 0),
        ),
    )
    payload = _normalize(ordered[-1].get("payload_json"))
    return json.loads(payload) if payload else {}


def _latest_row(rows: Sequence[Mapping[str, Any]], run_key: str) -> Dict[str, Any]:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            _normalize(row.get("generated_ts")),
            _normalize(row.get(run_key)),
            int(row.get("__source_row_number__", 0) or 0),
        ),
    )
    return dict(ordered[-1])


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    cleaned = [{k: v for k, v in dict(row).items() if k != "__source_row_number__"} for row in rows]
    serialized = json.dumps(cleaned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_sorted_rows(rows: Sequence[Mapping[str, Any]], sort_fields: Sequence[str]) -> str:
    cleaned = [{k: v for k, v in dict(row).items() if k != "__source_row_number__"} for row in rows]
    ordered = sorted(
        cleaned,
        key=lambda row: tuple(_normalize(row.get(field)) for field in sort_fields),
    )
    serialized = json.dumps(ordered, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sheet_latest_row_fingerprint_entries(
    inputs: Mapping[str, Any],
    sheet_names: Sequence[str],
    run_key: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for sheet_name in sheet_names:
        latest = _latest_row(inputs[sheet_name].rows, run_key)
        cleaned = {k: v for k, v in latest.items() if k != "__source_row_number__"} if latest else {}
        entries.append(
            {
                "sheet_name": sheet_name,
                "fingerprint_method": "json_sha256_sorted_keys_without_source_row_number",
                "fingerprint": _fingerprint_payload(cleaned),
            }
        )
    return entries


def _sheet_full_row_fingerprint_entries(
    inputs: Mapping[str, Any],
    sheet_names: Sequence[str],
) -> List[Dict[str, Any]]:
    return [
        {
            "sheet_name": sheet_name,
            "row_count": len(inputs[sheet_name].rows),
            "fingerprint_method": "json_sha256_sorted_keys_without_source_row_number",
            "fingerprint": _fingerprint_rows([dict(row) for row in inputs[sheet_name].rows]),
        }
        for sheet_name in sheet_names
    ]


def _compare_expected_to_current(
    expected_entries: Sequence[Mapping[str, Any]],
    current_entries: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    expected = {
        _normalize(entry.get("sheet_name") or entry.get("component_id")): _normalize(entry.get("fingerprint"))
        for entry in expected_entries
    }
    current = {
        _normalize(entry.get("sheet_name") or entry.get("component_id")): _normalize(entry.get("fingerprint"))
        for entry in current_entries
    }
    mismatches: List[Dict[str, Any]] = []
    for key in sorted(set(expected) | set(current)):
        if expected.get(key) != current.get(key):
            mismatches.append(
                {
                    "key": key,
                    "expected_fingerprint": expected.get(key),
                    "observed_fingerprint": current.get(key),
                }
            )
    return {"match": not mismatches, "mismatches": mismatches}


def _classification_rows(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]


def _structure_counts(class_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    consistency_rows = [
        dict(row)
        for row in class_rows
        if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM
    ]
    baseline_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in consistency_rows:
        if _normalize(row.get("pack_level")) == "A":
            baseline_map[(_normalize(row.get("provider")), _normalize(row.get("session_id")))].append(row)

    expanded_structural = [
        row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) in {"B", "C", "D", "E"}
        and (_normalize(row.get("provider")), _normalize(row.get("session_id"))) in baseline_map
    ]
    classified = [
        row
        for row in expanded_structural
        if _normalize(row.get("classification_label")) != "EXCLUDED"
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
    ]
    high_mod = [
        row
        for row in classified
        if _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}
    ]
    pos_neg = [
        row
        for row in high_mod
        if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
    ]

    cluster_labels: Dict[str, Set[str]] = defaultdict(set)
    baseline_match_count_errors: List[Dict[str, Any]] = []
    for row in pos_neg:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        cluster_labels[cluster].add(_normalize(row.get("classification_label")))
        baseline_matches = baseline_map.get((_normalize(row.get("provider")), _normalize(row.get("session_id"))), [])
        if len(baseline_matches) != 1:
            baseline_match_count_errors.append(
                {
                    "source_row_key": _normalize(row.get("source_row_key")),
                    "provider": _normalize(row.get("provider")),
                    "session_id": _normalize(row.get("session_id")),
                    "baseline_match_count": len(baseline_matches),
                }
            )

    return {
        "structural_baseline_expanded_pairs": len(expanded_structural),
        "consistency_classified_pairs": len(classified),
        "high_moderate_confidence_pairs": len(high_mod),
        "primary_contrast_eligible_observations": len(pos_neg),
        "positive_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "POSITIVE"
        ),
        "negative_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "NEGATIVE"
        ),
        "mixed_label_provider_session_clusters": sum(
            1 for labels in cluster_labels.values() if {"POSITIVE", "NEGATIVE"} <= labels
        ),
        "provider_count": len({_normalize(row.get("provider")) for row in pos_neg}),
        "session_count": len({_normalize(row.get("session_id")) for row in pos_neg}),
        "cluster_count": len(
            {f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}" for row in pos_neg}
        ),
        "baseline_match_count_errors": baseline_match_count_errors,
    }


def _parse_source_row_key(source_row_key: str) -> Tuple[str, str, int]:
    parts = source_row_key.split("::")
    _require(len(parts) == 3, f"Invalid source_row_key format: {source_row_key}")
    sheet_name, run_id, row_number_raw = parts
    return sheet_name, run_id, int(row_number_raw)


def _select_authoritative_rows(
    inputs: Mapping[str, Any],
    manifest: Mapping[str, Any],
    component_authority: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    component_records = {
        _normalize(record.get("component_id")): record
        for record in component_authority.get("component_records", [])
    }
    manifest_entries = manifest.get("authoritative_component_entries", [])
    _require(len(manifest_entries) == 12, "Canonical manifest does not contain 12 authoritative components.")

    selected: Dict[str, Dict[str, Any]] = {}
    seen_components: Set[str] = set()
    for entry in manifest_entries:
        component_id = _normalize(entry.get("component_id"))
        sheet_name = str(entry.get("source_sheet") or "")
        sheet_name_norm = _normalize(sheet_name)
        source_row_key = _normalize(entry.get("source_row_key"))
        _require(component_id not in seen_components, f"Duplicate component in manifest: {component_id}")
        seen_components.add(component_id)

        record = component_records.get(component_id)
        _require(record is not None, f"Component authority record missing for {component_id}")
        _require(
            _normalize(record.get("authority_status")) == "EXACTLY_ONE_COMPLETE_AUTHORITATIVE_ROW",
            f"Component authority status invalid for {component_id}: {record}",
        )

        parsed_sheet, parsed_run_id, parsed_row_number = _parse_source_row_key(source_row_key)
        _require(_normalize(parsed_sheet) == sheet_name_norm, f"Manifest source sheet mismatch for {component_id}")
        _require(parsed_run_id == AUTHORITATIVE_RUN_ID, f"Manifest run ID mismatch for {component_id}")

        matches = [
            dict(row)
            for row in inputs[sheet_name].rows
            if _normalize(row.get("clean_contract_repair_run_id")) == AUTHORITATIVE_RUN_ID
            and int(row.get("__source_row_number__", 0) or 0) == parsed_row_number
        ]
        _require(len(matches) == 1, f"Expected exactly one authoritative match for {component_id}; found {len(matches)}")
        row = matches[0]
        payload = json.loads(_normalize(row.get("payload_json")) or "{}")
        _require(isinstance(payload, dict) and bool(payload), f"Authoritative payload incomplete for {component_id}")
        current_fp = _fingerprint_payload(payload)
        _require(
            current_fp == _normalize(entry.get("fingerprint")),
            f"Authoritative fingerprint mismatch for {component_id}",
        )
        selected[sheet_name] = {
            "component_id": component_id,
            "source_row_key": source_row_key,
            "row": row,
            "payload": payload,
            "fingerprint": current_fp,
        }

    _require(len(selected) == 12, f"Expected 12 selected authoritative rows, found {len(selected)}")
    return selected


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, Any]:
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
            "notes": "Phase 9A-6R14S canonical mechanism-test execution readiness audit outputs.",
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
    return {"updated": len(OUTPUT_LOGICAL_IDS) - appended, "appended": appended, "status": "ok"}


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    readiness_audit_run_id = _run_id(run_ts)

    _require(
        not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)),
        "Forbidden outcome-bearing sheet included in readiness audit inputs.",
    )

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget = _ensure_cell_budget(service, known_titles)
    _ensure_output_sheets(service, known_titles)

    canonical_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Authority"].rows,
        "lineage_repair_run_id",
    )
    component_authority = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Component_Authority"].rows,
        "lineage_repair_run_id",
    )
    historical_disposition = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Historical_Run_Disposition"].rows,
        "lineage_repair_run_id",
    )
    scientific_equivalence = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Scientific_Equivalence_Audit"].rows,
        "lineage_repair_run_id",
    )
    canonical_manifest = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest"].rows,
        "lineage_repair_run_id",
    )
    authority_stop_rules = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Authority_Stop_Rules"].rows,
        "lineage_repair_run_id",
    )
    lineage_governance = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Governance"].rows,
        "lineage_repair_run_id",
    )
    lineage_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Summary"].rows,
        "lineage_repair_run_id",
    )

    canonical_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Canonical_R1"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_governance = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Approval_Governance"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_load_order = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Load_Order_Approval"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_stop_rules = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Stop_Rule_Approval"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_science = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Science_Approval"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_counts = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Count_Approval"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_fingerprint = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Fingerprint_Approval"].rows,
        "approval_canonical_r1_run_id",
    )
    canonical_approval_blinding = _latest_payload(
        inputs["Refined_Mechanism_Test_Canonical_R1_Blinding_Approval"].rows,
        "approval_canonical_r1_run_id",
    )

    _require(
        _normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION,
        "Canonical authority version mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID,
        "Canonical authority run ID mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH",
        "Canonical authority selection method mismatch.",
    )
    _require(
        _normalize(canonical_authority.get("authority_status")) == "CANONICAL_AUTHORITY_COMPLETE",
        "Canonical authority is not complete.",
    )
    _require(
        lineage_summary.get("ready_for_clean_r1_approval_rerun") is True,
        "Lineage repair did not mark the workbook ready for canonical approval rerun.",
    )
    _require(
        canonical_approval_summary.get("ready_for_one_canonical_clean_r1_mechanism_test_execution") is True,
        "Canonical approval did not mark the workbook ready for clean R1 mechanism test execution.",
    )

    selected_rows = _select_authoritative_rows(inputs, canonical_manifest, component_authority)
    selected_payloads = {sheet_name: row["payload"] for sheet_name, row in selected_rows.items()}
    component_fingerprint_by_id = {
        details["component_id"]: details["fingerprint"] for details in selected_rows.values()
    }
    component_source_key_by_id = {
        details["component_id"]: details["source_row_key"] for details in selected_rows.values()
    }
    canonical_component_bundle_fingerprint = _fingerprint_payload(
        {
            "preregistration_version": AUTHORITATIVE_VERSION,
            "authoritative_run_id": AUTHORITATIVE_RUN_ID,
            "component_fingerprints": component_fingerprint_by_id,
        }
    )

    prereg_r1 = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1"]
    outcome_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    join_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"]
    success_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"]
    method_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"]
    stop_rules_r1 = selected_payloads["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"]
    design_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Design_Reconciliation"]
    blinding_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Blinding_Audit"]
    fingerprint_freeze_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze"]
    governance_r1 = selected_payloads["Refined_Mechanism_Test_Clean_R1_Governance"]
    summary_r1 = selected_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1_Summary"]

    parent_current = _sheet_latest_row_fingerprint_entries(
        inputs,
        PARENT_CLEAN_SHEETS,
        "clean_preregistration_run_id",
    )
    original_current = _sheet_full_row_fingerprint_entries(inputs, ORIGINAL_SHEETS)
    parent_clean_bundle_fingerprint = _fingerprint_payload({"sheet_fingerprints": parent_current})
    original_bundle_fingerprint = _fingerprint_payload({"sheet_fingerprints": original_current})

    derived_entry_map = {
        _normalize(entry.get("component_id")): entry
        for entry in canonical_manifest.get("derived_entries", [])
    }
    expected_derived_entries = [
        {"component_id": component_id, "fingerprint": derived_entry_map[component_id].get("fingerprint")}
        for component_id in [
            "authoritative_run_identity",
            "parent_clean_version",
            "original_version",
            "primary_design",
            "population_and_counts",
            "sample_gates",
            "mechanism_hierarchy",
            "uncertainty_rules",
        ]
    ]
    current_derived_entries = [
        {
            "component_id": "authoritative_run_identity",
            "fingerprint": _fingerprint_payload(
                {
                    "preregistration_version": AUTHORITATIVE_VERSION,
                    "authoritative_run_id": AUTHORITATIVE_RUN_ID,
                    "authority_selection_method": "EXACT_VERSION_AND_RUN_ID_MATCH",
                }
            ),
        },
        {"component_id": "parent_clean_version", "fingerprint": parent_clean_bundle_fingerprint},
        {"component_id": "original_version", "fingerprint": original_bundle_fingerprint},
        {
            "component_id": "primary_design",
            "fingerprint": _fingerprint_payload(
                {
                    "primary_mechanism": prereg_r1.get("primary_mechanism"),
                    "primary_structure": prereg_r1.get("primary_structure"),
                    "primary_exposure": prereg_r1.get("primary_exposure"),
                    "primary_comparison_groups": prereg_r1.get("primary_comparison_groups"),
                    "baseline_role": prereg_r1.get("baseline_role"),
                    "primary_estimand": prereg_r1.get("primary_estimand"),
                }
            ),
        },
        {"component_id": "population_and_counts", "fingerprint": _fingerprint_payload(prereg_r1.get("counts", {}))},
        {"component_id": "sample_gates", "fingerprint": _fingerprint_payload(prereg_r1.get("sample_gates", {}))},
        {
            "component_id": "mechanism_hierarchy",
            "fingerprint": _fingerprint_payload(
                {
                    "primary_mechanism": prereg_r1.get("primary_mechanism"),
                    "exploratory_mechanism": prereg_r1.get("exploratory_mechanism"),
                    "descriptive_only_mechanism": prereg_r1.get("descriptive_only_mechanism"),
                }
            ),
        },
        {"component_id": "uncertainty_rules", "fingerprint": _fingerprint_payload(prereg_r1.get("uncertainty_rules", {}))},
    ]
    derived_cmp = _compare_expected_to_current(expected_derived_entries, current_derived_entries)

    manifest_component_entries = canonical_manifest.get("authoritative_component_entries", [])
    manifest_component_ids = [_normalize(entry.get("component_id")) for entry in manifest_component_entries]
    duplicate_manifest_components = [
        component for component, count in Counter(manifest_component_ids).items() if count > 1
    ]
    current_component_entries = [
        {
            "component_id": entry["component_id"],
            "fingerprint": component_fingerprint_by_id[_normalize(entry["component_id"])],
        }
        for entry in manifest_component_entries
    ]
    manifest_component_cmp = _compare_expected_to_current(manifest_component_entries, current_component_entries)

    class_rows = _classification_rows(inputs)
    classification_versions = sorted({_normalize(row.get("mechanism_version")) for row in class_rows})
    classification_run_ids = sorted({_normalize(row.get("classification_run_id")) for row in class_rows})
    classification_scope_fingerprint = _fingerprint_sorted_rows(
        class_rows,
        ("classification_run_id", "mechanism_id", "source_row_key"),
    )

    structure_counts = _structure_counts(class_rows)
    count_pass = all(
        int(structure_counts.get(key, -1)) == expected
        for key, expected in EXPECTED_COUNTS.items()
        if key != "baseline_match_count_errors"
    ) and not structure_counts["baseline_match_count_errors"]

    gate_contract = prereg_r1.get("sample_gate_contract", {})
    gate_statuses = {
        "positive_gate": _normalize(gate_contract.get("minimum_positive_count", {}).get("status")) == "PASS",
        "negative_gate": _normalize(gate_contract.get("minimum_negative_count", {}).get("status")) == "PASS",
        "primary_contrast_gate": _normalize(gate_contract.get("minimum_primary_contrast_observations", {}).get("status")) == "PASS",
        "cluster_gate": _normalize(gate_contract.get("minimum_clusters", {}).get("status")) == "PASS",
        "provider_gate": _normalize(gate_contract.get("minimum_providers", {}).get("status")) == "PASS",
        "session_gate": _normalize(gate_contract.get("minimum_sessions", {}).get("status")) == "PASS",
    }
    gate_pass = all(gate_statuses.values())

    authority_checks_pass = (
        _normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION
        and _normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID
        and _normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH"
        and int(canonical_authority.get("required_components", 0) or 0) == 12
        and int(canonical_authority.get("components_with_exactly_one_authoritative_row", 0) or 0) == 12
        and not canonical_authority.get("missing_authoritative_components")
        and not canonical_authority.get("duplicate_authoritative_components")
        and not duplicate_manifest_components
        and manifest_component_cmp["match"]
    )

    historical_isolation_pass = (
        set(lineage_summary.get("run_ids_found", [])) == KNOWN_R1_RUN_IDS
        and int(lineage_summary.get("complete_non_authoritative_runs", 0) or 0) == 1
        and int(lineage_summary.get("partial_runs", 0) or 0) == 1
        and int(lineage_summary.get("superseded_rows", 0) or 0) == 19
        and int(lineage_summary.get("unresolved_rows", 0) or 0) == 0
        and int(canonical_manifest.get("partial_rows_included", 0) or 0) == 0
        and int(canonical_manifest.get("superseded_rows_included", 0) or 0) == 0
        and _normalize(scientific_equivalence.get("scientific_equivalence_status"))
        == "ALL_COMPLETE_NONAUTHORITATIVE_RUNS_SCIENTIFICALLY_IDENTICAL"
    )

    fingerprint_pass = (
        _normalize(canonical_manifest.get("preregistration_version")) == AUTHORITATIVE_VERSION
        and _normalize(canonical_manifest.get("authoritative_run_id")) == AUTHORITATIVE_RUN_ID
        and int(canonical_manifest.get("authoritative_components_fingerprinted", 0) or 0) == 12
        and not canonical_manifest.get("missing_fingerprints")
        and int(canonical_manifest.get("partial_rows_included", 0) or 0) == 0
        and int(canonical_manifest.get("superseded_rows_included", 0) or 0) == 0
        and _normalize(canonical_manifest.get("manifest_status")) == "COMPLETE_AUTHORITATIVE_CLOSURE"
        and _normalize(canonical_manifest.get("stable_serialization_rule", {}).get("algorithm")) == "sha256"
        and canonical_manifest.get("stable_serialization_rule", {}).get("physical_row_order_affects_fingerprint") is False
        and manifest_component_cmp["match"]
        and derived_cmp["match"]
        and canonical_manifest.get("modification_allowed") is False
    )

    timestamp_contract = outcome_r1.get("outcome_timestamp_requirement", {})
    version_handling = outcome_r1.get("outcome_version_mismatch_handling", {})
    window_handling = outcome_r1.get("evaluation_window_mismatch_handling", {})
    outcome_contract_pass = (
        timestamp_contract.get("canonical_outcome_version_required") is True
        and timestamp_contract.get("approved_evaluation_window_required") is True
        and timestamp_contract.get("outcome_timestamp_at_or_after_evaluation_window_end") is True
        and timestamp_contract.get("no_information_outside_approved_evaluation_window") is True
        and timestamp_contract.get("source_availability_timestamp_compatible_with_canonical_repair_process") is True
        and timestamp_contract.get("deterministically_linked_to_forecast_observation") is True
        and timestamp_contract.get("reject_if_timestamp_provenance_missing_or_contradictory") is True
        and _normalize(timestamp_contract.get("failure_status")) == "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED"
        and _normalize(version_handling.get("result")) == "NOT_ELIGIBLE"
        and _normalize(version_handling.get("systemic_result")) == "HARD_BLOCK"
        and _normalize(window_handling.get("result")) == "NOT_ELIGIBLE"
        and _normalize(window_handling.get("systemic_result")) == "HARD_BLOCK"
    )

    join_contract_pass = (
        _normalize(join_r1.get("approved_future_join_path"))
        == "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id"
        and join_r1.get("physical_row_number_join_prohibited") is True
        and join_r1.get("fuzzy_text_join_prohibited") is True
        and join_r1.get("manual_matching_prohibited") is True
        and join_r1.get("nearest_date_matching_prohibited") is True
        and join_r1.get("provider_name_only_join_prohibited") is True
        and join_r1.get("session_only_join_prohibited") is True
        and join_r1.get("pack_level_only_join_prohibited") is True
        and join_r1.get("one_classification_observation_to_one_canonical_outcome_required") is True
        and _normalize(join_r1.get("duplicate_join_result")) == "DUPLICATE_JOIN_BLOCKED"
        and _normalize(join_r1.get("ambiguous_join_result")) == "AMBIGUOUS_JOIN_BLOCKED"
        and _normalize(join_r1.get("missing_join_result")) == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN"
        and join_r1.get("baseline_and_expanded_rows_must_map_to_correct_forecast_identity") is True
        and join_r1.get("version_match_required") is True
        and join_r1.get("evaluation_window_match_required") is True
        and join_r1.get("timestamp_requirement_pass_required") is True
    )

    explicit_case_map = success_r1.get("explicit_case_map", {})
    rule_precedence = success_r1.get("rule_precedence", [])
    success_pass = (
        set(success_r1.get("allowed_output_statuses", []))
        == {"SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"}
        and _normalize(explicit_case_map.get("UP_forecast_UP_outcome")) == "SUCCESS"
        and _normalize(explicit_case_map.get("UP_forecast_DOWN_outcome")) == "FAILURE"
        and _normalize(explicit_case_map.get("DOWN_forecast_DOWN_outcome")) == "SUCCESS"
        and _normalize(explicit_case_map.get("DOWN_forecast_UP_outcome")) == "FAILURE"
        and _normalize(explicit_case_map.get("forecast_FLAT_any_realized_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("realized_FLAT_any_forecast_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("forecast_NO_CLEAR_DIRECTION")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("no_signal_forecast")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("missing_forecast_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("missing_realized_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("invalid_forecast_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("invalid_realized_direction")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("duplicate_outcome_join")) == "AMBIGUOUS_JOIN_BLOCKED"
        and _normalize(explicit_case_map.get("ambiguous_outcome_join")) == "AMBIGUOUS_JOIN_BLOCKED"
        and _normalize(explicit_case_map.get("outcome_version_mismatch")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("evaluation_window_mismatch")) == "NOT_ELIGIBLE"
        and _normalize(explicit_case_map.get("timestamp_requirement_failure")) == "NOT_ELIGIBLE"
        and len(rule_precedence) >= 8
    )

    method_pass = (
        _normalize(method_r1.get("primary_method_id")) == PRIMARY_METHOD_ID
        and int(method_r1.get("bootstrap_replications", 0) or 0) == 10000
        and int(method_r1.get("bootstrap_random_seed", 0) or 0) == 9130613
        and _normalize(method_r1.get("resampling_unit")) == "shared_session_outcome_family"
        and _normalize(method_r1.get("confidence_interval_method")) == "two_sided_percentile_bootstrap_95pct_interval"
        and float(method_r1.get("confidence_interval_quantiles", {}).get("lower", -1)) == 0.025
        and float(method_r1.get("confidence_interval_quantiles", {}).get("upper", -1)) == 0.975
        and method_r1.get("automatic_method_substitution_allowed") is False
        and _normalize(method_r1.get("primary_interpretation")) == PRIMARY_INTERPRETATION
        and _normalize(method_r1.get("degenerate_bootstrap_handling", {}).get("trigger_status")) == "DEGENERATE_BOOTSTRAP_DISTRIBUTION"
        and method_r1.get("descriptive_fallback", {}).get("allowed") is True
        and method_r1.get("descriptive_fallback", {}).get("inferential_primary_result_allowed") is False
    )

    execution_stop_rules = stop_rules_r1.get("stop_rules", [])
    execution_stop_rule_names = {_normalize(rule.get("stop_rule_name")) for rule in execution_stop_rules}
    authority_stop_rules_list = authority_stop_rules.get("stop_rules", [])
    authority_stop_rule_names = {_normalize(rule.get("rule_name")) for rule in authority_stop_rules_list}

    execution_stop_rules_pass = (
        stop_rules_r1.get("automatic_retry_allowed") is False
        and stop_rules_r1.get("fail_closed") is True
        and stop_rules_r1.get("hard_stop_summary_allowed") is False
        and len(execution_stop_rules) == 29
        and execution_stop_rule_names == EXECUTION_STOP_RULE_NAMES
        and all(
            _normalize(rule.get("runtime_assertion"))
            and bool(rule.get("diagnostic_log_fields"))
            and rule.get("automatic_retry_allowed") is False
            for rule in execution_stop_rules
        )
    )
    authority_stop_rules_pass = (
        int(authority_stop_rules.get("total_stop_rules", 0) or 0) == 15
        and authority_stop_rule_names == AUTHORITY_STOP_RULE_NAMES
        and all(
            _normalize(rule.get("runtime_assertion"))
            and _normalize(rule.get("blocked_status")) == "BLOCKED"
            and rule.get("successful_execution_allowed") is False
            and rule.get("automatic_retry_allowed") is False
            and bool(rule.get("diagnostic_logging"))
            for rule in authority_stop_rules_list
        )
    )
    additive_stop_rules_pass = execution_stop_rule_names.isdisjoint(AUTHORITY_STOP_RULE_NAMES) and authority_stop_rules_pass

    parent_bundle_match = derived_cmp["match"] and (
        derived_entry_map["parent_clean_version"].get("fingerprint") == parent_clean_bundle_fingerprint
    )
    original_bundle_match = derived_cmp["match"] and (
        derived_entry_map["original_version"].get("fingerprint") == original_bundle_fingerprint
    )

    science_pass = (
        _normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM
        and _normalize(prereg_r1.get("exploratory_mechanism")) == EXPLORATORY_MECHANISM
        and _normalize(prereg_r1.get("descriptive_only_mechanism")) == DESCRIPTIVE_ONLY_MECHANISM
        and _normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE
        and _normalize(prereg_r1.get("primary_exposure")) == PRIMARY_EXPOSURE
        and _normalize(prereg_r1.get("primary_comparison_groups")) == PRIMARY_COMPARISON_GROUPS
        and _normalize(prereg_r1.get("baseline_role")) == BASELINE_ROLE
        and _normalize(prereg_r1.get("primary_estimand")) == PRIMARY_ESTIMAND
        and lineage_summary.get("hypothesis_changed") is False
        and lineage_summary.get("primary_structure_changed") is False
        and lineage_summary.get("primary_population_changed") is False
        and lineage_summary.get("hierarchy_changed") is False
        and lineage_summary.get("sample_gates_changed") is False
        and lineage_summary.get("uncertainty_rules_changed") is False
        and lineage_summary.get("outcome_contract_changed") is False
        and lineage_summary.get("join_rules_changed") is False
        and lineage_summary.get("success_derivation_changed") is False
        and lineage_summary.get("statistical_method_changed") is False
        and lineage_summary.get("stop_rules_changed") is False
        and parent_bundle_match
        and original_bundle_match
    )

    blinding_pass = (
        int(lineage_governance.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(lineage_governance.get("outcome_sheets_loaded", 0) or 0) == 0
        and int(lineage_governance.get("outcome_rows_loaded", 0) or 0) == 0
        and int(lineage_governance.get("realized_values_accessed", 0) or 0) == 0
        and int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0) == 0
        and int(lineage_governance.get("mechanism_tests_performed", 0) or 0) == 0
        and int(governance_r1.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(governance_r1.get("outcome_rows_loaded", 0) or 0) == 0
        and int(canonical_approval_governance.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(canonical_approval_governance.get("outcome_rows_loaded", 0) or 0) == 0
        and int(canonical_approval_blinding.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(canonical_approval_blinding.get("outcome_rows_loaded", 0) or 0) == 0
    )

    prereg_version_verified = _normalize(
        prereg_r1.get("repaired_preregistration_version") or prereg_r1.get("test_preregistration_version")
    ) == AUTHORITATIVE_VERSION

    environment_freeze_pass = all(
        [
            fingerprint_pass,
            outcome_contract_pass,
            join_contract_pass,
            success_pass,
            method_pass,
            execution_stop_rules_pass,
            authority_stop_rules_pass,
            prereg_version_verified,
        ]
    )

    load_sequence = [
        "Load canonical authority record.",
        "Verify version 1.0-clean-r1.",
        "Verify run ID 9A-6R13R1_20260711T020141Z.",
        "Load canonical component manifest.",
        "Verify exactly 12 authoritative components.",
        "Verify one authoritative row per component.",
        "Verify all authoritative fingerprints.",
        "Reject all superseded and partial rows.",
        "Verify classification fingerprints.",
        "Verify scientific counts and sample gates.",
        "Verify all stop rules.",
        "Only then permit outcome workbook access.",
    ]
    execution_order_pass = (
        canonical_authority.get("no_outcome_workbook_open_before_authority_pass") is True
        and authority_checks_pass
        and historical_isolation_pass
        and fingerprint_pass
        and count_pass
        and gate_pass
        and execution_stop_rules_pass
        and authority_stop_rules_pass
        and join_contract_pass
        and _normalize(canonical_approval_load_order.get("load_order_status")) == "PRE_OUTCOME_LOAD_ORDER_APPROVED"
    )

    combined_stop_rule_names = execution_stop_rule_names | authority_stop_rule_names
    stop_coverage_map = [
        {
            "condition": "fingerprint_mismatch",
            "governing_rules": [
                "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
                "AUTHORITATIVE_FINGERPRINT_MISMATCH",
                "CLASSIFICATION_FINGERPRINT_MISMATCH",
            ],
        },
        {
            "condition": "lineage_mismatch",
            "governing_rules": [
                "AUTHORITATIVE_COMPONENT_MISSING",
                "AUTHORITATIVE_COMPONENT_INCOMPLETE",
                "MIXED_RUN_CONTRACT_ASSEMBLY_ATTEMPT",
                "NONAUTHORITATIVE_RUN_USED_FOR_EXECUTION",
            ],
        },
        {
            "condition": "join_ambiguity",
            "governing_rules": ["AMBIGUOUS_JOIN"],
        },
        {
            "condition": "duplicate_joins",
            "governing_rules": ["DUPLICATE_JOIN"],
        },
        {
            "condition": "eligibility_mismatch",
            "governing_rules": ["UNEXPECTED_ELIGIBILITY_DIFFERENCE"],
        },
        {
            "condition": "outcome_version_mismatch",
            "governing_rules": ["OUTCOME_VERSION_MISMATCH"],
        },
        {
            "condition": "evaluation_window_mismatch",
            "governing_rules": ["EVALUATION_WINDOW_MISMATCH"],
        },
        {
            "condition": "bootstrap_configuration_mismatch",
            "governing_rules": ["CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH"],
        },
        {
            "condition": "statistical_method_mismatch",
            "governing_rules": [
                "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
                "UNAPPROVED_STATISTICAL_FALLBACK",
            ],
        },
        {
            "condition": "random_seed_mismatch",
            "governing_rules": ["CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH"],
        },
        {
            "condition": "unauthorized_fallback",
            "governing_rules": ["UNAPPROVED_STATISTICAL_FALLBACK"],
        },
        {
            "condition": "unapproved_execution_environment_drift",
            "governing_rules": [
                "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
                "AUTHORITATIVE_FINGERPRINT_MISMATCH",
                "CLASSIFICATION_FINGERPRINT_MISMATCH",
            ],
        },
    ]
    stop_rule_coverage = []
    for item in stop_coverage_map:
        rule_names = item["governing_rules"]
        present = [rule_name for rule_name in rule_names if rule_name in combined_stop_rule_names]
        stop_rule_coverage.append(
            {
                "condition": item["condition"],
                "governing_rules": rule_names,
                "rules_present": present,
                "coverage_complete": len(present) == len(rule_names),
                "halts_before_outcome_access": True,
            }
        )
    stop_rule_pass = (
        execution_stop_rules_pass
        and authority_stop_rules_pass
        and additive_stop_rules_pass
        and all(item["coverage_complete"] for item in stop_rule_coverage)
    )

    deterministic_input_identity = {
        "preregistration_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "canonical_component_bundle_fingerprint": canonical_component_bundle_fingerprint,
        "classification_scope_fingerprint": classification_scope_fingerprint,
        "method_fingerprint": component_fingerprint_by_id["statistical_method"],
        "join_fingerprint": component_fingerprint_by_id["join_rules"],
        "success_derivation_fingerprint": component_fingerprint_by_id["success_derivation"],
        "stop_rule_fingerprint": component_fingerprint_by_id["stop_rules"],
        "outcome_contract_fingerprint": component_fingerprint_by_id["outcome_definition"],
    }
    deterministic_input_identity_fingerprint = _fingerprint_payload(deterministic_input_identity)
    deterministic_audit_logging = all(
        bool(rule.get("diagnostic_log_fields")) for rule in execution_stop_rules
    ) and all(bool(rule.get("diagnostic_logging")) for rule in authority_stop_rules_list)
    determinism_pass = (
        authority_checks_pass
        and fingerprint_pass
        and execution_order_pass
        and _normalize(canonical_manifest.get("stable_serialization_rule", {}).get("algorithm")) == "sha256"
        and canonical_manifest.get("stable_serialization_rule", {}).get("physical_row_order_affects_fingerprint") is False
        and deterministic_audit_logging
    )

    reproducibility_artifacts = [
        {
            "artifact": "canonical_preregistration",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "fingerprint": component_fingerprint_by_id["preregistration"],
        },
        {
            "artifact": "canonical_authority_manifest",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
            "fingerprint": canonical_component_bundle_fingerprint,
        },
        {
            "artifact": "canonical_classification_scope",
            "version": CLASSIFICATION_VERSION,
            "source_sheet": "Refined_Mechanism_v11_Classifications",
            "fingerprint": classification_scope_fingerprint,
        },
        {
            "artifact": "outcome_contract",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
            "fingerprint": component_fingerprint_by_id["outcome_definition"],
        },
        {
            "artifact": "join_contract",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
            "fingerprint": component_fingerprint_by_id["join_rules"],
        },
        {
            "artifact": "success_derivation",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "fingerprint": component_fingerprint_by_id["success_derivation"],
        },
        {
            "artifact": "statistical_method",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1",
            "fingerprint": component_fingerprint_by_id["statistical_method"],
        },
        {
            "artifact": "execution_stop_rules",
            "version": AUTHORITATIVE_VERSION,
            "source_sheet": "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1",
            "fingerprint": component_fingerprint_by_id["stop_rules"],
        },
    ]
    reproducibility_pass = (
        authority_checks_pass
        and historical_isolation_pass
        and fingerprint_pass
        and science_pass
        and count_pass
        and gate_pass
        and environment_freeze_pass
        and determinism_pass
        and len(reproducibility_artifacts) == 8
    )

    governance_pass = (
        int(lineage_governance.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(lineage_governance.get("outcome_sheets_loaded", 0) or 0) == 0
        and int(lineage_governance.get("outcome_rows_loaded", 0) or 0) == 0
        and int(lineage_governance.get("realized_values_accessed", 0) or 0) == 0
        and int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0) == 0
        and int(lineage_governance.get("mechanism_tests_performed", 0) or 0) == 0
        and int(lineage_governance.get("classifications_modified", 0) or 0) == 0
        and int(lineage_governance.get("parent_clean_sheets_modified", 0) or 0) == 0
        and int(lineage_governance.get("original_sheets_modified", 0) or 0) == 0
        and int(lineage_governance.get("production_writes", 0) or 0) == 0
        and int(lineage_governance.get("production_behavior_changes", 0) or 0) == 0
        and int(canonical_approval_governance.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(canonical_approval_governance.get("mechanism_tests_performed", 0) or 0) == 0
        and int(canonical_approval_governance.get("production_writes", 0) or 0) == 0
        and int(governance_r1.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(governance_r1.get("mechanism_tests_performed", 0) or 0) == 0
    )

    canonical_authority_status = "CANONICAL_AUTHORITY_APPROVED" if authority_checks_pass and historical_isolation_pass and fingerprint_pass else "CANONICAL_AUTHORITY_BLOCKED"
    environment_freeze_status = "EXECUTION_ENVIRONMENT_FROZEN" if environment_freeze_pass else "EXECUTION_ENVIRONMENT_DRIFT_OR_INCOMPLETE"
    scientific_freeze_status = "SCIENTIFIC_FREEZE_CONFIRMED" if science_pass else "SCIENTIFIC_FREEZE_NOT_CONFIRMED"
    blinding_status = "BLINDING_INTACT_PRE_EXECUTION" if blinding_pass else "BLINDING_BREACH_OR_UNVERIFIABLE"
    determinism_status = "DETERMINISTIC_EXECUTION_READY" if determinism_pass else "DETERMINISM_NOT_CONFIRMED"
    stop_rule_status = "FAIL_CLOSED_STOP_RULES_APPROVED" if stop_rule_pass else "STOP_RULE_COVERAGE_INCOMPLETE"
    reproducibility_status = "REPRODUCIBILITY_CONFIRMED" if reproducibility_pass else "REPRODUCIBILITY_NOT_CONFIRMED"
    execution_ordering_status = "PRE_OUTCOME_EXECUTION_ORDERING_APPROVED" if execution_order_pass else "EXECUTION_ORDERING_NOT_APPROVED"

    all_checks_pass = all(
        [
            authority_checks_pass,
            historical_isolation_pass,
            fingerprint_pass,
            environment_freeze_pass,
            science_pass,
            blinding_pass,
            execution_order_pass,
            determinism_pass,
            stop_rule_pass,
            reproducibility_pass,
            governance_pass,
            count_pass,
            gate_pass,
        ]
    )

    if all_checks_pass:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_READINESS_READY_WITH_WARNINGS"
        recommended_next_step = "PROCEED_TO_PHASE9A6R15_CLEAN_R1_MECHANISM_TEST_EXECUTION"
    else:
        build_status = "FAIL"
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_READINESS_NEEDS_REPAIR"
        if not authority_checks_pass or not historical_isolation_pass or not fingerprint_pass:
            recommended_next_step = "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR"
        elif not environment_freeze_pass or not stop_rule_pass:
            recommended_next_step = "RUN_PHASE9A6R13R1_CONTRACT_REPAIR"
        else:
            recommended_next_step = "HOLD_MECHANISM_TESTING_PENDING_GOVERNANCE_REVIEW"

    canonical_authority_payload = {
        "canonical_preregistration_version": AUTHORITATIVE_VERSION,
        "canonical_authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": classification_versions,
        "classification_run_id": classification_run_ids,
        "classification_row_count": len(class_rows),
        "fingerprint_manifest_status": canonical_manifest.get("manifest_status"),
        "lineage_closure_status": lineage_summary.get("scientific_equivalence_status"),
        "canonical_authority_status": canonical_authority_status,
        "required_authoritative_components": int(canonical_authority.get("required_components", 0) or 0),
        "components_with_exactly_one_authoritative_row": int(
            canonical_authority.get("components_with_exactly_one_authoritative_row", 0) or 0
        ),
        "missing_authoritative_components": list(canonical_authority.get("missing_authoritative_components", [])),
        "duplicate_authoritative_components": list(canonical_authority.get("duplicate_authoritative_components", [])),
        "run_ids_found": sorted(lineage_summary.get("run_ids_found", [])),
        "unresolved_historical_rows": int(lineage_summary.get("unresolved_rows", 0) or 0),
        "canonical_component_bundle_fingerprint": canonical_component_bundle_fingerprint,
        "classification_scope_fingerprint": classification_scope_fingerprint,
        "scientific_authority_chain": [
            {"component": "original_preregistration", "version": ORIGINAL_VERSION, "preserved": original_bundle_match},
            {"component": "parent_clean_preregistration", "version": PARENT_CLEAN_VERSION, "preserved": parent_bundle_match},
            {"component": "clean_r1_authoritative_version", "version": AUTHORITATIVE_VERSION, "authoritative_run_id": AUTHORITATIVE_RUN_ID},
            {"component": "canonical_authority_manifest", "status": canonical_manifest.get("manifest_status")},
            {"component": "classification_run", "version": CLASSIFICATION_VERSION, "run_id": CLASSIFICATION_RUN_ID},
            {"component": "canonical_execution_approval", "status": canonical_approval_summary.get("final_interpretation")},
        ],
        "scientific_authority_chain_complete": all(
            [
                authority_checks_pass,
                historical_isolation_pass,
                fingerprint_pass,
                parent_bundle_match,
                original_bundle_match,
                classification_versions == [CLASSIFICATION_VERSION],
                classification_run_ids == [CLASSIFICATION_RUN_ID],
                len(class_rows) == 360,
            ]
        ),
    }

    environment_freeze_payload = {
        "environment_freeze_status": environment_freeze_status,
        "scientific_freeze_status": scientific_freeze_status,
        "preregistration_version_verified": prereg_version_verified,
        "statistical_method_version": AUTHORITATIVE_VERSION,
        "statistical_method_component": {
            "source_sheet": "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1",
            "source_row_key": component_source_key_by_id["statistical_method"],
            "fingerprint": component_fingerprint_by_id["statistical_method"],
            "primary_method_id": method_r1.get("primary_method_id"),
            "bootstrap_replications": int(method_r1.get("bootstrap_replications", 0) or 0),
            "bootstrap_random_seed": int(method_r1.get("bootstrap_random_seed", 0) or 0),
            "resampling_unit": method_r1.get("resampling_unit"),
            "confidence_interval_method": method_r1.get("confidence_interval_method"),
            "confidence_interval_quantiles": method_r1.get("confidence_interval_quantiles"),
        },
        "join_contract_version": AUTHORITATIVE_VERSION,
        "join_contract_component": {
            "source_sheet": "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1",
            "source_row_key": component_source_key_by_id["join_rules"],
            "fingerprint": component_fingerprint_by_id["join_rules"],
            "approved_future_join_path": join_r1.get("approved_future_join_path"),
            "stable_key_components": join_r1.get("stable_key_components"),
        },
        "success_derivation_version": AUTHORITATIVE_VERSION,
        "success_derivation_component": {
            "source_sheet": "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1",
            "source_row_key": component_source_key_by_id["success_derivation"],
            "fingerprint": component_fingerprint_by_id["success_derivation"],
            "allowed_output_statuses": success_r1.get("allowed_output_statuses"),
        },
        "stop_rule_version": AUTHORITATIVE_VERSION,
        "stop_rule_component": {
            "source_sheet": "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1",
            "source_row_key": component_source_key_by_id["stop_rules"],
            "fingerprint": component_fingerprint_by_id["stop_rules"],
            "execution_stop_rule_count": len(execution_stop_rules),
            "authority_stop_rule_count": len(authority_stop_rules_list),
        },
        "outcome_schema_contract_version": AUTHORITATIVE_VERSION,
        "outcome_schema_contract_component": {
            "source_sheet": "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1",
            "source_row_key": component_source_key_by_id["outcome_definition"],
            "fingerprint": component_fingerprint_by_id["outcome_definition"],
            "canonical_outcome_source_sheet": outcome_r1.get("canonical_outcome_source_sheet"),
            "canonical_outcome_component_field": outcome_r1.get("canonical_outcome_component_field"),
            "repaired_canonical_outcome_version": outcome_r1.get("repaired_canonical_outcome_version"),
            "evaluation_window_version": outcome_r1.get("evaluation_window_version"),
        },
        "scientific_freeze_checks": {
            "hypotheses_preserved": parent_bundle_match and lineage_summary.get("hypothesis_changed") is False,
            "hierarchy_preserved": lineage_summary.get("hierarchy_changed") is False,
            "exposure_definition_preserved": _normalize(prereg_r1.get("primary_exposure")) == PRIMARY_EXPOSURE,
            "estimand_preserved": _normalize(prereg_r1.get("primary_estimand")) == PRIMARY_ESTIMAND,
            "comparison_groups_preserved": _normalize(prereg_r1.get("primary_comparison_groups")) == PRIMARY_COMPARISON_GROUPS,
            "sample_gates_preserved": lineage_summary.get("sample_gates_changed") is False,
            "confidence_rules_preserved_via_parent_bundle": parent_bundle_match,
            "unknown_handling_preserved_via_parent_bundle": parent_bundle_match,
            "exclusion_rules_preserved_via_parent_bundle": parent_bundle_match,
            "statistical_method_preserved": lineage_summary.get("statistical_method_changed") is False,
            "reporting_plan_preserved_via_parent_bundle": parent_bundle_match,
        },
    }

    execution_order_payload = {
        "execution_ordering_status": execution_ordering_status,
        "approved_load_sequence": load_sequence,
        "authority_must_pass_before_outcome_access": authority_checks_pass,
        "fingerprint_must_pass_before_outcome_access": fingerprint_pass,
        "lineage_must_pass_before_outcome_access": historical_isolation_pass,
        "sample_gates_must_pass_before_outcome_access": gate_pass,
        "stop_rule_validation_must_pass_before_outcome_access": stop_rule_pass,
        "join_contract_validation_must_pass_before_outcome_access": join_contract_pass,
        "outcome_access_permitted_only_after_step": 12,
        "canonical_authority_future_algorithm": canonical_authority.get("future_test_builder_load_algorithm"),
        "prior_load_order_status": canonical_approval_load_order.get("load_order_status"),
    }

    stop_rule_payload = {
        "stop_rule_status": stop_rule_status,
        "execution_stop_rule_count": len(execution_stop_rules),
        "authority_stop_rule_count": len(authority_stop_rules_list),
        "execution_stop_rules_fail_closed": stop_rules_r1.get("fail_closed") is True,
        "execution_hard_stop_summary_allowed": stop_rules_r1.get("hard_stop_summary_allowed"),
        "execution_automatic_retry_allowed": stop_rules_r1.get("automatic_retry_allowed"),
        "authority_stop_rules_complete": authority_stop_rules_pass,
        "authority_stop_rules_additive": additive_stop_rules_pass,
        "pre_outcome_stop_coverage": stop_rule_coverage,
        "bootstrap_configuration": {
            "frozen_replications": int(method_r1.get("bootstrap_replications", 0) or 0),
            "frozen_random_seed": int(method_r1.get("bootstrap_random_seed", 0) or 0),
            "frozen_resampling_unit": method_r1.get("resampling_unit"),
            "drift_detection_control": "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
        },
        "environment_drift_detection": {
            "statistical_method_mismatch_rule": "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
            "random_seed_mismatch_rule": "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
            "unauthorized_fallback_rule": "UNAPPROVED_STATISTICAL_FALLBACK",
        },
    }

    determinism_payload = {
        "determinism_status": determinism_status,
        "deterministic_authority_selection": authority_checks_pass,
        "deterministic_lineage_resolution": historical_isolation_pass,
        "deterministic_fingerprints": fingerprint_pass,
        "deterministic_execution_specification": environment_freeze_pass,
        "deterministic_rerun_input_identity": deterministic_input_identity,
        "deterministic_rerun_input_identity_fingerprint": deterministic_input_identity_fingerprint,
        "deterministic_output_versioning": True,
        "deterministic_audit_logging": deterministic_audit_logging,
        "stable_serialization_rule": canonical_manifest.get("stable_serialization_rule"),
        "classification_scope_fingerprint": classification_scope_fingerprint,
        "canonical_component_bundle_fingerprint": canonical_component_bundle_fingerprint,
        "planned_output_version_basis": {
            "preregistration_version": AUTHORITATIVE_VERSION,
            "authoritative_run_id": AUTHORITATIVE_RUN_ID,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "input_identity_fingerprint": deterministic_input_identity_fingerprint,
        },
    }

    reproducibility_payload = {
        "reproducibility_status": reproducibility_status,
        "another_researcher_can_reproduce_execution": reproducibility_pass,
        "required_artifacts": reproducibility_artifacts,
        "reproduction_inputs_complete": reproducibility_pass,
        "frozen_inputs_only_required": True,
        "independent_reproduction_contract": {
            "requires_frozen_preregistration": True,
            "requires_canonical_classification": True,
            "requires_canonical_authority": True,
            "requires_frozen_contracts": True,
            "requires_frozen_fingerprints": True,
            "requires_deterministic_execution_specification": True,
        },
    }

    blinding_payload = {
        "outcome_workbooks_opened": int(lineage_governance.get("outcome_workbooks_opened", 0) or 0),
        "outcome_sheets_loaded": int(lineage_governance.get("outcome_sheets_loaded", 0) or 0),
        "outcome_rows_loaded": int(lineage_governance.get("outcome_rows_loaded", 0) or 0),
        "realized_values_accessed": int(lineage_governance.get("realized_values_accessed", 0) or 0),
        "accuracy_metrics_calculated": int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0),
        "provider_rankings_produced": 0,
        "source_blinding_checks": {
            "lineage_governance_zero": blinding_pass,
            "r1_governance_zero": int(governance_r1.get("outcome_rows_loaded", 0) or 0) == 0,
            "canonical_approval_blinding_zero": int(canonical_approval_blinding.get("outcome_rows_loaded", 0) or 0) == 0,
        },
        "blinding_status": blinding_status,
    }

    governance_payload = {
        "outcome_workbooks_opened": int(lineage_governance.get("outcome_workbooks_opened", 0) or 0),
        "outcome_sheets_loaded": int(lineage_governance.get("outcome_sheets_loaded", 0) or 0),
        "outcome_rows_loaded": int(lineage_governance.get("outcome_rows_loaded", 0) or 0),
        "realized_values_accessed": int(lineage_governance.get("realized_values_accessed", 0) or 0),
        "accuracy_metrics_calculated": int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0),
        "mechanism_tests_performed": int(lineage_governance.get("mechanism_tests_performed", 0) or 0),
        "preregistration_sheets_modified": 0,
        "lineage_authority_sheets_modified": 0,
        "classifications_modified": int(lineage_governance.get("classifications_modified", 0) or 0),
        "parent_clean_sheets_modified": int(lineage_governance.get("parent_clean_sheets_modified", 0) or 0),
        "original_sheets_modified": int(lineage_governance.get("original_sheets_modified", 0) or 0),
        "production_writes": int(lineage_governance.get("production_writes", 0) or 0),
        "production_behavior_changes": int(lineage_governance.get("production_behavior_changes", 0) or 0),
        "governance_pass": governance_pass,
    }

    overall_payload = {
        "readiness_audit_version": READINESS_AUDIT_VERSION,
        "canonical_preregistration_version": AUTHORITATIVE_VERSION,
        "canonical_authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "canonical_authority_status": canonical_authority_status,
        "environment_freeze_status": environment_freeze_status,
        "scientific_freeze_status": scientific_freeze_status,
        "outcome_blinding_status": blinding_status,
        "determinism_status": determinism_status,
        "stop_rule_status": stop_rule_status,
        "reproducibility_status": reproducibility_status,
        "execution_ordering_status": execution_ordering_status,
        "ready_for_clean_r1_mechanism_test_execution": all_checks_pass,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
    }

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "canonical_authority_status": canonical_authority_status,
        "environment_freeze_status": environment_freeze_status,
        "scientific_freeze_status": scientific_freeze_status,
        "outcome_blinding_status": blinding_status,
        "determinism_status": determinism_status,
        "stop_rule_status": stop_rule_status,
        "reproducibility_status": reproducibility_status,
        "execution_ordering_status": execution_ordering_status,
        "governance_counters": governance_payload,
        "ready_for_clean_r1_mechanism_test_execution": all_checks_pass,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
        "canonical_preregistration_version": AUTHORITATIVE_VERSION,
        "canonical_authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "classification_row_count": len(class_rows),
        "manifest_status": canonical_manifest.get("manifest_status"),
        "scientific_authority_chain_complete": canonical_authority_payload["scientific_authority_chain_complete"],
        "bootstrap_replications": int(method_r1.get("bootstrap_replications", 0) or 0),
        "bootstrap_random_seed": int(method_r1.get("bootstrap_random_seed", 0) or 0),
        "resampling_unit": method_r1.get("resampling_unit"),
        "execution_stop_rule_count": len(execution_stop_rules),
        "authority_stop_rule_count": len(authority_stop_rules_list),
    }

    payloads = {
        "Refined_Mechanism_Test_Execution_Readiness": overall_payload,
        "Refined_Mechanism_Test_Canonical_Authority_Audit": canonical_authority_payload,
        "Refined_Mechanism_Test_Environment_Freeze": environment_freeze_payload,
        "Refined_Mechanism_Test_Execution_Order_Audit": execution_order_payload,
        "Refined_Mechanism_Test_Stop_Rule_Verification": stop_rule_payload,
        "Refined_Mechanism_Test_Determinism_Verification": determinism_payload,
        "Refined_Mechanism_Test_Reproducibility_Audit": reproducibility_payload,
        "Refined_Mechanism_Test_Blinding_Verification": blinding_payload,
        "Refined_Mechanism_Test_Readiness_Governance": governance_payload,
        "Refined_Mechanism_Test_Readiness_Summary": summary_payload,
    }

    existing_output_rows = {
        sheet_name: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
        for sheet_name in OUTPUT_SHEETS
    }
    write_updates = []
    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        next_row_number = len(existing_output_rows[sheet_name]) + 2
        row_values = [
            generated_ts,
            SCHEMA_VERSION,
            readiness_audit_run_id,
            json.dumps(payloads[sheet_name], ensure_ascii=True, sort_keys=True),
        ]
        write_updates.append(
            {
                "range": f"'{sheet_name}'!A{next_row_number}:{_column_letter(len(COMMON_HEADERS))}{next_row_number}",
                "values": [row_values],
            }
        )
        rows_written[sheet_name] = 1

    if write_updates:
        batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, write_updates)

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "readiness_audit_run_id": readiness_audit_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": summary_payload,
        "registry_writes": registry_writes,
        "budget": budget,
    }


def main() -> None:
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
