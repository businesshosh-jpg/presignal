#!/usr/bin/env python3
"""Phase 9A-6R13 — Refined Mechanism Test Design and Preregistration.

This phase freezes the fully blinded experimental design for testing whether
frozen refined mechanism classifications are associated with corrected forecast
outcomes. It does not access outcome rows, calculate accuracy, join outcomes,
modify classifications, or test mechanisms.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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


PHASE_ID = "9A-6R13"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_design_preregistration_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_preregistration_v0"
PREREGISTRATION_VERSION = "refined_mechanism_test_preregistration_v0"
TEST_PREREGISTRATION_VERSION = "1.0"
TEST_PREREGISTRATION_STATUS = "FROZEN"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_PREREGISTRATION"
REGISTRY_OWNER_MODULE = "market_state"

CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
EXPLORATORY_MECHANISM = "MECH_INFORMATION_RELEVANCE"
DESCRIPTIVE_ONLY_MECHANISM = "MECH_INFORMATION_SPECIFICITY"

PRIMARY_MECHANISM_ID = "PM-003"
EXPLORATORY_MECHANISM_ID = "PM-001"
DESCRIPTIVE_ONLY_MECHANISM_ID = "PM-002"
NOVELTY_ID = "PM-S01"
UMBRELLA_ID = "PM-L01"

PRIMARY_UNIT_OF_ANALYSIS = "provider_session_pack_forecast_observation"
MATCHING_KEY = "provider + session_id + baseline_pack_A_source_row_key + expanded_pack_source_row_key"
CLUSTERING_LEVEL = "provider_session_cluster_nested_within_shared_session_outcome_family"
PRIMARY_COMPARISON = "WITHIN_PROVIDER_SESSION_BASELINE_TO_EXPANDED_CONSISTENCY_TRANSITION_DESIGN"
SECONDARY_COMPARISON = "WITHIN_PROVIDER_SESSION_MATCHED_POSITIVE_VS_NEGATIVE_CONSISTENCY"
EXPLORATORY_RELEVANCE_DESIGN = "WITHIN_PROVIDER_SESSION_MATCHED_POSITIVE_VS_NEGATIVE_RELEVANCE_SENSITIVITY"
SPECIFICITY_STATUS = "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION"
PRIMARY_EFFECT_MEASURE = "matched_baseline_to_expanded_corrected_directional_success_delta_difference"
PRIMARY_STATISTICAL_METHOD = (
    "provider_session_clustered_matched_risk_difference_on_baseline_to_expanded_success_delta_"
    "with_two_sided_95pct_cluster_bootstrap_interval_and_descriptive_fallback_if_sparse"
)
PRIMARY_OUTCOME_SOURCE = "DIAGNOSTICS.Market_Reaction_Canonical_Outcomes"
PRIMARY_OUTCOME_FIELD = "canonical_realized_direction"
OUTCOME_JOIN_BRIDGE = "DIAGNOSTICS.Corrected_Accuracy_Outcome_Mapping"
OUTCOME_JOIN_KEY = "provider + session_id + pack_level + source_row_key -> repaired_canonical_outcome_id -> canonical_outcome_id"

INPUT_SHEETS: Tuple[str, ...] = (
    # Permanent classifications
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Evidence",
    "Refined_Mechanism_v11_Classification_Conflicts",
    "Refined_Mechanism_v11_Classification_Confidence",
    "Refined_Mechanism_v11_Classification_Audit",
    "Refined_Mechanism_v11_Classification_Governance",
    "Refined_Mechanism_v11_Classification_Summary",
    # Phase 9A-6R11 execution review
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Run_Identity_Audit",
    "Refined_Mechanism_v11_Classification_Reconciliation",
    "Refined_Mechanism_v11_Trace_Completeness_Review",
    "Refined_Mechanism_v11_Determinism_Review",
    "Refined_Mechanism_v11_Leakage_Review",
    "Refined_Mechanism_v11_Execution_Review_Summary",
    # Phase 9A-6R12 planning-readiness outputs
    "Refined_Mechanism_Test_Planning_Readiness",
    "Refined_Mechanism_Test_Unit_Of_Analysis",
    "Refined_Mechanism_Test_Population_Structure",
    "Refined_Mechanism_Test_Label_Eligibility",
    "Refined_Mechanism_Test_Comparison_Design",
    "Refined_Mechanism_Test_Confounder_Map",
    "Refined_Mechanism_Test_Independence_Audit",
    "Refined_Mechanism_Test_Sample_Adequacy",
    "Refined_Mechanism_Test_Unknown_Handling",
    "Refined_Mechanism_Test_Confidence_Handling",
    "Refined_Mechanism_Test_Leakage_Boundary",
    "Refined_Mechanism_Test_Preregistration_Requirements",
    "Refined_Mechanism_Test_Planning_Governance",
    "Refined_Mechanism_Test_Planning_Readiness_Summary",
    # Frozen v1.1 mechanism definitions
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_PreRegistration_Summary",
)

OUTPUT_SHEETS = [
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
]

COMMON_HEADERS = ["generated_ts", "schema_version", "preregistration_run_id", "payload_json"]
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}

# We only compact trailing empty rows on older terminal summary sheets if the
# diagnostics workbook is at the cell limit. Content, headers, and scientific
# records remain unchanged.
BUDGET_RECOVERY_SHEETS: Tuple[Tuple[str, int], ...] = (
    ("Accuracy_Execution_Approval_Summary", 2),
    ("Controlled_Accuracy_Design_Summary", 2),
    ("Behavior_Accuracy_Revision_Summary", 2),
)

PRIMARY_SAMPLE_GATES = {
    "minimum_positive_count": 40,
    "minimum_negative_count": 12,
    "minimum_matched_pairs": 40,
    "minimum_clusters": 12,
    "minimum_providers": 2,
    "minimum_sessions": 4,
    "maximum_single_cluster_share": 0.20,
}

SPECIFICITY_FUTURE_SAMPLE_GATES = {
    "minimum_affirmative_negative_count": 12,
    "minimum_independent_cluster_count": 12,
    "minimum_matched_pair_count": 8,
    "minimum_negative_provider_count": 2,
    "minimum_negative_session_count": 4,
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R13_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _sheet_metadata(service) -> List[Dict[str, Any]]:
    return (
        service.spreadsheets()
        .get(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            fields="sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))",
        )
        .execute()
        .get("sheets", [])
    )


def _compact_for_budget(service, current_total: int, required_cells: int) -> Dict[str, Any]:
    remaining_gap = current_total + required_cells - 10_000_000
    if remaining_gap <= 0:
        return {"cells_before": current_total, "cells_after": current_total, "sheets_compacted": []}

    metadata = _sheet_metadata(service)
    by_title = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata}
    requests: List[Dict[str, Any]] = []
    compacted: List[Dict[str, Any]] = []
    reclaimed = 0

    for title, target_rows in BUDGET_RECOVERY_SHEETS:
        props = by_title.get(title)
        if not props:
            continue
        grid = props.get("gridProperties", {})
        current_rows = int(grid.get("rowCount", 0))
        current_cols = int(grid.get("columnCount", 0))
        if current_rows <= target_rows or current_cols <= 0:
            continue
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": props["sheetId"],
                        "gridProperties": {
                            "rowCount": target_rows,
                            "columnCount": current_cols,
                        },
                    },
                    "fields": "gridProperties.rowCount,gridProperties.columnCount",
                }
            }
        )
        reclaimed += (current_rows - target_rows) * current_cols
        compacted.append(
            {
                "sheet_name": title,
                "rows_before": current_rows,
                "rows_after": target_rows,
                "columns_preserved": current_cols,
                "cells_reclaimed": (current_rows - target_rows) * current_cols,
            }
        )
        if reclaimed >= remaining_gap:
            break

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": requests},
        ).execute()

    after_total = _sheet_cell_total(service)
    return {
        "cells_before": current_total,
        "cells_after": after_total,
        "sheets_compacted": compacted,
    }


def _ensure_cell_budget(service, known_titles: Set[str]) -> Dict[str, Any]:
    current = _sheet_cell_total(service)
    required = sum(2 * len(COMMON_HEADERS) for name in OUTPUT_SHEETS if name not in known_titles)
    if current + required <= 10_000_000:
        return {
            "cells_before": current,
            "cells_after": current,
            "required_cells": required,
            "sheets_compacted": [],
        }
    compaction = _compact_for_budget(service, current, required)
    final_total = _sheet_cell_total(service)
    if final_total + required > 10_000_000:
        raise RuntimeError(
            "Insufficient workbook cell budget for Phase 9A-6R13 outputs even after compacting trailing empty rows: "
            f"current={final_total}, required={required}."
        )
    compaction["required_cells"] = required
    compaction["cells_after"] = final_total
    return compaction


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
            "notes": "Phase 9A-6R13 blinded refined mechanism test preregistration outputs.",
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
    preregistration_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    budget_maintenance = _ensure_cell_budget(service, known_titles)

    planning_summary = _latest_payload(inputs["Refined_Mechanism_Test_Planning_Readiness_Summary"].rows, "readiness_run_id")
    if not planning_summary.get("ready_for_mechanism_test_design_and_preregistration"):
        raise RuntimeError("Phase 9A-6R12 did not declare readiness for blinded mechanism test preregistration.")

    execution_review_summary = _latest_row(inputs["Refined_Mechanism_v11_Execution_Review_Summary"].rows, "review_run_id")
    if _normalize(execution_review_summary.get("final_interpretation")) not in {
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY",
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY_WITH_WARNINGS",
    }:
        raise RuntimeError("Phase 9A-6R11 execution review is not ready for test-design preregistration.")

    planning_label_eligibility = _latest_payload(inputs["Refined_Mechanism_Test_Label_Eligibility"].rows, "readiness_run_id")
    planning_confounders = _latest_payload(inputs["Refined_Mechanism_Test_Confounder_Map"].rows, "readiness_run_id")
    planning_unknowns = _latest_payload(inputs["Refined_Mechanism_Test_Unknown_Handling"].rows, "readiness_run_id")
    planning_confidence = _latest_payload(inputs["Refined_Mechanism_Test_Confidence_Handling"].rows, "readiness_run_id")
    planning_prereg_requirements = _latest_payload(inputs["Refined_Mechanism_Test_Preregistration_Requirements"].rows, "readiness_run_id")

    class_rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]
    if len(class_rows) != 360:
        raise RuntimeError(f"Expected 360 permanent classification rows for {CLASSIFICATION_RUN_ID}, found {len(class_rows)}.")

    label_distribution = Counter(_normalize(row.get("classification_label")) for row in class_rows)
    unique_source_rows = len({_normalize(row.get("source_row_key")) for row in class_rows})
    unique_providers = len({_normalize(row.get("provider")) for row in class_rows})
    unique_sessions = len({_normalize(row.get("session_id")) for row in class_rows})
    unique_forecast_runs = unique_source_rows

    mechanism_stats = planning_label_eligibility.get("per_mechanism", {})
    consistency_rows = [row for row in class_rows if _normalize(row.get("mechanism_id")) == PRIMARY_MECHANISM]
    consistency_baselines = {
        (_normalize(row.get("provider")), _normalize(row.get("session_id"))): row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) == "A"
    }
    eligible_consistency_expanded = [
        row
        for row in consistency_rows
        if _normalize(row.get("pack_level")) in {"B", "C", "D", "E"}
        and _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
        and _normalize(row.get("confidence_category")) in {"HIGH", "MODERATE"}
        and _normalize(row.get("eligibility_status")) not in {"EXCLUDED", "OUT_OF_SCOPE"}
        and (_normalize(row.get("provider")), _normalize(row.get("session_id"))) in consistency_baselines
    ]
    primary_cluster_counts = Counter(
        f"{_normalize(row.get('provider'))}|{_normalize(row.get('session_id'))}"
        for row in eligible_consistency_expanded
    )
    max_cluster_share = (
        max(primary_cluster_counts.values()) / len(eligible_consistency_expanded)
        if primary_cluster_counts and eligible_consistency_expanded
        else 0.0
    )
    primary_provider_count = len({_normalize(row.get("provider")) for row in eligible_consistency_expanded})
    primary_session_count = len({_normalize(row.get("session_id")) for row in eligible_consistency_expanded})

    consistency_negative_provider_count = len(
        mechanism_stats.get(PRIMARY_MECHANISM, {}).get("negative_provider_counts", {})
    )

    primary_gates_pass = all(
        [
            mechanism_stats.get(PRIMARY_MECHANISM, {}).get("positive_eligible_count", 0) >= PRIMARY_SAMPLE_GATES["minimum_positive_count"],
            mechanism_stats.get(PRIMARY_MECHANISM, {}).get("negative_eligible_count", 0) >= PRIMARY_SAMPLE_GATES["minimum_negative_count"],
            len(eligible_consistency_expanded) >= PRIMARY_SAMPLE_GATES["minimum_matched_pairs"],
            mechanism_stats.get(PRIMARY_MECHANISM, {}).get("independent_cluster_count", 0) >= PRIMARY_SAMPLE_GATES["minimum_clusters"],
            primary_provider_count >= PRIMARY_SAMPLE_GATES["minimum_providers"],
            primary_session_count >= PRIMARY_SAMPLE_GATES["minimum_sessions"],
            max_cluster_share <= PRIMARY_SAMPLE_GATES["maximum_single_cluster_share"],
            consistency_negative_provider_count >= 2,
        ]
    )

    primary_design_adequacy = (
        "ADEQUATE_FOR_EXPLORATORY_MATCHED_TEST_WITH_WARNINGS"
        if primary_gates_pass
        else "INSUFFICIENT_FOR_PREREGISTERED_PRIMARY_CONSISTENCY_TEST"
    )

    primary_hypothesis = {
        "hypothesis_id": "RMTP-H1",
        "mechanism_id": PRIMARY_MECHANISM_ID,
        "mechanism_name": PRIMARY_MECHANISM,
        "population": (
            "expanded-pack provider_session_pack_forecast_observations (B-E) with matched same-provider same-session "
            "Pack A structural controls, future corrected directional outcome availability, and high/moderate consistency confidence"
        ),
        "comparison": (
            "expanded observations classified MECH_INFORMATION_CONSISTENCY = POSITIVE versus expanded observations "
            "classified MECH_INFORMATION_CONSISTENCY = NEGATIVE under frozen v1.1 rules"
        ),
        "directionality": "NON_DIRECTIONAL",
        "outcome": "corrected_directional_success_binary",
        "analysis_method": PRIMARY_STATISTICAL_METHOD,
        "confidence_inclusion": "HIGH_AND_MODERATE_ONLY",
        "exclusion_rules": "UNKNOWN|INSUFFICIENT_EVIDENCE|EXCLUDED|LOW_CONFIDENCE|MISSING_OR_AMBIGUOUS_OUTCOME_JOIN|INVALID_OUTPUT",
        "clustering_matching_rule": (
            "expanded observation matched to same-provider same-session Pack A control; clustered at provider_session "
            "within shared_session_outcome_family"
        ),
        "multiple_testing_family": "PRIMARY_FAMILY_PM003_ONLY",
    }

    secondary_hypothesis = {
        "hypothesis_id": "RMTP-H2",
        "mechanism_id": PRIMARY_MECHANISM_ID,
        "mechanism_name": PRIMARY_MECHANISM,
        "comparison": (
            "baseline-to-expanded provider-session outcome deltas differ between expanded consistency-positive and "
            "expanded consistency-negative observations"
        ),
        "design": PRIMARY_COMPARISON,
        "status": "SECONDARY",
        "notes": (
            "Pack A remains structurally EXCLUDED for mechanism labeling and functions only as a matched control forecast; "
            "no baseline consistency negative label is manufactured."
        ),
    }

    exploratory_hypotheses = [
        {
            "hypothesis_id": "RMTP-E1",
            "mechanism_id": EXPLORATORY_MECHANISM_ID,
            "mechanism_name": EXPLORATORY_MECHANISM,
            "comparison": "within-provider-session matched relevance positive versus negative sensitivity analysis",
            "status": "EXPLORATORY",
            "notes": "Negative class remains thin and highly collinear with other mechanisms.",
        },
        {
            "hypothesis_id": "RMTP-E2",
            "mechanism_id": DESCRIPTIVE_ONLY_MECHANISM_ID,
            "mechanism_name": DESCRIPTIVE_ONLY_MECHANISM,
            "comparison": "descriptive specificity label-outcome table only; no inferential binary hypothesis",
            "status": "DESCRIPTIVE_ONLY",
            "notes": "Specificity remains sample-expansion-only because affirmative negatives are too sparse and provider-concentrated.",
        },
        {
            "hypothesis_id": "RMTP-E3",
            "mechanism_id": "JOINT_PATTERNS",
            "mechanism_name": "JOINT_MECHANISM_PATTERN",
            "comparison": "consistency-only versus joint-positive co-occurrence descriptive pattern review",
            "status": "EXPLORATORY",
            "notes": "Joint patterns are reported descriptively unless sparse cells support a preregistered sensitivity fit.",
        },
    ]

    outcome_definition = {
        "canonical_outcome_source_workbook": "DIAGNOSTICS",
        "canonical_outcome_source_sheet": "Market_Reaction_Canonical_Outcomes",
        "canonical_outcome_id_field": "canonical_outcome_id",
        "canonical_outcome_field": PRIMARY_OUTCOME_FIELD,
        "outcome_metric_id": "CORRECTED_DIRECTIONAL_SUCCESS_BINARY",
        "outcome_metric_definition": (
            "Future binary indicator that an eligible forecast direction agrees with the corrected canonical realized direction "
            "materialized through the repaired market-reaction outcome layer."
        ),
        "corrected_mapping_bridge_sheet": "Corrected_Accuracy_Outcome_Mapping",
        "corrected_mapping_bridge_field": "repaired_canonical_outcome_id",
        "corrected_mapping_version_lineage": "market_reaction_outcome_source_implementation_v0 + corrected_accuracy_re_evaluation_design_v0",
        "evaluation_window_fields": ["window_policy", "window_minutes", "canonical_start_ts", "canonical_end_ts"],
        "tie_flat_handling": "exclude_flat_or_ambiguous_realized_direction_from_primary_binary_analysis_and_report_descriptively",
        "missing_outcome_handling": "exclude_from_inferential_analysis_and_report_reason",
        "duplicate_outcome_handling": "block_ambiguous_join_and_exclude_until_resolved_per_frozen_rule",
        "no_signal_handling": (
            "exclude_from_primary_directional_binary_and report_descriptively unless a future no-signal-specific secondary metric "
            "is separately preregistered"
        ),
        "provider_neutrality_rule": "one canonical corrected outcome per session window; no provider-specific outcome remapping allowed",
        "outcome_timestamp_requirement": "use only canonical outcomes whose release_ts and window metadata are frozen before test execution",
        "future_join_rule": OUTCOME_JOIN_KEY,
        "approved_value_access_during_preregistration": False,
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
        "confounder_map": planning_confounders,
    }

    missing_data_rules = {
        "missing_outcome": "exclude_from_primary_and_secondary_inference_and_report_reason",
        "duplicate_outcome": "block_row_until_resolved_or_exclude_under_frozen_duplicate_rule",
        "ambiguous_join": "exclude_and_report_join_failure",
        "missing_provider_session_pair": "exclude_from_matched_designs",
        "missing_baseline_or_expanded_observation": "exclude_from_primary_matched_delta_design",
        "invalid_forecast_output": "exclude_per_frozen_classification_scope",
        "incomplete_classification_trace": "block_test_execution_until_trace_repair",
        "missing_pack_condition_identity": "exclude_and_report_scope_failure",
        "imputation_rule": "no_imputation_of_outcome_correctness_or_mechanism_absence",
    }

    stop_rules = [
        {
            "stop_rule_id": "RMTP-STOP-001",
            "trigger": "classification_run_id_mismatch",
            "required_action": "stop_before_outcome_access_and_repair_lineage",
        },
        {
            "stop_rule_id": "RMTP-STOP-002",
            "trigger": "mechanism_version_mismatch_or_v11_rule_drift",
            "required_action": "block_test_execution_and_require_new_preregistration",
        },
        {
            "stop_rule_id": "RMTP-STOP-003",
            "trigger": "outcome_source_or_mapping_fingerprint_mismatch",
            "required_action": "stop_before_join_and_require_outcome_definition_reapproval",
        },
        {
            "stop_rule_id": "RMTP-STOP-004",
            "trigger": "classification_label_reinterpretation_attempt_for_UNKNOWN_or_INSUFFICIENT_EVIDENCE",
            "required_action": "block_execution_and_restore_frozen_label_semantics",
        },
        {
            "stop_rule_id": "RMTP-STOP-005",
            "trigger": "low_confidence_primary_inclusion_attempt",
            "required_action": "remove_from_primary_or stop_if_selection_is_ambiguous",
        },
        {
            "stop_rule_id": "RMTP-STOP-006",
            "trigger": "missing_or_ambiguous_outcome_join",
            "required_action": "exclude_row_and record_join_failure",
        },
        {
            "stop_rule_id": "RMTP-STOP-007",
            "trigger": "sample_gate_failure_after_future_outcome_join",
            "required_action": "downgrade_to_descriptive_or_exploratory_reporting_without_changing_rules",
        },
        {
            "stop_rule_id": "RMTP-STOP-008",
            "trigger": "single_cluster_dominance_above_frozen_threshold",
            "required_action": "block_confirmatory_claim_and downgrade_to_descriptive_or exploratory",
        },
        {
            "stop_rule_id": "RMTP-STOP-009",
            "trigger": "baseline_pack_A_not_available_for_required_matched_control",
            "required_action": "exclude_expanded_row_from_primary_matched_delta_design",
        },
        {
            "stop_rule_id": "RMTP-STOP-010",
            "trigger": "outcome_values_accessed_before_preregistration_freeze",
            "required_action": "block_phase_and require new preregistration cycle",
        },
        {
            "stop_rule_id": "RMTP-STOP-011",
            "trigger": "design_change_after_outcome_access",
            "required_action": "force new preregistration version and quarantine original primary analysis",
        },
        {
            "stop_rule_id": "RMTP-STOP-012",
            "trigger": "raw_360_mechanism_row_analysis_treated_as_independent",
            "required_action": "block_execution_and require clustered_or_matched redesign",
        },
    ]

    reporting_plan = {
        "primary_outputs": [
            "eligible_counts_by_label_and_provider_session_cluster",
            "matched_baseline_to_expanded_consistency_positive_vs_negative_effect_estimate",
            "two_sided_95pct_cluster_aware_interval_or_descriptive_fallback",
            "sample_gate_pass_fail_table",
            "all_primary_exclusions_by_reason",
        ],
        "secondary_outputs": [
            "secondary_consistency_positive_vs_negative_matched_effect_estimate",
            "baseline_to_expanded_consistency_delta_summary",
        ],
        "exploratory_outputs": [
            "relevance_sensitivity_effect_estimate_with_caveat",
            "specificity_descriptive_label_outcome_table_only",
            "mechanism_co_occurrence_pattern_summary",
            "low_confidence_sensitivity_appendix",
        ],
        "mandatory_guardrails": [
            "POSITIVE_does_not_mean_predictively_useful",
            "NEGATIVE_does_not_mean_harmful_or_inaccurate",
            "UNKNOWN_is_a_valid_final_scientific_status",
            "no_provider_ranking_or_production_recommendation",
            "no_causal_claim_from_mechanism_association_alone",
        ],
    }

    readiness_for_approval = primary_gates_pass
    build_status = "PASS_WITH_WARNINGS" if readiness_for_approval else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_PREREGISTRATION_READY_WITH_WARNINGS"
        if readiness_for_approval
        else "REFINED_MECHANISM_TEST_PREREGISTRATION_SAMPLE_INADEQUATE"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R14_MECHANISM_TEST_EXECUTION_APPROVAL"
        if readiness_for_approval
        else "EXPAND_SAMPLE_BEFORE_MECHANISM_TEST_PREREGISTRATION"
    )

    payloads = {
        "Refined_Mechanism_Test_Preregistration": {
            "test_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "test_preregistration_status": TEST_PREREGISTRATION_STATUS,
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
            "budget_maintenance": budget_maintenance,
        },
        "Refined_Mechanism_Test_Frozen_Hypotheses": {
            "primary": [primary_hypothesis],
            "secondary": [secondary_hypothesis],
            "exploratory": exploratory_hypotheses,
        },
        "Refined_Mechanism_Test_Frozen_Population": {
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "classification_rows": len(class_rows),
            "unique_source_rows": unique_source_rows,
            "unique_providers": unique_providers,
            "unique_sessions": unique_sessions,
            "unique_forecast_runs": unique_forecast_runs,
            "independent_clusters": planning_summary.get("independent_clusters", 24),
            "candidate_baseline_to_expanded_comparisons": planning_summary.get("candidate_matched_pairs", 82),
            "mechanism_hierarchy": {
                PRIMARY_MECHANISM: "PRIMARY_ONLY",
                EXPLORATORY_MECHANISM: "EXPLORATORY_ONLY",
                DESCRIPTIVE_ONLY_MECHANISM: "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION",
                "MECH_INFORMATION_NOVELTY": "SUPPORTING_ONLY",
                "MECH_INFORMATION_VALUE": "UMBRELLA_ONLY",
            },
            "label_distribution": dict(label_distribution),
            "pack_scope": {
                "A": "STRUCTURAL_BASELINE_CONTROL_ONLY_NOT_MECHANISM_TEST_ELIGIBLE",
                "B": "ELIGIBLE_IF_FROZEN_LABEL_AND_CONFIDENCE_RULES_PASS",
                "C": "ELIGIBLE_IF_FROZEN_LABEL_AND_CONFIDENCE_RULES_PASS",
                "D": "ELIGIBLE_IF_FROZEN_LABEL_AND_CONFIDENCE_RULES_PASS",
                "E": "ELIGIBLE_IF_FROZEN_LABEL_AND_CONFIDENCE_RULES_PASS",
            },
        },
        "Refined_Mechanism_Test_Frozen_Unit_Of_Analysis": {
            "primary_unit_of_analysis": PRIMARY_UNIT_OF_ANALYSIS,
            "observation_definition": (
                "one provider forecast for one session under one pack condition, linked to one future corrected outcome and one mechanism label"
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
            "baseline_control_rule": "Pack A is a structural matched control observation and never enters the mechanism binary label set.",
            "pseudoreplication_rule": "mechanism rows are not independent outcome observations; raw 360-row analysis is prohibited",
        },
        "Refined_Mechanism_Test_Frozen_Outcome_Definition": outcome_definition,
        "Refined_Mechanism_Test_Frozen_Comparison_Design": {
            "primary_design": {
                "design_id": PRIMARY_COMPARISON,
                "primary_comparison": (
                    "compare baseline-to-expanded corrected directional success deltas between expanded consistency-positive and "
                    "expanded consistency-negative observations"
                ),
                "baseline_role": "same-provider same-session Pack A structural control only",
                "effect_measure": PRIMARY_EFFECT_MEASURE,
                "statistical_method": PRIMARY_STATISTICAL_METHOD,
                "inference_mode": "EXPLORATORY_EFFECT_ESTIMATION_WITH_TWO_SIDED_95PCT_INTERVAL",
                "nominal_alpha_if_estimable": 0.05,
            },
            "secondary_design": {
                "design_id": SECONDARY_COMPARISON,
                "comparison": "within-provider-session matched positive versus negative consistency observations",
                "status": "SECONDARY",
            },
            "exploratory_relevance_design": {
                "design_id": EXPLORATORY_RELEVANCE_DESIGN,
                "status": "EXPLORATORY_ONLY",
                "notes": "effect estimate and uncertainty only; no confirmatory claim",
            },
            "specificity_design": {
                "design_id": SPECIFICITY_STATUS,
                "status": "DESCRIPTIVE_ONLY",
                "sample_expansion_gates": SPECIFICITY_FUTURE_SAMPLE_GATES,
            },
            "rejected_designs": planning_summary.get("designs_rejected", []),
        },
        "Refined_Mechanism_Test_Frozen_Cluster_Design": {
            "primary_clustering_level": CLUSTERING_LEVEL,
            "matching_structure": "provider_session baseline_pack_A matched to expanded_pack_B_to_E",
            "shared_outcome_rule": "multiple providers and packs within a session share one realized outcome family and must not be treated as independent",
            "multiple_mechanism_rule": "multiple mechanism labels on one forecast share the same future outcome and are not separate independent successes",
            "primary_cluster_count": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("independent_cluster_count", 0),
            "primary_session_count": primary_session_count,
            "primary_provider_count": primary_provider_count,
            "maximum_single_cluster_share_observed_blinded": round(max_cluster_share, 6),
        },
        "Refined_Mechanism_Test_Frozen_Eligibility_Rules": {
            "primary_mechanism_rule": {
                "mechanism_id": PRIMARY_MECHANISM_ID,
                "mechanism_name": PRIMARY_MECHANISM,
                "include_labels": ["POSITIVE", "NEGATIVE"],
                "include_pack_levels": ["B", "C", "D", "E"],
                "require_confidence": ["HIGH", "MODERATE"],
                "require_classification_run_id": CLASSIFICATION_RUN_ID,
                "require_mechanism_version": MECHANISM_VERSION,
                "require_matched_pack_A_baseline": True,
                "exclude_labels": ["UNKNOWN", "INSUFFICIENT_EVIDENCE", "EXCLUDED"],
                "exclude_low_confidence": True,
                "exclude_invalid_output": True,
                "exclude_ambiguous_or_missing_outcome_join": True,
                "existing_blinded_counts": {
                    "positive_eligible": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("positive_eligible_count", 0),
                    "negative_eligible": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("negative_eligible_count", 0),
                    "matched_baseline_to_expanded_pairs": len(eligible_consistency_expanded),
                },
            },
            "exploratory_relevance_rule": {
                "mechanism_id": EXPLORATORY_MECHANISM_ID,
                "status": "EXPLORATORY_ONLY",
                "include_labels": ["POSITIVE", "NEGATIVE"],
                "require_confidence": ["HIGH", "MODERATE"],
                "negative_count_warning": mechanism_stats.get(EXPLORATORY_MECHANISM, {}).get("negative_eligible_count", 0),
                "familywise_claim_allowed": False,
            },
            "specificity_rule": {
                "mechanism_id": DESCRIPTIVE_ONLY_MECHANISM_ID,
                "status": "DESCRIPTIVE_ONLY_PENDING_SAMPLE_EXPANSION",
                "binary_inferential_test_allowed": False,
                "future_sample_gates": SPECIFICITY_FUTURE_SAMPLE_GATES,
            },
        },
        "Refined_Mechanism_Test_Frozen_Confidence_Rules": {
            "primary_analysis": "HIGH_AND_MODERATE_ONLY",
            "sensitivity_analysis": "include_LOW_without_upgrading_original_confidence",
            "low_confidence_primary_allowed": False,
            "reviewed_low_confidence_case": "may_only_enter_preregistered_sensitivity_analysis",
            "unknown_confidence_rule": "exclude_unless_future_secondary_analysis_explicitly_preregistered",
            "planning_source": planning_confidence,
        },
        "Refined_Mechanism_Test_Frozen_Unknown_Rules": {
            "UNKNOWN": planning_unknowns.get("UNKNOWN", "EXCLUDE_FROM_PRIMARY_BINARY_TEST_AND_REPORT_DESCRIPTIVELY"),
            "INSUFFICIENT_EVIDENCE": planning_unknowns.get(
                "INSUFFICIENT_EVIDENCE",
                "EXCLUDE_FROM_PRIMARY_BINARY_TEST_AND_REPORT_DESCRIPTIVELY",
            ),
            "NEGATIVE": planning_unknowns.get("NEGATIVE", "AFFIRMATIVE_ABSENCE_ONLY_NOT_MISSINGNESS"),
            "EXCLUDED": planning_unknowns.get("EXCLUDED", "NEVER_INCLUDE"),
            "combination_rule": "UNKNOWN_and_INSUFFICIENT_EVIDENCE_must_not_be_combined_with_NEGATIVE_in_the_primary_test",
        },
        "Refined_Mechanism_Test_Frozen_Confounder_Rules": confounder_rules,
        "Refined_Mechanism_Test_Frozen_Multiple_Testing": {
            "primary_family": {
                "family_name": "PM003_PRIMARY_ONLY",
                "members": ["RMTP-H1"],
                "multiplicity_correction": "NOT_REQUIRED_FOR_SINGLE_PRIMARY_TEST",
            },
            "secondary_family": {
                "members": ["RMTP-H2"],
                "interpretation": "secondary_supporting_only_and_cannot_reverse_primary_conclusion",
            },
            "exploratory_family": {
                "members": [row["hypothesis_id"] for row in exploratory_hypotheses],
                "interpretation": "reported_without_confirmatory_claims; if p_values_are_reported_later_use_BH_FDR_within_exploratory_family",
            },
        },
        "Refined_Mechanism_Test_Frozen_Missing_Data": missing_data_rules,
        "Refined_Mechanism_Test_Frozen_Stop_Rules": {
            "sample_gates": PRIMARY_SAMPLE_GATES,
            "existing_blinded_counts": {
                "positive": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("positive_eligible_count", 0),
                "negative": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("negative_eligible_count", 0),
                "matched_pairs": len(eligible_consistency_expanded),
                "clusters": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("independent_cluster_count", 0),
                "providers": primary_provider_count,
                "sessions": primary_session_count,
                "max_single_cluster_share": round(max_cluster_share, 6),
            },
            "primary_design_adequacy": primary_design_adequacy,
            "stop_rules": stop_rules,
        },
        "Refined_Mechanism_Test_Frozen_Reporting_Plan": reporting_plan,
        "Refined_Mechanism_Test_Preregistration_Governance": {
            "provider_calls_performed": 0,
            "forecasts_generated": 0,
            "classification_rerun_performed": 0,
            "permanent_labels_modified": 0,
            "mechanism_tests_performed": 0,
            "accuracy_metrics_calculated": 0,
            "outcome_values_accessed": 0,
            "outcome_rows_loaded": 0,
            "provider_rankings_produced": 0,
            "v1_1_rules_modified": 0,
            "classifications_modified": 0,
            "production_writes": 0,
            "production_behavior_changes": 0,
            "notes": "Blinded preregistration only; no outcome join or test execution performed by the builder.",
        },
        "Refined_Mechanism_Test_Preregistration_Summary": {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "test_preregistration_version": TEST_PREREGISTRATION_VERSION,
            "preregistration_status": TEST_PREREGISTRATION_STATUS,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "primary_mechanism": PRIMARY_MECHANISM,
            "exploratory_mechanisms": [EXPLORATORY_MECHANISM],
            "descriptive_only_mechanisms": [DESCRIPTIVE_ONLY_MECHANISM],
            "primary_hypothesis": primary_hypothesis["comparison"],
            "hypothesis_direction": primary_hypothesis["directionality"],
            "primary_unit_of_analysis": PRIMARY_UNIT_OF_ANALYSIS,
            "matching_key": MATCHING_KEY,
            "clustering_level": CLUSTERING_LEVEL,
            "primary_comparison": PRIMARY_COMPARISON,
            "primary_effect_measure": PRIMARY_EFFECT_MEASURE,
            "primary_statistical_method": PRIMARY_STATISTICAL_METHOD,
            "primary_outcome_source": PRIMARY_OUTCOME_SOURCE,
            "primary_outcome_field": PRIMARY_OUTCOME_FIELD,
            "outcome_join_key": OUTCOME_JOIN_KEY,
            "outcome_values_accessed": False,
            "positive_eligible_rule": "PM-003 expanded B-E POSITIVE with HIGH|MODERATE confidence and matched baseline Pack A control",
            "negative_eligible_rule": "PM-003 expanded B-E NEGATIVE with HIGH|MODERATE confidence and matched baseline Pack A control",
            "unknown_handling": "exclude_from_primary_and_report_descriptively",
            "insufficient_evidence_handling": "exclude_from_primary_and_report_descriptively",
            "excluded_handling": "never_include",
            "low_confidence_handling": "exclude_from_primary_include_only_in_one_preregistered_sensitivity_analysis",
            "missing_outcome_handling": missing_data_rules["missing_outcome"],
            "duplicate_outcome_handling": missing_data_rules["duplicate_outcome"],
            "minimum_positive_count": PRIMARY_SAMPLE_GATES["minimum_positive_count"],
            "minimum_negative_count": PRIMARY_SAMPLE_GATES["minimum_negative_count"],
            "minimum_matched_pairs": PRIMARY_SAMPLE_GATES["minimum_matched_pairs"],
            "minimum_clusters": PRIMARY_SAMPLE_GATES["minimum_clusters"],
            "minimum_providers": PRIMARY_SAMPLE_GATES["minimum_providers"],
            "minimum_sessions": PRIMARY_SAMPLE_GATES["minimum_sessions"],
            "existing_blinded_counts": {
                "consistency_positive": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("positive_eligible_count", 0),
                "consistency_negative": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("negative_eligible_count", 0),
                "consistency_matched_baseline_to_expanded_pairs": len(eligible_consistency_expanded),
                "consistency_independent_clusters": mechanism_stats.get(PRIMARY_MECHANISM, {}).get("independent_cluster_count", 0),
                "consistency_unique_providers": primary_provider_count,
                "consistency_unique_sessions": primary_session_count,
            },
            "primary_design_adequacy": primary_design_adequacy,
            "secondary_hypotheses": [secondary_hypothesis["comparison"]],
            "exploratory_hypotheses": [row["comparison"] for row in exploratory_hypotheses],
            "relevance_status": "EXPLORATORY_ONLY",
            "specificity_status": SPECIFICITY_STATUS,
            "co_occurrence_handling": "descriptive_or_sparse_sensitivity_only_no_isolated_causal_claim",
            "multiple_testing_plan": "single_primary_family_for_PM003_only",
            "outcomes_accessed": 0,
            "outcome_rows_loaded": 0,
            "accuracy_metrics_calculated": 0,
            "provider_rankings_produced": 0,
            "hypothesis_selected_from_outcomes": False,
            "metric_selected_from_results": False,
            "design_frozen": True,
            "mechanisms_ready_for_test_execution_approval": 1 if readiness_for_approval else 0,
            "ready_for_mechanism_test_execution_approval": readiness_for_approval,
            "ready_for_mechanism_testing": False,
            "ready_for_production": False,
            "recommended_next_step": recommended_next_step,
            "notes": (
                "MECH_INFORMATION_CONSISTENCY is the only primary mechanism. Relevance remains exploratory only. "
                "Specificity remains descriptive/sample-expansion-only. Pack A stays excluded as a structural control rather than "
                "being coerced into a mechanism-negative label."
            ),
        },
    }

    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "preregistration_run_id": preregistration_run_id,
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
        "preregistration_run_id": preregistration_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Preregistration_Summary"],
        "budget_maintenance": budget_maintenance,
        "registry_writes": registry_writes,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
