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


SCHEMA_VERSION = "presignal_v2_market_reaction_canonical_outcome_validation_0.1"
VALIDATION_VERSION = "market_reaction_canonical_outcome_validation_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M3"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION"
REGISTRY_OWNER_MODULE = "market_state"

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Source_Selection",
    "Market_Reaction_Canonical_Source_Agreement",
    "Market_Reaction_Canonical_Window_Construction",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Canonical_Implementation_Issues",
    "Market_Reaction_Canonical_Implementation_Governance",
    "Market_Reaction_Canonical_Implementation_Summary",
    "Market_Reaction_Canonical_Source_Review",
    "Market_Reaction_Source_Strategy_Comparison",
    "Market_Reaction_Source_Risk_Assessment",
    "Market_Reaction_Canonical_Window_Review",
    "Market_Reaction_Canonical_Matching_Review",
    "Market_Reaction_Canonical_Trust_Model",
    "Market_Reaction_Source_Selection_Decision",
    "Market_Reaction_Canonical_Source_Review_Summary",
    "Market_Reaction_Outcome_Integrity_Summary",
    "Market_Reaction_Outcome_Match_Audit",
    "Market_Reaction_Accuracy_Impact_Audit",
    "Market_Reaction_Source_Comparison_Audit",
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Comparison_Results",
    "Controlled_Accuracy_Metric_Results",
    "Controlled_Accuracy_Invalid_Output_Results",
    "Controlled_Accuracy_Evaluation_Summary",
]

MAIN_INPUT_SHEETS = [
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Outcome_Ledger",
    "Event",
    "Config",
]

CRITICAL_DIAG_SHEETS = {
    "Market_Reaction_Canonical_Outcomes",
    "Market_Reaction_Canonical_Outcome_Matching",
    "Market_Reaction_Canonical_Trust_Assessment",
    "Market_Reaction_Canonical_Implementation_Issues",
    "Market_Reaction_Canonical_Implementation_Governance",
    "Market_Reaction_Canonical_Implementation_Summary",
    "Market_Reaction_Source_Selection_Decision",
    "Market_Reaction_Canonical_Source_Review_Summary",
    "Market_Reaction_Outcome_Integrity_Summary",
    "Market_Reaction_Outcome_Match_Audit",
    "Market_Reaction_Accuracy_Impact_Audit",
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation_Summary",
}
CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Config"}

OUTPUT_VALIDATION = "Market_Reaction_Canonical_Validation"
OUTPUT_COVERAGE = "Market_Reaction_Canonical_Coverage_Validation"
OUTPUT_TRUST = "Market_Reaction_Canonical_Trust_Validation"
OUTPUT_UNUSABLE = "Market_Reaction_Canonical_Unusable_Audit"
OUTPUT_MATCH = "Market_Reaction_Canonical_Match_Validation"
OUTPUT_REMAP = "Market_Reaction_Accuracy_Row_Remap_Preview"
OUTPUT_DISAGREEMENT = "Market_Reaction_Canonical_Disagreement_Validation"
OUTPUT_WINDOW = "Market_Reaction_Canonical_Window_Validation"
OUTPUT_ISSUES = "Market_Reaction_Canonical_Validation_Issues"
OUTPUT_GOVERNANCE = "Market_Reaction_Canonical_Validation_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Canonical_Validation_Summary"

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
    "impact_on_accuracy_re_evaluation",
    "recommended_action",
    "notes",
]

COVERAGE_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "coverage_scope",
    "expected_count",
    "canonical_outcomes_found",
    "high_trust_count",
    "medium_trust_count",
    "low_trust_count",
    "unusable_count",
    "strict_usable_count",
    "diagnostic_usable_count",
    "coverage_rate",
    "strict_usable_rate",
    "diagnostic_usable_rate",
    "coverage_status",
    "notes",
]

TRUST_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "canonical_outcome_id",
    "source_selection_status",
    "agreement_class",
    "window_status",
    "boundary_risk",
    "trust_level",
    "usable_for_strict_accuracy",
    "usable_for_diagnostic_accuracy",
    "expected_strict_usable",
    "expected_diagnostic_usable",
    "trust_consistency_match",
    "issue_type",
    "notes",
]

UNUSABLE_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "canonical_outcome_id",
    "country",
    "event_id",
    "batch_id",
    "session_id",
    "release_ts",
    "issue_count",
    "primary_unusable_reason",
    "secondary_unusable_reason",
    "source_issue",
    "window_issue",
    "matching_issue",
    "agreement_issue",
    "implementation_issue",
    "recommended_repair_type",
    "blocks_strict_accuracy",
    "blocks_diagnostic_accuracy",
    "notes",
]

MATCH_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "canonical_outcome_id",
    "country",
    "event_id",
    "batch_id",
    "session_id",
    "release_ts",
    "window_policy",
    "window_minutes",
    "matched_mr_provider_rows",
    "matched_evaluation_rows",
    "matched_accuracy_rows",
    "match_status",
    "canonical_id_unique",
    "ambiguity_resolved",
    "duplicate_risk",
    "missing_reference",
    "validation_status",
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
    "original_matched_outcome_source",
    "canonical_outcome_id",
    "canonical_match_status",
    "canonical_trust_level",
    "canonical_source",
    "fallback_used",
    "source_agreement_class",
    "canonical_realized_pips",
    "canonical_realized_direction",
    "canonical_realized_strength",
    "usable_for_strict_accuracy",
    "usable_for_diagnostic_accuracy",
    "original_accuracy_label_sensitivity",
    "remap_status",
    "recommended_re_evaluation_handling",
    "notes",
]

DISAGREEMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "canonical_outcome_id",
    "provider_sources_available",
    "pair_count",
    "max_pips_difference",
    "direction_disagreement_count",
    "strength_disagreement_count",
    "reported_agreement_class",
    "expected_agreement_class",
    "agreement_class_match",
    "trust_impact",
    "issue_type",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "canonical_outcome_id",
    "release_ts",
    "canonical_start_ts",
    "canonical_end_ts",
    "window_policy",
    "window_minutes",
    "horizon_source",
    "window_status",
    "expected_window_status",
    "window_status_match",
    "start_price_available",
    "end_price_available",
    "candle_count",
    "window_validation_status",
    "issue_type",
    "notes",
]

ISSUE_HEADERS = [
    "generated_ts",
    "schema_version",
    "validation_run_id",
    "issue_id",
    "canonical_outcome_id",
    "accuracy_row_id",
    "issue_area",
    "issue_severity",
    "issue_type",
    "description",
    "affected_scope",
    "affected_metric",
    "blocks_corrected_accuracy",
    "blocks_replication",
    "recommended_resolution",
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
    "canonical_outcomes_checked",
    "canonical_id_duplicates",
    "canonical_matches_ambiguous",
    "canonical_matches_missing",
    "canonical_outcomes_high_trust",
    "canonical_outcomes_medium_trust",
    "canonical_outcomes_low_trust",
    "canonical_outcomes_unusable",
    "strict_usable_count",
    "diagnostic_usable_count",
    "unusable_count",
    "accuracy_rows_checked",
    "accuracy_rows_strict_ready",
    "accuracy_rows_diagnostic_only",
    "accuracy_rows_low_trust",
    "accuracy_rows_unusable",
    "accuracy_rows_missing_canonical_match",
    "accuracy_rows_ambiguous_canonical_match",
    "primary_unusable_reason",
    "highest_risk_validation_issue",
    "highest_risk_accuracy_re_evaluation_blocker",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "accuracy_results_modified",
    "canonical_outcomes_modified",
    "market_reaction_values_modified",
    "mr_provider_runs_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_corrected_accuracy_re_evaluation",
    "ready_for_accuracy_replication",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


def _float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _fmt(value: Optional[float], digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _rate(part: int, whole: int) -> str:
    return _fmt(part / whole) if whole else ""


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_canonical_outcome_validation_v0_{compact}"


def _base(generated_ts: str, validation_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "validation_run_id": validation_run_id,
    }


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(
    service,
    spreadsheet_id: str,
    titles: Set[str],
    sheet_name: str,
    missing: List[str],
) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _get_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
    )
    values = result.get("values", [])
    return values[0] if values else []


def _ensure_sheet_minimal(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: Sequence[str],
    data_row_count: int,
) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                                "gridProperties": {
                                    "rowCount": max(1, data_row_count + 1),
                                    "columnCount": max(1, len(required_headers)),
                                },
                            }
                        }
                    }
                ]
            },
        ).execute()
        headers = list(required_headers)
    else:
        headers = _get_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in headers:
                headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _issue_id(scope: str, issue_type: str, key: str) -> str:
    return "VAL_" + hashlib.sha256(f"{scope}|{issue_type}|{key}".encode("utf-8")).hexdigest()[:16]


def _accuracy_key(row: Dict[str, Any]) -> Tuple[str, str]:
    raw = _norm(row.get("outcome_match_key"))
    if "|" in raw:
        country, release_ts = raw.split("|", 1)
        return country, release_ts
    return "", ""


def _split_tokens(raw: Any) -> Set[str]:
    return {token for token in _norm(raw).split("|") if token}


def _trust_rank(row: Dict[str, Any]) -> int:
    return {
        "HIGH_TRUST": 4,
        "MEDIUM_TRUST": 3,
        "LOW_TRUST": 2,
        "UNUSABLE": 1,
    }.get(_norm(row.get("trust_level")), 0)


def _select_canonical_candidate(
    candidates: Sequence[Dict[str, Any]],
    match_audit_row: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], str, bool, str]:
    if not candidates:
        return None, "MISSING", False, "No canonical outcome matched country + release_ts."
    if len(candidates) == 1:
        return candidates[0], "MATCHED_CANONICAL", False, "Unique country + release_ts canonical outcome."

    event_ids = _split_tokens(match_audit_row.get("matched_event_id"))
    batch_ids = _split_tokens(match_audit_row.get("matched_batch_id"))
    scoped = [
        row
        for row in candidates
        if _norm(row.get("event_id")) in event_ids or _norm(row.get("batch_id")) in batch_ids
    ]
    batch_scoped = [row for row in scoped if _norm(row.get("batch_id")) in batch_ids]
    if len(batch_scoped) == 1:
        return batch_scoped[0], "MATCHED_CANONICAL", False, "Canonical outcome resolved through prior batch_id audit key."
    if len(scoped) == 1:
        return scoped[0], "MATCHED_CANONICAL", False, "Canonical outcome resolved through prior event_id audit key."

    pool = batch_scoped or scoped or list(candidates)
    best_rank = max((_trust_rank(row) for row in pool), default=0)
    top = [row for row in pool if _trust_rank(row) == best_rank]
    if len(top) == 1:
        return top[0], "MATCHED_WITH_WARNING", False, "Multiple release-level candidates; unique highest-trust canonical outcome selected for preview."
    selected = top[0] if top else pool[0]
    return selected, "AMBIGUOUS", True, "Multiple canonical outcomes remain plausible for the historical release-level accuracy key."


def _expected_trust_flags(trust_level: str) -> Tuple[str, str]:
    if trust_level == "HIGH_TRUST":
        return "TRUE", "TRUE"
    if trust_level == "MEDIUM_TRUST":
        return "FALSE", "TRUE"
    return "FALSE", "FALSE"


def _build_indexes(
    outcomes: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str], List[Dict[str, Any]]], Counter[str]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_country_release: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    id_counts: Counter[str] = Counter()
    for row in outcomes:
        cid = _norm(row.get("canonical_outcome_id"))
        id_counts[cid] += 1
        by_id.setdefault(cid, row)
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if key != ("", ""):
            by_country_release[key].append(row)
    return by_id, by_country_release, id_counts


def _issue_from_impl(issues: Sequence[Dict[str, Any]], canonical_outcome_id: str) -> List[Dict[str, Any]]:
    return [row for row in issues if _norm(row.get("canonical_outcome_id")) == canonical_outcome_id]


def _unusable_reason(issue_rows: Sequence[Dict[str, Any]], trust_row: Dict[str, Any], matching_row: Dict[str, Any]) -> Tuple[str, str, bool, bool, bool, bool, bool, str]:
    issue_types = [_norm(row.get("issue_type")) for row in issue_rows]
    areas = [_norm(row.get("issue_area")) for row in issue_rows]
    source_issue = any(area == "source_selection" or "SOURCE" in issue for area, issue in zip(areas, issue_types))
    window_issue = any(area == "window" or "WINDOW" in issue or "CANDLE" in issue for area, issue in zip(areas, issue_types))
    matching_issue = _norm(matching_row.get("match_status")) in {"NO_MATCH", "AMBIGUOUS"} or _norm(matching_row.get("ambiguity_resolved")) != "TRUE"
    agreement_issue = any(area == "source_agreement" for area in areas) or _norm(trust_row.get("agreement_class")) in {"HIGH_DISAGREEMENT", "UNUSABLE"}
    implementation_issue = any(area in {"source_hierarchy", "threshold_boundary"} for area in areas)
    if source_issue:
        primary = "source_coverage"
        repair = "SOURCE_COVERAGE_REPAIR"
    elif window_issue:
        primary = "window_construction"
        repair = "WINDOW_POLICY_REPAIR"
    elif matching_issue:
        primary = "matching"
        repair = "MATCHING_REPAIR"
    elif agreement_issue:
        primary = "source_disagreement"
        repair = "SOURCE_HIERARCHY_REPAIR"
    elif implementation_issue:
        primary = "implementation_logic"
        repair = "IMPLEMENTATION_REPAIR"
    else:
        primary = "unclassified"
        repair = "MANUAL_REVIEW"
    secondary = "|".join(sorted(set(issue_types)))[:500]
    return primary, secondary, source_issue, window_issue, matching_issue, agreement_issue, implementation_issue, repair


def _validation_issue(
    generated_ts: str,
    validation_run_id: str,
    canonical_outcome_id: str,
    accuracy_row_id: str,
    area: str,
    severity: str,
    issue_type: str,
    description: str,
    affected_scope: str,
    affected_metric: str,
    blocks_corrected: bool,
    blocks_replication: bool,
    resolution: str,
) -> Dict[str, Any]:
    return {
        **_base(generated_ts, validation_run_id),
        "issue_id": _issue_id(area, issue_type, canonical_outcome_id + "|" + accuracy_row_id),
        "canonical_outcome_id": canonical_outcome_id,
        "accuracy_row_id": accuracy_row_id,
        "issue_area": area,
        "issue_severity": severity,
        "issue_type": issue_type,
        "description": description,
        "affected_scope": affected_scope,
        "affected_metric": affected_metric,
        "blocks_corrected_accuracy": "TRUE" if blocks_corrected else "FALSE",
        "blocks_replication": "TRUE" if blocks_replication else "FALSE",
        "recommended_resolution": resolution,
        "notes": "Validation issue only; no source/canonical/accuracy rows modified.",
    }


def _build_governance_rows(generated_ts: str, validation_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
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
    for name, expected, actual in checks:
        row = _base(generated_ts, validation_run_id)
        row.update(
            {
                "check_id": f"CHK_{name.upper()}",
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Canonical validation is read-only and does not rerun accuracy.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet_minimal(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS, 1)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_CANONICAL_VALIDATION", OUTPUT_VALIDATION, "market_reaction_canonical_validation"),
        ("MARKET_REACTION_CANONICAL_COVERAGE_VALIDATION", OUTPUT_COVERAGE, "market_reaction_canonical_coverage_validation"),
        ("MARKET_REACTION_CANONICAL_TRUST_VALIDATION", OUTPUT_TRUST, "market_reaction_canonical_trust_validation"),
        ("MARKET_REACTION_CANONICAL_UNUSABLE_AUDIT", OUTPUT_UNUSABLE, "market_reaction_canonical_unusable_audit"),
        ("MARKET_REACTION_CANONICAL_MATCH_VALIDATION", OUTPUT_MATCH, "market_reaction_canonical_match_validation"),
        ("MARKET_REACTION_ACCURACY_ROW_REMAP_PREVIEW", OUTPUT_REMAP, "market_reaction_accuracy_row_remap_preview"),
        ("MARKET_REACTION_CANONICAL_DISAGREEMENT_VALIDATION", OUTPUT_DISAGREEMENT, "market_reaction_canonical_disagreement_validation"),
        ("MARKET_REACTION_CANONICAL_WINDOW_VALIDATION", OUTPUT_WINDOW, "market_reaction_canonical_window_validation"),
        ("MARKET_REACTION_CANONICAL_VALIDATION_ISSUES", OUTPUT_ISSUES, "market_reaction_canonical_validation_issues"),
        ("MARKET_REACTION_CANONICAL_VALIDATION_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_canonical_validation_governance"),
        ("MARKET_REACTION_CANONICAL_VALIDATION_SUMMARY", OUTPUT_SUMMARY, "market_reaction_canonical_validation_summary"),
    ]
    updates = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
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
            "notes": "Phase 9A-5M3 canonical outcome validation; read-only validation.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M3 canonical outcome validation.")
    return parser.parse_args(argv)


def build_market_reaction_canonical_outcome_validation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
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
        raise RuntimeError(f"Missing critical Phase 9A-5M3 inputs: {missing_critical}")
    _ = main_inputs

    impl_summary = _latest(diag_inputs["Market_Reaction_Canonical_Implementation_Summary"])
    if _norm(impl_summary.get("ready_for_canonical_outcome_validation")) != "TRUE":
        raise RuntimeError("Phase 9A-5M2 is not ready for canonical outcome validation.")

    outcomes = diag_inputs["Market_Reaction_Canonical_Outcomes"]
    matching = diag_inputs["Market_Reaction_Canonical_Outcome_Matching"]
    trust = diag_inputs["Market_Reaction_Canonical_Trust_Assessment"]
    impl_issues = diag_inputs["Market_Reaction_Canonical_Implementation_Issues"]
    agreement = diag_inputs["Market_Reaction_Canonical_Source_Agreement"]
    window = diag_inputs["Market_Reaction_Canonical_Window_Construction"]
    accuracy_rows = diag_inputs["Controlled_Accuracy_Evaluation"]
    impact_rows = diag_inputs["Market_Reaction_Accuracy_Impact_Audit"]
    outcome_match_audit_rows = diag_inputs["Market_Reaction_Outcome_Match_Audit"]

    by_id, by_country_release, id_counts = _build_indexes(outcomes)
    matching_by_id = {_norm(row.get("canonical_outcome_id")): row for row in matching}
    trust_by_id = {_norm(row.get("canonical_outcome_id")): row for row in trust}
    window_by_id = {_norm(row.get("canonical_outcome_id")): row for row in window}
    impact_by_accuracy = {_norm(row.get("accuracy_row_id")): row for row in impact_rows}
    match_audit_by_accuracy = {_norm(row.get("accuracy_row_id")): row for row in outcome_match_audit_rows}
    issue_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for issue in impl_issues:
        issue_by_id[_norm(issue.get("canonical_outcome_id"))].append(issue)
    agreement_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in agreement:
        agreement_by_id[_norm(row.get("canonical_outcome_id"))].append(row)

    validation_issues: List[Dict[str, Any]] = []
    trust_rows: List[Dict[str, Any]] = []
    unusable_rows: List[Dict[str, Any]] = []
    match_rows: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []
    disagreement_rows: List[Dict[str, Any]] = []

    duplicate_ids = {cid for cid, count in id_counts.items() if count > 1 and cid}
    for outcome in outcomes:
        cid = _norm(outcome.get("canonical_outcome_id"))
        trust_row = trust_by_id.get(cid, {})
        matching_row = matching_by_id.get(cid, {})
        window_row = window_by_id.get(cid, {})
        impl_issue_rows = issue_by_id.get(cid, [])
        strict_expected, diagnostic_expected = _expected_trust_flags(_norm(outcome.get("trust_level")))
        strict_actual = _norm(outcome.get("usable_for_strict_accuracy"))
        diagnostic_actual = _norm(outcome.get("usable_for_diagnostic_accuracy"))
        consistency = strict_actual == strict_expected and diagnostic_actual == diagnostic_expected
        issue_type = "NONE" if consistency else "TRUST_FLAG_MISMATCH"
        if not consistency:
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    "",
                    "trust",
                    "HIGH",
                    issue_type,
                    "Trust level and usability flags are inconsistent with approved trust model.",
                    "canonical_outcome",
                    "all",
                    True,
                    True,
                    "Repair trust mapping before corrected accuracy re-evaluation.",
                )
            )
        trust_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "canonical_outcome_id": cid,
                "source_selection_status": trust_row.get("source_selection_status"),
                "agreement_class": outcome.get("source_agreement_class"),
                "window_status": window_row.get("window_status"),
                "boundary_risk": outcome.get("boundary_risk"),
                "trust_level": outcome.get("trust_level"),
                "usable_for_strict_accuracy": strict_actual,
                "usable_for_diagnostic_accuracy": diagnostic_actual,
                "expected_strict_usable": strict_expected,
                "expected_diagnostic_usable": diagnostic_expected,
                "trust_consistency_match": "TRUE" if consistency else "FALSE",
                "issue_type": issue_type,
                "notes": "Trust validation only; canonical outcome rows are read-only.",
            }
        )
        unique = cid not in duplicate_ids
        source_match_status = _norm(matching_row.get("match_status"))
        ambiguity = _norm(matching_row.get("ambiguity_resolved")) == "TRUE"
        missing_reference = _norm(matching_row.get("match_status")) == "NO_MATCH"
        if unique and ambiguity and source_match_status == "MATCHED_CANONICAL":
            match_status = "PASS"
        elif unique and source_match_status == "MATCHED_WITH_WARNING":
            match_status = "PASS_WITH_WARNINGS"
        else:
            match_status = "NEEDS_REPAIR"
        if not unique:
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    "",
                    "matching",
                    "CRITICAL",
                    "CANONICAL_ID_DUPLICATE",
                    "canonical_outcome_id is not unique.",
                    "canonical_outcome",
                    "all",
                    True,
                    True,
                    "Repair canonical ID construction.",
                )
            )
        if source_match_status == "AMBIGUOUS":
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    "",
                    "matching",
                    "HIGH",
                    "AMBIGUITY_NOT_RESOLVED",
                    "Canonical matching did not resolve ambiguity.",
                    "canonical_outcome",
                    "all",
                    True,
                    True,
                    "Repair canonical matching hierarchy.",
                )
            )
        elif source_match_status == "MATCHED_WITH_WARNING" or not ambiguity:
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    "",
                    "matching",
                    "LOW",
                    "MATCHED_WITH_WARNING",
                    "Canonical ID is unique, but country+release fallback remains warning-only.",
                    "canonical_outcome",
                    "corrected_accuracy_re_evaluation",
                    False,
                    False,
                    "Use canonical_outcome_id instead of release-level fallback in corrected re-evaluation.",
                )
            )
        match_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "canonical_outcome_id": cid,
                "country": outcome.get("country"),
                "event_id": outcome.get("event_id"),
                "batch_id": outcome.get("batch_id"),
                "session_id": outcome.get("session_id"),
                "release_ts": outcome.get("release_ts"),
                "window_policy": outcome.get("window_policy"),
                "window_minutes": outcome.get("window_minutes"),
                "matched_mr_provider_rows": matching_row.get("matched_mr_provider_rows"),
                "matched_evaluation_rows": matching_row.get("matched_evaluation_rows"),
                "matched_accuracy_rows": matching_row.get("matched_accuracy_rows"),
                "match_status": matching_row.get("match_status"),
                "canonical_id_unique": "TRUE" if unique else "FALSE",
                "ambiguity_resolved": matching_row.get("ambiguity_resolved"),
                "duplicate_risk": matching_row.get("duplicate_risk"),
                "missing_reference": "TRUE" if missing_reference else "FALSE",
                "validation_status": match_status,
                "notes": "Canonical matching validation; no rematching written to source evaluation sheets.",
            }
        )
        expected_window_status = "PASS" if _norm(outcome.get("trust_level")) in {"HIGH_TRUST", "MEDIUM_TRUST", "LOW_TRUST"} else _norm(window_row.get("window_status"))
        window_match = _norm(window_row.get("window_status")) == expected_window_status
        window_validation_status = "PASS" if window_match and _norm(window_row.get("window_status")) == "PASS" else "UNUSABLE" if _norm(window_row.get("window_confidence")) == "UNUSABLE" else "NEEDS_REPAIR"
        window_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "canonical_outcome_id": cid,
                "release_ts": outcome.get("release_ts"),
                "canonical_start_ts": window_row.get("canonical_start_ts"),
                "canonical_end_ts": window_row.get("canonical_end_ts"),
                "window_policy": window_row.get("window_policy"),
                "window_minutes": window_row.get("window_minutes"),
                "horizon_source": window_row.get("horizon_source"),
                "window_status": window_row.get("window_status"),
                "expected_window_status": expected_window_status,
                "window_status_match": "TRUE" if window_match else "FALSE",
                "start_price_available": window_row.get("start_price_available"),
                "end_price_available": window_row.get("end_price_available"),
                "candle_count": window_row.get("candle_count"),
                "window_validation_status": window_validation_status,
                "issue_type": window_row.get("issue_type"),
                "notes": "Window construction validation only.",
            }
        )
        pairs = agreement_by_id.get(cid, [])
        max_diff = max((_float(row.get("pips_difference")) or 0 for row in pairs), default=0)
        direction_disagree = sum(1 for row in pairs if _norm(row.get("direction_agreement")) != "TRUE")
        strength_disagree = sum(1 for row in pairs if _norm(row.get("strength_agreement")) != "TRUE")
        if not pairs:
            expected_agreement = "UNUSABLE"
        elif direction_disagree or max_diff >= 5:
            expected_agreement = "HIGH_DISAGREEMENT"
        elif max_diff > 1 or strength_disagree:
            expected_agreement = "MODERATE_DISAGREEMENT"
        else:
            expected_agreement = "LOW_DISAGREEMENT"
        reported_agreement = _norm(outcome.get("source_agreement_class"))
        agreement_match = expected_agreement == reported_agreement
        if not agreement_match:
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    "",
                    "agreement",
                    "HIGH",
                    "AGREEMENT_CLASS_MISMATCH",
                    "Reported agreement class does not match approved disagreement policy.",
                    "canonical_outcome",
                    "all",
                    True,
                    True,
                    "Repair source agreement classification.",
                )
            )
        disagreement_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "canonical_outcome_id": cid,
                "provider_sources_available": outcome.get("provider_sources_available"),
                "pair_count": len(pairs),
                "max_pips_difference": _fmt(max_diff),
                "direction_disagreement_count": direction_disagree,
                "strength_disagreement_count": strength_disagree,
                "reported_agreement_class": reported_agreement,
                "expected_agreement_class": expected_agreement,
                "agreement_class_match": "TRUE" if agreement_match else "FALSE",
                "trust_impact": outcome.get("trust_level"),
                "issue_type": "NONE" if agreement_match else "AGREEMENT_CLASS_MISMATCH",
                "notes": "Disagreement validation uses approved LOW/MODERATE/HIGH/UNUSABLE policy.",
            }
        )
        if _norm(outcome.get("trust_level")) == "UNUSABLE":
            primary, secondary, source_issue, window_issue, matching_issue, agreement_issue, implementation_issue, repair = _unusable_reason(impl_issue_rows, trust_row, matching_row)
            unusable_rows.append(
                {
                    **_base(generated_ts, validation_run_id),
                    "canonical_outcome_id": cid,
                    "country": outcome.get("country"),
                    "event_id": outcome.get("event_id"),
                    "batch_id": outcome.get("batch_id"),
                    "session_id": outcome.get("session_id"),
                    "release_ts": outcome.get("release_ts"),
                    "issue_count": outcome.get("issue_count"),
                    "primary_unusable_reason": primary,
                    "secondary_unusable_reason": secondary,
                    "source_issue": "TRUE" if source_issue else "FALSE",
                    "window_issue": "TRUE" if window_issue else "FALSE",
                    "matching_issue": "TRUE" if matching_issue else "FALSE",
                    "agreement_issue": "TRUE" if agreement_issue else "FALSE",
                    "implementation_issue": "TRUE" if implementation_issue else "FALSE",
                    "recommended_repair_type": repair,
                    "blocks_strict_accuracy": "TRUE",
                    "blocks_diagnostic_accuracy": "TRUE",
                    "notes": "Only UNUSABLE canonical outcomes are listed here to keep output compact.",
                }
            )

    remap_rows: List[Dict[str, Any]] = []
    for acc in accuracy_rows:
        country, release_ts = _accuracy_key(acc)
        candidates = by_country_release.get((country, release_ts), [])
        match_audit_row = match_audit_by_accuracy.get(_norm(acc.get("__source_row_number__")), {})
        canonical, canonical_match_status, remap_ambiguous, remap_note = _select_canonical_candidate(candidates, match_audit_row)
        cid = _norm(canonical.get("canonical_outcome_id")) if canonical else ""
        trust_level = _norm(canonical.get("trust_level")) if canonical else ""
        strict = _norm(canonical.get("usable_for_strict_accuracy")) == "TRUE" if canonical else False
        diagnostic = _norm(canonical.get("usable_for_diagnostic_accuracy")) == "TRUE" if canonical else False
        if canonical is None:
            remap_status = "REMAP_MISSING"
            handling = "EXCLUDE_FROM_RE_EVALUATION"
        elif remap_ambiguous:
            remap_status = "REMAP_AMBIGUOUS"
            handling = "REVIEW_BEFORE_RE_EVALUATION"
        elif strict:
            remap_status = "REMAP_STRICT_READY"
            handling = "INCLUDE_IN_STRICT_RE_EVALUATION"
        elif diagnostic:
            remap_status = "REMAP_DIAGNOSTIC_ONLY"
            handling = "INCLUDE_IN_DIAGNOSTIC_RE_EVALUATION_ONLY"
        elif trust_level == "LOW_TRUST":
            remap_status = "REMAP_LOW_TRUST"
            handling = "REVIEW_BEFORE_RE_EVALUATION"
        else:
            remap_status = "REMAP_UNUSABLE"
            handling = "EXCLUDE_FROM_RE_EVALUATION"
        sensitivity = _norm((impact_by_accuracy.get(_norm(acc.get("__source_row_number__"))) or {}).get("accuracy_label_sensitivity"))
        if remap_status in {"REMAP_MISSING", "REMAP_AMBIGUOUS", "REMAP_UNUSABLE"}:
            validation_issues.append(
                _validation_issue(
                    generated_ts,
                    validation_run_id,
                    cid,
                    _norm(acc.get("__source_row_number__")),
                    "accuracy_remap",
                    "HIGH" if remap_status != "REMAP_MISSING" else "CRITICAL",
                    remap_status,
                    "Controlled accuracy row is not strict-ready under canonical outcome validation.",
                    "controlled_accuracy_rows_145",
                    "corrected_accuracy_re_evaluation",
                    remap_status != "REMAP_DIAGNOSTIC_ONLY",
                    True,
                    "Review canonical matching/trust before corrected re-evaluation.",
                )
            )
        remap_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "accuracy_row_id": acc.get("__source_row_number__"),
                "experiment_id": acc.get("experiment_id"),
                "session_id": acc.get("session_id"),
                "provider": acc.get("provider"),
                "pack_level": acc.get("pack_level"),
                "country": country,
                "release_ts": release_ts,
                "original_matched_outcome_source": acc.get("outcome_source_sheet"),
                "canonical_outcome_id": cid,
                "canonical_match_status": canonical_match_status,
                "canonical_trust_level": trust_level,
                "canonical_source": canonical.get("canonical_source") if canonical else "",
                "fallback_used": canonical.get("fallback_used") if canonical else "",
                "source_agreement_class": canonical.get("source_agreement_class") if canonical else "",
                "canonical_realized_pips": canonical.get("canonical_realized_pips") if canonical else "",
                "canonical_realized_direction": canonical.get("canonical_realized_direction") if canonical else "",
                "canonical_realized_strength": canonical.get("canonical_realized_strength") if canonical else "",
                "usable_for_strict_accuracy": "TRUE" if strict else "FALSE",
                "usable_for_diagnostic_accuracy": "TRUE" if diagnostic else "FALSE",
                "original_accuracy_label_sensitivity": sensitivity,
                "remap_status": remap_status,
                "recommended_re_evaluation_handling": handling,
                "notes": f"{remap_note} Remap preview only; no direction_ok, overall_ok, or accuracy metrics recalculated.",
            }
        )

    trust_counts = Counter(_norm(row.get("trust_level")) for row in outcomes)
    strict_count = sum(1 for row in outcomes if _norm(row.get("usable_for_strict_accuracy")) == "TRUE")
    diagnostic_count = sum(1 for row in outcomes if _norm(row.get("usable_for_diagnostic_accuracy")) == "TRUE")
    remap_counts = Counter(row["remap_status"] for row in remap_rows)
    validation_issue_counts = Counter(row["issue_severity"] for row in validation_issues)
    unusable_reason_counts = Counter(row["primary_unusable_reason"] for row in unusable_rows)
    duplicate_count = sum(1 for count in Counter(_norm(row.get("canonical_outcome_id")) for row in outcomes).values() if count > 1)
    match_ambiguous = sum(1 for row in match_rows if _norm(row.get("match_status")) == "AMBIGUOUS")
    match_missing = sum(1 for row in match_rows if _norm(row.get("match_status")) == "NO_MATCH")

    coverage_rows = []
    coverage_specs = [
        ("all_canonical_outcomes", len(outcomes), len(outcomes)),
        ("controlled_accuracy_rows_145", len(accuracy_rows), len(remap_rows)),
        ("mr_provider_runs_event_windows", _int(_latest(diag_inputs["Market_Reaction_Canonical_Implementation_Summary"]).get("canonical_outcomes_created")), len(outcomes)),
        ("evaluation_rows_reference", len(main_inputs["Evaluation_Rows"]), sum(1 for row in match_rows if _int(row.get("matched_evaluation_rows")) > 0)),
        ("outcome_ledger_reference", len(main_inputs["Outcome_Ledger"]), sum(1 for row in outcomes if _norm(row.get("event_id")))),
    ]
    for scope, expected, found in coverage_specs:
        high = trust_counts["HIGH_TRUST"] if scope == "all_canonical_outcomes" else remap_counts["REMAP_STRICT_READY"] if scope == "controlled_accuracy_rows_145" else ""
        medium = trust_counts["MEDIUM_TRUST"] if scope == "all_canonical_outcomes" else remap_counts["REMAP_DIAGNOSTIC_ONLY"] if scope == "controlled_accuracy_rows_145" else ""
        low = trust_counts["LOW_TRUST"] if scope == "all_canonical_outcomes" else remap_counts["REMAP_LOW_TRUST"] if scope == "controlled_accuracy_rows_145" else ""
        unusable = trust_counts["UNUSABLE"] if scope == "all_canonical_outcomes" else remap_counts["REMAP_UNUSABLE"] if scope == "controlled_accuracy_rows_145" else ""
        strict_scope = strict_count if scope == "all_canonical_outcomes" else remap_counts["REMAP_STRICT_READY"] if scope == "controlled_accuracy_rows_145" else ""
        diag_scope = diagnostic_count if scope == "all_canonical_outcomes" else remap_counts["REMAP_DIAGNOSTIC_ONLY"] + remap_counts["REMAP_STRICT_READY"] if scope == "controlled_accuracy_rows_145" else ""
        strict_rate = _rate(int(strict_scope), expected) if isinstance(strict_scope, int) else ""
        diag_rate = _rate(int(diag_scope), expected) if isinstance(diag_scope, int) else ""
        if expected and found == expected and (not strict_rate or float(strict_rate) >= 0.5):
            status = "PASS"
        elif scope == "controlled_accuracy_rows_145" and found == expected and (remap_counts["REMAP_STRICT_READY"] + remap_counts["REMAP_DIAGNOSTIC_ONLY"]) > 0:
            status = "PASS_WITH_WARNINGS"
        elif found == 0:
            status = "BLOCKED"
        else:
            status = "LOW_STRICT_COVERAGE"
        coverage_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "coverage_scope": scope,
                "expected_count": expected,
                "canonical_outcomes_found": found,
                "high_trust_count": high,
                "medium_trust_count": medium,
                "low_trust_count": low,
                "unusable_count": unusable,
                "strict_usable_count": strict_scope,
                "diagnostic_usable_count": diag_scope,
                "coverage_rate": _rate(found, expected),
                "strict_usable_rate": strict_rate,
                "diagnostic_usable_rate": diag_rate,
                "coverage_status": status,
                "notes": "Coverage validation; no accuracy recalculation performed.",
            }
        )

    validation_area_rows = []
    area_specs = [
        ("canonical_id_uniqueness", "Market_Reaction_Canonical_Outcomes", len(outcomes), duplicate_count, "canonical_outcome_id removes duplicate ambiguity" if duplicate_count == 0 else "duplicate canonical IDs remain"),
        ("matching_ambiguity", "Market_Reaction_Canonical_Outcome_Matching", len(match_rows), match_ambiguous, "Canonical matching resolves ambiguity" if match_ambiguous == 0 else "Some canonical matches remain ambiguous"),
        ("controlled_accuracy_remap", "Controlled_Accuracy_Evaluation", len(remap_rows), remap_counts["REMAP_MISSING"] + remap_counts["REMAP_AMBIGUOUS"] + remap_counts["REMAP_UNUSABLE"], "145 controlled accuracy rows were remapped for preview"),
        ("trust_consistency", "Market_Reaction_Canonical_Trust_Assessment", len(trust_rows), sum(1 for row in trust_rows if _norm(row.get("trust_consistency_match")) != "TRUE"), "Trust flags are internally consistent"),
        ("unusable_explainability", "Market_Reaction_Canonical_Implementation_Issues", len(unusable_rows), sum(1 for row in unusable_rows if not _norm(row.get("primary_unusable_reason"))), "Unusable outcomes are classified by repair type"),
        ("governance", "Market_Reaction_Canonical_Validation_Governance", 16, 0, "No source, canonical, accuracy, or production rows modified"),
    ]
    for area, source, checked, issues, conclusion in area_specs:
        if checked == 0:
            status = "BLOCKED"
        elif issues == 0:
            status = "PASS"
        elif area == "controlled_accuracy_remap" and remap_counts["REMAP_STRICT_READY"] + remap_counts["REMAP_DIAGNOSTIC_ONLY"] > 0:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "NEEDS_REPAIR"
        validation_area_rows.append(
            {
                **_base(generated_ts, validation_run_id),
                "validation_version": VALIDATION_VERSION,
                "validation_area": area,
                "source_sheet": source,
                "rows_checked": checked,
                "issues_found": issues,
                "issue_rate": _rate(issues, checked),
                "validation_status": status,
                "validation_conclusion": conclusion,
                "impact_on_accuracy_re_evaluation": "Corrected accuracy can only use strict-ready rows; diagnostic rows must remain labeled.",
                "recommended_action": "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN" if area in {"canonical_id_uniqueness", "matching_ambiguity", "controlled_accuracy_remap"} and status in {"PASS", "PASS_WITH_WARNINGS"} else "PROCEED_TO_PHASE9A5M2R_CANONICAL_OUTCOME_IMPLEMENTATION_REPAIR",
                "notes": "Validation-only row.",
            }
        )

    governance_rows = _build_governance_rows(generated_ts, validation_run_id)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    accuracy_strict_ready = remap_counts["REMAP_STRICT_READY"]
    accuracy_diagnostic_only = remap_counts["REMAP_DIAGNOSTIC_ONLY"]
    accuracy_low_trust = remap_counts["REMAP_LOW_TRUST"]
    accuracy_unusable = remap_counts["REMAP_UNUSABLE"]
    accuracy_missing = remap_counts["REMAP_MISSING"]
    accuracy_ambiguous = remap_counts["REMAP_AMBIGUOUS"]
    ready_for_reeval = accuracy_strict_ready > 0 and accuracy_missing == 0 and accuracy_ambiguous == 0 and not governance_failed
    if governance_failed:
        final = "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_BLOCKED"
        build_status = "FAIL"
        recommended_next = "HOLD_ACCURACY_RESEARCH_PENDING_OUTCOME_REVIEW"
    elif ready_for_reeval:
        final = "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_READY_WITH_WARNINGS"
        build_status = "PASS_WITH_WARNINGS"
        recommended_next = "PROCEED_TO_PHASE9A5M4_CORRECTED_ACCURACY_RE_EVALUATION_DESIGN"
    elif accuracy_strict_ready + accuracy_diagnostic_only > 0:
        final = "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_NEEDS_REPAIR"
        build_status = "PASS_WITH_WARNINGS"
        recommended_next = "PROCEED_TO_PHASE9A5M2R_CANONICAL_OUTCOME_IMPLEMENTATION_REPAIR"
    else:
        final = "MARKET_REACTION_CANONICAL_OUTCOME_VALIDATION_BLOCKED"
        build_status = "FAIL"
        recommended_next = "HOLD_ACCURACY_RESEARCH_PENDING_OUTCOME_REVIEW"
    primary_unusable_reason = unusable_reason_counts.most_common(1)[0][0] if unusable_reason_counts else "NONE"
    highest_validation_issue = "unusable_outcome_volume" if trust_counts["UNUSABLE"] else "none_detected"
    highest_blocker = "strict_ready_rows_limited" if accuracy_strict_ready < len(accuracy_rows) else "none_detected"
    summary_row = {
        **_base(generated_ts, validation_run_id),
        "validation_version": VALIDATION_VERSION,
        "build_status": build_status,
        "final_interpretation": final,
        "canonical_outcomes_checked": len(outcomes),
        "canonical_id_duplicates": duplicate_count,
        "canonical_matches_ambiguous": match_ambiguous,
        "canonical_matches_missing": match_missing,
        "canonical_outcomes_high_trust": trust_counts["HIGH_TRUST"],
        "canonical_outcomes_medium_trust": trust_counts["MEDIUM_TRUST"],
        "canonical_outcomes_low_trust": trust_counts["LOW_TRUST"],
        "canonical_outcomes_unusable": trust_counts["UNUSABLE"],
        "strict_usable_count": strict_count,
        "diagnostic_usable_count": diagnostic_count,
        "unusable_count": trust_counts["UNUSABLE"],
        "accuracy_rows_checked": len(accuracy_rows),
        "accuracy_rows_strict_ready": accuracy_strict_ready,
        "accuracy_rows_diagnostic_only": accuracy_diagnostic_only,
        "accuracy_rows_low_trust": accuracy_low_trust,
        "accuracy_rows_unusable": accuracy_unusable,
        "accuracy_rows_missing_canonical_match": accuracy_missing,
        "accuracy_rows_ambiguous_canonical_match": accuracy_ambiguous,
        "primary_unusable_reason": primary_unusable_reason,
        "highest_risk_validation_issue": highest_validation_issue,
        "highest_risk_accuracy_re_evaluation_blocker": highest_blocker,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "canonical_outcomes_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_corrected_accuracy_re_evaluation": "TRUE" if ready_for_reeval else "FALSE",
        "ready_for_accuracy_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next,
        "notes": json.dumps(
            {
                "validation_questions_answered": True,
                "accuracy_rerun": False,
                "canonical_rows_modified": False,
                "controlled_accuracy_rows_required": 145,
                "corrected_accuracy_scope": "design_only_next",
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_VALIDATION, VALIDATION_HEADERS, validation_area_rows),
        (OUTPUT_COVERAGE, COVERAGE_HEADERS, coverage_rows),
        (OUTPUT_TRUST, TRUST_HEADERS, trust_rows),
        (OUTPUT_UNUSABLE, UNUSABLE_HEADERS, unusable_rows),
        (OUTPUT_MATCH, MATCH_HEADERS, match_rows),
        (OUTPUT_REMAP, REMAP_HEADERS, remap_rows),
        (OUTPUT_DISAGREEMENT, DISAGREEMENT_HEADERS, disagreement_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_ISSUES, ISSUE_HEADERS, validation_issues),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final,
        "file_created": "automation/build_market_reaction_canonical_outcome_validation_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "canonical_outcomes_checked": len(outcomes),
        "canonical_id_duplicates": duplicate_count,
        "canonical_matches_ambiguous": match_ambiguous,
        "canonical_matches_missing": match_missing,
        "canonical_outcomes_high_trust": trust_counts["HIGH_TRUST"],
        "canonical_outcomes_medium_trust": trust_counts["MEDIUM_TRUST"],
        "canonical_outcomes_low_trust": trust_counts["LOW_TRUST"],
        "canonical_outcomes_unusable": trust_counts["UNUSABLE"],
        "strict_usable_count": strict_count,
        "diagnostic_usable_count": diagnostic_count,
        "unusable_count": trust_counts["UNUSABLE"],
        "accuracy_rows_checked": len(accuracy_rows),
        "accuracy_rows_strict_ready": accuracy_strict_ready,
        "accuracy_rows_diagnostic_only": accuracy_diagnostic_only,
        "accuracy_rows_low_trust": accuracy_low_trust,
        "accuracy_rows_unusable": accuracy_unusable,
        "accuracy_rows_missing_canonical_match": accuracy_missing,
        "accuracy_rows_ambiguous_canonical_match": accuracy_ambiguous,
        "primary_unusable_reason": primary_unusable_reason,
        "highest_risk_validation_issue": highest_validation_issue,
        "highest_risk_accuracy_re_evaluation_blocker": highest_blocker,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "canonical_outcomes_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_corrected_accuracy_re_evaluation": ready_for_reeval,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_canonical_outcome_validation_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
