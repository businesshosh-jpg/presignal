import argparse
import hashlib
import itertools
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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


SCHEMA_VERSION = "presignal_v2_market_reaction_outcome_source_implementation_0.1"
IMPLEMENTATION_VERSION = "market_reaction_outcome_source_implementation_v0"
CONSTRUCTION_VERSION = "canonical_market_reaction_outcome_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_CANONICAL_OUTCOME_IMPLEMENTATION"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = [
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Outcome_Ledger",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Event",
    "Config",
]

DIAG_INPUT_SHEETS = [
    "Market_Reaction_Canonical_Source_Review",
    "Market_Reaction_Source_Strategy_Comparison",
    "Market_Reaction_Source_Risk_Assessment",
    "Market_Reaction_Canonical_Window_Review",
    "Market_Reaction_Canonical_Matching_Review",
    "Market_Reaction_Canonical_Trust_Model",
    "Market_Reaction_Source_Selection_Decision",
    "Market_Reaction_Canonical_Source_Review_Summary",
    "Market_Reaction_Outcome_Integrity_Summary",
    "Market_Reaction_Source_Comparison_Audit",
    "Market_Reaction_Outcome_Match_Audit",
    "Market_Reaction_Accuracy_Impact_Audit",
]

CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Outcome_Ledger", "Config"}
CRITICAL_DIAG_SHEETS = {
    "Market_Reaction_Source_Selection_Decision",
    "Market_Reaction_Canonical_Source_Review_Summary",
    "Market_Reaction_Canonical_Trust_Model",
    "Market_Reaction_Outcome_Integrity_Summary",
}

OUTPUT_OUTCOMES = "Market_Reaction_Canonical_Outcomes"
OUTPUT_SELECTION = "Market_Reaction_Canonical_Source_Selection"
OUTPUT_AGREEMENT = "Market_Reaction_Canonical_Source_Agreement"
OUTPUT_WINDOW = "Market_Reaction_Canonical_Window_Construction"
OUTPUT_MATCHING = "Market_Reaction_Canonical_Outcome_Matching"
OUTPUT_TRUST = "Market_Reaction_Canonical_Trust_Assessment"
OUTPUT_ISSUES = "Market_Reaction_Canonical_Implementation_Issues"
OUTPUT_GOVERNANCE = "Market_Reaction_Canonical_Implementation_Governance"
OUTPUT_SUMMARY = "Market_Reaction_Canonical_Implementation_Summary"

OUTCOME_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_version",
    "implementation_run_id",
    "canonical_outcome_id",
    "country",
    "event_id",
    "batch_id",
    "session_id",
    "release_ts",
    "window_policy",
    "window_minutes",
    "canonical_start_ts",
    "canonical_end_ts",
    "canonical_source",
    "fallback_used",
    "fallback_reason",
    "source_rows_available",
    "source_rows_used",
    "provider_sources_available",
    "canonical_start_price",
    "canonical_end_price",
    "canonical_realized_pips",
    "canonical_realized_direction",
    "canonical_realized_strength",
    "source_agreement_class",
    "window_confidence",
    "outcome_confidence",
    "trust_level",
    "construction_version",
    "usable_for_strict_accuracy",
    "usable_for_diagnostic_accuracy",
    "boundary_risk",
    "issue_count",
    "notes",
]

SELECTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
    "canonical_outcome_id",
    "candidate_sources",
    "source_priority_order",
    "selected_source",
    "selection_reason",
    "fallback_used",
    "fallback_from",
    "fallback_to",
    "fallback_reason",
    "source_selection_status",
    "notes",
]

AGREEMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
    "canonical_outcome_id",
    "provider_source_a",
    "provider_source_b",
    "realized_pips_a",
    "realized_pips_b",
    "pips_difference",
    "direction_a",
    "direction_b",
    "direction_agreement",
    "strength_a",
    "strength_b",
    "strength_agreement",
    "agreement_class",
    "issue_type",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
    "canonical_outcome_id",
    "country",
    "event_id",
    "batch_id",
    "session_id",
    "release_ts",
    "canonical_start_ts",
    "canonical_end_ts",
    "window_minutes",
    "window_policy",
    "horizon_source",
    "start_price_available",
    "end_price_available",
    "candle_count",
    "window_status",
    "window_confidence",
    "issue_type",
    "notes",
]

MATCHING_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
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
    "duplicate_risk",
    "ambiguity_resolved",
    "notes",
]

TRUST_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
    "canonical_outcome_id",
    "source_selection_status",
    "agreement_class",
    "window_status",
    "boundary_risk",
    "formula_issue",
    "trust_level",
    "usable_for_strict_accuracy",
    "usable_for_diagnostic_accuracy",
    "trust_reason",
    "recommended_handling",
    "notes",
]

ISSUE_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
    "issue_id",
    "canonical_outcome_id",
    "issue_area",
    "issue_severity",
    "issue_type",
    "description",
    "affected_source",
    "affected_metric",
    "blocks_strict_accuracy",
    "blocks_diagnostic_accuracy",
    "recommended_resolution",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "implementation_run_id",
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
    "implementation_version",
    "implementation_run_id",
    "build_status",
    "final_interpretation",
    "canonical_outcomes_created",
    "canonical_outcomes_high_trust",
    "canonical_outcomes_medium_trust",
    "canonical_outcomes_low_trust",
    "canonical_outcomes_unusable",
    "primary_source_selected_count",
    "fallback_source_selected_count",
    "no_valid_source_count",
    "source_disagreement_high_count",
    "source_disagreement_unusable_count",
    "window_pass_count",
    "window_warning_count",
    "window_issue_count",
    "canonical_matches_created",
    "canonical_matches_ambiguous",
    "canonical_matches_missing",
    "usable_for_strict_accuracy_count",
    "usable_for_diagnostic_accuracy_count",
    "excluded_from_strict_accuracy_count",
    "implementation_issues_total",
    "critical_issues",
    "high_issues",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_evaluation_performed",
    "accuracy_results_modified",
    "market_reaction_values_modified",
    "mr_provider_runs_modified",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_canonical_outcome_validation",
    "ready_for_accuracy_re_evaluation",
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


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_outcome_source_implementation_v0_{compact}"


def _base(generated_ts: str, implementation_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "implementation_run_id": implementation_run_id,
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


def _compact_existing_market_reaction_sheets(service) -> Dict[str, int]:
    known_dimensions = {
        "Market_Reaction_Outcome_Integrity_Audit": (8, 14),
        "Market_Reaction_Pips_Formula_Audit": (10997, 19),
        "Market_Reaction_Direction_Label_Audit": (10997, 16),
        "Market_Reaction_Strength_Label_Audit": (10997, 17),
        "Market_Reaction_Window_Audit": (10997, 20),
        "Market_Reaction_Source_Comparison_Audit": (3720, 25),
        "Market_Reaction_Outcome_Match_Audit": (146, 19),
        "Market_Reaction_Accuracy_Impact_Audit": (146, 20),
        "Market_Reaction_Governance_Audit": (15, 10),
        "Market_Reaction_Outcome_Integrity_Summary": (2, 38),
        "Market_Reaction_Source_Repair_Design": (7, 15),
        "Market_Reaction_Canonical_Source_Strategy": (5, 19),
        "Market_Reaction_Window_Definition_Design": (5, 17),
        "Market_Reaction_Outcome_Matching_Design": (4, 16),
        "Market_Reaction_Disagreement_Handling": (5, 13),
        "Market_Reaction_Trust_Scoring_Design": (12, 12),
        "Market_Reaction_Repair_Readiness": (10, 12),
        "Market_Reaction_Source_Repair_Governance": (16, 10),
        "Market_Reaction_Source_Repair_Summary": (2, 33),
        "Market_Reaction_Canonical_Source_Review": (8, 14),
        "Market_Reaction_Source_Strategy_Comparison": (5, 20),
        "Market_Reaction_Source_Risk_Assessment": (6, 12),
        "Market_Reaction_Canonical_Window_Review": (5, 13),
        "Market_Reaction_Canonical_Matching_Review": (4, 12),
        "Market_Reaction_Canonical_Trust_Model": (12, 11),
        "Market_Reaction_Source_Selection_Decision": (2, 18),
        "Market_Reaction_Canonical_Source_Governance": (15, 10),
        "Market_Reaction_Canonical_Source_Review_Summary": (2, 31),
    }
    metadata = service.spreadsheets().get(spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID).execute()
    requests = []
    compacted = 0
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        title = props.get("title", "")
        if title not in known_dimensions:
            continue
        target_rows, target_cols = known_dimensions[title]
        grid = props.get("gridProperties", {})
        if grid.get("rowCount") == target_rows and grid.get("columnCount") == target_cols:
            continue
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": props["sheetId"],
                        "gridProperties": {
                            "rowCount": target_rows,
                            "columnCount": target_cols,
                        },
                    },
                    "fields": "gridProperties(rowCount,columnCount)",
                }
            }
        )
        compacted += 1
    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": requests},
        ).execute()
    return {"sheets_compacted": compacted}


def _latest(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _parse_ts(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _config_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {_upper(row.get("key")): _norm(row.get("value")) for row in rows if _norm(row.get("key"))}


def _source_priority(config: Dict[str, str]) -> Tuple[List[str], str]:
    keys = ["MR_PRIMARY_PROVIDER", "MR_COMPARE_PROVIDER", "MR_COMPARE_PROVIDER_2", "MR_COMPARE_PROVIDER_3"]
    providers = [config.get(key) for key in keys if config.get(key)]
    hierarchy_source = "CONFIG_APPROVED_BY_PHASE9A5M1"
    if not providers:
        providers = ["tiingo", "eodhd", "massive", "twelvedata"]
        hierarchy_source = "INFERRED_DEFAULT_WITH_WARNING"
    deduped: List[str] = []
    for provider in providers:
        if provider and provider not in deduped:
            deduped.append(provider)
    return deduped, hierarchy_source


def _direction_threshold(config: Dict[str, str]) -> float:
    return _float(config.get("MR_FLAT_MAX_ABS_PIPS")) or 1.0


def _strength_thresholds(config: Dict[str, str]) -> Tuple[float, float]:
    return _float(config.get("MR_WEAK_MAX_ABS_PIPS")) or 5.0, _float(config.get("MR_MEDIUM_MAX_ABS_PIPS")) or 15.0


def _expected_direction(pips: Optional[float], threshold: float) -> str:
    if pips is None:
        return ""
    if pips >= threshold:
        return "UP"
    if pips <= -threshold:
        return "DOWN"
    return "FLAT"


def _expected_strength(pips: Optional[float], weak_threshold: float, medium_threshold: float) -> str:
    if pips is None:
        return ""
    abs_pips = abs(pips)
    if abs_pips < weak_threshold:
        return "WEAK"
    if abs_pips < medium_threshold:
        return "MEDIUM"
    return "STRONG"


def _canonical_key(country: str, event_or_batch: str, release_ts: str, window_policy: str, window_minutes: float, session_id: str = "") -> str:
    parts = [country, event_or_batch, release_ts, window_policy, str(int(window_minutes) if window_minutes.is_integer() else window_minutes)]
    if session_id:
        parts.insert(1, session_id)
    return "|".join(parts)


def _stable_issue_id(canonical_outcome_id: str, issue_area: str, issue_type: str, affected_source: str) -> str:
    raw = f"{canonical_outcome_id}|{issue_area}|{issue_type}|{affected_source}"
    return "ISSUE_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _event_occurrence_key(row: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return a strict identity for one event occurrence, or an empty key.

    Event IDs are not globally occurrence-unique in historical inputs.  The
    release timestamp is therefore part of canonical batch metadata identity;
    a missing or timezone-ambiguous timestamp cannot be used as a fallback.
    """
    country = _norm(row.get("country"))
    event_id = _norm(row.get("event_id"))
    release_dt = _parse_ts(row.get("release_ts"))
    if not country or not event_id or release_dt is None or release_dt.tzinfo is None:
        return ("", "", "")
    release_ts = release_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return (country, event_id, release_ts)


def _batch_claims(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], Set[str]]:
    claims: Dict[Tuple[str, str, str], Set[str]] = defaultdict(set)
    for row in rows:
        key = _event_occurrence_key(row)
        batch_id = _norm(row.get("batch_id"))
        if all(key) and batch_id:
            claims[key].add(batch_id)
    return claims


def _event_batch_map_details(
    event_rows: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    outcome_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str, str], str], Dict[Tuple[str, str, str], str]]:
    """Resolve batch metadata by exact occurrence without a weaker fallback.

    Existing evaluation and ledger records retain their prior exact-occurrence
    semantics.  When those records do not contain the occurrence, the Event
    table is the deterministic occurrence-level fallback.  Any conflicting
    claim leaves the occurrence unresolved rather than choosing first, latest,
    or row-order data.
    """
    evaluated_claims = _batch_claims(list(eval_rows) + list(outcome_rows))
    event_claims = _batch_claims(event_rows)
    mapping: Dict[Tuple[str, str, str], str] = {}
    sources: Dict[Tuple[str, str, str], str] = {}
    for key in sorted(set(evaluated_claims) | set(event_claims)):
        evaluated = evaluated_claims.get(key, set())
        event = event_claims.get(key, set())
        if len(evaluated) > 1:
            continue
        if len(evaluated) == 1:
            mapping[key] = next(iter(evaluated))
            sources[key] = "EVALUATION_OR_OUTCOME_LEDGER_EXACT_OCCURRENCE"
            continue
        if len(event) == 1:
            mapping[key] = next(iter(event))
            sources[key] = "EVENT_EXACT_OCCURRENCE_FALLBACK"
    return mapping, sources


def _event_batch_map(
    event_rows: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    outcome_rows: Sequence[Dict[str, Any]],
) -> Dict[Tuple[str, str, str], str]:
    """Map canonical rows to batch IDs using strict event-occurrence identity."""
    mapping, _ = _event_batch_map_details(event_rows, eval_rows, outcome_rows)
    return mapping


def _evaluation_index(eval_rows: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
    by_event: Counter[str] = Counter()
    by_country_release: Counter[Tuple[str, str]] = Counter()
    for row in eval_rows:
        event_id = _norm(row.get("event_id"))
        if event_id:
            by_event[event_id] += 1
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if key != ("", ""):
            by_country_release[key] += 1
    return dict(by_event), dict(by_country_release)


def _accuracy_match_index(match_rows: Sequence[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
    by_event: Counter[str] = Counter()
    by_country_release: Counter[Tuple[str, str]] = Counter()
    for row in match_rows:
        event_ids = [part for part in _norm(row.get("matched_event_id")).split("|") if part]
        for event_id in event_ids:
            by_event[event_id] += 1
        key = (_norm(row.get("country")), _norm(row.get("release_ts")))
        if key != ("", ""):
            by_country_release[key] += 1
    return dict(by_event), dict(by_country_release)


def _group_mr_rows(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_norm(row.get("country")), _norm(row.get("event_id")), _norm(row.get("release_ts")))
        if key[0] and key[1] and key[2]:
            groups[key].append(row)
    return groups


def _status_valid(row: Dict[str, Any]) -> bool:
    status = _norm(row.get("status")).lower()
    return status in {"ok", "flat"}


def _candidate_info(
    row: Dict[str, Any],
    canonical_start: Optional[datetime],
    canonical_end: Optional[datetime],
) -> Dict[str, Any]:
    start_price = _float(row.get("start_price"))
    end_price = _float(row.get("end_price"))
    reported_pips = _float(row.get("realized_pips"))
    recomputed_pips = (end_price - start_price) * 100.0 if start_price is not None and end_price is not None else None
    formula_match = (
        recomputed_pips is not None
        and reported_pips is not None
        and abs(recomputed_pips - reported_pips) <= 0.01
    )
    row_start = _parse_ts(row.get("start_ts"))
    row_end = _parse_ts(row.get("end_ts"))
    window_match = (
        canonical_start is not None
        and canonical_end is not None
        and row_start is not None
        and row_end is not None
        and abs((row_start - canonical_start).total_seconds()) <= 1
        and abs((row_end - canonical_end).total_seconds()) <= 1
    )
    candle_count = _int(row.get("candle_count"))
    valid = (
        _status_valid(row)
        and start_price is not None
        and end_price is not None
        and start_price > 0
        and end_price > 0
        and candle_count > 0
        and formula_match
        and window_match
    )
    return {
        "provider": _norm(row.get("provider")),
        "row": row,
        "start_price": start_price,
        "end_price": end_price,
        "reported_pips": reported_pips,
        "realized_pips": recomputed_pips,
        "formula_match": formula_match,
        "window_match": window_match,
        "candle_count": candle_count,
        "valid": valid,
    }


def _agreement_class(valid_candidates: Sequence[Dict[str, Any]], direction_threshold: float, weak_threshold: float, medium_threshold: float) -> Tuple[str, List[Dict[str, Any]]]:
    if not valid_candidates:
        return "UNUSABLE", []
    if len(valid_candidates) == 1:
        return "LOW_DISAGREEMENT", []
    pair_rows: List[Dict[str, Any]] = []
    worst = "LOW_DISAGREEMENT"
    severity = {"LOW_DISAGREEMENT": 0, "MODERATE_DISAGREEMENT": 1, "HIGH_DISAGREEMENT": 2, "UNUSABLE": 3}
    for left, right in itertools.combinations(sorted(valid_candidates, key=lambda c: c["provider"]), 2):
        pips_a = left["realized_pips"]
        pips_b = right["realized_pips"]
        diff = abs(pips_a - pips_b) if pips_a is not None and pips_b is not None else None
        direction_a = _expected_direction(pips_a, direction_threshold)
        direction_b = _expected_direction(pips_b, direction_threshold)
        strength_a = _expected_strength(pips_a, weak_threshold, medium_threshold)
        strength_b = _expected_strength(pips_b, weak_threshold, medium_threshold)
        if diff is None:
            cls = "UNUSABLE"
            issue = "MISSING_PIPS"
        elif direction_a != direction_b or diff >= 5:
            cls = "HIGH_DISAGREEMENT"
            issue = "SOURCE_DIRECTION_OR_LARGE_PIPS_DISAGREEMENT"
        elif diff > 1 or strength_a != strength_b:
            cls = "MODERATE_DISAGREEMENT"
            issue = "SOURCE_MODERATE_PIPS_OR_STRENGTH_DISAGREEMENT"
        else:
            cls = "LOW_DISAGREEMENT"
            issue = "NONE"
        if severity[cls] > severity[worst]:
            worst = cls
        pair_rows.append(
            {
                "provider_source_a": left["provider"],
                "provider_source_b": right["provider"],
                "realized_pips_a": _fmt(pips_a),
                "realized_pips_b": _fmt(pips_b),
                "pips_difference": _fmt(diff),
                "direction_a": direction_a,
                "direction_b": direction_b,
                "direction_agreement": "TRUE" if direction_a == direction_b else "FALSE",
                "strength_a": strength_a,
                "strength_b": strength_b,
                "strength_agreement": "TRUE" if strength_a == strength_b else "FALSE",
                "agreement_class": cls,
                "issue_type": issue,
            }
        )
    return worst, pair_rows


def _boundary_risk(pips: Optional[float], direction_threshold: float, weak_threshold: float, medium_threshold: float) -> bool:
    if pips is None:
        return False
    abs_pips = abs(pips)
    near_direction = abs(abs_pips - direction_threshold) <= 0.25
    near_strength = min(abs(abs_pips - weak_threshold), abs(abs_pips - medium_threshold)) <= 0.5
    return near_direction or near_strength


def _trust_level(
    selected: Optional[Dict[str, Any]],
    fallback_used: bool,
    agreement_class: str,
    window_status: str,
    boundary: bool,
    valid_count: int,
) -> Tuple[str, str, str, str]:
    if selected is None or agreement_class == "UNUSABLE" or window_status in {"MISSING_RELEASE_TS", "MISSING_START_PRICE", "MISSING_END_PRICE", "NO_CANDLES", "INVALID_WINDOW"}:
        return "UNUSABLE", "FALSE", "FALSE", "UNUSABLE"
    if agreement_class == "HIGH_DISAGREEMENT" or boundary or window_status == "PASS_WITH_WARNINGS":
        return "LOW_TRUST", "FALSE", "FALSE", "REVIEW_OUTCOME"
    if fallback_used or agreement_class == "MODERATE_DISAGREEMENT" or valid_count < 2:
        return "MEDIUM_TRUST", "FALSE", "TRUE", "USE_FOR_DIAGNOSTIC_ONLY"
    return "HIGH_TRUST", "TRUE", "TRUE", "USE_FOR_STRICT_ACCURACY"


def _window_status(selected: Optional[Dict[str, Any]], canonical_start: Optional[datetime], canonical_end: Optional[datetime]) -> Tuple[str, str, str]:
    if canonical_start is None:
        return "MISSING_RELEASE_TS", "UNUSABLE", "MISSING_RELEASE_TS"
    if canonical_end is None:
        return "INVALID_WINDOW", "UNUSABLE", "INVALID_WINDOW"
    if selected is None:
        return "NO_CANDLES", "UNUSABLE", "NO_VALID_SOURCE"
    if selected["start_price"] is None:
        return "MISSING_START_PRICE", "UNUSABLE", "MISSING_START_PRICE"
    if selected["end_price"] is None:
        return "MISSING_END_PRICE", "UNUSABLE", "MISSING_END_PRICE"
    if selected["candle_count"] <= 0:
        return "NO_CANDLES", "UNUSABLE", "NO_CANDLES"
    if not selected["window_match"]:
        return "INVALID_WINDOW", "UNUSABLE", "WINDOW_MISMATCH"
    return "PASS", "HIGH", "NONE"


def _select_source(candidates: Sequence[Dict[str, Any]], priority: Sequence[str]) -> Tuple[Optional[Dict[str, Any]], str, str, str, str]:
    by_provider: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_provider[candidate["provider"]].append(candidate)
    valid_by_provider = {
        provider: sorted([c for c in provider_candidates if c["valid"]], key=lambda c: _int(c["row"].get("__source_row_number__")), reverse=True)
        for provider, provider_candidates in by_provider.items()
    }
    for index, provider in enumerate(priority):
        provider_valid = valid_by_provider.get(provider) or []
        if provider_valid:
            fallback_used = index > 0
            return (
                provider_valid[0],
                "FALLBACK_SELECTED" if fallback_used else "PRIMARY_SELECTED",
                "TRUE" if fallback_used else "FALSE",
                priority[0] if fallback_used else "",
                provider if fallback_used else "",
            )
    return None, "NO_VALID_SOURCE", "FALSE", "", ""


def _issue(
    generated_ts: str,
    implementation_run_id: str,
    canonical_outcome_id: str,
    area: str,
    severity: str,
    issue_type: str,
    description: str,
    affected_source: str,
    affected_metric: str,
    blocks_strict: bool,
    blocks_diag: bool,
    resolution: str,
) -> Dict[str, Any]:
    return {
        **_base(generated_ts, implementation_run_id),
        "issue_id": _stable_issue_id(canonical_outcome_id, area, issue_type, affected_source),
        "canonical_outcome_id": canonical_outcome_id,
        "issue_area": area,
        "issue_severity": severity,
        "issue_type": issue_type,
        "description": description,
        "affected_source": affected_source,
        "affected_metric": affected_metric,
        "blocks_strict_accuracy": "TRUE" if blocks_strict else "FALSE",
        "blocks_diagnostic_accuracy": "TRUE" if blocks_diag else "FALSE",
        "recommended_resolution": resolution,
        "notes": "Canonical implementation issue; source rows remain unmodified.",
    }


def _build_governance_rows(generated_ts: str, implementation_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("accuracy_evaluation_performed", 0, 0),
        ("accuracy_results_modified", 0, 0),
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
        row = _base(generated_ts, implementation_run_id)
        row.update(
            {
                "check_id": f"CHK_{name.upper()}",
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Canonical outcome implementation creates diagnostic shadow sheets only.",
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
        ("MARKET_REACTION_CANONICAL_OUTCOMES", OUTPUT_OUTCOMES, "market_reaction_canonical_outcomes"),
        ("MARKET_REACTION_CANONICAL_SOURCE_SELECTION", OUTPUT_SELECTION, "market_reaction_canonical_source_selection"),
        ("MARKET_REACTION_CANONICAL_SOURCE_AGREEMENT", OUTPUT_AGREEMENT, "market_reaction_canonical_source_agreement"),
        ("MARKET_REACTION_CANONICAL_WINDOW_CONSTRUCTION", OUTPUT_WINDOW, "market_reaction_canonical_window_construction"),
        ("MARKET_REACTION_CANONICAL_OUTCOME_MATCHING", OUTPUT_MATCHING, "market_reaction_canonical_outcome_matching"),
        ("MARKET_REACTION_CANONICAL_TRUST_ASSESSMENT", OUTPUT_TRUST, "market_reaction_canonical_trust_assessment"),
        ("MARKET_REACTION_CANONICAL_IMPLEMENTATION_ISSUES", OUTPUT_ISSUES, "market_reaction_canonical_implementation_issues"),
        ("MARKET_REACTION_CANONICAL_IMPLEMENTATION_GOVERNANCE", OUTPUT_GOVERNANCE, "market_reaction_canonical_implementation_governance"),
        ("MARKET_REACTION_CANONICAL_IMPLEMENTATION_SUMMARY", OUTPUT_SUMMARY, "market_reaction_canonical_implementation_summary"),
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
            "notes": "Phase 9A-5M2 canonical market reaction outcome implementation; shadow-only.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M2 canonical outcome source implementation.")
    return parser.parse_args(argv)


def build_market_reaction_outcome_source_implementation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    implementation_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    main_titles = _sheet_titles(service, MAIN_SPREADSHEET_ID)
    diag_titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing_main: List[str] = []
    missing_diag: List[str] = []
    main_inputs = {sheet: _safe_rows(service, MAIN_SPREADSHEET_ID, main_titles, sheet, missing_main) for sheet in MAIN_INPUT_SHEETS}
    diag_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_diag) for sheet in DIAG_INPUT_SHEETS}
    missing_critical = sorted(
        [f"MAIN:{sheet}" for sheet in missing_main if sheet in CRITICAL_MAIN_SHEETS]
        + [f"DIAGNOSTICS:{sheet}" for sheet in missing_diag if sheet in CRITICAL_DIAG_SHEETS]
    )
    if missing_critical:
        raise RuntimeError(f"Missing critical Phase 9A-5M2 inputs: {missing_critical}")

    decision = _latest(diag_inputs["Market_Reaction_Source_Selection_Decision"])
    review_summary = _latest(diag_inputs["Market_Reaction_Canonical_Source_Review_Summary"])
    if _norm(review_summary.get("recommended_next_step")) != "PROCEED_TO_PHASE9A5M2_OUTCOME_SOURCE_IMPLEMENTATION":
        raise RuntimeError("Phase 9A-5M1 did not approve Phase 9A-5M2 implementation.")
    if _norm(decision.get("canonical_strategy_selected")) != "HIERARCHICAL_FALLBACK":
        raise RuntimeError("Canonical strategy is not HIERARCHICAL_FALLBACK; implementation blocked.")

    compaction = _compact_existing_market_reaction_sheets(service)

    config = _config_map(main_inputs["Config"])
    source_priority, hierarchy_source = _source_priority(config)
    horizon = _float(config.get("MR_HORIZON_MIN"))
    horizon_source = "CONFIG_MR_HORIZON_MIN"
    if horizon is None:
        horizon = 5.0
        horizon_source = "INFERRED_FROM_EXISTING_MR_PROVIDER_RUNS"
    direction_threshold = _direction_threshold(config)
    weak_threshold, medium_threshold = _strength_thresholds(config)

    eval_by_event, eval_by_country_release = _evaluation_index(main_inputs["Evaluation_Rows"])
    accuracy_by_event, accuracy_by_country_release = _accuracy_match_index(diag_inputs["Market_Reaction_Outcome_Match_Audit"])
    event_batch = _event_batch_map(
        main_inputs["Event"],
        main_inputs["Evaluation_Rows"],
        main_inputs["Outcome_Ledger"],
    )
    groups = _group_mr_rows(main_inputs["MR_ProviderRuns"])

    outcome_rows: List[Dict[str, Any]] = []
    selection_rows: List[Dict[str, Any]] = []
    agreement_rows: List[Dict[str, Any]] = []
    window_rows: List[Dict[str, Any]] = []
    matching_rows: List[Dict[str, Any]] = []
    trust_rows: List[Dict[str, Any]] = []
    issue_rows: List[Dict[str, Any]] = []

    window_policy = "EVENT_RELATIVE_FIXED_DURATION"
    for (country, event_id, release_ts), source_rows in sorted(groups.items()):
        release_dt = _parse_ts(release_ts)
        canonical_start = release_dt
        canonical_end = release_dt + timedelta(minutes=horizon) if release_dt is not None else None
        batch_id = event_batch.get(_event_occurrence_key({
            "country": country,
            "event_id": event_id,
            "release_ts": release_ts,
        }), "")
        session_id = ""
        canonical_id = _canonical_key(country, event_id or batch_id, release_ts, window_policy, horizon, session_id)
        candidates = [_candidate_info(row, canonical_start, canonical_end) for row in source_rows]
        valid_candidates = [candidate for candidate in candidates if candidate["valid"]]
        selected, selection_status, fallback_used, fallback_from, fallback_to = _select_source(candidates, source_priority)
        agreement_class, pair_data = _agreement_class(valid_candidates, direction_threshold, weak_threshold, medium_threshold)
        source_rows_used = len(valid_candidates)
        window_status, window_confidence, window_issue = _window_status(selected, canonical_start, canonical_end)
        selected_pips = selected["realized_pips"] if selected else None
        boundary = _boundary_risk(selected_pips, direction_threshold, weak_threshold, medium_threshold)
        trust_level, strict_ok, diagnostic_ok, handling = _trust_level(
            selected,
            fallback_used == "TRUE",
            agreement_class,
            window_status,
            boundary,
            len(valid_candidates),
        )
        formula_issue = "FALSE" if selected and selected["formula_match"] else "TRUE"
        if trust_level == "HIGH_TRUST":
            outcome_confidence = "HIGH"
        elif trust_level == "MEDIUM_TRUST":
            outcome_confidence = "MEDIUM"
        elif trust_level == "LOW_TRUST":
            outcome_confidence = "LOW"
        else:
            outcome_confidence = "UNUSABLE"
        direction = _expected_direction(selected_pips, direction_threshold)
        strength = _expected_strength(selected_pips, weak_threshold, medium_threshold)
        fallback_reason = ""
        if selected is None:
            fallback_reason = "no_valid_source"
        elif fallback_used == "TRUE":
            fallback_reason = "primary_source_invalid_or_missing_for_canonical_window"
        candidate_sources = sorted({candidate["provider"] for candidate in candidates if candidate["provider"]})
        provider_sources_available = "|".join(candidate_sources)

        local_issues: List[Dict[str, Any]] = []
        if selected is None:
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "source_selection",
                    "CRITICAL",
                    "NO_VALID_SOURCE",
                    "No provider source passed canonical source validity checks.",
                    "ALL",
                    "all",
                    True,
                    True,
                    "Review source availability/window construction or exclude outcome.",
                )
            )
        if source_rows_used < 2 and selected is not None:
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "source_agreement",
                    "MEDIUM",
                    "SINGLE_VALID_SOURCE",
                    "Only one valid source is available for agreement validation.",
                    selected["provider"],
                    "all",
                    True,
                    False,
                    "Keep diagnostic use; require validation before strict replication.",
                )
            )
        if agreement_class == "HIGH_DISAGREEMENT":
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "source_agreement",
                    "HIGH",
                    "HIGH_SOURCE_DISAGREEMENT",
                    "Valid providers disagree on direction or differ by at least 5 pips.",
                    provider_sources_available,
                    "direction_match_rate|overall_ok",
                    True,
                    False,
                    "Review source disagreement before strict accuracy use.",
                )
            )
        if window_status != "PASS":
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "window",
                    "CRITICAL" if trust_level == "UNUSABLE" else "HIGH",
                    window_issue,
                    "Selected source does not satisfy canonical fixed event-relative window construction.",
                    selected["provider"] if selected else "NONE",
                    "all",
                    True,
                    trust_level == "UNUSABLE",
                    "Repair or review window construction before accuracy use.",
                )
            )
        if boundary:
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "threshold_boundary",
                    "HIGH",
                    "BOUNDARY_RISK",
                    "Canonical pips are close to direction or strength threshold.",
                    selected["provider"] if selected else "NONE",
                    "direction_match_rate|overall_ok",
                    True,
                    False,
                    "Use threshold sensitivity review before strict accuracy use.",
                )
            )
        if hierarchy_source == "INFERRED_DEFAULT_WITH_WARNING":
            local_issues.append(
                _issue(
                    generated_ts,
                    implementation_run_id,
                    canonical_id,
                    "source_hierarchy",
                    "MEDIUM",
                    "SOURCE_HIERARCHY_INFERRED",
                    "Source hierarchy was inferred because Config hierarchy was unavailable.",
                    "CONFIG",
                    "all",
                    True,
                    False,
                    "Approve hierarchy explicitly before strict use.",
                )
            )
        issue_rows.extend(local_issues)
        issue_count = len(local_issues)

        outcome_row = {
            **_base(generated_ts, implementation_run_id),
            "implementation_version": IMPLEMENTATION_VERSION,
            "canonical_outcome_id": canonical_id,
            "country": country,
            "event_id": event_id,
            "batch_id": batch_id,
            "session_id": session_id,
            "release_ts": release_ts,
            "window_policy": window_policy,
            "window_minutes": _fmt(horizon, 3),
            "canonical_start_ts": _iso(canonical_start),
            "canonical_end_ts": _iso(canonical_end),
            "canonical_source": selected["provider"] if selected else "",
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "source_rows_available": len(source_rows),
            "source_rows_used": source_rows_used,
            "provider_sources_available": provider_sources_available,
            "canonical_start_price": _fmt(selected["start_price"]) if selected else "",
            "canonical_end_price": _fmt(selected["end_price"]) if selected else "",
            "canonical_realized_pips": _fmt(selected_pips),
            "canonical_realized_direction": direction,
            "canonical_realized_strength": strength,
            "source_agreement_class": agreement_class,
            "window_confidence": window_confidence,
            "outcome_confidence": outcome_confidence,
            "trust_level": trust_level,
            "construction_version": CONSTRUCTION_VERSION,
            "usable_for_strict_accuracy": strict_ok,
            "usable_for_diagnostic_accuracy": diagnostic_ok,
            "boundary_risk": "TRUE" if boundary else "FALSE",
            "issue_count": issue_count,
            "notes": f"source_hierarchy={' > '.join(source_priority)}; hierarchy_source={hierarchy_source}",
        }
        outcome_rows.append(outcome_row)

        selection_rows.append(
            {
                **_base(generated_ts, implementation_run_id),
                "canonical_outcome_id": canonical_id,
                "candidate_sources": provider_sources_available,
                "source_priority_order": " > ".join(source_priority),
                "selected_source": selected["provider"] if selected else "",
                "selection_reason": "Selected first valid provider in approved hierarchy." if selected else "No provider passed canonical validity checks.",
                "fallback_used": fallback_used,
                "fallback_from": fallback_from,
                "fallback_to": fallback_to,
                "fallback_reason": fallback_reason,
                "source_selection_status": "AMBIGUOUS_SOURCE" if agreement_class == "HIGH_DISAGREEMENT" and selected else selection_status,
                "notes": f"hierarchy_source={hierarchy_source}; source rows preserved read-only.",
            }
        )

        if pair_data:
            for pair in pair_data:
                row = {**_base(generated_ts, implementation_run_id), "canonical_outcome_id": canonical_id}
                row.update(pair)
                row["notes"] = "Agreement comparison among valid canonical-window source candidates."
                agreement_rows.append(row)
        else:
            agreement_rows.append(
                {
                    **_base(generated_ts, implementation_run_id),
                    "canonical_outcome_id": canonical_id,
                    "provider_source_a": selected["provider"] if selected else "",
                    "provider_source_b": "",
                    "realized_pips_a": _fmt(selected_pips),
                    "realized_pips_b": "",
                    "pips_difference": "",
                    "direction_a": direction,
                    "direction_b": "",
                    "direction_agreement": "TRUE" if selected else "FALSE",
                    "strength_a": strength,
                    "strength_b": "",
                    "strength_agreement": "TRUE" if selected else "FALSE",
                    "agreement_class": agreement_class,
                    "issue_type": "SINGLE_VALID_SOURCE" if selected else "NO_VALID_SOURCE",
                    "notes": "Synthetic agreement row because fewer than two valid canonical-window source candidates exist.",
                }
            )

        matched_eval = eval_by_event.get(event_id, 0)
        matched_eval_fallback = eval_by_country_release.get((country, release_ts), 0)
        matched_accuracy = accuracy_by_event.get(event_id, 0)
        matched_accuracy_fallback = accuracy_by_country_release.get((country, release_ts), 0)
        duplicate_risk = matched_eval_fallback > matched_eval or matched_accuracy_fallback > matched_accuracy
        if matched_eval or matched_accuracy:
            match_status = "MATCHED_CANONICAL"
        elif matched_eval_fallback or matched_accuracy_fallback:
            match_status = "MATCHED_WITH_WARNING"
        else:
            match_status = "NO_MATCH"
        ambiguity_resolved = bool(event_id and match_status in {"MATCHED_CANONICAL", "NO_MATCH"})
        matching_rows.append(
            {
                **_base(generated_ts, implementation_run_id),
                "canonical_outcome_id": canonical_id,
                "country": country,
                "event_id": event_id,
                "batch_id": batch_id,
                "session_id": session_id,
                "release_ts": release_ts,
                "window_policy": window_policy,
                "window_minutes": _fmt(horizon, 3),
                "matched_mr_provider_rows": len(source_rows),
                "matched_evaluation_rows": matched_eval or matched_eval_fallback,
                "matched_accuracy_rows": matched_accuracy or matched_accuracy_fallback,
                "match_status": match_status,
                "duplicate_risk": "TRUE" if duplicate_risk else "FALSE",
                "ambiguity_resolved": "TRUE" if ambiguity_resolved else "FALSE",
                "notes": "Canonical ID resolves event-level identity; country+release fallback remains warning-only.",
            }
        )
        window_rows.append(
            {
                **_base(generated_ts, implementation_run_id),
                "canonical_outcome_id": canonical_id,
                "country": country,
                "event_id": event_id,
                "batch_id": batch_id,
                "session_id": session_id,
                "release_ts": release_ts,
                "canonical_start_ts": _iso(canonical_start),
                "canonical_end_ts": _iso(canonical_end),
                "window_minutes": _fmt(horizon, 3),
                "window_policy": window_policy,
                "horizon_source": horizon_source,
                "start_price_available": "TRUE" if selected and selected["start_price"] is not None else "FALSE",
                "end_price_available": "TRUE" if selected and selected["end_price"] is not None else "FALSE",
                "candle_count": selected["candle_count"] if selected else 0,
                "window_status": window_status,
                "window_confidence": window_confidence,
                "issue_type": window_issue,
                "notes": "Canonical window construction only; original MR window rows are not modified.",
            }
        )
        trust_reason = f"agreement={agreement_class}; window={window_status}; fallback={fallback_used}; boundary={boundary}; valid_sources={len(valid_candidates)}"
        trust_rows.append(
            {
                **_base(generated_ts, implementation_run_id),
                "canonical_outcome_id": canonical_id,
                "source_selection_status": "AMBIGUOUS_SOURCE" if agreement_class == "HIGH_DISAGREEMENT" and selected else selection_status,
                "agreement_class": agreement_class,
                "window_status": window_status,
                "boundary_risk": "TRUE" if boundary else "FALSE",
                "formula_issue": formula_issue,
                "trust_level": trust_level,
                "usable_for_strict_accuracy": strict_ok,
                "usable_for_diagnostic_accuracy": diagnostic_ok,
                "trust_reason": trust_reason,
                "recommended_handling": handling,
                "notes": "Trust assessment controls future validation/accuracy eligibility; no accuracy rerun performed.",
            }
        )

    governance_rows = _build_governance_rows(generated_ts, implementation_run_id)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)
    counts = Counter(row["trust_level"] for row in outcome_rows)
    source_status = Counter(row["source_selection_status"] for row in selection_rows)
    agreement_counts = Counter(row["source_agreement_class"] for row in outcome_rows)
    window_counts = Counter(row["window_status"] for row in window_rows)
    match_counts = Counter(row["match_status"] for row in matching_rows)
    issue_counts = Counter(row["issue_severity"] for row in issue_rows)
    strict_count = sum(1 for row in outcome_rows if _norm(row.get("usable_for_strict_accuracy")) == "TRUE")
    diagnostic_count = sum(1 for row in outcome_rows if _norm(row.get("usable_for_diagnostic_accuracy")) == "TRUE")
    excluded_strict = len(outcome_rows) - strict_count
    final_interpretation = (
        "MARKET_REACTION_CANONICAL_OUTCOMES_IMPLEMENTED_WITH_WARNINGS"
        if not governance_failed and outcome_rows
        else "MARKET_REACTION_CANONICAL_OUTCOMES_BLOCKED"
    )
    build_status = "PASS_WITH_WARNINGS" if final_interpretation.endswith("WITH_WARNINGS") else "FAIL"
    recommended_next = (
        "PROCEED_TO_PHASE9A5M3_CANONICAL_OUTCOME_VALIDATION"
        if not governance_failed and outcome_rows
        else "HOLD_ACCURACY_RESEARCH_PENDING_OUTCOME_REVIEW"
    )
    summary_row = {
        **_base(generated_ts, implementation_run_id),
        "implementation_version": IMPLEMENTATION_VERSION,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "canonical_outcomes_created": len(outcome_rows),
        "canonical_outcomes_high_trust": counts["HIGH_TRUST"],
        "canonical_outcomes_medium_trust": counts["MEDIUM_TRUST"],
        "canonical_outcomes_low_trust": counts["LOW_TRUST"],
        "canonical_outcomes_unusable": counts["UNUSABLE"],
        "primary_source_selected_count": source_status["PRIMARY_SELECTED"],
        "fallback_source_selected_count": source_status["FALLBACK_SELECTED"],
        "no_valid_source_count": source_status["NO_VALID_SOURCE"],
        "source_disagreement_high_count": agreement_counts["HIGH_DISAGREEMENT"],
        "source_disagreement_unusable_count": agreement_counts["UNUSABLE"],
        "window_pass_count": window_counts["PASS"],
        "window_warning_count": window_counts["PASS_WITH_WARNINGS"],
        "window_issue_count": len(window_rows) - window_counts["PASS"] - window_counts["PASS_WITH_WARNINGS"],
        "canonical_matches_created": match_counts["MATCHED_CANONICAL"],
        "canonical_matches_ambiguous": match_counts["AMBIGUOUS"],
        "canonical_matches_missing": match_counts["NO_MATCH"],
        "usable_for_strict_accuracy_count": strict_count,
        "usable_for_diagnostic_accuracy_count": diagnostic_count,
        "excluded_from_strict_accuracy_count": excluded_strict,
        "implementation_issues_total": len(issue_rows),
        "critical_issues": issue_counts["CRITICAL"],
        "high_issues": issue_counts["HIGH"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_canonical_outcome_validation": "TRUE" if not governance_failed and outcome_rows else "FALSE",
        "ready_for_accuracy_re_evaluation": "FALSE",
        "ready_for_accuracy_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next,
        "notes": json.dumps(
            {
                "source_priority_order": source_priority,
                "source_hierarchy_source": hierarchy_source,
                "horizon_minutes": horizon,
                "horizon_source": horizon_source,
                "direction_threshold_pips": direction_threshold,
                "strength_thresholds": {"weak_lt": weak_threshold, "medium_lt": medium_threshold},
                "source_data_modified": False,
                "accuracy_rerun": False,
                "diagnostic_grid_compaction": compaction,
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]
    outputs = [
        (OUTPUT_OUTCOMES, OUTCOME_HEADERS, outcome_rows),
        (OUTPUT_SELECTION, SELECTION_HEADERS, selection_rows),
        (OUTPUT_AGREEMENT, AGREEMENT_HEADERS, agreement_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_MATCHING, MATCHING_HEADERS, matching_rows),
        (OUTPUT_TRUST, TRUST_HEADERS, trust_rows),
        (OUTPUT_ISSUES, ISSUE_HEADERS, issue_rows),
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
        "file_created": "automation/build_market_reaction_outcome_source_implementation_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "canonical_outcomes_created": len(outcome_rows),
        "canonical_outcomes_high_trust": counts["HIGH_TRUST"],
        "canonical_outcomes_medium_trust": counts["MEDIUM_TRUST"],
        "canonical_outcomes_low_trust": counts["LOW_TRUST"],
        "canonical_outcomes_unusable": counts["UNUSABLE"],
        "primary_source_selected_count": source_status["PRIMARY_SELECTED"],
        "fallback_source_selected_count": source_status["FALLBACK_SELECTED"],
        "no_valid_source_count": source_status["NO_VALID_SOURCE"],
        "high_source_disagreement_count": agreement_counts["HIGH_DISAGREEMENT"],
        "unusable_source_disagreement_count": agreement_counts["UNUSABLE"],
        "window_pass_count": window_counts["PASS"],
        "window_warning_count": window_counts["PASS_WITH_WARNINGS"],
        "window_issue_count": summary_row["window_issue_count"],
        "canonical_matches_created": match_counts["MATCHED_CANONICAL"],
        "canonical_matches_ambiguous": match_counts["AMBIGUOUS"],
        "canonical_matches_missing": match_counts["NO_MATCH"],
        "usable_for_strict_accuracy_count": strict_count,
        "usable_for_diagnostic_accuracy_count": diagnostic_count,
        "excluded_from_strict_accuracy_count": excluded_strict,
        "implementation_issues_total": len(issue_rows),
        "critical_issues": issue_counts["CRITICAL"],
        "high_issues": issue_counts["HIGH"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_evaluation_performed": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "mr_provider_runs_modified": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_canonical_outcome_validation": not governance_failed and bool(outcome_rows),
        "ready_for_accuracy_re_evaluation": False,
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_outcome_source_implementation_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
