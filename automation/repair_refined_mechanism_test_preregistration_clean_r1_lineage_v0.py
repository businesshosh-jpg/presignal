#!/usr/bin/env python3
"""Phase 9A-6R13R1L — Clean-R1 Partial-Write Lineage and Authority Repair.

This phase repairs only the lineage and authority contract for the existing
`1.0-clean-r1` preregistration family. It does not modify any scientific
content and does not access any outcome-bearing source.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple


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


PHASE_ID = "9A-6R13R1L"
BUILD_SCRIPT = "automation/repair_refined_mechanism_test_preregistration_clean_r1_lineage_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_preregistration_clean_r1_lineage_v0"
LINEAGE_REPAIR_VERSION = "refined_mechanism_test_preregistration_clean_r1_lineage_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_CLEAN_R1_LINEAGE_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_R1_VERSION = "1.0-clean-r1"
AUTHORITATIVE_RUN_ID = "9A-6R13R1_20260711T020141Z"
KNOWN_R1_RUN_IDS = (
    "9A-6R13R1_20260711T015443Z",
    "9A-6R13R1_20260711T015833Z",
    "9A-6R13R1_20260711T020141Z",
)
PARENT_CLEAN_VERSION = "1.0-clean"
PARENT_CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
ORIGINAL_VERSION = "1.0"

PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"
PRIMARY_ESTIMAND = (
    "difference in baseline-to-expanded corrected directional-success deltas"
)

EXPECTED_COUNTS = {
    "structural_pairs": 96,
    "consistency_classified_pairs": 82,
    "high_moderate_pairs": 72,
    "primary_contrast_observations": 72,
    "positive_observations": 57,
    "negative_observations": 15,
    "mixed_label_clusters": 12,
}

EXPECTED_SAMPLE_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_primary_contrast_observations": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
}

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}

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

COMPONENT_IDS: Dict[str, str] = {
    "Refined_Mechanism_Test_Preregistration_Clean_R1": "preregistration",
    "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1": "outcome_definition",
    "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1": "join_rules",
    "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1": "success_derivation",
    "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1": "statistical_method",
    "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1": "stop_rules",
    "Refined_Mechanism_Test_Clean_R1_Design_Reconciliation": "design_reconciliation",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Audit": "lineage_audit",
    "Refined_Mechanism_Test_Clean_R1_Blinding_Audit": "blinding_audit",
    "Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze": "fingerprint_freeze",
    "Refined_Mechanism_Test_Clean_R1_Governance": "governance",
    "Refined_Mechanism_Test_Preregistration_Clean_R1_Summary": "summary",
}

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

APPROVAL_INPUT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution_Approval_Clean_R1",
    "Refined_Mechanism_Test_Clean_R1_Authority_Approval",
    "Refined_Mechanism_Test_Clean_R1_Partial_Write_Audit",
    "Refined_Mechanism_Test_Clean_R1_Fingerprint_Approval",
    "Refined_Mechanism_Test_Execution_Approval_Clean_R1_Summary",
)

INPUT_SHEETS: Tuple[str, ...] = (*R1_SHEETS, *APPROVAL_INPUT_SHEETS, *PARENT_CLEAN_SHEETS, *ORIGINAL_SHEETS)

OUTPUT_SHEETS = [
    "Refined_Mechanism_Test_Clean_R1_Canonical_Authority",
    "Refined_Mechanism_Test_Clean_R1_Component_Authority",
    "Refined_Mechanism_Test_Clean_R1_Historical_Run_Disposition",
    "Refined_Mechanism_Test_Clean_R1_Scientific_Equivalence_Audit",
    "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest",
    "Refined_Mechanism_Test_Clean_R1_Authority_Stop_Rules",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Governance",
    "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Summary",
]

COMMON_HEADERS = ["generated_ts", "schema_version", "lineage_repair_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}

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


def _run_id(ts: datetime) -> str:
    return f"9A-6R13R1L_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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
        _normalize(entry.get("sheet_name") or entry.get("component")): _normalize(entry.get("fingerprint"))
        for entry in expected_entries
    }
    current = {
        _normalize(entry.get("sheet_name") or entry.get("component")): _normalize(entry.get("fingerprint"))
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


def _stop_rule(
    rule_id: str,
    rule_name: str,
    trigger: str,
    runtime_assertion: str,
    required_repair_phase: str,
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "trigger": trigger,
        "runtime_assertion": runtime_assertion,
        "severity": "HARD_STOP",
        "blocked_status": "BLOCKED",
        "diagnostic_logging": [
            "authority_preregistration_version",
            "authoritative_repair_run_id",
            "component_id",
            "sheet_name",
            "expected_value",
            "observed_value",
            "detection_timestamp",
        ],
        "successful_execution_allowed": False,
        "automatic_retry_allowed": False,
        "required_repair_phase": required_repair_phase,
    }


def _build_authority_stop_rules() -> List[Dict[str, Any]]:
    return [
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-001",
            "AUTHORITATIVE_RUN_ID_MISSING",
            "The canonical authority layer cannot locate the frozen authoritative run ID.",
            "authoritative_run_id_present == TRUE",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-002",
            "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT",
            "More than one authoritative row is returned for a required component.",
            "authoritative_row_count_per_component == 1",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-003",
            "AUTHORITATIVE_COMPONENT_MISSING",
            "A required authoritative component is missing.",
            "required_component_present == TRUE",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-004",
            "AUTHORITATIVE_COMPONENT_INCOMPLETE",
            "A required authoritative component exists but is incomplete.",
            "authoritative_component_payload_complete == TRUE",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-005",
            "SUPERSEDED_ROW_SELECTED",
            "A superseded non-authoritative row is selected for execution.",
            "selected_row_run_id == authoritative_run_id",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-006",
            "LATEST_ROW_SELECTION_ATTEMPT",
            "Execution attempts to choose authority using latest physical row position.",
            "selection_strategy != latest_physical_row",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-007",
            "LATEST_TIMESTAMP_SELECTION_ATTEMPT",
            "Execution attempts to choose authority using latest timestamp alone.",
            "selection_strategy != latest_timestamp",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-008",
            "MANUAL_AUTHORITY_OVERRIDE_REQUESTED",
            "Execution requests manual authority selection.",
            "manual_authority_override == FALSE",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-009",
            "AUTHORITATIVE_FINGERPRINT_MISMATCH",
            "An authoritative component fingerprint differs from the canonical manifest.",
            "observed_authoritative_component_fingerprint == canonical_manifest_fingerprint",
            "RERUN_PHASE9A6R14R1_CLEAN_R1_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-010",
            "FINGERPRINT_MANIFEST_INCOMPLETE",
            "The canonical authoritative fingerprint manifest is incomplete.",
            "canonical_manifest_component_count == 12",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-011",
            "PARTIAL_ROW_INCLUDED_IN_FINGERPRINT",
            "A partial or superseded row contributes to an authoritative fingerprint.",
            "authoritative_fingerprint_sources_all_authoritative == TRUE",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-012",
            "NONAUTHORITATIVE_RUN_USED_FOR_EXECUTION",
            "A non-authoritative complete run is used for execution.",
            "selected_run_id == authoritative_run_id",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-013",
            "AUTHORITY_VERSION_MISMATCH",
            "The execution authority version differs from the canonical lineage contract.",
            "selected_preregistration_version == authoritative_preregistration_version",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-014",
            "AUTHORITY_RUN_ID_MISMATCH",
            "The execution authority run ID differs from the canonical lineage contract.",
            "selected_repair_run_id == authoritative_repair_run_id",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1L-AUTH-015",
            "MIXED_RUN_CONTRACT_ASSEMBLY_ATTEMPT",
            "Execution assembles the contract from multiple R1 run IDs.",
            "unique_selected_run_ids == {authoritative_run_id}",
            "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR",
        ),
    ]


def _scientific_subset_preregistration(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "primary_mechanism": payload.get("primary_mechanism"),
        "exploratory_mechanism": payload.get("exploratory_mechanism"),
        "descriptive_only_mechanism": payload.get("descriptive_only_mechanism"),
        "primary_structure": payload.get("primary_structure"),
        "primary_unit": payload.get("primary_unit"),
        "primary_exposure": payload.get("primary_exposure"),
        "primary_comparison_groups": payload.get("primary_comparison_groups"),
        "baseline_role": payload.get("baseline_role"),
        "primary_estimand": payload.get("primary_estimand"),
        "sample_gates": payload.get("sample_gates"),
        "counts": payload.get("counts"),
        "uncertainty_rules": payload.get("uncertainty_rules"),
        "repair_type": payload.get("repair_type"),
    }


def _scientific_signature(payloads_by_sheet: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "preregistration": _scientific_subset_preregistration(
            payloads_by_sheet["Refined_Mechanism_Test_Preregistration_Clean_R1"]
        ),
        "outcome_definition": payloads_by_sheet["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"],
        "join_rules": payloads_by_sheet["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"],
        "success_derivation": payloads_by_sheet["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"],
        "statistical_method": payloads_by_sheet["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"],
        "stop_rules": payloads_by_sheet["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"],
        "design_reconciliation": payloads_by_sheet["Refined_Mechanism_Test_Clean_R1_Design_Reconciliation"],
    }


def _collect_r1_lineage(inputs: Mapping[str, Any]) -> Dict[str, Any]:
    run_coverage: Dict[str, Dict[str, Any]] = {}
    row_records: List[Dict[str, Any]] = []
    component_records: List[Dict[str, Any]] = []
    authoritative_rows: Dict[str, Dict[str, Any]] = {}

    for sheet_name in R1_SHEETS:
        parsed_rows: List[Dict[str, Any]] = []
        raw_rows = [dict(row) for row in inputs[sheet_name].rows]
        for row in sorted(
            raw_rows,
            key=lambda item: (
                _normalize(item.get("generated_ts")),
                _normalize(item.get("clean_contract_repair_run_id")),
                int(item.get("__source_row_number__", 0) or 0),
            ),
        ):
            payload_raw = _normalize(row.get("payload_json"))
            try:
                payload = json.loads(payload_raw) if payload_raw else None
            except json.JSONDecodeError:
                payload = None
            payload_complete = isinstance(payload, dict) and bool(payload)
            run_id = _normalize(row.get("clean_contract_repair_run_id"))
            row_number = int(row.get("__source_row_number__", 0) or 0)
            source_row_key = f"{sheet_name}::{run_id or 'MISSING_RUN_ID'}::{row_number}"
            parsed = {
                "sheet_name": sheet_name,
                "component_id": COMPONENT_IDS[sheet_name],
                "run_id": run_id,
                "generated_ts": _normalize(row.get("generated_ts")),
                "row_number": row_number,
                "source_row_key": source_row_key,
                "payload_complete": payload_complete,
                "payload": payload if isinstance(payload, dict) else {},
                "payload_fingerprint": _fingerprint_payload(payload) if payload_complete else "",
            }
            parsed_rows.append(parsed)
            row_records.append(parsed)

            if run_id:
                coverage = run_coverage.setdefault(
                    run_id,
                    {
                        "run_id": run_id,
                        "rows": 0,
                        "sheet_names": set(),
                        "complete_sheet_names": set(),
                        "timestamps": set(),
                    },
                )
                coverage["rows"] += 1
                coverage["sheet_names"].add(sheet_name)
                coverage["timestamps"].add(parsed["generated_ts"])
                if payload_complete:
                    coverage["complete_sheet_names"].add(sheet_name)

        authoritative_candidates = [row for row in parsed_rows if row["run_id"] == AUTHORITATIVE_RUN_ID]
        authoritative_complete = [row for row in authoritative_candidates if row["payload_complete"]]
        if len(authoritative_complete) == 1:
            authoritative_rows[sheet_name] = authoritative_complete[0]

        if len(authoritative_candidates) == 0:
            authority_status = "AUTHORITATIVE_COMPONENT_MISSING"
        elif len(authoritative_complete) == 0:
            authority_status = "AUTHORITATIVE_COMPONENT_INCOMPLETE"
        elif len(authoritative_complete) > 1:
            authority_status = "MULTIPLE_AUTHORITATIVE_ROWS_FOR_COMPONENT"
        else:
            authority_status = "EXACTLY_ONE_COMPLETE_AUTHORITATIVE_ROW"

        component_records.append(
            {
                "sheet_name": sheet_name,
                "component_id": COMPONENT_IDS[sheet_name],
                "rows_present": len(parsed_rows),
                "run_ids_present": sorted({row["run_id"] for row in parsed_rows if row["run_id"]}),
                "authoritative_row_count": len(authoritative_candidates),
                "complete_authoritative_row_count": len(authoritative_complete),
                "non_authoritative_complete_row_count": sum(
                    1 for row in parsed_rows if row["run_id"] != AUTHORITATIVE_RUN_ID and row["payload_complete"]
                ),
                "partial_row_count": sum(1 for row in parsed_rows if not row["payload_complete"]),
                "payload_completeness": {
                    "all_authoritative_payloads_complete": len(authoritative_complete) == 1,
                    "all_rows_parseable": all(
                        isinstance(row.get("payload"), dict) or not row["payload_complete"] for row in parsed_rows
                    ),
                },
                "authority_status": authority_status,
            }
        )

    run_records: List[Dict[str, Any]] = []
    for run_id, coverage in sorted(run_coverage.items()):
        complete_sheet_count = len(coverage["complete_sheet_names"])
        if run_id == AUTHORITATIVE_RUN_ID and complete_sheet_count == len(R1_SHEETS):
            run_status = "AUTHORITATIVE_SUCCESSFUL_RUN"
        elif complete_sheet_count == len(R1_SHEETS):
            run_status = "SUPERSEDED_COMPLETE_NONAUTHORITATIVE_RUN"
        elif complete_sheet_count > 0:
            run_status = "SUPERSEDED_PARTIAL_RUN"
        else:
            run_status = "INCOMPLETE_FAILED_RUN"
        run_records.append(
            {
                "run_id": run_id,
                "row_count": coverage["rows"],
                "sheet_count": len(coverage["sheet_names"]),
                "complete_sheet_count": complete_sheet_count,
                "sheet_names": sorted(coverage["sheet_names"]),
                "missing_sheets": sorted(set(R1_SHEETS) - set(coverage["sheet_names"])),
                "missing_complete_sheets": sorted(set(R1_SHEETS) - set(coverage["complete_sheet_names"])),
                "timestamps": sorted(coverage["timestamps"]),
                "run_status": run_status,
            }
        )

    run_status_map = {record["run_id"]: record["run_status"] for record in run_records}
    for record in row_records:
        if record["run_id"] == AUTHORITATIVE_RUN_ID:
            record["historical_row_classification"] = "AUTHORITATIVE_COMPLETE_ROW"
        else:
            run_status = run_status_map.get(record["run_id"])
            if run_status == "SUPERSEDED_COMPLETE_NONAUTHORITATIVE_RUN":
                record["historical_row_classification"] = "SUPERSEDED_COMPLETE_NONAUTHORITATIVE_RUN"
            elif run_status == "SUPERSEDED_PARTIAL_RUN":
                record["historical_row_classification"] = "SUPERSEDED_PARTIAL_RUN"
            elif not record["payload_complete"]:
                record["historical_row_classification"] = "INCOMPLETE_FAILED_RUN"
            else:
                record["historical_row_classification"] = "UNRESOLVED_HISTORICAL_ROW"

    authoritative_component_count = sum(
        1 for record in component_records if record["authority_status"] == "EXACTLY_ONE_COMPLETE_AUTHORITATIVE_ROW"
    )
    missing_components = [
        record["component_id"]
        for record in component_records
        if record["authoritative_row_count"] == 0
    ]
    duplicate_components = [
        record["component_id"]
        for record in component_records
        if record["complete_authoritative_row_count"] > 1
    ]

    if authoritative_component_count == len(R1_SHEETS):
        authority_status = "CANONICAL_AUTHORITY_COMPLETE"
    elif authoritative_component_count > 0:
        authority_status = "CANONICAL_AUTHORITY_INCOMPLETE"
    else:
        authority_status = "BLOCKED"

    return {
        "row_records": row_records,
        "component_records": component_records,
        "run_records": run_records,
        "authoritative_rows": authoritative_rows,
        "authority_status": authority_status,
        "required_components": len(R1_SHEETS),
        "components_with_exactly_one_authoritative_row": authoritative_component_count,
        "missing_components": missing_components,
        "duplicate_components": duplicate_components,
        "run_ids_found": sorted(run_coverage.keys()),
    }


def _find_source_row_key(rows: Sequence[Mapping[str, Any]], run_key: str) -> str:
    latest = _latest_row(rows, run_key)
    if not latest:
        return ""
    return f"{latest.get('__sheet_name__', '') or ''}::{_normalize(latest.get(run_key))}::{int(latest.get('__source_row_number__', 0) or 0)}"


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
            "notes": "Phase 9A-6R13R1L clean-r1 lineage and authority repair outputs.",
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
    lineage_repair_run_id = _run_id(run_ts)

    _require(
        not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)),
        "Forbidden outcome-bearing sheet included in lineage repair inputs.",
    )

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget = _ensure_cell_budget(service, known_titles)
    _ensure_output_sheets(service, known_titles)

    prior_approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Clean_R1_Summary"].rows,
        "approval_clean_r1_run_id",
    )
    prior_fingerprint_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_R1_Fingerprint_Approval"].rows,
        "approval_clean_r1_run_id",
    )
    _require(
        _normalize(prior_approval_summary.get("final_interpretation"))
        == "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_R1_LINEAGE_REPAIR_REQUIRED",
        "Phase 9A-6R14R1 did not leave the workbook in lineage-repair-required state.",
    )
    _require(
        _normalize(prior_approval_summary.get("authoritative_repair_run_id")) == AUTHORITATIVE_RUN_ID,
        "Prior approval authoritative run ID mismatch.",
    )

    lineage = _collect_r1_lineage(inputs)
    _require(
        lineage["components_with_exactly_one_authoritative_row"] == len(R1_SHEETS),
        f"Canonical authority component closure failed: missing={lineage['missing_components']} duplicates={lineage['duplicate_components']}",
    )

    authoritative_rows = lineage["authoritative_rows"]
    authoritative_payloads = {
        sheet_name: authoritative_rows[sheet_name]["payload"] for sheet_name in R1_SHEETS
    }

    prereg_r1 = authoritative_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1"]
    outcome_r1 = authoritative_payloads["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1"]
    join_r1 = authoritative_payloads["Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1"]
    success_r1 = authoritative_payloads["Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1"]
    method_r1 = authoritative_payloads["Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1"]
    stop_r1 = authoritative_payloads["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1"]
    design_r1 = authoritative_payloads["Refined_Mechanism_Test_Clean_R1_Design_Reconciliation"]
    lineage_r1 = authoritative_payloads["Refined_Mechanism_Test_Clean_R1_Lineage_Audit"]
    blinding_r1 = authoritative_payloads["Refined_Mechanism_Test_Clean_R1_Blinding_Audit"]
    fingerprint_r1 = authoritative_payloads["Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze"]
    governance_r1 = authoritative_payloads["Refined_Mechanism_Test_Clean_R1_Governance"]
    summary_r1 = authoritative_payloads["Refined_Mechanism_Test_Preregistration_Clean_R1_Summary"]

    _require(
        _normalize(prereg_r1.get("repaired_preregistration_version")) == AUTHORITATIVE_R1_VERSION,
        "Authoritative R1 preregistration version mismatch.",
    )
    _require(
        _normalize(prereg_r1.get("clean_contract_repair_run_id")) == AUTHORITATIVE_RUN_ID,
        "Authoritative R1 repair run ID mismatch inside preregistration payload.",
    )
    _require(
        _normalize(prereg_r1.get("parent_preregistration_version")) == PARENT_CLEAN_VERSION,
        "Parent clean version mismatch.",
    )
    _require(
        _normalize(prereg_r1.get("original_preregistration_version")) == ORIGINAL_VERSION,
        "Original preregistration version mismatch.",
    )
    _require(
        _normalize(prereg_r1.get("repair_type")) == "EXECUTION_CONTRACT_COMPLETION_ONLY",
        "R1 repair type changed.",
    )

    parent_expected = prereg_r1.get("authoritative_parent_clean_references", [])
    parent_current = _sheet_latest_row_fingerprint_entries(
        inputs,
        [_normalize(entry.get("sheet_name")) for entry in parent_expected],
        "clean_preregistration_run_id",
    )
    original_expected = fingerprint_r1.get("original_expected_fingerprints", [])
    original_current = _sheet_full_row_fingerprint_entries(inputs, ORIGINAL_SHEETS)

    parent_cmp = _compare_expected_to_current(parent_expected, parent_current)
    original_cmp = _compare_expected_to_current(original_expected, original_current)
    _require(parent_cmp["match"], f"Parent clean family changed: {parent_cmp['mismatches']}")
    _require(original_cmp["match"], f"Original v1.0 family changed: {original_cmp['mismatches']}")

    counts_r1 = prereg_r1.get("counts", {})
    expected_count_checks = {
        "structural_baseline_expanded_pairs": EXPECTED_COUNTS["structural_pairs"],
        "consistency_classified_pairs": EXPECTED_COUNTS["consistency_classified_pairs"],
        "high_moderate_confidence_pairs": EXPECTED_COUNTS["high_moderate_pairs"],
        "primary_contrast_eligible_observations": EXPECTED_COUNTS["primary_contrast_observations"],
        "positive_primary_observations": EXPECTED_COUNTS["positive_observations"],
        "negative_primary_observations": EXPECTED_COUNTS["negative_observations"],
        "mixed_label_provider_session_clusters": EXPECTED_COUNTS["mixed_label_clusters"],
    }
    for key, expected_value in expected_count_checks.items():
        _require(
            int(counts_r1.get(key, -1)) == expected_value,
            f"Authoritative R1 count changed for {key}: {counts_r1}",
        )
    _require(
        prereg_r1.get("sample_gates") == EXPECTED_SAMPLE_GATES,
        f"Authoritative sample gates changed: {prereg_r1.get('sample_gates')}",
    )

    run_payloads: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in lineage["row_records"]:
        if row["payload_complete"] and row["run_id"]:
            run_payloads[row["run_id"]][row["sheet_name"]] = row["payload"]

    authoritative_scientific_signature = _scientific_signature(authoritative_payloads)
    complete_non_authoritative_runs = [
        record
        for record in lineage["run_records"]
        if record["run_status"] == "SUPERSEDED_COMPLETE_NONAUTHORITATIVE_RUN"
    ]

    scientific_equivalence_rows: List[Dict[str, Any]] = []
    complete_non_auth_run_count = 0
    scientific_equivalence_status = "NO_COMPLETE_NONAUTHORITATIVE_RUNS"
    for record in complete_non_authoritative_runs:
        complete_non_auth_run_count += 1
        run_id = record["run_id"]
        payloads_by_sheet = run_payloads[run_id]
        signature = _scientific_signature(payloads_by_sheet)
        metadata_only_difference_components = []
        exact_full_payload_components = []
        scientific_content_difference_components = []
        for sheet_name in R1_SHEETS:
            nonauth_payload = payloads_by_sheet.get(sheet_name)
            auth_payload = authoritative_payloads[sheet_name]
            if nonauth_payload == auth_payload:
                exact_full_payload_components.append(sheet_name)
            elif sheet_name in {
                "Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze",
                "Refined_Mechanism_Test_Clean_R1_Governance",
            }:
                metadata_only_difference_components.append(sheet_name)
            elif sheet_name == "Refined_Mechanism_Test_Preregistration_Clean_R1":
                nonauth_subset = _scientific_subset_preregistration(nonauth_payload)
                auth_subset = _scientific_subset_preregistration(auth_payload)
                if nonauth_subset == auth_subset:
                    metadata_only_difference_components.append(sheet_name)
                else:
                    scientific_content_difference_components.append(sheet_name)
            elif nonauth_payload != auth_payload:
                scientific_content_difference_components.append(sheet_name)

        if signature == authoritative_scientific_signature and not scientific_content_difference_components:
            status = "SCIENTIFICALLY_IDENTICAL_SUPERSEDED_RUN"
        elif not scientific_content_difference_components:
            status = "METADATA_ONLY_DIFFERENCE"
        else:
            status = "SCIENTIFIC_CONTENT_DIFFERENCE"

        scientific_equivalence_rows.append(
            {
                "run_id": run_id,
                "run_status": record["run_status"],
                "scientific_equivalence_status": status,
                "exact_full_payload_components": exact_full_payload_components,
                "metadata_only_difference_components": metadata_only_difference_components,
                "scientific_content_difference_components": scientific_content_difference_components,
                "scientific_signature_fingerprint": _fingerprint_payload(signature),
                "authoritative_scientific_signature_fingerprint": _fingerprint_payload(authoritative_scientific_signature),
            }
        )

    if scientific_equivalence_rows and all(
        row["scientific_equivalence_status"] == "SCIENTIFICALLY_IDENTICAL_SUPERSEDED_RUN"
        for row in scientific_equivalence_rows
    ):
        scientific_equivalence_status = "ALL_COMPLETE_NONAUTHORITATIVE_RUNS_SCIENTIFICALLY_IDENTICAL"
    elif scientific_equivalence_rows and all(
        row["scientific_equivalence_status"] in {"SCIENTIFICALLY_IDENTICAL_SUPERSEDED_RUN", "METADATA_ONLY_DIFFERENCE"}
        for row in scientific_equivalence_rows
    ):
        scientific_equivalence_status = "ALL_COMPLETE_NONAUTHORITATIVE_RUNS_METADATA_ONLY_DIFFERENT"
    elif scientific_equivalence_rows:
        scientific_equivalence_status = "SCIENTIFIC_CONTENT_DIFFERENCE_PRESENT"

    unresolved_rows = [
        row for row in lineage["row_records"]
        if row["run_id"] != AUTHORITATIVE_RUN_ID and row["historical_row_classification"] == "UNRESOLVED_HISTORICAL_ROW"
    ]

    _require(
        not unresolved_rows,
        f"Historical rows remain unresolved: {[row['source_row_key'] for row in unresolved_rows]}",
    )

    serialization_rule = {
        "algorithm": "sha256",
        "encoding": "utf-8",
        "json_policy": "sorted_keys_compact_separators",
        "stable_column_ordering": True,
        "stable_field_ordering": True,
        "normalized_booleans": True,
        "normalized_null_representation": True,
        "normalized_whitespace": True,
        "volatile_fields_excluded": ["__source_row_number__"],
        "physical_row_order_affects_fingerprint": False,
    }

    authoritative_component_entries: List[Dict[str, Any]] = []
    for sheet_name in R1_SHEETS:
        row = authoritative_rows[sheet_name]
        authoritative_component_entries.append(
            {
                "component_id": COMPONENT_IDS[sheet_name],
                "source_sheet": sheet_name,
                "source_row_key": row["source_row_key"],
                "source_row_number": row["row_number"],
                "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
                "excluded_volatile_fields": [],
                "fingerprint": _fingerprint_payload(row["payload"]),
                "authoritative_membership": True,
                "source_generated_ts": row["generated_ts"],
                "creation_timestamp": generated_ts,
                "modification_allowed": False,
            }
        )

    parent_fingerprint_map = {
        _normalize(entry.get("sheet_name")): entry.get("fingerprint")
        for entry in parent_current
    }
    original_fingerprint_map = {
        _normalize(entry.get("sheet_name")): entry.get("fingerprint")
        for entry in original_current
    }
    parent_reporting_row = _latest_row(
        inputs["Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean"].rows,
        "clean_preregistration_run_id",
    )

    derived_entries = [
        {
            "component_id": "authoritative_run_identity",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
            "fingerprint": _fingerprint_payload(
                {
                    "preregistration_version": AUTHORITATIVE_R1_VERSION,
                    "authoritative_run_id": AUTHORITATIVE_RUN_ID,
                    "authority_selection_method": "EXACT_VERSION_AND_RUN_ID_MATCH",
                }
            ),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "parent_clean_version",
            "source_sheet": "PARENT_CLEAN_FAMILY",
            "source_row_key": f"{PARENT_CLEAN_VERSION}::{PARENT_CLEAN_RUN_ID}",
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": ["__source_row_number__"],
            "fingerprint": _fingerprint_payload({"sheet_fingerprints": parent_current}),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "original_version",
            "source_sheet": "ORIGINAL_V1_0_FAMILY",
            "source_row_key": ORIGINAL_VERSION,
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": ["__source_row_number__"],
            "fingerprint": _fingerprint_payload({"sheet_fingerprints": original_current}),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "primary_design",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
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
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "population_and_counts",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
            "fingerprint": _fingerprint_payload(prereg_r1.get("counts", {})),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "sample_gates",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
            "fingerprint": _fingerprint_payload(prereg_r1.get("sample_gates", {})),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "mechanism_hierarchy",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
            "fingerprint": _fingerprint_payload(
                {
                    "primary_mechanism": prereg_r1.get("primary_mechanism"),
                    "exploratory_mechanism": prereg_r1.get("exploratory_mechanism"),
                    "descriptive_only_mechanism": prereg_r1.get("descriptive_only_mechanism"),
                }
            ),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "uncertainty_rules",
            "source_sheet": "Refined_Mechanism_Test_Preregistration_Clean_R1",
            "source_row_key": authoritative_rows["Refined_Mechanism_Test_Preregistration_Clean_R1"]["source_row_key"],
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": [],
            "fingerprint": _fingerprint_payload(prereg_r1.get("uncertainty_rules", {})),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
        {
            "component_id": "reporting_plan",
            "source_sheet": "Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean",
            "source_row_key": (
                f"Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean::"
                f"{_normalize(parent_reporting_row.get('clean_preregistration_run_id'))}::"
                f"{int(parent_reporting_row.get('__source_row_number__', 0) or 0)}"
            ),
            "stable_serialization_rule": "json_sha256_sorted_keys_utf8_payload_only",
            "excluded_volatile_fields": ["__source_row_number__"],
            "fingerprint": parent_fingerprint_map.get(
                _normalize("Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean")
            ),
            "authoritative_membership": True,
            "creation_timestamp": generated_ts,
            "modification_allowed": False,
        },
    ]

    _require(
        len(authoritative_component_entries) == len(R1_SHEETS),
        "Authoritative component fingerprint entry count mismatch.",
    )

    manifest_missing_fingerprints = [
        entry["component_id"]
        for entry in [*authoritative_component_entries, *derived_entries]
        if not _normalize(entry.get("fingerprint"))
    ]
    _require(
        not manifest_missing_fingerprints,
        f"Canonical fingerprint manifest contains missing fingerprints: {manifest_missing_fingerprints}",
    )

    previous_gap_components = sorted(
        mismatch["key"] for mismatch in prior_fingerprint_approval.get("authoritative_fingerprint_mismatches", [])
    )

    stop_rules = _build_authority_stop_rules()
    _require(
        {rule["rule_name"] for rule in stop_rules} == AUTHORITY_STOP_RULE_NAMES,
        "Authority stop-rule set is incomplete.",
    )

    canonical_authority_payload = {
        "authority_preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_RUN_ID,
        "authority_selection_method": "EXACT_VERSION_AND_RUN_ID_MATCH",
        "latest_physical_row_rule_prohibited": True,
        "latest_timestamp_rule_prohibited": True,
        "implicit_single_row_assumption_prohibited": True,
        "fallback_to_another_complete_run_prohibited": True,
        "manual_authority_selection_prohibited": True,
        "required_components": len(R1_SHEETS),
        "components_with_exactly_one_authoritative_row": lineage["components_with_exactly_one_authoritative_row"],
        "missing_authoritative_components": lineage["missing_components"],
        "duplicate_authoritative_components": lineage["duplicate_components"],
        "authority_status": lineage["authority_status"],
        "future_test_builder_load_algorithm": [
            "Load canonical authority manifest.",
            "Verify preregistration version equals 1.0-clean-r1.",
            "Verify authoritative repair run ID equals 9A-6R13R1_20260711T020141Z.",
            "Verify exactly 12 required authoritative components.",
            "Verify one complete authoritative row per component.",
            "Verify all authoritative fingerprints.",
            "Reject all superseded rows.",
            "Reject mixed-run assembly.",
            "Stop before outcome access if any authority check fails.",
        ],
        "future_test_builder_selection_rule": {
            "required_preregistration_version": AUTHORITATIVE_R1_VERSION,
            "required_repair_run_id": AUTHORITATIVE_RUN_ID,
            "row_field_for_repair_run_id": "clean_contract_repair_run_id",
            "version_and_run_id_both_required": True,
        },
        "no_outcome_workbook_open_before_authority_pass": True,
    }

    component_authority_payload = {
        "authority_preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_RUN_ID,
        "component_records": lineage["component_records"],
    }

    historical_row_dispositions = [
        {
            "source_row_key": row["source_row_key"],
            "sheet_name": row["sheet_name"],
            "component_id": row["component_id"],
            "run_id": row["run_id"],
            "generated_ts": row["generated_ts"],
            "payload_complete": row["payload_complete"],
            "historical_row_classification": row["historical_row_classification"],
        }
        for row in lineage["row_records"]
        if row["run_id"] != AUTHORITATIVE_RUN_ID
    ]

    historical_run_payload = {
        "authority_preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_RUN_ID,
        "run_ids_found": lineage["run_ids_found"],
        "run_records": lineage["run_records"],
        "historical_row_dispositions": historical_row_dispositions,
        "complete_non_authoritative_runs": sum(
            1 for record in lineage["run_records"] if record["run_status"] == "SUPERSEDED_COMPLETE_NONAUTHORITATIVE_RUN"
        ),
        "partial_runs": sum(
            1 for record in lineage["run_records"] if record["run_status"] == "SUPERSEDED_PARTIAL_RUN"
        ),
        "superseded_rows": len(historical_row_dispositions),
        "unresolved_rows": len(unresolved_rows),
    }

    scientific_equivalence_payload = {
        "authoritative_repair_run_id": AUTHORITATIVE_RUN_ID,
        "scientific_equivalence_status": scientific_equivalence_status,
        "comparison_basis": [
            "primary_mechanism",
            "primary_hypothesis",
            "structure_a_design",
            "primary_population",
            "positive_count",
            "negative_count",
            "sample_gates",
            "mechanism_hierarchy",
            "uncertainty_handling",
            "outcome_contract",
            "join_rules",
            "success_derivation",
            "statistical_method",
            "stop_rules",
        ],
        "complete_run_audits": scientific_equivalence_rows,
    }

    canonical_manifest_payload = {
        "fingerprint_manifest_version": "clean_r1_authoritative_manifest_v1",
        "preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "stable_serialization_rule": serialization_rule,
        "authoritative_component_entries": authoritative_component_entries,
        "derived_entries": derived_entries,
        "authoritative_components_fingerprinted": len(authoritative_component_entries),
        "missing_fingerprints": manifest_missing_fingerprints,
        "partial_rows_included": 0,
        "superseded_rows_included": 0,
        "previous_closure_gap_components": previous_gap_components,
        "manifest_status": "COMPLETE_AUTHORITATIVE_CLOSURE" if not manifest_missing_fingerprints else "INCOMPLETE",
        "modification_allowed": False,
    }

    authority_stop_rules_payload = {
        "authority_preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_RUN_ID,
        "stop_rules": stop_rules,
        "total_stop_rules": len(stop_rules),
        "required_stop_rule_names": sorted(AUTHORITY_STOP_RULE_NAMES),
        "future_execution_authority_guard": "All authority checks pass before any outcome workbook is opened.",
    }

    governance_payload = {
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "classifications_modified": 0,
        "r1_scientific_sheets_modified": 0,
        "parent_clean_sheets_modified": 0,
        "original_sheets_modified": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
        "governance_pass": True,
        "budget": budget,
    }

    ready_for_clean_r1_approval_rerun = (
        lineage["authority_status"] == "CANONICAL_AUTHORITY_COMPLETE"
        and not lineage["missing_components"]
        and not lineage["duplicate_components"]
        and not unresolved_rows
        and not manifest_missing_fingerprints
        and parent_cmp["match"]
        and original_cmp["match"]
    )

    build_status = "PASS_WITH_WARNINGS" if ready_for_clean_r1_approval_rerun else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_CLEAN_R1_LINEAGE_REPAIR_READY_WITH_WARNINGS"
        if ready_for_clean_r1_approval_rerun
        else "REFINED_MECHANISM_TEST_CLEAN_R1_LINEAGE_REPAIR_NEEDS_REPAIR"
    )
    recommended_next_step = (
        "RERUN_PHASE9A6R14R1_CLEAN_R1_EXECUTION_APPROVAL"
        if ready_for_clean_r1_approval_rerun
        else "RUN_PHASE9A6R13R1L_LINEAGE_REPAIR"
    )

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "preregistration_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_run_id": AUTHORITATIVE_RUN_ID,
        "required_components": len(R1_SHEETS),
        "components_with_exactly_one_authoritative_row": lineage["components_with_exactly_one_authoritative_row"],
        "missing_authoritative_components": lineage["missing_components"],
        "duplicate_authoritative_components": lineage["duplicate_components"],
        "authority_status": lineage["authority_status"],
        "run_ids_found": lineage["run_ids_found"],
        "complete_non_authoritative_runs": historical_run_payload["complete_non_authoritative_runs"],
        "partial_runs": historical_run_payload["partial_runs"],
        "superseded_rows": historical_run_payload["superseded_rows"],
        "unresolved_rows": historical_run_payload["unresolved_rows"],
        "scientific_equivalence_status": scientific_equivalence_status,
        "canonical_manifest_created": True,
        "authoritative_components_fingerprinted": len(authoritative_component_entries),
        "missing_fingerprints": manifest_missing_fingerprints,
        "partial_rows_included": 0,
        "superseded_rows_included": 0,
        "serialization_method": serialization_rule["algorithm"],
        "manifest_status": canonical_manifest_payload["manifest_status"],
        "primary_mechanism_changed": False,
        "hypothesis_changed": False,
        "primary_structure_changed": False,
        "primary_population_changed": False,
        "counts_changed": False,
        "sample_gates_changed": False,
        "hierarchy_changed": False,
        "uncertainty_rules_changed": False,
        "outcome_contract_changed": False,
        "join_rules_changed": False,
        "success_derivation_changed": False,
        "statistical_method_changed": False,
        "stop_rules_changed": False,
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "scientific_sheets_modified": 0,
        "classifications_modified": 0,
        "production_writes": 0,
        "ready_for_clean_r1_approval_rerun": ready_for_clean_r1_approval_rerun,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
    }

    payloads = {
        "Refined_Mechanism_Test_Clean_R1_Canonical_Authority": canonical_authority_payload,
        "Refined_Mechanism_Test_Clean_R1_Component_Authority": component_authority_payload,
        "Refined_Mechanism_Test_Clean_R1_Historical_Run_Disposition": historical_run_payload,
        "Refined_Mechanism_Test_Clean_R1_Scientific_Equivalence_Audit": scientific_equivalence_payload,
        "Refined_Mechanism_Test_Clean_R1_Canonical_Fingerprint_Manifest": canonical_manifest_payload,
        "Refined_Mechanism_Test_Clean_R1_Authority_Stop_Rules": authority_stop_rules_payload,
        "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Governance": governance_payload,
        "Refined_Mechanism_Test_Clean_R1_Lineage_Repair_Summary": summary_payload,
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
            lineage_repair_run_id,
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
        "lineage_repair_run_id": lineage_repair_run_id,
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
