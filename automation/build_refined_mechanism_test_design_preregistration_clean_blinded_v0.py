#!/usr/bin/env python3
"""Phase 9A-6R13R — Clean Blinded Mechanism Test Preregistration.

This phase rebuilds the refined mechanism test preregistration as a separate,
clean, outcome-blinded version after Phase 9A-6R14 determined that the prior
v1.0 freeze could not prove blinding integrity because of external manual
schema contact. The clean rerun preserves the intended scientific design while
freezing it under a new versioned preregistration family with zero outcome
sheet access, zero outcome-row loads, and no modifications to the original
v1.0 preregistration.
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


PHASE_ID = "9A-6R13R"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_design_preregistration_clean_blinded_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_preregistration_clean_blinded_v0"
PREREGISTRATION_VERSION = "refined_mechanism_test_preregistration_clean_blinded_v0"
TEST_PREREGISTRATION_VERSION = "1.0-clean"
SOURCE_TEST_PREREGISTRATION_VERSION = "1.0"
TEST_PREREGISTRATION_STATUS = "FROZEN"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_PREREGISTRATION_CLEAN"
REGISTRY_OWNER_MODULE = "market_state"

CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"
PRIMARY_MECHANISM_ID = "PM-003"
EXPLORATORY_MECHANISM_ID = "PM-001"
DESCRIPTIVE_ONLY_MECHANISM_ID = "PM-002"

PRIMARY_STRUCTURE = "STRUCTURE_A_EXPANDED_STATE_GROUPED_DELTA_COMPARISON"
PRIMARY_UNIT_OF_ANALYSIS = "provider_session_pack_forecast_observation"
MATCHING_KEY = "provider + session_id + baseline_pack_A_source_row_key + expanded_pack_source_row_key"
CLUSTERING_LEVEL = "provider_session_cluster_nested_within_shared_session_outcome_family"
PRIMARY_COMPARISON = "STRUCTURE_A_EXPANDED_CONSISTENCY_POSITIVE_VS_NEGATIVE_WITH_MATCHED_PACK_A_DELTA_CONTROL"
SECONDARY_COMPARISON = "MIXED_LABEL_PROVIDER_SESSION_CLUSTER_CONSISTENCY_SENSITIVITY"
EXPLORATORY_RELEVANCE_DESIGN = "WITHIN_PROVIDER_SESSION_MATCHED_POSITIVE_VS_NEGATIVE_RELEVANCE_SENSITIVITY"
SPECIFICITY_STATUS = "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION"
PRIMARY_EFFECT_MEASURE = "matched_baseline_to_expanded_corrected_directional_success_delta_difference"
PRIMARY_STATISTICAL_METHOD = (
    "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta_"
    "with_two_sided_95pct_cluster_bootstrap_interval_and_descriptive_fallback_if_sparse"
)
PRIMARY_OUTCOME_SOURCE = "DIAGNOSTICS.Market_Reaction_Canonical_Outcomes"
PRIMARY_OUTCOME_FIELD = "canonical_realized_direction"
OUTCOME_JOIN_RULE = (
    "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id"
)

PRIMARY_SAMPLE_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_primary_contrast_observations": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
}

SOURCE_V10_SHEETS: Tuple[str, ...] = (
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
    # Original v1.0 preregistration family, read-only for lineage.
    *SOURCE_V10_SHEETS,
    # Planning-readiness evidence.
    "Refined_Mechanism_Test_Planning_Readiness",
    "Refined_Mechanism_Test_Unit_Of_Analysis",
    "Refined_Mechanism_Test_Label_Eligibility",
    "Refined_Mechanism_Test_Comparison_Design",
    "Refined_Mechanism_Test_Confounder_Map",
    "Refined_Mechanism_Test_Independence_Audit",
    "Refined_Mechanism_Test_Sample_Adequacy",
    "Refined_Mechanism_Test_Unknown_Handling",
    "Refined_Mechanism_Test_Confidence_Handling",
    "Refined_Mechanism_Test_Planning_Readiness_Summary",
    # Phase 9A-6R14 approval evidence. These payloads resolved the structure
    # ambiguity without requiring any outcome-sheet access here.
    "Refined_Mechanism_Test_Execution_Approval",
    "Refined_Mechanism_Test_Blinding_Audit",
    "Refined_Mechanism_Test_Matched_Pair_Reconciliation",
    "Refined_Mechanism_Test_Primary_Estimand_Audit",
    "Refined_Mechanism_Test_Outcome_Derivation_Audit",
    "Refined_Mechanism_Test_Join_Approval",
    "Refined_Mechanism_Test_Sample_Gate_Approval",
    "Refined_Mechanism_Test_Cluster_Design_Approval",
    "Refined_Mechanism_Test_Statistical_Method_Approval",
    "Refined_Mechanism_Test_Fingerprint_Freeze",
    "Refined_Mechanism_Test_Stop_Rule_Approval",
    "Refined_Mechanism_Test_Execution_Approval_Governance",
    "Refined_Mechanism_Test_Execution_Approval_Summary",
    # Permanent classifications and execution review.
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Summary",
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
)

OUTPUT_SHEETS = [
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
]

COMMON_HEADERS = ["generated_ts", "schema_version", "clean_preregistration_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _run_id(ts: datetime) -> str:
    return f"9A-6R13R_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _structure_a_counts(class_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    consistency_rows = [
        dict(row)
        for row in class_rows
        if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM
    ]
    baseline_pairs = {
        (_normalize(row.get("provider")), _normalize(row.get("session_id"))): row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) == "A"
    }
    expanded_structural = [
        row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) in {"B", "C", "D", "E"}
        and (_normalize(row.get("provider")), _normalize(row.get("session_id"))) in baseline_pairs
    ]
    consistency_classified = [
        row
        for row in expanded_structural
        if _normalize(row.get("classification_label")) != "EXCLUDED"
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
    ]
    high_moderate = [
        row
        for row in consistency_classified
        if _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}
    ]
    pos_neg = [
        row
        for row in high_moderate
        if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
    ]
    cluster_labels: Dict[str, Set[str]] = defaultdict(set)
    for row in pos_neg:
        cluster = f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        cluster_labels[cluster].add(_normalize(row.get("classification_label")))
    mixed_clusters = sorted(
        cluster for cluster, labels in cluster_labels.items() if {"POSITIVE", "NEGATIVE"} <= labels
    )
    provider_count = len({_normalize(row.get("provider")) for row in pos_neg})
    session_count = len({_normalize(row.get("session_id")) for row in pos_neg})
    cluster_counter = Counter(
        f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}" for row in pos_neg
    )
    max_cluster_share = (
        max(cluster_counter.values()) / len(pos_neg) if pos_neg and cluster_counter else 0.0
    )
    return {
        "structural_baseline_expanded_pairs": len(expanded_structural),
        "consistency_classified_pairs": len(consistency_classified),
        "high_moderate_confidence_pairs": len(high_moderate),
        "positive_or_negative_eligible_pairs": len(pos_neg),
        "positive_count": sum(1 for row in pos_neg if _normalize(row.get("classification_label")) == "POSITIVE"),
        "negative_count": sum(1 for row in pos_neg if _normalize(row.get("classification_label")) == "NEGATIVE"),
        "mixed_positive_negative_provider_session_clusters": len(mixed_clusters),
        "mixed_cluster_keys": mixed_clusters,
        "primary_contrast_eligible_observations": len(pos_neg),
        "provider_count": provider_count,
        "session_count": session_count,
        "max_cluster_share": max_cluster_share,
    }


def _label_counts_for_mechanism(class_rows: Sequence[Mapping[str, Any]], mechanism: str) -> Dict[str, int]:
    rows = [row for row in class_rows if _normalize(row.get("mechanism_id")) == mechanism]
    counts = Counter(_normalize(row.get("classification_label")) for row in rows)
    return {
        "positive": counts.get("POSITIVE", 0),
        "negative": counts.get("NEGATIVE", 0),
        "unknown": counts.get("UNKNOWN", 0),
        "insufficient_evidence": counts.get("INSUFFICIENT_EVIDENCE", 0),
        "excluded": counts.get("EXCLUDED", 0),
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
            "notes": "Phase 9A-6R13R clean blinded mechanism-test preregistration outputs.",
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
    clean_preregistration_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget_maintenance = _ensure_cell_budget(service, known_titles)

    prereg_summary_v10 = _latest_payload(
        inputs["Refined_Mechanism_Test_Preregistration_Summary"].rows,
        "preregistration_run_id",
    )
    if _normalize(prereg_summary_v10.get("test_preregistration_version")) != SOURCE_TEST_PREREGISTRATION_VERSION:
        raise RuntimeError("Original v1.0 preregistration summary is missing or not version 1.0.")
    if _normalize(prereg_summary_v10.get("preregistration_status")) != "FROZEN":
        raise RuntimeError("Original v1.0 preregistration is not frozen.")

    approval_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Execution_Approval_Summary"].rows,
        "approval_run_id",
    )
    if _normalize(approval_summary.get("recommended_next_step")) != "RERUN_PHASE9A6R13_CLEAN_BLINDED_PREREGISTRATION":
        raise RuntimeError("Phase 9A-6R14 did not direct a clean blinded preregistration rerun.")

    planning_summary = _latest_payload(
        inputs["Refined_Mechanism_Test_Planning_Readiness_Summary"].rows,
        "readiness_run_id",
    )
    label_eligibility = _latest_payload(inputs["Refined_Mechanism_Test_Label_Eligibility"].rows, "readiness_run_id")
    sample_adequacy = _latest_payload(inputs["Refined_Mechanism_Test_Sample_Adequacy"].rows, "readiness_run_id")
    unknown_handling_v12 = _latest_payload(inputs["Refined_Mechanism_Test_Unknown_Handling"].rows, "readiness_run_id")
    confidence_handling_v12 = _latest_payload(inputs["Refined_Mechanism_Test_Confidence_Handling"].rows, "readiness_run_id")
    confounder_map_v12 = _latest_payload(inputs["Refined_Mechanism_Test_Confounder_Map"].rows, "readiness_run_id")

    pair_reconciliation_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Matched_Pair_Reconciliation"].rows,
        "approval_run_id",
    )
    estimand_audit_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Primary_Estimand_Audit"].rows,
        "approval_run_id",
    )
    outcome_derivation_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Outcome_Derivation_Audit"].rows,
        "approval_run_id",
    )
    join_approval_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Join_Approval"].rows,
        "approval_run_id",
    )
    sample_gate_approval_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Sample_Gate_Approval"].rows,
        "approval_run_id",
    )
    cluster_approval_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Cluster_Design_Approval"].rows,
        "approval_run_id",
    )
    statistical_approval_v14 = _latest_payload(
        inputs["Refined_Mechanism_Test_Statistical_Method_Approval"].rows,
        "approval_run_id",
    )

    class_rows = _classification_rows(inputs)
    if len(class_rows) != 360:
        raise RuntimeError(f"Expected 360 permanent classification rows for {CLASSIFICATION_RUN_ID}, found {len(class_rows)}.")

    label_distribution = Counter(_normalize(row.get("classification_label")) for row in class_rows)
    unique_source_rows = len({_normalize(row.get("source_row_key")) for row in class_rows})
    unique_providers = len({_normalize(row.get("provider")) for row in class_rows})
    unique_sessions = len({_normalize(row.get("session_id")) for row in class_rows})
    unique_forecast_runs = unique_source_rows

    structure = _structure_a_counts(class_rows)
    expected_structure = {
        "structural_baseline_expanded_pairs": 96,
        "consistency_classified_pairs": 82,
        "high_moderate_confidence_pairs": 72,
        "positive_or_negative_eligible_pairs": 72,
        "positive_count": 57,
        "negative_count": 15,
        "mixed_positive_negative_provider_session_clusters": 12,
        "provider_count": 3,
        "session_count": 8,
    }
    for key, expected in expected_structure.items():
        if structure.get(key) != expected:
            raise RuntimeError(
                f"Structure A reconstruction mismatch for {key}: expected {expected}, observed {structure.get(key)}."
            )
    if structure["positive_or_negative_eligible_pairs"] != pair_reconciliation_v14.get("primary_contrast_eligible_pairs"):
        raise RuntimeError("Recomputed primary contrast count does not match Phase 9A-6R14 reconciliation.")

    mechanism_counts = {
        PRIMARY_MECHANISM: _label_counts_for_mechanism(class_rows, PRIMARY_MECHANISM),
        EXPLORATORY_MECHANISM: _label_counts_for_mechanism(class_rows, EXPLORATORY_MECHANISM),
        DESCRIPTIVE_ONLY_MECHANISM: _label_counts_for_mechanism(class_rows, DESCRIPTIVE_ONLY_MECHANISM),
    }
    mechanism_stats = planning_summary.get("mechanism_stats", {})

    primary_hypothesis = {
        "hypothesis_id": "RMTP-CLEAN-H1",
        "mechanism_id": PRIMARY_MECHANISM_ID,
        "mechanism_name": PRIMARY_MECHANISM,
        "structure_id": PRIMARY_STRUCTURE,
        "hypothesis_text": (
            "Among expanded Pack B-E provider_session_pack_forecast_observations with matched same-provider "
            "same-session Pack A structural controls and eligible high/moderate consistency classifications, "
            "the baseline-to-expanded corrected directional success delta differs between observations whose "
            "expanded consistency label is POSITIVE and observations whose expanded consistency label is NEGATIVE."
        ),
        "directionality": "NON_DIRECTIONAL",
        "primary_exposure": "expanded Pack B-E MECH_INFORMATION_CONSISTENCY label under frozen v1.1 rules",
        "comparison_groups": "expanded consistency POSITIVE versus expanded consistency NEGATIVE",
        "baseline_role": "same-provider same-session Pack A structural control used only for success-delta construction",
        "expanded_role": "mechanism-classified Pack B-E forecast observation",
        "estimand": "difference in baseline-to-expanded corrected directional success deltas between expanded-state label groups",
        "effect_measure": PRIMARY_EFFECT_MEASURE,
        "analysis_method": PRIMARY_STATISTICAL_METHOD,
        "confidence_inclusion": "HIGH_AND_MODERATE_ONLY",
        "multiple_testing_family": "PRIMARY_FAMILY_PM003_ONLY",
    }

    secondary_hypotheses = [
        {
            "hypothesis_id": "RMTP-CLEAN-H2",
            "mechanism_id": PRIMARY_MECHANISM_ID,
            "mechanism_name": PRIMARY_MECHANISM,
            "comparison": (
                "descriptive or sensitivity analysis within the 12 mixed-label provider-session clusters "
                "that contain both expanded consistency-positive and expanded consistency-negative observations"
            ),
            "status": "SECONDARY_STRUCTURAL_SENSITIVITY",
            "notes": (
                "The 12 mixed-label provider-session clusters are a structural count only and do not replace the "
                "72 primary-contrast eligible expanded observations."
            ),
        }
    ]

    exploratory_hypotheses = [
        {
            "hypothesis_id": "RMTP-CLEAN-E1",
            "mechanism_id": EXPLORATORY_MECHANISM_ID,
            "mechanism_name": EXPLORATORY_MECHANISM,
            "comparison": "within-provider-session matched relevance positive versus negative sensitivity analysis",
            "status": "EXPLORATORY_ONLY",
            "notes": "Negative class remains thin and collinear; no confirmatory inference.",
        },
        {
            "hypothesis_id": "RMTP-CLEAN-E2",
            "mechanism_id": DESCRIPTIVE_ONLY_MECHANISM_ID,
            "mechanism_name": DESCRIPTIVE_ONLY_MECHANISM,
            "comparison": "descriptive specificity label-outcome table only",
            "status": "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION",
            "notes": "Specificity remains descriptive/sample-expansion-only and never enters a primary binary test.",
        },
    ]

    outcome_definition = {
        "schema_contract_only": True,
        "schema_contract_sources": [
            "Refined_Mechanism_Test_Frozen_Outcome_Definition",
            "Refined_Mechanism_Test_Outcome_Derivation_Audit",
            "Refined_Mechanism_Test_Join_Approval",
        ],
        "no_outcome_sheet_loaded_by_clean_builder": True,
        "canonical_outcome_source_workbook": "DIAGNOSTICS",
        "canonical_outcome_source_sheet": "Market_Reaction_Canonical_Outcomes",
        "canonical_outcome_id_field": "canonical_outcome_id",
        "canonical_outcome_component_field": PRIMARY_OUTCOME_FIELD,
        "outcome_metric_id": "CORRECTED_DIRECTIONAL_SUCCESS_BINARY",
        "future_join_rule": OUTCOME_JOIN_RULE,
        "success_rule_up": "forecast_direction=UP and canonical_realized_direction=UP => success",
        "success_rule_down": "forecast_direction=DOWN and canonical_realized_direction=DOWN => success",
        "flat_handling": "exclude_flat_or_ambiguous_realized_direction_from_primary_binary_analysis_and_report_descriptively",
        "no_signal_handling": (
            "exclude_from_primary_directional_binary_and_report_descriptively_unless_a_future_no_signal_metric_"
            "is_separately_preregistered"
        ),
        "missing_forecast_direction_handling": "exclude_and_report_missing_forecast_direction",
        "duplicate_outcome_handling": "block_ambiguous_join_and_exclude_until_resolved_under_frozen_rule",
        "invalid_forecast_direction_handling": "exclude_and_report_invalid_output",
        "invalid_canonical_outcome_handling": "exclude_and_report_invalid_canonical_outcome",
        "ambiguous_canonical_outcome_handling": "exclude_without_manual_matching",
        "missing_outcome_handling": "exclude_from_inferential_analysis_and_report_reason",
        "provider_neutrality_rule": "one_canonical_corrected_outcome_per_session_window_no_provider_specific_remapping",
        "evaluation_window_version": outcome_derivation_v14.get("evaluation_window_version"),
        "repaired_canonical_outcome_version": outcome_derivation_v14.get("repaired_canonical_outcome_version"),
        "post_outcome_mapping_choice_allowed": False,
    }

    comparison_design = {
        "primary_structure": PRIMARY_STRUCTURE,
        "primary_comparison_id": PRIMARY_COMPARISON,
        "primary_exposure": estimand_audit_v14.get("treatment_exposure_variable"),
        "primary_comparison_groups": estimand_audit_v14.get("comparison_groups"),
        "baseline_role": estimand_audit_v14.get("baseline_role"),
        "expanded_role": estimand_audit_v14.get("expanded_pack_role"),
        "matched_pair_role": estimand_audit_v14.get("matched_pair_role"),
        "primary_estimand": estimand_audit_v14.get("contrast"),
        "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
        "primary_statistical_method": PRIMARY_STATISTICAL_METHOD,
        "primary_contrast_eligible_observations": structure["primary_contrast_eligible_observations"],
        "mixed_label_provider_session_clusters": structure["mixed_positive_negative_provider_session_clusters"],
        "structural_baseline_expanded_pairs": structure["structural_baseline_expanded_pairs"],
        "consistency_classified_pairs": structure["consistency_classified_pairs"],
        "high_moderate_confidence_pairs": structure["high_moderate_confidence_pairs"],
        "informative_transition_pairs": 0,
        "transition_language_rule": (
            "Pack A has no mechanism label; any true label-transition interpretation is forbidden in the primary design. "
            "The only approved primary interpretation is Structure A grouped delta comparison."
        ),
        "secondary_design": SECONDARY_COMPARISON,
        "exploratory_relevance_design": EXPLORATORY_RELEVANCE_DESIGN,
    }

    cluster_design = {
        "primary_unit_of_analysis": PRIMARY_UNIT_OF_ANALYSIS,
        "matching_key": MATCHING_KEY,
        "required_clustering_level": CLUSTERING_LEVEL,
        "provider_session_clusters": planning_summary.get("independent_clusters", 24),
        "shared_session_outcome_families": unique_sessions,
        "baseline_expanded_observations_handled": True,
        "multiple_providers_sharing_one_session_outcome_handled": True,
        "multiple_mechanisms_per_forecast_handled": True,
        "small_cluster_warning": cluster_approval_v14.get("small_cluster_warning"),
        "descriptive_fallback_frozen": True,
        "fallback_rule": (
            "If cluster bootstrap is unreliable or degenerate, report descriptive effect estimates with uncertainty notes "
            "and do not introduce a new post-hoc inferential method."
        ),
    }

    eligibility_rules = {
        "classification_run_id": CLASSIFICATION_RUN_ID,
        "mechanism_version": MECHANISM_VERSION,
        "primary_mechanism": PRIMARY_MECHANISM,
        "positive_eligible_rule": "expanded Pack B-E PM-003 POSITIVE with HIGH|MODERATE confidence and matched Pack A control",
        "negative_eligible_rule": "expanded Pack B-E PM-003 NEGATIVE with HIGH|MODERATE confidence and matched Pack A control",
        "primary_contrast_count_unit": "expanded Pack B-E PM-003 POSITIVE_or_NEGATIVE forecast observations with matched Pack A structural controls",
        "primary_contrast_eligible_observations": structure["primary_contrast_eligible_observations"],
        "positive_eligible_count": structure["positive_count"],
        "negative_eligible_count": structure["negative_count"],
        "future_outcome_join_requirement": "one classification observation must map deterministically to one canonical corrected outcome",
        "duplicate_forecast_observations": "exclude_from_primary_analysis",
        "invalid_output": "exclude",
        "mixed_label_cluster_count": structure["mixed_positive_negative_provider_session_clusters"],
        "mixed_label_cluster_unit": "provider_session clusters containing both expanded PM-003 POSITIVE and NEGATIVE observations",
        "mechanism_hierarchy": {
            PRIMARY_MECHANISM: "PRIMARY_ONLY",
            EXPLORATORY_MECHANISM: "EXPLORATORY_ONLY",
            DESCRIPTIVE_ONLY_MECHANISM: "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION",
        },
    }

    confidence_rules = {
        "primary_analysis": "HIGH_AND_MODERATE_ONLY",
        "sensitivity_analysis": "LOW_CONFIDENCE_INCLUDED_ONLY_IF_EXPLICITLY_PREREGISTERED",
        "unknown_confidence": "EXCLUDE_UNLESS_SEPARATELY_JUSTIFIED",
        "low_confidence_primary_inclusion_allowed": False,
        "single_reviewed_low_confidence_case_upgrade_allowed": False,
        "planning_confidence_reference": confidence_handling_v12 or planning_summary.get("confidence_handling", {}),
    }

    unknown_rules = {
        "UNKNOWN": "exclude_from_primary_binary_test_and_report_descriptively",
        "INSUFFICIENT_EVIDENCE": "exclude_from_primary_binary_test_and_report_descriptively",
        "EXCLUDED": "never_include",
        "NEGATIVE": "affirmative_absence_only_not_missingness",
        "LOW_CONFIDENCE": "excluded_from_primary_and_allowed_only_in_frozen_sensitivity_analysis",
        "unknown_is_not_negative": True,
        "insufficient_is_not_negative": True,
        "post_outcome_reclassification_allowed": False,
        "planning_unknown_reference": unknown_handling_v12 or planning_summary.get("unknown_handling", {}),
    }

    confounder_rules = {
        "required_controls": [
            "provider_identity",
            "session_identity",
            "pack_condition",
            "shared_session_outcome_family",
            "model_version_where_available",
            "classification_confidence_category",
            "repeated_provider_session_observations",
        ],
        "descriptive_or_sensitivity_controls": [
            "mechanism_co_occurrence",
            "session_or_event_family",
            "no_signal_state",
            "source_evidence_completeness",
        ],
        "prohibited_modeling": "high_dimensional_regression_exceeding_small_cluster_capacity",
        "source_confounder_map": confounder_map_v12,
    }

    multiple_testing = {
        "primary_family": "PM-003 consistency only",
        "secondary_family": "consistency structural sensitivity only",
        "exploratory_family": "relevance only",
        "descriptive_family": "specificity only",
        "hidden_co_primary_mechanisms": False,
        "hidden_co_primary_outcomes": False,
        "familywise_primary_claim_count": 1,
    }

    missing_data = {
        "missing_outcome": "exclude_from_inferential_analysis_and_report_reason",
        "duplicate_outcome": "block_or_exclude_per_frozen_duplicate_rule",
        "ambiguous_join": "exclude_without_manual_matching",
        "missing_provider_session_pair": "exclude_from_matched_designs",
        "missing_baseline_or_expanded_observation": "exclude_from_primary_delta_design",
        "invalid_forecast_output": "exclude",
        "incomplete_classification_trace": "block_test_execution_until_trace_repair",
        "missing_pack_condition_identity": "exclude_and_report_scope_failure",
        "imputation_rule": "no_imputation_of_outcomes_or_mechanism_absence",
    }

    stop_rules = [
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-001",
            "trigger": "outcome_workbook_or_outcome_sheet_access_attempt_during_clean_builder",
            "required_action": "stop_immediately_and_invalidate_clean_preregistration_run",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-002",
            "trigger": "outcome_row_load_or_realized_value_visibility_detected",
            "required_action": "stop_immediately_require_new_clean_preregistration_version",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-003",
            "trigger": "primary_structure_drift_from_structure_a",
            "required_action": "block_freeze_and_repair_design_coherence",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-004",
            "trigger": "primary_contrast_eligible_observation_count_mismatch",
            "required_action": "block_freeze_and_reconcile_structure_counts",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-005",
            "trigger": "mixed_label_provider_session_cluster_count_mismatch",
            "required_action": "block_secondary_structural_sensitivity_until_reconciled",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-006",
            "trigger": "classification_run_id_or_mechanism_version_mismatch",
            "required_action": "stop_before_freeze_and_repair_lineage",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-007",
            "trigger": "unknown_or_insufficient_reinterpreted_as_negative",
            "required_action": "block_freeze_and_restore_frozen_label_semantics",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-008",
            "trigger": "low_confidence_primary_inclusion",
            "required_action": "block_primary_design_and_restore_confidence_rule",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-009",
            "trigger": "outcome_schema_contract_changed_after_freeze",
            "required_action": "require_new_preregistration_version_before_outcome_access",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-010",
            "trigger": "sample_gate_unit_ambiguity_or_gate_failure",
            "required_action": "block_primary_execution_approval_until_units_and_counts_are_explicit",
        },
        {
            "stop_rule_id": "RMTP-CLEAN-STOP-011",
            "trigger": "classification_modification_or_production_write_attempt",
            "required_action": "stop_immediately_and_hold_for_governance_review",
        },
    ]

    reporting_plan = {
        "primary_outputs": [
            "eligible_counts_by_expanded_consistency_label",
            "baseline_to_expanded_corrected_directional_success_delta_difference_by_expanded_consistency_group",
            "two_sided_95pct_cluster_aware_interval_or_descriptive_fallback",
            "all_primary_exclusions_by_reason",
            "sample_gate_pass_fail_table",
        ],
        "secondary_outputs": [
            "mixed_label_provider_session_cluster_structural_sensitivity_summary",
        ],
        "exploratory_outputs": [
            "relevance_sensitivity_effect_estimate_with_caveat",
            "specificity_descriptive_label_outcome_table_only",
        ],
        "mandatory_guardrails": [
            "POSITIVE_does_not_mean_predictively_useful",
            "NEGATIVE_does_not_mean_harmful_or_inaccurate",
            "UNKNOWN_is_a_valid_final_scientific_status",
            "LOW_confidence_remains_low_confidence",
            "no_provider_ranking_or_production_recommendation",
            "no_causal_claim_from_mechanism_association_alone",
        ],
    }

    clean_blinding_audit = {
        "clean_rerun_reason": "Phase 9A-6R14 could not independently verify that prior manual metadata contact was schema-only.",
        "source_workbooks_opened": ["DIAGNOSTICS", "PROJECT_OVERVIEWS"],
        "source_sheets_loaded": list(INPUT_SHEETS),
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_bearing_rows_loaded": 0,
        "realized_values_accessed": 0,
        "accuracy_fields_accessed": 0,
        "provider_performance_results_accessed": 0,
        "post_session_evidence_accessed": 0,
        "manual_metadata_contact_repeated": False,
        "source_of_outcome_contract": "prior_blinded_payloads_and_approval_audits_only",
        "design_changed_after_external_contact": False,
        "blinding_status": "BLINDING_INTACT_SCHEMA_CONTRACT_ONLY",
    }

    governance = {
        "provider_calls_performed": 0,
        "forecasts_generated": 0,
        "classification_rerun_performed": 0,
        "permanent_labels_modified": 0,
        "mechanism_tests_performed": 0,
        "accuracy_metrics_calculated": 0,
        "outcomes_accessed": 0,
        "outcome_workbooks_opened": 0,
        "outcome_sheets_loaded": 0,
        "outcome_bearing_rows_loaded": 0,
        "realized_values_accessed": 0,
        "provider_rankings_produced": 0,
        "v1_0_preregistration_modified": 0,
        "classifications_modified": 0,
        "production_writes": 0,
        "production_behavior_changes": 0,
    }

    lineage_source_fingerprints = []
    for sheet_name in SOURCE_V10_SHEETS:
        rows = inputs[sheet_name].rows
        lineage_source_fingerprints.append(
            {
                "sheet_name": sheet_name,
                "row_count": len(rows),
                "fingerprint_method": "json_sha256_sorted_keys_without_source_row_number",
                "fingerprint": _fingerprint_rows(rows),
            }
        )

    design_reconciliation = {
        "source_preregistration_version": SOURCE_TEST_PREREGISTRATION_VERSION,
        "clean_preregistration_version": TEST_PREREGISTRATION_VERSION,
        "scientifically_equivalent_where_intended": True,
        "equivalence_checks": [
            {
                "area": "mechanism_hierarchy",
                "source": "v1.0 preregistration + 6R12 readiness",
                "clean_result": "Consistency primary; relevance exploratory; specificity descriptive/sample-expansion-only.",
                "status": "PRESERVED",
            },
            {
                "area": "primary_structure",
                "source": "6R14 estimand audit",
                "clean_result": "Structure A explicitly frozen as expanded-state grouped delta comparison.",
                "status": "CLARIFIED_NOT_SCIENTIFICALLY_CHANGED",
            },
            {
                "area": "pair_counts",
                "source": "6R14 pair reconciliation + permanent classifications",
                "clean_result": "72 primary-contrast eligible observations and 12 mixed-label provider-session clusters frozen as separate counts.",
                "status": "CLARIFIED_NOT_SCIENTIFICALLY_CHANGED",
            },
            {
                "area": "outcome_contract",
                "source": "v1.0 frozen outcome definition + 6R14 derivation audit",
                "clean_result": "Outcome source represented only through schema contract and future join specification; no outcome-sheet access repeated.",
                "status": "BLINDING_REPAIRED",
            },
            {
                "area": "eligibility_and_uncertainty",
                "source": "v1.0 preregistration + 6R12 readiness",
                "clean_result": "UNKNOWN, INSUFFICIENT_EVIDENCE, EXCLUDED, and LOW-confidence primary exclusion preserved.",
                "status": "PRESERVED",
            },
        ],
        "resolved_structure": PRIMARY_STRUCTURE,
        "resolved_primary_exposure": estimand_audit_v14.get("treatment_exposure_variable"),
        "resolved_comparison_groups": estimand_audit_v14.get("comparison_groups"),
        "resolved_baseline_role": estimand_audit_v14.get("baseline_role"),
        "resolved_estimand": estimand_audit_v14.get("contrast"),
        "resolved_effect_measure": PRIMARY_EFFECT_MEASURE,
        "resolved_statistical_method": PRIMARY_STATISTICAL_METHOD,
        "pair_reconciliation": {
            "structural_baseline_expanded_pairs": structure["structural_baseline_expanded_pairs"],
            "consistency_classified_pairs": structure["consistency_classified_pairs"],
            "high_moderate_confidence_pairs": structure["high_moderate_confidence_pairs"],
            "primary_contrast_eligible_observations": structure["primary_contrast_eligible_observations"],
            "mixed_label_provider_session_clusters": structure["mixed_positive_negative_provider_session_clusters"],
            "informative_transition_pairs": 0,
        },
    }

    primary_gates = {
        "minimum_positive": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_positive_count"],
            "observed_blinded": structure["positive_count"],
            "unit": "expanded PM-003 POSITIVE forecast observations",
            "status": "PASS" if structure["positive_count"] >= PRIMARY_SAMPLE_GATES["minimum_positive_count"] else "FAIL",
        },
        "minimum_negative": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_negative_count"],
            "observed_blinded": structure["negative_count"],
            "unit": "expanded PM-003 affirmative-negative forecast observations",
            "status": "PASS" if structure["negative_count"] >= PRIMARY_SAMPLE_GATES["minimum_negative_count"] else "FAIL",
        },
        "minimum_primary_contrast_observations": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_primary_contrast_observations"],
            "observed_blinded": structure["primary_contrast_eligible_observations"],
            "unit": "expanded Pack B-E PM-003 POSITIVE_or_NEGATIVE observations with matched Pack A controls",
            "status": (
                "PASS"
                if structure["primary_contrast_eligible_observations"] >= PRIMARY_SAMPLE_GATES["minimum_primary_contrast_observations"]
                else "FAIL"
            ),
        },
        "minimum_clusters": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_clusters"],
            "observed_blinded": planning_summary.get("independent_clusters", 24),
            "unit": "provider-session clusters",
            "status": (
                "PASS"
                if planning_summary.get("independent_clusters", 0) >= PRIMARY_SAMPLE_GATES["minimum_clusters"]
                else "FAIL"
            ),
        },
        "minimum_providers": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_providers"],
            "observed_blinded": structure["provider_count"],
            "unit": "providers represented in the primary PM-003 contrast",
            "status": "PASS" if structure["provider_count"] >= PRIMARY_SAMPLE_GATES["minimum_providers"] else "FAIL",
        },
        "minimum_sessions": {
            "threshold": PRIMARY_SAMPLE_GATES["minimum_sessions"],
            "observed_blinded": structure["session_count"],
            "unit": "session outcome families represented in the primary PM-003 contrast",
            "status": "PASS" if structure["session_count"] >= PRIMARY_SAMPLE_GATES["minimum_sessions"] else "FAIL",
        },
    }
    primary_gates_pass = all(item["status"] == "PASS" for item in primary_gates.values())

    build_status = "PASS_WITH_WARNINGS" if primary_gates_pass else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_PREREGISTRATION_CLEAN_READY_WITH_WARNINGS"
        if primary_gates_pass
        else "REFINED_MECHANISM_TEST_PREREGISTRATION_CLEAN_NEEDS_REPAIR"
    )
    recommended_next_step = (
        "RERUN_PHASE9A6R14_CLEAN_EXECUTION_APPROVAL"
        if primary_gates_pass
        else "RUN_PHASE9A6R13R_CLEAN_PREREGISTRATION_REPAIR"
    )

    payloads: Dict[str, Dict[str, Any]] = {
        "Refined_Mechanism_Test_Preregistration_Clean": {
            "test_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "test_preregistration_status": TEST_PREREGISTRATION_STATUS,
            "source_preregistration_version": SOURCE_TEST_PREREGISTRATION_VERSION,
            "source_preregistration_preserved_unchanged": True,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "mechanism_version": MECHANISM_VERSION,
            "primary_mechanism": PRIMARY_MECHANISM,
            "exploratory_mechanism": EXPLORATORY_MECHANISM,
            "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
            "outcome_access_allowed_after_freeze": True,
            "design_change_after_outcome_access": False,
            "hypothesis_change_after_outcome_access": False,
            "eligibility_change_after_outcome_access": False,
            "outcome_definition_change_after_access": False,
            "clean_blinding_mode": "SCHEMA_CONTRACT_ONLY",
            "budget_maintenance": budget_maintenance,
        },
        "Refined_Mechanism_Test_Frozen_Hypotheses_Clean": {
            "primary": [primary_hypothesis],
            "secondary": secondary_hypotheses,
            "exploratory": exploratory_hypotheses,
        },
        "Refined_Mechanism_Test_Frozen_Population_Clean": {
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "classification_rows": len(class_rows),
            "unique_source_rows": unique_source_rows,
            "unique_providers": unique_providers,
            "unique_sessions": unique_sessions,
            "unique_forecast_runs": unique_forecast_runs,
            "independent_provider_session_clusters": planning_summary.get("independent_clusters", 24),
            "candidate_baseline_to_expanded_comparisons": planning_summary.get("candidate_matched_pairs", 82),
            "mechanism_counts": mechanism_counts,
            "mechanism_stats_from_readiness": mechanism_stats,
            "label_distribution": dict(label_distribution),
        },
        "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis_Clean": {
            "primary_unit_of_analysis": PRIMARY_UNIT_OF_ANALYSIS,
            "observation_definition": (
                "one provider forecast for one session under one pack condition, later joined to one canonical corrected "
                "outcome and one frozen mechanism classification"
            ),
            "required_identifiers": [
                "provider",
                "session_id",
                "pack_level",
                "source_row_key",
                "classification_run_id",
                "mechanism_id",
                "classification_label",
            ],
            "matching_key": MATCHING_KEY,
            "pseudoreplication_rule": "mechanism rows are not automatically independent outcome observations",
            "baseline_role": "Pack A serves only as a structural matched control for delta construction",
        },
        "Refined_Mechanism_Test_Frozen_Outcome_Definition_Clean": outcome_definition,
        "Refined_Mechanism_Test_Frozen_Comparison_Design_Clean": comparison_design,
        "Refined_Mechanism_Test_Frozen_Cluster_Design_Clean": cluster_design,
        "Refined_Mechanism_Test_Frozen_Eligibility_Rules_Clean": eligibility_rules,
        "Refined_Mechanism_Test_Frozen_Confidence_Rules_Clean": confidence_rules,
        "Refined_Mechanism_Test_Frozen_Unknown_Rules_Clean": unknown_rules,
        "Refined_Mechanism_Test_Frozen_Confounder_Rules_Clean": confounder_rules,
        "Refined_Mechanism_Test_Frozen_Multiple_Testing_Clean": multiple_testing,
        "Refined_Mechanism_Test_Frozen_Missing_Data_Clean": missing_data,
        "Refined_Mechanism_Test_Frozen_Stop_Rules_Clean": {
            "stop_rules": stop_rules,
            "fail_closed": True,
        },
        "Refined_Mechanism_Test_Frozen_Reporting_Plan_Clean": reporting_plan,
        "Refined_Mechanism_Test_Clean_Lineage_Audit": {
            "source_preregistration_version": SOURCE_TEST_PREREGISTRATION_VERSION,
            "clean_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "source_preregistration_sheet_family": list(SOURCE_V10_SHEETS),
            "clean_preregistration_sheet_family": list(OUTPUT_SHEETS),
            "source_preregistration_preserved_unchanged": True,
            "source_sheet_fingerprints": lineage_source_fingerprints,
            "approval_block_origin": approval_summary.get("final_interpretation"),
            "clean_rerun_reason": approval_summary.get("recommended_next_step"),
        },
        "Refined_Mechanism_Test_Clean_Blinding_Audit": clean_blinding_audit,
        "Refined_Mechanism_Test_Clean_Design_Reconciliation": design_reconciliation,
        "Refined_Mechanism_Test_Preregistration_Clean_Governance": governance,
        "Refined_Mechanism_Test_Preregistration_Clean_Summary": {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "file_created": BUILD_SCRIPT,
            "test_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "source_preregistration_version": SOURCE_TEST_PREREGISTRATION_VERSION,
            "source_preregistration_preserved_unchanged": True,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "primary_structure": PRIMARY_STRUCTURE,
            "primary_mechanism": PRIMARY_MECHANISM,
            "exploratory_mechanism": EXPLORATORY_MECHANISM,
            "descriptive_only_mechanism": DESCRIPTIVE_ONLY_MECHANISM,
            "primary_exposure": estimand_audit_v14.get("treatment_exposure_variable"),
            "primary_comparison_groups": estimand_audit_v14.get("comparison_groups"),
            "baseline_role": estimand_audit_v14.get("baseline_role"),
            "primary_estimand": estimand_audit_v14.get("contrast"),
            "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
            "primary_statistical_method": PRIMARY_STATISTICAL_METHOD,
            "structural_baseline_expanded_pairs": structure["structural_baseline_expanded_pairs"],
            "consistency_classified_pairs": structure["consistency_classified_pairs"],
            "high_moderate_confidence_pairs": structure["high_moderate_confidence_pairs"],
            "primary_contrast_eligible_observations": structure["primary_contrast_eligible_observations"],
            "mixed_label_provider_session_clusters": structure["mixed_positive_negative_provider_session_clusters"],
            "positive_count": structure["positive_count"],
            "negative_count": structure["negative_count"],
            "unknown_handling": unknown_rules["UNKNOWN"],
            "insufficient_evidence_handling": unknown_rules["INSUFFICIENT_EVIDENCE"],
            "excluded_handling": unknown_rules["EXCLUDED"],
            "low_confidence_handling": unknown_rules["LOW_CONFIDENCE"],
            "outcome_source_contract_only": True,
            "outcome_rows_loaded": 0,
            "outcome_values_accessed": 0,
            "accuracy_metrics_calculated": 0,
            "classifications_modified": 0,
            "production_writes": 0,
            "sample_gates": primary_gates,
            "ready_for_clean_execution_approval": primary_gates_pass,
            "ready_for_mechanism_testing": False,
            "ready_for_production": False,
            "recommended_next_step": recommended_next_step,
        },
    }

    clean_rows_for_fingerprint = {
        sheet_name: {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "clean_preregistration_run_id": clean_preregistration_run_id,
            "payload_json": json.dumps(payloads[sheet_name], ensure_ascii=True, sort_keys=True),
        }
        for sheet_name in OUTPUT_SHEETS
        if sheet_name != "Refined_Mechanism_Test_Clean_Fingerprint_Freeze"
    }

    clean_output_fingerprints = [
        {
            "sheet_name": sheet_name,
            "fingerprint_method": "json_sha256_sorted_keys",
            "fingerprint": _fingerprint_payload(row),
        }
        for sheet_name, row in sorted(clean_rows_for_fingerprint.items())
    ]
    payloads["Refined_Mechanism_Test_Clean_Fingerprint_Freeze"] = {
        "source_v1_0_fingerprints": lineage_source_fingerprints,
        "clean_output_fingerprints": clean_output_fingerprints,
        "derived_fingerprints": [
            {
                "component": "classification_run_identity",
                "fingerprint": _fingerprint_payload(
                    {
                        "classification_run_id": CLASSIFICATION_RUN_ID,
                        "mechanism_version": MECHANISM_VERSION,
                        "row_count": len(class_rows),
                    }
                ),
            },
            {
                "component": "primary_structure_contract",
                "fingerprint": _fingerprint_payload(comparison_design),
            },
            {
                "component": "outcome_schema_contract",
                "fingerprint": _fingerprint_payload(outcome_definition),
            },
        ],
        "modification_allowed_after_freeze": False,
    }

    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "clean_preregistration_run_id": clean_preregistration_run_id,
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
        "clean_preregistration_run_id": clean_preregistration_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Preregistration_Clean_Summary"],
        "registry_writes": registry_writes,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
