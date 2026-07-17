import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_reaction_canonical_outcome_validation_v0 import (
    _bool,
    _ensure_sheet_minimal,
    _fmt,
    _int,
    _rate,
    _safe_rows,
    _sheet_titles,
    _split_tokens,
    _trust_rank,
)
from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_market_reaction_canonical_mapping_repair_0.1"
REPAIR_VERSION = "market_reaction_canonical_mapping_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M2R"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_CANONICAL_MAPPING_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = [
    "Evaluation_Rows",
    "Outcome_Ledger",
    "MR_ProviderRuns",
    "Event",
    "Config",
]

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Accuracy_Row_Remap_Preview",
    "Market_Reaction_Canonical_Validation",
    "Market_Reaction_Canonical_Validation_Summary",
    "Controlled_Accuracy_Evaluation",
]

CRITICAL_MAIN_SHEETS = {"Evaluation_Rows", "Outcome_Ledger", "MR_ProviderRuns", "Event"}
CRITICAL_DIAG_SHEETS = {
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Accuracy_Row_Remap_Preview",
    "Market_Reaction_Canonical_Validation_Summary",
    "Controlled_Accuracy_Evaluation",
}

OUTPUT_REPAIR = "Market_Reaction_Canonical_Mapping_Repair"
OUTPUT_ROW_AUDIT = "Market_Reaction_Accuracy_Row_Mapping_Audit"
OUTPUT_FAILURE = "Market_Reaction_Canonical_Mapping_Failure_Audit"
OUTPUT_SOURCE_GAP = "Market_Reaction_Source_Coverage_Gap_Audit"
OUTPUT_PLAN = "Market_Reaction_Canonical_Mapping_Repair_Plan"
OUTPUT_READINESS = "Market_Reaction_Canonical_Mapping_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Canonical_Mapping_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Canonical_Mapping_Repair_Summary"

REPAIR_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "repair_area",
    "source_sheet",
    "rows_checked",
    "issues_found",
    "repair_status",
    "repair_conclusion",
    "recommended_action",
    "notes",
]

ROW_AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "country",
    "release_ts",
    "current_remap_status",
    "current_canonical_outcome_id",
    "current_trust_level",
    "candidate_outcome_count",
    "candidate_batch_count",
    "candidate_event_count",
    "candidate_trust_levels",
    "candidate_batch_ids",
    "mapping_failure_class",
    "mapping_root_cause",
    "deterministic_repair_available",
    "proposed_mapping_rule",
    "projected_remap_status",
    "projected_strict_ready",
    "projected_diagnostic_ready",
    "projected_unusable",
    "notes",
]

FAILURE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "failure_type",
    "failure_classification",
    "root_cause",
    "candidate_outcome_count",
    "candidate_trust_summary",
    "canonical_outcome_id",
    "canonical_trust_level",
    "source_rows_available",
    "source_rows_used",
    "fallback_reason",
    "source_agreement_class",
    "repair_action",
    "expected_after_mapping_repair",
    "blocks_strict_accuracy",
    "blocks_diagnostic_accuracy",
    "notes",
]

SOURCE_GAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "canonical_outcome_id",
    "country",
    "release_ts",
    "event_id",
    "batch_id",
    "affected_accuracy_rows",
    "affected_sessions",
    "provider_sources_available",
    "source_rows_available",
    "source_rows_used",
    "canonical_source",
    "fallback_reason",
    "source_agreement_class",
    "window_confidence",
    "outcome_confidence",
    "trust_level",
    "source_coverage_gap_class",
    "recommended_repair_type",
    "notes",
]

PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "plan_step_id",
    "plan_step",
    "target_failure_class",
    "affected_rows",
    "proposed_change",
    "implementation_scope",
    "canonical_architecture_changed",
    "market_reaction_values_changed",
    "expected_strict_ready_delta",
    "expected_diagnostic_ready_delta",
    "expected_unusable_delta",
    "risk",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "readiness_check_id",
    "readiness_check",
    "status",
    "blocking_issue",
    "required_before_next_phase",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "build_status",
    "final_interpretation",
    "accuracy_rows_checked",
    "current_strict_ready_rows",
    "current_diagnostic_ready_rows",
    "current_ambiguous_rows",
    "current_unusable_rows",
    "ambiguous_rows_fully_classified",
    "unusable_rows_root_caused",
    "primary_mapping_failure",
    "primary_source_coverage_gap",
    "estimated_strict_ready_rows_after_repair",
    "estimated_diagnostic_ready_rows_after_repair",
    "estimated_still_unusable_rows_after_repair",
    "diagnostic_ready_delta_after_repair",
    "strict_ready_delta_after_repair",
    "remaining_blocking_issues",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "metric_values_recalculated",
    "market_reaction_values_modified",
    "canonical_outcomes_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_mapping_repair_implementation",
    "ready_for_corrected_accuracy_re_evaluation_design",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_canonical_mapping_repair_v0_{compact}"


def _base(generated_ts: str, repair_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "repair_version": REPAIR_VERSION,
        "repair_run_id": repair_run_id,
    }


def _candidate_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return _norm(row.get("country")), _norm(row.get("release_ts"))


def _candidate_signature(row: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        _norm(row.get("trust_level")),
        _norm(row.get("canonical_realized_pips")),
        _norm(row.get("canonical_realized_direction")),
        _norm(row.get("canonical_realized_strength")),
    )


def _index_by_country_release(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _candidate_key(row)
        if key != ("", ""):
            index[key].append(row)
    return index


def _canonical_by_id(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("canonical_outcome_id")): row for row in rows}


def _event_row_indexes(rows: Sequence[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str], Set[str]], Dict[Tuple[str, str], Set[str]]]:
    event_ids: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    batch_ids: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if key == ("", ""):
            continue
        event_id = _norm(row.get("event_id"))
        batch_id = _norm(row.get("batch_id"))
        if event_id:
            event_ids[key].add(event_id)
        if batch_id:
            batch_ids[key].add(batch_id)
    return event_ids, batch_ids


def _status_from_trust(trust_level: str) -> Tuple[str, bool, bool, bool]:
    trust = _norm(trust_level)
    if trust == "HIGH_TRUST":
        return "STRICT_READY_AFTER_MAPPING_REPAIR", True, True, False
    if trust == "MEDIUM_TRUST":
        return "DIAGNOSTIC_READY_AFTER_MAPPING_REPAIR", False, True, False
    if trust == "LOW_TRUST":
        return "LOW_TRUST_REVIEW_REQUIRED", False, False, False
    return "UNUSABLE_AFTER_MAPPING_REPAIR", False, False, True


def _classify_ambiguous(candidates: Sequence[Dict[str, Any]]) -> Tuple[str, str, str, str, bool, str, str, bool, bool, bool]:
    if not candidates:
        return (
            "missing_canonical_candidate",
            "release_key_has_no_canonical_outcome",
            "Create deterministic canonical mapping reference for this release.",
            "REMAP_MISSING_AFTER_REPAIR",
            False,
            "No candidate exists.",
            "FALSE",
            False,
            False,
            True,
        )
    trust_counts = Counter(_norm(row.get("trust_level")) for row in candidates)
    batch_ids = {_norm(row.get("batch_id")) for row in candidates if _norm(row.get("batch_id"))}
    signatures = {_candidate_signature(row) for row in candidates}
    best_rank = max(_trust_rank(row) for row in candidates)
    best = [row for row in candidates if _trust_rank(row) == best_rank]
    selected = best[0] if best else candidates[0]
    projected, strict, diagnostic, unusable = _status_from_trust(_norm(selected.get("trust_level")))
    if len(batch_ids) == 1 and len(signatures) == 1:
        failure_class = "multiple_event_outcomes_same_batch_identical_outcome"
        root_cause = "accuracy rows carry release-level key but not canonical event/member key; all candidates share batch and outcome values."
        repair_rule = "Map release-level controlled accuracy rows to a deterministic batch-level canonical representative when all candidate outcomes share batch_id and outcome signature."
        deterministic = True
    elif len(batch_ids) == 1:
        failure_class = "multiple_event_outcomes_same_batch_release_key_only"
        root_cause = "accuracy rows carry release-level key but not canonical event/member key; candidates share batch_id but not all outcome signatures."
        repair_rule = "Use Event batch_id plus a frozen representative-outcome rule; require review when candidate outcomes differ."
        deterministic = len(best) == 1
    elif trust_counts.get("UNUSABLE", 0) == len(candidates):
        failure_class = "release_key_multiple_unusable_candidates"
        root_cause = "historical release-level key maps to multiple event outcomes, and source coverage makes every candidate unusable."
        repair_rule = "Mapping can classify the row, but source coverage repair is required before strict/diagnostic use."
        deterministic = False
    else:
        failure_class = "canonical_outcome_selection_ambiguity"
        root_cause = "historical release-level key maps to multiple canonical outcomes without a unique event, batch, or trust-based selection."
        repair_rule = "Add deterministic event_id/batch_id bridge from controlled accuracy row to canonical_outcome_id."
        deterministic = len(best) == 1
    if projected == "UNUSABLE_AFTER_MAPPING_REPAIR":
        deterministic = deterministic and len(signatures) == 1
    return (
        failure_class,
        root_cause,
        repair_rule,
        projected,
        deterministic,
        _norm(selected.get("canonical_outcome_id")),
        "TRUE" if deterministic else "FALSE",
        strict,
        diagnostic,
        unusable,
    )


def _classify_unusable(canonical: Dict[str, Any]) -> Tuple[str, str, str, str]:
    source_rows_available = _int(canonical.get("source_rows_available"))
    source_rows_used = _int(canonical.get("source_rows_used"))
    fallback_reason = _norm(canonical.get("fallback_reason"))
    window_confidence = _norm(canonical.get("window_confidence"))
    if fallback_reason == "no_valid_source" and source_rows_available == 0:
        return "missing_source_coverage", "No market-data source rows exist for the canonical outcome.", "SOURCE_COVERAGE_REPAIR", "source_coverage"
    if fallback_reason == "no_valid_source" and source_rows_used == 0:
        return "fallback_exhaustion_no_valid_source", "Candidate provider rows exist but none passed canonical source/window validity.", "SOURCE_COVERAGE_REPAIR", "source_coverage"
    if window_confidence == "UNUSABLE":
        return "invalid_or_unavailable_window", "Canonical source exists but the event-relative window is unusable.", "WINDOW_POLICY_REPAIR", "window_construction"
    return "unusable_unclassified", "Canonical outcome is unusable but the compact fields do not isolate a narrower cause.", "MANUAL_REVIEW", "implementation_logic"


def _governance_rows(generated_ts: str, repair_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("metric_values_recalculated", 0, 0),
        ("market_reaction_values_modified", 0, 0),
        ("canonical_outcomes_modified", 0, 0),
        ("evaluation_rows_written", 0, 0),
        ("outcome_ledger_written", 0, 0),
        ("production_sheet_write_count", 0, 0),
        ("production_behavior_change_count", 0, 0),
        ("routing_changes", "FALSE", "FALSE"),
        ("weighting_changes", "FALSE", "FALSE"),
        ("calibration_changes", "FALSE", "FALSE"),
        ("ensemble_changes", "FALSE", "FALSE"),
    ]
    rows = []
    for check, expected, actual in checks:
        rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "check_id": f"CHK_{check.upper()}",
                "check_name": check,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Mapping repair audit only; no outcomes, evaluation rows, ledgers, or production sheets modified.",
            }
        )
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet_minimal(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS, 1)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_CANONICAL_MAPPING_REPAIR", OUTPUT_REPAIR, "market_reaction_canonical_mapping_repair"),
        ("MARKET_REACTION_ACCURACY_ROW_MAPPING_AUDIT", OUTPUT_ROW_AUDIT, "market_reaction_accuracy_row_mapping_audit"),
        ("MARKET_REACTION_CANONICAL_MAPPING_FAILURE_AUDIT", OUTPUT_FAILURE, "market_reaction_canonical_mapping_failure_audit"),
        ("MARKET_REACTION_SOURCE_COVERAGE_GAP_AUDIT", OUTPUT_SOURCE_GAP, "market_reaction_source_coverage_gap_audit"),
        ("MARKET_REACTION_CANONICAL_MAPPING_REPAIR_PLAN", OUTPUT_PLAN, "market_reaction_canonical_mapping_repair_plan"),
        ("MARKET_REACTION_CANONICAL_MAPPING_READINESS", OUTPUT_READINESS, "market_reaction_canonical_mapping_readiness"),
        ("MARKET_REACTION_CANONICAL_MAPPING_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_canonical_mapping_governance"),
        ("MARKET_REACTION_CANONICAL_MAPPING_REPAIR_SUMMARY", OUTPUT_SUMMARY, "market_reaction_canonical_mapping_repair_summary"),
    ]
    updates = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = logical_id.upper()
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-5M2R focused canonical mapping repair audit; read-only.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M2R canonical mapping repair audit.")
    return parser.parse_args(argv)


def build_market_reaction_canonical_mapping_repair_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    repair_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    diag_titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _sheet_titles(service, MAIN_SPREADSHEET_ID)
    missing_diag: List[str] = []
    missing_main: List[str] = []
    diag_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_diag) for sheet in DIAG_INPUT_SHEETS}
    main_inputs = {sheet: _safe_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, missing_main) for sheet in MAIN_INPUT_SHEETS}
    missing_critical = sorted(
        [f"DIAGNOSTICS:{sheet}" for sheet in missing_diag if sheet in CRITICAL_DIAG_SHEETS]
        + [f"MAIN:{sheet}" for sheet in missing_main if sheet in CRITICAL_MAIN_SHEETS]
    )
    if missing_critical:
        raise RuntimeError(f"Missing critical Phase 9A-5M2R inputs: {missing_critical}")

    validation_summary = diag_inputs["Market_Reaction_Canonical_Validation_Summary"][-1] if diag_inputs["Market_Reaction_Canonical_Validation_Summary"] else {}
    if _norm(validation_summary.get("final_interpretation")) not in {
        "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_NEEDS_REPAIR",
        "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_READY_WITH_WARNINGS",
        "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_READY",
    }:
        raise RuntimeError("Phase 9A-5M3 validation summary is missing or not in a repair/design-ready state.")

    outcomes = diag_inputs["Market_Reaction_Canonical_Outcomes"]
    matching = diag_inputs["Market_Reaction_Canonical_Outcome_Matching"]
    remap = diag_inputs["Market_Reaction_Accuracy_Row_Remap_Preview"]
    controlled_accuracy = diag_inputs["Controlled_Accuracy_Evaluation"]
    evaluation_rows = main_inputs["Evaluation_Rows"]
    outcome_ledger = main_inputs["Outcome_Ledger"]
    mr_provider_runs = main_inputs["MR_ProviderRuns"]
    event_rows = main_inputs["Event"]

    by_release = _index_by_country_release(outcomes)
    by_id = _canonical_by_id(outcomes)
    event_ids_by_release, batch_ids_by_release = _event_row_indexes(event_rows)
    evaluation_event_ids, evaluation_batch_ids = _event_row_indexes(evaluation_rows)
    ledger_event_ids, ledger_batch_ids = _event_row_indexes(outcome_ledger)
    mr_events, _ = _event_row_indexes(mr_provider_runs)
    matching_by_id = {_norm(row.get("canonical_outcome_id")): row for row in matching}

    row_audit_rows: List[Dict[str, Any]] = []
    failure_rows: List[Dict[str, Any]] = []
    source_gap_by_id: Dict[str, Dict[str, Any]] = {}
    projected_counts = Counter()
    failure_classes = Counter()
    source_gap_classes = Counter()
    ambiguous_classified = 0
    unusable_root_caused = 0

    for row in remap:
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        candidates = by_release.get(key, [])
        current_status = _norm(row.get("remap_status"))
        current_cid = _norm(row.get("canonical_outcome_id"))
        current_canonical = by_id.get(current_cid, {})
        candidate_trusts = Counter(_norm(candidate.get("trust_level")) for candidate in candidates)
        candidate_batches = {_norm(candidate.get("batch_id")) for candidate in candidates if _norm(candidate.get("batch_id"))}
        candidate_events = {_norm(candidate.get("event_id")) for candidate in candidates if _norm(candidate.get("event_id"))}
        deterministic = True
        proposed_rule = "Already strict-ready; no mapping repair needed."
        root_cause = "none"
        failure_class = "mapped_strict_ready"
        projected_status = "STRICT_READY_AFTER_MAPPING_REPAIR"
        strict = True
        diagnostic = True
        unusable = False
        selected_cid = current_cid

        if current_status == "REMAP_AMBIGUOUS":
            (
                failure_class,
                root_cause,
                proposed_rule,
                projected_status,
                deterministic,
                selected_cid,
                _deterministic_text,
                strict,
                diagnostic,
                unusable,
            ) = _classify_ambiguous(candidates)
            ambiguous_classified += 1
        elif current_status == "REMAP_UNUSABLE":
            failure_class, root_cause, repair_type, gap_class = _classify_unusable(current_canonical)
            proposed_rule = "Mapping layer can point to this canonical outcome, but source coverage/window validity must be repaired before use."
            projected_status = "UNUSABLE_AFTER_MAPPING_REPAIR"
            deterministic = True
            strict = False
            diagnostic = False
            unusable = True
            unusable_root_caused += 1
            source_gap_classes[gap_class] += 1
            repair_action = repair_type
        elif current_status == "REMAP_DIAGNOSTIC_ONLY":
            failure_class = "mapped_diagnostic_only"
            root_cause = "canonical outcome is medium-trust and intentionally excluded from strict accuracy."
            projected_status = "DIAGNOSTIC_READY_AFTER_MAPPING_REPAIR"
            strict = False
            diagnostic = True
            unusable = False
        elif current_status == "REMAP_LOW_TRUST":
            failure_class = "mapped_low_trust"
            root_cause = "canonical outcome is low-trust and requires review before evaluation use."
            projected_status = "LOW_TRUST_REVIEW_REQUIRED"
            strict = False
            diagnostic = False
            unusable = False
        elif current_status == "REMAP_MISSING":
            failure_class = "missing_canonical_mapping"
            root_cause = "controlled accuracy row has no canonical outcome candidate."
            proposed_rule = "Add deterministic canonical matching key or exclude from corrected evaluation."
            projected_status = "MISSING_AFTER_MAPPING_REPAIR"
            deterministic = False
            strict = False
            diagnostic = False
            unusable = True

        projected_counts[projected_status] += 1
        failure_classes[failure_class] += 1
        if current_status in {"REMAP_AMBIGUOUS", "REMAP_UNUSABLE", "REMAP_MISSING", "REMAP_LOW_TRUST"}:
            canonical_for_failure = by_id.get(selected_cid or current_cid, current_canonical)
            if current_status == "REMAP_UNUSABLE":
                repair_action = _classify_unusable(canonical_for_failure)[2]
            else:
                repair_action = "MAPPING_RULE_REPAIR" if current_status == "REMAP_AMBIGUOUS" else "MATCHING_REPAIR"
            failure_rows.append(
                {
                    **_base(generated_ts, repair_run_id),
                    "accuracy_row_id": row.get("accuracy_row_id"),
                    "experiment_id": row.get("experiment_id"),
                    "session_id": row.get("session_id"),
                    "provider": row.get("provider"),
                    "pack_level": row.get("pack_level"),
                    "failure_type": current_status,
                    "failure_classification": failure_class,
                    "root_cause": root_cause,
                    "candidate_outcome_count": len(candidates),
                    "candidate_trust_summary": "|".join(f"{k}:{v}" for k, v in sorted(candidate_trusts.items())),
                    "canonical_outcome_id": selected_cid or current_cid,
                    "canonical_trust_level": canonical_for_failure.get("trust_level"),
                    "source_rows_available": canonical_for_failure.get("source_rows_available"),
                    "source_rows_used": canonical_for_failure.get("source_rows_used"),
                    "fallback_reason": canonical_for_failure.get("fallback_reason"),
                    "source_agreement_class": canonical_for_failure.get("source_agreement_class"),
                    "repair_action": repair_action,
                    "expected_after_mapping_repair": projected_status,
                    "blocks_strict_accuracy": "TRUE" if not strict else "FALSE",
                    "blocks_diagnostic_accuracy": "TRUE" if not diagnostic else "FALSE",
                    "notes": "Failure classified without changing canonical outcomes or recalculating accuracy.",
                }
            )

        if current_status in {"REMAP_UNUSABLE", "REMAP_AMBIGUOUS"}:
            selected = by_id.get(selected_cid or current_cid, current_canonical)
            if _norm(selected.get("trust_level")) == "UNUSABLE" and selected:
                cid = _norm(selected.get("canonical_outcome_id"))
                gap_class, gap_reason, repair_type, source_gap = _classify_unusable(selected)
                entry = source_gap_by_id.setdefault(
                    cid,
                    {
                        **_base(generated_ts, repair_run_id),
                        "canonical_outcome_id": cid,
                        "country": selected.get("country"),
                        "release_ts": selected.get("release_ts"),
                        "event_id": selected.get("event_id"),
                        "batch_id": selected.get("batch_id"),
                        "affected_accuracy_rows": 0,
                        "affected_sessions": set(),
                        "provider_sources_available": selected.get("provider_sources_available"),
                        "source_rows_available": selected.get("source_rows_available"),
                        "source_rows_used": selected.get("source_rows_used"),
                        "canonical_source": selected.get("canonical_source"),
                        "fallback_reason": selected.get("fallback_reason"),
                        "source_agreement_class": selected.get("source_agreement_class"),
                        "window_confidence": selected.get("window_confidence"),
                        "outcome_confidence": selected.get("outcome_confidence"),
                        "trust_level": selected.get("trust_level"),
                        "source_coverage_gap_class": gap_class,
                        "recommended_repair_type": repair_type,
                        "notes": gap_reason,
                    },
                )
                entry["affected_accuracy_rows"] += 1
                entry["affected_sessions"].add(_norm(row.get("session_id")))

        row_audit_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": row.get("accuracy_row_id"),
                "experiment_id": row.get("experiment_id"),
                "session_id": row.get("session_id"),
                "provider": row.get("provider"),
                "pack_level": row.get("pack_level"),
                "country": row.get("country"),
                "release_ts": row.get("release_ts"),
                "current_remap_status": current_status,
                "current_canonical_outcome_id": current_cid,
                "current_trust_level": row.get("canonical_trust_level"),
                "candidate_outcome_count": len(candidates),
                "candidate_batch_count": len(candidate_batches),
                "candidate_event_count": len(candidate_events),
                "candidate_trust_levels": "|".join(f"{k}:{v}" for k, v in sorted(candidate_trusts.items())),
                "candidate_batch_ids": "|".join(sorted(candidate_batches)),
                "mapping_failure_class": failure_class,
                "mapping_root_cause": root_cause,
                "deterministic_repair_available": "TRUE" if deterministic else "FALSE",
                "proposed_mapping_rule": proposed_rule,
                "projected_remap_status": projected_status,
                "projected_strict_ready": "TRUE" if strict else "FALSE",
                "projected_diagnostic_ready": "TRUE" if diagnostic else "FALSE",
                "projected_unusable": "TRUE" if unusable else "FALSE",
                "notes": "Mapping-only projection; no accuracy fields recalculated.",
            }
        )

    source_gap_rows = []
    for row in source_gap_by_id.values():
        copy = dict(row)
        copy["affected_sessions"] = "|".join(sorted(copy["affected_sessions"]))
        source_gap_rows.append(copy)

    current_counts = Counter(_norm(row.get("remap_status")) for row in remap)
    current_strict = current_counts["REMAP_STRICT_READY"]
    current_diagnostic_total = current_counts["REMAP_STRICT_READY"] + current_counts["REMAP_DIAGNOSTIC_ONLY"]
    estimated_strict = sum(1 for row in row_audit_rows if row["projected_strict_ready"] == "TRUE")
    estimated_diagnostic = sum(1 for row in row_audit_rows if row["projected_diagnostic_ready"] == "TRUE")
    estimated_unusable = sum(1 for row in row_audit_rows if row["projected_unusable"] == "TRUE")
    primary_mapping_failure = failure_classes.most_common(1)[0][0] if failure_classes else "none"
    primary_source_gap = Counter(row["source_coverage_gap_class"] for row in source_gap_rows).most_common(1)
    primary_source_gap_value = primary_source_gap[0][0] if primary_source_gap else "none"

    repair_rows = []
    repair_specs = [
        (
            "mapping_failure_classification",
            OUTPUT_ROW_AUDIT,
            len(row_audit_rows),
            current_counts["REMAP_AMBIGUOUS"] + current_counts["REMAP_UNUSABLE"],
            "PASS_WITH_WARNINGS",
            "All current ambiguous and unusable controlled-accuracy rows received deterministic failure classifications.",
            "PROCEED_TO_PHASE9A5M2RR_CANONICAL_MAPPING_IMPLEMENTATION_REPAIR",
            f"Ambiguous classified={ambiguous_classified}; unusable root-caused={unusable_root_caused}.",
        ),
        (
            "matching_hierarchy_validation",
            OUTPUT_ROW_AUDIT,
            len(row_audit_rows),
            current_counts["REMAP_AMBIGUOUS"],
            "NEEDS_REPAIR" if current_counts["REMAP_AMBIGUOUS"] else "PASS",
            "Release-level historical keys are insufficient for event/member canonical remapping.",
            "PROCEED_TO_PHASE9A5M2RR_CANONICAL_MAPPING_IMPLEMENTATION_REPAIR",
            "Add a deterministic bridge from controlled accuracy row/session/release to canonical outcome representative.",
        ),
        (
            "source_coverage_gap",
            OUTPUT_SOURCE_GAP,
            len(source_gap_rows),
            sum(_int(row["affected_accuracy_rows"]) for row in source_gap_rows),
            "NEEDS_REPAIR" if source_gap_rows else "PASS",
            "Most strict-readiness loss comes from no valid source selected, not from canonical ID construction.",
            "PROCEED_TO_PHASE9A5M2RR_CANONICAL_MAPPING_IMPLEMENTATION_REPAIR",
            "Mapping repair cannot convert no-valid-source outcomes into strict-ready outcomes.",
        ),
        (
            "repair_impact_projection",
            OUTPUT_SUMMARY,
            len(remap),
            estimated_unusable,
            "PASS_WITH_WARNINGS",
            "Mapping repair improves diagnostic coverage but strict-ready rows remain limited without source coverage repair.",
            "PROCEED_TO_PHASE9A5M2RR_CANONICAL_MAPPING_IMPLEMENTATION_REPAIR",
            f"Estimated strict={estimated_strict}; diagnostic={estimated_diagnostic}; still unusable={estimated_unusable}.",
        ),
    ]
    for area, sheet, checked, issues, status, conclusion, action, notes in repair_specs:
        repair_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "repair_area": area,
                "source_sheet": sheet,
                "rows_checked": checked,
                "issues_found": issues,
                "repair_status": status,
                "repair_conclusion": conclusion,
                "recommended_action": action,
                "notes": notes,
            }
        )

    plan_specs = [
        (
            "PLAN_01",
            "Create controlled_accuracy_to_canonical_outcome mapping bridge.",
            "release_key_level_ambiguity",
            current_counts["REMAP_AMBIGUOUS"],
            "Materialize a deterministic preview/implementation mapping keyed by accuracy_row_id, country, release_ts, session_id, batch candidate set, and canonical representative rule.",
            "diagnostics_mapping_layer_only",
            0,
            estimated_diagnostic - current_diagnostic_total,
            0,
            "Medium: prevents accidental event-level over-selection but does not fix source coverage.",
        ),
        (
            "PLAN_02",
            "Use batch-level representative only when candidate outcomes share batch and outcome signature.",
            "multiple_event_outcomes_same_batch_identical_outcome",
            failure_classes["multiple_event_outcomes_same_batch_identical_outcome"],
            "Allow deterministic representative mapping for identical candidate outcome signatures; otherwise require review.",
            "mapping_rule_only",
            0,
            projected_counts["DIAGNOSTIC_READY_AFTER_MAPPING_REPAIR"],
            0,
            "Low: preserves canonical architecture and does not alter outcome values.",
        ),
        (
            "PLAN_03",
            "Keep no-valid-source rows excluded from strict corrected accuracy.",
            "fallback_exhaustion_no_valid_source",
            failure_classes["fallback_exhaustion_no_valid_source"] + failure_classes["release_key_multiple_unusable_candidates"],
            "Classify these rows as mapped-but-unusable until a source/window coverage repair creates valid canonical outcomes.",
            "source_coverage_followup",
            0,
            0,
            0,
            "High: source coverage remains the main blocker for strict-ready sample size.",
        ),
    ]
    plan_rows = []
    for step_id, step, target, affected, change, scope, strict_delta, diagnostic_delta, unusable_delta, risk in plan_specs:
        plan_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "plan_step_id": step_id,
                "plan_step": step,
                "target_failure_class": target,
                "affected_rows": affected,
                "proposed_change": change,
                "implementation_scope": scope,
                "canonical_architecture_changed": "FALSE",
                "market_reaction_values_changed": "FALSE",
                "expected_strict_ready_delta": strict_delta,
                "expected_diagnostic_ready_delta": diagnostic_delta,
                "expected_unusable_delta": unusable_delta,
                "risk": risk,
                "notes": "Plan only; implementation belongs to Phase 9A-5M2RR.",
            }
        )

    readiness_specs = [
        ("ambiguous_rows_fully_classified", ambiguous_classified == current_counts["REMAP_AMBIGUOUS"], "", "Implement deterministic mapping bridge."),
        ("unusable_rows_root_caused", unusable_root_caused == current_counts["REMAP_UNUSABLE"], "", "Retain source-coverage blocker classification."),
        ("canonical_architecture_preserved", True, "", "No canonical_outcome_id, trust model, source hierarchy, or disagreement policy redesign proposed."),
        ("strict_ready_after_mapping_sufficient", estimated_strict >= 50, "strict_ready_rows_limited", "Do not proceed directly to corrected strict accuracy design."),
        ("mapping_repair_implementation_ready", True, "", "Proceed to focused mapping implementation repair."),
        ("corrected_accuracy_re_evaluation_design_ready", False, "strict_ready_rows_limited", "Repair mapping first; source coverage may still require a later repair."),
    ]
    readiness_rows = []
    for check, ok, blocker, required in readiness_specs:
        readiness_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "readiness_check_id": f"READY_{check.upper()}",
                "readiness_check": check,
                "status": "PASS" if ok else "FAIL",
                "blocking_issue": blocker,
                "required_before_next_phase": required,
                "notes": "Readiness is for mapping repair implementation, not accuracy re-evaluation execution.",
            }
        )

    governance_rows = _governance_rows(generated_ts, repair_run_id)
    governance_failed = any(row["status"] != "PASS" for row in governance_rows)
    ready_for_mapping_implementation = (
        ambiguous_classified == current_counts["REMAP_AMBIGUOUS"]
        and unusable_root_caused == current_counts["REMAP_UNUSABLE"]
        and not governance_failed
    )
    ready_for_corrected_design = estimated_strict >= 50 and current_counts["REMAP_AMBIGUOUS"] == 0 and not governance_failed
    build_status = "PASS_WITH_WARNINGS" if not governance_failed else "FAIL"
    final_interpretation = (
        "CANONICAL_MAPPING_REPAIR_READY_WITH_WARNINGS"
        if ready_for_mapping_implementation
        else "CANONICAL_MAPPING_REPAIR_NEEDS_REVIEW"
    )
    recommended_next_step = (
        "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN"
        if ready_for_corrected_design
        else "PROCEED_TO_PHASE9A5M2RR_CANONICAL_MAPPING_IMPLEMENTATION_REPAIR"
    )
    remaining_blockers = []
    if estimated_strict < 50:
        remaining_blockers.append("strict_ready_rows_limited")
    if estimated_unusable:
        remaining_blockers.append("source_coverage_gap")
    if current_counts["REMAP_AMBIGUOUS"]:
        remaining_blockers.append("release_level_accuracy_key_ambiguity")

    summary_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "accuracy_rows_checked": len(remap),
            "current_strict_ready_rows": current_strict,
            "current_diagnostic_ready_rows": current_diagnostic_total,
            "current_ambiguous_rows": current_counts["REMAP_AMBIGUOUS"],
            "current_unusable_rows": current_counts["REMAP_UNUSABLE"],
            "ambiguous_rows_fully_classified": "TRUE" if ambiguous_classified == current_counts["REMAP_AMBIGUOUS"] else "FALSE",
            "unusable_rows_root_caused": "TRUE" if unusable_root_caused == current_counts["REMAP_UNUSABLE"] else "FALSE",
            "primary_mapping_failure": primary_mapping_failure,
            "primary_source_coverage_gap": primary_source_gap_value,
            "estimated_strict_ready_rows_after_repair": estimated_strict,
            "estimated_diagnostic_ready_rows_after_repair": estimated_diagnostic,
            "estimated_still_unusable_rows_after_repair": estimated_unusable,
            "diagnostic_ready_delta_after_repair": estimated_diagnostic - current_diagnostic_total,
            "strict_ready_delta_after_repair": estimated_strict - current_strict,
            "remaining_blocking_issues": "|".join(remaining_blockers),
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "accuracy_evaluation_performed": 0,
            "metric_values_recalculated": 0,
            "market_reaction_values_modified": 0,
            "canonical_outcomes_modified": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_mapping_repair_implementation": "TRUE" if ready_for_mapping_implementation else "FALSE",
            "ready_for_corrected_accuracy_re_evaluation_design": "TRUE" if ready_for_corrected_design else "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next_step,
            "notes": "Focused mapping repair audit; no accuracy evaluation, metric recalculation, canonical outcome modification, or source Market Reaction modification performed.",
        }
    ]

    outputs = [
        (OUTPUT_REPAIR, REPAIR_HEADERS, repair_rows),
        (OUTPUT_ROW_AUDIT, ROW_AUDIT_HEADERS, row_audit_rows),
        (OUTPUT_FAILURE, FAILURE_HEADERS, failure_rows),
        (OUTPUT_SOURCE_GAP, SOURCE_GAP_HEADERS, source_gap_rows),
        (OUTPUT_PLAN, PLAN_HEADERS, plan_rows),
        (OUTPUT_READINESS, READINESS_HEADERS, readiness_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_market_reaction_canonical_mapping_repair_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "ambiguous_rows_fully_classified": ambiguous_classified == current_counts["REMAP_AMBIGUOUS"],
        "unusable_rows_root_caused": unusable_root_caused == current_counts["REMAP_UNUSABLE"],
        "primary_mapping_failure": primary_mapping_failure,
        "primary_source_coverage_gap": primary_source_gap_value,
        "estimated_strict_ready_rows_after_repair": estimated_strict,
        "estimated_diagnostic_ready_rows_after_repair": estimated_diagnostic,
        "remaining_blocking_issues": "|".join(remaining_blockers),
        "ready_for_mapping_repair_implementation": ready_for_mapping_implementation,
        "recommended_next_step": recommended_next_step,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "metric_values_recalculated": 0,
        "market_reaction_values_modified": 0,
        "canonical_outcomes_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_canonical_mapping_repair_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
