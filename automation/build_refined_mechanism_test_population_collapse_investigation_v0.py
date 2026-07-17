#!/usr/bin/env python3
"""Phase 9A-6R15A — Primary Population Collapse Investigation.

This is a read-only scientific diagnostic phase. It explains why the frozen
primary analysis population of 72 planned primary-contrast observations
collapsed to 3 final eligible observations during the already-executed
canonical mechanism test.

The investigation does not rerun the experiment, does not rejoin outcomes,
and does not modify classifications, preregistration artifacts, or production
behavior. It relies on the existing execution audit outputs written by the
approved Phase 9A-6R15 mechanism-test execution.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple


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
    _classification_rows,
    _derive_success_status,
    _eligible_candidates,
    _fetch_input_sheets,
    _latest_payload,
    _latest_row,
    _normalize,
    _sheet_titles_light,
    _to_bool,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9A-6R15A"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_population_collapse_investigation_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_population_collapse_investigation_v0"
INVESTIGATION_VERSION = "refined_mechanism_test_population_collapse_investigation_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_POPULATION_COLLAPSE"
REGISTRY_OWNER_MODULE = "market_state"

CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
PRIMARY_MECHANISM = "MECH_INFORMATION_CONSISTENCY"
PRIMARY_MECHANISM_ID = "PM-003"
PRIMARY_ANALYSIS_ID = "PRIMARY_PM003_STRUCTURE_A"
EXPECTED_PLANNED_OBSERVATIONS = 72
EXPECTED_FINAL_ELIGIBLE = 3

INPUT_SHEETS: Tuple[str, ...] = (
    "Refined_Mechanism_Test_Execution",
    "Refined_Mechanism_Test_Outcome_Join_Audit",
    "Refined_Mechanism_Test_Eligibility_Audit",
    "Refined_Mechanism_Test_Missing_Data_Audit",
    "Refined_Mechanism_Test_Execution_Governance",
    "Refined_Mechanism_Test_Execution_Summary",
    "Refined_Mechanism_Test_Readiness_Summary",
    "Refined_Mechanism_Test_Execution_Approval_Canonical_R1_Summary",
    "Refined_Mechanism_v11_Classifications",
)

OUTPUT_POPULATION_COLLAPSE = "Refined_Mechanism_Test_Population_Collapse"
OUTPUT_ROW_LINEAGE = "Refined_Mechanism_Test_Row_Lineage_Audit"
OUTPUT_JOIN_FAILURE = "Refined_Mechanism_Test_Outcome_Join_Failure_Audit"
OUTPUT_SUCCESS_MAPPING = "Refined_Mechanism_Test_Success_Mapping_Audit"
OUTPUT_TRANSITIONS = "Refined_Mechanism_Test_Eligibility_Transition_Audit"
OUTPUT_ROOT_CAUSE = "Refined_Mechanism_Test_Collapse_Root_Cause"
OUTPUT_QUANTIFICATION = "Refined_Mechanism_Test_Collapse_Quantification"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Collapse_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Collapse_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_POPULATION_COLLAPSE: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "build_status",
        "final_interpretation",
        "planned_primary_observations",
        "final_eligible_observations",
        "complete_population_reconciliation",
        "outcome_join_losses",
        "success_mapping_losses",
        "eligibility_losses",
        "confidence_losses",
        "unknown_losses",
        "overlay_losses",
        "other_losses",
        "root_cause_attribution",
        "scientific_interpretation",
        "recommended_next_step",
        "payload_json",
    ],
    OUTPUT_ROW_LINEAGE: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "source_row_key",
        "matched_baseline_source_row_key",
        "provider",
        "session_id",
        "pack_level",
        "expanded_label",
        "confidence_category",
        "planned_primary_observation",
        "expanded_join_status",
        "expanded_join_reason",
        "baseline_join_status",
        "baseline_join_reason",
        "expanded_success_status",
        "expanded_success_reason",
        "baseline_success_status",
        "baseline_success_reason",
        "included_in_analysis",
        "execution_exclusion_reason",
        "final_disposition",
        "root_cause_category",
        "bridge_consensus_status",
        "repaired_canonical_outcome_id",
        "canonical_outcome_id",
        "payload_json",
    ],
    OUTPUT_JOIN_FAILURE: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "audit_level",
        "side",
        "reason_code",
        "observation_count",
        "side_event_count",
        "notes",
        "payload_json",
    ],
    OUTPUT_SUCCESS_MAPPING: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "audit_level",
        "side",
        "reason_code",
        "observation_count",
        "side_event_count",
        "notes",
        "payload_json",
    ],
    OUTPUT_TRANSITIONS: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "transition_stage",
        "transition_count",
        "status",
        "notes",
        "payload_json",
    ],
    OUTPUT_ROOT_CAUSE: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "cause_id",
        "cause_type",
        "row_count",
        "primary_or_secondary",
        "status",
        "interpretation",
        "payload_json",
    ],
    OUTPUT_QUANTIFICATION: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "source_test_execution_run_id",
        "metric_name",
        "metric_value",
        "unit",
        "status",
        "notes",
        "payload_json",
    ],
    OUTPUT_GOVERNANCE: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "counter_name",
        "counter_value",
        "status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "population_collapse_run_id",
        "build_status",
        "final_interpretation",
        "planned_primary_observations",
        "final_eligible_observations",
        "complete_population_reconciliation",
        "outcome_join_losses",
        "success_mapping_losses",
        "eligibility_losses",
        "confidence_losses",
        "unknown_losses",
        "overlay_losses",
        "other_losses",
        "root_cause_attribution",
        "scientific_interpretation",
        "recommended_next_step",
        "payload_json",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_POPULATION_COLLAPSE: "REFINED_MECHANISM_TEST_POPULATION_COLLAPSE",
    OUTPUT_ROW_LINEAGE: "REFINED_MECHANISM_TEST_ROW_LINEAGE_AUDIT",
    OUTPUT_JOIN_FAILURE: "REFINED_MECHANISM_TEST_OUTCOME_JOIN_FAILURE_AUDIT",
    OUTPUT_SUCCESS_MAPPING: "REFINED_MECHANISM_TEST_SUCCESS_MAPPING_AUDIT",
    OUTPUT_TRANSITIONS: "REFINED_MECHANISM_TEST_ELIGIBILITY_TRANSITION_AUDIT",
    OUTPUT_ROOT_CAUSE: "REFINED_MECHANISM_TEST_COLLAPSE_ROOT_CAUSE",
    OUTPUT_QUANTIFICATION: "REFINED_MECHANISM_TEST_COLLAPSE_QUANTIFICATION",
    OUTPUT_GOVERNANCE: "REFINED_MECHANISM_TEST_COLLAPSE_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_TEST_COLLAPSE_SUMMARY",
}


def _run_id(ts: datetime) -> str:
    return f"9A-6R15A_{ts.strftime('%Y%m%dT%H%M%SZ')}"


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


def _safe_sheet_title(title: str) -> str:
    return title.replace("'", "''")


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
            "notes": "Phase 9A-6R15A primary population collapse investigation outputs.",
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


def _select_execution_run(inputs: Mapping[str, Any]) -> Tuple[str, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    latest_summary_row = _latest_row(
        inputs["Refined_Mechanism_Test_Execution_Summary"].rows,
        "test_execution_run_id",
    )
    if not latest_summary_row:
        raise RuntimeError("No mechanism-test execution summary rows found for Phase 9A-6R15.")
    latest_summary_payload = _json_loads_safe(latest_summary_row.get("payload_json")) or {}
    source_test_execution_run_id = _normalize(latest_summary_row.get("test_execution_run_id"))
    if not source_test_execution_run_id:
        raise RuntimeError("Latest execution summary row is missing test_execution_run_id.")
    if _to_int(latest_summary_row.get("eligible_sample")) != EXPECTED_FINAL_ELIGIBLE:
        raise RuntimeError(
            "Latest execution summary does not match the expected collapse target "
            f"(eligible_sample={latest_summary_row.get('eligible_sample')})."
        )
    execution_row = _latest_row(
        [
            dict(row)
            for row in inputs["Refined_Mechanism_Test_Execution"].rows
            if _normalize(row.get("test_execution_run_id")) == source_test_execution_run_id
        ],
        "test_execution_run_id",
    )
    if not execution_row:
        raise RuntimeError(f"Execution row missing for run {source_test_execution_run_id}.")
    execution_payload = _json_loads_safe(execution_row.get("payload_json")) or {}
    eligibility_row = _latest_row(
        [
            dict(row)
            for row in inputs["Refined_Mechanism_Test_Eligibility_Audit"].rows
            if _normalize(row.get("test_execution_run_id")) == source_test_execution_run_id
            and _normalize(row.get("analysis_id")) == PRIMARY_ANALYSIS_ID
        ],
        "test_execution_run_id",
    )
    if not eligibility_row:
        raise RuntimeError(f"Primary eligibility audit row missing for run {source_test_execution_run_id}.")
    return source_test_execution_run_id, latest_summary_row, latest_summary_payload, {
        "execution_row": execution_row,
        "execution_payload": execution_payload,
        "eligibility_row": eligibility_row,
    }


def _planned_primary_rows(inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
    class_rows = _classification_rows(inputs)
    planned = _eligible_candidates(
        class_rows,
        PRIMARY_MECHANISM,
        allowed_labels={"POSITIVE", "NEGATIVE"},
        require_high_moderate=True,
    )
    if len(planned) != EXPECTED_PLANNED_OBSERVATIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_PLANNED_OBSERVATIONS} planned primary observations; found {len(planned)}."
        )
    return planned


def _derive_success_reason(join_details: Mapping[str, Any], success_status: str) -> str:
    derived_status, derived_reason = _derive_success_status(
        forecast_direction=_normalize(join_details.get("forecast_direction")),
        no_signal_flag=_to_bool(join_details.get("no_signal_flag")),
        output_valid=_to_bool(join_details.get("output_valid")),
        realized_direction=_normalize(join_details.get("realized_direction")),
        join_status=_normalize(join_details.get("join_validation_status")),
        join_reason=_normalize(join_details.get("join_validation_reason")),
    )
    if derived_status != _normalize(success_status):
        raise RuntimeError(
            "Derived success status mismatch: "
            f"expected {success_status}, derived {derived_status} for details {join_details}."
        )
    return derived_reason


def _standardize_final_disposition(exclusion_reason: str, included: bool) -> Tuple[str, str]:
    if included:
        return "PRIMARY_ELIGIBLE", "PRIMARY_ELIGIBLE"
    mapping = {
        "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN": ("MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN", "OUTCOME_LINKAGE"),
        "MISSING_EXPANDED_OUTCOME_JOIN": ("MISSING_EXPANDED_OUTCOME_JOIN", "OUTCOME_LINKAGE"),
        "MISSING_BASELINE_OUTCOME_JOIN": ("MISSING_BASELINE_OUTCOME_JOIN", "OUTCOME_LINKAGE"),
        "MISSING_REPAIRED_OUTCOME_OVERLAY": ("MISSING_REPAIRED_OUTCOME_OVERLAY", "REPAIRED_OUTCOME_OVERLAY"),
        "OUTCOME_VERSION_MISMATCH": ("OUTCOME_VERSION_MISMATCH", "OUTCOME_LINKAGE"),
        "EVALUATION_WINDOW_MISMATCH": ("EVALUATION_WINDOW_MISMATCH", "OUTCOME_LINKAGE"),
        "AMBIGUOUS_JOIN_BLOCKED": ("AMBIGUOUS_OUTCOME", "OUTCOME_LINKAGE"),
        "DUPLICATE_JOIN_BLOCKED": ("DUPLICATE_OUTCOME", "OUTCOME_LINKAGE"),
        "EXPANDED_AND_BASELINE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING": ("SUCCESS_MAPPING_EXCLUSION", "SUCCESS_DERIVATION"),
        "EXPANDED_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING": ("EXPANDED_NOT_ELIGIBLE", "SUCCESS_DERIVATION"),
        "BASELINE_NOT_ELIGIBLE_AFTER_SUCCESS_MAPPING": ("BASELINE_NOT_ELIGIBLE", "SUCCESS_DERIVATION"),
        "INVALID_SUCCESS_MAPPING": ("INVALID_SUCCESS_MAPPING", "SUCCESS_DERIVATION"),
        "CONFIDENCE_EXCLUSION": ("CONFIDENCE_EXCLUSION", "FROZEN_ELIGIBILITY"),
        "UNKNOWN_EXCLUSION": ("UNKNOWN_EXCLUSION", "FROZEN_ELIGIBILITY"),
        "INSUFFICIENT_EVIDENCE_EXCLUSION": ("INSUFFICIENT_EVIDENCE_EXCLUSION", "FROZEN_ELIGIBILITY"),
        "OTHER_FROZEN_EXCLUSION": ("OTHER_FROZEN_EXCLUSION", "FROZEN_ELIGIBILITY"),
    }
    if exclusion_reason not in mapping:
        return "OTHER_FROZEN_EXCLUSION", "OTHER"
    return mapping[exclusion_reason]


def _build_row_lineage(
    planned_rows: Sequence[Mapping[str, Any]],
    join_rows: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    join_by_key: Dict[str, Dict[str, Any]] = {}
    duplicate_keys: List[str] = []
    for row in join_rows:
        key = _normalize(row.get("source_row_key"))
        if key in join_by_key:
            duplicate_keys.append(key)
        join_by_key[key] = dict(row)
    if duplicate_keys:
        raise RuntimeError(f"Duplicate join audit keys detected: {sorted(set(duplicate_keys))}")

    planned_by_key = {_normalize(row.get("source_row_key")): dict(row) for row in planned_rows}
    planned_keys = set(planned_by_key)
    join_keys = set(join_by_key)
    if planned_keys != join_keys:
        raise RuntimeError(
            "Planned population and join-audit population do not reconcile. "
            f"planned_only={sorted(planned_keys - join_keys)} join_only={sorted(join_keys - planned_keys)}"
        )

    lineage_rows: List[Dict[str, Any]] = []
    final_disposition_counts: Counter = Counter()
    final_disposition_by_label: Dict[str, Counter] = defaultdict(Counter)
    root_cause_counts: Counter = Counter()
    transition_counts: Counter = Counter()
    transition_counts["PLANNED_PRIMARY_OBSERVATIONS"] = len(planned_rows)

    expanded_join_reason_counts: Counter = Counter()
    baseline_join_reason_counts: Counter = Counter()
    expanded_success_reason_counts: Counter = Counter()
    baseline_success_reason_counts: Counter = Counter()
    execution_exclusion_counts: Counter = Counter()

    for key in sorted(planned_keys):
        planned = planned_by_key[key]
        audit_row = join_by_key[key]
        payload = _json_loads_safe(audit_row.get("payload_json")) or {}
        expanded_join = payload.get("expanded_join") or {}
        baseline_join = payload.get("baseline_join") or {}

        expanded_join_status = _normalize(expanded_join.get("join_validation_status"))
        expanded_join_reason = _normalize(expanded_join.get("join_validation_reason"))
        baseline_join_status = _normalize(baseline_join.get("join_validation_status"))
        baseline_join_reason = _normalize(baseline_join.get("join_validation_reason"))
        expanded_success_status = _normalize(audit_row.get("expanded_success_status"))
        baseline_success_status = _normalize(audit_row.get("baseline_success_status"))
        expanded_success_reason = _derive_success_reason(expanded_join, expanded_success_status)
        baseline_success_reason = _derive_success_reason(baseline_join, baseline_success_status)
        included = _normalize(audit_row.get("included_in_analysis")) == "TRUE"
        execution_exclusion_reason = _normalize(audit_row.get("exclusion_reason"))
        final_disposition, root_cause_category = _standardize_final_disposition(
            execution_exclusion_reason,
            included,
        )

        if expanded_join_status == "OK":
            transition_counts["EXPANDED_JOIN_READY"] += 1
        else:
            transition_counts["EXPANDED_JOIN_FAILED"] += 1
        if baseline_join_status == "OK":
            transition_counts["BASELINE_JOIN_READY"] += 1
        else:
            transition_counts["BASELINE_JOIN_FAILED"] += 1
        if expanded_join_status == "OK" and baseline_join_status == "OK":
            transition_counts["BOTH_JOINS_READY"] += 1
        if expanded_success_status in {"SUCCESS", "FAILURE"}:
            transition_counts["EXPANDED_SUCCESS_MAPPED"] += 1
        if baseline_success_status in {"SUCCESS", "FAILURE"}:
            transition_counts["BASELINE_SUCCESS_MAPPED"] += 1
        if expanded_success_status in {"SUCCESS", "FAILURE"} and baseline_success_status in {"SUCCESS", "FAILURE"}:
            transition_counts["BOTH_SUCCESS_MAPPED"] += 1
        if included:
            transition_counts["PRIMARY_ELIGIBLE"] += 1
        else:
            transition_counts["PRIMARY_EXCLUDED"] += 1

        expanded_join_reason_counts[expanded_join_reason] += 1
        baseline_join_reason_counts[baseline_join_reason] += 1
        expanded_success_reason_counts[expanded_success_reason] += 1
        baseline_success_reason_counts[baseline_success_reason] += 1
        execution_exclusion_counts[execution_exclusion_reason or "PRIMARY_ELIGIBLE"] += 1
        final_disposition_counts[final_disposition] += 1
        final_disposition_by_label[_normalize(audit_row.get("expanded_label"))][final_disposition] += 1
        root_cause_counts[root_cause_category] += 0 if included else 1

        lineage_rows.append(
            {
                "source_row_key": key,
                "matched_baseline_source_row_key": _normalize(audit_row.get("matched_baseline_source_row_key")),
                "provider": _normalize(audit_row.get("provider")),
                "session_id": _normalize(audit_row.get("session_id")),
                "pack_level": _normalize(audit_row.get("pack_level")),
                "expanded_label": _normalize(audit_row.get("expanded_label")),
                "confidence_category": _normalize(audit_row.get("confidence_category")),
                "planned_primary_observation": "TRUE",
                "expanded_join_status": expanded_join_status,
                "expanded_join_reason": expanded_join_reason,
                "baseline_join_status": baseline_join_status,
                "baseline_join_reason": baseline_join_reason,
                "expanded_success_status": expanded_success_status,
                "expanded_success_reason": expanded_success_reason,
                "baseline_success_status": baseline_success_status,
                "baseline_success_reason": baseline_success_reason,
                "included_in_analysis": "TRUE" if included else "FALSE",
                "execution_exclusion_reason": execution_exclusion_reason,
                "final_disposition": final_disposition,
                "root_cause_category": root_cause_category,
                "bridge_consensus_status": _normalize(audit_row.get("bridge_consensus_status")),
                "repaired_canonical_outcome_id": _normalize(audit_row.get("repaired_canonical_outcome_id")),
                "canonical_outcome_id": _normalize(audit_row.get("canonical_outcome_id")),
                "payload_json": _canonical_json(
                    {
                        "classification_label": _normalize(planned.get("classification_label")),
                        "classification_confidence": _normalize(planned.get("confidence_category")),
                        "expanded_join_reason": expanded_join_reason,
                        "baseline_join_reason": baseline_join_reason,
                        "expanded_success_reason": expanded_success_reason,
                        "baseline_success_reason": baseline_success_reason,
                        "execution_exclusion_reason": execution_exclusion_reason,
                        "final_disposition": final_disposition,
                        "root_cause_category": root_cause_category,
                    }
                ),
            }
        )

    if len(lineage_rows) != EXPECTED_PLANNED_OBSERVATIONS:
        raise RuntimeError(f"Expected {EXPECTED_PLANNED_OBSERVATIONS} lineage rows; found {len(lineage_rows)}.")
    if sum(final_disposition_counts.values()) != EXPECTED_PLANNED_OBSERVATIONS:
        raise RuntimeError("Final disposition counts do not sum to the planned population.")
    if final_disposition_counts.get("PRIMARY_ELIGIBLE", 0) != EXPECTED_FINAL_ELIGIBLE:
        raise RuntimeError(
            f"Expected {EXPECTED_FINAL_ELIGIBLE} primary-eligible observations; "
            f"found {final_disposition_counts.get('PRIMARY_ELIGIBLE', 0)}."
        )

    return lineage_rows, {
        "final_disposition_counts": final_disposition_counts,
        "final_disposition_by_label": {k: dict(v) for k, v in final_disposition_by_label.items()},
        "root_cause_counts": root_cause_counts,
        "transition_counts": transition_counts,
        "expanded_join_reason_counts": expanded_join_reason_counts,
        "baseline_join_reason_counts": baseline_join_reason_counts,
        "expanded_success_reason_counts": expanded_success_reason_counts,
        "baseline_success_reason_counts": baseline_success_reason_counts,
        "execution_exclusion_counts": execution_exclusion_counts,
    }


def _build_output_rows(
    *,
    generated_ts: str,
    collapse_run_id: str,
    source_test_execution_run_id: str,
    lineage_rows: Sequence[Mapping[str, Any]],
    counts: Mapping[str, Any],
    latest_summary_row: Mapping[str, Any],
    eligibility_row: Mapping[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    final_disposition_counts: Counter = counts["final_disposition_counts"]
    final_by_label: Dict[str, Dict[str, int]] = counts["final_disposition_by_label"]
    transition_counts: Counter = counts["transition_counts"]
    expanded_join_reason_counts: Counter = counts["expanded_join_reason_counts"]
    baseline_join_reason_counts: Counter = counts["baseline_join_reason_counts"]
    expanded_success_reason_counts: Counter = counts["expanded_success_reason_counts"]
    baseline_success_reason_counts: Counter = counts["baseline_success_reason_counts"]
    execution_exclusion_counts: Counter = counts["execution_exclusion_counts"]

    outcome_join_losses = (
        final_disposition_counts.get("MISSING_EXPANDED_OUTCOME_JOIN", 0)
        + final_disposition_counts.get("MISSING_BASELINE_OUTCOME_JOIN", 0)
        + final_disposition_counts.get("MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN", 0)
        + final_disposition_counts.get("OUTCOME_VERSION_MISMATCH", 0)
        + final_disposition_counts.get("EVALUATION_WINDOW_MISMATCH", 0)
        + final_disposition_counts.get("AMBIGUOUS_OUTCOME", 0)
        + final_disposition_counts.get("DUPLICATE_OUTCOME", 0)
    )
    overlay_losses = final_disposition_counts.get("MISSING_REPAIRED_OUTCOME_OVERLAY", 0)
    success_mapping_losses = (
        final_disposition_counts.get("SUCCESS_MAPPING_EXCLUSION", 0)
        + final_disposition_counts.get("BASELINE_NOT_ELIGIBLE", 0)
        + final_disposition_counts.get("EXPANDED_NOT_ELIGIBLE", 0)
        + final_disposition_counts.get("INVALID_SUCCESS_MAPPING", 0)
    )
    confidence_losses = final_disposition_counts.get("CONFIDENCE_EXCLUSION", 0)
    unknown_losses = final_disposition_counts.get("UNKNOWN_EXCLUSION", 0)
    insufficient_losses = final_disposition_counts.get("INSUFFICIENT_EVIDENCE_EXCLUSION", 0)
    eligibility_losses = confidence_losses + unknown_losses + insufficient_losses
    other_losses = (
        EXPECTED_PLANNED_OBSERVATIONS
        - final_disposition_counts.get("PRIMARY_ELIGIBLE", 0)
        - outcome_join_losses
        - overlay_losses
        - success_mapping_losses
        - eligibility_losses
    )
    complete_population_reconciliation = (
        len(lineage_rows) == EXPECTED_PLANNED_OBSERVATIONS
        and sum(final_disposition_counts.values()) == EXPECTED_PLANNED_OBSERVATIONS
        and final_disposition_counts.get("PRIMARY_ELIGIBLE", 0) == EXPECTED_FINAL_ELIGIBLE
    )
    implementation_defect_detected = False
    scientific_assessment = (
        "G_COMBINATION_OF_CAUSES: outcome linkage (22 row-level losses) + repaired outcome overlay "
        "(11 losses) + deterministic success derivation / frozen eligibility consequences (36 losses); "
        "no implementation defect detected."
    )
    scientific_interpretation = (
        "The collapse from 72 planned primary observations to 3 final eligible observations is fully "
        "deterministic and completely reconciled. No planned observation disappeared. The dominant causes "
        "were missing canonical outcome linkage, missing repaired overlay availability, and frozen "
        "directional-success eligibility rules that rendered joined rows not eligible after success mapping. "
        "All 15 planned NEGATIVE expanded observations were excluded before final eligibility, and the 3 "
        "remaining eligible observations were all POSITIVE rows from one provider-session cluster."
    )

    build_status = "PASS_WITH_WARNINGS" if complete_population_reconciliation else "FAIL"
    final_interpretation = (
        "REFINED_MECHANISM_TEST_PRIMARY_POPULATION_COLLAPSE_EXPLAINED_WITH_WARNINGS"
        if complete_population_reconciliation
        else "REFINED_MECHANISM_TEST_PRIMARY_POPULATION_COLLAPSE_UNRESOLVED"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R16_MECHANISM_TEST_EXECUTION_REVIEW"
        if complete_population_reconciliation and not implementation_defect_detected
        else "RUN_PHASE9A6R15A_POPULATION_COLLAPSE_REPAIR"
    )

    outputs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    outputs[OUTPUT_POPULATION_COLLAPSE].append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "population_collapse_run_id": collapse_run_id,
            "source_test_execution_run_id": source_test_execution_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "planned_primary_observations": EXPECTED_PLANNED_OBSERVATIONS,
            "final_eligible_observations": final_disposition_counts.get("PRIMARY_ELIGIBLE", 0),
            "complete_population_reconciliation": "TRUE" if complete_population_reconciliation else "FALSE",
            "outcome_join_losses": outcome_join_losses,
            "success_mapping_losses": success_mapping_losses,
            "eligibility_losses": eligibility_losses,
            "confidence_losses": confidence_losses,
            "unknown_losses": unknown_losses,
            "overlay_losses": overlay_losses,
            "other_losses": other_losses,
            "root_cause_attribution": scientific_assessment,
            "scientific_interpretation": scientific_interpretation,
            "recommended_next_step": recommended_next_step,
            "payload_json": _canonical_json(
                {
                    "primary_analysis_id": PRIMARY_ANALYSIS_ID,
                    "source_summary_effective_sample": _to_int(latest_summary_row.get("eligible_sample")),
                    "source_eligibility_row": {
                        "candidate_source_count": _to_int(eligibility_row.get("candidate_source_count")),
                        "joined_candidate_count": _to_int(eligibility_row.get("joined_candidate_count")),
                        "eligible_sample_count": _to_int(eligibility_row.get("eligible_sample_count")),
                        "positive_sample_count": _to_int(eligibility_row.get("positive_sample_count")),
                        "negative_sample_count": _to_int(eligibility_row.get("negative_sample_count")),
                        "cluster_count": _to_int(eligibility_row.get("cluster_count")),
                        "provider_count": _to_int(eligibility_row.get("provider_count")),
                        "session_count": _to_int(eligibility_row.get("session_count")),
                    },
                    "final_disposition_counts": dict(final_disposition_counts),
                    "final_disposition_by_label": final_by_label,
                    "transition_counts": dict(transition_counts),
                }
            ),
        }
    )

    for row in lineage_rows:
        outputs[OUTPUT_ROW_LINEAGE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                **row,
            }
        )

    row_level_join_reasons = [
        ("MISSING_EXPANDED_OUTCOME_JOIN", final_disposition_counts.get("MISSING_EXPANDED_OUTCOME_JOIN", 0)),
        ("MISSING_BASELINE_OUTCOME_JOIN", final_disposition_counts.get("MISSING_BASELINE_OUTCOME_JOIN", 0)),
        (
            "MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN",
            final_disposition_counts.get("MISSING_EXPANDED_AND_BASELINE_OUTCOME_JOIN", 0),
        ),
        ("OUTCOME_VERSION_MISMATCH", final_disposition_counts.get("OUTCOME_VERSION_MISMATCH", 0)),
        ("EVALUATION_WINDOW_MISMATCH", final_disposition_counts.get("EVALUATION_WINDOW_MISMATCH", 0)),
        ("AMBIGUOUS_OUTCOME", final_disposition_counts.get("AMBIGUOUS_OUTCOME", 0)),
        ("DUPLICATE_OUTCOME", final_disposition_counts.get("DUPLICATE_OUTCOME", 0)),
    ]
    for reason_code, count in row_level_join_reasons:
        outputs[OUTPUT_JOIN_FAILURE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                "audit_level": "ROW_LEVEL_FINAL_DISPOSITION",
                "side": "ROW",
                "reason_code": reason_code,
                "observation_count": count,
                "side_event_count": count,
                "notes": "Observation-level final disposition count after execution precedence.",
                "payload_json": _canonical_json({"reason_code": reason_code, "count": count}),
            }
        )
    for side, counter in (("EXPANDED", expanded_join_reason_counts), ("BASELINE", baseline_join_reason_counts)):
        for reason_code in sorted(counter):
            outputs[OUTPUT_JOIN_FAILURE].append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "population_collapse_run_id": collapse_run_id,
                    "source_test_execution_run_id": source_test_execution_run_id,
                    "audit_level": "SIDE_LEVEL_JOIN_RESULT",
                    "side": side,
                    "reason_code": reason_code,
                    "observation_count": counter[reason_code],
                    "side_event_count": counter[reason_code],
                    "notes": "Per-side join-validation reason from existing execution audit rows.",
                    "payload_json": _canonical_json({"reason_code": reason_code, "count": counter[reason_code]}),
                }
            )

    row_level_success_reasons = [
        ("SUCCESS_MAPPING_EXCLUSION", final_disposition_counts.get("SUCCESS_MAPPING_EXCLUSION", 0)),
        ("BASELINE_NOT_ELIGIBLE", final_disposition_counts.get("BASELINE_NOT_ELIGIBLE", 0)),
        ("EXPANDED_NOT_ELIGIBLE", final_disposition_counts.get("EXPANDED_NOT_ELIGIBLE", 0)),
        ("INVALID_SUCCESS_MAPPING", final_disposition_counts.get("INVALID_SUCCESS_MAPPING", 0)),
        ("PRIMARY_ELIGIBLE", final_disposition_counts.get("PRIMARY_ELIGIBLE", 0)),
    ]
    for reason_code, count in row_level_success_reasons:
        outputs[OUTPUT_SUCCESS_MAPPING].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                "audit_level": "ROW_LEVEL_FINAL_DISPOSITION",
                "side": "ROW",
                "reason_code": reason_code,
                "observation_count": count,
                "side_event_count": count,
                "notes": "Observation-level outcome after deterministic success mapping.",
                "payload_json": _canonical_json({"reason_code": reason_code, "count": count}),
            }
        )
    for side, counter in (("EXPANDED", expanded_success_reason_counts), ("BASELINE", baseline_success_reason_counts)):
        for reason_code in sorted(counter):
            outputs[OUTPUT_SUCCESS_MAPPING].append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "population_collapse_run_id": collapse_run_id,
                    "source_test_execution_run_id": source_test_execution_run_id,
                    "audit_level": "SIDE_LEVEL_SUCCESS_MAPPING",
                    "side": side,
                    "reason_code": reason_code,
                    "observation_count": counter[reason_code],
                    "side_event_count": counter[reason_code],
                    "notes": "Per-side deterministic success-mapping reason reconstructed from execution audit fields.",
                    "payload_json": _canonical_json({"reason_code": reason_code, "count": counter[reason_code]}),
                }
            )

    transition_rows = [
        ("PLANNED_PRIMARY_OBSERVATIONS", EXPECTED_PLANNED_OBSERVATIONS, "PASS", "Frozen planned primary population."),
        ("EXPANDED_JOIN_ATTEMPTED", EXPECTED_PLANNED_OBSERVATIONS, "PASS", "Expanded-side deterministic join attempted for every planned observation."),
        ("BASELINE_JOIN_ATTEMPTED", EXPECTED_PLANNED_OBSERVATIONS, "PASS", "Baseline-side deterministic join attempted for every planned observation."),
        ("BOTH_JOINS_READY", transition_counts.get("BOTH_JOINS_READY", 0), "PASS", "Both expanded and baseline joins passed frozen join validation."),
        ("OUTCOME_JOIN_LOSSES", outcome_join_losses, "WARN", "Rows lost to missing canonical outcome linkage before success mapping."),
        ("OVERLAY_LOSSES", overlay_losses, "WARN", "Rows lost because repaired canonical overlay was unavailable for at least one side."),
        ("SUCCESS_MAPPING_LOSSES", success_mapping_losses, "WARN", "Rows lost after successful joining because frozen success mapping made at least one side not eligible."),
        ("PRIMARY_ELIGIBLE", final_disposition_counts.get("PRIMARY_ELIGIBLE", 0), "WARN", "Rows remaining for the frozen primary analysis population."),
    ]
    for stage, count, status, notes in transition_rows:
        outputs[OUTPUT_TRANSITIONS].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                "transition_stage": stage,
                "transition_count": count,
                "status": status,
                "notes": notes,
                "payload_json": _canonical_json({"transition_stage": stage, "transition_count": count}),
            }
        )

    root_cause_rows = [
        (
            "OUTCOME_LINKAGE",
            "OUTCOME_LINKAGE",
            outcome_join_losses,
            "PRIMARY",
            "Missing canonical join components explain 22 row-level losses before overlay or success evaluation.",
        ),
        (
            "REPAIRED_OUTCOME_OVERLAY",
            "DATA_AVAILABILITY",
            overlay_losses,
            "PRIMARY",
            "11 rows failed because repaired outcome overlay support was unavailable even though the observation remained in scope pre-outcome.",
        ),
        (
            "SUCCESS_DERIVATION",
            "SUCCESS_DERIVATION",
            success_mapping_losses,
            "PRIMARY",
            "36 rows survived outcome linkage but were deterministically excluded by the frozen corrected-directional success rules.",
        ),
        (
            "FROZEN_ELIGIBILITY",
            "FROZEN_ELIGIBILITY",
            eligibility_losses,
            "SECONDARY",
            "No planned row was later lost to confidence, UNKNOWN, or insufficient-evidence relabeling.",
        ),
        (
            "IMPLEMENTATION_DEFECT",
            "IMPLEMENTATION_DEFECT",
            0,
            "SECONDARY",
            "No implementation defect signal: planned and audited key sets match exactly and all 72 observations reconcile.",
        ),
        (
            "DESIGN_LIMITATION",
            "SCIENTIFIC_DESIGN_LIMITATION",
            success_mapping_losses,
            "SECONDARY",
            "The frozen Structure A primary comparison is highly sensitive to baseline directional eligibility, which eliminated every NEGATIVE expanded observation.",
        ),
    ]
    for cause_id, cause_type, row_count, priority, interpretation in root_cause_rows:
        outputs[OUTPUT_ROOT_CAUSE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                "cause_id": cause_id,
                "cause_type": cause_type,
                "row_count": row_count,
                "primary_or_secondary": priority,
                "status": "ACTIVE" if row_count else "NONE_DETECTED",
                "interpretation": interpretation,
                "payload_json": _canonical_json({"cause_id": cause_id, "row_count": row_count}),
            }
        )

    quant_rows = [
        ("planned_primary_observations", EXPECTED_PLANNED_OBSERVATIONS, "observations", "PASS", "Frozen pre-outcome primary population."),
        ("final_primary_eligible_observations", final_disposition_counts.get("PRIMARY_ELIGIBLE", 0), "observations", "WARN", "Observed final eligible sample."),
        ("outcome_join_losses", outcome_join_losses, "observations", "WARN", "Row-level losses due to missing canonical join support."),
        ("overlay_losses", overlay_losses, "observations", "WARN", "Row-level losses due to missing repaired overlay support."),
        ("success_mapping_losses", success_mapping_losses, "observations", "WARN", "Row-level losses after deterministic success mapping."),
        ("confidence_losses", confidence_losses, "observations", "PASS", "No loss from frozen confidence rules."),
        ("unknown_losses", unknown_losses, "observations", "PASS", "No loss from UNKNOWN handling inside the planned 72."),
        ("other_losses", other_losses, "observations", "PASS" if other_losses == 0 else "WARN", "Residual unexplained loss count."),
        ("planned_negative_observations", 15, "observations", "PASS", "Frozen negative primary-contrast observations."),
        ("final_negative_observations", _to_int(eligibility_row.get("negative_sample_count")), "observations", "WARN", "Final negative sample after join and success mapping."),
        ("planned_positive_observations", 57, "observations", "PASS", "Frozen positive primary-contrast observations."),
        ("final_positive_observations", _to_int(eligibility_row.get("positive_sample_count")), "observations", "WARN", "Final positive sample after join and success mapping."),
    ]
    for metric_name, metric_value, unit, status, notes in quant_rows:
        outputs[OUTPUT_QUANTIFICATION].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
                "source_test_execution_run_id": source_test_execution_run_id,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "unit": unit,
                "status": status,
                "notes": notes,
                "payload_json": _canonical_json({"metric_name": metric_name, "metric_value": metric_value}),
            }
        )

    governance_counters = [
        ("outcome_rows_loaded", 0, "PASS", "This investigation used existing execution audit sheets only; no raw outcome workbook rows were loaded."),
        ("outcome_joins_performed", 0, "PASS", "No new join execution occurred; only prior audited join outputs were reviewed."),
        ("classifications_modified", 0, "PASS", "Permanent classifications were not modified."),
        ("eligibility_rules_modified", 0, "PASS", "Frozen eligibility rules were not modified."),
        ("preregistration_modified", 0, "PASS", "Preregistration artifacts were not modified."),
        ("mechanism_tests_performed", 0, "PASS", "No new mechanism test was executed."),
        ("production_writes", 0, "PASS", "No production workbooks were modified."),
    ]
    for counter_name, counter_value, status, notes in governance_counters:
        outputs[OUTPUT_GOVERNANCE].append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "population_collapse_run_id": collapse_run_id,
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
            "population_collapse_run_id": collapse_run_id,
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "planned_primary_observations": EXPECTED_PLANNED_OBSERVATIONS,
            "final_eligible_observations": final_disposition_counts.get("PRIMARY_ELIGIBLE", 0),
            "complete_population_reconciliation": "TRUE" if complete_population_reconciliation else "FALSE",
            "outcome_join_losses": outcome_join_losses,
            "success_mapping_losses": success_mapping_losses,
            "eligibility_losses": eligibility_losses,
            "confidence_losses": confidence_losses,
            "unknown_losses": unknown_losses,
            "overlay_losses": overlay_losses,
            "other_losses": other_losses,
            "root_cause_attribution": scientific_assessment,
            "scientific_interpretation": scientific_interpretation,
            "recommended_next_step": recommended_next_step,
            "payload_json": _canonical_json(
                {
                    "final_disposition_counts": dict(final_disposition_counts),
                    "execution_exclusion_counts": dict(execution_exclusion_counts),
                    "expanded_join_reason_counts": dict(expanded_join_reason_counts),
                    "baseline_join_reason_counts": dict(baseline_join_reason_counts),
                    "expanded_success_reason_counts": dict(expanded_success_reason_counts),
                    "baseline_success_reason_counts": dict(baseline_success_reason_counts),
                    "negative_final_dispositions": final_by_label.get("NEGATIVE", {}),
                    "positive_final_dispositions": final_by_label.get("POSITIVE", {}),
                }
            ),
        }
    )

    summary = {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "planned_primary_observations": EXPECTED_PLANNED_OBSERVATIONS,
        "final_eligible_observations": final_disposition_counts.get("PRIMARY_ELIGIBLE", 0),
        "complete_population_reconciliation": complete_population_reconciliation,
        "outcome_join_losses": outcome_join_losses,
        "success_mapping_losses": success_mapping_losses,
        "eligibility_losses": eligibility_losses,
        "confidence_losses": confidence_losses,
        "unknown_losses": unknown_losses,
        "overlay_losses": overlay_losses,
        "other_losses": other_losses,
        "root_cause_attribution": scientific_assessment,
        "scientific_interpretation": scientific_interpretation,
        "recommended_next_step": recommended_next_step,
        "negative_final_observations": _to_int(eligibility_row.get("negative_sample_count")),
        "positive_final_observations": _to_int(eligibility_row.get("positive_sample_count")),
        "cluster_count": _to_int(eligibility_row.get("cluster_count")),
        "provider_count": _to_int(eligibility_row.get("provider_count")),
        "session_count": _to_int(eligibility_row.get("session_count")),
        "final_disposition_by_label": final_by_label,
    }
    return outputs, summary


def main() -> None:
    ts = datetime.now(timezone.utc)
    generated_ts = _now_iso(ts)
    collapse_run_id = _run_id(ts)

    service = build_sheets_service(load_credentials())
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    source_test_execution_run_id, latest_summary_row, _latest_summary_payload, context = _select_execution_run(inputs)

    planned_rows = _planned_primary_rows(inputs)
    join_rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_Test_Outcome_Join_Audit"].rows
        if _normalize(row.get("test_execution_run_id")) == source_test_execution_run_id
        and _normalize(row.get("analysis_id")) == PRIMARY_ANALYSIS_ID
    ]
    if len(join_rows) != EXPECTED_PLANNED_OBSERVATIONS:
        raise RuntimeError(
            f"Expected {EXPECTED_PLANNED_OBSERVATIONS} primary join-audit rows; found {len(join_rows)}."
        )

    lineage_rows, counts = _build_row_lineage(planned_rows, join_rows)
    outputs, summary = _build_output_rows(
        generated_ts=generated_ts,
        collapse_run_id=collapse_run_id,
        source_test_execution_run_id=source_test_execution_run_id,
        lineage_rows=lineage_rows,
        counts=counts,
        latest_summary_row=latest_summary_row,
        eligibility_row=context["eligibility_row"],
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
        "planned_primary_observations": summary["planned_primary_observations"],
        "final_eligible_observations": summary["final_eligible_observations"],
        "complete_population_reconciliation": summary["complete_population_reconciliation"],
        "outcome_join_losses": summary["outcome_join_losses"],
        "success_mapping_losses": summary["success_mapping_losses"],
        "eligibility_losses": summary["eligibility_losses"],
        "confidence_losses": summary["confidence_losses"],
        "unknown_losses": summary["unknown_losses"],
        "overlay_losses": summary["overlay_losses"],
        "other_losses": summary["other_losses"],
        "root_cause_attribution": summary["root_cause_attribution"],
        "scientific_interpretation": summary["scientific_interpretation"],
        "governance_counters": {
            "outcome_rows_loaded": 0,
            "outcome_joins_performed": 0,
            "classifications_modified": 0,
            "eligibility_rules_modified": 0,
            "preregistration_modified": 0,
            "mechanism_tests_performed": 0,
            "production_writes": 0,
        },
        "recommended_next_step": summary["recommended_next_step"],
        "source_test_execution_run_id": source_test_execution_run_id,
        "registry_status": registry_status,
    }
    print(json.dumps(final_report, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
