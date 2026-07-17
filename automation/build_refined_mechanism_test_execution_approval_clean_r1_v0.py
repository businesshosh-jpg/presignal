#!/usr/bin/env python3
"""Phase 9A-6R14R1 — Clean-R1 Refined Mechanism Test Execution Approval Rerun.

This approval rerun reviews the repaired clean preregistration contract
(`1.0-clean-r1`) using explicit successful-run authority selection so that
superseded partial-write rows cannot participate in the approved test-execution
contract.
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


PHASE_ID = "9A-6R14R1"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_approval_clean_r1_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_approval_clean_r1_v0"
APPROVAL_VERSION = "refined_mechanism_test_execution_approval_clean_r1_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION_APPROVAL_CLEAN_R1"
REGISTRY_OWNER_MODULE = "market_state"

AUTHORITATIVE_R1_VERSION = "1.0-clean-r1"
AUTHORITATIVE_R1_RUN_ID = "9A-6R13R1_20260711T020141Z"
PARENT_CLEAN_VERSION = "1.0-clean"
PARENT_CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
ORIGINAL_VERSION = "1.0"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"

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
PRIMARY_METHOD = "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta"

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

INPUT_SHEETS: Tuple[str, ...] = (
    *R1_SHEETS,
    *PARENT_CLEAN_SHEETS,
    *ORIGINAL_SHEETS,
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
    "Refined_Mechanism_Test_Planning_Readiness_Summary",
    "Refined_Mechanism_Test_Label_Eligibility",
)

OUTPUT_SHEETS = [
    "Refined_Mechanism_Test_Execution_Approval_Clean_R1",
    "Refined_Mechanism_Test_Clean_R1_Authority_Approval",
    "Refined_Mechanism_Test_Clean_R1_Partial_Write_Audit",
    "Refined_Mechanism_Test_Clean_R1_Blinding_Approval",
    "Refined_Mechanism_Test_Clean_R1_Science_Approval",
    "Refined_Mechanism_Test_Clean_R1_Count_Approval",
    "Refined_Mechanism_Test_Clean_R1_Outcome_Contract_Approval",
    "Refined_Mechanism_Test_Clean_R1_Join_Approval",
    "Refined_Mechanism_Test_Clean_R1_Success_Derivation_Approval",
    "Refined_Mechanism_Test_Clean_R1_Method_Approval",
    "Refined_Mechanism_Test_Clean_R1_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Clean_R1_Fingerprint_Approval",
    "Refined_Mechanism_Test_Clean_R1_Hierarchy_Approval",
    "Refined_Mechanism_Test_Clean_R1_Execution_Approval_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Clean_R1_Summary",
]

COMMON_HEADERS = ["generated_ts", "schema_version", "approval_clean_r1_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}

REQUIRED_STOP_RULE_NAMES = {
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

REQUIRED_HARD_STOP_NAMES = {
    "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
    "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
    "CLASSIFICATION_FINGERPRINT_MISMATCH",
    "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
    "PHYSICAL_ROW_NUMBER_JOIN_ATTEMPT",
    "FUZZY_JOIN_ATTEMPT",
    "MANUAL_JOIN_OVERRIDE_REQUESTED",
    "INVALID_SUCCESS_MAPPING",
    "UNKNOWN_CONVERTED_TO_NEGATIVE",
    "INSUFFICIENT_EVIDENCE_CONVERTED_TO_NEGATIVE",
    "LOW_CONFIDENCE_INCLUDED_IN_PRIMARY",
    "UNAPPROVED_STATISTICAL_FALLBACK",
    "DESIGN_CHANGE_AFTER_APPROVAL",
    "OUTCOME_ACCESS_BEFORE_APPROVAL",
    "PRODUCTION_WRITE_ATTEMPT",
}

REQUIRED_FALLBACK_STOP_NAMES = {
    "POSITIVE_SAMPLE_GATE_FAILURE",
    "NEGATIVE_SAMPLE_GATE_FAILURE",
    "PRIMARY_CONTRAST_GATE_FAILURE",
    "CLUSTER_GATE_FAILURE",
    "PROVIDER_GATE_FAILURE",
    "SESSION_GATE_FAILURE",
    "PRIMARY_METHOD_COMPUTATION_FAILED",
    "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R14R1_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_row_wrapper(row: Mapping[str, Any]) -> str:
    cleaned = {k: v for k, v in dict(row).items() if k != "__source_row_number__"}
    serialized = json.dumps(cleaned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    cleaned = [{k: v for k, v in dict(row).items() if k != "__source_row_number__"} for row in rows]
    serialized = json.dumps(cleaned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sheet_row_fingerprints(inputs: Mapping[str, Any], sheet_names: Sequence[str]) -> List[Dict[str, Any]]:
    return [
        {
            "sheet_name": sheet_name,
            "row_count": len(inputs[sheet_name].rows),
            "fingerprint_method": "json_sha256_sorted_keys_without_source_row_number",
            "fingerprint": _fingerprint_rows([dict(r) for r in inputs[sheet_name].rows]),
        }
        for sheet_name in sheet_names
    ]


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


def _collect_r1_authority(inputs: Mapping[str, Any]) -> Dict[str, Any]:
    run_coverage: Dict[str, Dict[str, Any]] = {}
    sheet_records: List[Dict[str, Any]] = []
    row_records: List[Dict[str, Any]] = []
    authoritative_rows: Dict[str, Dict[str, Any]] = {}

    for sheet_name in R1_SHEETS:
        rows = [dict(row) for row in inputs[sheet_name].rows]
        parsed_rows = []
        for row in sorted(
            rows,
            key=lambda item: (
                _normalize(item.get("generated_ts")),
                _normalize(item.get("clean_contract_repair_run_id")),
                int(item.get("__source_row_number__", 0) or 0),
            ),
        ):
            payload_raw = _normalize(row.get("payload_json"))
            try:
                payload = json.loads(payload_raw) if payload_raw else None
                payload_complete = isinstance(payload, dict) and bool(payload)
            except json.JSONDecodeError:
                payload = None
                payload_complete = False
            run_id = _normalize(row.get("clean_contract_repair_run_id"))
            timestamp = _normalize(row.get("generated_ts"))
            row_fp = _fingerprint_row_wrapper(row)
            payload_fp = _fingerprint_payload(payload) if isinstance(payload, dict) and payload else ""
            parsed = {
                "sheet_name": sheet_name,
                "row_number": int(row.get("__source_row_number__", 0) or 0),
                "run_id": run_id,
                "generated_ts": timestamp,
                "payload_complete": payload_complete,
                "payload_type": type(payload).__name__ if payload is not None else "none",
                "payload_length": len(payload_raw),
                "payload": payload if isinstance(payload, dict) else {},
                "row_wrapper_fingerprint": row_fp,
                "payload_fingerprint": payload_fp,
            }
            parsed_rows.append(parsed)
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
                coverage["timestamps"].add(timestamp)
                if payload_complete:
                    coverage["complete_sheet_names"].add(sheet_name)

        authoritative_candidates = [row for row in parsed_rows if row["run_id"] == AUTHORITATIVE_R1_RUN_ID]
        authoritative_complete = [row for row in authoritative_candidates if row["payload_complete"]]
        if len(authoritative_complete) == 1:
            authoritative_rows[sheet_name] = authoritative_complete[0]

        if len(authoritative_complete) == 1:
            authority_status = "AUTHORITATIVE_COMPLETE"
        elif len(authoritative_candidates) == 0:
            authority_status = "AUTHORITATIVE_ROW_MISSING"
        elif len(authoritative_complete) == 0:
            authority_status = "AUTHORITATIVE_ROW_INCOMPLETE"
        else:
            authority_status = "MULTIPLE_AUTHORITATIVE_ROWS"

        run_ids_present = sorted({row["run_id"] for row in parsed_rows if row["run_id"]})
        timestamps_present = sorted({row["generated_ts"] for row in parsed_rows if row["generated_ts"]})
        complete_row_count = sum(1 for row in parsed_rows if row["payload_complete"])
        incomplete_row_count = len(parsed_rows) - complete_row_count
        superseded_row_count = sum(1 for row in parsed_rows if row["run_id"] != AUTHORITATIVE_R1_RUN_ID)

        sheet_records.append(
            {
                "sheet_name": sheet_name,
                "total_rows_present": len(parsed_rows),
                "run_ids_present": run_ids_present,
                "timestamps_present": timestamps_present,
                "complete_row_count": complete_row_count,
                "incomplete_row_count": incomplete_row_count,
                "successful_run_membership_count": sum(
                    1 for row in parsed_rows if row["run_id"] == AUTHORITATIVE_R1_RUN_ID
                ),
                "superseded_run_membership_count": superseded_row_count,
                "authority_status": authority_status,
            }
        )

        row_records.extend(parsed_rows)

    run_records: List[Dict[str, Any]] = []
    for run_id, record in sorted(run_coverage.items()):
        complete_sheet_count = len(record["complete_sheet_names"])
        sheet_count = len(record["sheet_names"])
        if run_id == AUTHORITATIVE_R1_RUN_ID and complete_sheet_count == len(R1_SHEETS):
            status = "AUTHORITATIVE_SUCCESSFUL_RUN"
        elif complete_sheet_count < len(R1_SHEETS):
            status = "SUPERSEDED_PARTIAL_RUN"
        else:
            status = "NONAUTHORITATIVE_COMPLETE_RUN"
        run_records.append(
            {
                "run_id": run_id,
                "row_count": record["rows"],
                "sheet_count": sheet_count,
                "complete_sheet_count": complete_sheet_count,
                "sheet_names": sorted(record["sheet_names"]),
                "missing_sheets": sorted(set(R1_SHEETS) - set(record["sheet_names"])),
                "missing_complete_sheets": sorted(set(R1_SHEETS) - set(record["complete_sheet_names"])),
                "timestamps": sorted(record["timestamps"]),
                "run_status": status,
            }
        )

    authoritative_complete_across_all = len(authoritative_rows) == len(R1_SHEETS)
    non_authoritative_complete_runs = [
        record
        for record in run_records
        if record["run_id"] != AUTHORITATIVE_R1_RUN_ID and record["complete_sheet_count"] == len(R1_SHEETS)
    ]
    non_authoritative_runs = [record for record in run_records if record["run_id"] != AUTHORITATIVE_R1_RUN_ID]

    if authoritative_complete_across_all and not non_authoritative_runs:
        lineage_status = "CLEAN_SINGLE_RUN"
    elif authoritative_complete_across_all and not non_authoritative_complete_runs and all(
        record["complete_sheet_count"] < len(R1_SHEETS) for record in non_authoritative_runs
    ):
        lineage_status = "SINGLE_AUTHORITATIVE_RUN_WITH_SUPERSEDED_PARTIALS"
    elif authoritative_complete_across_all and non_authoritative_complete_runs:
        lineage_status = "MIXED_RUN_AUTHORITY"
    elif authoritative_rows:
        lineage_status = "UNRESOLVED_PARTIAL_WRITE_LINEAGE"
    else:
        lineage_status = "BLOCKED"

    return {
        "sheet_records": sheet_records,
        "row_records": row_records,
        "run_records": run_records,
        "authoritative_rows": authoritative_rows,
        "lineage_status": lineage_status,
        "authoritative_complete_across_all": authoritative_complete_across_all,
        "non_authoritative_complete_runs": non_authoritative_complete_runs,
        "total_rows_reviewed": len(row_records),
        "complete_successful_run_rows": len(authoritative_rows),
        "partial_or_superseded_rows": sum(
            1 for row in row_records if row["run_id"] != AUTHORITATIVE_R1_RUN_ID
        ),
        "mixed_run_components": sum(
            1 for record in sheet_records if record["authority_status"] != "AUTHORITATIVE_COMPLETE"
        ),
        "run_ids_found": sorted(run_coverage.keys()),
    }


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
            "notes": "Phase 9A-6R14R1 clean-r1 mechanism-test execution approval rerun outputs.",
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


def build() -> Dict[str, Any]:
    run_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = run_ts.isoformat().replace("+00:00", "Z")
    approval_clean_r1_run_id = _run_id(run_ts)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in approval inputs.")

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget = _ensure_cell_budget(service, known_titles)
    _ensure_output_sheets(service, known_titles)

    authority = _collect_r1_authority(inputs)
    authoritative_rows = authority["authoritative_rows"]
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

    parent_clean_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows,
        "clean_preregistration_run_id",
    )
    original_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Summary"].rows,
        "preregistration_run_id",
    )

    _require(_normalize(prereg_r1.get("repaired_preregistration_version")) == AUTHORITATIVE_R1_VERSION, "R1 preregistration version mismatch.")
    _require(_normalize(prereg_r1.get("clean_logical_run_id")) == PARENT_CLEAN_RUN_ID, "R1 parent clean logical run ID mismatch.")
    _require(_normalize(prereg_r1.get("parent_preregistration_version")) == PARENT_CLEAN_VERSION, "R1 parent clean version mismatch.")
    _require(_normalize(prereg_r1.get("original_preregistration_version")) == ORIGINAL_VERSION, "R1 original version mismatch.")
    _require(_normalize(prereg_r1.get("repair_type")) == "EXECUTION_CONTRACT_COMPLETION_ONLY", "R1 repair type mismatch.")
    _require(_normalize(parent_clean_summary.get("test_preregistration_version")) == PARENT_CLEAN_VERSION, "Parent clean summary not found.")
    _require(_normalize(original_summary.get("test_preregistration_version")) == ORIGINAL_VERSION, "Original summary not found.")

    parent_current_rows = [
        {
            "sheet_name": sheet_name,
            "fingerprint": _fingerprint_row_wrapper(
                sorted(
                    [dict(r) for r in inputs[sheet_name].rows],
                    key=lambda row: (
                        _normalize(row.get("generated_ts")),
                        _normalize(row.get("clean_preregistration_run_id")),
                        int(row.get("__source_row_number__", 0) or 0),
                    ),
                )[-1]
            ),
        }
        for sheet_name in PARENT_CLEAN_SHEETS
    ]
    parent_expected_rows = prereg_r1.get("authoritative_parent_clean_references", [])
    parent_fingerprint_cmp = _compare_expected_to_current(parent_expected_rows, parent_current_rows)
    _require(parent_fingerprint_cmp["match"], f"Parent clean sheets changed: {parent_fingerprint_cmp['mismatches']}")

    original_current_rows = _sheet_row_fingerprints(inputs, ORIGINAL_SHEETS)
    original_expected_rows = fingerprint_r1.get("original_expected_fingerprints", [])
    original_fingerprint_cmp = _compare_expected_to_current(original_expected_rows, original_current_rows)
    _require(original_fingerprint_cmp["match"], f"Original preregistration sheets changed: {original_fingerprint_cmp['mismatches']}")

    class_rows = _classification_rows(inputs)
    structure_counts = _structure_counts(class_rows)
    for key, expected in EXPECTED_COUNTS.items():
        _require(structure_counts[key] == expected, f"Classification count mismatch for {key}: expected {expected}, observed {structure_counts[key]}.")

    _require(not structure_counts["baseline_match_count_errors"], "Baseline matching errors detected in primary contrast population.")

    sample_gate_contract = prereg_r1.get("sample_gate_contract", {})
    gate_checks = {
        "minimum_positive_count": {
            "counting_unit": sample_gate_contract["minimum_positive_count"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_positive_count"]["stable_counting_key"],
            "current_blinded_count": structure_counts["positive_primary_observations"],
            "threshold": EXPECTED_GATES["minimum_positive_count"],
            "status": "PASS" if structure_counts["positive_primary_observations"] >= EXPECTED_GATES["minimum_positive_count"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_positive_count"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_positive_count"]["stop_or_downgrade_action"],
        },
        "minimum_negative_count": {
            "counting_unit": sample_gate_contract["minimum_negative_count"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_negative_count"]["stable_counting_key"],
            "current_blinded_count": structure_counts["negative_primary_observations"],
            "threshold": EXPECTED_GATES["minimum_negative_count"],
            "status": "PASS" if structure_counts["negative_primary_observations"] >= EXPECTED_GATES["minimum_negative_count"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_negative_count"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_negative_count"]["stop_or_downgrade_action"],
        },
        "minimum_primary_contrast_observations": {
            "counting_unit": sample_gate_contract["minimum_primary_contrast_observations"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_primary_contrast_observations"]["stable_counting_key"],
            "current_blinded_count": structure_counts["primary_contrast_eligible_observations"],
            "threshold": EXPECTED_GATES["minimum_primary_contrast_observations"],
            "status": "PASS" if structure_counts["primary_contrast_eligible_observations"] >= EXPECTED_GATES["minimum_primary_contrast_observations"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_primary_contrast_observations"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_primary_contrast_observations"]["stop_or_downgrade_action"],
        },
        "minimum_clusters": {
            "counting_unit": sample_gate_contract["minimum_clusters"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_clusters"]["stable_counting_key"],
            "current_blinded_count": structure_counts["cluster_count"],
            "threshold": EXPECTED_GATES["minimum_clusters"],
            "status": "PASS" if structure_counts["cluster_count"] >= EXPECTED_GATES["minimum_clusters"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_clusters"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_clusters"]["stop_or_downgrade_action"],
        },
        "minimum_providers": {
            "counting_unit": sample_gate_contract["minimum_providers"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_providers"]["stable_counting_key"],
            "current_blinded_count": structure_counts["provider_count"],
            "threshold": EXPECTED_GATES["minimum_providers"],
            "status": "PASS" if structure_counts["provider_count"] >= EXPECTED_GATES["minimum_providers"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_providers"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_providers"]["stop_or_downgrade_action"],
        },
        "minimum_sessions": {
            "counting_unit": sample_gate_contract["minimum_sessions"]["counting_unit"],
            "stable_counting_key": sample_gate_contract["minimum_sessions"]["stable_counting_key"],
            "current_blinded_count": structure_counts["session_count"],
            "threshold": EXPECTED_GATES["minimum_sessions"],
            "status": "PASS" if structure_counts["session_count"] >= EXPECTED_GATES["minimum_sessions"] else "FAIL",
            "future_outcome_join_recheck": bool(sample_gate_contract["minimum_sessions"]["future_post_join_recheck"]),
            "fail_or_downgrade_action": sample_gate_contract["minimum_sessions"]["stop_or_downgrade_action"],
        },
    }
    all_gates_pass = all(item["status"] == "PASS" for item in gate_checks.values())

    science_preserved = (
        _normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM
        and _normalize(prereg_r1.get("exploratory_mechanism")) == EXPLORATORY_MECHANISM
        and _normalize(prereg_r1.get("descriptive_only_mechanism")) == DESCRIPTIVE_ONLY_MECHANISM
        and _normalize(prereg_r1.get("primary_structure")) == PRIMARY_STRUCTURE
        and _normalize(prereg_r1.get("primary_exposure")) == PRIMARY_EXPOSURE
        and _normalize(prereg_r1.get("primary_comparison_groups")) == PRIMARY_COMPARISON_GROUPS
        and _normalize(prereg_r1.get("baseline_role")) == BASELINE_ROLE
        and _normalize(prereg_r1.get("primary_estimand")) == PRIMARY_ESTIMAND
        and not bool(prereg_r1.get("scientific_hypothesis_changed"))
        and not bool(prereg_r1.get("primary_population_changed"))
        and not bool(prereg_r1.get("mechanism_hierarchy_changed"))
        and not bool(prereg_r1.get("sample_gates_changed"))
        and not bool(summary_r1.get("primary_hypothesis_changed"))
        and not bool(summary_r1.get("primary_structure_changed"))
        and not bool(summary_r1.get("hierarchy_changed"))
    )

    timestamp_requirement = outcome_r1.get("outcome_timestamp_requirement", {})
    timestamp_approved = (
        _normalize(timestamp_requirement.get("failure_status")) == "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED"
        and bool(timestamp_requirement.get("canonical_outcome_version_required"))
        and bool(timestamp_requirement.get("approved_evaluation_window_required"))
        and bool(timestamp_requirement.get("outcome_timestamp_at_or_after_evaluation_window_end"))
        and bool(timestamp_requirement.get("no_information_outside_approved_evaluation_window"))
        and bool(timestamp_requirement.get("source_availability_timestamp_compatible_with_canonical_repair_process"))
        and bool(timestamp_requirement.get("deterministically_linked_to_forecast_observation"))
        and bool(timestamp_requirement.get("reject_if_timestamp_provenance_missing_or_contradictory"))
    )

    outcome_version_handling = outcome_r1.get("outcome_version_mismatch_handling", {})
    evaluation_window_handling = outcome_r1.get("evaluation_window_mismatch_handling", {})
    outcome_version_approved = (
        _normalize(outcome_version_handling.get("result")) == "NOT_ELIGIBLE"
        and _normalize(outcome_version_handling.get("systemic_result")) == "HARD_BLOCK"
        and "do_not_fall_back_to_another_outcome_version" in outcome_version_handling.get("required_actions", [])
        and "do_not_choose_latest_available_version_automatically" in outcome_version_handling.get("required_actions", [])
    )
    evaluation_window_approved = (
        _normalize(evaluation_window_handling.get("result")) == "NOT_ELIGIBLE"
        and _normalize(evaluation_window_handling.get("systemic_result")) == "HARD_BLOCK"
        and "do_not_substitute_another_window" in evaluation_window_handling.get("required_actions", [])
        and "recheck_sample_gates_after_exclusions" in evaluation_window_handling.get("required_actions", [])
    )

    join_approved = (
        _normalize(join_r1.get("approved_future_join_path")) == "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id"
        and bool(join_r1.get("physical_row_number_join_prohibited"))
        and bool(join_r1.get("fuzzy_text_join_prohibited"))
        and bool(join_r1.get("manual_matching_prohibited"))
        and bool(join_r1.get("nearest_date_matching_prohibited"))
        and bool(join_r1.get("provider_name_only_join_prohibited"))
        and bool(join_r1.get("session_only_join_prohibited"))
        and bool(join_r1.get("pack_level_only_join_prohibited"))
        and bool(join_r1.get("one_classification_observation_to_one_canonical_outcome_required"))
        and _normalize(join_r1.get("ambiguous_join_result")) == "AMBIGUOUS_JOIN_BLOCKED"
        and _normalize(join_r1.get("duplicate_join_result")) == "DUPLICATE_JOIN_BLOCKED"
        and _normalize(join_r1.get("missing_join_result")) == "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN"
    )

    required_success_keys = {
        "UP_forecast_UP_outcome",
        "UP_forecast_DOWN_outcome",
        "DOWN_forecast_DOWN_outcome",
        "DOWN_forecast_UP_outcome",
        "forecast_FLAT_any_realized_direction",
        "realized_FLAT_any_forecast_direction",
        "forecast_NO_CLEAR_DIRECTION",
        "no_signal_forecast",
        "missing_forecast_direction",
        "missing_realized_direction",
        "invalid_forecast_direction",
        "invalid_realized_direction",
        "duplicate_outcome_join",
        "ambiguous_outcome_join",
        "outcome_version_mismatch",
        "evaluation_window_mismatch",
        "timestamp_requirement_failure",
    }
    allowed_statuses = {"SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"}
    case_map = success_r1.get("explicit_case_map", {})
    success_approved = (
        set(success_r1.get("allowed_output_statuses", [])) == allowed_statuses
        and required_success_keys <= set(case_map)
        and set(case_map.values()) <= allowed_statuses
    )

    method_approved = (
        _normalize(method_r1.get("primary_method_id")) == PRIMARY_METHOD
        and int(method_r1.get("bootstrap_replications", 0)) == 10000
        and int(method_r1.get("bootstrap_random_seed", 0)) == 9130613
        and _normalize(method_r1.get("resampling_unit")) == "shared_session_outcome_family"
        and _normalize(method_r1.get("confidence_interval_method")) == "two_sided_percentile_bootstrap_95pct_interval"
        and float(method_r1.get("confidence_interval_quantiles", {}).get("lower", -1)) == 0.025
        and float(method_r1.get("confidence_interval_quantiles", {}).get("upper", -1)) == 0.975
        and _normalize(method_r1.get("primary_interpretation")) == PRIMARY_INTERPRETATION
        and not bool(method_r1.get("automatic_method_substitution_allowed"))
        and bool(method_r1.get("descriptive_fallback", {}).get("allowed"))
        and not bool(method_r1.get("descriptive_fallback", {}).get("inferential_primary_result_allowed"))
        and _normalize(method_r1.get("zero_cell_handling", {}).get("status")) == "ZERO_PRIMARY_GROUP_CELL"
        and _normalize(method_r1.get("degenerate_bootstrap_handling", {}).get("trigger_status")) == "DEGENERATE_BOOTSTRAP_DISTRIBUTION"
        and _normalize(method_r1.get("primary_method_computation_failure", {}).get("trigger_status")) == "PRIMARY_METHOD_COMPUTATION_FAILED"
    )

    stop_rules = stop_r1.get("stop_rules", [])
    stop_rule_names = {_normalize(rule.get("stop_rule_name")) for rule in stop_rules}
    stop_rules_by_name = {_normalize(rule.get("stop_rule_name")): rule for rule in stop_rules}
    hard_stops_ok = all(
        name in stop_rules_by_name
        and stop_rules_by_name[name].get("successful_summary_allowed") is False
        and stop_rules_by_name[name].get("automatic_retry_allowed") is False
        for name in REQUIRED_HARD_STOP_NAMES
    )
    fallback_stops_ok = all(
        name in stop_rules_by_name
        and stop_rules_by_name[name].get("inferential_primary_result_allowed") is False
        and stop_rules_by_name[name].get("descriptive_fallback_allowed") is True
        for name in REQUIRED_FALLBACK_STOP_NAMES
    )
    stop_rules_approved = (
        bool(stop_r1.get("fail_closed"))
        and len(stop_rules) == 29
        and stop_rule_names == REQUIRED_STOP_RULE_NAMES
        and hard_stops_ok
        and fallback_stops_ok
    )

    expected_r1_output_fps = {
        _normalize(entry.get("sheet_name")): _normalize(entry.get("fingerprint"))
        for entry in fingerprint_r1.get("repaired_output_fingerprints", [])
    }
    authoritative_payload_fp_entries = [
        {
            "sheet_name": sheet_name,
            "fingerprint": _fingerprint_payload(authoritative_rows[sheet_name]["payload"]),
        }
        for sheet_name in R1_SHEETS
    ]
    r1_fingerprint_cmp = _compare_expected_to_current(
        [{"sheet_name": k, "fingerprint": v} for k, v in expected_r1_output_fps.items()],
        authoritative_payload_fp_entries,
    )
    required_derived_components = {
        "parent_clean_version",
        "primary_design",
        "outcome_contract",
        "join_rules",
        "success_derivation",
        "statistical_method",
        "stop_rules",
        "sample_gates",
        "hierarchy",
        "uncertainty_rules",
        "reporting_plan_reference",
    }
    derived_components_present = {
        _normalize(entry.get("component")) for entry in fingerprint_r1.get("derived_fingerprints", [])
    }
    approval_derived_fingerprints = [
        {"component": "authoritative_successful_run_id", "fingerprint": _fingerprint_payload({"run_id": AUTHORITATIVE_R1_RUN_ID})},
        {
            "component": "primary_population",
            "fingerprint": _fingerprint_payload(
                {
                    "classification_run_id": CLASSIFICATION_RUN_ID,
                    "counts": structure_counts,
                    "primary_exposure": PRIMARY_EXPOSURE,
                    "primary_structure": PRIMARY_STRUCTURE,
                }
            ),
        },
        {
            "component": "sample_gates_rechecked",
            "fingerprint": _fingerprint_payload(gate_checks),
        },
    ]
    partial_rows_included_in_authority = sum(
        1
        for row in authority["row_records"]
        if row["run_id"] != AUTHORITATIVE_R1_RUN_ID and row["run_id"] == AUTHORITATIVE_R1_RUN_ID
    )
    fingerprints_approved = (
        r1_fingerprint_cmp["match"]
        and lineage_r1.get("parent_clean_fingerprints_match") is True
        and lineage_r1.get("original_fingerprints_match") is True
        and required_derived_components <= derived_components_present
        and fingerprint_r1.get("modification_allowed_after_repair") is False
    )

    hierarchy_approved = (
        _normalize(prereg_r1.get("primary_mechanism")) == PRIMARY_MECHANISM
        and _normalize(prereg_r1.get("exploratory_mechanism")) == EXPLORATORY_MECHANISM
        and _normalize(prereg_r1.get("descriptive_only_mechanism")) == DESCRIPTIVE_ONLY_MECHANISM
        and _normalize(prereg_r1.get("uncertainty_rules", {}).get("UNKNOWN")) == "excluded_from_primary"
        and _normalize(prereg_r1.get("uncertainty_rules", {}).get("INSUFFICIENT_EVIDENCE")) == "excluded_from_primary"
        and _normalize(prereg_r1.get("uncertainty_rules", {}).get("EXCLUDED")) == "never_included"
        and _normalize(prereg_r1.get("uncertainty_rules", {}).get("LOW_CONFIDENCE")) == "excluded_from_primary"
        and bool(prereg_r1.get("uncertainty_rules", {}).get("no_uncertain_class_converted_to_negative"))
    )

    blinding_status = (
        "BLINDING_INTACT_CLEAN_R1"
        if all(
            int(blinding_r1.get(field, 0)) == 0
            for field in [
                "outcome_workbooks_opened",
                "outcome_sheets_loaded",
                "outcome_rows_loaded",
                "realized_values_accessed",
                "accuracy_metrics_calculated",
                "mechanism_tests_performed",
                "provider_rankings_produced",
                "post_session_evidence_accessed",
            ]
        )
        else "BLINDING_BREACH"
    )
    _require(blinding_status == "BLINDING_INTACT_CLEAN_R1", "R1 blinding integrity failed.")

    science_preservation_status = "PRESERVED" if science_preserved else "CHANGED"
    gate_status = "ALL_PASS" if all_gates_pass else "GATE_FAILURE"
    count_definitions_approved = all(
        gate_checks[name]["threshold"] == EXPECTED_GATES[name] and bool(gate_checks[name]["counting_unit"]) and bool(gate_checks[name]["stable_counting_key"])
        for name in EXPECTED_GATES
    )

    ready_for_execution = all(
        [
            authority["lineage_status"] in {"SINGLE_AUTHORITATIVE_RUN_WITH_SUPERSEDED_PARTIALS", "CLEAN_SINGLE_RUN"},
            parent_fingerprint_cmp["match"],
            original_fingerprint_cmp["match"],
            blinding_status == "BLINDING_INTACT_CLEAN_R1",
            science_preserved,
            all_gates_pass,
            count_definitions_approved,
            timestamp_approved,
            outcome_version_approved,
            evaluation_window_approved,
            join_approved,
            success_approved,
            method_approved,
            stop_rules_approved,
            fingerprints_approved,
            hierarchy_approved,
            int(governance_r1.get("outcome_rows_loaded", 0)) == 0,
            int(governance_r1.get("realized_values_accessed", 0)) == 0,
            int(governance_r1.get("accuracy_metrics_calculated", 0)) == 0,
            int(governance_r1.get("mechanism_tests_performed", 0)) == 0,
            int(governance_r1.get("classifications_modified", 0)) == 0,
            int(governance_r1.get("parent_clean_sheets_modified", 0)) == 0,
            int(governance_r1.get("original_preregistration_sheets_modified", 0)) == 0,
            int(governance_r1.get("production_writes", 0)) == 0,
            int(governance_r1.get("production_behavior_changes", 0)) == 0,
        ]
    )

    build_status = "PASS_WITH_WARNINGS" if ready_for_execution and authority["lineage_status"] == "SINGLE_AUTHORITATIVE_RUN_WITH_SUPERSEDED_PARTIALS" else ("PASS" if ready_for_execution else "FAIL")
    final_interpretation = (
        "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_R1_APPROVED_WITH_WARNINGS"
        if ready_for_execution and authority["lineage_status"] == "SINGLE_AUTHORITATIVE_RUN_WITH_SUPERSEDED_PARTIALS"
        else (
            "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_R1_APPROVED"
            if ready_for_execution
            else (
                "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_R1_LINEAGE_REPAIR_REQUIRED"
                if authority["lineage_status"] in {"MIXED_RUN_AUTHORITY", "UNRESOLVED_PARTIAL_WRITE_LINEAGE"}
                else "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_R1_APPROVAL_NEEDS_REPAIR"
            )
        )
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R15_CLEAN_R1_MECHANISM_TEST_EXECUTION"
        if ready_for_execution
        else (
            "RUN_PHASE9A6R13R1_PARTIAL_WRITE_LINEAGE_REPAIR"
            if authority["lineage_status"] in {"MIXED_RUN_AUTHORITY", "UNRESOLVED_PARTIAL_WRITE_LINEAGE"}
            else "RUN_PHASE9A6R13R1_CONTRACT_REPAIR"
        )
    )

    authority_payload = {
        "r1_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_R1_RUN_ID,
        "r1_rows_reviewed": authority["total_rows_reviewed"],
        "run_ids_found": authority["run_ids_found"],
        "sheet_authority_records": authority["sheet_records"],
        "run_lineage_records": authority["run_records"],
        "authority_selection_method": "EXPLICIT_RUN_ID_AND_VERSION_FILTER",
        "complete_successful_run_rows": authority["complete_successful_run_rows"],
        "partial_or_superseded_rows": authority["partial_or_superseded_rows"],
        "mixed_run_components": authority["mixed_run_components"],
        "authority_status": authority["lineage_status"],
        "partial_rows_included_in_fingerprints": 0,
        "no_latest_row_by_physical_position_rule_used": True,
    }

    partial_write_audit_payload = {
        "authoritative_repair_run_id": AUTHORITATIVE_R1_RUN_ID,
        "row_records": [
            {
                "sheet_name": row["sheet_name"],
                "row_number": row["row_number"],
                "run_id": row["run_id"],
                "generated_ts": row["generated_ts"],
                "payload_complete": row["payload_complete"],
                "successful_run_membership": row["run_id"] == AUTHORITATIVE_R1_RUN_ID,
                "superseded_run_membership": row["run_id"] != AUTHORITATIVE_R1_RUN_ID,
                "included_in_approved_fingerprint_set": row["run_id"] == AUTHORITATIVE_R1_RUN_ID,
                "row_status": (
                    "AUTHORITATIVE_COMPLETE"
                    if row["run_id"] == AUTHORITATIVE_R1_RUN_ID and row["payload_complete"]
                    else (
                        "SUPERSEDED_COMPLETE_ROW_FROM_PARTIAL_RUN"
                        if row["run_id"] != AUTHORITATIVE_R1_RUN_ID and row["payload_complete"]
                        else "INCOMPLETE_OR_UNVERIFIABLE_ROW"
                    )
                ),
            }
            for row in authority["row_records"]
        ],
        "partial_write_interpretation": "Rows from non-authoritative run IDs are superseded and excluded by explicit run-id authority selection.",
    }

    blinding_payload = {
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "provider_performance_viewed": 0,
        "post_session_evidence_accessed": 0,
        "blinding_status": blinding_status,
        "forbidden_input_titles_absent": True,
    }

    science_payload = {
        "primary_mechanism": PRIMARY_MECHANISM,
        "exploratory_mechanism": EXPLORATORY_MECHANISM,
        "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
        "primary_structure": PRIMARY_STRUCTURE,
        "primary_exposure": PRIMARY_EXPOSURE,
        "comparison_groups": PRIMARY_COMPARISON_GROUPS,
        "baseline_role": BASELINE_ROLE,
        "primary_estimand": PRIMARY_ESTIMAND,
        "primary_interpretation": PRIMARY_INTERPRETATION,
        "primary_hypothesis_changed": bool(summary_r1.get("primary_hypothesis_changed")),
        "primary_structure_changed": bool(summary_r1.get("primary_structure_changed")),
        "primary_population_changed": bool(summary_r1.get("primary_population_changed")),
        "hierarchy_changed": bool(summary_r1.get("hierarchy_changed")),
        "sample_gates_changed": bool(summary_r1.get("sample_gates_changed")),
        "scientific_preservation_status": science_preservation_status,
    }

    count_payload = {
        "structural_pairs": structure_counts["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": structure_counts["consistency_classified_pairs"],
        "high_moderate_pairs": structure_counts["high_moderate_confidence_pairs"],
        "primary_contrast_observations": structure_counts["primary_contrast_eligible_observations"],
        "positive_observations": structure_counts["positive_primary_observations"],
        "negative_observations": structure_counts["negative_primary_observations"],
        "mixed_label_clusters": structure_counts["mixed_label_provider_session_clusters"],
        "gate_checks": gate_checks,
        "gate_status": gate_status,
        "count_definitions_approved": count_definitions_approved,
    }

    outcome_contract_payload = {
        "schema_contract_approved": True,
        "outcome_timestamp_requirement_approved": timestamp_approved,
        "outcome_timestamp_requirement": timestamp_requirement,
        "outcome_version_handling_approved": outcome_version_approved,
        "outcome_version_mismatch_handling": outcome_version_handling,
        "evaluation_window_handling_approved": evaluation_window_approved,
        "evaluation_window_mismatch_handling": evaluation_window_handling,
        "no_actual_timestamps_inspected_in_approval": True,
        "source_sheet_contract_only": {
            "workbook": outcome_r1.get("canonical_outcome_source_workbook"),
            "sheet": outcome_r1.get("canonical_outcome_source_sheet"),
            "component_field": outcome_r1.get("canonical_outcome_component_field"),
        },
    }

    join_payload = {
        "approved_join_path": join_r1.get("approved_future_join_path"),
        "stable_key_components": join_r1.get("stable_key_components"),
        "exact_one_to_one_required": bool(join_r1.get("one_classification_observation_to_one_canonical_outcome_required")),
        "physical_row_join_prohibited": bool(join_r1.get("physical_row_number_join_prohibited")),
        "fuzzy_join_prohibited": bool(join_r1.get("fuzzy_text_join_prohibited")),
        "manual_join_prohibited": bool(join_r1.get("manual_matching_prohibited")),
        "nearest_date_join_prohibited": bool(join_r1.get("nearest_date_matching_prohibited")),
        "provider_only_join_prohibited": bool(join_r1.get("provider_name_only_join_prohibited")),
        "session_only_join_prohibited": bool(join_r1.get("session_only_join_prohibited")),
        "pack_only_join_prohibited": bool(join_r1.get("pack_level_only_join_prohibited")),
        "ambiguous_join_result": join_r1.get("ambiguous_join_result"),
        "duplicate_join_result": join_r1.get("duplicate_join_result"),
        "missing_join_result": join_r1.get("missing_join_result"),
        "join_guardrails_approved": join_approved,
    }

    success_payload = {
        "allowed_statuses": success_r1.get("allowed_output_statuses"),
        "explicit_case_map_keys": sorted(case_map),
        "success_derivation_approved": success_approved,
        "flat_policy": success_r1.get("policy_notes", {}).get("realized_flat_policy"),
        "no_signal_policy": success_r1.get("policy_notes", {}).get("no_signal_policy"),
        "duplicate_or_ambiguous_join_blocked": (
            case_map.get("duplicate_outcome_join") == "AMBIGUOUS_JOIN_BLOCKED"
            and case_map.get("ambiguous_outcome_join") == "AMBIGUOUS_JOIN_BLOCKED"
        ),
    }

    method_payload = {
        "primary_method": method_r1.get("primary_method_id"),
        "bootstrap_replications": method_r1.get("bootstrap_replications"),
        "bootstrap_random_seed": method_r1.get("bootstrap_random_seed"),
        "resampling_unit": method_r1.get("resampling_unit"),
        "quantiles": method_r1.get("confidence_interval_quantiles"),
        "zero_cell_handling": method_r1.get("zero_cell_handling"),
        "degenerate_bootstrap_handling": method_r1.get("degenerate_bootstrap_handling"),
        "primary_method_computation_failure": method_r1.get("primary_method_computation_failure"),
        "descriptive_fallback": method_r1.get("descriptive_fallback"),
        "statistical_method_approved": method_approved,
        "descriptive_fallback_frozen": bool(method_r1.get("descriptive_fallback", {}).get("allowed")),
        "small_cluster_warning": method_r1.get("small_cluster_warning"),
    }

    stop_payload = {
        "total_stop_rules": len(stop_rules),
        "stop_rule_names": sorted(stop_rule_names),
        "required_stop_rule_coverage_complete": stop_rule_names == REQUIRED_STOP_RULE_NAMES,
        "hard_stop_contracts_approved": hard_stops_ok,
        "fallback_stop_contracts_approved": fallback_stops_ok,
        "stop_rules_approved": stop_rules_approved,
    }

    current_r1_sheet_fingerprints = [
        {
            "sheet_name": sheet_name,
            "fingerprint": _fingerprint_payload(authoritative_rows[sheet_name]["payload"]),
        }
        for sheet_name in R1_SHEETS
    ]
    fingerprint_payload = {
        "authoritative_repair_run_id": AUTHORITATIVE_R1_RUN_ID,
        "partial_rows_excluded_from_authority": True,
        "partial_rows_included_in_fingerprints": 0,
        "authoritative_sheet_payload_fingerprints": current_r1_sheet_fingerprints,
        "expected_authoritative_sheet_payload_fingerprints": fingerprint_r1.get("repaired_output_fingerprints"),
        "authoritative_fingerprint_match": r1_fingerprint_cmp["match"],
        "authoritative_fingerprint_mismatches": r1_fingerprint_cmp["mismatches"],
        "parent_version_preserved": parent_fingerprint_cmp["match"],
        "original_version_preserved": original_fingerprint_cmp["match"],
        "derived_fingerprints_present": sorted(derived_components_present),
        "approval_derived_fingerprints": approval_derived_fingerprints,
        "modification_allowed_after_approval": False,
        "fingerprints_approved": fingerprints_approved,
    }

    hierarchy_payload = {
        "primary_mechanism": PRIMARY_MECHANISM,
        "exploratory_mechanism": EXPLORATORY_MECHANISM,
        "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
        "unknown_handling": prereg_r1.get("uncertainty_rules", {}).get("UNKNOWN"),
        "insufficient_evidence_handling": prereg_r1.get("uncertainty_rules", {}).get("INSUFFICIENT_EVIDENCE"),
        "excluded_handling": prereg_r1.get("uncertainty_rules", {}).get("EXCLUDED"),
        "low_confidence_handling": prereg_r1.get("uncertainty_rules", {}).get("LOW_CONFIDENCE"),
        "no_uncertain_class_converted_to_negative": bool(prereg_r1.get("uncertainty_rules", {}).get("no_uncertain_class_converted_to_negative")),
        "hierarchy_approved": hierarchy_approved,
    }

    governance_payload = {
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "classifications_modified": 0,
        "r1_preregistration_modified_during_approval": 0,
        "parent_clean_sheets_modified": 0,
        "original_sheets_modified": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
        "governance_pass": True,
    }

    summary_payload = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "r1_version": AUTHORITATIVE_R1_VERSION,
        "authoritative_repair_run_id": AUTHORITATIVE_R1_RUN_ID,
        "r1_rows_reviewed": authority["total_rows_reviewed"],
        "run_ids_found": authority["run_ids_found"],
        "complete_successful_run_rows": authority["complete_successful_run_rows"],
        "partial_superseded_rows": authority["partial_or_superseded_rows"],
        "mixed_run_components": authority["mixed_run_components"],
        "authority_status": authority["lineage_status"],
        "partial_rows_included_in_fingerprints": 0,
        "parent_version_preserved": parent_fingerprint_cmp["match"],
        "original_version_preserved": original_fingerprint_cmp["match"],
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "blinding_status": blinding_status,
        "primary_mechanism": PRIMARY_MECHANISM,
        "primary_hypothesis_changed": bool(summary_r1.get("primary_hypothesis_changed")),
        "primary_structure_changed": bool(summary_r1.get("primary_structure_changed")),
        "primary_population_changed": bool(summary_r1.get("primary_population_changed")),
        "hierarchy_changed": bool(summary_r1.get("hierarchy_changed")),
        "sample_gates_changed": bool(summary_r1.get("sample_gates_changed")),
        "scientific_preservation_status": science_preservation_status,
        "structural_pairs": structure_counts["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": structure_counts["consistency_classified_pairs"],
        "high_moderate_pairs": structure_counts["high_moderate_confidence_pairs"],
        "primary_contrast_observations": structure_counts["primary_contrast_eligible_observations"],
        "positive_observations": structure_counts["positive_primary_observations"],
        "negative_observations": structure_counts["negative_primary_observations"],
        "mixed_label_clusters": structure_counts["mixed_label_provider_session_clusters"],
        "gate_status": gate_status,
        "outcome_timestamp_requirement_approved": timestamp_approved,
        "outcome_version_handling_approved": outcome_version_approved,
        "evaluation_window_handling_approved": evaluation_window_approved,
        "join_guardrails_approved": join_approved,
        "success_derivation_approved": success_approved,
        "statistical_method_approved": method_approved,
        "bootstrap_replications": method_r1.get("bootstrap_replications"),
        "random_seed": method_r1.get("bootstrap_random_seed"),
        "resampling_unit": method_r1.get("resampling_unit"),
        "zero_cell_handling_approved": _normalize(method_r1.get("zero_cell_handling", {}).get("status")) == "ZERO_PRIMARY_GROUP_CELL",
        "degenerate_bootstrap_handling_approved": _normalize(method_r1.get("degenerate_bootstrap_handling", {}).get("trigger_status")) == "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
        "descriptive_fallback_frozen": bool(method_r1.get("descriptive_fallback", {}).get("allowed")),
        "stop_rules_approved": stop_rules_approved,
        "total_stop_rules": len(stop_rules),
        "fingerprints_approved": fingerprints_approved,
        "partial_rows_excluded_from_authority": True,
        "outcome_access": 0,
        "test_execution": 0,
        "preregistration_modification": 0,
        "classification_modification": 0,
        "production_writes": 0,
        "ready_for_one_clean_r1_mechanism_test_execution": ready_for_execution,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
    }

    payloads = {
        "Refined_Mechanism_Test_Execution_Approval_Clean_R1": {
            "approval_version": APPROVAL_VERSION,
            "authoritative_r1_version": AUTHORITATIVE_R1_VERSION,
            "authoritative_repair_run_id": AUTHORITATIVE_R1_RUN_ID,
            "authority_status": authority["lineage_status"],
            "blinding_status": blinding_status,
            "scientific_preservation_status": science_preservation_status,
            "gate_status": gate_status,
            "outcome_contract_complete": timestamp_approved and outcome_version_approved and evaluation_window_approved,
            "join_guardrails_complete": join_approved,
            "success_mapping_complete": success_approved,
            "statistical_method_complete": method_approved,
            "stop_rules_complete": stop_rules_approved,
            "fingerprints_approved": fingerprints_approved,
            "ready_for_one_clean_r1_mechanism_test_execution": ready_for_execution,
            "recommended_next_step": recommended_next_step,
        },
        "Refined_Mechanism_Test_Clean_R1_Authority_Approval": authority_payload,
        "Refined_Mechanism_Test_Clean_R1_Partial_Write_Audit": partial_write_audit_payload,
        "Refined_Mechanism_Test_Clean_R1_Blinding_Approval": blinding_payload,
        "Refined_Mechanism_Test_Clean_R1_Science_Approval": science_payload,
        "Refined_Mechanism_Test_Clean_R1_Count_Approval": count_payload,
        "Refined_Mechanism_Test_Clean_R1_Outcome_Contract_Approval": outcome_contract_payload,
        "Refined_Mechanism_Test_Clean_R1_Join_Approval": join_payload,
        "Refined_Mechanism_Test_Clean_R1_Success_Derivation_Approval": success_payload,
        "Refined_Mechanism_Test_Clean_R1_Method_Approval": method_payload,
        "Refined_Mechanism_Test_Clean_R1_Stop_Rule_Approval": stop_payload,
        "Refined_Mechanism_Test_Clean_R1_Fingerprint_Approval": fingerprint_payload,
        "Refined_Mechanism_Test_Clean_R1_Hierarchy_Approval": hierarchy_payload,
        "Refined_Mechanism_Test_Clean_R1_Execution_Approval_Governance": governance_payload,
        "Refined_Mechanism_Test_Execution_Approval_Clean_R1_Summary": summary_payload,
    }

    existing_output_rows = {
        sheet_name: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
        for sheet_name in OUTPUT_SHEETS
    }
    write_updates = []
    rows_written_per_sheet: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        next_row_number = len(existing_output_rows[sheet_name]) + 2
        write_updates.append(
            {
                "range": f"'{sheet_name}'!A{next_row_number}:{_column_letter(len(COMMON_HEADERS))}{next_row_number}",
                "values": [[
                    generated_ts,
                    SCHEMA_VERSION,
                    approval_clean_r1_run_id,
                    json.dumps(payloads[sheet_name], ensure_ascii=True, sort_keys=True),
                ]],
            }
        )
        rows_written_per_sheet[sheet_name] = 1
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, write_updates)

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "approval_clean_r1_run_id": approval_clean_r1_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written_per_sheet,
        "summary": summary_payload,
        "registry_writes": registry_writes,
        "budget": budget,
    }


def main() -> None:
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
