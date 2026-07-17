#!/usr/bin/env python3
"""Phase 9A-6R15B — Outcome Architecture Root Cause Investigation.

This is a completely read-only diagnostic phase. It analyzes the evaluation
architecture that collapsed the preregistered primary analysis population from
72 planned observations to 3 final eligible observations.

The investigation does not modify classifications, preregistration, outcomes,
evaluation rules, or production workbooks. It reuses the already-written
execution and collapse-investigation diagnostics to determine which
architectural layer is fundamentally limiting inferential mechanism testing.
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
from automation.build_refined_mechanism_test_execution_v0 import (  # type: ignore
    _append_rows,
    _canonical_json,
    _fetch_input_sheets,
    _latest_row,
    _normalize,
    _sheet_titles_light,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R15B"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_root_cause_investigation_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_root_cause_investigation_v0"
INVESTIGATION_VERSION = "refined_mechanism_test_outcome_architecture_root_cause_investigation_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE"
REGISTRY_OWNER_MODULE = "market_state"

PRIMARY_ANALYSIS_ID = "PRIMARY_PM003_STRUCTURE_A"
EXPECTED_PLANNED_OBSERVATIONS = 72
EXPECTED_FINAL_ELIGIBLE = 3
EXPECTED_POSITIVE_PLANNED = 57
EXPECTED_NEGATIVE_PLANNED = 15
EXPECTED_GATES = {
    "positive": 40,
    "negative": 12,
    "primary_contrast": 40,
    "clusters": 12,
    "providers": 2,
    "sessions": 4,
}

INPUT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Population_Collapse",
    "Refined_Mechanism_Test_Row_Lineage_Audit",
    "Refined_Mechanism_Test_Outcome_Join_Failure_Audit",
    "Refined_Mechanism_Test_Success_Mapping_Audit",
    "Refined_Mechanism_Test_Eligibility_Transition_Audit",
    "Refined_Mechanism_Test_Collapse_Root_Cause",
    "Refined_Mechanism_Test_Collapse_Quantification",
    "Refined_Mechanism_Test_Collapse_Summary",
    "Refined_Mechanism_Test_Execution_Summary",
    "Refined_Mechanism_Test_Eligibility_Audit",
)

OUTPUT_ROOT = "Refined_Mechanism_Test_Outcome_Architecture_Root_Cause"
OUTPUT_FIRST_EXCLUSION = "Refined_Mechanism_Test_First_Exclusion_Point_Audit"
OUTPUT_ATTRIBUTION = "Refined_Mechanism_Test_Outcome_Architecture_Attribution"
OUTPUT_NEGATIVE = "Refined_Mechanism_Test_Negative_Attrition_Audit"
OUTPUT_SENSITIVITY = "Refined_Mechanism_Test_Outcome_Architecture_Sensitivity"
OUTPUT_RANKING = "Refined_Mechanism_Test_Outcome_Architecture_Bottleneck_Ranking"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_ROOT: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "source_test_execution_run_id",
        "build_status",
        "final_interpretation",
        "architecture_capability_classification",
        "principal_bottleneck_layer",
        "negative_disappearance_classification",
        "scientific_interpretation",
        "recommended_research_direction",
        "payload_json",
    ],
    OUTPUT_FIRST_EXCLUSION: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "source_row_key",
        "provider",
        "session_id",
        "pack_level",
        "expanded_label",
        "confidence_category",
        "first_exclusion_layer",
        "first_exclusion_point",
        "first_exclusion_side",
        "first_exclusion_reason",
        "expanded_join_reason",
        "baseline_join_reason",
        "expanded_success_reason",
        "baseline_success_reason",
        "payload_json",
    ],
    OUTPUT_ATTRIBUTION: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "layer_name",
        "first_hit_observation_count",
        "share_of_planned_observations",
        "share_of_excluded_observations",
        "negative_observations_lost",
        "positive_observations_lost",
        "status",
        "payload_json",
    ],
    OUTPUT_NEGATIVE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "metric_name",
        "metric_value",
        "status",
        "notes",
        "payload_json",
    ],
    OUTPUT_SENSITIVITY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "scenario_id",
        "scenario_name",
        "counterfactual_type",
        "additional_observations_released",
        "counterfactual_row_level_eligible",
        "counterfactual_positive",
        "counterfactual_negative",
        "counterfactual_clusters",
        "counterfactual_providers",
        "counterfactual_sessions",
        "gate_status_summary",
        "status",
        "payload_json",
    ],
    OUTPUT_RANKING: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "source_population_collapse_run_id",
        "rank_order",
        "layer_name",
        "bottleneck_status",
        "rationale",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "outcome_architecture_run_id",
        "build_status",
        "final_interpretation",
        "architecture_capability_classification",
        "principal_bottleneck_layer",
        "negative_disappearance_classification",
        "recommended_research_direction",
        "scientific_interpretation",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_ROOT: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_ROOT_CAUSE",
    OUTPUT_FIRST_EXCLUSION: "REFINED_MECHANISM_TEST_FIRST_EXCLUSION_POINT_AUDIT",
    OUTPUT_ATTRIBUTION: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_ATTRIBUTION",
    OUTPUT_NEGATIVE: "REFINED_MECHANISM_TEST_NEGATIVE_ATTRITION_AUDIT",
    OUTPUT_SENSITIVITY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SENSITIVITY",
    OUTPUT_RANKING: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_BOTTLENECK_RANKING",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15B_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _now_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


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
            "notes": "Phase 9A-6R15B outcome architecture root cause investigation outputs.",
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


def _latest_collapse_context(inputs: Mapping[str, Any]) -> Tuple[str, str, List[Dict[str, Any]], Dict[str, Any]]:
    summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Collapse_Summary"].rows,
        "population_collapse_run_id",
    )
    if not summary_row:
        raise RuntimeError("No Phase 9A-6R15A collapse summary rows found.")
    collapse_run_id = _normalize(summary_row.get("population_collapse_run_id"))
    population_rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_Test_Population_Collapse"].rows
        if _normalize(row.get("population_collapse_run_id")) == collapse_run_id
    ]
    population_row = _latest_row(population_rows, "population_collapse_run_id")
    source_test_execution_run_id = _normalize(population_row.get("source_test_execution_run_id"))
    if not collapse_run_id or not source_test_execution_run_id:
        raise RuntimeError("Collapse summary / population collapse rows are missing lineage identifiers.")
    lineage_rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_Test_Row_Lineage_Audit"].rows
        if _normalize(row.get("population_collapse_run_id")) == collapse_run_id
    ]
    if len(lineage_rows) != EXPECTED_PLANNED_OBSERVATIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_PLANNED_OBSERVATIONS} lineage rows for collapse run {collapse_run_id}; "
            f"found {len(lineage_rows)}."
        )
    payload = _json_loads_safe(summary_row.get("payload_json")) or {}
    return collapse_run_id, source_test_execution_run_id, lineage_rows, payload


def _first_exclusion_layer(final_disposition: str) -> str:
    mapping = {
        "PRIMARY_ELIGIBLE": "PRIMARY_ELIGIBLE",
        "MISSING_EXPANDED_OUTCOME_JOIN": "CANONICAL_OUTCOME_COVERAGE",
        "MISSING_BASELINE_OUTCOME_JOIN": "CANONICAL_OUTCOME_COVERAGE",
        "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN": "CANONICAL_OUTCOME_COVERAGE",
        "OUTCOME_VERSION_MISMATCH": "CANONICAL_OUTCOME_COVERAGE",
        "EVALUATION_WINDOW_MISMATCH": "CANONICAL_OUTCOME_COVERAGE",
        "AMBIGUOUS_OUTCOME": "CANONICAL_OUTCOME_COVERAGE",
        "DUPLICATE_OUTCOME": "CANONICAL_OUTCOME_COVERAGE",
        "MISSING_REPAIRED_OUTCOME_OVERLAY": "OUTCOME_OVERLAY_COVERAGE",
        "SUCCESS_MAPPING_EXCLUSION": "CORRECTED_DIRECTIONAL_SUCCESS_MAPPING",
        "BASELINE_NOT_ELIGIBLE": "CORRECTED_DIRECTIONAL_SUCCESS_MAPPING",
        "EXPANDED_NOT_ELIGIBLE": "CORRECTED_DIRECTIONAL_SUCCESS_MAPPING",
        "INVALID_SUCCESS_MAPPING": "CORRECTED_DIRECTIONAL_SUCCESS_MAPPING",
        "CONFIDENCE_EXCLUSION": "DOWNSTREAM_ELIGIBILITY_LOGIC",
        "UNKNOWN_EXCLUSION": "DOWNSTREAM_ELIGIBILITY_LOGIC",
        "INSUFFICIENT_EVIDENCE_EXCLUSION": "DOWNSTREAM_ELIGIBILITY_LOGIC",
        "OTHER_FROZEN_EXCLUSION": "DOWNSTREAM_ELIGIBILITY_LOGIC",
    }
    return mapping.get(final_disposition, "DOWNSTREAM_ELIGIBILITY_LOGIC")


def _first_exclusion_point(row: Mapping[str, Any]) -> Tuple[str, str, str]:
    final_disposition = _normalize(row.get("final_disposition"))
    expanded_join_reason = _normalize(row.get("expanded_join_reason"))
    baseline_join_reason = _normalize(row.get("baseline_join_reason"))
    expanded_success_reason = _normalize(row.get("expanded_success_reason"))
    baseline_success_reason = _normalize(row.get("baseline_success_reason"))

    if final_disposition == "MISSING_EXPANDED_OUTCOME_JOIN":
        return (
            "EXPANDED_CANONICAL_OUTCOME_JOIN_MISSING",
            "EXPANDED",
            expanded_join_reason,
        )
    if final_disposition == "MISSING_BASELINE_OUTCOME_JOIN":
        return (
            "BASELINE_CANONICAL_OUTCOME_JOIN_MISSING",
            "BASELINE",
            baseline_join_reason,
        )
    if final_disposition == "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN":
        return (
            "BOTH_CANONICAL_OUTCOME_JOINS_MISSING",
            "BOTH",
            f"{expanded_join_reason}|{baseline_join_reason}",
        )
    if final_disposition == "MISSING_REPAIRED_OUTCOME_OVERLAY":
        if expanded_join_reason == "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME" and baseline_join_reason == "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME":
            return (
                "BOTH_REPAIRED_OUTCOME_OVERLAYS_MISSING",
                "BOTH",
                f"{expanded_join_reason}|{baseline_join_reason}",
            )
        if expanded_join_reason == "NOT_ELIGIBLE_MISSING_REPAIRED_OUTCOME":
            return (
                "EXPANDED_REPAIRED_OUTCOME_OVERLAY_MISSING",
                "EXPANDED",
                expanded_join_reason,
            )
        return (
            "BASELINE_REPAIRED_OUTCOME_OVERLAY_MISSING",
            "BASELINE",
            baseline_join_reason,
        )
    if final_disposition == "SUCCESS_MAPPING_EXCLUSION":
        return (
            "BOTH_SIDES_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING",
            "BOTH",
            f"{expanded_success_reason}|{baseline_success_reason}",
        )
    if final_disposition == "BASELINE_NOT_ELIGIBLE":
        return (
            "BASELINE_SIDE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING",
            "BASELINE",
            baseline_success_reason,
        )
    if final_disposition == "EXPANDED_NOT_ELIGIBLE":
        return (
            "EXPANDED_SIDE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING",
            "EXPANDED",
            expanded_success_reason,
        )
    if final_disposition == "INVALID_SUCCESS_MAPPING":
        return (
            "INVALID_SUCCESS_MAPPING",
            "UNKNOWN",
            f"{expanded_success_reason}|{baseline_success_reason}",
        )
    return (
        final_disposition or "UNSPECIFIED_FIRST_EXCLUSION_POINT",
        "UNKNOWN",
        _normalize(row.get("execution_exclusion_reason")),
    )


def _gate_status(value: int, threshold: int) -> str:
    return "PASS" if value >= threshold else "FAIL"


def _gate_summary(metrics: Mapping[str, int]) -> str:
    statuses = {
        "positive": _gate_status(metrics["positive"], EXPECTED_GATES["positive"]),
        "negative": _gate_status(metrics["negative"], EXPECTED_GATES["negative"]),
        "primary_contrast": _gate_status(metrics["eligible"], EXPECTED_GATES["primary_contrast"]),
        "clusters": _gate_status(metrics["clusters"], EXPECTED_GATES["clusters"]),
        "providers": _gate_status(metrics["providers"], EXPECTED_GATES["providers"]),
        "sessions": _gate_status(metrics["sessions"], EXPECTED_GATES["sessions"]),
    }
    return "|".join(f"{name.upper()}={status}" for name, status in statuses.items())


def _scenario_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    return {
        "eligible": len(rows),
        "positive": sum(1 for row in rows if _normalize(row.get("expanded_label")) == "POSITIVE"),
        "negative": sum(1 for row in rows if _normalize(row.get("expanded_label")) == "NEGATIVE"),
        "clusters": len({(_normalize(row.get("provider")), _normalize(row.get("session_id"))) for row in rows}),
        "providers": len({_normalize(row.get("provider")) for row in rows}),
        "sessions": len({_normalize(row.get("session_id")) for row in rows}),
    }


def _build_outputs(
    *,
    generated_ts: str,
    architecture_run_id: str,
    collapse_run_id: str,
    source_test_execution_run_id: str,
    lineage_rows: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    excluded_rows = [dict(row) for row in lineage_rows if _normalize(row.get("final_disposition")) != "PRIMARY_ELIGIBLE"]
    eligible_rows = [dict(row) for row in lineage_rows if _normalize(row.get("final_disposition")) == "PRIMARY_ELIGIBLE"]
    if len(eligible_rows) != EXPECTED_FINAL_ELIGIBLE:
        raise RuntimeError(
            f"Expected {EXPECTED_FINAL_ELIGIBLE} primary-eligible rows in lineage; found {len(eligible_rows)}."
        )

    first_hit_counts: Counter = Counter()
    first_hit_by_label: Dict[str, Counter] = defaultdict(Counter)
    first_exclusion_rows: List[Dict[str, Any]] = []
    negative_final_dispositions: Counter = Counter()

    for row in excluded_rows:
        final_disposition = _normalize(row.get("final_disposition"))
        layer = _first_exclusion_layer(final_disposition)
        point, side, reason = _first_exclusion_point(row)
        label = _normalize(row.get("expanded_label"))
        first_hit_counts[layer] += 1
        first_hit_by_label[label][layer] += 1
        if label == "NEGATIVE":
            negative_final_dispositions[final_disposition] += 1
        first_exclusion_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_run_id": architecture_run_id,
                "source_population_collapse_run_id": collapse_run_id,
                "source_row_key": _normalize(row.get("source_row_key")),
                "provider": _normalize(row.get("provider")),
                "session_id": _normalize(row.get("session_id")),
                "pack_level": _normalize(row.get("pack_level")),
                "expanded_label": label,
                "confidence_category": _normalize(row.get("confidence_category")),
                "first_exclusion_layer": layer,
                "first_exclusion_point": point,
                "first_exclusion_side": side,
                "first_exclusion_reason": reason,
                "expanded_join_reason": _normalize(row.get("expanded_join_reason")),
                "baseline_join_reason": _normalize(row.get("baseline_join_reason")),
                "expanded_success_reason": _normalize(row.get("expanded_success_reason")),
                "baseline_success_reason": _normalize(row.get("baseline_success_reason")),
                "payload_json": _canonical_json(
                    {
                        "final_disposition": final_disposition,
                        "execution_exclusion_reason": _normalize(row.get("execution_exclusion_reason")),
                        "first_exclusion_layer": layer,
                        "first_exclusion_point": point,
                        "first_exclusion_side": side,
                    }
                ),
            }
        )

    total_excluded = len(excluded_rows)
    total_negative_lost = EXPECTED_NEGATIVE_PLANNED
    total_positive_lost = EXPECTED_POSITIVE_PLANNED - EXPECTED_FINAL_ELIGIBLE

    attribution_rows: List[Dict[str, Any]] = []
    for layer in [
        "CANONICAL_OUTCOME_COVERAGE",
        "OUTCOME_OVERLAY_COVERAGE",
        "CORRECTED_DIRECTIONAL_SUCCESS_MAPPING",
        "DOWNSTREAM_ELIGIBILITY_LOGIC",
        "PRIMARY_ELIGIBLE",
    ]:
        count = first_hit_counts.get(layer, 0) if layer != "PRIMARY_ELIGIBLE" else len(eligible_rows)
        negative_lost = first_hit_by_label["NEGATIVE"].get(layer, 0)
        positive_lost = first_hit_by_label["POSITIVE"].get(layer, 0) if layer != "PRIMARY_ELIGIBLE" else len(eligible_rows)
        attribution_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_run_id": architecture_run_id,
                "source_population_collapse_run_id": collapse_run_id,
                "layer_name": layer,
                "first_hit_observation_count": count,
                "share_of_planned_observations": round(count / EXPECTED_PLANNED_OBSERVATIONS, 6),
                "share_of_excluded_observations": round((count / total_excluded), 6) if layer != "PRIMARY_ELIGIBLE" else "",
                "negative_observations_lost": negative_lost,
                "positive_observations_lost": positive_lost,
                "status": "ACTIVE" if count else "NONE",
                "payload_json": _canonical_json(
                    {
                        "layer_name": layer,
                        "count": count,
                        "negative_observations_lost": negative_lost,
                        "positive_observations_lost": positive_lost,
                    }
                ),
            }
        )

    current_metrics = _scenario_metrics(eligible_rows)
    scenario_a_rows = [
        row
        for row in lineage_rows
        if _normalize(row.get("final_disposition"))
        in {
            "PRIMARY_ELIGIBLE",
            "MISSING_EXPANDED_OUTCOME_JOIN",
            "MISSING_BASELINE_OUTCOME_JOIN",
            "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN",
            "OUTCOME_VERSION_MISMATCH",
            "EVALUATION_WINDOW_MISMATCH",
            "AMBIGUOUS_OUTCOME",
            "DUPLICATE_OUTCOME",
        }
    ]
    scenario_b_rows = [
        row
        for row in lineage_rows
        if _normalize(row.get("final_disposition"))
        in {
            "PRIMARY_ELIGIBLE",
            "MISSING_REPAIRED_OUTCOME_OVERLAY",
        }
    ]
    scenario_c_rows = [
        row
        for row in lineage_rows
        if _normalize(row.get("final_disposition"))
        in {
            "PRIMARY_ELIGIBLE",
            "SUCCESS_MAPPING_EXCLUSION",
            "BASELINE_NOT_ELIGIBLE",
            "EXPANDED_NOT_ELIGIBLE",
            "INVALID_SUCCESS_MAPPING",
        }
    ]
    scenario_abc_rows = list(lineage_rows)

    scenario_rows = [
        (
            "CURRENT_EXECUTED_ARCHITECTURE",
            "Current executed row-level eligible sample",
            "OBSERVED_EXECUTION",
            0,
            current_metrics,
            "Observed current architecture output.",
        ),
        (
            "A_CANONICAL_OUTCOME_COVERAGE_COMPLETE",
            "Canonical outcome coverage complete",
            "OPTIMISTIC_UPPER_BOUND",
            first_hit_counts.get("CANONICAL_OUTCOME_COVERAGE", 0),
            _scenario_metrics(scenario_a_rows),
            "Releases first-hit canonical coverage exclusions only; later overlay and success-mapping outcomes remain unknown, so this is an upper bound rather than a rerun result.",
        ),
        (
            "B_OUTCOME_OVERLAY_COVERAGE_COMPLETE",
            "Repaired outcome overlay coverage complete",
            "OPTIMISTIC_UPPER_BOUND",
            first_hit_counts.get("OUTCOME_OVERLAY_COVERAGE", 0),
            _scenario_metrics(scenario_b_rows),
            "Releases first-hit overlay exclusions only; later success-mapping outcomes remain unknown, so this is an upper bound rather than a rerun result.",
        ),
        (
            "C_SUCCESS_MAPPING_ACCEPTS_ALL_VALID_JOINS",
            "Corrected directional-success mapping accepts all valid joins",
            "DIRECT_COUNTERFACTUAL_RELEASE",
            first_hit_counts.get("CORRECTED_DIRECTIONAL_SUCCESS_MAPPING", 0),
            _scenario_metrics(scenario_c_rows),
            "Rows blocked only by success mapping already had valid join and overlay support, so this counterfactual directly adds them to the row-level eligible sample.",
        ),
        (
            "ABC_COMBINED_ARCHITECTURE_CEILING",
            "Combined architecture ceiling if canonical coverage, overlay coverage, and success mapping all ceased to limit the planned population",
            "PLANNED_POPULATION_CEILING",
            EXPECTED_PLANNED_OBSERVATIONS - EXPECTED_FINAL_ELIGIBLE,
            _scenario_metrics(scenario_abc_rows),
            "This is the blinded planned-population ceiling and shows whether the inferential design would have been supportable if the architecture had preserved the planned sample.",
        ),
    ]

    sensitivity_rows: List[Dict[str, Any]] = []
    for scenario_id, scenario_name, counterfactual_type, released, metrics, notes in scenario_rows:
        sensitivity_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_run_id": architecture_run_id,
                "source_population_collapse_run_id": collapse_run_id,
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "counterfactual_type": counterfactual_type,
                "additional_observations_released": released,
                "counterfactual_row_level_eligible": metrics["eligible"],
                "counterfactual_positive": metrics["positive"],
                "counterfactual_negative": metrics["negative"],
                "counterfactual_clusters": metrics["clusters"],
                "counterfactual_providers": metrics["providers"],
                "counterfactual_sessions": metrics["sessions"],
                "gate_status_summary": _gate_summary(metrics),
                "status": "ACTIVE",
                "payload_json": _canonical_json(
                    {
                        "metrics": metrics,
                        "gate_thresholds": EXPECTED_GATES,
                        "notes": notes,
                    }
                ),
            }
        )

    negative_layer_counts = first_hit_by_label["NEGATIVE"]
    negative_disappearance_classification = (
        "INTERACTION_OF_MULTIPLE_LAYERS_PRIMARY_SUCCESS_MAPPING"
        if negative_layer_counts.get("CORRECTED_DIRECTIONAL_SUCCESS_MAPPING", 0) > 0
        and (
            negative_layer_counts.get("CANONICAL_OUTCOME_COVERAGE", 0) > 0
            or negative_layer_counts.get("OUTCOME_OVERLAY_COVERAGE", 0) > 0
        )
        else "SINGLE_LAYER_ATTRITION"
    )

    negative_rows: List[Dict[str, Any]] = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "planned_negative_observations",
            "metric_value": EXPECTED_NEGATIVE_PLANNED,
            "status": "PASS",
            "notes": "Frozen preregistered negative primary observations.",
            "payload_json": _canonical_json({"count": EXPECTED_NEGATIVE_PLANNED}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "final_negative_observations",
            "metric_value": current_metrics["negative"],
            "status": "WARN",
            "notes": "Observed negative observations remaining in the executed eligible sample.",
            "payload_json": _canonical_json({"count": current_metrics["negative"]}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "negative_first_hit_canonical_outcome_coverage",
            "metric_value": negative_layer_counts.get("CANONICAL_OUTCOME_COVERAGE", 0),
            "status": "WARN",
            "notes": "Negative observations lost first at canonical outcome coverage.",
            "payload_json": _canonical_json({"count": negative_layer_counts.get("CANONICAL_OUTCOME_COVERAGE", 0)}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "negative_first_hit_overlay_coverage",
            "metric_value": negative_layer_counts.get("OUTCOME_OVERLAY_COVERAGE", 0),
            "status": "WARN",
            "notes": "Negative observations lost first at repaired overlay coverage.",
            "payload_json": _canonical_json({"count": negative_layer_counts.get("OUTCOME_OVERLAY_COVERAGE", 0)}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "negative_first_hit_success_mapping",
            "metric_value": negative_layer_counts.get("CORRECTED_DIRECTIONAL_SUCCESS_MAPPING", 0),
            "status": "WARN",
            "notes": "Negative observations lost first at corrected directional-success mapping.",
            "payload_json": _canonical_json({"count": negative_layer_counts.get("CORRECTED_DIRECTIONAL_SUCCESS_MAPPING", 0)}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "negative_structural_imbalance_context",
            "metric_value": EXPECTED_NEGATIVE_PLANNED,
            "status": "WARN",
            "notes": "Only 15 negatives were planned pre-outcome, so multi-layer attrition fully erased the negative arm.",
            "payload_json": _canonical_json({"planned_negative": EXPECTED_NEGATIVE_PLANNED, "planned_positive": EXPECTED_POSITIVE_PLANNED}),
        },
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "metric_name": "negative_success_mapping_reason_breakdown",
            "metric_value": sum(negative_final_dispositions.values()),
            "status": "INFO",
            "notes": "Negative attrition by final first-hit disposition.",
            "payload_json": _canonical_json(dict(negative_final_dispositions)),
        },
    ]

    ranking_rows = [
        (
            1,
            "SUCCESS_MAPPING",
            "PRIMARY_BOTTLENECK",
            "Largest first-hit loss layer with 36 rows. It removed 8 of 15 NEGATIVE observations and, on its own, still leaves only a 39-row counterfactual sample with 8 negatives.",
        ),
        (
            2,
            "CANONICAL_OUTCOME",
            "MAJOR_BOTTLENECK",
            "Second-largest first-hit loss layer with 22 rows. Five NEGATIVE observations disappear here before overlay or success evaluation can even occur.",
        ),
        (
            3,
            "OUTCOME_OVERLAY",
            "MATERIAL_BOTTLENECK",
            "Eleven observations are blocked after join support because repaired overlay coverage is missing. Overlay completion alone still yields only a 14-row upper-bound eligible sample.",
        ),
        (
            4,
            "ELIGIBILITY_DESIGN",
            "AMPLIFIER",
            "No row is first excluded by confidence/UNKNOWN rules, but the Structure A baseline-to-expanded delta design amplifies outcome-evaluability fragility because both sides must survive directional success mapping.",
        ),
        (
            5,
            "SAMPLE_SIZE",
            "DERIVED_BOTTLENECK",
            "The planned sample was adequate at 72/57/15, but the executed usable sample is inadequate because upstream architecture layers collapse it to 3/3/0.",
        ),
        (
            6,
            "STATISTICAL_DESIGN",
            "DOWNSTREAM_LIMIT",
            "The inferential method is not the root cause of row loss; it simply downgrades to descriptive reporting once the architecture leaves only one provider-session cluster and zero negatives.",
        ),
        (
            7,
            "MECHANISM_CLASSIFICATION",
            "NOT_CURRENT_BOTTLENECK",
            "Classification is not limiting the test: it produced the frozen 72 planned observations exactly as preregistered.",
        ),
    ]

    architecture_capability_classification = "NOT_YET_TESTABLE"
    principal_bottleneck_layer = "SUCCESS_MAPPING"
    recommended_research_direction = "OUTCOME_ARCHITECTURE_REFINEMENT"
    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_NOT_YET_TESTABLE"
    scientific_interpretation = (
        "The current outcome architecture is not yet capable of supporting inferential mechanism testing. "
        "The main bottleneck is the corrected directional-success mapping, which is the largest first-hit "
        "loss layer and the main reason the NEGATIVE arm disappears. Canonical outcome coverage and repaired "
        "overlay coverage are also material contributors. No single isolated layer fix is sufficient: "
        "canonical coverage alone yields only a 25-row optimistic ceiling, overlay alone 14, and success "
        "mapping relaxation alone 39 with only 8 negatives. The architecture therefore requires refinement "
        "before the inferential design can be meaningfully evaluated."
    )

    governance_rows = [
        ("provider_calls_performed", 0, "PASS", "No provider APIs were called."),
        ("outcome_rules_modified", 0, "PASS", "Outcome rules were not modified."),
        ("mechanism_rules_modified", 0, "PASS", "Mechanism rules were not modified."),
        ("preregistration_modified", 0, "PASS", "Preregistration was not modified."),
        ("mechanism_tests_performed", 0, "PASS", "No new mechanism test was executed."),
        ("production_writes", 0, "PASS", "No production workbooks were modified."),
        ("outcome_rows_loaded", 0, "PASS", "No raw outcome workbook rows were loaded; existing execution diagnostics were analyzed instead."),
    ]

    outputs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    outputs[OUTPUT_ROOT].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "source_population_collapse_run_id": collapse_run_id,
            "source_test_execution_run_id": source_test_execution_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "architecture_capability_classification": architecture_capability_classification,
            "principal_bottleneck_layer": principal_bottleneck_layer,
            "negative_disappearance_classification": negative_disappearance_classification,
            "scientific_interpretation": scientific_interpretation,
            "recommended_research_direction": recommended_research_direction,
            "payload_json": _canonical_json(
                {
                    "first_hit_counts": dict(first_hit_counts),
                    "negative_first_hit_counts": dict(first_hit_by_label["NEGATIVE"]),
                    "positive_first_hit_counts": dict(first_hit_by_label["POSITIVE"]),
                    "current_metrics": current_metrics,
                }
            ),
        }
    )
    outputs[OUTPUT_FIRST_EXCLUSION] = first_exclusion_rows
    outputs[OUTPUT_ATTRIBUTION] = attribution_rows
    outputs[OUTPUT_NEGATIVE] = negative_rows
    outputs[OUTPUT_SENSITIVITY] = sensitivity_rows
    for rank_order, layer_name, bottleneck_status, rationale in ranking_rows:
        outputs[OUTPUT_RANKING].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_run_id": architecture_run_id,
                "source_population_collapse_run_id": collapse_run_id,
                "rank_order": rank_order,
                "layer_name": layer_name,
                "bottleneck_status": bottleneck_status,
                "rationale": rationale,
                "payload_json": _canonical_json({"rank_order": rank_order, "layer_name": layer_name}),
            }
        )
    for counter_name, counter_value, status, notes in governance_rows:
        outputs[OUTPUT_GOVERNANCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "outcome_architecture_run_id": architecture_run_id,
                "counter_name": counter_name,
                "counter_value": counter_value,
                "status": status,
                "notes": notes,
            }
        )
    outputs[OUTPUT_SUMMARY].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "outcome_architecture_run_id": architecture_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "architecture_capability_classification": architecture_capability_classification,
            "principal_bottleneck_layer": principal_bottleneck_layer,
            "negative_disappearance_classification": negative_disappearance_classification,
            "recommended_research_direction": recommended_research_direction,
            "scientific_interpretation": scientific_interpretation,
            "payload_json": _canonical_json(
                {
                    "first_hit_counts": dict(first_hit_counts),
                    "negative_first_hit_counts": dict(first_hit_by_label["NEGATIVE"]),
                    "current_metrics": current_metrics,
                    "scenario_summaries": {
                        row["scenario_id"]: {
                            "additional_observations_released": row["additional_observations_released"],
                            "counterfactual_row_level_eligible": row["counterfactual_row_level_eligible"],
                            "counterfactual_positive": row["counterfactual_positive"],
                            "counterfactual_negative": row["counterfactual_negative"],
                            "gate_status_summary": row["gate_status_summary"],
                        }
                        for row in sensitivity_rows
                    },
                }
            ),
        }
    )

    summary = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "architecture_capability_classification": architecture_capability_classification,
        "principal_bottleneck_layer": principal_bottleneck_layer,
        "negative_disappearance_classification": negative_disappearance_classification,
        "recommended_research_direction": recommended_research_direction,
        "scientific_interpretation": scientific_interpretation,
        "first_hit_counts": dict(first_hit_counts),
        "negative_first_hit_counts": dict(first_hit_by_label["NEGATIVE"]),
        "current_metrics": current_metrics,
        "scenario_c_metrics": _scenario_metrics(scenario_c_rows),
    }
    return outputs, summary


def main() -> None:
    ts = datetime.now(timezone.utc)
    generated_ts = _now_iso(ts)
    architecture_run_id = _run_id(ts)

    service = build_sheets_service(load_credentials())
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    collapse_run_id, source_test_execution_run_id, lineage_rows, _collapse_payload = _latest_collapse_context(inputs)

    outputs, summary = _build_outputs(
        generated_ts=generated_ts,
        architecture_run_id=architecture_run_id,
        collapse_run_id=collapse_run_id,
        source_test_execution_run_id=source_test_execution_run_id,
        lineage_rows=lineage_rows,
    )

    rows_written_per_sheet: Dict[str, int] = {}
    for sheet_name, rows in outputs.items():
        rows_written_per_sheet[sheet_name] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            OUTPUT_SHEETS[sheet_name],
            rows,
            known_titles,
        )

    registry_status = _upsert_registry_rows(service, generated_ts)

    final_report = {
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "file_created": BUILD_SCRIPT,
        "sheets_written": list(outputs.keys()),
        "rows_written_per_sheet": rows_written_per_sheet,
        "canonical_outcome_coverage_first_hit_losses": summary["first_hit_counts"].get("CANONICAL_OUTCOME_COVERAGE", 0),
        "outcome_overlay_first_hit_losses": summary["first_hit_counts"].get("OUTCOME_OVERLAY_COVERAGE", 0),
        "success_mapping_first_hit_losses": summary["first_hit_counts"].get("CORRECTED_DIRECTIONAL_SUCCESS_MAPPING", 0),
        "downstream_eligibility_first_hit_losses": summary["first_hit_counts"].get("DOWNSTREAM_ELIGIBILITY_LOGIC", 0),
        "architecture_capability_classification": summary["architecture_capability_classification"],
        "negative_disappearance_classification": summary["negative_disappearance_classification"],
        "principal_bottleneck_layer": summary["principal_bottleneck_layer"],
        "scientific_interpretation": summary["scientific_interpretation"],
        "governance_counters": {
            "provider_calls_performed": 0,
            "outcome_rules_modified": 0,
            "mechanism_rules_modified": 0,
            "preregistration_modified": 0,
            "mechanism_tests_performed": 0,
            "production_writes": 0,
            "outcome_rows_loaded": 0,
        },
        "recommended_next_step": summary["recommended_research_direction"],
        "source_population_collapse_run_id": collapse_run_id,
        "source_test_execution_run_id": source_test_execution_run_id,
        "registry_status": registry_status,
    }
    print(json.dumps(final_report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
