#!/usr/bin/env python3
"""Phase 9A-6R13R1 — Clean Blinded Mechanism Test Preregistration Contract Repair.

This repair freezes the missing execution-contract details for the authoritative
clean blinded mechanism-test preregistration without changing the approved
science, population, hierarchy, sample gates, or uncertainty rules.
"""

from __future__ import annotations

import hashlib
import json
import sys
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
    _append_rows,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)


PHASE_ID = "9A-6R13R1"
BUILD_SCRIPT = "automation/repair_refined_mechanism_test_preregistration_clean_contract_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_preregistration_clean_contract_repair_v0"
PREREGISTRATION_REPAIR_VERSION = "refined_mechanism_test_preregistration_clean_contract_repair_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_PREREGISTRATION_CLEAN_R1"
REGISTRY_OWNER_MODULE = "market_state"

ORIGINAL_PREREGISTRATION_VERSION = "1.0"
PARENT_CLEAN_VERSION = "1.0-clean"
REPAIRED_CLEAN_VERSION = "1.0-clean-r1"
PARENT_CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"

PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"
PRIMARY_UNIT = "provider_session_pack_forecast_observation"
PRIMARY_EXPOSURE = "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules"
PRIMARY_COMPARISON_GROUPS = "expanded consistency POSITIVE versus expanded consistency NEGATIVE"
BASELINE_ROLE = "same-provider same-session Pack A structural control used only for success-delta construction"
PRIMARY_ESTIMAND = (
    "difference in baseline-to-expanded corrected directional success deltas "
    "between expanded-state label groups"
)
PRIMARY_EFFECT_MEASURE = "matched_baseline_to_expanded_corrected_directional_success_delta_difference"
PRIMARY_STATISTICAL_METHOD = (
    "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta"
)
PRIMARY_INTERPRETATION = "EXPLORATORY_PREREGISTERED_PRIMARY"
PRIMARY_MATCHING_KEY = (
    "provider + session_id + baseline_pack_A_source_row_key + expanded_pack_source_row_key"
)
PRIMARY_JOIN_RULE = (
    "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id"
)
PRIMARY_RESAMPLING_UNIT = "shared_session_outcome_family"
PRIMARY_OUTCOME_SOURCE_WORKBOOK = "DIAGNOSTICS"
PRIMARY_OUTCOME_SOURCE_SHEET = "Market_Reaction_Canonical_Outcomes"
PRIMARY_OUTCOME_FIELD = "canonical_realized_direction"
OUTCOME_BRIDGE_SHEET = "Corrected_Accuracy_Outcome_Mapping"
OUTCOME_BRIDGE_FIELD = "repaired_canonical_outcome_id"

EXPECTED_COUNTS = {
    "structural_baseline_expanded_pairs": 96,
    "consistency_classified_pairs": 82,
    "high_moderate_confidence_pairs": 72,
    "primary_contrast_eligible_observations": 72,
    "positive_primary_observations": 57,
    "negative_primary_observations": 15,
    "mixed_label_provider_session_clusters": 12,
}

EXPECTED_SAMPLE_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_primary_contrast_observations": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
}

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

CLEAN_SHEETS: Tuple[str, ...] = (
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

APPROVAL_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution_Approval_Clean",
    "Refined_Mechanism_Test_Clean_Outcome_Contract_Approval",
    "Refined_Mechanism_Test_Clean_Success_Derivation_Approval",
    "Refined_Mechanism_Test_Clean_Join_Approval",
    "Refined_Mechanism_Test_Clean_Method_Approval",
    "Refined_Mechanism_Test_Clean_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Execution_Approval_Clean_Summary",
)

INPUT_SHEETS: Tuple[str, ...] = (*ORIGINAL_SHEETS, *CLEAN_SHEETS, *APPROVAL_SHEETS)

OUTPUT_SHEETS = [
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
]

COMMON_HEADERS = ["generated_ts", "schema_version", "clean_contract_repair_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}

FORBIDDEN_INPUT_TITLES = {
    "Market_Reaction_Canonical_Outcomes",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Corrected_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R13R1_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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
    return {
        "cells_before": current,
        "cells_after": current,
        "required_cells": required,
        "compaction_performed": False,
    }


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
                                    "rowCount": 2,
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
        current_rows = int(grid.get("rowCount", 0))
        current_cols = int(grid.get("columnCount", 0))
        target_rows = max(current_rows, 10)
        target_cols = max(current_cols, len(COMMON_HEADERS))
        if target_rows != current_rows or target_cols != current_cols:
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

    header_updates = [
        {
            "range": f"'{name}'!A1:{_column_letter(len(COMMON_HEADERS))}1",
            "values": [COMMON_HEADERS],
        }
        for name in OUTPUT_SHEETS
    ]
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, header_updates)


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


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    cleaned: List[Dict[str, Any]] = []
    for row in rows:
        cleaned.append({k: v for k, v in dict(row).items() if k != "__source_row_number__"})
    serialized = json.dumps(cleaned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _sheet_fingerprint_entries(inputs: Mapping[str, Any], sheet_names: Sequence[str]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for name in sheet_names:
        rows = [dict(row) for row in inputs[name].rows]
        entries.append(
            {
                "sheet_name": name,
                "row_count": len(rows),
                "fingerprint_method": "json_sha256_sorted_keys_without_source_row_number",
                "fingerprint": _fingerprint_rows(rows),
            }
        )
    return entries


def _sheet_payload_fingerprint_entries(
    inputs: Mapping[str, Any],
    sheet_names: Sequence[str],
    run_key: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for name in sheet_names:
        payload = _latest_payload(inputs[name].rows, run_key)
        entries.append(
            {
                "sheet_name": name,
                "fingerprint_method": "json_sha256_sorted_keys",
                "fingerprint": _fingerprint_payload(payload),
            }
        )
    return entries


def _sheet_latest_row_fingerprint_entries(
    inputs: Mapping[str, Any],
    sheet_names: Sequence[str],
    run_key: str,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for name in sheet_names:
        rows = [dict(row) for row in inputs[name].rows]
        ordered = sorted(
            rows,
            key=lambda row: (
                _normalize(row.get("generated_ts")),
                _normalize(row.get(run_key)),
                int(row.get("__source_row_number__", 0) or 0),
            ),
        )
        latest = {k: v for k, v in ordered[-1].items() if k != "__source_row_number__"} if ordered else {}
        entries.append(
            {
                "sheet_name": name,
                "fingerprint_method": "json_sha256_sorted_keys",
                "fingerprint": _fingerprint_payload(latest),
            }
        )
    return entries


def _compare_fingerprint_entries(
    expected_entries: Sequence[Mapping[str, Any]],
    current_entries: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    expected = {
        _normalize(entry.get("sheet_name")): _normalize(entry.get("fingerprint"))
        for entry in expected_entries
    }
    current = {
        _normalize(entry.get("sheet_name")): _normalize(entry.get("fingerprint"))
        for entry in current_entries
    }
    mismatches: List[Dict[str, Any]] = []
    all_sheets = sorted(set(expected) | set(current))
    for sheet_name in all_sheets:
        exp = expected.get(sheet_name)
        cur = current.get(sheet_name)
        if exp != cur:
            mismatches.append(
                {
                    "sheet_name": sheet_name,
                    "expected_fingerprint": exp,
                    "observed_fingerprint": cur,
                }
            )
    return {
        "match": not mismatches,
        "mismatches": mismatches,
    }


def _stop_rule(
    stop_rule_id: str,
    stop_rule_name: str,
    trigger: str,
    runtime_assertion: str,
    severity: str,
    blocked_or_downgrade_behavior: str,
    diagnostic_log_fields: Sequence[str],
    successful_summary_allowed: bool,
    automatic_retry_allowed: bool,
    required_next_phase: str,
    inferential_primary_result_allowed: bool = False,
    descriptive_fallback_allowed: bool = False,
) -> Dict[str, Any]:
    return {
        "stop_rule_id": stop_rule_id,
        "stop_rule_name": stop_rule_name,
        "trigger": trigger,
        "runtime_assertion": runtime_assertion,
        "severity": severity,
        "blocked_or_downgrade_behavior": blocked_or_downgrade_behavior,
        "diagnostic_log_fields": list(diagnostic_log_fields),
        "successful_summary_allowed": successful_summary_allowed,
        "automatic_retry_allowed": automatic_retry_allowed,
        "required_next_phase": required_next_phase,
        "inferential_primary_result_allowed": inferential_primary_result_allowed,
        "descriptive_fallback_allowed": descriptive_fallback_allowed,
    }


def _build_stop_rules() -> List[Dict[str, Any]]:
    hard = "HARD_STOP"
    soft = "DESCRIPTIVE_FALLBACK_ONLY"
    common_log = [
        "classification_run_id",
        "test_preregistration_version",
        "rule_id",
        "expected_value",
        "observed_value",
        "detection_timestamp",
    ]
    return [
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-001",
            "CLEAN_PREREGISTRATION_FINGERPRINT_MISMATCH",
            "Any authoritative clean preregistration sheet fingerprint differs from the approved parent clean freeze.",
            "approved_parent_clean_fingerprint == observed_parent_clean_fingerprint",
            hard,
            "stop_immediately_and_require_contract_repair_or_clean_rerun",
            [*common_log, "sheet_name", "parent_clean_version"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-002",
            "REPEATED_CLEAN_RUN_CONTENT_MISMATCH",
            "Repeated clean preregistration execution for the same logical clean run ID changes frozen scientific content or payload fingerprints.",
            "same_clean_logical_run_id_implies_exact_parent_clean_payload_fingerprints",
            hard,
            "stop_immediately_and_require_new_clean_preregistration_version",
            [*common_log, "clean_logical_run_id", "mismatching_component"],
            False,
            False,
            "RERUN_PHASE9A6R13R_CLEAN_BLINDED_PREREGISTRATION",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-003",
            "CLASSIFICATION_FINGERPRINT_MISMATCH",
            "The approved permanent classification scope or classification-run fingerprint differs from the frozen classification authority.",
            "approved_classification_scope_fingerprint == observed_classification_scope_fingerprint",
            hard,
            "stop_immediately_and_require_classification_execution_review",
            [*common_log, "classification_run_id", "scope_component"],
            False,
            False,
            "RETURN_TO_PHASE9A6R11_CLASSIFICATION_EXECUTION_REVIEW",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-004",
            "OUTCOME_SCHEMA_CONTRACT_MISMATCH",
            "The live outcome schema, field names, or bridge contract differs from the frozen clean-r1 outcome schema contract.",
            "approved_outcome_schema_contract_fingerprint == observed_outcome_schema_contract_fingerprint",
            hard,
            "stop_immediately_and_require_preregistration_contract_repair",
            [*common_log, "schema_component", "schema_version"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-005",
            "OUTCOME_VERSION_MISMATCH",
            "The observed canonical outcome version or repaired mapping version differs from the frozen clean-r1 contract.",
            "observed_outcome_version == frozen_outcome_version and observed_mapping_version == frozen_mapping_version",
            "ROW_LEVEL_BLOCK_OR_SYSTEMIC_HARD_STOP",
            "mark_row_not_eligible_or_stop_if_systemic",
            [*common_log, "expected_outcome_version", "observed_outcome_version", "canonical_outcome_id"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-006",
            "EVALUATION_WINDOW_MISMATCH",
            "The observed outcome evaluation-window identity differs from the frozen clean-r1 window contract.",
            "observed_evaluation_window_version == frozen_evaluation_window_version",
            "ROW_LEVEL_BLOCK_OR_SYSTEMIC_HARD_STOP",
            "mark_row_not_eligible_or_stop_if_systemic",
            [*common_log, "expected_window_version", "observed_window_version", "canonical_outcome_id"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-007",
            "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED",
            "The outcome timestamp provenance is missing, contradictory, outside the approved window, or not at/after the approved window end.",
            "timestamp_provenance_complete_and_outcome_timestamp_compatible == TRUE",
            "ROW_LEVEL_BLOCK_OR_SYSTEMIC_HARD_STOP",
            "mark_row_not_eligible_or_stop_if_systemic",
            [*common_log, "outcome_timestamp", "window_end_timestamp", "timestamp_provenance_fields"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-008",
            "AMBIGUOUS_JOIN",
            "A classification observation maps ambiguously to more than one candidate outcome under the frozen exact-key contract.",
            "resolved_join_count_per_classification_observation in {0,1}",
            "ROW_LEVEL_BLOCK_OR_SYSTEMIC_HARD_STOP",
            "assign_AMBIGUOUS_JOIN_BLOCKED_and_exclude_or_stop_if_systemic",
            [*common_log, "join_key", "candidate_outcome_ids"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-009",
            "DUPLICATE_JOIN",
            "A classification observation produces a duplicate canonical-outcome mapping for the same frozen join key.",
            "canonical_join_key_is_unique_per_classification_observation",
            "ROW_LEVEL_BLOCK_OR_SYSTEMIC_HARD_STOP",
            "assign_DUPLICATE_JOIN_BLOCKED_and_exclude_or_stop_if_systemic",
            [*common_log, "join_key", "duplicate_canonical_outcome_ids"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-010",
            "PHYSICAL_ROW_NUMBER_JOIN_ATTEMPT",
            "The execution builder attempts to join classifications to outcomes using a physical row number.",
            "join_method != physical_row_number",
            hard,
            "stop_immediately_and_require_join_rule_repair",
            [*common_log, "attempted_join_method", "attempted_row_reference"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-011",
            "FUZZY_JOIN_ATTEMPT",
            "The execution builder attempts fuzzy, nearest-date, or text-similarity matching instead of the frozen exact-key join.",
            "join_method == frozen_exact_stable_key_join_only",
            hard,
            "stop_immediately_and_require_join_rule_repair",
            [*common_log, "attempted_join_method", "attempted_similarity_threshold"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-012",
            "MANUAL_JOIN_OVERRIDE_REQUESTED",
            "Any row requires manual intervention or discretionary matching to complete the outcome join.",
            "manual_join_override_required == FALSE",
            hard,
            "stop_immediately_and_hold_until_contract_repair",
            [*common_log, "source_row_key", "override_request_reason"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-013",
            "INVALID_SUCCESS_MAPPING",
            "A joined forecast/outcome combination does not map deterministically under the frozen clean-r1 success-derivation rules.",
            "every_eligible_joined_observation_maps_to_one_allowed_status",
            hard,
            "stop_immediately_and_require_success_derivation_repair",
            [*common_log, "forecast_direction", "realized_direction", "derived_status"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-014",
            "UNEXPECTED_ELIGIBILITY_DIFFERENCE",
            "Execution-time eligibility differs from the frozen primary analysis population or uncertainty exclusions.",
            "observed_primary_eligibility_scope == frozen_primary_eligibility_scope",
            hard,
            "stop_immediately_and_require_approval_rerun",
            [*common_log, "missing_keys", "additional_keys", "changed_status_keys"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-015",
            "POSITIVE_SAMPLE_GATE_FAILURE",
            "The final eligible positive group falls below the frozen minimum positive count.",
            "eligible_positive_count >= frozen_minimum_positive_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "eligible_positive_count", "minimum_positive_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-016",
            "NEGATIVE_SAMPLE_GATE_FAILURE",
            "The final eligible negative group falls below the frozen minimum negative count.",
            "eligible_negative_count >= frozen_minimum_negative_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "eligible_negative_count", "minimum_negative_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-017",
            "PRIMARY_CONTRAST_GATE_FAILURE",
            "The final primary-contrast population falls below the frozen minimum count.",
            "primary_contrast_observation_count >= frozen_minimum_primary_contrast_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "primary_contrast_observation_count", "minimum_primary_contrast_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-018",
            "CLUSTER_GATE_FAILURE",
            "The final eligible analysis population falls below the frozen minimum independent-cluster count.",
            "eligible_cluster_count >= frozen_minimum_cluster_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "eligible_cluster_count", "minimum_cluster_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-019",
            "PROVIDER_GATE_FAILURE",
            "The final eligible analysis population falls below the frozen provider-representation minimum.",
            "eligible_provider_count >= frozen_minimum_provider_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "eligible_provider_count", "minimum_provider_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-020",
            "SESSION_GATE_FAILURE",
            "The final eligible analysis population falls below the frozen session-family minimum.",
            "eligible_session_family_count >= frozen_minimum_session_count",
            soft,
            "downgrade_to_descriptive_only_and_report_gate_failure",
            [*common_log, "eligible_session_family_count", "minimum_session_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-021",
            "UNKNOWN_CONVERTED_TO_NEGATIVE",
            "An UNKNOWN mechanism classification is reinterpreted as NEGATIVE in the primary analysis.",
            "unknown_rows_reclassified_as_negative == 0",
            hard,
            "stop_immediately_and_require_classification_or_preregistration_repair",
            [*common_log, "mechanism_id", "source_row_key"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-022",
            "INSUFFICIENT_EVIDENCE_CONVERTED_TO_NEGATIVE",
            "An INSUFFICIENT_EVIDENCE classification is reinterpreted as NEGATIVE in the primary analysis.",
            "insufficient_evidence_rows_reclassified_as_negative == 0",
            hard,
            "stop_immediately_and_require_classification_or_preregistration_repair",
            [*common_log, "mechanism_id", "source_row_key"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-023",
            "LOW_CONFIDENCE_INCLUDED_IN_PRIMARY",
            "LOW-confidence rows are included in the primary analysis population.",
            "low_confidence_rows_in_primary == 0",
            hard,
            "stop_immediately_and_require_eligibility_repair",
            [*common_log, "source_row_key", "confidence_category"],
            False,
            False,
            "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-024",
            "UNAPPROVED_STATISTICAL_FALLBACK",
            "Execution substitutes an unregistered statistical model, interval method, correction, or fallback.",
            "observed_statistical_method in {frozen_primary_method, frozen_descriptive_fallback_only}",
            hard,
            "stop_immediately_and_require_method_repair",
            [*common_log, "observed_method", "observed_fallback_reason"],
            False,
            False,
            "RUN_PHASE9A6R13R1_CONTRACT_REPAIR",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-025",
            "PRIMARY_METHOD_COMPUTATION_FAILED",
            "The frozen primary estimator cannot be computed as registered.",
            "primary_method_status == estimable",
            soft,
            "skip_inferential_primary_result_and_use_frozen_descriptive_fallback_only",
            [*common_log, "computation_failure_reason", "estimable_resample_count"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-026",
            "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
            "The frozen cluster bootstrap is non-estimable, invalid, or too degenerate to support interval estimation.",
            "estimable_bootstrap_fraction >= 0.80 and bootstrap_interval_computable == TRUE",
            soft,
            "skip_inferential_primary_result_and_use_frozen_descriptive_fallback_only",
            [*common_log, "estimable_bootstrap_fraction", "bootstrap_failure_reason"],
            True,
            False,
            "PROCEED_WITH_DESCRIPTIVE_FALLBACK_ONLY_AND_EXECUTION_REVIEW",
            inferential_primary_result_allowed=False,
            descriptive_fallback_allowed=True,
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-027",
            "DESIGN_CHANGE_AFTER_APPROVAL",
            "Any approved design, eligibility, join, success mapping, method, or hierarchy element changes after approval.",
            "approved_design_fingerprint == execution_design_fingerprint",
            hard,
            "stop_immediately_and_require_new_preregistration_and_approval_cycle",
            [*common_log, "changed_component", "approved_fingerprint", "observed_fingerprint"],
            False,
            False,
            "RERUN_PHASE9A6R13R_CLEAN_BLINDED_PREREGISTRATION",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-028",
            "OUTCOME_ACCESS_BEFORE_APPROVAL",
            "Outcome-bearing rows, realized values, correctness values, or accuracy summaries are accessed before clean execution approval is granted.",
            "outcome_values_accessed_before_execution_approval == 0",
            hard,
            "stop_immediately_and_hold_for_governance_review",
            [*common_log, "resource_accessed", "access_purpose", "access_timestamp"],
            False,
            False,
            "HOLD_MECHANISM_TESTING_PENDING_GOVERNANCE_REVIEW",
        ),
        _stop_rule(
            "RMTP-CLEAN-R1-STOP-029",
            "PRODUCTION_WRITE_ATTEMPT",
            "Any test execution builder attempts to write production sheets, provider rankings, or production behavior controls.",
            "production_write_count == 0",
            hard,
            "stop_immediately_and_hold_for_governance_review",
            [*common_log, "target_sheet", "write_attempt_type"],
            False,
            False,
            "HOLD_MECHANISM_TESTING_PENDING_GOVERNANCE_REVIEW",
        ),
    ]


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
            "notes": "Phase 9A-6R13R1 clean blinded mechanism-test preregistration contract repair outputs.",
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
    clean_contract_repair_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget = _ensure_cell_budget(service, known_titles)
    _ensure_output_sheets(service, known_titles)

    _require(not (FORBIDDEN_INPUT_TITLES & set(INPUT_SHEETS)), "Forbidden outcome-bearing sheet included in repair inputs.")

    original_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Summary"].rows,
        "preregistration_run_id",
    )
    original_outcome = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Outcome_Definition"].rows,
        "preregistration_run_id",
    )
    clean_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows,
        "clean_preregistration_run_id",
    )
    clean_outcome = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_hypotheses = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Hypotheses_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_comparison = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Comparison_Design_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_cluster = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Cluster_Design_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_eligibility = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_confidence = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Confidence_Rules_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_unknown = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Unknown_Rules_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_missing = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Missing_Data_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_stop = _latest_payload(
        inputs["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean"].rows,
        "clean_preregistration_run_id",
    )
    clean_lineage = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Lineage_Audit"].rows,
        "clean_preregistration_run_id",
    )
    clean_design = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Design_Reconciliation"].rows,
        "clean_preregistration_run_id",
    )
    clean_fingerprints = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Fingerprint_Freeze"].rows,
        "clean_preregistration_run_id",
    )
    clean_governance = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Clean_Governance"].rows,
        "clean_preregistration_run_id",
    )

    approval_main = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Clean"].rows,
        "approval_clean_run_id",
    )
    approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Clean_Summary"].rows,
        "approval_clean_run_id",
    )
    outcome_contract_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Outcome_Contract_Approval"].rows,
        "approval_clean_run_id",
    )
    success_derivation_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Success_Derivation_Approval"].rows,
        "approval_clean_run_id",
    )
    join_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Join_Approval"].rows,
        "approval_clean_run_id",
    )
    method_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Method_Approval"].rows,
        "approval_clean_run_id",
    )
    stop_rule_approval = _latest_payload(
        inputs["Refined_Mechanism_Test_Clean_Stop_Rule_Approval"].rows,
        "approval_clean_run_id",
    )

    _require(
        _normalize(original_summary.get("test_preregistration_version")) == ORIGINAL_PREREGISTRATION_VERSION,
        "Original preregistration summary is missing or not version 1.0.",
    )
    _require(
        _normalize(clean_summary.get("test_preregistration_version")) == PARENT_CLEAN_VERSION,
        "Authoritative clean preregistration summary is missing or not version 1.0-clean.",
    )
    _require(
        _normalize(clean_summary.get("classification_run_id")) == CLASSIFICATION_RUN_ID,
        "Clean preregistration classification run ID does not match the approved permanent classification run.",
    )
    _require(
        _normalize(clean_summary.get("source_preregistration_version")) == ORIGINAL_PREREGISTRATION_VERSION,
        "Clean preregistration does not point to original version 1.0 for lineage.",
    )
    _require(
        bool(clean_summary.get("source_preregistration_preserved_unchanged")),
        "Clean preregistration does not report that the original version was preserved unchanged.",
    )
    _require(
        _normalize(approval_summary.get("clean_version")) == PARENT_CLEAN_VERSION,
        "Clean approval summary does not review the authoritative 1.0-clean preregistration.",
    )
    _require(
        _normalize(approval_summary.get("recommended_next_step")) == "RUN_PHASE9A6R13R_CLEAN_PREREGISTRATION_REPAIR",
        "Clean execution approval did not direct a preregistration repair.",
    )
    _require(
        _normalize(approval_summary.get("final_interpretation"))
        == "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_APPROVAL_NEEDS_REPAIR",
        "Clean approval summary is not in the expected repair-required state.",
    )
    _require(
        not bool(outcome_contract_approval.get("schema_contract_approved"))
        and "outcome_timestamp_requirement" in outcome_contract_approval.get("missing_contract_fields", []),
        "Expected outcome schema contract gap is not present.",
    )
    _require(
        not bool(success_derivation_approval.get("success_derivation_approved"))
        and {"outcome_version_mismatch", "evaluation_window_mismatch"}
        <= set(success_derivation_approval.get("missing_or_underdefined_cases", [])),
        "Expected success-derivation contract gaps are not present.",
    )
    _require(
        not bool(join_approval.get("join_rule_approved"))
        and any("no_physical_row_number" in warning or "fuzzy_join" in warning for warning in join_approval.get("warnings", [])),
        "Expected join-guardrail gap is not present.",
    )
    _require(
        not bool(method_approval.get("statistical_method_approved"))
        and not bool(method_approval.get("explicit_bootstrap_replications_frozen"))
        and not bool(method_approval.get("explicit_random_seed_frozen"))
        and not bool(method_approval.get("explicit_resampling_unit_frozen"))
        and not bool(method_approval.get("explicit_zero_cell_handling_frozen")),
        "Expected statistical-method contract gaps are not present.",
    )
    _require(
        not bool(stop_rule_approval.get("stop_rules_approved")),
        "Expected stop-rule gap is not present.",
    )

    comparable_parent_count_keys = (
        "structural_baseline_expanded_pairs",
        "consistency_classified_pairs",
        "high_moderate_confidence_pairs",
        "primary_contrast_eligible_observations",
        "mixed_label_provider_session_clusters",
    )
    for key in comparable_parent_count_keys:
        expected = EXPECTED_COUNTS[key]
        parent_value = clean_summary.get(key)
        if parent_value is None:
            parent_value = clean_comparison.get(key)
        _require(
            int(parent_value) == expected,
            f"Parent clean preregistration count mismatch for {key}: expected {expected}, observed {parent_value}.",
        )

    _require(
        int(clean_summary.get("positive_count")) == EXPECTED_COUNTS["positive_primary_observations"],
        "Parent clean positive primary count changed.",
    )
    _require(
        int(clean_summary.get("negative_count")) == EXPECTED_COUNTS["negative_primary_observations"],
        "Parent clean negative primary count changed.",
    )
    _require(
        int(clean_eligibility.get("positive_eligible_count")) == EXPECTED_COUNTS["positive_primary_observations"],
        "Parent clean eligibility positive count changed.",
    )
    _require(
        int(clean_eligibility.get("negative_eligible_count")) == EXPECTED_COUNTS["negative_primary_observations"],
        "Parent clean eligibility negative count changed.",
    )
    _require(
        int(clean_eligibility.get("primary_contrast_eligible_observations"))
        == EXPECTED_COUNTS["primary_contrast_eligible_observations"],
        "Parent clean primary-contrast observation count changed.",
    )
    _require(
        int(clean_eligibility.get("mixed_label_cluster_count"))
        == EXPECTED_COUNTS["mixed_label_provider_session_clusters"],
        "Parent clean mixed-label cluster count changed.",
    )

    parent_clean_reference_entries = _sheet_latest_row_fingerprint_entries(
        inputs,
        CLEAN_SHEETS,
        "clean_preregistration_run_id",
    )
    parent_clean_expected_sheet_names = [
        _normalize(entry.get("sheet_name")) for entry in clean_fingerprints.get("clean_output_fingerprints", [])
    ]
    parent_clean_current = _sheet_latest_row_fingerprint_entries(
        inputs,
        parent_clean_expected_sheet_names,
        "clean_preregistration_run_id",
    )
    original_current = _sheet_fingerprint_entries(inputs, ORIGINAL_SHEETS)
    parent_clean_expected = clean_fingerprints.get("clean_output_fingerprints", [])
    original_expected = clean_fingerprints.get("source_v1_0_fingerprints", [])
    parent_clean_cmp = _compare_fingerprint_entries(parent_clean_expected, parent_clean_current)
    original_cmp = _compare_fingerprint_entries(original_expected, original_current)

    _require(parent_clean_cmp["match"], f"Parent clean sheet family changed: {parent_clean_cmp['mismatches']}")
    _require(original_cmp["match"], f"Original v1.0 sheet family changed: {original_cmp['mismatches']}")

    stop_rules = _build_stop_rules()
    total_stop_rules = len(stop_rules)

    derived_sample_gates = {
        "minimum_positive_count": {
            "counting_unit": "expanded Pack B-E PM-003 POSITIVE forecast observations with HIGH|MODERATE confidence and matched Pack A structural controls",
            "stable_counting_key": "classification_run_id + mechanism_id + source_row_key",
            "current_blinded_count": EXPECTED_COUNTS["positive_primary_observations"],
            "threshold": EXPECTED_SAMPLE_GATES["minimum_positive_count"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "POSITIVE_SAMPLE_GATE_FAILURE -> descriptive fallback only",
        },
        "minimum_negative_count": {
            "counting_unit": "expanded Pack B-E PM-003 NEGATIVE forecast observations with HIGH|MODERATE confidence and matched Pack A structural controls",
            "stable_counting_key": "classification_run_id + mechanism_id + source_row_key",
            "current_blinded_count": EXPECTED_COUNTS["negative_primary_observations"],
            "threshold": EXPECTED_SAMPLE_GATES["minimum_negative_count"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "NEGATIVE_SAMPLE_GATE_FAILURE -> descriptive fallback only",
        },
        "minimum_primary_contrast_observations": {
            "counting_unit": "Structure A primary-contrast eligible expanded observations with valid same-provider same-session Pack A controls",
            "stable_counting_key": "classification_run_id + mechanism_id + expanded_source_row_key",
            "current_blinded_count": EXPECTED_COUNTS["primary_contrast_eligible_observations"],
            "threshold": EXPECTED_SAMPLE_GATES["minimum_primary_contrast_observations"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "PRIMARY_CONTRAST_GATE_FAILURE -> descriptive fallback only",
        },
        "minimum_clusters": {
            "counting_unit": "provider_session clusters",
            "stable_counting_key": "provider + session_id",
            "current_blinded_count": 24,
            "threshold": EXPECTED_SAMPLE_GATES["minimum_clusters"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "CLUSTER_GATE_FAILURE -> descriptive fallback only",
        },
        "minimum_providers": {
            "counting_unit": "providers represented in the Structure A primary contrast",
            "stable_counting_key": "provider",
            "current_blinded_count": 3,
            "threshold": EXPECTED_SAMPLE_GATES["minimum_providers"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "PROVIDER_GATE_FAILURE -> descriptive fallback only",
        },
        "minimum_sessions": {
            "counting_unit": "shared session outcome families represented in the Structure A primary contrast",
            "stable_counting_key": "session_id",
            "current_blinded_count": 8,
            "threshold": EXPECTED_SAMPLE_GATES["minimum_sessions"],
            "status": "PASS",
            "future_post_join_recheck": True,
            "stop_or_downgrade_action": "SESSION_GATE_FAILURE -> descriptive fallback only",
        },
    }

    outcome_definition_r1 = {
        "test_preregistration_version": REPAIRED_CLEAN_VERSION,
        "parent_clean_version": PARENT_CLEAN_VERSION,
        "original_preregistration_version": ORIGINAL_PREREGISTRATION_VERSION,
        "repair_type": "EXECUTION_CONTRACT_COMPLETION_ONLY",
        "schema_contract_only": True,
        "canonical_outcome_source_workbook": PRIMARY_OUTCOME_SOURCE_WORKBOOK,
        "canonical_outcome_source_sheet": PRIMARY_OUTCOME_SOURCE_SHEET,
        "canonical_outcome_id_field": clean_outcome.get("canonical_outcome_id_field")
        or original_outcome.get("canonical_outcome_id_field")
        or "canonical_outcome_id",
        "canonical_outcome_component_field": clean_outcome.get("canonical_outcome_component_field")
        or original_outcome.get("canonical_outcome_field")
        or PRIMARY_OUTCOME_FIELD,
        "forecast_direction_field_name": outcome_contract_approval.get("forecast_direction_field_name") or "forecast_direction",
        "corrected_mapping_bridge_sheet": original_outcome.get("corrected_mapping_bridge_sheet") or OUTCOME_BRIDGE_SHEET,
        "corrected_mapping_bridge_field": original_outcome.get("corrected_mapping_bridge_field") or OUTCOME_BRIDGE_FIELD,
        "outcome_metric_id": clean_outcome.get("outcome_metric_id")
        or original_outcome.get("outcome_metric_id")
        or "CORRECTED_DIRECTIONAL_SUCCESS_BINARY",
        "outcome_metric_definition": original_outcome.get("outcome_metric_definition")
        or (
            "Future binary indicator that an eligible forecast direction agrees with the corrected "
            "canonical realized direction materialized through the repaired market-reaction outcome layer."
        ),
        "repaired_canonical_outcome_version": clean_outcome.get("repaired_canonical_outcome_version")
        or original_outcome.get("corrected_mapping_version_lineage")
        or "market_reaction_outcome_source_implementation_v0 + corrected_accuracy_re_evaluation_design_v0",
        "evaluation_window_version": clean_outcome.get("evaluation_window_version")
        or original_outcome.get("evaluation_window_version")
        or "Market_Reaction_Canonical_Outcomes window_policy/window_minutes metadata",
        "evaluation_window_fields": original_outcome.get("evaluation_window_fields")
        or ["window_policy", "window_minutes", "canonical_start_ts", "canonical_end_ts"],
        "provider_neutrality_rule": clean_outcome.get("provider_neutrality_rule")
        or original_outcome.get("provider_neutrality_rule")
        or "one canonical corrected outcome per session window; no provider-specific outcome remapping allowed",
        "future_join_rule": PRIMARY_JOIN_RULE,
        "one_to_one_join_requirement": True,
        "missing_outcome_handling": clean_outcome.get("missing_outcome_handling")
        or original_outcome.get("missing_outcome_handling")
        or "exclude_from_inferential_analysis_and_report_reason",
        "duplicate_outcome_handling": clean_outcome.get("duplicate_outcome_handling")
        or original_outcome.get("duplicate_outcome_handling")
        or "block_ambiguous_join_and_exclude_until_resolved_per_frozen_rule",
        "ambiguous_canonical_outcome_handling": clean_outcome.get("ambiguous_canonical_outcome_handling")
        or "exclude_without_manual_matching",
        "invalid_canonical_outcome_handling": clean_outcome.get("invalid_canonical_outcome_handling")
        or "exclude_and_report_invalid_canonical_outcome",
        "invalid_forecast_direction_handling": clean_outcome.get("invalid_forecast_direction_handling")
        or original_outcome.get("invalid_forecast_direction_handling")
        or "exclude_and_report_invalid_output",
        "flat_handling": clean_outcome.get("flat_handling")
        or original_outcome.get("tie_flat_handling")
        or "exclude_flat_or_ambiguous_realized_direction_from_primary_binary_analysis_and_report_descriptively",
        "no_signal_handling": clean_outcome.get("no_signal_handling")
        or original_outcome.get("no_signal_handling")
        or (
            "exclude_from_primary_directional_binary_and_report_descriptively unless a future "
            "no-signal-specific secondary metric is separately preregistered"
        ),
        "no_outcome_sheet_loaded_by_repair_builder": True,
        "future_schema_fingerprint_verification_required": True,
        "outcome_timestamp_requirement": {
            "rule_id": "OUTCOME_TIMESTAMP_REQUIREMENT",
            "canonical_outcome_version_required": True,
            "approved_evaluation_window_required": True,
            "outcome_timestamp_at_or_after_evaluation_window_end": True,
            "no_information_outside_approved_evaluation_window": True,
            "source_availability_timestamp_compatible_with_canonical_repair_process": True,
            "deterministically_linked_to_forecast_observation": True,
            "reject_if_timestamp_provenance_missing_or_contradictory": True,
            "failure_status": "OUTCOME_TIMESTAMP_REQUIREMENT_FAILED",
            "failure_action": "mark_join_not_eligible_do_not_calculate_success_log_reason_no_manual_override",
            "systemic_failure_behavior": "fail_closed_and_recheck_primary_sample_gates",
        },
        "outcome_version_mismatch_handling": {
            "trigger": [
                "live_canonical_outcome_version_differs_from_frozen_contract",
                "repaired_mapping_version_differs_from_frozen_contract",
                "required_version_field_missing",
                "multiple_outcome_versions_returned_for_same_canonical_id",
            ],
            "result": "NOT_ELIGIBLE",
            "systemic_result": "HARD_BLOCK",
            "required_actions": [
                "do_not_calculate_directional_success",
                "do_not_fall_back_to_another_outcome_version",
                "do_not_choose_latest_available_version_automatically",
                "log_expected_and_observed_versions",
                "require_preregistration_repair_or_new_approval_if_canonical_version_changes",
            ],
        },
        "evaluation_window_mismatch_handling": {
            "trigger": [
                "outcome_evaluation_window_version_differs_from_frozen_version",
                "evaluation_window_start_or_end_timestamps_do_not_match_the_approved_window_rule",
                "baseline_and_expanded_observations_use_incompatible_evaluation_windows",
                "window_identity_missing_or_ambiguous",
            ],
            "result": "NOT_ELIGIBLE",
            "systemic_result": "HARD_BLOCK",
            "required_actions": [
                "do_not_calculate_success",
                "do_not_substitute_another_window",
                "do_not_manually_repair_the_row",
                "log_expected_and_observed_window_definitions",
                "recheck_sample_gates_after_exclusions",
            ],
        },
        "authoritative_parent_references": [
            "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean",
            "Refined_Mechanism_Test_Frozen_Comparison_Design_Clean",
            "Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean",
        ],
    }

    join_rules_r1 = {
        "test_preregistration_version": REPAIRED_CLEAN_VERSION,
        "approved_future_join_path": PRIMARY_JOIN_RULE,
        "stable_key_components": ["provider", "session_id", "pack_level", "source_row_key"],
        "bridge_components": ["repaired_canonical_outcome_id", "canonical_outcome_id"],
        "one_classification_observation_to_one_canonical_outcome_required": True,
        "exact_stable_key_match_required": True,
        "physical_row_number_join_prohibited": True,
        "fuzzy_text_join_prohibited": True,
        "manual_matching_prohibited": True,
        "nearest_date_matching_prohibited": True,
        "provider_name_only_join_prohibited": True,
        "session_only_join_prohibited": True,
        "pack_level_only_join_prohibited": True,
        "version_match_required": True,
        "evaluation_window_match_required": True,
        "timestamp_requirement_pass_required": True,
        "ambiguous_join_result": "AMBIGUOUS_JOIN_BLOCKED",
        "duplicate_join_result": "DUPLICATE_JOIN_BLOCKED",
        "missing_join_result": "NOT_ELIGIBLE_MISSING_OUTCOME_JOIN",
        "required_actions_on_failure": [
            "do_not_calculate_directional_success",
            "do_not_manually_override",
            "do_not_add_fuzzy_repair_logic",
            "log_join_failure_reason",
            "exclude_or_block_under_frozen_rule",
        ],
        "baseline_and_expanded_rows_must_map_to_correct_forecast_identity": True,
        "future_schema_fingerprint_verification_required": True,
        "parent_clean_join_rule_reference": clean_outcome.get("future_join_rule") or PRIMARY_JOIN_RULE,
    }

    success_derivation_r1 = {
        "test_preregistration_version": REPAIRED_CLEAN_VERSION,
        "allowed_output_statuses": ["SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"],
        "primary_metric_scope": "directional_binary_on_eligible_forecast_directions_only",
        "preserved_existing_flat_policy": True,
        "preserved_existing_no_signal_policy": True,
        "rule_precedence": [
            {
                "order": 1,
                "condition": "duplicate_outcome_join_or_ambiguous_outcome_join",
                "result": "AMBIGUOUS_JOIN_BLOCKED",
            },
            {
                "order": 2,
                "condition": "outcome_version_mismatch_or_evaluation_window_mismatch_or_timestamp_requirement_failure",
                "result": "NOT_ELIGIBLE",
            },
            {
                "order": 3,
                "condition": "missing_or_invalid_forecast_or_realized_direction",
                "result": "NOT_ELIGIBLE",
            },
            {
                "order": 4,
                "condition": "forecast_direction == NO_CLEAR_DIRECTION",
                "result": "NOT_ELIGIBLE",
            },
            {
                "order": 5,
                "condition": "no_signal_forecast == TRUE",
                "result": "NOT_ELIGIBLE",
            },
            {
                "order": 6,
                "condition": "realized_direction in {FLAT, NO_CLEAR_DIRECTION, AMBIGUOUS}",
                "result": "NOT_ELIGIBLE",
                "policy_source": "existing clean flat/no-clear-direction exclusion policy preserved",
            },
            {
                "order": 7,
                "condition": "forecast_direction == FLAT",
                "result": "NOT_ELIGIBLE",
                "policy_source": "eligible forecast direction boundary preserved from original outcome metric definition",
            },
            {
                "order": 8,
                "condition": "forecast_direction == UP and realized_direction == UP",
                "result": "SUCCESS",
            },
            {
                "order": 9,
                "condition": "forecast_direction == UP and realized_direction == DOWN",
                "result": "FAILURE",
            },
            {
                "order": 10,
                "condition": "forecast_direction == DOWN and realized_direction == DOWN",
                "result": "SUCCESS",
            },
            {
                "order": 11,
                "condition": "forecast_direction == DOWN and realized_direction == UP",
                "result": "FAILURE",
            },
            {
                "order": 12,
                "condition": "any_other_state_not_explicitly_allowed",
                "result": "NOT_ELIGIBLE",
            },
        ],
        "explicit_case_map": {
            "UP_forecast_UP_outcome": "SUCCESS",
            "UP_forecast_DOWN_outcome": "FAILURE",
            "DOWN_forecast_DOWN_outcome": "SUCCESS",
            "DOWN_forecast_UP_outcome": "FAILURE",
            "forecast_FLAT_any_realized_direction": "NOT_ELIGIBLE",
            "realized_FLAT_any_forecast_direction": "NOT_ELIGIBLE",
            "forecast_NO_CLEAR_DIRECTION": "NOT_ELIGIBLE",
            "no_signal_forecast": "NOT_ELIGIBLE",
            "missing_forecast_direction": "NOT_ELIGIBLE",
            "missing_realized_direction": "NOT_ELIGIBLE",
            "invalid_forecast_direction": "NOT_ELIGIBLE",
            "invalid_realized_direction": "NOT_ELIGIBLE",
            "duplicate_outcome_join": "AMBIGUOUS_JOIN_BLOCKED",
            "ambiguous_outcome_join": "AMBIGUOUS_JOIN_BLOCKED",
            "outcome_version_mismatch": "NOT_ELIGIBLE",
            "evaluation_window_mismatch": "NOT_ELIGIBLE",
            "timestamp_requirement_failure": "NOT_ELIGIBLE",
        },
        "policy_notes": {
            "realized_flat_policy": clean_outcome.get("flat_handling")
            or original_outcome.get("tie_flat_handling"),
            "no_signal_policy": clean_outcome.get("no_signal_handling")
            or original_outcome.get("no_signal_handling"),
            "forecast_flat_policy_reason": "primary metric remains directional-only and preserves the eligible forecast direction boundary",
        },
    }

    statistical_method_r1 = {
        "test_preregistration_version": REPAIRED_CLEAN_VERSION,
        "primary_method_id": PRIMARY_STATISTICAL_METHOD,
        "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
        "primary_interpretation": PRIMARY_INTERPRETATION,
        "grouping_variable": PRIMARY_COMPARISON_GROUPS,
        "matched_unit": "same-provider same-session Pack A baseline paired with one expanded Pack B-E observation",
        "outcome_delta_definition": (
            "expanded corrected directional success status minus matched Pack A corrected directional success status "
            "for each eligible provider-session pair"
        ),
        "resampling_unit": PRIMARY_RESAMPLING_UNIT,
        "resampling_procedure": (
            "resample entire shared session outcome families with replacement; keep all nested provider-session "
            "observations, Pack A controls, expanded observations, and group assignments together"
        ),
        "bootstrap_replications": 10000,
        "bootstrap_random_seed": 9130613,
        "confidence_interval_method": "two_sided_percentile_bootstrap_95pct_interval",
        "confidence_interval_quantiles": {"lower": 0.025, "upper": 0.975},
        "shared_session_outcome_families": 8,
        "provider_session_clusters": 24,
        "small_cluster_warning": clean_cluster.get("small_cluster_warning"),
        "ordinary_unclustered_row_level_comparison_prohibited": True,
        "zero_cell_handling": {
            "trigger": "one_primary_comparison_group_has_zero_eligible_joined_outcomes",
            "status": "ZERO_PRIMARY_GROUP_CELL",
            "required_action": "do_not_calculate_inferential_effect_downgrade_to_descriptive_only_no_continuity_correction",
            "bootstrap_resample_rule": "non_estimable_resamples_are_counted_and_interval_continues_only_if_estimable_fraction_at_least_0_80",
        },
        "sparse_group_handling": {
            "trigger": "either_final_joined_primary_group_falls_below_its_frozen_gate",
            "required_action": "do_not_perform_primary_inferential_test_report_descriptive_counts_and_deltas_only",
            "threshold_lowering_allowed": False,
        },
        "degenerate_bootstrap_handling": {
            "trigger_status": "DEGENERATE_BOOTSTRAP_DISTRIBUTION",
            "trigger_conditions": [
                "estimable_bootstrap_fraction_below_0_80",
                "all_estimable_effects_identical_due_to_insufficient_variation",
                "bootstrap_interval_cannot_be_calculated",
                "resampling_breaks_the_frozen_matched_structure",
            ],
            "fallback": {
                "report_observed_matched_risk_difference_estimate": True,
                "report_raw_group_counts": True,
                "report_session_level_descriptive_deltas": True,
                "state_interval_estimation_failed_explicitly": True,
                "make_no_significance_claim": True,
                "select_another_inferential_method": False,
            },
        },
        "primary_method_computation_failure": {
            "trigger_status": "PRIMARY_METHOD_COMPUTATION_FAILED",
            "required_action": "preserve_logs_use_only_frozen_descriptive_fallback_no_alternative_model_no_p_value",
            "automatic_method_substitution_allowed": False,
        },
        "descriptive_fallback": {
            "allowed": True,
            "content": [
                "raw_group_counts",
                "matched_success_delta_estimate",
                "session_level_descriptive_deltas",
                "gate_failure_or_method_failure_reason",
            ],
            "inferential_primary_result_allowed": False,
        },
        "automatic_method_substitution_allowed": False,
    }

    stop_rules_r1 = {
        "test_preregistration_version": REPAIRED_CLEAN_VERSION,
        "fail_closed": True,
        "hard_stop_summary_allowed": False,
        "automatic_retry_allowed": False,
        "stop_rules": stop_rules,
    }

    parent_clean_fingerprint_map = {
        _normalize(entry.get("sheet_name")): entry.get("fingerprint")
        for entry in parent_clean_reference_entries
    }
    original_fingerprint_map = {
        _normalize(entry.get("sheet_name")): entry.get("fingerprint")
        for entry in original_current
    }
    parent_clean_references = [
        {
            "sheet_name": sheet_name,
            "fingerprint": parent_clean_fingerprint_map.get(sheet_name),
            "modification_allowed_after_repair": False,
        }
        for sheet_name in CLEAN_SHEETS
    ]

    preregistration_r1 = {
        "phase_id": PHASE_ID,
        "build_script": BUILD_SCRIPT,
        "preregistration_repair_version": PREREGISTRATION_REPAIR_VERSION,
        "parent_preregistration_version": PARENT_CLEAN_VERSION,
        "repaired_preregistration_version": REPAIRED_CLEAN_VERSION,
        "original_preregistration_version": ORIGINAL_PREREGISTRATION_VERSION,
        "clean_logical_run_id": PARENT_CLEAN_RUN_ID,
        "clean_contract_repair_run_id": clean_contract_repair_run_id,
        "repair_type": "EXECUTION_CONTRACT_COMPLETION_ONLY",
        "test_preregistration_status": "FROZEN",
        "scientific_hypothesis_changed": False,
        "primary_population_changed": False,
        "mechanism_hierarchy_changed": False,
        "sample_gates_changed": False,
        "outcome_values_accessed": False,
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "mechanism_version": MECHANISM_VERSION,
        "primary_mechanism": PRIMARY_MECHANISM,
        "exploratory_mechanism": EXPLORATORY_MECHANISM,
        "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
        "primary_structure": PRIMARY_STRUCTURE,
        "primary_exposure": PRIMARY_EXPOSURE,
        "primary_comparison_groups": PRIMARY_COMPARISON_GROUPS,
        "baseline_role": BASELINE_ROLE,
        "primary_estimand": PRIMARY_ESTIMAND,
        "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
        "primary_unit": PRIMARY_UNIT,
        "counts": EXPECTED_COUNTS,
        "sample_gates": EXPECTED_SAMPLE_GATES,
        "sample_gate_contract": derived_sample_gates,
        "uncertainty_rules": {
            "UNKNOWN": "excluded_from_primary",
            "INSUFFICIENT_EVIDENCE": "excluded_from_primary",
            "EXCLUDED": "never_included",
            "LOW_CONFIDENCE": "excluded_from_primary",
            "no_uncertain_class_converted_to_negative": True,
        },
        "authoritative_parent_clean_references": parent_clean_references,
        "supporting_unchanged_clean_sheets_duplicated": False,
        "supporting_unchanged_clean_sheets_reason": "workbook_cell_budget_preservation_with_immutable_parent_references",
        "modification_allowed_after_repair": False,
    }

    design_reconciliation_r1 = {
        "parent_clean_version": PARENT_CLEAN_VERSION,
        "repaired_clean_version": REPAIRED_CLEAN_VERSION,
        "repair_type": "EXECUTION_CONTRACT_COMPLETION_ONLY",
        "science_preservation": {
            "primary_mechanism_changed": False,
            "primary_hypothesis_changed": False,
            "primary_structure_changed": False,
            "primary_population_changed": False,
            "positive_count_changed": False,
            "negative_count_changed": False,
            "sample_gates_changed": False,
            "hierarchy_changed": False,
            "uncertainty_rules_changed": False,
        },
        "equivalence_checks": [
            {
                "area": "primary_mechanism_and_hierarchy",
                "parent_value": {
                    "primary": PRIMARY_MECHANISM,
                    "exploratory": EXPLORATORY_MECHANISM,
                    "descriptive_only": DESCRIPTIVE_ONLY_MECHANISM,
                },
                "r1_value": {
                    "primary": PRIMARY_MECHANISM,
                    "exploratory": EXPLORATORY_MECHANISM,
                    "descriptive_only": DESCRIPTIVE_ONLY_MECHANISM,
                },
                "status": "PRESERVED",
            },
            {
                "area": "structure_a_design",
                "parent_value": {
                    "structure": clean_comparison.get("primary_structure"),
                    "exposure": clean_comparison.get("primary_exposure"),
                    "comparison_groups": clean_comparison.get("primary_comparison_groups"),
                    "baseline_role": clean_comparison.get("baseline_role"),
                    "estimand": clean_comparison.get("primary_estimand"),
                },
                "r1_value": {
                    "structure": PRIMARY_STRUCTURE,
                    "exposure": PRIMARY_EXPOSURE,
                    "comparison_groups": PRIMARY_COMPARISON_GROUPS,
                    "baseline_role": BASELINE_ROLE,
                    "estimand": PRIMARY_ESTIMAND,
                },
                "status": "PRESERVED",
            },
            {
                "area": "counts_and_sample_gates",
                "parent_value": {
                    "counts": EXPECTED_COUNTS,
                    "gates": EXPECTED_SAMPLE_GATES,
                },
                "r1_value": {
                    "counts": EXPECTED_COUNTS,
                    "gates": EXPECTED_SAMPLE_GATES,
                },
                "status": "PRESERVED",
            },
            {
                "area": "uncertainty_rules",
                "parent_value": {
                    "UNKNOWN": clean_unknown.get("UNKNOWN"),
                    "INSUFFICIENT_EVIDENCE": clean_unknown.get("INSUFFICIENT_EVIDENCE"),
                    "EXCLUDED": clean_unknown.get("EXCLUDED"),
                    "LOW_CONFIDENCE": clean_unknown.get("LOW_CONFIDENCE"),
                },
                "r1_value": preregistration_r1["uncertainty_rules"],
                "status": "PRESERVED",
            },
        ],
        "contract_completion": [
            {"component": "outcome_timestamp_requirement", "status": "ADDED_AND_FROZEN"},
            {"component": "outcome_version_mismatch_handling", "status": "ADDED_AND_FROZEN"},
            {"component": "evaluation_window_mismatch_handling", "status": "ADDED_AND_FROZEN"},
            {"component": "stable_key_join_guardrails", "status": "ADDED_AND_FROZEN"},
            {"component": "complete_success_derivation", "status": "ADDED_AND_FROZEN"},
            {"component": "fully_specified_statistical_method", "status": "ADDED_AND_FROZEN"},
            {"component": "complete_fail_closed_stop_rules", "status": "ADDED_AND_FROZEN"},
        ],
    }

    lineage_audit_r1 = {
        "original_preregistration_version": ORIGINAL_PREREGISTRATION_VERSION,
        "parent_clean_version": PARENT_CLEAN_VERSION,
        "repaired_preregistration_version": REPAIRED_CLEAN_VERSION,
        "repair_type": "EXECUTION_CONTRACT_COMPLETION_ONLY",
        "original_sheet_family": list(ORIGINAL_SHEETS),
        "parent_clean_sheet_family": list(CLEAN_SHEETS),
        "r1_sheet_family": list(OUTPUT_SHEETS),
        "clean_logical_run_id": PARENT_CLEAN_RUN_ID,
        "clean_builder_detectable_execution_events": approval_summary.get("detectable_clean_execution_events"),
        "clean_repeated_execution_status": approval_summary.get("repeated_execution_status"),
        "parent_clean_fingerprints_match": parent_clean_cmp["match"],
        "original_fingerprints_match": original_cmp["match"],
        "parent_clean_mismatches": parent_clean_cmp["mismatches"],
        "original_mismatches": original_cmp["mismatches"],
        "source_preregistration_preserved_unchanged": True,
        "parent_clean_preserved_unchanged": True,
        "scientific_hypothesis_changed": False,
        "primary_population_changed": False,
        "mechanism_hierarchy_changed": False,
        "sample_gates_changed": False,
        "outcome_values_accessed": False,
        "execution_authority_after_repair_pending_approval_rerun": REPAIRED_CLEAN_VERSION,
    }

    blinding_audit_r1 = {
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "provider_rankings_produced": 0,
        "post_session_evidence_accessed": 0,
        "forbidden_inputs_present": [],
        "blinding_status": "BLINDING_INTACT_CLEAN_R1_CONTRACT_REPAIR",
        "repair_builder_scope": "schema_contract_completion_only",
        "design_changed_by_outcome_information": False,
    }

    governance_r1 = {
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "classifications_modified": 0,
        "parent_clean_sheets_modified": 0,
        "original_preregistration_sheets_modified": 0,
        "scientific_hypothesis_changes": 0,
        "population_changes": 0,
        "sample_gate_changes": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
        "budget": budget,
    }

    payloads: Dict[str, Dict[str, Any]] = {
        "Refined_Mechanism_Test_Preregistration_Clean_R1": preregistration_r1,
        "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean_R1": outcome_definition_r1,
        "Refined_Mechanism_Test_Frozen_Join_Rules_Clean_R1": join_rules_r1,
        "Refined_Mechanism_Test_Frozen_Success_Derivation_Clean_R1": success_derivation_r1,
        "Refined_Mechanism_Test_Frozen_Statistical_Method_Clean_R1": statistical_method_r1,
        "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean_R1": stop_rules_r1,
        "Refined_Mechanism_Test_Clean_R1_Design_Reconciliation": design_reconciliation_r1,
        "Refined_Mechanism_Test_Clean_R1_Lineage_Audit": lineage_audit_r1,
        "Refined_Mechanism_Test_Clean_R1_Blinding_Audit": blinding_audit_r1,
        "Refined_Mechanism_Test_Clean_R1_Governance": governance_r1,
    }

    repaired_output_fingerprints = [
        {
            "sheet_name": sheet_name,
            "fingerprint_method": "json_sha256_sorted_keys",
            "fingerprint": _fingerprint_payload(payloads[sheet_name]),
        }
        for sheet_name in payloads
    ]
    derived_fingerprints = [
        {
            "component": "parent_clean_version",
            "fingerprint": _fingerprint_payload({"version": PARENT_CLEAN_VERSION, "run_id": PARENT_CLEAN_RUN_ID}),
        },
        {
            "component": "primary_design",
            "fingerprint": _fingerprint_payload(
                {
                    "primary_structure": PRIMARY_STRUCTURE,
                    "primary_exposure": PRIMARY_EXPOSURE,
                    "comparison_groups": PRIMARY_COMPARISON_GROUPS,
                    "baseline_role": BASELINE_ROLE,
                    "primary_estimand": PRIMARY_ESTIMAND,
                    "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
                    "primary_unit": PRIMARY_UNIT,
                }
            ),
        },
        {"component": "outcome_contract", "fingerprint": _fingerprint_payload(outcome_definition_r1)},
        {"component": "join_rules", "fingerprint": _fingerprint_payload(join_rules_r1)},
        {"component": "success_derivation", "fingerprint": _fingerprint_payload(success_derivation_r1)},
        {"component": "statistical_method", "fingerprint": _fingerprint_payload(statistical_method_r1)},
        {"component": "stop_rules", "fingerprint": _fingerprint_payload(stop_rules_r1)},
        {"component": "sample_gates", "fingerprint": _fingerprint_payload(derived_sample_gates)},
        {
            "component": "hierarchy",
            "fingerprint": _fingerprint_payload(
                {
                    "primary": PRIMARY_MECHANISM,
                    "exploratory": EXPLORATORY_MECHANISM,
                    "descriptive_only": DESCRIPTIVE_ONLY_MECHANISM,
                }
            ),
        },
        {
            "component": "uncertainty_rules",
            "fingerprint": _fingerprint_payload(preregistration_r1["uncertainty_rules"]),
        },
        {
            "component": "reporting_plan_reference",
            "fingerprint": _fingerprint_payload(
                {
                    "parent_reporting_sheet": "Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean",
                    "parent_reporting_fingerprint": parent_clean_fingerprint_map.get(
                        "Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean"
                    ),
                }
            ),
        },
    ]

    payloads["Refined_Mechanism_Test_Clean_R1_Fingerprint_Freeze"] = {
        "parent_clean_current_fingerprints": parent_clean_current,
        "parent_clean_expected_fingerprints": parent_clean_expected,
        "parent_clean_match": parent_clean_cmp["match"],
        "original_current_fingerprints": original_current,
        "original_expected_fingerprints": original_expected,
        "original_match": original_cmp["match"],
        "repaired_output_fingerprints": repaired_output_fingerprints,
        "derived_fingerprints": derived_fingerprints,
        "modification_allowed_after_repair": False,
    }

    build_status = "PASS"
    final_interpretation = "REFINED_MECHANISM_TEST_PREREGISTRATION_CLEAN_R1_READY"
    recommended_next_step = "RERUN_PHASE9A6R14R_CLEAN_EXECUTION_APPROVAL"

    payloads["Refined_Mechanism_Test_Preregistration_Clean_R1_Summary"] = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": BUILD_SCRIPT,
        "repaired_preregistration_version": REPAIRED_CLEAN_VERSION,
        "parent_clean_version": PARENT_CLEAN_VERSION,
        "primary_mechanism_changed": False,
        "primary_hypothesis_changed": False,
        "primary_structure_changed": False,
        "primary_population_changed": False,
        "positive_count_changed": False,
        "negative_count_changed": False,
        "sample_gates_changed": False,
        "hierarchy_changed": False,
        "uncertainty_rules_changed": False,
        "outcome_timestamp_requirement_added": True,
        "outcome_version_mismatch_handling_added": True,
        "evaluation_window_mismatch_handling_added": True,
        "physical_row_join_prohibited": True,
        "fuzzy_join_prohibited": True,
        "manual_join_prohibited": True,
        "binary_success_derivation_complete": True,
        "bootstrap_replications_frozen": True,
        "random_seed_frozen": True,
        "resampling_unit_frozen": True,
        "zero_cell_handling_frozen": True,
        "degenerate_bootstrap_handling_frozen": True,
        "descriptive_fallback_frozen": True,
        "stop_rules_frozen": True,
        "total_stop_rules": total_stop_rules,
        "structural_pairs": EXPECTED_COUNTS["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": EXPECTED_COUNTS["consistency_classified_pairs"],
        "high_moderate_pairs": EXPECTED_COUNTS["high_moderate_confidence_pairs"],
        "primary_contrast_observations": EXPECTED_COUNTS["primary_contrast_eligible_observations"],
        "positive_observations": EXPECTED_COUNTS["positive_primary_observations"],
        "negative_observations": EXPECTED_COUNTS["negative_primary_observations"],
        "mixed_label_clusters": EXPECTED_COUNTS["mixed_label_provider_session_clusters"],
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "parent_sheets_modified": 0,
        "original_sheets_modified": 0,
        "classifications_modified": 0,
        "production_writes": 0,
        "ready_for_clean_execution_approval_rerun": True,
        "ready_for_mechanism_testing": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next_step,
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
            clean_contract_repair_run_id,
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
        "clean_contract_repair_run_id": clean_contract_repair_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Preregistration_Clean_R1_Summary"],
        "registry_writes": registry_writes,
        "budget": budget,
    }
def main() -> None:
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
