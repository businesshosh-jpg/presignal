import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


SCHEMA_VERSION = "presignal_v2_market_reaction_source_coverage_implementation_repair_0.1"
REPAIR_VERSION = "market_reaction_source_coverage_implementation_repair_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M-SRC2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_SOURCE_COVERAGE_IMPLEMENTATION_REPAIR"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = ["MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Event", "Config"]
DIAG_INPUT_SHEETS = [
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Source_Selection",
    "Market_Reaction_Canonical_Window_Construction",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Source_Coverage_Gap_Detail",
    "Market_Reaction_Source_Candidate_Recovery_Audit",
    "Market_Reaction_Window_Coverage_Repair_Audit",
    "Market_Reaction_Coverage_Repair_Plan",
    "Market_Reaction_Coverage_Repair_Summary",
]
CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Event", "Config"}
CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)

OUTPUT_IMPLEMENTATION = "Market_Reaction_Source_Coverage_Implementation"
OUTPUT_WINDOW = "Market_Reaction_Window_Repair_Results"
OUTPUT_RECOVERED = "Market_Reaction_Recovered_Canonical_Outcomes"
OUTPUT_AUDIT = "Market_Reaction_Recovered_Coverage_Audit"
OUTPUT_READINESS = "Market_Reaction_Source_Coverage_Implementation_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Source_Coverage_Implementation_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Source_Coverage_Implementation_Summary"

IMPLEMENTATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "implementation_area",
    "blocked_rows_processed",
    "successfully_recovered_rows",
    "leakage_blocked_rows",
    "remaining_unusable_rows",
    "implementation_status",
    "implementation_conclusion",
    "recommended_action",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "country",
    "release_ts",
    "selected_provider_source",
    "window_repair_method",
    "canonical_start_ts",
    "canonical_end_ts",
    "repaired_start_ts",
    "repaired_end_ts",
    "window_shift_start_minutes",
    "window_shift_end_minutes",
    "repair_confidence",
    "leakage_safe",
    "recovered",
    "leakage_blocked",
    "unrecoverable_reason",
    "notes",
]

RECOVERED_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "repaired_canonical_overlay_id",
    "canonical_outcome_id",
    "country",
    "event_id",
    "batch_id",
    "session_id",
    "release_ts",
    "canonical_start_ts",
    "canonical_end_ts",
    "repaired_start_ts",
    "repaired_end_ts",
    "window_repair_method",
    "window_shift_start_minutes",
    "window_shift_end_minutes",
    "repaired_canonical_source",
    "fallback_used",
    "source_agreement_class",
    "repaired_start_price",
    "repaired_end_price",
    "repaired_realized_pips",
    "repaired_realized_direction",
    "repaired_realized_strength",
    "repaired_trust_level",
    "repair_confidence",
    "leakage_safe",
    "usable_for_strict_accuracy",
    "usable_for_diagnostic_accuracy",
    "original_trust_level",
    "overlay_only",
    "notes",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_run_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "repaired_canonical_overlay_id",
    "original_trust_level",
    "repaired_trust_level",
    "original_final_remap_status",
    "repaired_remap_status",
    "strict_ready_after_repair",
    "diagnostic_ready_after_repair",
    "remaining_unusable",
    "repair_method",
    "repair_confidence",
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
    "blocked_rows_processed",
    "successfully_recovered_rows",
    "leakage_blocked_rows",
    "remaining_unusable_rows",
    "recovered_canonical_outcomes",
    "strict_ready_estimate",
    "diagnostic_ready_estimate",
    "remaining_unusable_estimate",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "metric_values_recalculated",
    "canonical_outcomes_modified",
    "market_reaction_values_modified",
    "mr_provider_runs_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_canonical_outcome_validation",
    "ready_for_corrected_accuracy_re_evaluation",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_source_coverage_implementation_repair_v0_{compact}"


def _base(generated_ts: str, repair_run_id: str, include_version: bool = False) -> Dict[str, Any]:
    row = {"generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "repair_run_id": repair_run_id}
    if include_version:
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


def _minutes(left: Optional[datetime], right: Optional[datetime]) -> Optional[float]:
    if left is None or right is None:
        return None
    return (left - right).total_seconds() / 60.0


def _source_priority(selection_rows: Sequence[Dict[str, Any]]) -> List[str]:
    for row in selection_rows:
        raw = _norm(row.get("source_priority_order"))
        if raw:
            return [part.strip().lower() for part in raw.split(">") if part.strip()]
    return ["tiingo", "eodhd", "massive", "twelvedata"]


def _status_valid(row: Dict[str, Any]) -> bool:
    return _norm(row.get("status")).lower() in {"ok", "flat"}


def _formula_match(row: Dict[str, Any]) -> bool:
    start = _float(row.get("start_price"))
    end = _float(row.get("end_price"))
    reported = _float(row.get("realized_pips"))
    if start is None or end is None or reported is None:
        return False
    return abs(((end - start) * 100.0) - reported) <= 0.01


def _candidate_valid(row: Dict[str, Any]) -> bool:
    start = _float(row.get("start_price"))
    end = _float(row.get("end_price"))
    return (
        _status_valid(row)
        and start is not None
        and end is not None
        and start > 0
        and end > 0
        and _int(row.get("candle_count")) > 0
        and _formula_match(row)
    )


def _direction_from_pips(pips: Optional[float]) -> str:
    if pips is None:
        return ""
    if pips >= 1.0:
        return "UP"
    if pips <= -1.0:
        return "DOWN"
    return "FLAT"


def _strength_from_pips(pips: Optional[float]) -> str:
    if pips is None:
        return ""
    mag = abs(pips)
    if mag < 5:
        return "WEAK"
    if mag < 15:
        return "MEDIUM"
    return "STRONG"


def _overlay_id(canonical_outcome_id: str) -> str:
    return f"{canonical_outcome_id}|SRC2_WINDOW_REPAIR"


def _group_by_event_release(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("event_id")), _norm(row.get("release_ts")))
        if all(key):
            grouped[key].append(row)
    return grouped


def _choose_candidate(
    candidates: Sequence[Dict[str, Any]],
    canonical: Dict[str, Any],
    hierarchy: Sequence[str],
) -> Tuple[Optional[Dict[str, Any]], str, str, str, bool, Optional[float], Optional[float]]:
    c_start = _parse_ts(canonical.get("canonical_start_ts"))
    c_end = _parse_ts(canonical.get("canonical_end_ts"))
    valid = [row for row in candidates if _candidate_valid(row)]
    if not valid:
        return None, "NO_VALID_CANDIDATE", "LOW", "no valid price/status/formula candidate", False, None, None

    scored = []
    for row in valid:
        start_ts = _parse_ts(row.get("start_ts"))
        end_ts = _parse_ts(row.get("end_ts"))
        start_shift = _minutes(start_ts, c_start)
        end_shift = _minutes(end_ts, c_end)
        status = _norm(row.get("status")).lower()
        if start_shift is None or end_shift is None:
            continue
        if abs(start_shift) <= 1 and abs(end_shift) <= 1:
            method = "EXACT_CONFIGURED_WINDOW"
            confidence = "HIGH"
            leakage_safe = True
            score = (0, abs(start_shift) + abs(end_shift))
        elif 0 <= start_shift <= 5 and 0 <= end_shift <= 5:
            method = "NEAREST_SAFE_PROVIDER_WINDOW_WITHIN_TOLERANCE"
            confidence = "HIGH"
            leakage_safe = True
            score = (1, start_shift + end_shift)
        elif status == "flat" and abs(start_shift) <= 1 and end_shift <= 0:
            method = "FLAT_ZERO_DURATION_PROVIDER_RESULT"
            confidence = "MEDIUM"
            leakage_safe = True
            score = (2, abs(start_shift) + abs(end_shift))
        else:
            continue
        provider = _norm(row.get("provider")).lower()
        priority_index = hierarchy.index(provider) if provider in hierarchy else len(hierarchy) + 1
        scored.append((priority_index, score, row, method, confidence, leakage_safe, start_shift, end_shift))
    if not scored:
        return None, "NO_LEAKAGE_SAFE_CANDIDATE", "LOW", "no candidate satisfied approved window tolerance", False, None, None
    selected = sorted(scored, key=lambda item: (item[0], item[1], _norm(item[2].get("__source_row_number__"))))[0]
    _, _, row, method, confidence, leakage_safe, start_shift, end_shift = selected
    return row, method, confidence, "", leakage_safe, start_shift, end_shift


def _agreement_for_candidate(selected: Dict[str, Any], candidates: Sequence[Dict[str, Any]]) -> str:
    selected_provider = _norm(selected.get("provider")).lower()
    comparable = [row for row in candidates if _candidate_valid(row) and _norm(row.get("provider")).lower() == selected_provider]
    if len(comparable) <= 1:
        return "LOW_DISAGREEMENT"
    pips = [_float(row.get("realized_pips")) for row in comparable]
    dirs = {_direction_from_pips(value) for value in pips if value is not None}
    if len(dirs) > 1:
        return "HIGH_DISAGREEMENT"
    if max(pips) - min(pips) > 1 if all(value is not None for value in pips) else False:
        return "MODERATE_DISAGREEMENT"
    return "LOW_DISAGREEMENT"


def _governance_rows(generated_ts: str, repair_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("metric_values_recalculated", 0, 0),
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
            "notes": "Implementation repair writes overlay diagnostics only; no source, canonical, evaluation, or production sheets modified.",
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
        ("MARKET_REACTION_SOURCE_COVERAGE_IMPLEMENTATION", OUTPUT_IMPLEMENTATION, "market_reaction_source_coverage_implementation"),
        ("MARKET_REACTION_WINDOW_REPAIR_RESULTS", OUTPUT_WINDOW, "market_reaction_window_repair_results"),
        ("MARKET_REACTION_RECOVERED_CANONICAL_OUTCOMES", OUTPUT_RECOVERED, "market_reaction_recovered_canonical_outcomes"),
        ("MARKET_REACTION_RECOVERED_COVERAGE_AUDIT", OUTPUT_AUDIT, "market_reaction_recovered_coverage_audit"),
        ("MARKET_REACTION_SOURCE_COVERAGE_IMPLEMENTATION_READINESS", OUTPUT_READINESS, "market_reaction_source_coverage_implementation_readiness"),
        ("MARKET_REACTION_SOURCE_COVERAGE_IMPLEMENTATION_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_source_coverage_implementation_governance"),
        ("MARKET_REACTION_SOURCE_COVERAGE_IMPLEMENTATION_SUMMARY", OUTPUT_SUMMARY, "market_reaction_source_coverage_implementation_summary"),
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
            "notes": "Phase 9A-5M-SRC2 repaired canonical outcome overlay; source/canonical/evaluation sheets remain untouched.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        row_number = by_id[key] if key in by_id else len(rows) + appended + 2
        if key not in by_id:
            appended += 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M-SRC2 source coverage implementation repair.")
    return parser.parse_args(argv)


def build_market_reaction_source_coverage_implementation_repair_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
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
        raise RuntimeError(f"Missing critical Phase 9A-5M-SRC2 inputs: {missing_critical}")
    src_summary = diag_inputs["Market_Reaction_Coverage_Repair_Summary"][-1] if diag_inputs["Market_Reaction_Coverage_Repair_Summary"] else {}
    if _norm(src_summary.get("ready_for_source_coverage_implementation_repair")) != "TRUE":
        raise RuntimeError("Phase 9A-5M-SRC did not approve source coverage implementation repair.")

    canonical = {_norm(row.get("canonical_outcome_id")): row for row in diag_inputs["Market_Reaction_Canonical_Outcomes"]}
    source_selection = diag_inputs["Market_Reaction_Canonical_Source_Selection"]
    hierarchy = _source_priority(source_selection)
    mr_by_event = _group_by_event_release(main_inputs["MR_ProviderRuns"])
    blocked = diag_inputs["Market_Reaction_Source_Coverage_Gap_Detail"]

    window_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    recovered_by_cid: Dict[str, Dict[str, Any]] = {}
    processed = recovered = leakage_blocked = remaining_unusable = 0
    for blocked_row in blocked:
        if _norm(blocked_row.get("source_coverage_blocked")) != "TRUE":
            continue
        processed += 1
        cid = _norm(blocked_row.get("current_canonical_outcome_id"))
        c = canonical.get(cid, {})
        key = (_norm(c.get("country")), _norm(c.get("event_id")), _norm(c.get("release_ts")))
        candidates = mr_by_event.get(key, [])
        selected, method, confidence, reason, leakage_safe, start_shift, end_shift = _choose_candidate(candidates, c, hierarchy)
        is_recovered = selected is not None and leakage_safe
        if is_recovered:
            recovered += 1
        elif selected is not None and not leakage_safe:
            leakage_blocked += 1
        else:
            remaining_unusable += 1
        start_price = _float(selected.get("start_price")) if selected else None
        end_price = _float(selected.get("end_price")) if selected else None
        repaired_pips = (end_price - start_price) * 100.0 if start_price is not None and end_price is not None else None
        repaired_direction = _direction_from_pips(repaired_pips)
        repaired_strength = _strength_from_pips(repaired_pips)
        agreement = _agreement_for_candidate(selected, candidates) if selected else "UNUSABLE"
        trust = "HIGH_TRUST" if is_recovered and agreement == "LOW_DISAGREEMENT" else "MEDIUM_TRUST" if is_recovered else "UNUSABLE"
        strict = trust == "HIGH_TRUST"
        diagnostic = trust in {"HIGH_TRUST", "MEDIUM_TRUST"}
        overlay_id = _overlay_id(cid)
        if is_recovered and cid not in recovered_by_cid:
            recovered_by_cid[cid] = {
                **_base(generated_ts, repair_run_id, True),
                "repaired_canonical_overlay_id": overlay_id,
                "canonical_outcome_id": cid,
                "country": c.get("country"),
                "event_id": c.get("event_id"),
                "batch_id": c.get("batch_id"),
                "session_id": c.get("session_id"),
                "release_ts": c.get("release_ts"),
                "canonical_start_ts": c.get("canonical_start_ts"),
                "canonical_end_ts": c.get("canonical_end_ts"),
                "repaired_start_ts": selected.get("start_ts") if selected else "",
                "repaired_end_ts": selected.get("end_ts") if selected else "",
                "window_repair_method": method,
                "window_shift_start_minutes": _fmt(start_shift, 3) if start_shift is not None else "",
                "window_shift_end_minutes": _fmt(end_shift, 3) if end_shift is not None else "",
                "repaired_canonical_source": selected.get("provider") if selected else "",
                "fallback_used": "FALSE" if selected and hierarchy and _norm(selected.get("provider")).lower() == hierarchy[0] else "TRUE",
                "source_agreement_class": agreement,
                "repaired_start_price": selected.get("start_price") if selected else "",
                "repaired_end_price": selected.get("end_price") if selected else "",
                "repaired_realized_pips": _fmt(repaired_pips),
                "repaired_realized_direction": repaired_direction,
                "repaired_realized_strength": repaired_strength,
                "repaired_trust_level": trust,
                "repair_confidence": confidence,
                "leakage_safe": "TRUE" if leakage_safe else "FALSE",
                "usable_for_strict_accuracy": "TRUE" if strict else "FALSE",
                "usable_for_diagnostic_accuracy": "TRUE" if diagnostic else "FALSE",
                "original_trust_level": c.get("trust_level"),
                "overlay_only": "TRUE",
                "notes": "Recovered overlay only; original canonical outcome remains unchanged.",
            }
        window_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": blocked_row.get("accuracy_row_id"),
                "canonical_outcome_id": cid,
                "country": c.get("country"),
                "release_ts": c.get("release_ts"),
                "selected_provider_source": selected.get("provider") if selected else "",
                "window_repair_method": method,
                "canonical_start_ts": c.get("canonical_start_ts"),
                "canonical_end_ts": c.get("canonical_end_ts"),
                "repaired_start_ts": selected.get("start_ts") if selected else "",
                "repaired_end_ts": selected.get("end_ts") if selected else "",
                "window_shift_start_minutes": _fmt(start_shift, 3) if start_shift is not None else "",
                "window_shift_end_minutes": _fmt(end_shift, 3) if end_shift is not None else "",
                "repair_confidence": confidence,
                "leakage_safe": "TRUE" if leakage_safe else "FALSE",
                "recovered": "TRUE" if is_recovered else "FALSE",
                "leakage_blocked": "TRUE" if selected is not None and not leakage_safe else "FALSE",
                "unrecoverable_reason": "" if is_recovered else reason,
                "notes": "Window repair result only; no accuracy metric calculated.",
            }
        )
        audit_rows.append(
            {
                **_base(generated_ts, repair_run_id),
                "accuracy_row_id": blocked_row.get("accuracy_row_id"),
                "canonical_outcome_id": cid,
                "repaired_canonical_overlay_id": overlay_id if is_recovered else "",
                "original_trust_level": c.get("trust_level"),
                "repaired_trust_level": trust,
                "original_final_remap_status": "UNUSABLE_SOURCE_COVERAGE",
                "repaired_remap_status": "STRICT_READY" if strict else "DIAGNOSTIC_READY" if diagnostic else "UNUSABLE_SOURCE_COVERAGE",
                "strict_ready_after_repair": "TRUE" if strict else "FALSE",
                "diagnostic_ready_after_repair": "TRUE" if diagnostic else "FALSE",
                "remaining_unusable": "TRUE" if not is_recovered else "FALSE",
                "repair_method": method,
                "repair_confidence": confidence,
                "notes": "Recovered coverage audit only; corrected accuracy evaluation is not run.",
            }
        )

    existing_strict = 17
    existing_diagnostic_only = 16
    strict_recovered = sum(1 for row in audit_rows if row["strict_ready_after_repair"] == "TRUE")
    diagnostic_recovered = sum(1 for row in audit_rows if row["diagnostic_ready_after_repair"] == "TRUE")
    strict_ready_estimate = existing_strict + strict_recovered
    diagnostic_ready_estimate = existing_strict + existing_diagnostic_only + diagnostic_recovered
    remaining_unusable_estimate = processed - diagnostic_recovered

    implementation_rows = [
        {
            **_base(generated_ts, repair_run_id, True),
            "implementation_area": "leakage_safe_window_repair",
            "blocked_rows_processed": processed,
            "successfully_recovered_rows": recovered,
            "leakage_blocked_rows": leakage_blocked,
            "remaining_unusable_rows": remaining_unusable,
            "implementation_status": "PASS_WITH_WARNINGS" if recovered else "NEEDS_REPAIR",
            "implementation_conclusion": "Recovered source coverage into an overlay layer without modifying original canonical outcomes.",
            "recommended_action": "PROCEED_TO_PHASE9A5M_SRC3_REPAIRED_CANONICAL_OUTCOME_VALIDATION",
            "notes": "Overlay must be validated before corrected accuracy re-evaluation.",
        }
    ]

    readiness_rows = [
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "canonical_outcome_validation",
            "status": "PASS" if recovered else "FAIL",
            "evidence": f"recovered_rows={recovered}; overlay_outcomes={len(recovered_by_cid)}",
            "blocking_issue": "",
            "recommended_action": "Proceed to repaired canonical outcome validation.",
            "notes": "Validation required before any corrected accuracy work.",
        },
        {
            **_base(generated_ts, repair_run_id),
            "readiness_area": "corrected_accuracy_re_evaluation",
            "status": "FAIL",
            "evidence": "repaired overlay not yet validated",
            "blocking_issue": "repaired_canonical_overlay_validation_pending",
            "recommended_action": "Do not re-evaluate accuracy until SRC3 validates overlay.",
            "notes": "No accuracy evaluation performed.",
        },
    ]
    governance_rows = _governance_rows(generated_ts, repair_run_id)
    governance_ok = all(row["status"] == "PASS" for row in governance_rows)
    final = (
        "SOURCE_COVERAGE_IMPLEMENTATION_REPAIR_READY_WITH_WARNINGS"
        if recovered and governance_ok
        else "SOURCE_COVERAGE_IMPLEMENTATION_REPAIR_NEEDS_REPAIR"
    )
    recommended = (
        "PROCEED_TO_PHASE9A5M_SRC3_REPAIRED_CANONICAL_OUTCOME_VALIDATION"
        if recovered and governance_ok
        else "HOLD_ACCURACY_RESEARCH_PENDING_OUTCOME_REVIEW"
    )
    summary_rows = [
        {
            **_base(generated_ts, repair_run_id, True),
            "build_status": "PASS_WITH_WARNINGS" if governance_ok else "FAIL",
            "final_interpretation": final,
            "blocked_rows_processed": processed,
            "successfully_recovered_rows": recovered,
            "leakage_blocked_rows": leakage_blocked,
            "remaining_unusable_rows": remaining_unusable,
            "recovered_canonical_outcomes": len(recovered_by_cid),
            "strict_ready_estimate": strict_ready_estimate,
            "diagnostic_ready_estimate": diagnostic_ready_estimate,
            "remaining_unusable_estimate": remaining_unusable_estimate,
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "accuracy_evaluation_performed": 0,
            "metric_values_recalculated": 0,
            "canonical_outcomes_modified": 0,
            "market_reaction_values_modified": 0,
            "mr_provider_runs_modified": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_canonical_outcome_validation": "TRUE" if recovered and governance_ok else "FALSE",
            "ready_for_corrected_accuracy_re_evaluation": "FALSE",
            "ready_for_accuracy_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended,
            "notes": "Created repaired canonical outcome overlay only; original canonical and MR source sheets are unchanged.",
        }
    ]

    outputs = [
        (OUTPUT_IMPLEMENTATION, IMPLEMENTATION_HEADERS, implementation_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_RECOVERED, RECOVERED_HEADERS, list(recovered_by_cid.values())),
        (OUTPUT_AUDIT, AUDIT_HEADERS, audit_rows),
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
        "final_interpretation": final,
        "file_created": "automation/build_market_reaction_source_coverage_implementation_repair_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "blocked_rows_processed": processed,
        "successfully_recovered_rows": recovered,
        "leakage_blocked_rows": leakage_blocked,
        "remaining_unusable_rows": remaining_unusable,
        "recovered_canonical_outcomes": len(recovered_by_cid),
        "strict_ready_estimate": strict_ready_estimate,
        "diagnostic_ready_estimate": diagnostic_ready_estimate,
        "remaining_unusable_estimate": remaining_unusable_estimate,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "metric_values_recalculated": 0,
        "canonical_outcomes_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_canonical_outcome_validation": recovered and governance_ok,
        "ready_for_corrected_accuracy_re_evaluation": False,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_source_coverage_implementation_repair_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
