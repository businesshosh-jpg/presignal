#!/usr/bin/env python3
"""Phase 9A-6R12 — Refined Mechanism Test Planning Readiness.

This phase evaluates whether the permanent v1.1 refined mechanism
classifications can support a scientifically defensible, preregistered
mechanism test design without accessing any outcomes.
"""

from __future__ import annotations

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


PHASE_ID = "9A-6R12"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_planning_readiness_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_planning_readiness_v0"
READINESS_VERSION = "refined_mechanism_test_planning_readiness_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_PLANNING"
REGISTRY_OWNER_MODULE = "market_state"

CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_VERSION = "1.1"
PREREGISTRATION_VERSION = "1.1"
MECHANISMS = [
    "MECH_INFORMATION_RELEVANCE",
    "MECH_INFORMATION_SPECIFICITY",
    "MECH_INFORMATION_CONSISTENCY",
]

INPUT_SHEETS: Tuple[str, ...] = (
    # Permanent classifications
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Evidence",
    "Refined_Mechanism_v11_Classification_Conflicts",
    "Refined_Mechanism_v11_Classification_Confidence",
    "Refined_Mechanism_v11_Classification_Audit",
    "Refined_Mechanism_v11_Classification_Governance",
    "Refined_Mechanism_v11_Classification_Summary",
    # Phase 9A-6R11 review
    "Refined_Mechanism_v11_Execution_Review",
    "Refined_Mechanism_v11_Run_Identity_Audit",
    "Refined_Mechanism_v11_Classification_Reconciliation",
    "Refined_Mechanism_v11_Resume_Idempotence_Audit",
    "Refined_Mechanism_v11_Conflict_Disposition_Review",
    "Refined_Mechanism_v11_Trace_Completeness_Review",
    "Refined_Mechanism_v11_Compact_Support_Audit",
    "Refined_Mechanism_v11_Determinism_Review",
    "Refined_Mechanism_v11_Leakage_Review",
    "Refined_Mechanism_v11_Stop_Rule_Review",
    "Refined_Mechanism_v11_Execution_Review_Governance",
    "Refined_Mechanism_v11_Execution_Review_Summary",
    # Frozen v1.1 definitions and governance
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


OUTPUT_SHEETS = [
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
]

COMMON_HEADERS = ["generated_ts", "schema_version", "readiness_run_id", "payload_json"]

OUTPUT_LOGICAL_IDS = {
    name: name.upper() for name in OUTPUT_SHEETS
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id(ts: datetime) -> str:
    return f"9A-6R12_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _single_row(rows: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    return dict(rows[0]) if rows else {}


def _latest_ready_review_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    ready_rows = [
        dict(row)
        for row in rows
        if _normalize(row.get("final_interpretation"))
        in {
            "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY",
            "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY_WITH_WARNINGS",
        }
    ]
    if not ready_rows:
        return {}
    ready_rows.sort(key=lambda row: (_normalize(row.get("generated_ts")), _normalize(row.get("review_run_id"))))
    return ready_rows[-1]


def _source_rows(class_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in class_rows:
        source_key = _normalize(row.get("source_row_key"))
        bucket = out.setdefault(
            source_key,
            {
                "source_row_key": source_key,
                "provider": _normalize(row.get("provider")),
                "session_id": _normalize(row.get("session_id")),
                "pack_level": _normalize(row.get("pack_level")),
                "labels": {},
                "confidence": {},
                "eligibility": {},
            },
        )
        mech = _normalize(row.get("mechanism_id"))
        bucket["labels"][mech] = _normalize(row.get("classification_label"))
        bucket["confidence"][mech] = _normalize(row.get("confidence_category"))
        bucket["eligibility"][mech] = _normalize(row.get("eligibility_status"))
    return out


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


def _ensure_cell_budget(service, known_titles: Set[str]):
    current = _sheet_cell_total(service)
    required = sum(2 * len(COMMON_HEADERS) for name in OUTPUT_SHEETS if name not in known_titles)
    if current + required > 10_000_000:
        raise RuntimeError(
            f"Insufficient workbook cell budget for Phase 9A-6R12 outputs: current={current}, required={required}."
        )


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
            "notes": "Phase 9A-6R12 blinded mechanism-test planning readiness outputs.",
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
    readiness_run_id = _run_id(run_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    _ensure_cell_budget(service, known_titles)

    execution_review_summary = _latest_ready_review_summary(inputs["Refined_Mechanism_v11_Execution_Review_Summary"].rows)
    if _normalize(execution_review_summary.get("final_interpretation")) not in {
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY",
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY_WITH_WARNINGS",
    }:
        raise RuntimeError("Phase 9A-6R11 execution review is not ready for test-planning readiness.")

    class_rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID
    ]
    if len(class_rows) != 360:
        raise RuntimeError(f"Expected 360 classification rows for {CLASSIFICATION_RUN_ID}, found {len(class_rows)}.")

    class_summary = _single_row(
        [row for row in inputs["Refined_Mechanism_v11_Classification_Summary"].rows if _normalize(row.get("classification_run_id")) == CLASSIFICATION_RUN_ID]
    )
    source_rows = _source_rows(class_rows)

    unique_source_rows = len(source_rows)
    unique_providers = len({_normalize(row.get("provider")) for row in class_rows})
    unique_sessions = len({_normalize(row.get("session_id")) for row in class_rows})
    unique_forecast_runs = unique_source_rows
    provider_session_clusters = {(row["provider"], row["session_id"]) for row in source_rows.values()}
    independent_clusters = len(provider_session_clusters)
    session_clusters = len({row["session_id"] for row in source_rows.values()})
    candidate_matched_pairs = len([row for row in source_rows.values() if row["pack_level"] != "A" and any(v != "EXCLUDED" for v in row["labels"].values())])

    label_distribution = Counter(_normalize(row.get("classification_label")) for row in class_rows)
    confidence_distribution = Counter(_normalize(row.get("confidence_category")) for row in class_rows)

    mechanism_stats: Dict[str, Dict[str, Any]] = {}
    by_source = source_rows
    pairwise_positive_counts = {
        "relevance_specificity": 0,
        "specificity_consistency": 0,
        "relevance_consistency": 0,
        "all_three": 0,
        "relevance_only": 0,
        "specificity_only": 0,
        "consistency_only": 0,
    }
    for source in by_source.values():
        pos = {mech for mech, label in source["labels"].items() if label == "POSITIVE"}
        if {"MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_SPECIFICITY"}.issubset(pos):
            pairwise_positive_counts["relevance_specificity"] += 1
        if {"MECH_INFORMATION_SPECIFICITY", "MECH_INFORMATION_CONSISTENCY"}.issubset(pos):
            pairwise_positive_counts["specificity_consistency"] += 1
        if {"MECH_INFORMATION_RELEVANCE", "MECH_INFORMATION_CONSISTENCY"}.issubset(pos):
            pairwise_positive_counts["relevance_consistency"] += 1
        if len(pos) == 3:
            pairwise_positive_counts["all_three"] += 1
        if pos == {"MECH_INFORMATION_RELEVANCE"}:
            pairwise_positive_counts["relevance_only"] += 1
        if pos == {"MECH_INFORMATION_SPECIFICITY"}:
            pairwise_positive_counts["specificity_only"] += 1
        if pos == {"MECH_INFORMATION_CONSISTENCY"}:
            pairwise_positive_counts["consistency_only"] += 1

    for mech in MECHANISMS:
        rows = [row for row in class_rows if _normalize(row.get("mechanism_id")) == mech]
        label_counts = Counter(_normalize(row.get("classification_label")) for row in rows)
        confidence_counts = Counter(_normalize(row.get("confidence_category")) for row in rows)
        pos_neg_clusters = {
            (_normalize(row.get("provider")), _normalize(row.get("session_id")))
            for row in rows
            if _normalize(row.get("classification_label")) in {"POSITIVE", "NEGATIVE"}
        }
        matched_clusters = set()
        pos_neg_pairs = 0
        by_cluster: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_cluster[(_normalize(row.get("provider")), _normalize(row.get("session_id")))].append(row)
            by_session[_normalize(row.get("session_id"))].append(row)
        neg_provider_counts = Counter(_normalize(row.get("provider")) for row in rows if _normalize(row.get("classification_label")) == "NEGATIVE")
        for cluster, grp in by_cluster.items():
            pos = [row for row in grp if _normalize(row.get("classification_label")) == "POSITIVE"]
            neg = [row for row in grp if _normalize(row.get("classification_label")) == "NEGATIVE"]
            if pos and neg:
                matched_clusters.add(cluster)
                pos_neg_pairs += len(pos) * len(neg)
        pos_sessions = sum(1 for grp in by_session.values() if any(_normalize(row.get("classification_label")) == "POSITIVE" for row in grp))
        neg_sessions = sum(1 for grp in by_session.values() if any(_normalize(row.get("classification_label")) == "NEGATIVE" for row in grp))
        both_sessions = sum(
            1
            for grp in by_session.values()
            if any(_normalize(row.get("classification_label")) == "POSITIVE" for row in grp)
            and any(_normalize(row.get("classification_label")) == "NEGATIVE" for row in grp)
        )

        if mech == "MECH_INFORMATION_CONSISTENCY":
            co_occurrence_status = "PARTIAL_SEPARATION"
            sample_adequacy_status = "ADEQUATE_FOR_EXPLORATORY_TEST"
            recommended_test_design = "DESIGN_D_WITHIN_PROVIDER_SESSION_BASELINE_TO_EXPANDED_PLUS_DESIGN_C_MATCHED_POSITIVE_VS_NEGATIVE"
            testability_status = "READY_FOR_TEST_PREREGISTRATION"
        elif mech == "MECH_INFORMATION_RELEVANCE":
            co_occurrence_status = "HIGH_COLLINEARITY"
            sample_adequacy_status = "UNDERPOWERED_FOR_BINARY_TEST"
            recommended_test_design = "DESIGN_C_WITHIN_PROVIDER_SESSION_MATCHED_POSITIVE_VS_NEGATIVE_SENSITIVITY_ONLY"
            testability_status = "READY_FOR_EXPLORATORY_PREREGISTRATION"
        else:
            co_occurrence_status = "HIGH_COLLINEARITY"
            sample_adequacy_status = "UNDERPOWERED_FOR_BINARY_TEST"
            recommended_test_design = "DESIGN_D_BASELINE_TO_EXPANDED_DESCRIPTIVE_OR_SAMPLE_EXPANSION_FIRST"
            testability_status = "NEEDS_SAMPLE_EXPANSION"

        mechanism_stats[mech] = {
            "positive_eligible_count": label_counts.get("POSITIVE", 0),
            "negative_eligible_count": label_counts.get("NEGATIVE", 0),
            "unknown_count": label_counts.get("UNKNOWN", 0),
            "insufficient_evidence_count": label_counts.get("INSUFFICIENT_EVIDENCE", 0),
            "excluded_count": label_counts.get("EXCLUDED", 0),
            "independent_cluster_count": len(pos_neg_clusters),
            "matched_pair_count": len(matched_clusters),
            "candidate_pos_neg_pair_count": pos_neg_pairs,
            "positive_session_count": pos_sessions,
            "negative_session_count": neg_sessions,
            "matched_session_count": both_sessions,
            "confidence_counts": dict(confidence_counts),
            "negative_provider_counts": dict(neg_provider_counts),
            "co_occurrence_status": co_occurrence_status,
            "sample_adequacy_status": sample_adequacy_status,
            "recommended_test_design": recommended_test_design,
            "testability_status": testability_status,
        }

    primary_unit = "provider_session_pack_forecast_observation"
    required_clustering_level = "provider_session_cluster_nested_within_shared_session_outcome_family"
    primary_comparison_design = "DESIGN_D_WITHIN_PROVIDER_SESSION_BASELINE_TO_EXPANDED_DELTA_FOR_MECH_INFORMATION_CONSISTENCY"
    secondary_comparison_designs = [
        "DESIGN_C_WITHIN_PROVIDER_SESSION_MATCHED_POSITIVE_VS_NEGATIVE",
        "DESIGN_A_POOLED_POSITIVE_VS_NEGATIVE_WITH_PROVIDER_AND_SESSION_CONTROLS",
    ]
    designs_rejected = [
        "DESIGN_B_POSITIVE_VS_NON_POSITIVE_WITH_UNKNOWN_AS_ABSENCE",
        "RAW_360_ROW_UNCLUSTERED_COMPARISON",
    ]
    pseudoreplication_risk = "HIGH_IF_ROW_LEVEL_OR_SOURCE_ROW_LEVEL_OUTCOMES_ARE_TREATED_AS_INDEPENDENT"
    highest_confounder_risk = "shared_session_outcome_plus_provider_and_pack_condition_confounding"
    mechanism_collinearity_status = "HIGH_COLLINEARITY"
    confidence_handling = {
        "primary_analysis": "HIGH_AND_MODERATE_CONFIDENCE_ONLY",
        "sensitivity_analysis": "LOW_CONFIDENCE_INCLUDED_WITHOUT_UPGRADING_THE_SINGLE_REVIEWED_LOW_CASE",
        "unknown_confidence": "EXCLUDE_UNLESS_EXPLICITLY_PREREGISTERED",
    }
    unknown_handling = {
        "UNKNOWN": "EXCLUDE_FROM_PRIMARY_BINARY_TEST_AND_REPORT_DESCRIPTIVELY",
        "INSUFFICIENT_EVIDENCE": "EXCLUDE_FROM_PRIMARY_BINARY_TEST_AND_REPORT_DESCRIPTIVELY",
        "EXCLUDED": "NEVER_INCLUDE",
        "NEGATIVE": "AFFIRMATIVE_ABSENCE_ONLY_NOT_MISSINGNESS",
    }
    multiple_testing_plan_requirement = "ONE_PRIMARY_MECHANISM_FAMILY_WITH_HIERARCHICAL_SECONDARY_AND_EXPLORATORY_ANALYSES"

    confounder_map = [
        {
            "confounder_id": "CONF_PROVIDER_IDENTITY",
            "why_it_matters": "provider behavior and model family vary systematically",
            "available_control_field": "provider",
            "proposed_handling": "within-provider matching plus provider-fixed control",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
        {
            "confounder_id": "CONF_SHARED_SESSION_OUTCOME",
            "why_it_matters": "packs and providers tied to the same session share one realized outcome",
            "available_control_field": "session_id",
            "proposed_handling": "cluster or match within provider_session and treat session as higher-level shared outcome family",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
        {
            "confounder_id": "CONF_PACK_CONDITION",
            "why_it_matters": "mechanism presence may co-vary with baseline vs expanded information context",
            "available_control_field": "pack_level",
            "proposed_handling": "baseline-to-expanded paired design and pack-stratified sensitivity",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
        {
            "confounder_id": "CONF_MECHANISM_COOCCURRENCE",
            "why_it_matters": "isolated mechanism effects are weakly separable because positives often overlap",
            "available_control_field": "other_mechanism_labels",
            "proposed_handling": "pre-register joint-pattern or multivariable sensitivity analysis",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
        {
            "confounder_id": "CONF_NEGATIVE_CLASS_THINNESS",
            "why_it_matters": "negative labels are sparse and unevenly distributed, especially for specificity",
            "available_control_field": "mechanism_label_counts_by_provider_session",
            "proposed_handling": "limit primary inference to the strongest mechanism and push weak mechanisms to exploratory or sample expansion",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
        {
            "confounder_id": "CONF_INVALID_OUTPUT_EXCLUSION",
            "why_it_matters": "excluded invalid-output rows may alter provider and pack balance",
            "available_control_field": "exclusion_status",
            "proposed_handling": "freeze exclusion rules and describe excluded population separately",
            "required": True,
            "controllable_now": True,
            "blocks_primary_test": False,
        },
    ]

    outcome_definition_requirements = [
        "freeze_canonical_outcome_source_before_outcome_access",
        "freeze_corrected_market_reaction_mapping",
        "freeze_evaluation_window_and_missing_outcome_handling",
        "freeze_no_signal_and_flat_treatment",
        "freeze_provider_neutral_scoring_and_duplicate_outcome_handling",
    ]
    preregistration_requirements = [
        "mechanism_version",
        "classification_run_id",
        "eligible_mechanism_labels",
        "confidence_inclusion_rules",
        "conflict_handling",
        "exclusion_rules",
        "unit_of_analysis",
        "cluster_or_matched_key",
        "canonical_outcome_source",
        "outcome_metric",
        "evaluation_window",
        "provider_session_controls",
        "hypothesis_direction",
        "primary_vs_secondary_tests",
        "multiple_testing_handling",
        "missing_data_rules",
        "minimum_sample_criteria",
        "stop_rules",
        "reporting_format",
    ]

    hypotheses = {
        "primary": [
            {
                "mechanism": "MECH_INFORMATION_CONSISTENCY",
                "statement": "Positive versus negative consistency classifications differ on a future corrected outcome metric under a provider-session clustered paired design.",
            }
        ],
        "secondary": [
            {
                "mechanism": "MECH_INFORMATION_RELEVANCE",
                "statement": "Within-provider-session matched relevance-positive versus relevance-negative comparisons differ on a preregistered corrected outcome metric.",
            }
        ],
        "exploratory": [
            {
                "mechanism": "MECH_INFORMATION_SPECIFICITY",
                "statement": "Specificity associations are estimated descriptively or only after sample expansion because the current negative class is thin and provider-concentrated.",
            },
            {
                "mechanism": "JOINT_PATTERNS",
                "statement": "Co-occurring mechanism patterns may differ from isolated mechanisms under preregistered joint-pattern analyses.",
            },
        ],
    }

    mechanisms_ready_for_test_prereg = sum(1 for mech in mechanism_stats.values() if mech["testability_status"] == "READY_FOR_TEST_PREREGISTRATION")
    mechanisms_exploratory_only = sum(1 for mech in mechanism_stats.values() if mech["testability_status"] == "READY_FOR_EXPLORATORY_PREREGISTRATION")
    mechanisms_needing_sample_expansion = sum(1 for mech in mechanism_stats.values() if mech["testability_status"] == "NEEDS_SAMPLE_EXPANSION")
    ready_for_test_design = mechanisms_ready_for_test_prereg >= 1

    final_interpretation = (
        "REFINED_MECHANISM_TEST_PLANNING_READINESS_READY_WITH_WARNINGS"
        if ready_for_test_design
        else "REFINED_MECHANISM_TEST_PLANNING_READINESS_SAMPLE_INADEQUATE"
    )
    build_status = "PASS_WITH_WARNINGS" if ready_for_test_design else "FAIL"
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R13_MECHANISM_TEST_DESIGN_AND_PREREGISTRATION"
        if ready_for_test_design
        else "EXPAND_MECHANISM_CLASSIFICATION_SAMPLE_BEFORE_TESTING"
    )

    payloads = {
        "Refined_Mechanism_Test_Planning_Readiness": {
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "final_interpretation": final_interpretation,
            "overall_readiness": ready_for_test_design,
            "scientific_guardrail": "No outcomes accessed; this phase only assesses whether a blinded experiment can be designed fairly.",
        },
        "Refined_Mechanism_Test_Unit_Of_Analysis": {
            "primary_unit_of_analysis": primary_unit,
            "required_clustering_level": required_clustering_level,
            "matched_design_unit": "provider_session_baseline_pack_A_to_expanded_pack_B_to_E",
            "pseudoreplication_rule": "360 mechanism rows are not independent outcome observations.",
        },
        "Refined_Mechanism_Test_Population_Structure": {
            "classification_rows": len(class_rows),
            "unique_source_rows": unique_source_rows,
            "unique_providers": unique_providers,
            "unique_sessions": unique_sessions,
            "unique_forecast_runs": unique_forecast_runs,
            "independent_clusters": {"provider_session_clusters": independent_clusters, "session_outcome_families": session_clusters},
            "candidate_matched_pairs": candidate_matched_pairs,
            "label_distribution": dict(label_distribution),
            "confidence_distribution": dict(confidence_distribution),
        },
        "Refined_Mechanism_Test_Label_Eligibility": {
            "primary_eligibility_rule": "POSITIVE_vs_NEGATIVE_only",
            "unknown_rule": unknown_handling["UNKNOWN"],
            "insufficient_evidence_rule": unknown_handling["INSUFFICIENT_EVIDENCE"],
            "excluded_rule": unknown_handling["EXCLUDED"],
            "per_mechanism": mechanism_stats,
        },
        "Refined_Mechanism_Test_Comparison_Design": {
            "design_A_positive_vs_negative": {
                "status": "SECONDARY_CANDIDATE",
                "notes": "Requires provider/session controls and cannot be run as an unclustered pooled test.",
            },
            "design_B_positive_vs_non_positive": {
                "status": "NOT_SUPPORTED",
                "notes": "UNKNOWN and INSUFFICIENT_EVIDENCE must not be silently recast as absence.",
            },
            "design_C_within_provider_matched": {
                "status": "PRIMARY_CANDIDATE",
                "notes": "Best for controlling provider confounding where positive and negative labels coexist inside provider-session clusters.",
            },
            "design_D_within_session_or_paired_pack": {
                "status": "PRIMARY_CANDIDATE",
                "notes": "Best aligned with added-information mechanisms via baseline A to expanded B-E paired comparisons.",
            },
            "design_E_multivariable_clustered_model": {
                "status": "SENSITIVITY_ONLY",
                "notes": "High collinearity and limited cluster count cap model complexity.",
            },
        },
        "Refined_Mechanism_Test_Confounder_Map": confounder_map,
        "Refined_Mechanism_Test_Independence_Audit": {
            "shared_outcome_structure": {
                "mechanism_rows": 360,
                "source_rows": 120,
                "provider_session_clusters": independent_clusters,
                "session_outcome_families": session_clusters,
            },
            "repeated_measures": "five pack conditions per provider-session, three mechanism labels per source row",
            "raw_row_level_test_allowed": False,
            "recommended_handling": "clustered_or_matched_design_required",
        },
        "Refined_Mechanism_Test_Sample_Adequacy": {
            "hypothetical_effect_size_scenarios": ["small", "moderate", "large"],
            "per_mechanism": {
                mech: {
                    "positive_eligible_count": stats["positive_eligible_count"],
                    "negative_eligible_count": stats["negative_eligible_count"],
                    "independent_cluster_count": stats["independent_cluster_count"],
                    "matched_pair_count": stats["matched_pair_count"],
                    "sample_adequacy_status": stats["sample_adequacy_status"],
                }
                for mech, stats in mechanism_stats.items()
            },
        },
        "Refined_Mechanism_Test_Unknown_Handling": unknown_handling,
        "Refined_Mechanism_Test_Confidence_Handling": confidence_handling,
        "Refined_Mechanism_Test_Leakage_Boundary": {
            "outcome_accessed": False,
            "forbidden_sources": [
                "Outcome_Ledger",
                "Evaluation_Rows",
                "Controlled_Accuracy_Evaluation",
                "Corrected_Accuracy_Evaluation",
                "realized_direction",
                "overall_ok",
                "market_reaction_outcomes",
            ],
            "future_requirement": "freeze_outcome_definition_before_any_outcome_access",
        },
        "Refined_Mechanism_Test_Preregistration_Requirements": {
            "requirements_defined": len(preregistration_requirements),
            "outcome_definition_requirements": outcome_definition_requirements,
            "full_preregistration_requirements": preregistration_requirements,
            "hypotheses": hypotheses,
        },
        "Refined_Mechanism_Test_Planning_Governance": {
            "provider_calls_performed": 0,
            "forecasts_generated": 0,
            "classification_rerun_performed": 0,
            "permanent_labels_modified": 0,
            "mechanism_tests_performed": 0,
            "accuracy_metrics_calculated": 0,
            "outcomes_accessed": 0,
            "outcome_sheets_accessed": 0,
            "provider_rankings_produced": 0,
            "v1_1_rules_modified": 0,
            "production_writes": 0,
            "production_behavior_changes": 0,
        },
        "Refined_Mechanism_Test_Planning_Readiness_Summary": {
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "classification_run_id": CLASSIFICATION_RUN_ID,
            "mechanisms_reviewed": len(MECHANISMS),
            "classification_rows_reviewed": len(class_rows),
            "positive_labels": label_distribution.get("POSITIVE", 0),
            "negative_labels": label_distribution.get("NEGATIVE", 0),
            "unknown_labels": label_distribution.get("UNKNOWN", 0),
            "insufficient_evidence_labels": label_distribution.get("INSUFFICIENT_EVIDENCE", 0),
            "excluded_labels": label_distribution.get("EXCLUDED", 0),
            "unique_source_rows": unique_source_rows,
            "unique_providers": unique_providers,
            "unique_sessions": unique_sessions,
            "unique_forecast_runs": unique_forecast_runs,
            "independent_clusters": independent_clusters,
            "candidate_matched_pairs": candidate_matched_pairs,
            "mechanism_stats": mechanism_stats,
            "primary_unit_of_analysis": primary_unit,
            "required_clustering_level": required_clustering_level,
            "primary_comparison_design": primary_comparison_design,
            "secondary_comparison_designs": secondary_comparison_designs,
            "designs_rejected": designs_rejected,
            "pseudoreplication_risk": pseudoreplication_risk,
            "highest_confounder_risk": highest_confounder_risk,
            "mechanism_collinearity_status": mechanism_collinearity_status,
            "confidence_handling": confidence_handling,
            "unknown_handling": unknown_handling,
            "multiple_testing_plan_requirement": multiple_testing_plan_requirement,
            "requirements_defined": len(preregistration_requirements),
            "outcome_definition_frozen": False,
            "outcome_accessed": False,
            "hypotheses_proposed": sum(len(v) for v in hypotheses.values()),
            "primary_hypotheses": len(hypotheses["primary"]),
            "secondary_hypotheses": len(hypotheses["secondary"]),
            "exploratory_hypotheses": len(hypotheses["exploratory"]),
            "mechanisms_ready_for_test_preregistration": mechanisms_ready_for_test_prereg,
            "mechanisms_exploratory_only": mechanisms_exploratory_only,
            "mechanisms_needing_sample_expansion": mechanisms_needing_sample_expansion,
            "ready_for_mechanism_test_design_and_preregistration": ready_for_test_design,
            "ready_for_mechanism_testing": False,
            "ready_for_production": False,
            "recommended_next_step": recommended_next_step,
            "notes": "Consistency is the strongest primary candidate; relevance is exploratory only; specificity needs sample expansion because negatives are thin and provider-skewed.",
        },
    }

    rows_written: Dict[str, int] = {}
    for sheet_name in OUTPUT_SHEETS:
        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "readiness_run_id": readiness_run_id,
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
        "readiness_run_id": readiness_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": rows_written,
        "summary": payloads["Refined_Mechanism_Test_Planning_Readiness_Summary"],
        "registry_writes": registry_writes,
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
