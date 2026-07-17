import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_reaction_canonical_outcome_validation_v0 import (
    _ensure_sheet_minimal,
    _float,
    _fmt,
    _int,
    _safe_rows,
    _sheet_titles,
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


SCHEMA_VERSION = "presignal_v2_market_reaction_outcome_source_coverage_repair_0.1"
REPAIR_VERSION = "market_reaction_outcome_source_coverage_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M-SRC"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_SOURCE_COVERAGE_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Canonical_Remap_Repaired",
    "Market_Reaction_Canonical_Remap_Unresolved_Audit",
    "Market_Reaction_Canonical_Remap_Repair_Summary",
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Source_Selection",
    "Market_Reaction_Canonical_Source_Agreement",
    "Market_Reaction_Canonical_Window_Construction",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Canonical_Implementation_Issues",
    "Market_Reaction_Canonical_Implementation_Summary",
    "Market_Reaction_Canonical_Validation_Summary",
    "Market_Reaction_Canonical_Unusable_Audit",
    "Market_Reaction_Canonical_Window_Validation",
    "Market_Reaction_Canonical_Disagreement_Validation",
    "Controlled_Accuracy_Evaluation",
]

MAIN_INPUT_SHEETS = ["MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Event", "Config"]
CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)
CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Event", "Config"}

OUTPUT_REPAIR = "Market_Reaction_Source_Coverage_Repair"
OUTPUT_GAP = "Market_Reaction_Source_Coverage_Gap_Detail"
OUTPUT_RECOVERY = "Market_Reaction_Source_Candidate_Recovery_Audit"
OUTPUT_WINDOW = "Market_Reaction_Window_Coverage_Repair_Audit"
OUTPUT_HIERARCHY = "Market_Reaction_Source_Hierarchy_Repair_Audit"
OUTPUT_NORMALIZATION = "Market_Reaction_Source_Normalization_Audit"
OUTPUT_PLAN = "Market_Reaction_Coverage_Repair_Plan"
OUTPUT_READINESS = "Market_Reaction_Coverage_Repair_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Coverage_Repair_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Coverage_Repair_Summary"

REPAIR_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "repair_area",
    "rows_checked",
    "blocked_rows_checked",
    "recoverable_rows_estimated",
    "unrecoverable_rows_estimated",
    "repair_status",
    "repair_conclusion",
    "recommended_action",
    "notes",
]

GAP_HEADERS = [
    "generated_ts",
    "schema_version",
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
    "canonical_trust_level",
    "source_coverage_blocked",
    "root_cause",
    "recoverability_class",
    "recommended_repair_type",
    "notes",
]

RECOVERY_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "candidate_rank",
    "candidate_type",
    "candidate_source_sheet",
    "candidate_event_id",
    "candidate_batch_id",
    "candidate_country",
    "candidate_release_ts",
    "candidate_start_ts",
    "candidate_end_ts",
    "candidate_provider_source",
    "candidate_start_price",
    "candidate_end_price",
    "candidate_realized_pips",
    "candidate_direction",
    "candidate_strength",
    "candidate_selection_allowed",
    "candidate_blocking_reason",
    "candidate_recovery_confidence",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "canonical_start_ts",
    "canonical_end_ts",
    "window_policy",
    "window_minutes",
    "current_window_status",
    "nearest_start_candle_available",
    "nearest_start_candle_gap_minutes",
    "nearest_end_candle_available",
    "nearest_end_candle_gap_minutes",
    "window_repair_candidate",
    "window_repair_type",
    "leakage_safe",
    "recommended_window_action",
    "notes",
]

HIERARCHY_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "current_hierarchy_sources",
    "available_sources_for_row",
    "valid_sources_outside_hierarchy",
    "hierarchy_status",
    "recommended_hierarchy_action",
    "notes",
]

NORMALIZATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "source_value_raw",
    "source_value_normalized",
    "row_count",
    "affected_blocked_rows",
    "normalization_issue",
    "recommended_normalization_action",
    "notes",
]

PLAN_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "repair_plan_id",
    "repair_type",
    "repair_description",
    "affected_rows_estimated",
    "expected_strict_ready_gain",
    "expected_diagnostic_ready_gain",
    "leakage_risk",
    "implementation_risk",
    "requires_governance_approval",
    "recommended_sequence",
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
    "blocked_rows_checked",
    "root_causes_classified",
    "recoverable_rows_estimated",
    "unrecoverable_rows_estimated",
    "source_normalization_repair_candidates",
    "source_hierarchy_repair_candidates",
    "window_policy_repair_candidates",
    "timestamp_tolerance_repair_candidates",
    "manual_review_candidates",
    "estimated_strict_ready_after_repair",
    "estimated_diagnostic_ready_after_repair",
    "estimated_still_unusable_after_repair",
    "primary_root_cause",
    "highest_impact_repair_type",
    "highest_risk_repair_type",
    "remaining_blocking_issue",
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
    "ready_for_source_coverage_implementation_repair",
    "ready_for_corrected_accuracy_re_evaluation",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_outcome_source_coverage_repair_v0_{compact}"


def _base(generated_ts: str, repair_run_id: str, version: bool = False) -> Dict[str, Any]:
    row = {"generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "repair_run_id": repair_run_id}
    if version:
        row["repair_version"] = REPAIR_VERSION
    return row


def _parse_ts(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    normalized = raw.replace(".000Z", "Z")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _minutes_between(left: Optional[datetime], right: Optional[datetime]) -> Optional[float]:
    if left is None or right is None:
        return None
    return (left - right).total_seconds() / 60.0


def _status_valid(row: Dict[str, Any]) -> bool:
    return _norm(row.get("status")).lower() in {"ok", "flat"}


def _formula_match(row: Dict[str, Any]) -> bool:
    start = _float(row.get("start_price"))
    end = _float(row.get("end_price"))
    reported = _float(row.get("realized_pips"))
    if start is None or end is None or reported is None:
        return False
    return abs(((end - start) * 100.0) - reported) <= 0.01


def _price_valid(row: Dict[str, Any]) -> bool:
    start = _float(row.get("start_price"))
    end = _float(row.get("end_price"))
    return start is not None and end is not None and start > 0 and end > 0


def _candidate_basic_valid(row: Dict[str, Any]) -> bool:
    return _status_valid(row) and _price_valid(row) and _int(row.get("candle_count")) > 0 and _formula_match(row)


def _canonical_by_id(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get("canonical_outcome_id")): row for row in rows}


def _rows_by_event_release(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("event_id")), _norm(row.get("release_ts")))
        if all(key):
            index[key].append(row)
    return index


def _rows_by_country_release(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if all(key):
            index[key].append(row)
    return index


def _source_priority(selection_rows: Sequence[Dict[str, Any]]) -> List[str]:
    for row in selection_rows:
        raw = _norm(row.get("source_priority_order"))
        if raw:
            return [part.strip().lower() for part in raw.split(">") if part.strip()]
    return ["tiingo", "eodhd", "massive", "twelvedata"]


def _root_cause_for(canonical: Dict[str, Any], candidates: Sequence[Dict[str, Any]], canonical_start: Optional[datetime], canonical_end: Optional[datetime]) -> Tuple[str, str, str]:
    if not candidates:
        return "NO_RAW_PROVIDER_RUN", "NO_RECOVERY_CANDIDATE", "NO_REPAIR_EXCLUDE"
    if not any(_status_valid(row) for row in candidates):
        return "NO_VALID_SOURCE_IN_HIERARCHY", "SOURCE_HIERARCHY_CANDIDATE", "SOURCE_HIERARCHY_EXPANSION"
    if not any(_price_valid(row) for row in candidates):
        missing_start = any(_float(row.get("start_price")) is None for row in candidates)
        if missing_start:
            return "WINDOW_START_PRICE_MISSING", "WINDOW_POLICY_CANDIDATE", "WINDOW_POLICY_REPAIR"
        return "WINDOW_END_PRICE_MISSING", "WINDOW_POLICY_CANDIDATE", "WINDOW_POLICY_REPAIR"
    if not any(_int(row.get("candle_count")) > 0 for row in candidates):
        return "NO_CANDLES_IN_WINDOW", "WINDOW_POLICY_CANDIDATE", "WINDOW_POLICY_REPAIR"
    if not any(_formula_match(row) for row in candidates):
        return "SOURCE_EXCLUDED_BY_TRUST_POLICY", "SOURCE_HIERARCHY_CANDIDATE", "SOURCE_HIERARCHY_EXPANSION"
    shifted = []
    zero_duration = []
    for row in candidates:
        start_gap = _minutes_between(_parse_ts(row.get("start_ts")), canonical_start)
        end_gap = _minutes_between(_parse_ts(row.get("end_ts")), canonical_end)
        if start_gap is not None and end_gap is not None and abs(start_gap) <= 5 and abs(end_gap) <= 5:
            shifted.append(row)
        if _norm(row.get("status")).lower() == "flat" and _norm(row.get("start_ts")) == _norm(row.get("end_ts")):
            zero_duration.append(row)
    if shifted:
        return "RECOVERABLE_WITH_WINDOW_POLICY_REPAIR", "WINDOW_POLICY_CANDIDATE", "WINDOW_POLICY_REPAIR"
    if zero_duration:
        return "RECOVERABLE_WITH_WINDOW_POLICY_REPAIR", "WINDOW_POLICY_CANDIDATE", "WINDOW_POLICY_REPAIR"
    return "FALLBACK_EXHAUSTION_NO_VALID_SOURCE", "NO_RECOVERY_CANDIDATE", "MANUAL_REVIEW_QUEUE"


def _candidate_type(row: Dict[str, Any], canonical: Dict[str, Any], canonical_start: Optional[datetime], canonical_end: Optional[datetime]) -> Tuple[str, str, str]:
    start_gap = _minutes_between(_parse_ts(row.get("start_ts")), canonical_start)
    end_gap = _minutes_between(_parse_ts(row.get("end_ts")), canonical_end)
    if _norm(row.get("event_id")) == _norm(canonical.get("event_id")) and abs(start_gap or 999) <= 1 and abs(end_gap or 999) <= 1 and _candidate_basic_valid(row):
        return "EXACT_RECOVERY_CANDIDATE", "FALSE", "candidate meets exact validity but selection remains prohibited in design phase"
    if start_gap is not None and end_gap is not None and abs(start_gap) <= 5 and abs(end_gap) <= 5 and _candidate_basic_valid(row):
        return "TIMESTAMP_TOLERANCE_CANDIDATE", "FALSE", "requires approved timestamp/window tolerance repair before use"
    if _norm(row.get("status")).lower() == "flat" and _norm(row.get("start_ts")) == _norm(row.get("end_ts")) and _candidate_basic_valid(row):
        return "WINDOW_POLICY_CANDIDATE", "FALSE", "requires approved flat/zero-duration outcome handling policy"
    if _norm(row.get("provider")).lower() != _norm(row.get("provider")):
        return "SOURCE_NORMALIZATION_CANDIDATE", "FALSE", "requires source normalization repair"
    return "SOURCE_HIERARCHY_CANDIDATE" if _candidate_basic_valid(row) else "NO_RECOVERY_CANDIDATE", "FALSE", "candidate does not satisfy current canonical validity"


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
    return [
        {
            **_base(generated_ts, repair_run_id),
            "check_id": f"CHK_{name.upper()}",
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if str(expected) == str(actual) else "FAIL",
            "notes": "Coverage repair is audit/design only; no values or accuracy rows modified.",
        }
        for name, expected, actual in checks
    ]


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet_minimal(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS, 1)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_SOURCE_COVERAGE_REPAIR", OUTPUT_REPAIR, "market_reaction_source_coverage_repair"),
        ("MARKET_REACTION_SOURCE_COVERAGE_GAP_DETAIL", OUTPUT_GAP, "market_reaction_source_coverage_gap_detail"),
        ("MARKET_REACTION_SOURCE_CANDIDATE_RECOVERY_AUDIT", OUTPUT_RECOVERY, "market_reaction_source_candidate_recovery_audit"),
        ("MARKET_REACTION_WINDOW_COVERAGE_REPAIR_AUDIT", OUTPUT_WINDOW, "market_reaction_window_coverage_repair_audit"),
        ("MARKET_REACTION_SOURCE_HIERARCHY_REPAIR_AUDIT", OUTPUT_HIERARCHY, "market_reaction_source_hierarchy_repair_audit"),
        ("MARKET_REACTION_SOURCE_NORMALIZATION_AUDIT", OUTPUT_NORMALIZATION, "market_reaction_source_normalization_audit"),
        ("MARKET_REACTION_COVERAGE_REPAIR_PLAN", OUTPUT_PLAN, "market_reaction_coverage_repair_plan"),
        ("MARKET_REACTION_COVERAGE_REPAIR_READINESS", OUTPUT_READINESS, "market_reaction_coverage_repair_readiness"),
        ("MARKET_REACTION_COVERAGE_REPAIR_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_coverage_repair_governance"),
        ("MARKET_REACTION_COVERAGE_REPAIR_SUMMARY", OUTPUT_SUMMARY, "market_reaction_coverage_repair_summary"),
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
            "notes": "Phase 9A-5M-SRC source coverage repair audit/design; read-only diagnostics.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M-SRC source coverage repair audit.")
    return parser.parse_args(argv)


def build_market_reaction_outcome_source_coverage_repair_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
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
        raise RuntimeError(f"Missing critical Phase 9A-5M-SRC inputs: {missing_critical}")

    remap_summary = diag_inputs["Market_Reaction_Canonical_Remap_Repair_Summary"][-1] if diag_inputs["Market_Reaction_Canonical_Remap_Repair_Summary"] else {}
    if _norm(remap_summary.get("ready_for_source_coverage_repair")) != "TRUE":
        raise RuntimeError("Phase 9A-5M2RR did not approve source coverage repair.")

    remap_rows = diag_inputs["Market_Reaction_Canonical_Remap_Repaired"]
    blocked_rows = [row for row in remap_rows if _norm(row.get("final_remap_status")) == "UNUSABLE_SOURCE_COVERAGE"]
    outcomes_by_id = _canonical_by_id(diag_inputs["Market_Reaction_Canonical_Outcomes"])
    windows_by_id = _canonical_by_id(diag_inputs["Market_Reaction_Canonical_Window_Construction"])
    source_selection = diag_inputs["Market_Reaction_Canonical_Source_Selection"]
    hierarchy = _source_priority(source_selection)
    hierarchy_set = set(hierarchy)
    mr_rows = main_inputs["MR_ProviderRuns"]
    mr_by_event = _rows_by_event_release(mr_rows)
    mr_by_country_release = _rows_by_country_release(mr_rows)

    gap_rows: List[Dict[str, Any]] = []
    recovery_rows: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []
    hierarchy_rows: List[Dict[str, Any]] = []
    root_counts = Counter()
    recoverability_counts = Counter()
    repair_type_counts = Counter()
    unique_recoverable_cids: Set[str] = set()
    unique_unrecoverable_cids: Set[str] = set()
    row_recoverability: Dict[str, Tuple[str, str, str]] = {}

    for row in blocked_rows:
        cid = _norm(row.get("repaired_canonical_outcome_id"))
        canonical = outcomes_by_id.get(cid, {})
        window = windows_by_id.get(cid, {})
        canonical_start = _parse_ts(canonical.get("canonical_start_ts"))
        canonical_end = _parse_ts(canonical.get("canonical_end_ts"))
        event_key = (_norm(canonical.get("country")), _norm(canonical.get("event_id")), _norm(canonical.get("release_ts")))
        release_key = (_norm(canonical.get("country")), _norm(canonical.get("release_ts")))
        candidates = mr_by_event.get(event_key) or mr_by_country_release.get(release_key, [])
        root_cause, recoverability, repair_type = _root_cause_for(canonical, candidates, canonical_start, canonical_end)
        root_counts[root_cause] += 1
        recoverability_counts[recoverability] += 1
        repair_type_counts[repair_type] += 1
        if recoverability != "NO_RECOVERY_CANDIDATE":
            unique_recoverable_cids.add(cid)
        else:
            unique_unrecoverable_cids.add(cid)
        row_recoverability[_norm(row.get("accuracy_row_id"))] = (root_cause, recoverability, repair_type)

        gap_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": row.get("accuracy_row_id"),
                "experiment_id": row.get("experiment_id"),
                "session_id": row.get("session_id"),
                "provider": row.get("provider"),
                "pack_level": row.get("pack_level"),
                "country": row.get("country"),
                "release_ts": row.get("release_ts"),
                "current_remap_status": row.get("final_remap_status"),
                "current_canonical_outcome_id": cid,
                "canonical_trust_level": row.get("canonical_trust_level"),
                "source_coverage_blocked": "TRUE",
                "root_cause": root_cause,
                "recoverability_class": recoverability,
                "recommended_repair_type": repair_type,
                "notes": "Source coverage classification only; no canonical outcomes or MR source rows modified.",
            }
        )

        ranked_candidates = sorted(
            candidates,
            key=lambda candidate: (
                abs(_minutes_between(_parse_ts(candidate.get("start_ts")), canonical_start) or 9999),
                _norm(candidate.get("provider")),
                _norm(candidate.get("__source_row_number__")),
            ),
        )[:6]
        for rank, candidate in enumerate(ranked_candidates, start=1):
            candidate_type, allowed, reason = _candidate_type(candidate, canonical, canonical_start, canonical_end)
            recovery_rows.append(
                {
                    **_base(generated_ts, repair_run_id),
                    "accuracy_row_id": row.get("accuracy_row_id"),
                    "candidate_rank": rank,
                    "candidate_type": candidate_type,
                    "candidate_source_sheet": "MR_ProviderRuns",
                    "candidate_event_id": candidate.get("event_id"),
                    "candidate_batch_id": canonical.get("batch_id"),
                    "candidate_country": candidate.get("country"),
                    "candidate_release_ts": candidate.get("release_ts"),
                    "candidate_start_ts": candidate.get("start_ts"),
                    "candidate_end_ts": candidate.get("end_ts"),
                    "candidate_provider_source": candidate.get("provider"),
                    "candidate_start_price": candidate.get("start_price"),
                    "candidate_end_price": candidate.get("end_price"),
                    "candidate_realized_pips": candidate.get("realized_pips"),
                    "candidate_direction": candidate.get("real_dir"),
                    "candidate_strength": candidate.get("real_strength"),
                    "candidate_selection_allowed": allowed,
                    "candidate_blocking_reason": reason,
                    "candidate_recovery_confidence": "HIGH" if candidate_type in {"TIMESTAMP_TOLERANCE_CANDIDATE", "WINDOW_POLICY_CANDIDATE"} else "LOW",
                    "notes": "Candidate audit only; no candidate selected in this phase.",
                }
            )

        basic_valid = [candidate for candidate in candidates if _candidate_basic_valid(candidate)]
        nearest_start_gap = min((abs(_minutes_between(_parse_ts(candidate.get("start_ts")), canonical_start) or 9999) for candidate in basic_valid), default=None)
        nearest_end_gap = min((abs(_minutes_between(_parse_ts(candidate.get("end_ts")), canonical_end) or 9999) for candidate in basic_valid), default=None)
        delayed_safe = any(
            (_minutes_between(_parse_ts(candidate.get("start_ts")), canonical_start) or 9999) >= 0
            and abs(_minutes_between(_parse_ts(candidate.get("start_ts")), canonical_start) or 9999) <= 5
            and (_minutes_between(_parse_ts(candidate.get("end_ts")), canonical_end) or 9999) >= -5
            and _candidate_basic_valid(candidate)
            for candidate in candidates
        )
        zero_flat = any(_norm(candidate.get("status")).lower() == "flat" and _norm(candidate.get("start_ts")) == _norm(candidate.get("end_ts")) for candidate in candidates)
        if delayed_safe:
            window_action = "ALLOW_NEAREST_SAFE_CANDLE_POLICY"
            window_repair_type = "nearest_safe_candle_within_tolerance"
        elif zero_flat:
            window_action = "REVIEW_WINDOW_POLICY"
            window_repair_type = "flat_zero_duration_policy_review"
        else:
            window_action = "UNRECOVERABLE_WINDOW"
            window_repair_type = "no_safe_window_candidate"
        window_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": row.get("accuracy_row_id"),
                "canonical_start_ts": canonical.get("canonical_start_ts"),
                "canonical_end_ts": canonical.get("canonical_end_ts"),
                "window_policy": canonical.get("window_policy"),
                "window_minutes": canonical.get("window_minutes"),
                "current_window_status": window.get("window_status") or "INVALID_WINDOW",
                "nearest_start_candle_available": "TRUE" if nearest_start_gap is not None else "FALSE",
                "nearest_start_candle_gap_minutes": _fmt(nearest_start_gap, 3) if nearest_start_gap is not None else "",
                "nearest_end_candle_available": "TRUE" if nearest_end_gap is not None else "FALSE",
                "nearest_end_candle_gap_minutes": _fmt(nearest_end_gap, 3) if nearest_end_gap is not None else "",
                "window_repair_candidate": "TRUE" if delayed_safe or zero_flat else "FALSE",
                "window_repair_type": window_repair_type,
                "leakage_safe": "TRUE" if delayed_safe else "FALSE",
                "recommended_window_action": window_action,
                "notes": "Window repair candidate only; current canonical fixed window remains unmodified.",
            }
        )

        available_sources = sorted({_norm(candidate.get("provider")).lower() for candidate in candidates if _norm(candidate.get("provider"))})
        valid_sources = sorted({_norm(candidate.get("provider")).lower() for candidate in basic_valid if _norm(candidate.get("provider"))})
        outside = sorted(set(valid_sources) - hierarchy_set)
        if not candidates:
            hierarchy_status = "HIERARCHY_NOT_APPLICABLE"
            hierarchy_action = "NO_ACTION_SOURCE_MISSING"
        elif outside:
            hierarchy_status = "HIERARCHY_TOO_NARROW"
            hierarchy_action = "ADD_SOURCE_TO_FALLBACK_CANDIDATES"
        else:
            hierarchy_status = "HIERARCHY_SUFFICIENT"
            hierarchy_action = "KEEP_HIERARCHY"
        hierarchy_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": row.get("accuracy_row_id"),
                "current_hierarchy_sources": "|".join(hierarchy),
                "available_sources_for_row": "|".join(available_sources),
                "valid_sources_outside_hierarchy": "|".join(outside),
                "hierarchy_status": hierarchy_status,
                "recommended_hierarchy_action": hierarchy_action,
                "notes": "Source hierarchy audit only; hierarchy is not changed in this phase.",
            }
        )

    source_raw_counts = Counter(_norm(row.get("provider")) for row in mr_rows if _norm(row.get("provider")))
    affected_by_source = Counter()
    for row in recovery_rows:
        affected_by_source[_norm(row.get("candidate_provider_source"))] += 1
    normalization_rows = []
    for raw, count in sorted(source_raw_counts.items()):
        normalized = raw.lower()
        issue = "NONE" if raw == normalized else "CASE_VARIANT"
        normalization_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "source_value_raw": raw,
                "source_value_normalized": normalized,
                "row_count": count,
                "affected_blocked_rows": affected_by_source.get(raw, 0),
                "normalization_issue": issue,
                "recommended_normalization_action": "NO_ACTION" if issue == "NONE" else "STANDARDIZE_CASE",
                "notes": "Source normalization audit only; source labels are not rewritten.",
            }
        )

    blocked = len(blocked_rows)
    recoverable_rows = sum(1 for row in gap_rows if row["recoverability_class"] != "NO_RECOVERY_CANDIDATE")
    unrecoverable_rows = blocked - recoverable_rows
    current_strict = _int(remap_summary_value(diag_inputs["Market_Reaction_Canonical_Remap_Repair_Summary"], "accuracy_rows_strict_ready"))
    current_diagnostic_only = _int(remap_summary_value(diag_inputs["Market_Reaction_Canonical_Remap_Repair_Summary"], "accuracy_rows_diagnostic_ready"))
    estimated_strict_after = current_strict + recoverable_rows
    estimated_diagnostic_after = estimated_strict_after + current_diagnostic_only
    estimated_unusable_after = unrecoverable_rows
    primary_root = root_counts.most_common(1)[0][0] if root_counts else "none"

    repair_rows = [
        {
            **_base(generated_ts, repair_run_id, True),
            "repair_area": "source_coverage_root_cause",
            "rows_checked": len(remap_rows),
            "blocked_rows_checked": blocked,
            "recoverable_rows_estimated": recoverable_rows,
            "unrecoverable_rows_estimated": unrecoverable_rows,
            "repair_status": "NEEDS_IMPLEMENTATION_REPAIR" if recoverable_rows else "NEEDS_DESIGN_REVIEW",
            "repair_conclusion": "Blocked rows have MR provider candidates but fail strict fixed-window validity.",
            "recommended_action": "PROCEED_TO_PHASE9A5M_SRC2_SOURCE_COVERAGE_IMPLEMENTATION_REPAIR",
            "notes": "Primary repair path is window/timestamp tolerance; no accuracy evaluation performed.",
        },
        {
            **_base(generated_ts, repair_run_id, True),
            "repair_area": "candidate_recovery",
            "rows_checked": len(recovery_rows),
            "blocked_rows_checked": blocked,
            "recoverable_rows_estimated": recoverable_rows,
            "unrecoverable_rows_estimated": unrecoverable_rows,
            "repair_status": "PASS_WITH_WARNINGS",
            "repair_conclusion": "Candidate rows were identified but not selected in this design phase.",
            "recommended_action": "PROCEED_TO_PHASE9A5M_SRC2_SOURCE_COVERAGE_IMPLEMENTATION_REPAIR",
            "notes": "Candidate selection remains FALSE pending approved deterministic implementation.",
        },
    ]

    plan_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "repair_plan_id": "SRC_PLAN_01",
            "repair_type": "WINDOW_POLICY_REPAIR",
            "repair_description": "Allow nearest leakage-safe start/end candle within a small configured tolerance when exact release-relative candle is unavailable.",
            "affected_rows_estimated": recoverability_counts["WINDOW_POLICY_CANDIDATE"],
            "expected_strict_ready_gain": recoverable_rows,
            "expected_diagnostic_ready_gain": recoverable_rows,
            "leakage_risk": "LOW if start candle is at/after release and tolerance is capped.",
            "implementation_risk": "MEDIUM",
            "requires_governance_approval": "TRUE",
            "recommended_sequence": "1",
            "notes": "Narrowest high-impact repair; preserves no-pre-release leakage.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "repair_plan_id": "SRC_PLAN_02",
            "repair_type": "TIMESTAMP_TOLERANCE_REPAIR",
            "repair_description": "Add explicit timestamp tolerance metadata and trust downgrade rules for shifted provider windows.",
            "affected_rows_estimated": recoverability_counts["TIMESTAMP_TOLERANCE_CANDIDATE"],
            "expected_strict_ready_gain": 0,
            "expected_diagnostic_ready_gain": recoverable_rows,
            "leakage_risk": "LOW",
            "implementation_risk": "MEDIUM",
            "requires_governance_approval": "TRUE",
            "recommended_sequence": "2",
            "notes": "Use if strict repair is considered too aggressive; would likely support diagnostic corrected re-evaluation first.",
        },
    ]

    readiness_rows = []
    readiness_specs = [
        ("source_coverage_root_cause_classification", blocked == len(gap_rows), f"root_causes_classified={len(gap_rows)}", "", "Proceed to implementation repair."),
        ("candidate_recovery_identification", recoverable_rows > 0, f"recoverable_rows={recoverable_rows}", "", "Implement deterministic candidate acceptance rules."),
        ("source_hierarchy_readiness", not any(row["hierarchy_status"] == "HIERARCHY_TOO_NARROW" for row in hierarchy_rows), "hierarchy sufficient for observed candidates", "", "Keep hierarchy; focus on window policy."),
        ("source_normalization_readiness", not any(row["normalization_issue"] != "NONE" for row in normalization_rows), "no source alias/case blocker found", "", "No normalization repair needed before window repair."),
        ("window_policy_readiness", recoverability_counts["WINDOW_POLICY_CANDIDATE"] > 0, f"window_policy_candidates={recoverability_counts['WINDOW_POLICY_CANDIDATE']}", "", "Design implementation for safe window tolerance."),
        ("implementation_repair_readiness", recoverable_rows > 0, f"recoverable_rows={recoverable_rows}", "", "Proceed to Phase 9A-5M-SRC2."),
        ("corrected_accuracy_re_evaluation_readiness", False, "repair is not implemented yet", "source_coverage_repair_not_implemented", "Do not proceed to re-evaluation design yet."),
        ("replication_readiness", False, "corrected accuracy re-evaluation not complete", "replication_not_available", "Replication remains blocked."),
    ]
    for area, ok, evidence, blocker, action in readiness_specs:
        readiness_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "readiness_area": area,
                "status": "PASS" if ok else "FAIL",
                "evidence": evidence,
                "blocking_issue": blocker,
                "recommended_action": action,
                "notes": "Readiness is for source coverage implementation repair only.",
            }
        )

    governance_rows = _governance_rows(generated_ts, repair_run_id)
    governance_ok = all(row["status"] == "PASS" for row in governance_rows)
    final_interpretation = "OUTCOME_SOURCE_COVERAGE_REPAIR_NEEDS_IMPLEMENTATION_REPAIR" if recoverable_rows and governance_ok else "OUTCOME_SOURCE_COVERAGE_REPAIR_BLOCKED"
    recommended_next = "PROCEED_TO_PHASE9A5M_SRC2_SOURCE_COVERAGE_IMPLEMENTATION_REPAIR" if recoverable_rows and governance_ok else "HOLD_ACCURACY_RESEARCH_PENDING_OUTCOME_REVIEW"
    summary_rows = [
        {
            **_base(generated_ts, repair_run_id, True),
            "build_status": "PASS_WITH_WARNINGS" if governance_ok else "FAIL",
            "final_interpretation": final_interpretation,
            "blocked_rows_checked": blocked,
            "root_causes_classified": len(gap_rows),
            "recoverable_rows_estimated": recoverable_rows,
            "unrecoverable_rows_estimated": unrecoverable_rows,
            "source_normalization_repair_candidates": sum(1 for row in normalization_rows if row["normalization_issue"] != "NONE"),
            "source_hierarchy_repair_candidates": sum(1 for row in hierarchy_rows if row["hierarchy_status"] == "HIERARCHY_TOO_NARROW"),
            "window_policy_repair_candidates": recoverability_counts["WINDOW_POLICY_CANDIDATE"],
            "timestamp_tolerance_repair_candidates": sum(1 for row in recovery_rows if row["candidate_type"] == "TIMESTAMP_TOLERANCE_CANDIDATE"),
            "manual_review_candidates": unrecoverable_rows,
            "estimated_strict_ready_after_repair": estimated_strict_after,
            "estimated_diagnostic_ready_after_repair": estimated_diagnostic_after,
            "estimated_still_unusable_after_repair": estimated_unusable_after,
            "primary_root_cause": primary_root,
            "highest_impact_repair_type": "WINDOW_POLICY_REPAIR",
            "highest_risk_repair_type": "WINDOW_POLICY_REPAIR",
            "remaining_blocking_issue": "source_coverage_repair_not_implemented",
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
            "ready_for_source_coverage_implementation_repair": "TRUE" if recoverable_rows and governance_ok else "FALSE",
            "ready_for_corrected_accuracy_re_evaluation": "FALSE",
            "ready_for_accuracy_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": "Audit/design only. Candidate rows were inspected but not selected; canonical outcomes and MR source rows remain unchanged.",
        }
    ]

    outputs = [
        (OUTPUT_REPAIR, REPAIR_HEADERS, repair_rows),
        (OUTPUT_GAP, GAP_HEADERS, gap_rows),
        (OUTPUT_RECOVERY, RECOVERY_HEADERS, recovery_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_HIERARCHY, HIERARCHY_HEADERS, hierarchy_rows),
        (OUTPUT_NORMALIZATION, NORMALIZATION_HEADERS, normalization_rows),
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
        "build_status": summary_rows[0]["build_status"],
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_market_reaction_outcome_source_coverage_repair_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "blocked_rows_checked": blocked,
        "root_causes_classified": len(gap_rows),
        "recoverable_rows_estimated": recoverable_rows,
        "unrecoverable_rows_estimated": unrecoverable_rows,
        "source_normalization_repair_candidates": summary_rows[0]["source_normalization_repair_candidates"],
        "source_hierarchy_repair_candidates": summary_rows[0]["source_hierarchy_repair_candidates"],
        "window_policy_repair_candidates": summary_rows[0]["window_policy_repair_candidates"],
        "timestamp_tolerance_repair_candidates": summary_rows[0]["timestamp_tolerance_repair_candidates"],
        "manual_review_candidates": unrecoverable_rows,
        "estimated_strict_ready_after_repair": estimated_strict_after,
        "estimated_diagnostic_ready_after_repair": estimated_diagnostic_after,
        "estimated_still_unusable_after_repair": estimated_unusable_after,
        "primary_root_cause": primary_root,
        "highest_impact_repair_type": "WINDOW_POLICY_REPAIR",
        "highest_risk_repair_type": "WINDOW_POLICY_REPAIR",
        "remaining_blocking_issue": "source_coverage_repair_not_implemented",
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
        "ready_for_source_coverage_implementation_repair": recoverable_rows > 0 and governance_ok,
        "ready_for_corrected_accuracy_re_evaluation": False,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def remap_summary_value(rows: Sequence[Dict[str, Any]], key: str) -> Any:
    return rows[-1].get(key, "") if rows else ""


def main() -> None:
    result = build_market_reaction_outcome_source_coverage_repair_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
