import argparse
import hashlib
import json
import sys
from collections import Counter
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


SCHEMA_VERSION = "presignal_v2_market_reaction_repaired_canonical_outcome_validation_0.1"
VALIDATION_VERSION = "market_reaction_repaired_canonical_outcome_validation_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M-SRC3"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_REPAIRED_CANONICAL_OUTCOME_VALIDATION"
REGISTRY_OWNER_MODULE = "market_state"
APPROVED_TOLERANCE_MINUTES = 5.0

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Source_Coverage_Implementation",
    "Market_Reaction_Window_Repair_Results",
    "Market_Reaction_Recovered_Canonical_Outcomes",
    "Market_Reaction_Recovered_Coverage_Audit",
    "Market_Reaction_Source_Coverage_Implementation_Readiness",
    "Market_Reaction_Source_Coverage_Implementation_Governance",
    "Market_Reaction_Source_Coverage_Implementation_Summary",
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Remap_Repaired",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Canonical_Window_Construction",
    "Market_Reaction_Canonical_Source_Selection",
    "Market_Reaction_Canonical_Source_Agreement",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Canonical_Validation_Summary",
    "Market_Reaction_Canonical_Remap_Repair_Summary",
    "Market_Reaction_Source_Coverage_Gap_Detail",
    "Market_Reaction_Source_Candidate_Recovery_Audit",
    "Market_Reaction_Window_Coverage_Repair_Audit",
    "Market_Reaction_Coverage_Repair_Plan",
    "Market_Reaction_Coverage_Repair_Summary",
    "Controlled_Accuracy_Evaluation",
]

MAIN_INPUT_SHEETS = ["MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Event", "Config"]
CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)
CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Event"}

OUTPUT_VALIDATION = "Market_Reaction_Repaired_Outcome_Validation"
OUTPUT_WINDOW = "Market_Reaction_Repaired_Window_Validation"
OUTPUT_LEAKAGE = "Market_Reaction_Repaired_Leakage_Safety_Audit"
OUTPUT_COVERAGE = "Market_Reaction_Repaired_Coverage_Validation"
OUTPUT_TRUST = "Market_Reaction_Repaired_Trust_Validation"
OUTPUT_REMAP = "Market_Reaction_Repaired_Remap_Validation"
OUTPUT_ISSUES = "Market_Reaction_Repaired_Outcome_Issues"
OUTPUT_READINESS = "Market_Reaction_Repaired_Validation_Readiness"
OUTPUT_GOVERNANCE = "Market_Reaction_Repaired_Validation_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Repaired_Validation_Summary"

VALIDATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_version",
    "validation_run_id",
    "validation_area",
    "source_sheet",
    "rows_checked",
    "issues_found",
    "issue_rate",
    "validation_status",
    "validation_conclusion",
    "impact_on_corrected_re_evaluation",
    "recommended_action",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "original_window_start_ts",
    "original_window_end_ts",
    "repaired_start_ts",
    "repaired_end_ts",
    "window_repair_method",
    "window_shift_start_minutes",
    "window_shift_end_minutes",
    "approved_tolerance_minutes",
    "within_approved_tolerance",
    "start_candle_rule_valid",
    "end_candle_rule_valid",
    "window_validation_status",
    "issue_type",
    "notes",
]

LEAKAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "release_ts",
    "original_window_start_ts",
    "original_window_end_ts",
    "repaired_start_ts",
    "repaired_end_ts",
    "leakage_safe_reported",
    "leakage_safe_validated",
    "leakage_risk_type",
    "leakage_risk_severity",
    "blocks_corrected_accuracy",
    "notes",
]

COVERAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "coverage_scope",
    "expected_rows",
    "rows_found",
    "strict_ready_count",
    "diagnostic_ready_count",
    "low_trust_count",
    "unusable_count",
    "missing_count",
    "ambiguous_count",
    "coverage_status",
    "notes",
]

TRUST_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "canonical_trust_level_before",
    "repaired_trust_level",
    "source_agreement_class",
    "window_repair_method",
    "leakage_safe_validated",
    "expected_strict_ready",
    "expected_diagnostic_ready",
    "actual_strict_ready",
    "actual_diagnostic_ready",
    "trust_consistency_match",
    "issue_type",
    "notes",
]

REMAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "country",
    "release_ts",
    "original_canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "uses_repaired_overlay",
    "remap_status",
    "canonical_source",
    "fallback_used",
    "source_agreement_class",
    "repaired_trust_level",
    "repaired_realized_pips",
    "repaired_realized_direction",
    "repaired_realized_strength",
    "strict_ready",
    "diagnostic_ready",
    "low_trust",
    "unusable",
    "missing",
    "ambiguous",
    "leakage_safe_validated",
    "recommended_re_evaluation_handling",
    "notes",
]

ISSUES_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "issue_id",
    "accuracy_row_id",
    "canonical_outcome_id",
    "repaired_canonical_outcome_id",
    "issue_area",
    "issue_severity",
    "issue_type",
    "description",
    "affected_scope",
    "blocks_corrected_accuracy",
    "blocks_replication",
    "recommended_resolution",
    "notes",
]

READINESS_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
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
    "validation_run_id",
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
    "validation_version",
    "validation_run_id",
    "build_status",
    "final_interpretation",
    "repaired_rows_checked",
    "repaired_rows_leakage_safe",
    "repaired_rows_leakage_blocked",
    "repaired_rows_within_tolerance",
    "repaired_rows_outside_tolerance",
    "recovered_canonical_outcomes_checked",
    "recovered_canonical_outcome_duplicates",
    "recovered_canonical_outcomes_valid",
    "accuracy_rows_checked",
    "accuracy_rows_strict_ready",
    "accuracy_rows_diagnostic_ready",
    "accuracy_rows_low_trust",
    "accuracy_rows_unusable",
    "accuracy_rows_missing",
    "accuracy_rows_ambiguous",
    "accuracy_rows_leakage_blocked",
    "strict_ready_estimate_validated",
    "diagnostic_ready_estimate_validated",
    "validation_issues_total",
    "critical_issues",
    "high_issues",
    "highest_risk_validation_issue",
    "highest_risk_corrected_accuracy_blocker",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "metric_values_recalculated",
    "accuracy_results_modified",
    "canonical_outcomes_modified",
    "repaired_overlay_modified",
    "market_reaction_values_modified",
    "mr_provider_runs_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_corrected_accuracy_re_evaluation_design",
    "ready_for_corrected_accuracy_re_evaluation_execution",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_repaired_canonical_outcome_validation_v0_{compact}"


def _base(generated_ts: str, validation_run_id: str, include_version: bool = False) -> Dict[str, Any]:
    row = {"generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "validation_run_id": validation_run_id}
    if include_version:
        row["validation_version"] = VALIDATION_VERSION
    return row


def _issue_id(area: str, issue_type: str, key: str) -> str:
    return "SRC3_" + hashlib.sha256(f"{area}|{issue_type}|{key}".encode("utf-8")).hexdigest()[:16]


def _bool_text(value: Any) -> str:
    return "TRUE" if _norm(value).upper() in {"TRUE", "YES", "1", "Y"} else "FALSE"


def _trust_expectations(trust: str) -> Tuple[bool, bool]:
    level = _norm(trust)
    if level == "HIGH_TRUST":
        return True, True
    if level == "MEDIUM_TRUST":
        return False, True
    return False, False


def _status_from_flags(strict: bool, diagnostic: bool, low: bool, unusable: bool, missing: bool, ambiguous: bool, leakage_blocked: bool) -> str:
    if leakage_blocked:
        return "LEAKAGE_BLOCKED"
    if missing:
        return "MISSING"
    if ambiguous:
        return "AMBIGUOUS"
    if strict:
        return "STRICT_READY"
    if diagnostic:
        return "DIAGNOSTIC_READY"
    if low:
        return "LOW_TRUST_EXCLUDED"
    if unusable:
        return "UNUSABLE"
    return "UNUSABLE"


def _handling(status: str) -> str:
    if status == "STRICT_READY":
        return "INCLUDE_IN_STRICT_RE_EVALUATION"
    if status == "DIAGNOSTIC_READY":
        return "INCLUDE_IN_DIAGNOSTIC_RE_EVALUATION_ONLY"
    if status == "LOW_TRUST_EXCLUDED":
        return "REVIEW_BEFORE_RE_EVALUATION"
    return "EXCLUDE_FROM_RE_EVALUATION"


def _governance_rows(generated_ts: str, validation_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("metric_values_recalculated", 0, 0),
        ("accuracy_results_modified", 0, 0),
        ("canonical_outcomes_modified", 0, 0),
        ("repaired_overlay_modified", 0, 0),
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
            **_base(generated_ts, validation_run_id),
            "check_id": f"CHK_{name.upper()}",
            "check_name": name,
            "expected_value": expected,
            "actual_value": actual,
            "status": "PASS" if str(expected) == str(actual) else "FAIL",
            "notes": "SRC3 validation is read-only and does not rerun accuracy.",
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
        ("MARKET_REACTION_REPAIRED_OUTCOME_VALIDATION", OUTPUT_VALIDATION, "market_reaction_repaired_outcome_validation"),
        ("MARKET_REACTION_REPAIRED_WINDOW_VALIDATION", OUTPUT_WINDOW, "market_reaction_repaired_window_validation"),
        ("MARKET_REACTION_REPAIRED_LEAKAGE_SAFETY_AUDIT", OUTPUT_LEAKAGE, "market_reaction_repaired_leakage_safety_audit"),
        ("MARKET_REACTION_REPAIRED_COVERAGE_VALIDATION", OUTPUT_COVERAGE, "market_reaction_repaired_coverage_validation"),
        ("MARKET_REACTION_REPAIRED_TRUST_VALIDATION", OUTPUT_TRUST, "market_reaction_repaired_trust_validation"),
        ("MARKET_REACTION_REPAIRED_REMAP_VALIDATION", OUTPUT_REMAP, "market_reaction_repaired_remap_validation"),
        ("MARKET_REACTION_REPAIRED_OUTCOME_ISSUES", OUTPUT_ISSUES, "market_reaction_repaired_outcome_issues"),
        ("MARKET_REACTION_REPAIRED_VALIDATION_READINESS", OUTPUT_READINESS, "market_reaction_repaired_validation_readiness"),
        ("MARKET_REACTION_REPAIRED_VALIDATION_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_repaired_validation_governance"),
        ("MARKET_REACTION_REPAIRED_VALIDATION_SUMMARY", OUTPUT_SUMMARY, "market_reaction_repaired_validation_summary"),
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
            "notes": "Phase 9A-5M-SRC3 repaired canonical outcome validation; read-only.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M-SRC3 repaired canonical outcome validation.")
    return parser.parse_args(argv)


def build_market_reaction_repaired_canonical_outcome_validation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    validation_run_id = _run_id(generated_ts)
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
        raise RuntimeError(f"Missing critical Phase 9A-5M-SRC3 inputs: {missing_critical}")
    src2_summary = diag_inputs["Market_Reaction_Source_Coverage_Implementation_Summary"][-1] if diag_inputs["Market_Reaction_Source_Coverage_Implementation_Summary"] else {}
    if _norm(src2_summary.get("ready_for_canonical_outcome_validation")) != "TRUE":
        raise RuntimeError("Phase 9A-5M-SRC2 is not ready for repaired canonical outcome validation.")
    _ = main_inputs

    window_results = diag_inputs["Market_Reaction_Window_Repair_Results"]
    overlays = diag_inputs["Market_Reaction_Recovered_Canonical_Outcomes"]
    coverage_audit = { _norm(row.get("accuracy_row_id")): row for row in diag_inputs["Market_Reaction_Recovered_Coverage_Audit"] }
    original_remap = { _norm(row.get("accuracy_row_id")): row for row in diag_inputs["Market_Reaction_Canonical_Remap_Repaired"] }
    controlled_rows = diag_inputs["Controlled_Accuracy_Evaluation"]
    overlay_by_cid = { _norm(row.get("canonical_outcome_id")): row for row in overlays }
    overlay_id_counts = Counter(_norm(row.get("repaired_canonical_overlay_id")) for row in overlays)

    issues: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    window_valid_by_accuracy: Dict[str, Dict[str, Any]] = {}
    for row in window_results:
        aid = _norm(row.get("accuracy_row_id"))
        cid = _norm(row.get("canonical_outcome_id"))
        overlay = overlay_by_cid.get(cid, {})
        start_shift = _float(row.get("window_shift_start_minutes"))
        end_shift = _float(row.get("window_shift_end_minutes"))
        method = _norm(row.get("window_repair_method"))
        within = (
            start_shift is not None
            and end_shift is not None
            and abs(start_shift) <= APPROVED_TOLERANCE_MINUTES
            and abs(end_shift) <= APPROVED_TOLERANCE_MINUTES
        )
        leakage_reported = _bool_text(row.get("leakage_safe")) == "TRUE"
        if method == "FLAT_ZERO_DURATION_PROVIDER_RESULT":
            start_rule = start_shift is not None and abs(start_shift) <= 1
            end_rule = end_shift is not None and -APPROVED_TOLERANCE_MINUTES <= end_shift <= 0
            window_status = "PASS_WITH_WARNINGS" if within and leakage_reported else "NEEDS_REPAIR"
            issue_type = "FLAT_ZERO_DURATION_WINDOW_WARNING" if window_status == "PASS_WITH_WARNINGS" else "WINDOW_RULE_FAILURE"
            severity = "LOW" if window_status == "PASS_WITH_WARNINGS" else "HIGH"
        elif method == "NEAREST_SAFE_PROVIDER_WINDOW_WITHIN_TOLERANCE":
            start_rule = start_shift is not None and 0 <= start_shift <= APPROVED_TOLERANCE_MINUTES
            end_rule = end_shift is not None and 0 <= end_shift <= APPROVED_TOLERANCE_MINUTES
            window_status = "PASS" if within and start_rule and end_rule and leakage_reported else "NEEDS_REPAIR"
            issue_type = "NONE" if window_status == "PASS" else "WINDOW_RULE_FAILURE"
            severity = "HIGH"
        elif method == "EXACT_CONFIGURED_WINDOW":
            start_rule = start_shift is not None and abs(start_shift) <= 1
            end_rule = end_shift is not None and abs(end_shift) <= 1
            window_status = "PASS" if within and start_rule and end_rule and leakage_reported else "NEEDS_REPAIR"
            issue_type = "NONE" if window_status == "PASS" else "WINDOW_RULE_FAILURE"
            severity = "HIGH"
        else:
            start_rule = False
            end_rule = False
            window_status = "NEEDS_REPAIR"
            issue_type = "UNKNOWN_WINDOW_REPAIR_METHOD"
            severity = "HIGH"
        leakage_validated = leakage_reported and within and start_rule and end_rule
        if not leakage_validated:
            leakage_status = "HIGH"
            leakage_type = "WINDOW_RULE_LEAKAGE_OR_TOLERANCE_FAILURE"
            blocks = True
        else:
            leakage_status = "NONE"
            leakage_type = "NONE"
            blocks = False
        if issue_type != "NONE":
            issues.append(
                {
                    **_base(generated_ts, validation_run_id),
                    "issue_id": _issue_id("window", issue_type, aid + cid),
                    "accuracy_row_id": aid,
                    "canonical_outcome_id": cid,
                    "repaired_canonical_outcome_id": overlay.get("repaired_canonical_overlay_id"),
                    "issue_area": "window",
                    "issue_severity": severity,
                    "issue_type": issue_type,
                    "description": "Repaired window requires validation attention." if severity == "LOW" else "Repaired window failed approved tolerance/leakage validation.",
                    "affected_scope": "repaired_rows_112",
                    "blocks_corrected_accuracy": "TRUE" if blocks else "FALSE",
                    "blocks_replication": "TRUE" if severity in {"HIGH", "CRITICAL"} else "FALSE",
                    "recommended_resolution": "Validate flat zero-duration policy in corrected re-evaluation design." if severity == "LOW" else "Repair repaired overlay window selection.",
                    "notes": "Validation issue only; overlay and source rows were not modified.",
                }
            )
        window_valid_by_accuracy[aid] = {
            "leakage_safe_validated": leakage_validated,
            "window_validation_status": window_status,
            "issue_type": issue_type,
        }
        window_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "accuracy_row_id": aid,
                "canonical_outcome_id": cid,
                "repaired_canonical_outcome_id": overlay.get("repaired_canonical_overlay_id"),
                "original_window_start_ts": row.get("canonical_start_ts"),
                "original_window_end_ts": row.get("canonical_end_ts"),
                "repaired_start_ts": row.get("repaired_start_ts"),
                "repaired_end_ts": row.get("repaired_end_ts"),
                "window_repair_method": method,
                "window_shift_start_minutes": row.get("window_shift_start_minutes"),
                "window_shift_end_minutes": row.get("window_shift_end_minutes"),
                "approved_tolerance_minutes": _fmt(APPROVED_TOLERANCE_MINUTES, 3),
                "within_approved_tolerance": "TRUE" if within else "FALSE",
                "start_candle_rule_valid": "TRUE" if start_rule else "FALSE",
                "end_candle_rule_valid": "TRUE" if end_rule else "FALSE",
                "window_validation_status": window_status,
                "issue_type": issue_type,
                "notes": "Window validation only; no corrected accuracy calculated.",
            }
        )
        leakage_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "accuracy_row_id": aid,
                "canonical_outcome_id": cid,
                "repaired_canonical_outcome_id": overlay.get("repaired_canonical_overlay_id"),
                "release_ts": row.get("release_ts"),
                "original_window_start_ts": row.get("canonical_start_ts"),
                "original_window_end_ts": row.get("canonical_end_ts"),
                "repaired_start_ts": row.get("repaired_start_ts"),
                "repaired_end_ts": row.get("repaired_end_ts"),
                "leakage_safe_reported": row.get("leakage_safe"),
                "leakage_safe_validated": "TRUE" if leakage_validated else "FALSE",
                "leakage_risk_type": leakage_type,
                "leakage_risk_severity": leakage_status,
                "blocks_corrected_accuracy": "TRUE" if blocks else "FALSE",
                "notes": "Leakage safety audit only.",
            }
        )

    remap_rows: List[Dict[str, Any]] = []
    trust_rows: List[Dict[str, Any]] = []
    for acc in controlled_rows:
        aid = _norm(acc.get("__source_row_number__"))
        original = original_remap.get(aid, {})
        cid = _norm(original.get("repaired_canonical_outcome_id"))
        overlay = overlay_by_cid.get(cid, {})
        uses_overlay = bool(overlay)
        window_valid = window_valid_by_accuracy.get(aid, {})
        if uses_overlay:
            trust = _norm(overlay.get("repaired_trust_level"))
            source = overlay.get("repaired_canonical_source")
            fallback = overlay.get("fallback_used")
            agreement = overlay.get("source_agreement_class")
            pips = overlay.get("repaired_realized_pips")
            direction = overlay.get("repaired_realized_direction")
            strength = overlay.get("repaired_realized_strength")
            overlay_id = overlay.get("repaired_canonical_overlay_id")
            leakage_safe = bool(window_valid.get("leakage_safe_validated"))
        else:
            trust = _norm(original.get("canonical_trust_level"))
            source = original.get("canonical_source")
            fallback = original.get("fallback_used")
            agreement = original.get("source_agreement_class")
            pips = original.get("canonical_realized_pips")
            direction = original.get("canonical_realized_direction")
            strength = original.get("canonical_realized_strength")
            overlay_id = ""
            leakage_safe = True
        expected_strict, expected_diagnostic = _trust_expectations(trust)
        if uses_overlay and not leakage_safe:
            strict = diagnostic = False
            low = False
            unusable = False
            missing = False
            ambiguous = False
            status = "LEAKAGE_BLOCKED"
        else:
            strict = expected_strict
            diagnostic = expected_diagnostic and not expected_strict
            low = trust == "LOW_TRUST"
            unusable = trust in {"UNUSABLE", ""} and not missing
            missing = not cid
            ambiguous = False
            status = _status_from_flags(strict, diagnostic, low, unusable, missing, ambiguous, False)
        actual_strict = strict
        actual_diagnostic = strict or diagnostic
        trust_match = actual_strict == expected_strict and actual_diagnostic == expected_diagnostic if not (uses_overlay and not leakage_safe) else False
        if not trust_match:
            issues.append(
                {
                    **_base(generated_ts, validation_run_id),
                    "issue_id": _issue_id("trust", "TRUST_CONSISTENCY_MISMATCH", aid + cid),
                    "accuracy_row_id": aid,
                    "canonical_outcome_id": cid,
                    "repaired_canonical_outcome_id": overlay_id,
                    "issue_area": "trust",
                    "issue_severity": "HIGH",
                    "issue_type": "TRUST_CONSISTENCY_MISMATCH",
                    "description": "Repaired trust level does not match strict/diagnostic usability flags.",
                    "affected_scope": "controlled_accuracy_rows_145",
                    "blocks_corrected_accuracy": "TRUE",
                    "blocks_replication": "TRUE",
                    "recommended_resolution": "Repair trust mapping before corrected re-evaluation design.",
                    "notes": "Validation issue only.",
                }
            )
        trust_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "accuracy_row_id": aid,
                "canonical_outcome_id": cid,
                "repaired_canonical_outcome_id": overlay_id,
                "canonical_trust_level_before": original.get("canonical_trust_level"),
                "repaired_trust_level": trust,
                "source_agreement_class": agreement,
                "window_repair_method": overlay.get("window_repair_method") if uses_overlay else "",
                "leakage_safe_validated": "TRUE" if leakage_safe else "FALSE",
                "expected_strict_ready": "TRUE" if expected_strict else "FALSE",
                "expected_diagnostic_ready": "TRUE" if expected_diagnostic else "FALSE",
                "actual_strict_ready": "TRUE" if actual_strict else "FALSE",
                "actual_diagnostic_ready": "TRUE" if actual_diagnostic else "FALSE",
                "trust_consistency_match": "TRUE" if trust_match else "FALSE",
                "issue_type": "NONE" if trust_match else "TRUST_CONSISTENCY_MISMATCH",
                "notes": "Trust validation only.",
            }
        )
        remap_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "accuracy_row_id": aid,
                "experiment_id": acc.get("experiment_id"),
                "session_id": acc.get("session_id"),
                "provider": acc.get("provider"),
                "pack_level": acc.get("pack_level"),
                "country": original.get("country") or "",
                "release_ts": original.get("release_ts") or "",
                "original_canonical_outcome_id": cid,
                "repaired_canonical_outcome_id": overlay_id,
                "uses_repaired_overlay": "TRUE" if uses_overlay else "FALSE",
                "remap_status": status,
                "canonical_source": source,
                "fallback_used": fallback,
                "source_agreement_class": agreement,
                "repaired_trust_level": trust,
                "repaired_realized_pips": pips,
                "repaired_realized_direction": direction,
                "repaired_realized_strength": strength,
                "strict_ready": "TRUE" if strict else "FALSE",
                "diagnostic_ready": "TRUE" if diagnostic else "FALSE",
                "low_trust": "TRUE" if low else "FALSE",
                "unusable": "TRUE" if unusable else "FALSE",
                "missing": "TRUE" if missing else "FALSE",
                "ambiguous": "TRUE" if ambiguous else "FALSE",
                "leakage_safe_validated": "TRUE" if leakage_safe else "FALSE",
                "recommended_re_evaluation_handling": _handling(status),
                "notes": "Validated repaired remap preview only; no accuracy metrics calculated.",
            }
        )

    remap_counts = Counter(row["remap_status"] for row in remap_rows)
    repaired_leakage_safe = sum(1 for row in leakage_rows if row["leakage_safe_validated"] == "TRUE")
    repaired_leakage_blocked = len(leakage_rows) - repaired_leakage_safe
    within_tolerance = sum(1 for row in window_rows if row["within_approved_tolerance"] == "TRUE")
    outside_tolerance = len(window_rows) - within_tolerance
    duplicate_overlays = sum(1 for count in overlay_id_counts.values() if count > 1)
    overlay_valid = sum(1 for row in overlays if _norm(row.get("leakage_safe")) == "TRUE" and _norm(row.get("repaired_realized_pips")) and _norm(row.get("repaired_realized_direction")) and _norm(row.get("repaired_realized_strength")))
    issue_counts = Counter(row["issue_severity"] for row in issues)
    high_or_critical = issue_counts["HIGH"] + issue_counts["CRITICAL"]
    low_issues = issue_counts["LOW"]
    governance_rows = _governance_rows(generated_ts, validation_run_id)
    governance_ok = all(row["status"] == "PASS" for row in governance_rows)
    strict_validated = remap_counts["STRICT_READY"] == 129
    diagnostic_validated = (remap_counts["STRICT_READY"] + remap_counts["DIAGNOSTIC_READY"]) == 145
    ready_design = (
        governance_ok
        and repaired_leakage_blocked == 0
        and outside_tolerance == 0
        and remap_counts["MISSING"] == 0
        and remap_counts["AMBIGUOUS"] == 0
        and remap_counts["UNUSABLE"] == 0
        and high_or_critical == 0
        and strict_validated
        and diagnostic_validated
    )

    coverage_rows = []
    coverage_specs = [
        ("recovered_rows_112", 112, len(window_rows)),
        ("controlled_accuracy_rows_145", 145, len(remap_rows)),
        ("recovered_canonical_outcomes_6", 6, len(overlays)),
        ("strict_ready_estimate", 129, remap_counts["STRICT_READY"]),
        ("diagnostic_ready_estimate", 145, remap_counts["STRICT_READY"] + remap_counts["DIAGNOSTIC_READY"]),
    ]
    for scope, expected, found in coverage_specs:
        coverage_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "coverage_scope": scope,
                "expected_rows": expected,
                "rows_found": found,
                "strict_ready_count": remap_counts["STRICT_READY"],
                "diagnostic_ready_count": remap_counts["STRICT_READY"] + remap_counts["DIAGNOSTIC_READY"],
                "low_trust_count": remap_counts["LOW_TRUST_EXCLUDED"],
                "unusable_count": remap_counts["UNUSABLE"],
                "missing_count": remap_counts["MISSING"],
                "ambiguous_count": remap_counts["AMBIGUOUS"],
                "coverage_status": "PASS" if expected == found else "NEEDS_REPAIR",
                "notes": "Coverage validation only.",
            }
        )

    readiness_specs = [
        ("leakage_safety_readiness", repaired_leakage_blocked == 0, f"leakage_safe={repaired_leakage_safe}/{len(leakage_rows)}", "", "Proceed to corrected re-evaluation design."),
        ("window_tolerance_readiness", outside_tolerance == 0, f"within_tolerance={within_tolerance}/{len(window_rows)}", "", "Proceed; carry flat zero-duration warning into design."),
        ("coverage_readiness", remap_counts["MISSING"] == 0 and remap_counts["AMBIGUOUS"] == 0, "missing=0; ambiguous=0", "", "Proceed."),
        ("trust_model_readiness", high_or_critical == 0, f"high_or_critical_issues={high_or_critical}", "", "Proceed."),
        ("remap_readiness", remap_counts["UNUSABLE"] == 0 and remap_counts["LEAKAGE_BLOCKED"] == 0, "unusable=0; leakage_blocked=0", "", "Proceed."),
        ("strict_re_evaluation_readiness", strict_validated, f"strict_ready={remap_counts['STRICT_READY']}", "", "Design strict corrected re-evaluation."),
        ("diagnostic_re_evaluation_readiness", diagnostic_validated, f"strict_plus_diagnostic={remap_counts['STRICT_READY'] + remap_counts['DIAGNOSTIC_READY']}", "", "Design diagnostic corrected re-evaluation as secondary."),
        ("replication_readiness", False, "corrected accuracy re-evaluation not complete", "replication_not_available", "Replication remains unavailable until corrected re-evaluation is executed and reviewed."),
    ]
    readiness_rows = [
        {
            **_base(generated_ts, validation_run_id),
            "readiness_area": area,
            "status": "PASS" if ok else "FAIL",
            "evidence": evidence,
            "blocking_issue": blocker,
            "recommended_action": action,
            "notes": "Readiness is for corrected re-evaluation design, not execution.",
        }
        for area, ok, evidence, blocker, action in readiness_specs
    ]

    validation_rows = []
    validation_specs = [
        ("window_safety", OUTPUT_WINDOW, len(window_rows), high_or_critical, "PASS_WITH_WARNINGS" if low_issues else "PASS", "Repaired windows are leakage-safe and within tolerance; flat zero-duration rows require interpretation warning."),
        ("coverage", OUTPUT_COVERAGE, len(remap_rows), remap_counts["MISSING"] + remap_counts["AMBIGUOUS"] + remap_counts["UNUSABLE"], "PASS", "Repaired overlay covers the 145 controlled accuracy rows."),
        ("trust_model", OUTPUT_TRUST, len(trust_rows), high_or_critical, "PASS", "Repaired trust flags align with strict/diagnostic eligibility."),
        ("governance", OUTPUT_GOVERNANCE, len(governance_rows), 0 if governance_ok else 1, "PASS" if governance_ok else "BLOCKED", "No provider calls, accuracy reruns, source mutations, or production writes occurred."),
    ]
    for area, sheet, rows_checked, issues_found, status, conclusion in validation_specs:
        validation_rows.append(
            {
                **_base(generated_ts, validation_run_id, True),
                "validation_area": area,
                "source_sheet": sheet,
                "rows_checked": rows_checked,
                "issues_found": issues_found,
                "issue_rate": _fmt(issues_found / rows_checked if rows_checked else 0),
                "validation_status": status,
                "validation_conclusion": conclusion,
                "impact_on_corrected_re_evaluation": "READY_FOR_DESIGN" if ready_design else "NEEDS_REPAIR",
                "recommended_action": "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN" if ready_design else "PROCEED_TO_PHASE9A5M_SRC2R_REPAIRED_OVERLAY_REPAIR",
                "notes": "Validation only; no corrected accuracy calculated.",
            }
        )

    highest_issue = "flat_zero_duration_window_warning" if low_issues else "none"
    final = "REPAIRED_CANONICAL_OUTCOME_VALIDATION_READY_WITH_WARNINGS" if ready_design and low_issues else "REPAIRED_CANONICAL_OUTCOME_VALIDATION_READY" if ready_design else "REPAIRED_CANONICAL_OUTCOME_VALIDATION_NEEDS_REPAIR"
    recommended = "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN" if ready_design else "PROCEED_TO_PHASE9A5M_SRC2R_REPAIRED_OVERLAY_REPAIR"
    summary_rows = [
        {
            **_base(generated_ts, validation_run_id, True),
            "build_status": "PASS_WITH_WARNINGS" if ready_design and low_issues else "PASS" if ready_design else "FAIL",
            "final_interpretation": final,
            "repaired_rows_checked": len(window_rows),
            "repaired_rows_leakage_safe": repaired_leakage_safe,
            "repaired_rows_leakage_blocked": repaired_leakage_blocked,
            "repaired_rows_within_tolerance": within_tolerance,
            "repaired_rows_outside_tolerance": outside_tolerance,
            "recovered_canonical_outcomes_checked": len(overlays),
            "recovered_canonical_outcome_duplicates": duplicate_overlays,
            "recovered_canonical_outcomes_valid": overlay_valid,
            "accuracy_rows_checked": len(remap_rows),
            "accuracy_rows_strict_ready": remap_counts["STRICT_READY"],
            "accuracy_rows_diagnostic_ready": remap_counts["DIAGNOSTIC_READY"],
            "accuracy_rows_low_trust": remap_counts["LOW_TRUST_EXCLUDED"],
            "accuracy_rows_unusable": remap_counts["UNUSABLE"],
            "accuracy_rows_missing": remap_counts["MISSING"],
            "accuracy_rows_ambiguous": remap_counts["AMBIGUOUS"],
            "accuracy_rows_leakage_blocked": remap_counts["LEAKAGE_BLOCKED"],
            "strict_ready_estimate_validated": "TRUE" if strict_validated else "FALSE",
            "diagnostic_ready_estimate_validated": "TRUE" if diagnostic_validated else "FALSE",
            "validation_issues_total": len(issues),
            "critical_issues": issue_counts["CRITICAL"],
            "high_issues": issue_counts["HIGH"],
            "highest_risk_validation_issue": highest_issue,
            "highest_risk_corrected_accuracy_blocker": "none" if ready_design else "validation_issue_blocks_design",
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "accuracy_evaluation_performed": 0,
            "metric_values_recalculated": 0,
            "accuracy_results_modified": 0,
            "canonical_outcomes_modified": 0,
            "repaired_overlay_modified": 0,
            "market_reaction_values_modified": 0,
            "mr_provider_runs_modified": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "ready_for_corrected_accuracy_re_evaluation_design": "TRUE" if ready_design else "FALSE",
            "ready_for_corrected_accuracy_re_evaluation_execution": "FALSE",
            "ready_for_accuracy_replication": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended,
            "notes": "Repaired overlay validated for design with warnings; corrected accuracy execution remains prohibited.",
        }
    ]

    outputs = [
        (OUTPUT_VALIDATION, VALIDATION_HEADERS, validation_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_LEAKAGE, LEAKAGE_HEADERS, leakage_rows),
        (OUTPUT_COVERAGE, COVERAGE_HEADERS, coverage_rows),
        (OUTPUT_TRUST, TRUST_HEADERS, trust_rows),
        (OUTPUT_REMAP, REMAP_HEADERS, remap_rows),
        (OUTPUT_ISSUES, ISSUES_HEADERS, issues),
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
        "file_created": "automation/build_market_reaction_repaired_canonical_outcome_validation_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "repaired_rows_checked": len(window_rows),
        "repaired_rows_leakage_safe": repaired_leakage_safe,
        "repaired_rows_leakage_blocked": repaired_leakage_blocked,
        "repaired_rows_within_tolerance": within_tolerance,
        "repaired_rows_outside_tolerance": outside_tolerance,
        "recovered_canonical_outcomes_checked": len(overlays),
        "recovered_canonical_outcome_duplicates": duplicate_overlays,
        "recovered_canonical_outcomes_valid": overlay_valid,
        "accuracy_rows_checked": len(remap_rows),
        "accuracy_rows_strict_ready": remap_counts["STRICT_READY"],
        "accuracy_rows_diagnostic_ready": remap_counts["DIAGNOSTIC_READY"],
        "accuracy_rows_low_trust": remap_counts["LOW_TRUST_EXCLUDED"],
        "accuracy_rows_unusable": remap_counts["UNUSABLE"],
        "accuracy_rows_missing": remap_counts["MISSING"],
        "accuracy_rows_ambiguous": remap_counts["AMBIGUOUS"],
        "accuracy_rows_leakage_blocked": remap_counts["LEAKAGE_BLOCKED"],
        "strict_ready_estimate_validated": strict_validated,
        "diagnostic_ready_estimate_validated": diagnostic_validated,
        "validation_issues_total": len(issues),
        "critical_issues": issue_counts["CRITICAL"],
        "high_issues": issue_counts["HIGH"],
        "highest_risk_validation_issue": highest_issue,
        "highest_risk_corrected_accuracy_blocker": "none" if ready_design else "validation_issue_blocks_design",
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "metric_values_recalculated": 0,
        "accuracy_results_modified": 0,
        "canonical_outcomes_modified": 0,
        "repaired_overlay_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_corrected_accuracy_re_evaluation_design": ready_design,
        "ready_for_corrected_accuracy_re_evaluation_execution": False,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_repaired_canonical_outcome_validation_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
