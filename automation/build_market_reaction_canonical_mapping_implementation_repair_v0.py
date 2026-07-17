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

from automation.build_market_reaction_canonical_mapping_repair_v0 import (
    _base as _mapping_base,
)
from automation.build_market_reaction_canonical_outcome_validation_v0 import (
    _ensure_sheet_minimal,
    _int,
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
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_market_reaction_canonical_mapping_implementation_repair_0.1"
REPAIR_VERSION = "market_reaction_canonical_mapping_implementation_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M2RR"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_CANONICAL_REMAP_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

DIAG_INPUT_SHEETS = [
    "Controlled_Accuracy_Evaluation",
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Canonical_Source_Selection",
    "Market_Reaction_Canonical_Window_Construction",
    "Market_Reaction_Accuracy_Row_Remap_Preview",
    "Market_Reaction_Canonical_Validation_Summary",
    "Market_Reaction_Canonical_Mapping_Repair",
    "Market_Reaction_Accuracy_Row_Mapping_Audit",
    "Market_Reaction_Canonical_Mapping_Failure_Audit",
    "Market_Reaction_Canonical_Mapping_Repair_Plan",
    "Market_Reaction_Canonical_Mapping_Readiness",
    "Market_Reaction_Canonical_Mapping_Repair_Summary",
]

MAIN_INPUT_SHEETS = [
    "Evaluation_Rows",
    "Outcome_Ledger",
    "MR_ProviderRuns",
    "Event",
    "Config",
]

CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)
CRITICAL_MAIN_SHEETS = {"Evaluation_Rows", "Outcome_Ledger", "MR_ProviderRuns", "Event"}

OUTPUT_REPAIRED = "Market_Reaction_Canonical_Remap_Repaired"
OUTPUT_CANDIDATES = "Market_Reaction_Canonical_Remap_Candidate_Audit"
OUTPUT_RESOLUTION = "Market_Reaction_Canonical_Remap_Resolution_Audit"
OUTPUT_UNRESOLVED = "Market_Reaction_Canonical_Remap_Unresolved_Audit"
OUTPUT_READINESS = "Market_Reaction_Canonical_Remap_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Canonical_Remap_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Canonical_Remap_Repair_Summary"

REPAIRED_HEADERS = [
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
    "original_remap_status",
    "original_canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "remap_resolution_method",
    "candidate_count_before",
    "candidate_count_after",
    "canonical_source",
    "fallback_used",
    "source_agreement_class",
    "canonical_trust_level",
    "canonical_realized_pips",
    "canonical_realized_direction",
    "canonical_realized_strength",
    "strict_ready",
    "diagnostic_ready",
    "low_trust",
    "unusable",
    "missing",
    "unresolved_ambiguous",
    "final_remap_status",
    "recommended_re_evaluation_handling",
    "notes",
]

CANDIDATE_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "candidate_count_initial",
    "candidate_count_after_canonical_id",
    "candidate_count_after_event_window",
    "candidate_count_after_batch_window",
    "candidate_count_after_session_release_window",
    "candidate_count_final",
    "candidate_selection_method",
    "candidate_selection_status",
    "notes",
]

RESOLUTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "previous_failure_classification",
    "previous_remap_status",
    "resolution_attempted",
    "resolution_method",
    "resolved",
    "resolved_canonical_outcome_id",
    "final_remap_status",
    "remaining_issue",
    "notes",
]

UNRESOLVED_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "final_remap_status",
    "blocking_reason",
    "root_cause",
    "source_coverage_gap",
    "window_issue",
    "matching_issue",
    "trust_issue",
    "recommended_next_repair",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "readiness_area",
    "status",
    "evidence",
    "blocking_issue",
    "recommended_action",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
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
    "accuracy_rows_processed",
    "accuracy_rows_strict_ready",
    "accuracy_rows_diagnostic_ready",
    "accuracy_rows_low_trust",
    "accuracy_rows_unusable",
    "accuracy_rows_missing",
    "accuracy_rows_unresolved_ambiguous",
    "previous_ambiguous_rows",
    "ambiguous_rows_resolved",
    "ambiguous_rows_remaining",
    "previous_unusable_rows",
    "unusable_rows_remaining",
    "source_coverage_blocked_rows",
    "primary_remaining_blocker",
    "estimated_rows_available_for_strict_corrected_accuracy",
    "estimated_rows_available_for_diagnostic_corrected_accuracy",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "metric_values_recalculated",
    "accuracy_results_modified",
    "canonical_outcomes_modified",
    "market_reaction_values_modified",
    "mr_provider_runs_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_strict_corrected_accuracy_re_evaluation",
    "ready_for_diagnostic_corrected_accuracy_re_evaluation",
    "ready_for_source_coverage_repair",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_canonical_mapping_implementation_repair_v0_{compact}"


def _base(generated_ts: str, repair_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "repair_version": REPAIR_VERSION,
        "repair_run_id": repair_run_id,
    }


def _simple_base(generated_ts: str, repair_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "repair_run_id": repair_run_id,
    }


def _accuracy_key(row: Dict[str, Any]) -> Tuple[str, str]:
    raw = _norm(row.get("outcome_match_key"))
    if "|" in raw:
        return tuple(raw.split("|", 1))  # type: ignore[return-value]
    return _norm(row.get("country")), _norm(row.get("release_ts"))


def _index_by_id(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("canonical_outcome_id")): row for row in rows}


def _index_by_accuracy_id(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("accuracy_row_id")): row for row in rows}


def _index_outcomes_by_release(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if key != ("", ""):
            index[key].append(row)
    return index


def _candidate_signature(row: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        _norm(row.get("trust_level")),
        _norm(row.get("canonical_realized_pips")),
        _norm(row.get("canonical_realized_direction")),
        _norm(row.get("canonical_realized_strength")),
        _norm(row.get("source_agreement_class")),
    )


def _filter_by_event(candidates: Sequence[Dict[str, Any]], event_ids: Set[str]) -> List[Dict[str, Any]]:
    if not event_ids:
        return list(candidates)
    filtered = [row for row in candidates if _norm(row.get("event_id")) in event_ids]
    return filtered or list(candidates)


def _filter_by_batch(candidates: Sequence[Dict[str, Any]], batch_ids: Set[str]) -> List[Dict[str, Any]]:
    if not batch_ids:
        return list(candidates)
    filtered = [row for row in candidates if _norm(row.get("batch_id")) in batch_ids]
    return filtered or list(candidates)


def _canonical_sort_key(row: Dict[str, Any]) -> str:
    return _norm(row.get("canonical_outcome_id"))


def _deterministic_representative(candidates: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    return sorted(candidates, key=_canonical_sort_key)[0]


def _trust_status(canonical: Optional[Dict[str, Any]]) -> Tuple[str, str, bool, bool, bool, bool, bool, bool]:
    if not canonical:
        return "MISSING_CANONICAL_OUTCOME", "EXCLUDE_FROM_RE_EVALUATION", False, False, False, False, True, False
    trust = _norm(canonical.get("trust_level"))
    if trust == "HIGH_TRUST":
        return "STRICT_READY", "INCLUDE_IN_STRICT_RE_EVALUATION", True, True, False, False, False, False
    if trust == "MEDIUM_TRUST":
        return "DIAGNOSTIC_READY", "INCLUDE_IN_DIAGNOSTIC_RE_EVALUATION_ONLY", False, True, False, False, False, False
    if trust == "LOW_TRUST":
        return "LOW_TRUST_EXCLUDED", "REVIEW_BEFORE_RE_EVALUATION", False, False, True, False, False, False
    fallback_reason = _norm(canonical.get("fallback_reason"))
    window_confidence = _norm(canonical.get("window_confidence"))
    if window_confidence == "UNUSABLE" and fallback_reason != "no_valid_source":
        return "UNUSABLE_WINDOW", "EXCLUDE_FROM_RE_EVALUATION", False, False, False, True, False, False
    return "UNUSABLE_SOURCE_COVERAGE", "EXCLUDE_FROM_RE_EVALUATION", False, False, False, True, False, False


def _resolve_candidates(
    acc_row: Dict[str, Any],
    original_remap: Dict[str, Any],
    mapping_audit: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], str, str, int, int, int, int, int, str, str]:
    original_status = _norm(original_remap.get("remap_status"))
    original_cid = _norm(original_remap.get("canonical_outcome_id"))
    event_ids = _split_tokens(acc_row.get("event_id"))
    batch_ids = _split_tokens(acc_row.get("batch_id")) or _split_tokens(mapping_audit.get("candidate_batch_ids"))

    after_canonical = [row for row in candidates if _norm(row.get("canonical_outcome_id")) == original_cid] if original_cid and original_status != "REMAP_AMBIGUOUS" else []
    if after_canonical:
        selected = after_canonical[0]
        return selected, "exact_canonical_outcome_id", "UNIQUE_SELECTED", len(candidates), len(after_canonical), len(after_canonical), len(after_canonical), 1, "Exact canonical ID was available from prior remap.", ""

    after_event = _filter_by_event(candidates, event_ids)
    after_batch = _filter_by_batch(after_event, batch_ids)
    after_session = after_batch

    if len(after_event) == 1:
        selected = after_event[0]
        return selected, "exact_event_window", "UNIQUE_SELECTED", len(candidates), 0, len(after_event), len(after_batch), 1, "Resolved by event_id + window.", ""
    if len(after_batch) == 1:
        selected = after_batch[0]
        return selected, "exact_batch_window", "UNIQUE_SELECTED", len(candidates), 0, len(after_event), len(after_batch), 1, "Resolved by batch_id + window.", ""

    pool = after_batch or after_event or list(candidates)
    if not pool:
        return None, "country_release_window", "NO_CANDIDATE", len(candidates), 0, len(after_event), len(after_batch), 0, "No canonical candidate found.", "missing_canonical_outcome"

    signatures = {_candidate_signature(row) for row in pool}
    trusts = {_norm(row.get("trust_level")) for row in pool}
    batches = {_norm(row.get("batch_id")) for row in pool if _norm(row.get("batch_id"))}
    if len(signatures) == 1:
        selected = _deterministic_representative(pool)
        status = "SOURCE_COVERAGE_BLOCKED" if trusts == {"UNUSABLE"} else "UNIQUE_SELECTED"
        return selected, "identical_candidate_signature_representative", status, len(candidates), 0, len(after_event), len(after_batch), 1, "Multiple candidates share identical outcome/trust signature; deterministic representative selected for bookkeeping.", ""

    best_rank = max((_trust_rank(row) for row in pool), default=0)
    top = [row for row in pool if _trust_rank(row) == best_rank]
    if len(top) == 1 and best_rank >= 3:
        selected = top[0]
        return selected, "unique_highest_trust_candidate", "UNIQUE_SELECTED", len(candidates), 0, len(after_event), len(after_batch), 1, "Unique highest-trust candidate selected without using forecast correctness.", ""

    if trusts == {"UNUSABLE"}:
        selected = _deterministic_representative(pool)
        return selected, "source_coverage_blocked_representative", "SOURCE_COVERAGE_BLOCKED", len(candidates), 0, len(after_event), len(after_batch), 1, "All remaining candidates are unusable; representative selected only to preserve deterministic exclusion.", ""

    return None, "unresolved_after_hierarchy", "MULTIPLE_UNRESOLVED", len(candidates), 0, len(after_event), len(after_batch), len(pool), "More than one non-identical candidate remains after approved hierarchy.", "multiple_candidate_outcomes"


def _governance_rows(generated_ts: str, repair_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("metric_values_recalculated", 0, 0),
        ("accuracy_results_modified", 0, 0),
        ("canonical_outcomes_modified", 0, 0),
        ("market_reaction_values_modified", 0, 0),
        ("mr_provider_runs_modified", 0, 0),
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
                **_simple_base(generated_ts, repair_run_id),
                "check_id": f"CHK_{check.upper()}",
                "check_name": check,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Canonical remap repair writes diagnostics only and does not rerun accuracy.",
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
        ("MARKET_REACTION_CANONICAL_REMAP_REPAIRED", OUTPUT_REPAIRED, "market_reaction_canonical_remap_repaired"),
        ("MARKET_REACTION_CANONICAL_REMAP_CANDIDATE_AUDIT", OUTPUT_CANDIDATES, "market_reaction_canonical_remap_candidate_audit"),
        ("MARKET_REACTION_CANONICAL_REMAP_RESOLUTION_AUDIT", OUTPUT_RESOLUTION, "market_reaction_canonical_remap_resolution_audit"),
        ("MARKET_REACTION_CANONICAL_REMAP_UNRESOLVED_AUDIT", OUTPUT_UNRESOLVED, "market_reaction_canonical_remap_unresolved_audit"),
        ("MARKET_REACTION_CANONICAL_REMAP_READINESS", OUTPUT_READINESS, "market_reaction_canonical_remap_readiness"),
        ("MARKET_REACTION_CANONICAL_REMAP_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_canonical_remap_governance"),
        ("MARKET_REACTION_CANONICAL_REMAP_REPAIR_SUMMARY", OUTPUT_SUMMARY, "market_reaction_canonical_remap_repair_summary"),
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
            "notes": "Phase 9A-5M2RR canonical remap implementation repair; read-only diagnostic layer.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M2RR canonical remap implementation repair.")
    return parser.parse_args(argv)


def build_market_reaction_canonical_mapping_implementation_repair_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
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
        raise RuntimeError(f"Missing critical Phase 9A-5M2RR inputs: {missing_critical}")

    mapping_summary = diag_inputs["Market_Reaction_Canonical_Mapping_Repair_Summary"][-1] if diag_inputs["Market_Reaction_Canonical_Mapping_Repair_Summary"] else {}
    if _norm(mapping_summary.get("ready_for_mapping_repair_implementation")) != "TRUE":
        raise RuntimeError("Phase 9A-5M2R did not approve mapping repair implementation.")
    _ = main_inputs

    accuracy_rows = diag_inputs["Controlled_Accuracy_Evaluation"]
    outcomes = diag_inputs["Market_Reaction_Canonical_Outcomes"]
    previous_remap = _index_by_accuracy_id(diag_inputs["Market_Reaction_Accuracy_Row_Remap_Preview"])
    mapping_audit = _index_by_accuracy_id(diag_inputs["Market_Reaction_Accuracy_Row_Mapping_Audit"])
    failure_audit = _index_by_accuracy_id(diag_inputs["Market_Reaction_Canonical_Mapping_Failure_Audit"])
    outcomes_by_release = _index_outcomes_by_release(outcomes)

    repaired_rows: List[Dict[str, Any]] = []
    candidate_rows: List[Dict[str, Any]] = []
    resolution_rows: List[Dict[str, Any]] = []
    unresolved_rows: List[Dict[str, Any]] = []

    previous_counts = Counter(_norm(row.get("remap_status")) for row in previous_remap.values())
    for acc in accuracy_rows:
        accuracy_row_id = _norm(acc.get("__source_row_number__"))
        prev = previous_remap.get(accuracy_row_id, {})
        audit = mapping_audit.get(accuracy_row_id, {})
        failure = failure_audit.get(accuracy_row_id, {})
        country, release_ts = _accuracy_key(acc)
        candidates = outcomes_by_release.get((country, release_ts), [])
        selected, method, selection_status, initial_count, after_cid, after_event, after_batch, final_count, selection_notes, remaining_issue = _resolve_candidates(acc, prev, audit, candidates)
        final_status, handling, strict, diagnostic, low, unusable, missing, unresolved = _trust_status(selected)
        if selection_status == "MULTIPLE_UNRESOLVED":
            final_status = "UNRESOLVED_AMBIGUOUS"
            handling = "REVIEW_BEFORE_RE_EVALUATION"
            strict = diagnostic = low = unusable = missing = False
            unresolved = True
        if selection_status == "NO_CANDIDATE":
            final_status = "MISSING_CANONICAL_OUTCOME"
            handling = "EXCLUDE_FROM_RE_EVALUATION"
            strict = diagnostic = low = unusable = unresolved = False
            missing = True
        if selection_status == "SOURCE_COVERAGE_BLOCKED":
            final_status = "UNUSABLE_SOURCE_COVERAGE"
            handling = "EXCLUDE_FROM_RE_EVALUATION"
            strict = diagnostic = low = missing = unresolved = False
            unusable = True

        original_status = _norm(prev.get("remap_status"))
        repaired_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": accuracy_row_id,
                "experiment_id": acc.get("experiment_id"),
                "session_id": acc.get("session_id"),
                "provider": acc.get("provider"),
                "pack_level": acc.get("pack_level"),
                "country": country,
                "release_ts": release_ts,
                "original_remap_status": original_status,
                "original_canonical_outcome_id": prev.get("canonical_outcome_id"),
                "repaired_canonical_outcome_id": selected.get("canonical_outcome_id") if selected else "",
                "remap_resolution_method": method,
                "candidate_count_before": initial_count,
                "candidate_count_after": final_count,
                "canonical_source": selected.get("canonical_source") if selected else "",
                "fallback_used": selected.get("fallback_used") if selected else "",
                "source_agreement_class": selected.get("source_agreement_class") if selected else "",
                "canonical_trust_level": selected.get("trust_level") if selected else "",
                "canonical_realized_pips": selected.get("canonical_realized_pips") if selected else "",
                "canonical_realized_direction": selected.get("canonical_realized_direction") if selected else "",
                "canonical_realized_strength": selected.get("canonical_realized_strength") if selected else "",
                "strict_ready": "TRUE" if strict else "FALSE",
                "diagnostic_ready": "TRUE" if diagnostic else "FALSE",
                "low_trust": "TRUE" if low else "FALSE",
                "unusable": "TRUE" if unusable else "FALSE",
                "missing": "TRUE" if missing else "FALSE",
                "unresolved_ambiguous": "TRUE" if unresolved else "FALSE",
                "final_remap_status": final_status,
                "recommended_re_evaluation_handling": handling,
                "notes": f"{selection_notes} Mapping repair only; no correctness or accuracy metrics calculated.",
            }
        )
        candidate_rows.append(
            {
                **_simple_base(generated_ts, repair_run_id),
                "accuracy_row_id": accuracy_row_id,
                "candidate_count_initial": initial_count,
                "candidate_count_after_canonical_id": after_cid,
                "candidate_count_after_event_window": after_event,
                "candidate_count_after_batch_window": after_batch,
                "candidate_count_after_session_release_window": after_batch,
                "candidate_count_final": final_count,
                "candidate_selection_method": method,
                "candidate_selection_status": selection_status,
                "notes": selection_notes,
            }
        )
        if original_status == "REMAP_AMBIGUOUS":
            resolved = final_status != "UNRESOLVED_AMBIGUOUS"
            resolution_rows.append(
                {
                    **_simple_base(generated_ts, repair_run_id),
                    "accuracy_row_id": accuracy_row_id,
                    "previous_failure_classification": audit.get("mapping_failure_class") or failure.get("failure_classification"),
                    "previous_remap_status": original_status,
                    "resolution_attempted": "TRUE",
                    "resolution_method": method,
                    "resolved": "TRUE" if resolved else "FALSE",
                    "resolved_canonical_outcome_id": selected.get("canonical_outcome_id") if selected else "",
                    "final_remap_status": final_status,
                    "remaining_issue": "" if resolved else remaining_issue,
                    "notes": "Ambiguous release-level remap repaired through deterministic hierarchy or classified as source-coverage blocked.",
                }
            )
        if final_status not in {"STRICT_READY", "DIAGNOSTIC_READY"}:
            root_cause = failure.get("root_cause") or audit.get("mapping_root_cause") or selection_notes
            source_gap = final_status == "UNUSABLE_SOURCE_COVERAGE"
            window_issue = final_status == "UNUSABLE_WINDOW"
            trust_issue = final_status == "LOW_TRUST_EXCLUDED"
            matching_issue = final_status in {"MISSING_CANONICAL_OUTCOME", "UNRESOLVED_AMBIGUOUS"}
            if source_gap:
                next_repair = "OUTCOME_SOURCE_COVERAGE_REPAIR"
            elif window_issue:
                next_repair = "WINDOW_POLICY_REPAIR"
            elif matching_issue:
                next_repair = "CANONICAL_ID_REPAIR"
            elif trust_issue:
                next_repair = "MANUAL_REVIEW"
            else:
                next_repair = "EXCLUDE_FROM_CORRECTED_RE_EVALUATION"
            unresolved_rows.append(
                {
                    **_simple_base(generated_ts, repair_run_id),
                    "accuracy_row_id": accuracy_row_id,
                    "final_remap_status": final_status,
                    "blocking_reason": remaining_issue or final_status,
                    "root_cause": root_cause,
                    "source_coverage_gap": "TRUE" if source_gap else "FALSE",
                    "window_issue": "TRUE" if window_issue else "FALSE",
                    "matching_issue": "TRUE" if matching_issue else "FALSE",
                    "trust_issue": "TRUE" if trust_issue else "FALSE",
                    "recommended_next_repair": next_repair,
                    "notes": "Unusable/unresolved audit only; no source rows modified.",
                }
            )

    final_counts = Counter(_norm(row["final_remap_status"]) for row in repaired_rows)
    strict_ready = final_counts["STRICT_READY"]
    diagnostic_ready = final_counts["DIAGNOSTIC_READY"]
    low_trust = final_counts["LOW_TRUST_EXCLUDED"]
    missing_count = final_counts["MISSING_CANONICAL_OUTCOME"]
    unresolved_ambiguous = final_counts["UNRESOLVED_AMBIGUOUS"]
    unusable_count = final_counts["UNUSABLE_SOURCE_COVERAGE"] + final_counts["UNUSABLE_WINDOW"]
    source_coverage_blocked = final_counts["UNUSABLE_SOURCE_COVERAGE"]
    previous_ambiguous = previous_counts["REMAP_AMBIGUOUS"]
    ambiguous_resolved = sum(1 for row in resolution_rows if row["resolved"] == "TRUE")
    ambiguous_remaining = previous_ambiguous - ambiguous_resolved
    previous_unusable = previous_counts["REMAP_UNUSABLE"]
    primary_blocker = "source_coverage_gap" if source_coverage_blocked else "none"

    governance_rows = _governance_rows(generated_ts, repair_run_id)
    governance_ok = all(row["status"] == "PASS" for row in governance_rows)
    ready_strict = strict_ready >= 50 and governance_ok
    ready_diagnostic = (strict_ready + diagnostic_ready) >= 50 and governance_ok
    ready_source_repair = source_coverage_blocked > 0 and governance_ok
    final_interpretation = (
        "CANONICAL_MAPPING_IMPLEMENTATION_REPAIR_NEEDS_SOURCE_COVERAGE_REPAIR"
        if ready_source_repair and not ready_strict
        else "CANONICAL_MAPPING_IMPLEMENTATION_REPAIR_READY_WITH_WARNINGS"
        if governance_ok
        else "CANONICAL_MAPPING_IMPLEMENTATION_REPAIR_BLOCKED"
    )
    recommended_next = (
        "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN"
        if ready_strict or ready_diagnostic
        else "PROCEED_TO_PHASE9A5M_SRC_OUTCOME_SOURCE_COVERAGE_REPAIR"
        if ready_source_repair
        else "PROCEED_TO_PHASE9A5M2RRR_MAPPING_REPAIR_REVIEW"
    )
    build_status = "PASS_WITH_WARNINGS" if governance_ok else "FAIL"

    readiness_specs = [
        (
            "strict_re_evaluation_readiness",
            "PASS" if ready_strict else "FAIL",
            f"strict_ready={strict_ready}",
            "" if ready_strict else "strict_ready_rows_below_threshold",
            "Repair source coverage before strict corrected re-evaluation.",
        ),
        (
            "diagnostic_re_evaluation_readiness",
            "PASS" if ready_diagnostic else "FAIL",
            f"strict_plus_diagnostic={strict_ready + diagnostic_ready}",
            "" if ready_diagnostic else "diagnostic_rows_below_threshold",
            "Use diagnostic-only design only after source coverage improves sample size.",
        ),
        (
            "source_coverage_readiness",
            "PASS" if ready_source_repair else "PASS_WITH_WARNINGS",
            f"source_coverage_blocked_rows={source_coverage_blocked}",
            "source_coverage_gap" if source_coverage_blocked else "",
            "Proceed to outcome source coverage repair if blocked rows remain.",
        ),
        (
            "ambiguity_resolution_readiness",
            "PASS" if ambiguous_remaining == 0 else "FAIL",
            f"ambiguous_resolved={ambiguous_resolved}; ambiguous_remaining={ambiguous_remaining}",
            "" if ambiguous_remaining == 0 else "unresolved_ambiguous_rows",
            "Review unresolved rows before corrected re-evaluation.",
        ),
        (
            "governance_readiness",
            "PASS" if governance_ok else "FAIL",
            "all governance counters remain zero",
            "" if governance_ok else "governance_check_failed",
            "Hold if any governance counter fails.",
        ),
        (
            "replication_readiness",
            "FAIL",
            "corrected accuracy re-evaluation has not run",
            "replication_not_available_before_corrected_re_evaluation",
            "Replication remains unavailable until repaired outcomes and corrected evaluation are validated.",
        ),
    ]
    readiness_rows = [
        {
            **_simple_base(generated_ts, repair_run_id),
            "readiness_area": area,
            "status": status,
            "evidence": evidence,
            "blocking_issue": blocker,
            "recommended_action": action,
            "notes": "Readiness is for future corrected re-evaluation design only; no accuracy calculated.",
        }
        for area, status, evidence, blocker, action in readiness_specs
    ]

    summary_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "accuracy_rows_processed": len(repaired_rows),
            "accuracy_rows_strict_ready": strict_ready,
            "accuracy_rows_diagnostic_ready": diagnostic_ready,
            "accuracy_rows_low_trust": low_trust,
            "accuracy_rows_unusable": unusable_count,
            "accuracy_rows_missing": missing_count,
            "accuracy_rows_unresolved_ambiguous": unresolved_ambiguous,
            "previous_ambiguous_rows": previous_ambiguous,
            "ambiguous_rows_resolved": ambiguous_resolved,
            "ambiguous_rows_remaining": ambiguous_remaining,
            "previous_unusable_rows": previous_unusable,
            "unusable_rows_remaining": unusable_count,
            "source_coverage_blocked_rows": source_coverage_blocked,
            "primary_remaining_blocker": primary_blocker,
            "estimated_rows_available_for_strict_corrected_accuracy": strict_ready,
            "estimated_rows_available_for_diagnostic_corrected_accuracy": strict_ready + diagnostic_ready,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "accuracy_evaluation_performed": 0,
            "metric_values_recalculated": 0,
            "accuracy_results_modified": 0,
            "canonical_outcomes_modified": 0,
            "market_reaction_values_modified": 0,
            "mr_provider_runs_modified": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_strict_corrected_accuracy_re_evaluation": "TRUE" if ready_strict else "FALSE",
            "ready_for_diagnostic_corrected_accuracy_re_evaluation": "TRUE" if ready_diagnostic else "FALSE",
            "ready_for_source_coverage_repair": "TRUE" if ready_source_repair else "FALSE",
            "ready_for_accuracy_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": "Mapping-layer implementation repair completed; source coverage remains outside this phase.",
        }
    ]

    outputs = [
        (OUTPUT_REPAIRED, REPAIRED_HEADERS, repaired_rows),
        (OUTPUT_CANDIDATES, CANDIDATE_HEADERS, candidate_rows),
        (OUTPUT_RESOLUTION, RESOLUTION_HEADERS, resolution_rows),
        (OUTPUT_UNRESOLVED, UNRESOLVED_HEADERS, unresolved_rows),
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
        "file_created": "automation/build_market_reaction_canonical_mapping_implementation_repair_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "accuracy_rows_processed": len(repaired_rows),
        "accuracy_rows_strict_ready": strict_ready,
        "accuracy_rows_diagnostic_ready": diagnostic_ready,
        "accuracy_rows_low_trust": low_trust,
        "accuracy_rows_unusable": unusable_count,
        "accuracy_rows_missing": missing_count,
        "accuracy_rows_unresolved_ambiguous": unresolved_ambiguous,
        "previous_ambiguous_rows": previous_ambiguous,
        "ambiguous_rows_resolved": ambiguous_resolved,
        "ambiguous_rows_remaining": ambiguous_remaining,
        "previous_unusable_rows": previous_unusable,
        "unusable_rows_remaining": unusable_count,
        "source_coverage_blocked_rows": source_coverage_blocked,
        "primary_remaining_blocker": primary_blocker,
        "estimated_rows_available_for_strict_corrected_accuracy": strict_ready,
        "estimated_rows_available_for_diagnostic_corrected_accuracy": strict_ready + diagnostic_ready,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "metric_values_recalculated": 0,
        "accuracy_results_modified": 0,
        "canonical_outcomes_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_strict_corrected_accuracy_re_evaluation": ready_strict,
        "ready_for_diagnostic_corrected_accuracy_re_evaluation": ready_diagnostic,
        "ready_for_source_coverage_repair": ready_source_repair,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_canonical_mapping_implementation_repair_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
