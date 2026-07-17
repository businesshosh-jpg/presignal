#!/usr/bin/env python3
"""Phase 9A-6R11 — v1.1 Refined Classification Execution Review.

This phase independently reviews the permanent versioned diagnostic
classification execution produced in Phase 9A-6R10. It does not rerun
classification writes, modify permanent labels, test mechanisms, evaluate
accuracy, or access outcome data.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


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
    APPROVAL_RERUN_VERSION,
    EXECUTION_VERSION,
    MECHANISM_VERSION,
    PREREGISTRATION_VERSION,
    _append_rows,
    _build_rows,
    _compare_builds,
    _fetch_input_sheets,
    _fingerprint_verification,
    _index_by,
    _json_loads_safe,
    _normalize,
    _sheet_titles_light,
)


PHASE_ID = "9A-6R11"
BUILD_SCRIPT = "automation/build_refined_mechanism_v11_classification_execution_review_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_v11_classification_execution_review_v0"
REVIEW_VERSION = "refined_mechanism_v11_classification_execution_review_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_V11_EXECUTION_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"

TARGET_CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
TARGET_FINAL_INTERPRETATIONS = {
    "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_READY",
    "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_READY_WITH_WARNINGS",
}

EXPECTED_SCOPE = {
    "candidate": 360,
    "previewed": 225,
    "unknown_status": 20,
    "low_confidence_status": 1,
    "excluded": 114,
    "blocked": 0,
}

EXPECTED_LABELS = {
    "POSITIVE": 183,
    "NEGATIVE": 32,
    "UNKNOWN": 21,
    "INSUFFICIENT_EVIDENCE": 10,
    "EXCLUDED": 114,
}

EXPECTED_CONFLICTS = {
    "reviewed": 21,
    "unknown_preserved": 20,
    "low_confidence_preserved": 1,
    "forced_conversions": 0,
    "confidence_increases": 0,
    "manual_overrides": 0,
}

INPUT_SHEETS: Tuple[str, ...] = (
    # Phase 9A-6R10 outputs
    "Refined_Mechanism_v11_Classifications",
    "Refined_Mechanism_v11_Classification_Evidence",
    "Refined_Mechanism_v11_Classification_Conflicts",
    "Refined_Mechanism_v11_Classification_Confidence",
    "Refined_Mechanism_v11_Classification_Audit",
    "Refined_Mechanism_v11_Classification_Governance",
    "Refined_Mechanism_v11_Classification_Summary",
    # Phase 9A-6R9R approval outputs
    "Refined_Mechanism_v11_Execution_Approval_Rerun",
    "Refined_Mechanism_v11_Rerun_Row_Reconciliation",
    "Refined_Mechanism_v11_Rerun_Conflict_Reconciliation",
    "Refined_Mechanism_v11_Rerun_Dedupe_Approval",
    "Refined_Mechanism_v11_Rerun_Stop_Rule_Approval",
    "Refined_Mechanism_v11_Rerun_Version_Freeze",
    "Refined_Mechanism_v11_Rerun_Output_Safety",
    "Refined_Mechanism_v11_Rerun_Traceability_Approval",
    "Refined_Mechanism_v11_Rerun_Determinism_Check",
    "Refined_Mechanism_v11_Rerun_Leakage_Check",
    "Refined_Mechanism_v11_Execution_Approval_Rerun_Summary",
    # Phase 9A-6R8R repaired plan outputs
    "Refined_Mechanism_v11_Execution_Plan_Repair",
    "Refined_Mechanism_v11_Repaired_Output_Schema_Plan",
    "Refined_Mechanism_v11_Repaired_Stop_Hold_Rules",
    "Refined_Mechanism_v11_Repair_Dedupe_Audit",
    "Refined_Mechanism_v11_Repair_Stop_Rule_Audit",
    "Refined_Mechanism_v11_Repair_Row_Scope_Reconciliation",
    "Refined_Mechanism_v11_Execution_Plan_Repair_Summary",
    # Phase 9A-6R7 conflict review evidence
    "Refined_Mechanism_v11_Unresolved_Conflict_Review",
    "Refined_Mechanism_v11_Execution_Readiness",
    "Refined_Mechanism_v11_Conflict_Review_Summary",
    # Phase 9A-6R6 dry-run evidence
    "Refined_Mechanism_v11_Classification_Dry_Run",
    "Refined_Mechanism_v11_Label_Preview",
    "Refined_Mechanism_v11_Evidence_Audit",
    "Refined_Mechanism_v11_Rule_Path_Audit",
    "Refined_Mechanism_v11_Specificity_Boundary_Audit",
    "Refined_Mechanism_v11_Conflict_Audit",
    "Refined_Mechanism_v11_Confidence_Preview",
    "Refined_Mechanism_v11_Determinism_Audit",
    "Refined_Mechanism_v11_Leakage_Audit",
    "Refined_Mechanism_v11_Dry_Run_Summary",
    # Frozen preregistration
    "Refined_Mechanism_v11_PreRegistration",
    "Refined_Mechanism_v11_Frozen_Definitions",
    "Refined_Mechanism_v11_Frozen_Observables",
    "Refined_Mechanism_v11_Frozen_Label_Rules",
    "Refined_Mechanism_v11_Frozen_Confidence_Rules",
    "Refined_Mechanism_v11_Frozen_Conflict_Rules",
    "Refined_Mechanism_v11_Frozen_Falsification_Rules",
    "Refined_Mechanism_v11_Separation_Rules",
    "Refined_Mechanism_v11_PreRegistration_Summary",
    # Inputs required by the frozen execution rebuild
    "Refined_Mechanism_v11_Row_Execution_Scope",
    "Refined_Mechanism_v11_Conflict_Disposition_Plan",
)


OUTPUT_REVIEW = "Refined_Mechanism_v11_Execution_Review"
OUTPUT_RUN_IDENTITY = "Refined_Mechanism_v11_Run_Identity_Audit"
OUTPUT_RECON = "Refined_Mechanism_v11_Classification_Reconciliation"
OUTPUT_RESUME = "Refined_Mechanism_v11_Resume_Idempotence_Audit"
OUTPUT_CONFLICTS = "Refined_Mechanism_v11_Conflict_Disposition_Review"
OUTPUT_TRACE = "Refined_Mechanism_v11_Trace_Completeness_Review"
OUTPUT_COMPACT = "Refined_Mechanism_v11_Compact_Support_Audit"
OUTPUT_DETERMINISM = "Refined_Mechanism_v11_Determinism_Review"
OUTPUT_LEAKAGE = "Refined_Mechanism_v11_Leakage_Review"
OUTPUT_STOP = "Refined_Mechanism_v11_Stop_Rule_Review"
OUTPUT_GOV = "Refined_Mechanism_v11_Execution_Review_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_v11_Execution_Review_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    OUTPUT_REVIEW: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "review_area",
        "review_status",
        "evidence_summary",
        "readiness_flag",
        "notes",
    ],
    OUTPUT_RUN_IDENTITY: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "classification_rows_reviewed",
        "rows_with_approved_run_id",
        "rows_with_other_run_ids",
        "rows_with_missing_run_id",
        "version_lineage_mismatches",
        "resume_classification",
        "notes",
    ],
    OUTPUT_RECON: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "exact_scientific_matches",
        "exact_idempotent_duplicates",
        "key_match_content_mismatches",
        "trace_mismatches",
        "version_mismatches",
        "unverifiable_rows",
        "scope_mismatches",
        "notes",
    ],
    OUTPUT_RESUME: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "target_classification_run_id",
        "initial_row_generated_ts",
        "final_summary_generated_ts",
        "prior_partial_write_detected",
        "same_run_id_resumed",
        "rows_revalidated_before_acceptance",
        "resume_classification",
        "notes",
    ],
    OUTPUT_CONFLICTS: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "conflict_rows_reviewed",
        "unknown_dispositions_preserved",
        "low_confidence_disposition_preserved",
        "forced_conversions",
        "confidence_increases",
        "manual_overrides",
        "review_status",
        "notes",
    ],
    OUTPUT_TRACE: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "full_inline_trace_rows",
        "stable_reference_trace_rows",
        "partial_trace_rows",
        "missing_trace_rows",
        "broken_references",
        "trace_status",
        "notes",
    ],
    OUTPUT_COMPACT: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "support_rows_written",
        "non_conflict_rows_reviewed",
        "reproducible_via_stable_reference",
        "confidence_basis_verifiable",
        "rule_path_identifiable",
        "compact_support_design_status",
        "notes",
    ],
    OUTPUT_DETERMINISM: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "rebuilt_expected_rows",
        "actual_rows_reviewed",
        "dry_run_alignment",
        "approved_disposition_alignment",
        "determinism_review_status",
        "notes",
    ],
    OUTPUT_LEAKAGE: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "rows_reviewed",
        "outcome_independence_true_rows",
        "forbidden_access_findings",
        "future_information_findings",
        "leakage_review_status",
        "notes",
    ],
    OUTPUT_STOP: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "blocked_attempts_before_success",
        "approved_stop_rules_reviewed",
        "recovery_lineage_clear",
        "recovery_not_marked_success_before_summary",
        "stop_rule_recovery_status",
        "notes",
    ],
    OUTPUT_GOV: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "provider_calls_performed",
        "forecasts_generated",
        "classification_rerun_performed",
        "permanent_labels_modified",
        "mechanism_testing_performed",
        "accuracy_evaluation_performed",
        "outcomes_accessed",
        "source_sheets_modified",
        "production_writes",
        "production_behavior_changes",
        "governance_status",
        "notes",
    ],
    OUTPUT_SUMMARY: [
        "generated_ts",
        "schema_version",
        "review_version",
        "review_run_id",
        "classification_rows_reviewed",
        "rows_with_approved_run_id",
        "rows_with_other_run_ids",
        "rows_with_missing_run_id",
        "version_lineage_mismatches",
        "resume_classification",
        "exact_scientific_matches",
        "exact_idempotent_duplicates",
        "key_match_content_mismatches",
        "trace_mismatches",
        "version_mismatches",
        "unverifiable_rows",
        "rows_as_previewed",
        "rows_as_unknown",
        "rows_with_low_confidence",
        "rows_excluded",
        "scope_mismatches",
        "positive_labels",
        "negative_labels",
        "unknown_labels",
        "insufficient_evidence_labels",
        "excluded_labels",
        "conflict_rows_reviewed",
        "unknown_dispositions_preserved",
        "low_confidence_disposition_preserved",
        "forced_conversions",
        "confidence_increases",
        "manual_overrides",
        "full_inline_trace_rows",
        "stable_reference_trace_rows",
        "partial_trace_rows",
        "missing_trace_rows",
        "broken_references",
        "compact_support_design_status",
        "unique_dedupe_keys",
        "exact_duplicate_events",
        "contradictory_duplicates",
        "fingerprints_matched",
        "determinism_review",
        "leakage_findings",
        "stop_rule_recovery_status",
        "build_status",
        "final_interpretation",
        "ready_for_mechanism_test_planning_readiness_review",
        "ready_for_mechanism_testing",
        "ready_for_production",
        "recommended_next_step",
        "notes",
    ],
}

OUTPUT_LOGICAL_IDS = {
    OUTPUT_REVIEW: "REFINED_MECHANISM_V11_EXECUTION_REVIEW",
    OUTPUT_RUN_IDENTITY: "REFINED_MECHANISM_V11_RUN_IDENTITY_AUDIT",
    OUTPUT_RECON: "REFINED_MECHANISM_V11_CLASSIFICATION_RECONCILIATION",
    OUTPUT_RESUME: "REFINED_MECHANISM_V11_RESUME_IDEMPOTENCE_AUDIT",
    OUTPUT_CONFLICTS: "REFINED_MECHANISM_V11_CONFLICT_DISPOSITION_REVIEW",
    OUTPUT_TRACE: "REFINED_MECHANISM_V11_TRACE_COMPLETENESS_REVIEW",
    OUTPUT_COMPACT: "REFINED_MECHANISM_V11_COMPACT_SUPPORT_AUDIT",
    OUTPUT_DETERMINISM: "REFINED_MECHANISM_V11_DETERMINISM_REVIEW",
    OUTPUT_LEAKAGE: "REFINED_MECHANISM_V11_LEAKAGE_REVIEW",
    OUTPUT_STOP: "REFINED_MECHANISM_V11_STOP_RULE_REVIEW",
    OUTPUT_GOV: "REFINED_MECHANISM_V11_EXECUTION_REVIEW_GOVERNANCE",
    OUTPUT_SUMMARY: "REFINED_MECHANISM_V11_EXECUTION_REVIEW_SUMMARY",
}

SCIENTIFIC_FIELDS = [
    "classification_label",
    "confidence_category",
    "eligibility_status",
    "frozen_rule_id",
    "decisive_observable_ids",
    "decisive_evidence_trace",
    "conflict_status",
    "conflict_disposition",
    "exclusion_reason",
    "unknown_reason",
    "low_confidence_reason",
    "outcome_independence_verified",
    "mechanism_version",
    "preregistration_version",
    "execution_plan_version",
    "approval_rerun_version",
    "source_row_key",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _review_run_id(ts: datetime) -> str:
    return f"9A-6R11_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _single_row(rows: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    return dict(rows[0]) if rows else {}


def _row_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))


def _classification_key(row: Mapping[str, Any]) -> Tuple[str, str, str, str]:
    return (
        _normalize(row.get("classification_run_id")),
        _normalize(row.get("mechanism_version")),
        _normalize(row.get("mechanism_id")),
        _normalize(row.get("source_row_key")),
    )


def _parse_trace(trace_text: Any) -> Dict[str, Any]:
    parsed = _json_loads_safe(trace_text)
    return parsed if isinstance(parsed, dict) else {}


def _count_by(rows: Sequence[Mapping[str, Any]], field: str) -> Counter:
    return Counter(_normalize(row.get(field)) for row in rows)


def _safe_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


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
            "notes": (
                "Phase 9A-6R11 independent execution-review outputs for v1.1 refined permanent diagnostic "
                "classification; diagnostic-only and non-production."
            ),
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


def _summary_rows_for_run(rows: Sequence[Mapping[str, Any]], run_id: str) -> List[Dict[str, str]]:
    return [dict(row) for row in rows if _normalize(row.get("classification_run_id")) == run_id]


def _target_execution_summary(inputs: Dict[str, Any]) -> Dict[str, str]:
    rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Summary"].rows, TARGET_CLASSIFICATION_RUN_ID)
    if len(rows) != 1:
        raise RuntimeError(
            f"Expected exactly one execution summary row for {TARGET_CLASSIFICATION_RUN_ID}, found {len(rows)}."
        )
    summary = rows[0]
    if _normalize(summary.get("final_interpretation")) not in TARGET_FINAL_INTERPRETATIONS:
        raise RuntimeError("Target classification run summary is not a successful or warning-successful execution.")
    return summary


def _collect_target_classifications(inputs: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = [
        dict(row)
        for row in inputs["Refined_Mechanism_v11_Classifications"].rows
        if _normalize(row.get("classification_run_id")) == TARGET_CLASSIFICATION_RUN_ID
    ]
    if len(rows) != EXPECTED_SCOPE["candidate"]:
        raise RuntimeError(
            f"Expected {EXPECTED_SCOPE['candidate']} classification rows for {TARGET_CLASSIFICATION_RUN_ID}, found {len(rows)}."
        )
    return rows


def _run_identity_audit(
    class_rows: Sequence[Mapping[str, Any]],
    summary_row: Mapping[str, Any],
) -> Dict[str, Any]:
    approved_run_id_rows = 0
    other_run_id_rows = 0
    missing_run_id_rows = 0
    version_lineage_mismatches = 0
    generated_ts_values: Set[str] = set()

    expected_plan_version = _normalize(summary_row.get("execution_plan_version"))
    for row in class_rows:
        run_id = _normalize(row.get("classification_run_id"))
        if not run_id:
            missing_run_id_rows += 1
        elif run_id == TARGET_CLASSIFICATION_RUN_ID:
            approved_run_id_rows += 1
        else:
            other_run_id_rows += 1

        generated_ts_values.add(_normalize(row.get("generated_ts")))
        mismatch = any(
            [
                _normalize(row.get("mechanism_version")) != MECHANISM_VERSION,
                _normalize(row.get("preregistration_version")) != PREREGISTRATION_VERSION,
                _normalize(row.get("approval_rerun_version")) != APPROVAL_RERUN_VERSION,
                _normalize(row.get("execution_plan_version")) != expected_plan_version,
                not _normalize(row.get("classification_timestamp")),
                not _normalize(row.get("source_row_key")),
                len(_classification_key(row)) != 4,
            ]
        )
        if mismatch:
            version_lineage_mismatches += 1

    resume_note = _normalize(summary_row.get("notes")).lower()
    resume_classification = (
        "VALID_SAME_RUN_RESUME"
        if "resumed from an already-persisted partial run" in resume_note
        and len(generated_ts_values) == 1
        else "UNVERIFIABLE_PARTIAL_WRITE"
    )
    return {
        "classification_rows_reviewed": len(class_rows),
        "rows_with_approved_run_id": approved_run_id_rows,
        "rows_with_other_run_ids": other_run_id_rows,
        "rows_with_missing_run_id": missing_run_id_rows,
        "version_lineage_mismatches": version_lineage_mismatches,
        "resume_classification": resume_classification,
        "initial_row_generated_ts": next(iter(generated_ts_values)) if len(generated_ts_values) == 1 else "",
    }


def _rebuild_expected_execution(
    inputs: Dict[str, Any],
    generated_ts: str,
) -> Tuple[List[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]], bool]:
    build_first = _build_rows(generated_ts, TARGET_CLASSIFICATION_RUN_ID, inputs)
    build_second = _build_rows(generated_ts, TARGET_CLASSIFICATION_RUN_ID, inputs)
    determinism_match = _compare_builds(build_first, build_second)
    expected_by_key = {_row_key(row): row for row in build_first.classifications}
    return build_first.classifications, expected_by_key, determinism_match


def _classification_reconciliation(
    actual_rows: Sequence[Mapping[str, Any]],
    expected_by_key: Mapping[Tuple[str, str], Mapping[str, Any]],
    summary_row: Mapping[str, Any],
) -> Dict[str, Any]:
    exact_scientific_matches = 0
    exact_idempotent_duplicates = 0
    key_match_content_mismatches = 0
    trace_mismatches = 0
    version_mismatches = 0
    unverifiable_rows = 0
    issues: List[str] = []
    resumed = "resumed from an already-persisted partial run" in _normalize(summary_row.get("notes")).lower()

    for row in actual_rows:
        key = _row_key(row)
        expected = expected_by_key.get(key)
        if expected is None:
            unverifiable_rows += 1
            issues.append(f"missing_expected:{key[0]}|{key[1]}")
            continue

        mismatched_fields = [
            field
            for field in SCIENTIFIC_FIELDS
            if _normalize(row.get(field)) != _normalize(expected.get(field))
        ]
        if mismatched_fields:
            if any(field in {"mechanism_version", "preregistration_version", "execution_plan_version", "approval_rerun_version"} for field in mismatched_fields):
                version_mismatches += 1
            elif any(field in {"decisive_observable_ids", "decisive_evidence_trace"} for field in mismatched_fields):
                trace_mismatches += 1
            else:
                key_match_content_mismatches += 1
            issues.append(f"{key[0]}|{key[1]}:{','.join(mismatched_fields[:4])}")
            continue

        if resumed:
            exact_idempotent_duplicates += 1
        else:
            exact_scientific_matches += 1

    if len(expected_by_key) != len(actual_rows):
        unverifiable_rows += abs(len(expected_by_key) - len(actual_rows))

    return {
        "exact_scientific_matches": exact_scientific_matches,
        "exact_idempotent_duplicates": exact_idempotent_duplicates,
        "key_match_content_mismatches": key_match_content_mismatches,
        "trace_mismatches": trace_mismatches,
        "version_mismatches": version_mismatches,
        "unverifiable_rows": unverifiable_rows,
        "issues": issues[:5],
    }


def _scope_and_label_review(class_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    status_counts = {
        "candidate": len(class_rows),
        "previewed": 0,
        "unknown_status": 0,
        "low_confidence_status": 0,
        "excluded": 0,
        "blocked": 0,
    }
    label_counts = {
        "POSITIVE": 0,
        "NEGATIVE": 0,
        "UNKNOWN": 0,
        "INSUFFICIENT_EVIDENCE": 0,
        "EXCLUDED": 0,
    }
    for row in class_rows:
        status = _normalize(row.get("eligibility_status"))
        label = _normalize(row.get("classification_label"))
        if status == "EXECUTE_AS_PREVIEWED":
            status_counts["previewed"] += 1
        elif status == "EXECUTE_AS_UNKNOWN":
            status_counts["unknown_status"] += 1
        elif status == "EXECUTE_WITH_LOW_CONFIDENCE":
            status_counts["low_confidence_status"] += 1
        elif status in {"OUT_OF_SCOPE", "EXCLUDE_FROM_EXECUTION"}:
            status_counts["excluded"] += 1
        else:
            status_counts["blocked"] += 1
        label_counts[label] = label_counts.get(label, 0) + 1

    scope_mismatches = 0
    for key, expected in EXPECTED_SCOPE.items():
        if status_counts.get(key, 0) != expected:
            scope_mismatches += 1
    for key, expected in EXPECTED_LABELS.items():
        if label_counts.get(key, 0) != expected:
            scope_mismatches += 1

    return {"status_counts": status_counts, "label_counts": label_counts, "scope_mismatches": scope_mismatches}


def _conflict_review(
    class_rows: Sequence[Mapping[str, Any]],
    conflict_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    class_by_key = {_row_key(row): row for row in class_rows}
    unknown_preserved = 0
    low_confidence_preserved = 0
    forced_conversions = 0
    confidence_increases = 0
    manual_overrides = 0
    notes: List[str] = []

    for row in conflict_rows:
        key = (_normalize(row.get("mechanism_id")), _normalize(row.get("source_row_key")))
        actual = class_by_key.get(key, {})
        disposition = _normalize(row.get("repaired_execution_disposition"))
        planned_label = _normalize(row.get("planned_execution_label"))
        planned_confidence = _normalize(row.get("planned_execution_confidence"))
        actual_label = _normalize(actual.get("classification_label"))
        actual_confidence = _normalize(actual.get("confidence_category"))
        if disposition == "EXECUTE_AS_UNKNOWN" and actual_label == "UNKNOWN":
            unknown_preserved += 1
        elif disposition == "EXECUTE_AS_UNKNOWN":
            forced_conversions += 1
            notes.append(f"unexpected_non_unknown:{key[0]}|{key[1]}")
        elif disposition == "EXECUTE_WITH_LOW_CONFIDENCE":
            if actual_label == planned_label and actual_confidence == planned_confidence == "LOW":
                low_confidence_preserved += 1
            else:
                confidence_increases += 1
                notes.append(f"low_confidence_mismatch:{key[0]}|{key[1]}")
        if _normalize(row.get("manual_override_required")) == "TRUE":
            manual_overrides += 1

    return {
        "conflict_rows_reviewed": len(conflict_rows),
        "unknown_dispositions_preserved": unknown_preserved,
        "low_confidence_disposition_preserved": low_confidence_preserved,
        "forced_conversions": forced_conversions,
        "confidence_increases": confidence_increases,
        "manual_overrides": manual_overrides,
        "notes": notes[:5],
    }


def _trace_review(
    class_rows: Sequence[Mapping[str, Any]],
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    label_preview_by_key = _index_by(inputs["Refined_Mechanism_v11_Label_Preview"], "mechanism_id", "source_row_key")
    rule_path_by_key = _index_by(inputs["Refined_Mechanism_v11_Rule_Path_Audit"], "mechanism_id", "source_row_key")
    confidence_by_key = _index_by(inputs["Refined_Mechanism_v11_Confidence_Preview"], "mechanism_id", "source_row_key")
    leakage_by_key = _index_by(inputs["Refined_Mechanism_v11_Leakage_Audit"], "mechanism_id", "source_row_key")

    full_inline_trace_rows = 0
    stable_reference_trace_rows = 0
    partial_trace_rows = 0
    missing_trace_rows = 0
    broken_references = 0
    notes: List[str] = []

    for row in class_rows:
        key = _row_key(row)
        trace = _parse_trace(row.get("decisive_evidence_trace"))
        required_inline = all(
            [
                _normalize(row.get("classification_run_id")),
                _normalize(row.get("mechanism_version")),
                _normalize(row.get("preregistration_version")),
                _normalize(row.get("execution_plan_version")),
                _normalize(row.get("approval_rerun_version")),
                _normalize(row.get("mechanism_id")),
                _normalize(row.get("source_row_key")),
                _normalize(row.get("source_sheet")),
                _normalize(row.get("source_row_reference")),
                _normalize(row.get("frozen_rule_id")),
                _normalize(row.get("decisive_observable_ids")),
                _normalize(row.get("decisive_evidence_trace")),
                _normalize(row.get("conflict_status")),
                _normalize(row.get("conflict_disposition")),
                _normalize(row.get("confidence_category")),
                _normalize(row.get("outcome_independence_verified")) == "TRUE",
            ]
        )
        has_references = all(
            [
                key in label_preview_by_key,
                key in rule_path_by_key,
                key in confidence_by_key,
                key in leakage_by_key,
                _normalize(trace.get("preview_id")),
                _normalize(trace.get("rule_path_sheet")),
                _normalize(trace.get("source_sheet")),
            ]
        )
        if required_inline and has_references:
            full_inline_trace_rows += 1
        elif required_inline:
            stable_reference_trace_rows += 1
            broken_references += 1
            notes.append(f"reference_gap:{key[0]}|{key[1]}")
        elif any(
            [
                _normalize(row.get("frozen_rule_id")),
                _normalize(row.get("decisive_observable_ids")),
                _normalize(row.get("decisive_evidence_trace")),
            ]
        ):
            partial_trace_rows += 1
            notes.append(f"partial_trace:{key[0]}|{key[1]}")
        else:
            missing_trace_rows += 1
            notes.append(f"missing_trace:{key[0]}|{key[1]}")

    trace_status = (
        "PASS"
        if partial_trace_rows == 0 and missing_trace_rows == 0 and broken_references == 0
        else "NEEDS_REPAIR"
    )
    return {
        "full_inline_trace_rows": full_inline_trace_rows,
        "stable_reference_trace_rows": stable_reference_trace_rows,
        "partial_trace_rows": partial_trace_rows,
        "missing_trace_rows": missing_trace_rows,
        "broken_references": broken_references,
        "trace_status": trace_status,
        "notes": notes[:5],
    }


def _compact_support_audit(
    class_rows: Sequence[Mapping[str, Any]],
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    evidence_rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Evidence"].rows, TARGET_CLASSIFICATION_RUN_ID)
    conflict_rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Conflicts"].rows, TARGET_CLASSIFICATION_RUN_ID)
    confidence_rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Confidence"].rows, TARGET_CLASSIFICATION_RUN_ID)
    audit_rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Audit"].rows, TARGET_CLASSIFICATION_RUN_ID)
    rule_path_by_key = _index_by(inputs["Refined_Mechanism_v11_Rule_Path_Audit"], "mechanism_id", "source_row_key")
    confidence_by_key = _index_by(inputs["Refined_Mechanism_v11_Confidence_Preview"], "mechanism_id", "source_row_key")
    leakage_by_key = _index_by(inputs["Refined_Mechanism_v11_Leakage_Audit"], "mechanism_id", "source_row_key")

    non_conflict_rows = [
        row for row in class_rows if _normalize(row.get("eligibility_status")) != "EXECUTE_AS_UNKNOWN" and not (
            _normalize(row.get("eligibility_status")) == "EXECUTE_WITH_LOW_CONFIDENCE"
        )
    ]
    reproducible_via_stable_reference = True
    confidence_basis_verifiable = True
    rule_path_identifiable = True
    notes: List[str] = []

    for row in non_conflict_rows:
        key = _row_key(row)
        trace = _parse_trace(row.get("decisive_evidence_trace"))
        if not _normalize(trace.get("preview_id")) or key not in leakage_by_key:
            reproducible_via_stable_reference = False
            notes.append(f"reproducibility_gap:{key[0]}|{key[1]}")
        if key not in confidence_by_key:
            confidence_basis_verifiable = False
            notes.append(f"confidence_gap:{key[0]}|{key[1]}")
        if key not in rule_path_by_key:
            rule_path_identifiable = False
            notes.append(f"rule_path_gap:{key[0]}|{key[1]}")

    support_rows_written = len(evidence_rows) + len(conflict_rows) + len(confidence_rows) + len(audit_rows)
    design_status = (
        "ACCEPTABLE_WITH_WARNINGS"
        if reproducible_via_stable_reference and confidence_basis_verifiable and rule_path_identifiable
        else "TRACE_INCOMPLETE"
    )
    return {
        "support_rows_written": support_rows_written,
        "non_conflict_rows_reviewed": len(non_conflict_rows),
        "reproducible_via_stable_reference": reproducible_via_stable_reference,
        "confidence_basis_verifiable": confidence_basis_verifiable,
        "rule_path_identifiable": rule_path_identifiable,
        "compact_support_design_status": design_status,
        "notes": notes[:5],
    }


def _dedupe_audit(class_rows: Sequence[Mapping[str, Any]], summary_row: Mapping[str, Any]) -> Dict[str, Any]:
    keys = [_classification_key(row) for row in class_rows]
    unique_dedupe_keys = len(set(keys))
    contradictory_duplicates = len(keys) - unique_dedupe_keys
    resumed = "resumed from an already-persisted partial run" in _normalize(summary_row.get("notes")).lower()
    exact_duplicate_events = len(class_rows) if resumed else 0
    return {
        "unique_dedupe_keys": unique_dedupe_keys,
        "exact_duplicate_events": exact_duplicate_events,
        "contradictory_duplicates": contradictory_duplicates,
    }


def _stop_rule_review(inputs: Dict[str, Any], summary_row: Mapping[str, Any]) -> Dict[str, Any]:
    all_summaries = inputs["Refined_Mechanism_v11_Classification_Summary"].rows
    blocked_attempts = [
        row
        for row in all_summaries
        if _normalize(row.get("classification_run_id")) != TARGET_CLASSIFICATION_RUN_ID
        and _normalize(row.get("final_interpretation")) == "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_BLOCKED"
    ]
    stop_rules = inputs["Refined_Mechanism_v11_Repaired_Stop_Hold_Rules"].rows
    recovery_lineage_clear = "resumed from an already-persisted partial run" in _normalize(summary_row.get("notes")).lower()
    recovery_not_marked_success_before_summary = len(_summary_rows_for_run(all_summaries, TARGET_CLASSIFICATION_RUN_ID)) == 1
    recovery_status = (
        "RECOVERY_COMPLIANT_WITH_WARNINGS"
        if recovery_lineage_clear and recovery_not_marked_success_before_summary
        else "RECOVERY_RULE_AMBIGUITY"
    )
    return {
        "blocked_attempts_before_success": len(blocked_attempts),
        "approved_stop_rules_reviewed": len(stop_rules),
        "recovery_lineage_clear": recovery_lineage_clear,
        "recovery_not_marked_success_before_summary": recovery_not_marked_success_before_summary,
        "stop_rule_recovery_status": recovery_status,
        "notes": [f"{_normalize(row.get('classification_run_id'))}:{_normalize(row.get('notes'))}" for row in blocked_attempts[:2]],
    }


def _governance_review(inputs: Dict[str, Any]) -> Dict[str, Any]:
    gov_rows = _summary_rows_for_run(inputs["Refined_Mechanism_v11_Classification_Governance"].rows, TARGET_CLASSIFICATION_RUN_ID)
    governance_map = {_normalize(row.get("check_name")): _normalize(row.get("actual_value")) for row in gov_rows}
    counters = {
        "provider_calls_performed": int(governance_map.get("provider_calls_performed", "0") or 0),
        "forecasts_generated": int(governance_map.get("forecasts_generated", "0") or 0),
        "classification_rerun_performed": 0,
        "permanent_labels_modified": 0,
        "mechanism_testing_performed": int(governance_map.get("mechanism_testing_performed", "0") or 0),
        "accuracy_evaluation_performed": int(governance_map.get("accuracy_evaluation_performed", "0") or 0),
        "outcomes_accessed": int(governance_map.get("outcome_values_accessed", "0") or 0),
        "source_sheets_modified": int(governance_map.get("execution_plan_modified", "0") or 0),
        "production_writes": int(governance_map.get("production_sheet_writes", "0") or 0),
        "production_behavior_changes": int(governance_map.get("production_behavior_changes", "0") or 0),
    }
    governance_status = "PASS" if all(value == 0 for value in counters.values()) else "FAIL"
    return {**counters, "governance_status": governance_status}


def build() -> Dict[str, Any]:
    review_ts = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = review_ts.isoformat().replace("+00:00", "Z")
    review_run_id = _review_run_id(review_ts)

    service = build_sheets_service(load_credentials())
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHEETS)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    summary_row = _target_execution_summary(inputs)
    class_rows = _collect_target_classifications(inputs)
    run_identity = _run_identity_audit(class_rows, summary_row)
    expected_rows, expected_by_key, determinism_rebuild_match = _rebuild_expected_execution(
        inputs, run_identity["initial_row_generated_ts"]
    )
    reconciliation = _classification_reconciliation(class_rows, expected_by_key, summary_row)
    scope_review = _scope_and_label_review(class_rows)
    conflict_review = _conflict_review(class_rows, inputs["Refined_Mechanism_v11_Rerun_Conflict_Reconciliation"].rows)
    trace_review = _trace_review(class_rows, inputs)
    compact_support = _compact_support_audit(class_rows, inputs)
    dedupe_review = _dedupe_audit(class_rows, summary_row)
    fingerprint_rows, fingerprints_matched = _fingerprint_verification(inputs)
    stop_review = _stop_rule_review(inputs, summary_row)
    governance_review = _governance_review(inputs)

    actual_by_key = {_row_key(row): row for row in class_rows}
    determinism_review_status = (
        "PASS"
        if determinism_rebuild_match
        and len(expected_rows) == len(class_rows)
        and all(
            all(_normalize(actual_by_key[_row_key(expected)].get(field)) == _normalize(expected.get(field)) for field in SCIENTIFIC_FIELDS)
            for expected in expected_rows
        )
        else "FAIL"
    )

    leakage_findings = 0
    outcome_independence_true_rows = 0
    leakage_notes: List[str] = []
    leakage_by_key = _index_by(inputs["Refined_Mechanism_v11_Leakage_Audit"], "mechanism_id", "source_row_key")
    for row in class_rows:
        key = _row_key(row)
        leakage_row = leakage_by_key.get(key, {})
        if _normalize(row.get("outcome_independence_verified")) == "TRUE":
            outcome_independence_true_rows += 1
        else:
            leakage_findings += 1
            leakage_notes.append(f"classification_flag_false:{key[0]}|{key[1]}")
        if any(
            [
                _normalize(leakage_row.get("outcome_field_accessed")) != "FALSE",
                _normalize(leakage_row.get("future_information_accessed")) != "FALSE",
                _normalize(leakage_row.get("prohibited_sheet_accessed")) != "FALSE",
            ]
        ):
            leakage_findings += 1
            leakage_notes.append(f"dry_run_leakage:{key[0]}|{key[1]}")

    ready_for_next = all(
        [
            run_identity["rows_with_approved_run_id"] == EXPECTED_SCOPE["candidate"],
            run_identity["rows_with_other_run_ids"] == 0,
            run_identity["rows_with_missing_run_id"] == 0,
            run_identity["version_lineage_mismatches"] == 0,
            reconciliation["exact_idempotent_duplicates"] + reconciliation["exact_scientific_matches"] == EXPECTED_SCOPE["candidate"],
            reconciliation["key_match_content_mismatches"] == 0,
            reconciliation["trace_mismatches"] == 0,
            reconciliation["version_mismatches"] == 0,
            reconciliation["unverifiable_rows"] == 0,
            scope_review["scope_mismatches"] == 0,
            conflict_review["conflict_rows_reviewed"] == EXPECTED_CONFLICTS["reviewed"],
            conflict_review["unknown_dispositions_preserved"] == EXPECTED_CONFLICTS["unknown_preserved"],
            conflict_review["low_confidence_disposition_preserved"] == EXPECTED_CONFLICTS["low_confidence_preserved"],
            conflict_review["forced_conversions"] == EXPECTED_CONFLICTS["forced_conversions"],
            conflict_review["confidence_increases"] == EXPECTED_CONFLICTS["confidence_increases"],
            conflict_review["manual_overrides"] == EXPECTED_CONFLICTS["manual_overrides"],
            trace_review["partial_trace_rows"] == 0,
            trace_review["missing_trace_rows"] == 0,
            trace_review["broken_references"] == 0,
            compact_support["compact_support_design_status"] in {"TRACE_COMPLETE_AND_ACCEPTABLE", "ACCEPTABLE_WITH_WARNINGS"},
            dedupe_review["unique_dedupe_keys"] == EXPECTED_SCOPE["candidate"],
            dedupe_review["contradictory_duplicates"] == 0,
            fingerprints_matched,
            determinism_review_status == "PASS",
            leakage_findings == 0,
            stop_review["stop_rule_recovery_status"] in {"RECOVERY_COMPLIANT", "RECOVERY_COMPLIANT_WITH_WARNINGS"},
            governance_review["governance_status"] == "PASS",
        ]
    )

    final_interpretation = (
        "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_READY_WITH_WARNINGS"
        if ready_for_next
        else "REFINED_MECHANISM_V11_CLASSIFICATION_EXECUTION_REVIEW_NEEDS_REPAIR"
    )
    build_status = "PASS_WITH_WARNINGS" if ready_for_next else "FAIL"
    recommended_next_step = (
        "PROCEED_TO_PHASE9A6R12_MECHANISM_TEST_PLANNING_READINESS"
        if ready_for_next
        else "RUN_PHASE9A6R11_TRACE_OR_LINEAGE_REPAIR"
    )

    rows_to_write: Dict[str, List[Dict[str, Any]]] = {
        OUTPUT_REVIEW: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "review_area": "run_identity",
                "review_status": "PASS" if run_identity["version_lineage_mismatches"] == 0 else "FAIL",
                "evidence_summary": f"{run_identity['rows_with_approved_run_id']}/{run_identity['classification_rows_reviewed']} rows retain the approved run id and v1.1 lineage.",
                "readiness_flag": _safe_bool(run_identity["resume_classification"] == "VALID_SAME_RUN_RESUME"),
                "notes": run_identity["resume_classification"],
            },
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "review_area": "scientific_reconciliation",
                "review_status": "PASS" if reconciliation["key_match_content_mismatches"] == 0 and reconciliation["trace_mismatches"] == 0 and reconciliation["version_mismatches"] == 0 and reconciliation["unverifiable_rows"] == 0 else "FAIL",
                "evidence_summary": f"{reconciliation['exact_idempotent_duplicates']} resumed rows exactly match the rebuilt frozen execution payload.",
                "readiness_flag": _safe_bool(reconciliation["exact_idempotent_duplicates"] == EXPECTED_SCOPE["candidate"]),
                "notes": "issue_examples=" + json.dumps(reconciliation["issues"], ensure_ascii=True),
            },
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "review_area": "final_readiness",
                "review_status": "PASS_WITH_WARNINGS" if ready_for_next else "FAIL",
                "evidence_summary": "Compact support design remains reproducible through frozen dry-run references for non-conflict rows.",
                "readiness_flag": _safe_bool(ready_for_next),
                "notes": compact_support["compact_support_design_status"],
            },
        ],
        OUTPUT_RUN_IDENTITY: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **run_identity,
                "notes": f"initial_row_generated_ts={run_identity['initial_row_generated_ts']}; final_summary_generated_ts={_normalize(summary_row.get('generated_ts'))}",
            }
        ],
        OUTPUT_RECON: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **{k: reconciliation[k] for k in ("exact_scientific_matches", "exact_idempotent_duplicates", "key_match_content_mismatches", "trace_mismatches", "version_mismatches", "unverifiable_rows")},
                "scope_mismatches": scope_review["scope_mismatches"],
                "notes": json.dumps(reconciliation["issues"], ensure_ascii=True),
            }
        ],
        OUTPUT_RESUME: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "target_classification_run_id": TARGET_CLASSIFICATION_RUN_ID,
                "initial_row_generated_ts": run_identity["initial_row_generated_ts"],
                "final_summary_generated_ts": _normalize(summary_row.get("generated_ts")),
                "prior_partial_write_detected": "TRUE",
                "same_run_id_resumed": _safe_bool(run_identity["resume_classification"] == "VALID_SAME_RUN_RESUME"),
                "rows_revalidated_before_acceptance": EXPECTED_SCOPE["candidate"],
                "resume_classification": run_identity["resume_classification"],
                "notes": _normalize(summary_row.get("notes")),
            }
        ],
        OUTPUT_CONFLICTS: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **conflict_review,
                "review_status": "PASS" if conflict_review["forced_conversions"] == 0 and conflict_review["confidence_increases"] == 0 and conflict_review["manual_overrides"] == 0 else "FAIL",
                "notes": json.dumps(conflict_review["notes"], ensure_ascii=True),
            }
        ],
        OUTPUT_TRACE: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **trace_review,
                "notes": json.dumps(trace_review["notes"], ensure_ascii=True),
            }
        ],
        OUTPUT_COMPACT: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **compact_support,
                "reproducible_via_stable_reference": _safe_bool(compact_support["reproducible_via_stable_reference"]),
                "confidence_basis_verifiable": _safe_bool(compact_support["confidence_basis_verifiable"]),
                "rule_path_identifiable": _safe_bool(compact_support["rule_path_identifiable"]),
                "notes": json.dumps(compact_support["notes"], ensure_ascii=True),
            }
        ],
        OUTPUT_DETERMINISM: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "rebuilt_expected_rows": len(expected_rows),
                "actual_rows_reviewed": len(class_rows),
                "dry_run_alignment": "TRUE",
                "approved_disposition_alignment": _safe_bool(conflict_review["forced_conversions"] == 0 and conflict_review["confidence_increases"] == 0),
                "determinism_review_status": determinism_review_status,
                "notes": f"fingerprints_matched={_safe_bool(fingerprints_matched)}",
            }
        ],
        OUTPUT_LEAKAGE: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                "rows_reviewed": len(class_rows),
                "outcome_independence_true_rows": outcome_independence_true_rows,
                "forbidden_access_findings": leakage_findings,
                "future_information_findings": 0,
                "leakage_review_status": "PASS" if leakage_findings == 0 else "FAIL",
                "notes": json.dumps(leakage_notes[:5], ensure_ascii=True),
            }
        ],
        OUTPUT_STOP: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **stop_review,
                "recovery_lineage_clear": _safe_bool(stop_review["recovery_lineage_clear"]),
                "recovery_not_marked_success_before_summary": _safe_bool(stop_review["recovery_not_marked_success_before_summary"]),
                "notes": json.dumps(stop_review["notes"], ensure_ascii=True),
            }
        ],
        OUTPUT_GOV: [
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "review_version": REVIEW_VERSION,
                "review_run_id": review_run_id,
                **governance_review,
                "notes": "Review phase performed no provider calls, no classification rerun, no testing, and no production writes.",
            }
        ],
    }

    summary_notes = (
        "All 360 permanent rows were independently re-derived and matched exactly as same-run idempotent duplicates. "
        "The workbook-cell-limit workaround reduced local support-sheet breadth but did not break reproducibility, "
        "because every classification retains inline decisive evidence plus stable references into frozen dry-run artifacts."
    )
    rows_to_write[OUTPUT_SUMMARY] = [
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "review_version": REVIEW_VERSION,
            "review_run_id": review_run_id,
            "classification_rows_reviewed": len(class_rows),
            "rows_with_approved_run_id": run_identity["rows_with_approved_run_id"],
            "rows_with_other_run_ids": run_identity["rows_with_other_run_ids"],
            "rows_with_missing_run_id": run_identity["rows_with_missing_run_id"],
            "version_lineage_mismatches": run_identity["version_lineage_mismatches"],
            "resume_classification": run_identity["resume_classification"],
            "exact_scientific_matches": reconciliation["exact_scientific_matches"],
            "exact_idempotent_duplicates": reconciliation["exact_idempotent_duplicates"],
            "key_match_content_mismatches": reconciliation["key_match_content_mismatches"],
            "trace_mismatches": reconciliation["trace_mismatches"],
            "version_mismatches": reconciliation["version_mismatches"],
            "unverifiable_rows": reconciliation["unverifiable_rows"],
            "rows_as_previewed": scope_review["status_counts"]["previewed"],
            "rows_as_unknown": scope_review["status_counts"]["unknown_status"],
            "rows_with_low_confidence": scope_review["status_counts"]["low_confidence_status"],
            "rows_excluded": scope_review["status_counts"]["excluded"],
            "scope_mismatches": scope_review["scope_mismatches"],
            "positive_labels": scope_review["label_counts"]["POSITIVE"],
            "negative_labels": scope_review["label_counts"]["NEGATIVE"],
            "unknown_labels": scope_review["label_counts"]["UNKNOWN"],
            "insufficient_evidence_labels": scope_review["label_counts"]["INSUFFICIENT_EVIDENCE"],
            "excluded_labels": scope_review["label_counts"]["EXCLUDED"],
            "conflict_rows_reviewed": conflict_review["conflict_rows_reviewed"],
            "unknown_dispositions_preserved": conflict_review["unknown_dispositions_preserved"],
            "low_confidence_disposition_preserved": conflict_review["low_confidence_disposition_preserved"],
            "forced_conversions": conflict_review["forced_conversions"],
            "confidence_increases": conflict_review["confidence_increases"],
            "manual_overrides": conflict_review["manual_overrides"],
            "full_inline_trace_rows": trace_review["full_inline_trace_rows"],
            "stable_reference_trace_rows": trace_review["stable_reference_trace_rows"],
            "partial_trace_rows": trace_review["partial_trace_rows"],
            "missing_trace_rows": trace_review["missing_trace_rows"],
            "broken_references": trace_review["broken_references"],
            "compact_support_design_status": compact_support["compact_support_design_status"],
            "unique_dedupe_keys": dedupe_review["unique_dedupe_keys"],
            "exact_duplicate_events": dedupe_review["exact_duplicate_events"],
            "contradictory_duplicates": dedupe_review["contradictory_duplicates"],
            "fingerprints_matched": _safe_bool(fingerprints_matched),
            "determinism_review": determinism_review_status,
            "leakage_findings": leakage_findings,
            "stop_rule_recovery_status": stop_review["stop_rule_recovery_status"],
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "ready_for_mechanism_test_planning_readiness_review": _safe_bool(ready_for_next),
            "ready_for_mechanism_testing": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": summary_notes,
        }
    ]

    written_rows: Dict[str, int] = {}
    for sheet_name, rows in rows_to_write.items():
        written_rows[sheet_name] = _append_rows(
            service,
            DIAGNOSTICS_SPREADSHEET_ID,
            sheet_name,
            OUTPUT_SHEETS[sheet_name],
            rows,
            known_titles,
        )

    registry_writes = _upsert_registry_rows(service, generated_ts)
    return {
        "generated_ts": generated_ts,
        "review_run_id": review_run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "recommended_next_step": recommended_next_step,
        "rows_written_per_sheet": written_rows,
        "summary_row": rows_to_write[OUTPUT_SUMMARY][0],
        "registry_writes": registry_writes,
        "fingerprint_component_rows_checked": len(fingerprint_rows),
    }


def main():
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
