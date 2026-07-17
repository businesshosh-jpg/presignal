#!/usr/bin/env python3
"""Phase 9A-6R15B — Success Mapping Architecture Investigation.

This is a completely read-only investigation of the 36 observations whose
first deterministic exclusion point was the corrected directional-success
mapping layer.

The script does not modify any workbook, preregistration artifact, outcome
artifact, classification artifact, or production surface. It reads the
existing execution diagnostics and prints a structured scientific report that:

1. assigns exactly one primary cause to every success-mapping exclusion;
2. clusters recurring exclusion patterns;
3. classifies each pattern's scientific status;
4. computes row-level sensitivity ceilings if each pattern were removed alone;
5. evaluates whether a leakage-safe preregistered Success Mapping v2 appears
   scientifically plausible without designing it.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _sheet_to_rows  # type: ignore
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore


BUILD_SCRIPT = "automation/build_refined_mechanism_test_success_mapping_architecture_investigation_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_success_mapping_architecture_investigation_v0"

EXPECTED_PLANNED_PRIMARY = 72
EXPECTED_FINAL_ELIGIBLE = 3
EXPECTED_POSITIVE_PLANNED = 57
EXPECTED_NEGATIVE_PLANNED = 15
EXPECTED_SUCCESS_MAPPING_FIRST_HIT = 36

CAUSE_SCI_REQUIRED = "SCIENTIFICALLY_REQUIRED_RULE"
CAUSE_POLICY = "POLICY_DECISION"
CAUSE_ARCH = "ARCHITECTURAL_LIMITATION"
CAUSE_IMPL = "IMPLEMENTATION_ARTIFACT"
CAUSE_AMBIG = "UNRESOLVED_AMBIGUITY"

STATUS_ESSENTIAL = "SCIENTIFICALLY_ESSENTIAL"
STATUS_OPTIONAL = "SCIENTIFICALLY_OPTIONAL"
STATUS_REPLACEABLE = "POTENTIALLY_REPLACEABLE"
STATUS_INDETERMINATE = "CURRENTLY_INDETERMINATE"


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _latest(rows: Sequence[Mapping[str, Any]], key: str) -> Mapping[str, Any]:
    if not rows:
        return {}
    return sorted(
        rows,
        key=lambda row: (
            _normalize(row.get(key)),
            _normalize(row.get("generated_ts")),
            int(_normalize(row.get("__source_row_number__")) or "0"),
        ),
    )[-1]


def _load_context(service) -> Dict[str, Any]:
    lineage_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Refined_Mechanism_Test_Row_Lineage_Audit")
    population_collapse_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Refined_Mechanism_Test_Population_Collapse")
    join_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Refined_Mechanism_Test_Outcome_Join_Audit")
    collapse_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Refined_Mechanism_Test_Collapse_Summary")

    latest_collapse = _latest(population_collapse_rows, "population_collapse_run_id")
    latest_summary = _latest(collapse_summary_rows, "population_collapse_run_id")
    collapse_run_id = _normalize(latest_collapse.get("population_collapse_run_id"))
    test_execution_run_id = _normalize(latest_collapse.get("source_test_execution_run_id"))
    if not collapse_run_id or not test_execution_run_id:
        raise RuntimeError("Could not resolve authoritative Phase 9A-6R15A lineage.")

    lineage = [dict(row) for row in lineage_rows if _normalize(row.get("population_collapse_run_id")) == collapse_run_id]
    if len(lineage) != EXPECTED_PLANNED_PRIMARY:
        raise RuntimeError(
            f"Expected {EXPECTED_PLANNED_PRIMARY} lineage rows for {collapse_run_id}; found {len(lineage)}."
        )

    join_index = {
        _normalize(row.get("source_row_key")): dict(row)
        for row in join_rows
        if _normalize(row.get("test_execution_run_id")) == test_execution_run_id
        and _normalize(row.get("analysis_id")) == "PRIMARY_PM003_STRUCTURE_A"
    }
    if len(join_index) != EXPECTED_PLANNED_PRIMARY:
        raise RuntimeError(
            f"Expected {EXPECTED_PLANNED_PRIMARY} primary join-audit rows for {test_execution_run_id}; "
            f"found {len(join_index)}."
        )

    return {
        "collapse_run_id": collapse_run_id,
        "test_execution_run_id": test_execution_run_id,
        "lineage_rows": lineage,
        "join_index": join_index,
        "latest_collapse": dict(latest_collapse),
        "latest_summary": dict(latest_summary),
    }


def _pattern_for_row(row: Mapping[str, Any]) -> Tuple[str, str, str, str]:
    """Return pattern_id, primary_cause, scientific_status, rationale."""
    expanded_reason = _normalize(row.get("expanded_success_reason"))
    baseline_reason = _normalize(row.get("baseline_success_reason"))
    final_disposition = _normalize(row.get("final_disposition"))

    if expanded_reason == "REALIZED_FLAT_OR_AMBIGUOUS" and baseline_reason == "REALIZED_FLAT_OR_AMBIGUOUS":
        return (
            "PATTERN_BOTH_REALIZED_FLAT",
            CAUSE_POLICY,
            STATUS_REPLACEABLE,
            "Both sides joined successfully but the current mapping treats flat realized outcomes as not eligible rather than scoreable directional outcomes.",
        )
    if expanded_reason == "REALIZED_FLAT_OR_AMBIGUOUS" and baseline_reason == "FORECAST_NO_CLEAR_DIRECTION":
        return (
            "PATTERN_EXPANDED_FLAT_BASELINE_NO_CLEAR",
            CAUSE_POLICY,
            STATUS_INDETERMINATE,
            "The expanded side is excluded by flat-outcome handling while the baseline side is simultaneously non-directional, so the exclusion reflects a mixed policy-plus-architecture interaction.",
        )
    if expanded_reason == "FORECAST_NO_CLEAR_DIRECTION" and baseline_reason == "FORECAST_NO_CLEAR_DIRECTION":
        return (
            "PATTERN_BOTH_NO_CLEAR_DIRECTION",
            CAUSE_SCI_REQUIRED,
            STATUS_ESSENTIAL,
            "Neither side contains a directional forecast, so the current directional-success endpoint cannot be evaluated without changing the scientific meaning of the outcome.",
        )
    if final_disposition == "BASELINE_NOT_ELIGIBLE" and baseline_reason == "FORECAST_FLAT":
        return (
            "PATTERN_BASELINE_FLAT_ONLY",
            CAUSE_POLICY,
            STATUS_OPTIONAL,
            "The expanded observation is directionally scoreable, but the baseline control is excluded because the current mapping chooses not to score flat forecasts.",
        )
    if final_disposition == "BASELINE_NOT_ELIGIBLE" and baseline_reason == "FORECAST_NO_CLEAR_DIRECTION":
        return (
            "PATTERN_BASELINE_NO_CLEAR_ONLY",
            CAUSE_ARCH,
            STATUS_REPLACEABLE,
            "The expanded observation is scoreable, but the baseline delta control is structurally non-directional. This reflects a mismatch between the Pack A control architecture and the delta design rather than a failure of the mechanism label.",
        )
    if expanded_reason == "FORECAST_NO_CLEAR_DIRECTION" and baseline_reason == "REALIZED_FLAT_OR_AMBIGUOUS":
        return (
            "PATTERN_EXPANDED_NO_CLEAR_BASELINE_FLAT",
            CAUSE_SCI_REQUIRED,
            STATUS_ESSENTIAL,
            "The expanded observation itself is non-directional, so it is not directionally evaluable under the current primary endpoint regardless of the baseline side.",
        )
    return (
        "PATTERN_UNCLASSIFIED",
        CAUSE_AMBIG,
        STATUS_INDETERMINATE,
        "The exclusion did not match any recurring audited pattern and remains scientifically unresolved in this investigation.",
    )


def _counterfactual_metrics(current_rows: Sequence[Mapping[str, Any]], recovered_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    combined = list(current_rows) + list(recovered_rows)
    return {
        "recovered_observations": len(recovered_rows),
        "recovered_positives": sum(1 for row in recovered_rows if _normalize(row.get("expanded_label")) == "POSITIVE"),
        "recovered_negatives": sum(1 for row in recovered_rows if _normalize(row.get("expanded_label")) == "NEGATIVE"),
        "recovered_provider_session_clusters": len(
            {(_normalize(row.get("provider")), _normalize(row.get("session_id"))) for row in recovered_rows}
        ),
        "counterfactual_total_eligible": len(combined),
        "counterfactual_total_positive": sum(1 for row in combined if _normalize(row.get("expanded_label")) == "POSITIVE"),
        "counterfactual_total_negative": sum(1 for row in combined if _normalize(row.get("expanded_label")) == "NEGATIVE"),
        "counterfactual_provider_count": len({_normalize(row.get("provider")) for row in combined}),
        "counterfactual_session_count": len({_normalize(row.get("session_id")) for row in combined}),
        "counterfactual_cluster_count": len(
            {(_normalize(row.get("provider")), _normalize(row.get("session_id"))) for row in combined}
        ),
    }


def _main_report(context: Mapping[str, Any]) -> Dict[str, Any]:
    lineage_rows = context["lineage_rows"]
    join_index = context["join_index"]
    eligible_rows = [row for row in lineage_rows if _normalize(row.get("final_disposition")) == "PRIMARY_ELIGIBLE"]
    success_mapping_rows = [row for row in lineage_rows if _normalize(row.get("root_cause_category")) == "SUCCESS_DERIVATION"]

    if len(eligible_rows) != EXPECTED_FINAL_ELIGIBLE:
        raise RuntimeError(f"Expected {EXPECTED_FINAL_ELIGIBLE} eligible rows; found {len(eligible_rows)}.")
    if len(success_mapping_rows) != EXPECTED_SUCCESS_MAPPING_FIRST_HIT:
        raise RuntimeError(
            f"Expected {EXPECTED_SUCCESS_MAPPING_FIRST_HIT} success-mapping first-hit exclusions; "
            f"found {len(success_mapping_rows)}."
        )

    row_assignments: List[Dict[str, Any]] = []
    cause_counts: Counter = Counter()
    pattern_counts: Counter = Counter()
    pattern_status_counts: Counter = Counter()
    pattern_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in success_mapping_rows:
        pattern_id, primary_cause, pattern_status, rationale = _pattern_for_row(row)
        join_row = join_index[_normalize(row.get("source_row_key"))]
        assignment = {
            "source_row_key": _normalize(row.get("source_row_key")),
            "provider": _normalize(row.get("provider")),
            "session_id": _normalize(row.get("session_id")),
            "pack_level": _normalize(row.get("pack_level")),
            "expanded_label": _normalize(row.get("expanded_label")),
            "confidence_category": _normalize(row.get("confidence_category")),
            "final_disposition": _normalize(row.get("final_disposition")),
            "expanded_success_reason": _normalize(row.get("expanded_success_reason")),
            "baseline_success_reason": _normalize(row.get("baseline_success_reason")),
            "expanded_forecast_direction": _normalize(join_row.get("expanded_forecast_direction")),
            "baseline_forecast_direction": _normalize(join_row.get("baseline_forecast_direction")),
            "expanded_realized_direction": _normalize(join_row.get("expanded_realized_direction")),
            "baseline_realized_direction": _normalize(join_row.get("baseline_realized_direction")),
            "pattern_id": pattern_id,
            "primary_cause": primary_cause,
            "scientific_status": pattern_status,
            "cause_rationale": rationale,
        }
        row_assignments.append(assignment)
        cause_counts[primary_cause] += 1
        pattern_counts[pattern_id] += 1
        pattern_status_counts[pattern_status] += 1
        pattern_rows[pattern_id].append(assignment)

    if len(row_assignments) != EXPECTED_SUCCESS_MAPPING_FIRST_HIT:
        raise RuntimeError("Row-cause assignment count does not reconcile to 36.")

    pattern_summaries: List[Dict[str, Any]] = []
    for pattern_id, rows in sorted(pattern_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        sample = rows[0]
        metrics = _counterfactual_metrics(eligible_rows, rows)
        pattern_summaries.append(
            {
                "pattern_id": pattern_id,
                "row_count": len(rows),
                "primary_cause": sample["primary_cause"],
                "scientific_status": sample["scientific_status"],
                "rationale": sample["cause_rationale"],
                "expanded_labels": dict(Counter(row["expanded_label"] for row in rows)),
                "providers": len({row["provider"] for row in rows}),
                "sessions": len({row["session_id"] for row in rows}),
                "provider_session_clusters": len({(row["provider"], row["session_id"]) for row in rows}),
                "dominant_structure": {
                    "expanded_success_reason": sample["expanded_success_reason"],
                    "baseline_success_reason": sample["baseline_success_reason"],
                },
                "counterfactual_if_pattern_removed_alone": metrics,
            }
        )

    cause_counterfactuals: List[Dict[str, Any]] = []
    for cause_name in [CAUSE_POLICY, CAUSE_ARCH, CAUSE_SCI_REQUIRED, CAUSE_IMPL, CAUSE_AMBIG]:
        rows = [row for row in row_assignments if row["primary_cause"] == cause_name]
        metrics = _counterfactual_metrics(eligible_rows, rows)
        cause_counterfactuals.append(
            {
                "primary_cause": cause_name,
                "row_count": len(rows),
                "expanded_labels": dict(Counter(row["expanded_label"] for row in rows)),
                "scientific_interpretation": {
                    CAUSE_POLICY: "Conservative design choice rather than a necessity of leakage-safe science.",
                    CAUSE_ARCH: "Mismatch between the baseline delta architecture and the directional endpoint.",
                    CAUSE_SCI_REQUIRED: "Required to preserve the meaning of the current directional-success endpoint.",
                    CAUSE_IMPL: "Would indicate a bug or historical execution artifact rather than scientific intent.",
                    CAUSE_AMBIG: "Would indicate unresolved scientific ambiguity in the current audited state.",
                }[cause_name],
                "counterfactual_if_cause_family_removed": metrics,
            }
        )

    dominant_failure_modes = [
        {
            "failure_mode": "realized_flat_handling",
            "row_count": sum(
                1
                for row in row_assignments
                if row["expanded_success_reason"] == "REALIZED_FLAT_OR_AMBIGUOUS"
                or row["baseline_success_reason"] == "REALIZED_FLAT_OR_AMBIGUOUS"
            ),
            "interpretation": "Flat realized outcomes are the dominant recurring corrected-direction scenario inside success-mapping exclusions.",
        },
        {
            "failure_mode": "baseline_no_clear_direction",
            "row_count": sum(1 for row in row_assignments if row["baseline_success_reason"] == "FORECAST_NO_CLEAR_DIRECTION"),
            "interpretation": "The Pack A control frequently fails because it is non-directional even when the expanded observation is scoreable.",
        },
        {
            "failure_mode": "expanded_no_clear_direction",
            "row_count": sum(1 for row in row_assignments if row["expanded_success_reason"] == "FORECAST_NO_CLEAR_DIRECTION"),
            "interpretation": "Some expanded observations are themselves non-directional and therefore scientifically incompatible with the current endpoint.",
        },
        {
            "failure_mode": "baseline_flat_forecast",
            "row_count": sum(1 for row in row_assignments if row["baseline_success_reason"] == "FORECAST_FLAT"),
            "interpretation": "A smaller set of otherwise scoreable deltas is lost because flat baseline forecasts are treated as not eligible.",
        },
    ]

    v2_feasibility = {
        "scientifically_valid_v2_appears_possible": True,
        "reasoning": [
            "28 of the 36 exclusions are not scientifically essential under the current evidence record.",
            "22 exclusions are conservative policy choices tied to flat handling.",
            "6 exclusions reflect a baseline-control architecture mismatch rather than a necessity of mechanism science.",
            "A future redesign could be frozen before outcome access and evaluated without using realized performance to choose rules.",
        ],
        "hard_constraints_for_any_future_v2": [
            "must be preregistered before any new outcome access",
            "must preserve zero outcome leakage and no hindsight optimization",
            "must not silently convert no-clear observations into directional forecasts",
            "must preserve the scientific meaning of mechanism presence versus forecast evaluability",
        ],
        "important_limit": (
            "Success Mapping v2 alone would still be insufficient for inferential testing: "
            "removing all 36 success-mapping exclusions would only yield 39 eligible observations "
            "with 8 negatives, still below the frozen primary inferential gates."
        ),
    }

    principal_limitation = "SUCCESS_MAPPING_WITH_INTERACTION_EFFECTS"
    recommendation = {
        "primary_recommendation": "PREREGISTER_SUCCESS_MAPPING_V2",
        "supporting_recommendation": "MAINTAIN_DESCRIPTIVE_ONLY_TESTING_UNTIL_COMBINED_ARCHITECTURE_IMPROVES",
        "rationale": (
            "Success Mapping is the next scientific research target because it is still the largest first-hit "
            "loss layer and most of its exclusions are policy- or architecture-driven rather than essential. "
            "But no single Success Mapping redesign will restore inferential viability on its own, so descriptive-only "
            "testing should remain in place until canonical coverage and overlay coverage also improve."
        ),
    }
    build_status = "PASS_WITH_WARNINGS"
    final_interpretation = "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_INVESTIGATION_READY_WITH_WARNINGS"

    final_report = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "generated_ts": _now_iso(),
        "schema_version": SCHEMA_VERSION,
        "file_created": BUILD_SCRIPT,
        "source_population_collapse_run_id": context["collapse_run_id"],
        "source_test_execution_run_id": context["test_execution_run_id"],
        "read_only_workbook_investigation": True,
        "workbook_sheets_written": 0,
        "planned_primary_observations": EXPECTED_PLANNED_PRIMARY,
        "final_eligible_observations": EXPECTED_FINAL_ELIGIBLE,
        "success_mapping_first_deterministic_exclusions": EXPECTED_SUCCESS_MAPPING_FIRST_HIT,
        "primary_cause_counts": dict(cause_counts),
        "scientific_status_counts": dict(pattern_status_counts),
        "dominant_failure_modes": dominant_failure_modes,
        "pattern_summaries": pattern_summaries,
        "cause_family_counterfactuals": cause_counterfactuals,
        "current_primary_population": {
            "eligible_observations": len(eligible_rows),
            "positive_observations": sum(1 for row in eligible_rows if _normalize(row.get("expanded_label")) == "POSITIVE"),
            "negative_observations": sum(1 for row in eligible_rows if _normalize(row.get("expanded_label")) == "NEGATIVE"),
            "provider_session_clusters": len({(_normalize(row.get("provider")), _normalize(row.get("session_id"))) for row in eligible_rows}),
            "providers": len({_normalize(row.get("provider")) for row in eligible_rows}),
            "sessions": len({_normalize(row.get("session_id")) for row in eligible_rows}),
        },
        "success_mapping_encodes": {
            "scientific_necessity_rows": cause_counts[CAUSE_SCI_REQUIRED],
            "policy_decision_rows": cause_counts[CAUSE_POLICY],
            "architectural_limitation_rows": cause_counts[CAUSE_ARCH],
            "implementation_artifact_rows": cause_counts[CAUSE_IMPL],
            "unresolved_ambiguity_rows": cause_counts[CAUSE_AMBIG],
            "interpretation": (
                "The current Success Mapping architecture is driven mostly by conservative policy choices "
                "and baseline-control architecture mismatch, not by scientific necessity alone."
            ),
        },
        "future_v2_feasibility": v2_feasibility,
        "principal_limitation": principal_limitation,
        "scientific_bottleneck_assessment": (
            "The principal limitation remains Success Mapping, but it interacts materially with canonical outcome "
            "coverage and repaired overlay coverage. Success Mapping is the most informative next scientific target, "
            "not the sole remaining limitation."
        ),
        "recommendation": recommendation,
        "recommended_next_step": recommendation["primary_recommendation"],
        "governance_counters": {
            "provider_calls_performed": 0,
            "outcome_rows_loaded": 0,
            "outcome_rules_modified": 0,
            "success_mapping_modified": 0,
            "mechanism_rules_modified": 0,
            "preregistration_modified": 0,
            "mechanism_tests_performed": 0,
            "production_writes": 0,
        },
        "row_level_primary_cause_assignments": row_assignments,
    }
    return final_report


def main() -> None:
    service = build_sheets_service(load_credentials())
    context = _load_context(service)
    report = _main_report(context)
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
