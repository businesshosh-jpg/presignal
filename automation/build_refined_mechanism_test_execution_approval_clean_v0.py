#!/usr/bin/env python3
"""Phase 9A-6R14R — Clean Blinded Refined Mechanism Test Execution Approval.

This approval phase reviews the authoritative clean mechanism-test
preregistration (`1.0-clean`) without loading any outcome workbook, outcome
sheet, outcome-bearing row, realized value, or accuracy result. It verifies
both scientific/blinding validity and lineage safety for the clean rerun.
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
    _append_rows,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)


PHASE_ID = "9A-6R14R"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_execution_approval_clean_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_execution_approval_clean_v0"
APPROVAL_VERSION = "refined_mechanism_test_execution_approval_clean_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_EXECUTION_APPROVAL_CLEAN"
REGISTRY_OWNER_MODULE = "market_state"

CLEAN_PREREG_VERSION = "1.0-clean"
SOURCE_PREREG_VERSION = "1.0"
CLEAN_RUN_ID = "9A-6R13R_20260711T002150Z"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"

V10_SHEETS: Tuple[str, ...] = (
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

INPUT_SHEETS: Tuple[str, ...] = (
    *CLEAN_SHEETS,
    *V10_SHEETS,
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
    "Refined_Mechanism_Test_Planning_Readiness_Summary",
    "Refined_Mechanism_Test_Label_Eligibility",
)

OUTPUT_SHEETS = [
    "Refined_Mechanism_Test_Execution_Approval_Clean",
    "Refined_Mechanism_Test_Clean_Lineage_Approval",
    "Refined_Mechanism_Test_Clean_Blinding_Approval",
    "Refined_Mechanism_Test_Clean_Structure_Approval",
    "Refined_Mechanism_Test_Clean_Count_Definition_Approval",
    "Refined_Mechanism_Test_Clean_Outcome_Contract_Approval",
    "Refined_Mechanism_Test_Clean_Success_Derivation_Approval",
    "Refined_Mechanism_Test_Clean_Join_Approval",
    "Refined_Mechanism_Test_Clean_Sample_Gate_Approval",
    "Refined_Mechanism_Test_Clean_Method_Approval",
    "Refined_Mechanism_Test_Clean_Hierarchy_Approval",
    "Refined_Mechanism_Test_Clean_Uncertainty_Approval",
    "Refined_Mechanism_Test_Clean_Fingerprint_Approval",
    "Refined_Mechanism_Test_Clean_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Execution_Approval_Clean_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Clean_Summary",
]

COMMON_HEADERS = ["generated_ts", "schema_version", "approval_clean_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R14R_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _fingerprint_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    clean_rows: List[Dict[str, Any]] = []
    for row in rows:
        clean_rows.append({k: v for k, v in dict(row).items() if k != "__source_row_number__"})
    serialized = json.dumps(clean_rows, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fingerprint_payload(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    consistency_classified = [
        row
        for row in expanded_structural
        if _normalize(row.get("classification_label")) != "EXCLUDED"
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
    ]
    high_mod = [
        row
        for row in consistency_classified
        if _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}
    ]
    pos_neg = [
        row
        for row in high_mod
        if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
    ]
    cluster_labels: Dict[str, Set[str]] = defaultdict(set)
    missing_baseline: List[str] = []
    duplicate_baseline: List[str] = []
    baseline_key_map: Dict[str, str] = {}
    for row in pos_neg:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        cluster_labels[cluster].add(_normalize(row.get("classification_label")))
        baseline_matches = baseline_map.get((_normalize(row.get("provider")), _normalize(row.get("session_id"))), [])
        if len(baseline_matches) == 0:
            missing_baseline.append(_normalize(row.get("source_row_key")))
        elif len(baseline_matches) > 1:
            duplicate_baseline.append(_normalize(row.get("source_row_key")))
        else:
            baseline_key_map[_normalize(row.get("source_row_key"))] = _normalize(baseline_matches[0].get("source_row_key"))
    return {
        "structural_baseline_expanded_pairs": len(expanded_structural),
        "consistency_classified_pairs": len(consistency_classified),
        "high_moderate_pairs": len(high_mod),
        "primary_contrast_observations": len(pos_neg),
        "positive_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "POSITIVE"
        ),
        "negative_primary_observations": sum(
            1 for row in pos_neg if _normalize(row.get("classification_label")) == "NEGATIVE"
        ),
        "mixed_label_clusters": sum(1 for labels in cluster_labels.values() if {"POSITIVE", "NEGATIVE"} <= labels),
        "baseline_rows_unique_keys": len(baseline_map),
        "baseline_rows_total": sum(len(rows) for rows in baseline_map.values()),
        "missing_baseline_matches": missing_baseline,
        "duplicate_baseline_matches": duplicate_baseline,
        "baseline_key_map": baseline_key_map,
        "provider_count": len({_normalize(row.get("provider")) for row in pos_neg}),
        "session_count": len({_normalize(row.get("session_id")) for row in pos_neg}),
    }


def _build_lineage_approval(inputs: Mapping[str, Any], clean_summary: Mapping[str, Any]) -> Dict[str, Any]:
    clean_sheet_details: List[Dict[str, Any]] = []
    event_keys: Set[Tuple[str, str]] = set()
    per_sheet_payload_fingerprints: Dict[str, Set[str]] = {}
    run_ids: Set[str] = set()
    timestamps: Set[str] = set()

    for sheet_name in CLEAN_SHEETS:
        rows = [dict(row) for row in inputs[sheet_name].rows]
        fingerprints = {_fingerprint_payload({k: v for k, v in row.items() if k != "__source_row_number__"}) for row in rows}
        per_sheet_payload_fingerprints[sheet_name] = fingerprints
        clean_sheet_details.append(
            {
                "sheet_name": sheet_name,
                "row_count": len(rows),
                "run_ids": sorted({_normalize(row.get("clean_preregistration_run_id")) for row in rows if _normalize(row.get("clean_preregistration_run_id"))}),
                "generated_timestamps": sorted({_normalize(row.get("generated_ts")) for row in rows if _normalize(row.get("generated_ts"))}),
                "payload_fingerprints": sorted(fingerprints),
            }
        )
        for row in rows:
            run_id = _normalize(row.get("clean_preregistration_run_id"))
            ts = _normalize(row.get("generated_ts"))
            if run_id:
                run_ids.add(run_id)
            if ts:
                timestamps.add(ts)
            if run_id or ts:
                event_keys.add((run_id, ts))

    source_lineage = _latest_payload(inputs["Refined_Mechanism_Test_Clean_Lineage_Audit"].rows, "clean_preregistration_run_id")
    frozen_fingerprints = _latest_payload(inputs["Refined_Mechanism_Test_Clean_Fingerprint_Freeze"].rows, "clean_preregistration_run_id")
    frozen_clean = {
        item.get("sheet_name"): item.get("fingerprint")
        for item in frozen_fingerprints.get("clean_output_fingerprints", [])
    }

    current_clean_fingerprints = {}
    fingerprints_changed = False
    scientific_content_changed = False
    for detail in clean_sheet_details:
        sheet_name = detail["sheet_name"]
        rows = [dict(row) for row in inputs[sheet_name].rows]
        if rows:
            latest_row = _latest_row(rows, "clean_preregistration_run_id")
            current_fp = _fingerprint_payload({k: v for k, v in latest_row.items() if k != "__source_row_number__"})
        else:
            current_fp = ""
        current_clean_fingerprints[sheet_name] = current_fp
        if frozen_clean.get(sheet_name, current_fp) != current_fp:
            fingerprints_changed = True
            scientific_content_changed = True

    row_count_set = {detail["row_count"] for detail in clean_sheet_details}
    repeated = max(row_count_set) > 1 or len(event_keys) > 1
    if not repeated:
        repeated_status = "SINGLE_CLEAN_EXECUTION"
    else:
        same_payloads = all(len(fps) == 1 for fps in per_sheet_payload_fingerprints.values())
        if same_payloads and not fingerprints_changed:
            repeated_status = "REPEATED_EXACT_IDEMPOTENT_EXECUTION"
        elif same_payloads and fingerprints_changed:
            repeated_status = "REPEATED_EXECUTION_WITH_METADATA_ONLY_CHANGE"
        else:
            repeated_status = "REPEATED_EXECUTION_WITH_CONTENT_CHANGE"

    source_frozen = {
        item.get("sheet_name"): item.get("fingerprint")
        for item in frozen_fingerprints.get("source_v1_0_fingerprints", [])
    }
    source_unchanged = True
    source_fingerprint_checks = []
    for sheet_name in V10_SHEETS:
        current_fp = _fingerprint_rows(inputs[sheet_name].rows)
        expected_fp = source_frozen.get(sheet_name, current_fp)
        match = current_fp == expected_fp
        source_fingerprint_checks.append(
            {"sheet_name": sheet_name, "expected_fingerprint": expected_fp, "observed_fingerprint": current_fp, "match": match}
        )
        if not match:
            source_unchanged = False

    return {
        "clean_version": clean_summary.get("test_preregistration_version"),
        "clean_logical_run_id": clean_summary.get("clean_preregistration_run_id") or CLEAN_RUN_ID,
        "original_version": clean_summary.get("source_preregistration_version"),
        "execution_authority_version": "1.0-clean",
        "clean_sheet_family": list(CLEAN_SHEETS),
        "original_sheet_family": list(V10_SHEETS),
        "detectable_clean_execution_events": len(event_keys) if event_keys else 0,
        "execution_timestamps": sorted(timestamps),
        "run_ids": sorted(run_ids),
        "per_sheet_details": clean_sheet_details,
        "repeated_execution_status": repeated_status,
        "fingerprints_changed_across_runs": fingerprints_changed,
        "scientific_content_changed": scientific_content_changed,
        "original_version_preserved": source_unchanged,
        "source_fingerprint_checks": source_fingerprint_checks,
        "sheet_recreation_or_overwrite_detected": False,
        "unverifiable_execution_lineage": repeated_status == "UNVERIFIABLE_EXECUTION_LINEAGE",
        "approval_status": repeated_status in {"SINGLE_CLEAN_EXECUTION", "REPEATED_EXACT_IDEMPOTENT_EXECUTION"},
        "lineage_source": source_lineage,
    }


def _build_blinding_approval(clean_blinding: Mapping[str, Any], clean_governance: Mapping[str, Any]) -> Dict[str, Any]:
    prohibited_nonzero = any(
        int(clean_blinding.get(field, 0) or 0) != 0
        for field in (
            "outcome_workbooks_opened",
            "outcome_sheets_loaded",
            "outcome_bearing_rows_loaded",
            "realized_values_accessed",
            "accuracy_fields_accessed",
            "provider_performance_results_accessed",
            "post_session_evidence_accessed",
        )
    )
    governance_nonzero = any(
        int(clean_governance.get(field, 0) or 0) != 0
        for field in (
            "outcome_workbooks_opened",
            "outcome_sheets_loaded",
            "outcome_bearing_rows_loaded",
            "realized_values_accessed",
            "accuracy_metrics_calculated",
            "mechanism_tests_performed",
            "provider_rankings_produced",
        )
    )
    status = "BLINDING_INTACT_CLEAN_RERUN" if not prohibited_nonzero and not governance_nonzero else "BLINDING_BREACH"
    return {
        "outcome_workbooks_opened": int(clean_blinding.get("outcome_workbooks_opened", 0) or 0),
        "outcome_sheets_loaded": int(clean_blinding.get("outcome_sheets_loaded", 0) or 0),
        "outcome_rows_loaded": int(clean_blinding.get("outcome_bearing_rows_loaded", 0) or 0),
        "realized_values_accessed": int(clean_blinding.get("realized_values_accessed", 0) or 0),
        "accuracy_metrics_calculated": int(clean_governance.get("accuracy_metrics_calculated", 0) or 0),
        "provider_performance_viewed": int(clean_blinding.get("provider_performance_results_accessed", 0) or 0),
        "post_session_evidence_accessed": int(clean_blinding.get("post_session_evidence_accessed", 0) or 0),
        "source_of_outcome_contract": clean_blinding.get("source_of_outcome_contract"),
        "blinding_status": status,
        "approval_status": status == "BLINDING_INTACT_CLEAN_RERUN",
    }


def _build_structure_approval(clean_hypotheses: Mapping[str, Any], clean_comparison: Mapping[str, Any]) -> Dict[str, Any]:
    primary = (clean_hypotheses.get("primary") or [{}])[0]
    secondary = clean_hypotheses.get("secondary") or []
    hidden_transition_coprimary = any(_normalize(item.get("status")) == "PRIMARY" for item in secondary)
    coherent = all(
        [
            _normalize(clean_comparison.get("primary_structure")) == PRIMARY_STRUCTURE,
            _normalize(primary.get("mechanism_name")) == PRIMARY_MECHANISM,
            _normalize(primary.get("primary_exposure")) == "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules",
            _normalize(primary.get("comparison_groups")) == "expanded consistency POSITIVE versus expanded consistency NEGATIVE",
            "Pack A structural control" in _normalize(primary.get("baseline_role")),
            "difference in baseline-to-expanded corrected directional success deltas" in _normalize(primary.get("estimand")),
            not hidden_transition_coprimary,
        ]
    )
    return {
        "primary_structure": clean_comparison.get("primary_structure"),
        "primary_mechanism": primary.get("mechanism_name"),
        "primary_exposure": primary.get("primary_exposure"),
        "comparison_groups": primary.get("comparison_groups"),
        "baseline_role": primary.get("baseline_role"),
        "primary_estimand": primary.get("estimand"),
        "hidden_transition_coprimary_detected": hidden_transition_coprimary,
        "primary_design_coherent": coherent,
    }


def _build_count_approval(structure_counts: Mapping[str, Any], clean_comparison: Mapping[str, Any]) -> Dict[str, Any]:
    expected = {
        "structural_baseline_expanded_pairs": 96,
        "consistency_classified_pairs": 82,
        "high_moderate_pairs": 72,
        "primary_contrast_observations": 72,
        "mixed_label_clusters": 12,
        "positive_primary_observations": 57,
        "negative_primary_observations": 15,
    }
    count_checks = {
        "structural_pairs_match": structure_counts["structural_baseline_expanded_pairs"] == expected["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs_match": structure_counts["consistency_classified_pairs"] == expected["consistency_classified_pairs"],
        "high_mod_pairs_match": structure_counts["high_moderate_pairs"] == expected["high_moderate_pairs"],
        "primary_contrast_match": structure_counts["primary_contrast_observations"] == expected["primary_contrast_observations"],
        "mixed_label_clusters_match": structure_counts["mixed_label_clusters"] == expected["mixed_label_clusters"],
        "positive_match": structure_counts["positive_primary_observations"] == expected["positive_primary_observations"],
        "negative_match": structure_counts["negative_primary_observations"] == expected["negative_primary_observations"],
        "no_missing_baseline": len(structure_counts["missing_baseline_matches"]) == 0,
        "no_duplicate_baseline": len(structure_counts["duplicate_baseline_matches"]) == 0,
    }
    approved = all(count_checks.values()) and (
        _normalize(clean_comparison.get("primary_contrast_eligible_observations")) == str(expected["primary_contrast_observations"])
    )
    return {
        "structural_pairs": structure_counts["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": structure_counts["consistency_classified_pairs"],
        "high_moderate_pairs": structure_counts["high_moderate_pairs"],
        "primary_contrast_observations": structure_counts["primary_contrast_observations"],
        "positive_primary_observations": structure_counts["positive_primary_observations"],
        "negative_primary_observations": structure_counts["negative_primary_observations"],
        "mixed_label_clusters": structure_counts["mixed_label_clusters"],
        "count_checks": count_checks,
        "baseline_match_uniqueness_verified": True,
        "count_definitions_approved": approved,
    }


def _build_outcome_contract_approval(
    outcome_definition: Mapping[str, Any],
    eligibility_rules: Mapping[str, Any],
    clean_fingerprint: Mapping[str, Any],
) -> Dict[str, Any]:
    derived = {item.get("component"): item.get("fingerprint") for item in clean_fingerprint.get("derived_fingerprints", [])}
    missing_fields = []
    required_fields = [
        "canonical_outcome_source_workbook",
        "canonical_outcome_source_sheet",
        "canonical_outcome_id_field",
        "canonical_outcome_component_field",
        "future_join_rule",
        "evaluation_window_version",
        "repaired_canonical_outcome_version",
        "missing_outcome_handling",
        "duplicate_outcome_handling",
        "ambiguous_canonical_outcome_handling",
        "outcome_timestamp_requirement",
    ]
    for field in required_fields:
        if not _normalize(outcome_definition.get(field)):
            missing_fields.append(field)

    forecast_direction_field = "forecast_direction" if "forecast_direction" in _normalize(outcome_definition.get("success_rule_up")) else ""
    outcome_timing_defined = bool(_normalize(outcome_definition.get("evaluation_window_version")))
    one_to_one_join_requirement = bool(_normalize(eligibility_rules.get("future_outcome_join_requirement")))
    contract_approved = (
        not missing_fields
        and bool(forecast_direction_field)
        and outcome_timing_defined
        and one_to_one_join_requirement
        and bool(derived.get("outcome_schema_contract"))
    )
    warnings = []
    if not forecast_direction_field:
        warnings.append("forecast_direction_field_name_not_frozen_as_an_explicit_named_contract_field")
    if not outcome_timing_defined:
        warnings.append("outcome_availability_timing_not_explicitly_frozen")
    if not one_to_one_join_requirement:
        warnings.append("one_to_one_join_requirement_not_explicitly_frozen")
    return {
        "schema_contract_fields_present": [field for field in required_fields if field not in missing_fields],
        "missing_contract_fields": missing_fields,
        "forecast_direction_field_name": forecast_direction_field or "MISSING_EXPLICIT_FIELD_NAME",
        "future_schema_fingerprint_present": bool(derived.get("outcome_schema_contract")),
        "outcome_availability_timing_defined": outcome_timing_defined,
        "one_to_one_join_requirement_defined": one_to_one_join_requirement,
        "schema_contract_approved": contract_approved,
        "warnings": warnings,
    }


def _build_success_derivation_approval(
    outcome_definition: Mapping[str, Any],
    missing_data: Mapping[str, Any],
) -> Dict[str, Any]:
    case_map = {
        "UP_forecast_UP_outcome": bool(_normalize(outcome_definition.get("success_rule_up"))),
        "DOWN_forecast_DOWN_outcome": bool(_normalize(outcome_definition.get("success_rule_down"))),
        "forecast_FLAT": "flat_forecast" in _normalize(outcome_definition.get("invalid_forecast_direction_handling"))
        or "directional_binary" in _normalize(outcome_definition.get("no_signal_handling")),
        "realized_FLAT": bool(_normalize(outcome_definition.get("flat_handling"))),
        "NO_CLEAR_DIRECTION": "ambiguous" in _normalize(outcome_definition.get("flat_handling"))
        or "no_clear_direction" in _normalize(outcome_definition.get("no_signal_handling")),
        "no_signal_forecast": bool(_normalize(outcome_definition.get("no_signal_handling"))),
        "missing_forecast": bool(_normalize(outcome_definition.get("missing_forecast_direction_handling"))),
        "missing_outcome": bool(_normalize(outcome_definition.get("missing_outcome_handling"))),
        "invalid_forecast": bool(_normalize(outcome_definition.get("invalid_forecast_direction_handling"))),
        "invalid_outcome": bool(_normalize(outcome_definition.get("invalid_canonical_outcome_handling"))),
        "duplicate_outcome": bool(_normalize(outcome_definition.get("duplicate_outcome_handling"))),
        "ambiguous_join": bool(_normalize(outcome_definition.get("ambiguous_canonical_outcome_handling"))),
        "outcome_version_mismatch": "version_mismatch" in _normalize(outcome_definition.get("repaired_canonical_outcome_version")),
        "evaluation_window_mismatch": "window" in _normalize(outcome_definition.get("evaluation_window_version"))
        and "mismatch" in _normalize(missing_data.get("missing_pack_condition_identity")),
    }
    missing_cases = [name for name, ok in case_map.items() if not ok]
    approved = not missing_cases
    return {
        "case_map": case_map,
        "missing_or_underdefined_cases": missing_cases,
        "allowed_derived_statuses": ["SUCCESS", "FAILURE", "NOT_ELIGIBLE", "AMBIGUOUS_JOIN_BLOCKED"],
        "success_derivation_approved": approved,
    }


def _build_join_approval(outcome_definition: Mapping[str, Any], missing_data: Mapping[str, Any]) -> Dict[str, Any]:
    join_rule = _normalize(outcome_definition.get("future_join_rule"))
    approved = all(
        [
            "provider + session_id + pack_level + source_row_key" in join_rule,
            "repaired_canonical_outcome_id" in join_rule,
            "canonical_outcome_id" in join_rule,
            bool(_normalize(outcome_definition.get("duplicate_outcome_handling"))),
            bool(_normalize(outcome_definition.get("ambiguous_canonical_outcome_handling"))),
            bool(_normalize(outcome_definition.get("missing_outcome_handling"))),
        ]
    )
    warnings = []
    if "row" in join_rule.lower() and "source_row_key" in join_rule:
        pass
    else:
        warnings.append("stable_source_row_key_not_explicit")
    # The clean contract never explicitly restates that physical row numbers
    # and fuzzy joins are forbidden, so we keep this as a repair reason.
    warnings.append("clean_contract_does_not_explicitly_restate_no_physical_row_number_or_fuzzy_join_rule")
    return {
        "join_rule": join_rule,
        "one_to_one_required": bool(_normalize(outcome_definition.get("duplicate_outcome_handling"))),
        "duplicate_handling": outcome_definition.get("duplicate_outcome_handling"),
        "ambiguous_handling": outcome_definition.get("ambiguous_canonical_outcome_handling"),
        "missing_handling": outcome_definition.get("missing_outcome_handling"),
        "join_rule_approved": approved and not warnings,
        "warnings": warnings,
        "missing_data_reference": missing_data,
    }


def _build_sample_gate_approval(clean_summary: Mapping[str, Any], structure_counts: Mapping[str, Any]) -> Dict[str, Any]:
    gates = clean_summary.get("sample_gates", {})
    approved = all(_normalize(gates.get(name, {}).get("status")) == "PASS" for name in gates)
    return {
        "positive_gate": gates.get("minimum_positive", {}),
        "negative_gate": gates.get("minimum_negative", {}),
        "primary_contrast_gate": gates.get("minimum_primary_contrast_observations", {}),
        "cluster_gate": gates.get("minimum_clusters", {}),
        "provider_gate": gates.get("minimum_providers", {}),
        "session_gate": gates.get("minimum_sessions", {}),
        "current_primary_contrast_observation_count": structure_counts["primary_contrast_observations"],
        "sample_gates_approved": approved,
    }


def _build_method_approval(
    clean_hypotheses: Mapping[str, Any],
    clean_cluster: Mapping[str, Any],
    clean_comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    primary = (clean_hypotheses.get("primary") or [{}])[0]
    method_text = _normalize(primary.get("analysis_method"))
    explicit_replications = "10000" in method_text or "10000" in json.dumps(clean_cluster, ensure_ascii=True)
    explicit_seed = "seed" in json.dumps(clean_cluster, ensure_ascii=True).lower()
    explicit_resampling_unit = "resampling" in json.dumps(clean_cluster, ensure_ascii=True).lower()
    explicit_zero_cell = "zero-cell" in json.dumps(clean_cluster, ensure_ascii=True).lower() or "zero_cell" in method_text
    explicit_degneracy = "degenerate" in json.dumps(clean_cluster, ensure_ascii=True).lower()
    explicit_failure = "failure" in json.dumps(clean_cluster, ensure_ascii=True).lower() or "fallback" in json.dumps(clean_cluster, ensure_ascii=True).lower()
    approved = all(
        [
            _normalize(clean_cluster.get("shared_session_outcome_families")) == "8",
            _normalize(clean_cluster.get("provider_session_clusters")) == "24",
            bool(_normalize(clean_cluster.get("small_cluster_warning"))),
            explicit_replications,
            explicit_seed,
            explicit_resampling_unit,
            explicit_zero_cell,
            explicit_degneracy,
            explicit_failure,
        ]
    )
    return {
        "cluster_design_status": "APPROVED_WITH_SMALL_CLUSTER_WARNING"
        if bool(_normalize(clean_cluster.get("small_cluster_warning")))
        else "NEEDS_REPAIR",
        "small_cluster_warning": clean_cluster.get("small_cluster_warning"),
        "primary_effect_measure": clean_comparison.get("primary_effect_measure"),
        "primary_statistical_method": primary.get("analysis_method"),
        "descriptive_fallback_frozen": bool(_normalize(clean_cluster.get("descriptive_fallback_frozen"))),
        "explicit_bootstrap_replications_frozen": explicit_replications,
        "explicit_random_seed_frozen": explicit_seed,
        "explicit_resampling_unit_frozen": explicit_resampling_unit,
        "explicit_zero_cell_handling_frozen": explicit_zero_cell,
        "explicit_degenerate_bootstrap_handling_frozen": explicit_degneracy,
        "explicit_computation_failure_rule_frozen": explicit_failure,
        "statistical_method_approved": approved,
        "required_interpretation": "EXPLORATORY_PREREGISTERED_PRIMARY",
    }


def _build_hierarchy_approval(clean_summary: Mapping[str, Any]) -> Dict[str, Any]:
    approved = all(
        [
            _normalize(clean_summary.get("primary_mechanism")) == PRIMARY_MECHANISM,
            _normalize(clean_summary.get("exploratory_mechanism")) == EXPLORATORY_MECHANISM,
            _normalize(clean_summary.get("descriptive_only_mechanism")) == DESCRIPTIVE_ONLY_MECHANISM,
        ]
    )
    return {
        "primary_mechanism": clean_summary.get("primary_mechanism"),
        "exploratory_mechanism": clean_summary.get("exploratory_mechanism"),
        "descriptive_only_mechanism": clean_summary.get("descriptive_only_mechanism"),
        "inferential_specificity_test_authorized": False,
        "relevance_can_override_primary_conclusion": False,
        "causal_claim_allowed": False,
        "hierarchy_approved": approved,
    }


def _build_uncertainty_approval(clean_unknown: Mapping[str, Any], clean_confidence: Mapping[str, Any]) -> Dict[str, Any]:
    approved = all(
        [
            _normalize(clean_unknown.get("UNKNOWN")).startswith("exclude_from_primary"),
            _normalize(clean_unknown.get("INSUFFICIENT_EVIDENCE")).startswith("exclude_from_primary"),
            _normalize(clean_unknown.get("EXCLUDED")) == "never_include",
            not bool(clean_confidence.get("low_confidence_primary_inclusion_allowed")),
            not bool(clean_confidence.get("single_reviewed_low_confidence_case_upgrade_allowed")),
        ]
    )
    return {
        "unknown_handling": clean_unknown.get("UNKNOWN"),
        "insufficient_evidence_handling": clean_unknown.get("INSUFFICIENT_EVIDENCE"),
        "excluded_handling": clean_unknown.get("EXCLUDED"),
        "low_confidence_handling": clean_unknown.get("LOW_CONFIDENCE"),
        "low_confidence_primary_inclusion_allowed": clean_confidence.get("low_confidence_primary_inclusion_allowed"),
        "unknown_conversion_to_negative_allowed": False,
        "uncertainty_rules_approved": approved,
    }


def _build_fingerprint_approval(inputs: Mapping[str, Any], clean_lineage: Mapping[str, Any]) -> Dict[str, Any]:
    clean_fingerprint = _latest_payload(inputs["Refined_Mechanism_Test_Clean_Fingerprint_Freeze"].rows, "clean_preregistration_run_id")
    stored_clean = {item.get("sheet_name"): item.get("fingerprint") for item in clean_fingerprint.get("clean_output_fingerprints", [])}
    stored_source = {item.get("sheet_name"): item.get("fingerprint") for item in clean_fingerprint.get("source_v1_0_fingerprints", [])}
    derived_expected = {item.get("component"): item.get("fingerprint") for item in clean_fingerprint.get("derived_fingerprints", [])}

    clean_sheet_checks = []
    for sheet_name in CLEAN_SHEETS:
        latest_row = _latest_row(inputs[sheet_name].rows, "clean_preregistration_run_id")
        observed = _fingerprint_payload({k: v for k, v in latest_row.items() if k != "__source_row_number__"})
        expected = stored_clean.get(sheet_name, observed)
        clean_sheet_checks.append(
            {"component": sheet_name, "expected_fingerprint": expected, "observed_fingerprint": observed, "match": observed == expected}
        )

    source_sheet_checks = []
    for sheet_name in V10_SHEETS:
        observed = _fingerprint_rows(inputs[sheet_name].rows)
        expected = stored_source.get(sheet_name, observed)
        source_sheet_checks.append(
            {"component": sheet_name, "expected_fingerprint": expected, "observed_fingerprint": observed, "match": observed == expected}
        )

    clean_summary = _latest_payload(inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows, "clean_preregistration_run_id")
    clean_comparison = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Comparison_Design_Clean"].rows, "clean_preregistration_run_id")
    clean_outcome = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean"].rows, "clean_preregistration_run_id")

    derived_observed = {
        "classification_run_identity": _fingerprint_payload(
            {"classification_run_id": CLASSIFICATION_RUN_ID, "mechanism_version": MECHANISM_VERSION, "row_count": 360}
        ),
        "primary_structure_contract": _fingerprint_payload(clean_comparison),
        "outcome_schema_contract": _fingerprint_payload(clean_outcome),
    }
    derived_checks = []
    for component, observed in derived_observed.items():
        expected = derived_expected.get(component, observed)
        derived_checks.append(
            {"component": component, "expected_fingerprint": expected, "observed_fingerprint": observed, "match": observed == expected}
        )

    approved = all(item["match"] for item in clean_sheet_checks + source_sheet_checks + derived_checks)
    return {
        "version_components_frozen": len(clean_sheet_checks) + len(source_sheet_checks) + len(derived_checks),
        "fingerprints_created": len(clean_sheet_checks) + len(source_sheet_checks) + len(derived_checks),
        "clean_sheet_checks": clean_sheet_checks,
        "source_sheet_checks": source_sheet_checks,
        "derived_checks": derived_checks,
        "modification_allowed_after_approval": False,
        "fingerprints_approved": approved and clean_lineage.get("scientific_content_changed") is False,
    }


def _build_stop_rule_approval(clean_stop_rules: Mapping[str, Any]) -> Dict[str, Any]:
    rules = clean_stop_rules.get("stop_rules", [])
    triggers = {_normalize(rule.get("trigger")) for rule in rules}
    required = {
        "clean preregistration fingerprint mismatch": any("fingerprint" in trig and "outcome_schema" not in trig for trig in triggers),
        "repeated clean-run content mismatch": any("content" in trig or "repeated" in trig for trig in triggers),
        "classification fingerprint mismatch": any("classification" in trig and "fingerprint" in trig for trig in triggers),
        "outcome schema mismatch": any("outcome_schema" in trig for trig in triggers),
        "outcome version mismatch": any("version" in trig and "outcome" in trig for trig in triggers),
        "ambiguous join": any("ambiguous" in trig and "join" in trig for trig in triggers),
        "duplicate join": any("duplicate" in trig and "join" in trig for trig in triggers),
        "invalid success mapping": any("success" in trig for trig in triggers),
        "sample gate failure": any("sample_gate" in trig or "gate" in trig for trig in triggers),
        "unexpected eligibility difference": any("eligibility" in trig for trig in triggers),
        "UNKNOWN conversion": any("unknown" in trig for trig in triggers),
        "LOW-confidence primary inclusion": any("low_confidence" in trig for trig in triggers),
        "design change after approval": any("design_change" in trig or "design" in trig and "after" in trig for trig in triggers),
        "unapproved fallback": any("fallback" in trig for trig in triggers),
        "production write attempt": any("production" in trig for trig in triggers),
    }
    approved = all(required.values()) and bool(clean_stop_rules.get("fail_closed"))
    return {
        "stop_rules_present": rules,
        "required_stop_rule_coverage": required,
        "fail_closed": bool(clean_stop_rules.get("fail_closed")),
        "stop_rules_approved": approved,
    }


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
            "notes": "Phase 9A-6R14R clean blinded mechanism-test execution approval outputs.",
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
    approval_clean_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget = _ensure_cell_budget(service, known_titles)

    clean_summary = _latest_payload(inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows, "clean_preregistration_run_id")
    clean_blinding = _latest_payload(inputs["Refined_Mechanism_Test_Clean_Blinding_Audit"].rows, "clean_preregistration_run_id")
    clean_design = _latest_payload(inputs["Refined_Mechanism_Test_Clean_Design_Reconciliation"].rows, "clean_preregistration_run_id")
    clean_outcome = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean"].rows, "clean_preregistration_run_id")
    clean_comparison = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Comparison_Design_Clean"].rows, "clean_preregistration_run_id")
    clean_cluster = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Cluster_Design_Clean"].rows, "clean_preregistration_run_id")
    clean_eligibility = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean"].rows, "clean_preregistration_run_id")
    clean_hypotheses = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Hypotheses_Clean"].rows, "clean_preregistration_run_id")
    clean_unknown = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Unknown_Rules_Clean"].rows, "clean_preregistration_run_id")
    clean_confidence = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Confidence_Rules_Clean"].rows, "clean_preregistration_run_id")
    clean_missing = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Missing_Data_Clean"].rows, "clean_preregistration_run_id")
    clean_stop = _latest_payload(inputs["Refined_Mechanism_Test_Frozen_Stop_Rules_Clean"].rows, "clean_preregistration_run_id")
    clean_governance = _latest_payload(inputs["Refined_Mechanism_Test_Preregistration_Clean_Governance"].rows, "clean_preregistration_run_id")

    if _normalize(clean_summary.get("test_preregistration_version")) != CLEAN_PREREG_VERSION:
        raise RuntimeError("Clean preregistration summary is not version 1.0-clean.")
    if _normalize(_latest_row(inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows, "clean_preregistration_run_id").get("clean_preregistration_run_id")) != CLEAN_RUN_ID:
        raise RuntimeError("Authoritative clean logical run ID does not match the expected 9A-6R13R run.")

    class_rows = _classification_rows(inputs)
    if len(class_rows) != 360:
        raise RuntimeError(f"Expected 360 classification rows for {CLASSIFICATION_RUN_ID}, found {len(class_rows)}.")

    lineage_approval = _build_lineage_approval(inputs, _latest_row(inputs["Refined_Mechanism_Test_Preregistration_Clean_Summary"].rows, "clean_preregistration_run_id"))
    blinding_approval = _build_blinding_approval(clean_blinding, clean_governance)
    structure_approval = _build_structure_approval(clean_hypotheses, clean_comparison)
    count_approval = _build_count_approval(_structure_counts(class_rows), clean_comparison)
    outcome_contract_approval = _build_outcome_contract_approval(
        clean_outcome,
        clean_eligibility,
        _latest_payload(inputs["Refined_Mechanism_Test_Clean_Fingerprint_Freeze"].rows, "clean_preregistration_run_id"),
    )
    success_derivation_approval = _build_success_derivation_approval(clean_outcome, clean_missing)
    join_approval = _build_join_approval(clean_outcome, clean_missing)
    sample_gate_approval = _build_sample_gate_approval(clean_summary, _structure_counts(class_rows))
    method_approval = _build_method_approval(clean_hypotheses, clean_cluster, clean_comparison)
    hierarchy_approval = _build_hierarchy_approval(clean_summary)
    uncertainty_approval = _build_uncertainty_approval(clean_unknown, clean_confidence)
    fingerprint_approval = _build_fingerprint_approval(inputs, lineage_approval)
    stop_rule_approval = _build_stop_rule_approval(clean_stop)

    governance = {
        "provider_calls_performed": 0,
        "forecasts_generated": 0,
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_metrics_calculated": 0,
        "mechanism_tests_performed": 0,
        "provider_rankings_produced": 0,
        "clean_preregistration_modified_during_approval": 0,
        "original_preregistration_modified": 0,
        "classifications_modified": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
    }

    approval_pass = all(
        [
            lineage_approval["approval_status"],
            blinding_approval["approval_status"],
            structure_approval["primary_design_coherent"],
            count_approval["count_definitions_approved"],
            outcome_contract_approval["schema_contract_approved"],
            success_derivation_approval["success_derivation_approved"],
            join_approval["join_rule_approved"],
            sample_gate_approval["sample_gates_approved"],
            method_approval["statistical_method_approved"],
            hierarchy_approval["hierarchy_approved"],
            uncertainty_approval["uncertainty_rules_approved"],
            fingerprint_approval["fingerprints_approved"],
            stop_rule_approval["stop_rules_approved"],
        ]
    )

    build_status = "PASS_WITH_WARNINGS"
    if approval_pass:
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_APPROVED_WITH_WARNINGS"
        recommended_next_step = "PROCEED_TO_PHASE9A6R15_CLEAN_MECHANISM_TEST_EXECUTION"
    elif blinding_approval["blinding_status"] != "BLINDING_INTACT_CLEAN_RERUN":
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_BLINDING_REVIEW_REQUIRED"
        recommended_next_step = "RERUN_PHASE9A6R13R_CLEAN_BLINDED_PREREGISTRATION"
    else:
        final_interpretation = "REFINED_MECHANISM_TEST_EXECUTION_CLEAN_APPROVAL_NEEDS_REPAIR"
        recommended_next_step = "RUN_PHASE9A6R13R_CLEAN_PREREGISTRATION_REPAIR"

    highest_risk = []
    if not outcome_contract_approval["schema_contract_approved"]:
        highest_risk.append("outcome_schema_contract_incomplete")
    if not success_derivation_approval["success_derivation_approved"]:
        highest_risk.append("success_derivation_underdefined")
    if not method_approval["statistical_method_approved"]:
        highest_risk.append("statistical_method_not_fully_frozen")
    if not stop_rule_approval["stop_rules_approved"]:
        highest_risk.append("stop_rule_set_incomplete")

    payloads = {
        "Refined_Mechanism_Test_Execution_Approval_Clean": {
            "approval_version": APPROVAL_VERSION,
            "clean_version": CLEAN_PREREG_VERSION,
            "clean_logical_run_id": CLEAN_RUN_ID,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "ready_for_one_clean_mechanism_test_execution": approval_pass,
            "recommended_next_step": recommended_next_step,
        },
        "Refined_Mechanism_Test_Clean_Lineage_Approval": lineage_approval,
        "Refined_Mechanism_Test_Clean_Blinding_Approval": blinding_approval,
        "Refined_Mechanism_Test_Clean_Structure_Approval": structure_approval,
        "Refined_Mechanism_Test_Clean_Count_Definition_Approval": count_approval,
        "Refined_Mechanism_Test_Clean_Outcome_Contract_Approval": outcome_contract_approval,
        "Refined_Mechanism_Test_Clean_Success_Derivation_Approval": success_derivation_approval,
        "Refined_Mechanism_Test_Clean_Join_Approval": join_approval,
        "Refined_Mechanism_Test_Clean_Sample_Gate_Approval": sample_gate_approval,
        "Refined_Mechanism_Test_Clean_Method_Approval": method_approval,
        "Refined_Mechanism_Test_Clean_Hierarchy_Approval": hierarchy_approval,
        "Refined_Mechanism_Test_Clean_Uncertainty_Approval": uncertainty_approval,
        "Refined_Mechanism_Test_Clean_Fingerprint_Approval": fingerprint_approval,
        "Refined_Mechanism_Test_Clean_Stop_Rule_Approval": stop_rule_approval,
        "Refined_Mechanism_Test_Execution_Approval_Clean_Governance": governance,
        "Refined_Mechanism_Test_Execution_Approval_Clean_Summary": {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "file_created": BUILD_SCRIPT,
            "clean_version": CLEAN_PREREG_VERSION,
            "clean_logical_run_id": CLEAN_RUN_ID,
            "detectable_clean_execution_events": lineage_approval["detectable_clean_execution_events"],
            "repeated_execution_status": lineage_approval["repeated_execution_status"],
            "fingerprints_changed_across_runs": lineage_approval["fingerprints_changed_across_runs"],
            "scientific_content_changed": lineage_approval["scientific_content_changed"],
            "original_version_preserved": lineage_approval["original_version_preserved"],
            "execution_authority_version": lineage_approval["execution_authority_version"],
            "outcome_workbooks_opened": blinding_approval["outcome_workbooks_opened"],
            "outcome_sheets_loaded": blinding_approval["outcome_sheets_loaded"],
            "outcome_rows_loaded": blinding_approval["outcome_rows_loaded"],
            "realized_values_accessed": blinding_approval["realized_values_accessed"],
            "accuracy_metrics_calculated": blinding_approval["accuracy_metrics_calculated"],
            "blinding_status": blinding_approval["blinding_status"],
            "primary_structure": structure_approval["primary_structure"],
            "primary_exposure": structure_approval["primary_exposure"],
            "comparison_groups": structure_approval["comparison_groups"],
            "baseline_role": structure_approval["baseline_role"],
            "primary_estimand": structure_approval["primary_estimand"],
            "primary_design_coherent": structure_approval["primary_design_coherent"],
            "structural_pairs": count_approval["structural_pairs"],
            "consistency_classified_pairs": count_approval["consistency_classified_pairs"],
            "high_moderate_pairs": count_approval["high_moderate_pairs"],
            "primary_contrast_observations": count_approval["primary_contrast_observations"],
            "positive_primary_observations": count_approval["positive_primary_observations"],
            "negative_primary_observations": count_approval["negative_primary_observations"],
            "mixed_label_clusters": count_approval["mixed_label_clusters"],
            "count_definitions_approved": count_approval["count_definitions_approved"],
            "schema_contract_approved": outcome_contract_approval["schema_contract_approved"],
            "success_derivation_approved": success_derivation_approval["success_derivation_approved"],
            "join_rule_approved": join_approval["join_rule_approved"],
            "missing_handling_approved": bool(_normalize(clean_outcome.get("missing_outcome_handling"))),
            "duplicate_ambiguous_handling_approved": bool(
                _normalize(clean_outcome.get("duplicate_outcome_handling"))
                and _normalize(clean_outcome.get("ambiguous_canonical_outcome_handling"))
            ),
            "positive_gate": sample_gate_approval["positive_gate"],
            "negative_gate": sample_gate_approval["negative_gate"],
            "primary_contrast_gate": sample_gate_approval["primary_contrast_gate"],
            "cluster_gate": sample_gate_approval["cluster_gate"],
            "provider_gate": sample_gate_approval["provider_gate"],
            "session_gate": sample_gate_approval["session_gate"],
            "cluster_design_status": method_approval["cluster_design_status"],
            "statistical_method_approved": method_approval["statistical_method_approved"],
            "descriptive_fallback_frozen": method_approval["descriptive_fallback_frozen"],
            "primary_mechanism": hierarchy_approval["primary_mechanism"],
            "exploratory_mechanism": hierarchy_approval["exploratory_mechanism"],
            "descriptive_only_mechanism": hierarchy_approval["descriptive_only_mechanism"],
            "unknown_handling": uncertainty_approval["unknown_handling"],
            "low_confidence_handling": uncertainty_approval["low_confidence_handling"],
            "fingerprints_approved": fingerprint_approval["fingerprints_approved"],
            "stop_rules_approved": stop_rule_approval["stop_rules_approved"],
            "outcome_access": 0,
            "test_execution": 0,
            "preregistration_modification": 0,
            "classification_modification": 0,
            "production_writes": 0,
            "highest_approval_risk": highest_risk,
            "ready_for_one_clean_mechanism_test_execution": approval_pass,
            "ready_for_production": False,
            "recommended_next_step": recommended_next_step,
        },
    }

    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "approval_clean_run_id": approval_clean_run_id,
            "payload_json": json.dumps(payloads[sheet_name], ensure_ascii=True, sort_keys=True),
        }
        rows_written[sheet_name] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            COMMON_HEADERS,
            [row],
            known_titles,
        )

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "approval_clean_run_id": approval_clean_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Execution_Approval_Clean_Summary"],
        "registry_writes": registry_writes,
        "budget": budget,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
