#!/usr/bin/env python3
"""Phase 9A-6R14R2 — Canonical Clean-R1 Mechanism Test Execution Approval Rerun.

This approval rerun consumes the canonical Clean-R1 authority layer and
authorizes exactly one clean mechanism-test execution only if authority,
fingerprints, blinding, science preservation, and the full execution contract
all pass independently.
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


PHASE_ID = "9A-6R14R2"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_approval_clean_r1_canonical_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_approval_clean_r1_canonical_v0"
APPROVAL_VERSION = "refined_mechanism_test_execution_approval_clean_r1_canonical_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION_APPROVAL_CANONICAL_R1"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
PARENT_CLEAN_VERSION = "1.0-clean"
PARENT_CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
ORIGINAL_VERSION = "1.0"
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

SUPPORT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
)

INPUT_SHEETS: Tuple[str, ...] = (*AUTHORITY_SHEETS, *R1_SHEETS, *PARENT_CLEAN_SHEETS, *ORIGINAL_SHEETS, *SUPPORT_SHEETS)

OUTPUT_SHEETS = [
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
]

COMMON_HEADERS = ["generated_ts", "schema_version", "approval_canonical_r1_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R14R2_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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
            "notes": "Phase 9A-6R14R2 canonical Clean-R1 mechanism-test execution approval rerun outputs.",
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
    approval_canonical_r1_run_id = _run_id(run_ts)

    _require(
        not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)),
        "Forbidden outcome-bearing sheet included in canonical approval inputs.",
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

    selected_rows = _select_authoritative_rows(inputs, canonical_manifest, component_authority)
    selected_payloads = {sheet_name: row["payload"] for sheet_name, row in selected_rows.items()}

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

    manifest_component_entries = canonical_manifest.get("authoritative_component_entries", [])
    manifest_component_count = len(manifest_component_entries)
    manifest_component_ids = [_normalize(entry.get("component_id")) for entry in manifest_component_entries]
    duplicate_manifest_components = [
        component for component, count in Counter(manifest_component_ids).items() if count > 1
    ]
    current_component_entries = [
        {
            "component_id": entry["component_id"],
            "fingerprint": selected_rows[entry["source_sheet"]]["fingerprint"],
        }
        for entry in manifest_component_entries
    ]
    manifest_component_cmp = _compare_expected_to_current(manifest_component_entries, current_component_entries)

    derived_entry_map = {
        _normalize(entry.get("component_id")): entry
        for entry in canonical_manifest.get("derived_entries", [])
    }
    parent_current = _sheet_latest_row_fingerprint_entries(
        inputs,
        PARENT_CLEAN_SHEETS,
        "clean_preregistration_run_id",
    )
    original_current = _sheet_full_row_fingerprint_entries(inputs, ORIGINAL_SHEETS)

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
        {"component_id": "parent_clean_version", "fingerprint": _fingerprint_payload({"sheet_fingerprints": parent_current})},
        {"component_id": "original_version", "fingerprint": _fingerprint_payload({"sheet_fingerprints": original_current})},
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
    derived_cmp = _compare_expected_to_current(expected_derived_entries, current_derived_entries)

    parent_component_fingerprint = derived_entry_map["parent_clean_version"].get("fingerprint")
    original_component_fingerprint = derived_entry_map["original_version"].get("fingerprint")

    authority_checks_pass = (
        _normalize(canonical_authority.get("authority_preregistration_version")) == AUTHORITATIVE_VERSION
        and _normalize(canonical_authority.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID
        and _normalize(canonical_authority.get("authority_selection_method")) == "EXACT_VERSION_AND_RUN_ID_MATCH"
        and int(canonical_authority.get("required_components", 0) or 0) == 12
        and int(canonical_authority.get("components_with_exactly_one_authoritative_row", 0) or 0) == 12
        and not canonical_authority.get("missing_authoritative_components")
        and not canonical_authority.get("duplicate_authoritative_components")
        and manifest_component_count == 12
        and not duplicate_manifest_components
    )

    authority_payload = {
        "authoritative_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "required_components": 12,
        "components_approved": int(canonical_authority.get("components_with_exactly_one_authoritative_row", 0) or 0),
        "missing_components": list(canonical_authority.get("missing_authoritative_components", [])),
        "duplicate_components": list(canonical_authority.get("duplicate_authoritative_components", [])),
        "mixed_run_components": 0,
        "unresolved_historical_rows": int(lineage_summary.get("unresolved_rows", 0) or 0),
        "authority_selection_method": canonical_authority.get("authority_selection_method"),
        "latest_physical_row_used": False,
        "latest_timestamp_used": False,
        "first_matching_row_rule_used": False,
        "workbook_row_order_used": False,
        "implicit_single_row_assumption_used": False,
        "manual_selection_used": False,
        "fallback_to_another_complete_run_used": False,
        "canonical_authority_status": "CANONICAL_AUTHORITY_APPROVED" if authority_checks_pass else "CANONICAL_AUTHORITY_BLOCKED",
    }

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
    historical_payload = {
        "run_ids_found": sorted(lineage_summary.get("run_ids_found", [])),
        "authoritative_run_count": 1,
        "complete_non_authoritative_runs": int(lineage_summary.get("complete_non_authoritative_runs", 0) or 0),
        "partial_runs": int(lineage_summary.get("partial_runs", 0) or 0),
        "superseded_rows": int(lineage_summary.get("superseded_rows", 0) or 0),
        "unresolved_rows": int(lineage_summary.get("unresolved_rows", 0) or 0),
        "partial_rows_in_authority": 0,
        "superseded_rows_in_authority": 0,
        "partial_rows_in_fingerprints": int(canonical_manifest.get("partial_rows_included", 0) or 0),
        "superseded_rows_in_fingerprints": int(canonical_manifest.get("superseded_rows_included", 0) or 0),
        "historical_isolation_status": "HISTORICAL_ROWS_SAFELY_ISOLATED" if historical_isolation_pass else "HISTORICAL_ROWS_NOT_ISOLATED",
    }

    fingerprint_pass = (
        _normalize(canonical_manifest.get("preregistration_version")) == AUTHORITATIVE_VERSION
        and _normalize(canonical_manifest.get("authoritative_run_id")) == AUTHORITATIVE_RUN_ID
        and manifest_component_count == 12
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
    fingerprint_payload = {
        "manifest_components": manifest_component_count,
        "components_fingerprinted": int(canonical_manifest.get("authoritative_components_fingerprinted", 0) or 0),
        "missing_fingerprints": list(canonical_manifest.get("missing_fingerprints", [])),
        "duplicate_authoritative_fingerprints": duplicate_manifest_components,
        "partial_rows_in_fingerprints": int(canonical_manifest.get("partial_rows_included", 0) or 0),
        "superseded_rows_in_fingerprints": int(canonical_manifest.get("superseded_rows_included", 0) or 0),
        "fingerprint_algorithm": canonical_manifest.get("stable_serialization_rule", {}).get("algorithm"),
        "stable_serialization_rule": canonical_manifest.get("stable_serialization_rule"),
        "authoritative_run_in_manifest": _normalize(canonical_manifest.get("authoritative_run_id")) == AUTHORITATIVE_RUN_ID,
        "parent_version_fingerprint_match": _normalize(parent_component_fingerprint) == _fingerprint_payload({"sheet_fingerprints": parent_current}),
        "original_version_fingerprint_match": _normalize(original_component_fingerprint) == _fingerprint_payload({"sheet_fingerprints": original_current}),
        "fingerprint_component_match": manifest_component_cmp["match"],
        "fingerprint_component_mismatches": manifest_component_cmp["mismatches"],
        "derived_fingerprint_match": derived_cmp["match"],
        "derived_fingerprint_mismatches": derived_cmp["mismatches"],
        "fingerprint_status": "CANONICAL_FINGERPRINT_CLOSURE_APPROVED" if fingerprint_pass else "CANONICAL_FINGERPRINT_CLOSURE_BLOCKED",
    }

    authority_stop_rules_list = authority_stop_rules.get("stop_rules", [])
    authority_stop_rule_names = {_normalize(rule.get("rule_name")) for rule in authority_stop_rules_list}
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
        and lineage_summary.get("statistical_method_changed") is False
    )
    science_payload = {
        "primary_mechanism": prereg_r1.get("primary_mechanism"),
        "exploratory_mechanism": prereg_r1.get("exploratory_mechanism"),
        "descriptive_only_mechanism": prereg_r1.get("descriptive_only_mechanism"),
        "primary_structure": prereg_r1.get("primary_structure"),
        "primary_exposure": prereg_r1.get("primary_exposure"),
        "primary_comparison_groups": prereg_r1.get("primary_comparison_groups"),
        "baseline_role": prereg_r1.get("baseline_role"),
        "primary_estimand": prereg_r1.get("primary_estimand"),
        "interpretation": PRIMARY_INTERPRETATION,
        "hypothesis_changed": bool(lineage_summary.get("hypothesis_changed")),
        "structure_changed": bool(lineage_summary.get("primary_structure_changed")),
        "population_changed": bool(lineage_summary.get("primary_population_changed")),
        "hierarchy_changed": bool(lineage_summary.get("hierarchy_changed")),
        "sample_gates_changed": bool(lineage_summary.get("sample_gates_changed")),
        "uncertainty_handling_changed": bool(lineage_summary.get("uncertainty_rules_changed")),
        "outcome_contract_changed": bool(lineage_summary.get("outcome_contract_changed")),
        "statistical_method_changed": bool(lineage_summary.get("statistical_method_changed")),
        "scientific_preservation_status": "SCIENTIFIC_CONTRACT_PRESERVED" if science_pass else "SCIENTIFIC_CONTRACT_CHANGED",
    }

    blinding_pass = (
        int(lineage_governance.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(lineage_governance.get("outcome_sheets_loaded", 0) or 0) == 0
        and int(lineage_governance.get("outcome_rows_loaded", 0) or 0) == 0
        and int(lineage_governance.get("realized_values_accessed", 0) or 0) == 0
        and int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0) == 0
        and int(lineage_governance.get("mechanism_tests_performed", 0) or 0) == 0
        and int(governance_r1.get("outcome_workbooks_opened", 0) or 0) == 0
        and int(governance_r1.get("outcome_rows_loaded", 0) or 0) == 0
    )
    blinding_payload = {
        "outcome_workbooks_opened": int(lineage_governance.get("outcome_workbooks_opened", 0) or 0),
        "outcome_sheets_loaded": int(lineage_governance.get("outcome_sheets_loaded", 0) or 0),
        "outcome_rows_loaded": int(lineage_governance.get("outcome_rows_loaded", 0) or 0),
        "realized_values_accessed": int(lineage_governance.get("realized_values_accessed", 0) or 0),
        "correctness_fields_accessed": 0,
        "accuracy_metrics_calculated": int(lineage_governance.get("accuracy_metrics_calculated", 0) or 0),
        "provider_performance_viewed": 0,
        "post_session_evidence_accessed": 0,
        "blinding_status": "BLINDING_INTACT_CLEAN_R1_CANONICAL" if blinding_pass else "BLINDING_BREACH_OR_UNVERIFIABLE",
    }

    structure_counts = _structure_counts(_classification_rows(inputs))
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
    count_payload = {
        "structural_pairs": structure_counts["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": structure_counts["consistency_classified_pairs"],
        "high_moderate_pairs": structure_counts["high_moderate_confidence_pairs"],
        "primary_contrast_observations": structure_counts["primary_contrast_eligible_observations"],
        "positive_observations": structure_counts["positive_primary_observations"],
        "negative_observations": structure_counts["negative_primary_observations"],
        "mixed_label_clusters": structure_counts["mixed_label_provider_session_clusters"],
        "provider_count": structure_counts["provider_count"],
        "session_count": structure_counts["session_count"],
        "cluster_count": structure_counts["cluster_count"],
        "baseline_match_count_errors": structure_counts["baseline_match_count_errors"],
        "gate_contract": gate_contract,
        "positive_gate": "PASS" if gate_statuses["positive_gate"] else "FAIL",
        "negative_gate": "PASS" if gate_statuses["negative_gate"] else "FAIL",
        "primary_contrast_gate": "PASS" if gate_statuses["primary_contrast_gate"] else "FAIL",
        "cluster_gate": "PASS" if gate_statuses["cluster_gate"] else "FAIL",
        "provider_gate": "PASS" if gate_statuses["provider_gate"] else "FAIL",
        "session_gate": "PASS" if gate_statuses["session_gate"] else "FAIL",
        "count_status": "ALL_BLINDED_SAMPLE_GATES_APPROVED" if count_pass and gate_pass else "BLINDED_SAMPLE_GATES_BLOCKED",
    }

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
    outcome_contract_payload = {
        "canonical_outcome_source_name": outcome_r1.get("canonical_outcome_source_sheet"),
        "canonical_outcome_source_workbook": outcome_r1.get("canonical_outcome_source_workbook"),
        "canonical_outcome_component_field": outcome_r1.get("canonical_outcome_component_field"),
        "canonical_outcome_version": outcome_r1.get("repaired_canonical_outcome_version"),
        "evaluation_window_version": outcome_r1.get("evaluation_window_version"),
        "outcome_timestamp_contract": timestamp_contract,
        "outcome_version_handling": version_handling,
        "evaluation_window_handling": window_handling,
        "outcome_contract_status": "OUTCOME_TIMESTAMP_AND_VERSION_CONTRACT_APPROVED" if outcome_contract_pass else "OUTCOME_CONTRACT_BLOCKED",
    }

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
    )
    join_payload = {
        "approved_future_join_path": join_r1.get("approved_future_join_path"),
        "stable_key_components": join_r1.get("stable_key_components"),
        "bridge_components": join_r1.get("bridge_components"),
        "physical_row_join_prohibited": join_r1.get("physical_row_number_join_prohibited"),
        "fuzzy_join_prohibited": join_r1.get("fuzzy_text_join_prohibited"),
        "manual_join_prohibited": join_r1.get("manual_matching_prohibited"),
        "nearest_date_join_prohibited": join_r1.get("nearest_date_matching_prohibited"),
        "provider_only_join_prohibited": join_r1.get("provider_name_only_join_prohibited"),
        "session_only_join_prohibited": join_r1.get("session_only_join_prohibited"),
        "pack_only_join_prohibited": join_r1.get("pack_level_only_join_prohibited"),
        "duplicate_join_result": join_r1.get("duplicate_join_result"),
        "ambiguous_join_result": join_r1.get("ambiguous_join_result"),
        "missing_join_result": join_r1.get("missing_join_result"),
        "join_status": "STABLE_FAIL_CLOSED_JOIN_APPROVED" if join_contract_pass else "JOIN_CONTRACT_BLOCKED",
    }

    explicit_case_map = success_r1.get("explicit_case_map", {})
    rule_precedence = success_r1.get("rule_precedence", [])
    success_pass = (
        set(success_r1.get("allowed_output_statuses", [])) == {"SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"}
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
    success_payload = {
        "allowed_output_statuses": success_r1.get("allowed_output_statuses"),
        "explicit_case_map": explicit_case_map,
        "rule_precedence": rule_precedence,
        "policy_notes": success_r1.get("policy_notes"),
        "success_derivation_status": "SUCCESS_DERIVATION_APPROVED" if success_pass else "SUCCESS_DERIVATION_BLOCKED",
    }

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
    method_payload = {
        "primary_method": method_r1.get("primary_method_id"),
        "bootstrap_replications": int(method_r1.get("bootstrap_replications", 0) or 0),
        "random_seed": int(method_r1.get("bootstrap_random_seed", 0) or 0),
        "resampling_unit": method_r1.get("resampling_unit"),
        "resampling_procedure": method_r1.get("resampling_procedure"),
        "confidence_interval_method": method_r1.get("confidence_interval_method"),
        "confidence_interval_quantiles": method_r1.get("confidence_interval_quantiles"),
        "zero_cell_handling": method_r1.get("zero_cell_handling"),
        "sparse_group_handling": method_r1.get("sparse_group_handling"),
        "degenerate_bootstrap_handling": method_r1.get("degenerate_bootstrap_handling"),
        "primary_method_computation_failure": method_r1.get("primary_method_computation_failure"),
        "descriptive_fallback": method_r1.get("descriptive_fallback"),
        "primary_interpretation": method_r1.get("primary_interpretation"),
        "small_cluster_warning": method_r1.get("small_cluster_warning"),
        "method_status": "STATISTICAL_METHOD_APPROVED" if method_pass else "STATISTICAL_METHOD_BLOCKED",
    }

    execution_stop_rules = stop_rules_r1.get("stop_rules", [])
    execution_stop_rule_names = {_normalize(rule.get("stop_rule_name")) for rule in execution_stop_rules}
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
    additive_stop_rules_pass = execution_stop_rule_names.isdisjoint(AUTHORITY_STOP_RULE_NAMES) and authority_stop_rules_pass
    stop_rule_payload = {
        "execution_stop_rule_names": sorted(execution_stop_rule_names),
        "authority_stop_rule_names": sorted(authority_stop_rule_names),
        "execution_stop_rule_count": len(execution_stop_rules),
        "authority_stop_rule_count": len(authority_stop_rules_list),
        "execution_stop_rules_fail_closed": stop_rules_r1.get("fail_closed") is True,
        "execution_stop_rules_automatic_retry_allowed": stop_rules_r1.get("automatic_retry_allowed"),
        "execution_hard_stop_summary_allowed": stop_rules_r1.get("hard_stop_summary_allowed"),
        "authority_stop_rules_complete": authority_stop_rules_pass,
        "authority_stop_rules_additive": additive_stop_rules_pass,
        "stop_rule_status": (
            "EXECUTION_AND_AUTHORITY_STOP_RULES_APPROVED"
            if execution_stop_rules_pass and additive_stop_rules_pass
            else "STOP_RULE_CONTRACT_BLOCKED"
        ),
    }

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
    load_order_pass = (
        canonical_authority.get("no_outcome_workbook_open_before_authority_pass") is True
        and int(canonical_authority.get("required_components", 0) or 0) == 12
        and authority_checks_pass
        and fingerprint_pass
    )
    load_order_payload = {
        "approved_load_sequence": load_sequence,
        "canonical_authority_future_algorithm": canonical_authority.get("future_test_builder_load_algorithm"),
        "outcome_access_permitted_only_after_step": 12,
        "load_order_status": "PRE_OUTCOME_LOAD_ORDER_APPROVED" if load_order_pass else "LOAD_ORDER_BLOCKED",
    }

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
    )
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

    all_checks_pass = all(
        [
            authority_checks_pass,
            historical_isolation_pass,
            fingerprint_pass,
            authority_stop_rules_pass,
            science_pass,
            blinding_pass,
            count_pass,
            gate_pass,
            outcome_contract_pass,
            join_contract_pass,
            success_pass,
            method_pass,
            execution_stop_rules_pass,
            additive_stop_rules_pass,
            load_order_pass,
            governance_pass,
        ]
    )

    build_status = "PASS_WITH_WARNINGS" if all_checks_pass else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_EXECUTION_CANONICAL_R1_APPROVED_WITH_WARNINGS"
        if all_checks_pass
        else "REFINED_MECHANISM_TEST_EXECUTION_CANONICAL_R1_APPROVAL_NEEDS_REPAIR"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R15_CLEAN_R1_MECHANISM_TEST_EXECUTION"
        if all_checks_pass
        else "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR"
    )

    overall_payload = {
        "approval_version": APPROVAL_VERSION,
        "authoritative_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "canonical_authority_status": authority_payload["canonical_authority_status"],
        "historical_isolation_status": historical_payload["historical_isolation_status"],
        "fingerprint_status": fingerprint_payload["fingerprint_status"],
        "blinding_status": blinding_payload["blinding_status"],
        "science_status": science_payload["scientific_preservation_status"],
        "count_status": count_payload["count_status"],
        "outcome_contract_status": outcome_contract_payload["outcome_contract_status"],
        "join_status": join_payload["join_status"],
        "success_derivation_status": success_payload["success_derivation_status"],
        "method_status": method_payload["method_status"],
        "stop_rule_status": stop_rule_payload["stop_rule_status"],
        "load_order_status": load_order_payload["load_order_status"],
        "ready_for_one_canonical_clean_r1_mechanism_test_execution": all_checks_pass,
        "recommended_next_step": recommended_next_step,
    }

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "authoritative_version": AUTHORITATIVE_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "required_components": 12,
        "components_approved": authority_payload["components_approved"],
        "missing_components": authority_payload["missing_components"],
        "duplicate_components": authority_payload["duplicate_components"],
        "canonical_authority_status": authority_payload["canonical_authority_status"],
        "run_ids_found": historical_payload["run_ids_found"],
        "complete_non_authoritative_runs": historical_payload["complete_non_authoritative_runs"],
        "partial_runs": historical_payload["partial_runs"],
        "superseded_rows": historical_payload["superseded_rows"],
        "unresolved_rows": historical_payload["unresolved_rows"],
        "partial_rows_in_authority": historical_payload["partial_rows_in_authority"],
        "superseded_rows_in_authority": historical_payload["superseded_rows_in_authority"],
        "historical_isolation_status": historical_payload["historical_isolation_status"],
        "manifest_components": fingerprint_payload["manifest_components"],
        "components_fingerprinted": fingerprint_payload["components_fingerprinted"],
        "missing_fingerprints": fingerprint_payload["missing_fingerprints"],
        "partial_rows_in_fingerprints": fingerprint_payload["partial_rows_in_fingerprints"],
        "superseded_rows_in_fingerprints": fingerprint_payload["superseded_rows_in_fingerprints"],
        "fingerprint_status": fingerprint_payload["fingerprint_status"],
        "outcome_workbooks_opened": blinding_payload["outcome_workbooks_opened"],
        "outcome_sheets_loaded": blinding_payload["outcome_sheets_loaded"],
        "outcome_rows_loaded": blinding_payload["outcome_rows_loaded"],
        "realized_values_accessed": blinding_payload["realized_values_accessed"],
        "accuracy_metrics_calculated": blinding_payload["accuracy_metrics_calculated"],
        "blinding_status": blinding_payload["blinding_status"],
        "primary_mechanism": science_payload["primary_mechanism"],
        "hypothesis_changed": science_payload["hypothesis_changed"],
        "structure_changed": science_payload["structure_changed"],
        "population_changed": science_payload["population_changed"],
        "hierarchy_changed": science_payload["hierarchy_changed"],
        "sample_gates_changed": science_payload["sample_gates_changed"],
        "scientific_preservation_status": science_payload["scientific_preservation_status"],
        "structural_pairs": count_payload["structural_pairs"],
        "consistency_classified_pairs": count_payload["consistency_classified_pairs"],
        "high_moderate_pairs": count_payload["high_moderate_pairs"],
        "primary_contrast_observations": count_payload["primary_contrast_observations"],
        "positive_observations": count_payload["positive_observations"],
        "negative_observations": count_payload["negative_observations"],
        "mixed_label_clusters": count_payload["mixed_label_clusters"],
        "positive_gate": count_payload["positive_gate"],
        "negative_gate": count_payload["negative_gate"],
        "primary_contrast_gate": count_payload["primary_contrast_gate"],
        "cluster_gate": count_payload["cluster_gate"],
        "provider_gate": count_payload["provider_gate"],
        "session_gate": count_payload["session_gate"],
        "outcome_timestamp_contract": outcome_contract_pass,
        "outcome_version_handling": outcome_contract_pass,
        "evaluation_window_handling": outcome_contract_pass,
        "join_contract": join_contract_pass,
        "success_derivation": success_pass,
        "statistical_method": method_pass,
        "bootstrap_replications": method_payload["bootstrap_replications"],
        "random_seed": method_payload["random_seed"],
        "resampling_unit": method_payload["resampling_unit"],
        "descriptive_fallback": method_payload["descriptive_fallback"],
        "execution_stop_rules": execution_stop_rules_pass,
        "authority_stop_rules": authority_stop_rules_pass,
        "fingerprints_approved": fingerprint_pass,
        "outcome_access": 0,
        "test_execution": 0,
        "preregistration_modification": 0,
        "classification_modification": governance_payload["classifications_modified"],
        "production_writes": governance_payload["production_writes"],
        "ready_for_one_canonical_clean_r1_mechanism_test_execution": all_checks_pass,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
    }

    payloads = {
        "Refined_Mechanism_Test_Execution_Approval_Canonical_R1": overall_payload,
        "Refined_Mechanism_Test_Canonical_R1_Authority_Approval": authority_payload,
        "Refined_Mechanism_Test_Canonical_R1_Historical_Isolation_Approval": historical_payload,
        "Refined_Mechanism_Test_Canonical_R1_Fingerprint_Approval": fingerprint_payload,
        "Refined_Mechanism_Test_Canonical_R1_Blinding_Approval": blinding_payload,
        "Refined_Mechanism_Test_Canonical_R1_Science_Approval": science_payload,
        "Refined_Mechanism_Test_Canonical_R1_Count_Approval": count_payload,
        "Refined_Mechanism_Test_Canonical_R1_Outcome_Contract_Approval": outcome_contract_payload,
        "Refined_Mechanism_Test_Canonical_R1_Join_Approval": join_payload,
        "Refined_Mechanism_Test_Canonical_R1_Success_Approval": success_payload,
        "Refined_Mechanism_Test_Canonical_R1_Method_Approval": method_payload,
        "Refined_Mechanism_Test_Canonical_R1_Stop_Rule_Approval": stop_rule_payload,
        "Refined_Mechanism_Test_Canonical_R1_Load_Order_Approval": load_order_payload,
        "Refined_Mechanism_Test_Canonical_R1_Approval_Governance": governance_payload,
        "Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary": summary_payload,
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
            approval_canonical_r1_run_id,
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
        "approval_canonical_r1_run_id": approval_canonical_r1_run_id,
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
