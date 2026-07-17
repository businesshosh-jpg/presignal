import argparse
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_market_reaction_outcome_integrity_audit_0.1"
AUDIT_VERSION = "market_reaction_outcome_integrity_audit_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M-0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_REACTION_OUTCOME_INTEGRITY_AUDIT"
REGISTRY_OWNER_MODULE = "market_state"

MAIN_INPUT_SHEETS = [
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Outcome_Ledger",
    "Event",
    "Config",
]

DIAG_INPUT_SHEETS = [
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Experiment_Results",
    "Controlled_Accuracy_Comparison_Results",
    "Controlled_Accuracy_Metric_Results",
    "Controlled_Accuracy_Invalid_Output_Results",
    "Controlled_Accuracy_Evaluation_Summary",
    "Behavior_Accuracy_Revision_Summary",
    "Behavior_Accuracy_Metric_Revision_Audit",
]

CRITICAL_MAIN_SHEETS = {"MR_ProviderRuns", "Evaluation_Rows", "Config"}
CRITICAL_DIAG_SHEETS = {
    "Controlled_Accuracy_Evaluation",
    "Controlled_Accuracy_Evaluation_Summary",
    "Behavior_Accuracy_Revision_Summary",
}

OUTPUT_INTEGRITY = "Market_Reaction_Outcome_Integrity_Audit"
OUTPUT_PIPS = "Market_Reaction_Pips_Formula_Audit"
OUTPUT_DIRECTION = "Market_Reaction_Direction_Label_Audit"
OUTPUT_STRENGTH = "Market_Reaction_Strength_Label_Audit"
OUTPUT_WINDOW = "Market_Reaction_Window_Audit"
OUTPUT_SOURCE = "Market_Reaction_Source_Comparison_Audit"
OUTPUT_MATCH = "Market_Reaction_Outcome_Match_Audit"
OUTPUT_IMPACT = "Market_Reaction_Accuracy_Impact_Audit"
OUTPUT_GOVERNANCE = "Market_Reaction_Governance_Audit"
OUTPUT_SUMMARY = "Market_Reaction_Outcome_Integrity_Summary"

INTEGRITY_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_version",
    "audit_run_id",
    "audit_area",
    "source_sheet",
    "rows_checked",
    "issues_found",
    "issue_rate",
    "audit_status",
    "trust_classification",
    "impact_on_accuracy_evaluation",
    "recommended_action",
    "notes",
]

PIPS_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "source_sheet",
    "row_id",
    "event_id",
    "batch_id",
    "provider",
    "provider_source",
    "start_ts",
    "end_ts",
    "start_price",
    "end_price",
    "reported_realized_pips",
    "recomputed_realized_pips",
    "absolute_difference",
    "formula_match",
    "issue_type",
    "notes",
]

DIRECTION_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "source_sheet",
    "row_id",
    "event_id",
    "batch_id",
    "provider",
    "provider_source",
    "realized_pips",
    "reported_direction",
    "expected_direction",
    "direction_match",
    "threshold_used",
    "issue_type",
    "notes",
]

STRENGTH_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "source_sheet",
    "row_id",
    "event_id",
    "batch_id",
    "provider",
    "provider_source",
    "realized_pips",
    "abs_realized_pips",
    "reported_strength",
    "expected_strength",
    "strength_match",
    "threshold_used",
    "issue_type",
    "notes",
]

WINDOW_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "source_sheet",
    "row_id",
    "event_id",
    "batch_id",
    "provider",
    "provider_source",
    "start_ts",
    "end_ts",
    "window_minutes",
    "expected_window_minutes",
    "window_match",
    "candle_count",
    "start_price",
    "end_price",
    "window_status",
    "issue_type",
    "notes",
]

SOURCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "comparison_key",
    "event_id",
    "batch_id",
    "release_ts",
    "start_ts",
    "end_ts",
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
    "candle_count_a",
    "candle_count_b",
    "comparison_status",
    "issue_type",
    "notes",
]

MATCH_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "country",
    "release_ts",
    "matched_outcome_source",
    "matched_event_id",
    "matched_batch_id",
    "matched_eval_row_key",
    "match_status",
    "duplicate_match_count",
    "missing_match",
    "ambiguous_match",
    "notes",
]

IMPACT_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
    "accuracy_row_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_direction",
    "reported_outcome_direction",
    "reported_realized_pips",
    "direction_threshold_distance",
    "near_direction_boundary",
    "source_direction_disagreement",
    "source_strength_disagreement",
    "window_issue",
    "pips_formula_issue",
    "accuracy_label_sensitivity",
    "affected_metric",
    "recommended_handling",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "audit_run_id",
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
    "audit_version",
    "audit_run_id",
    "build_status",
    "final_interpretation",
    "mr_rows_checked",
    "pips_formula_mismatches",
    "direction_label_mismatches",
    "strength_label_mismatches",
    "window_issues",
    "source_comparison_pairs",
    "source_direction_disagreements",
    "source_strength_disagreements",
    "large_pips_disagreements",
    "outcome_matches_checked",
    "outcome_matches_missing",
    "outcome_matches_ambiguous",
    "accuracy_rows_high_sensitivity",
    "accuracy_rows_medium_sensitivity",
    "market_reaction_trust_classification",
    "primary_risk",
    "highest_risk_source_pair",
    "recommended_outcome_handling",
    "recommended_metric_handling",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "evaluation_rerun_count",
    "accuracy_results_modified",
    "market_reaction_values_modified",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "ready_for_phase9a5m_metric_or_outcome_repair",
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
        val = float(raw)
    except ValueError:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _int(value: Any) -> int:
    val = _float(value)
    return int(val) if val is not None else 0


def _fmt(value: Optional[float], digits: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}"


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"market_reaction_outcome_integrity_audit_v0_{compact}"


def _base(generated_ts: str, audit_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "audit_run_id": audit_run_id,
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


def _first(row: Dict[str, Any], aliases: Sequence[str]) -> str:
    for alias in aliases:
        if _norm(row.get(alias)):
            return _norm(row.get(alias))
    return ""


def _parse_ts(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _config_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    return {_upper(row.get("key")): _norm(row.get("value")) for row in rows if _norm(row.get("key"))}


def _direction_threshold(config: Dict[str, str]) -> float:
    return _float(config.get("MR_FLAT_MAX_ABS_PIPS")) or 1.0


def _strength_thresholds(config: Dict[str, str]) -> Tuple[float, float, str]:
    weak = _float(config.get("MR_WEAK_MAX_ABS_PIPS")) or 5.0
    medium = _float(config.get("MR_MEDIUM_MAX_ABS_PIPS")) or 15.0
    source = (
        "config:MR_WEAK_MAX_ABS_PIPS/MR_MEDIUM_MAX_ABS_PIPS"
        if config.get("MR_WEAK_MAX_ABS_PIPS") or config.get("MR_MEDIUM_MAX_ABS_PIPS")
        else "default:weak<5;medium<15;strong>=15"
    )
    return weak, medium, source


def _expected_direction(pips: Optional[float], threshold: float) -> str:
    if pips is None:
        return ""
    if pips >= threshold:
        return "UP"
    if pips <= -threshold:
        return "DOWN"
    return "FLAT"


def _normalize_direction(value: Any) -> str:
    raw = _upper(value).replace("-", "_").replace(" ", "_")
    if raw in {"UP", "LONG", "BULLISH", "USDJPY_UP"}:
        return "UP"
    if raw in {"DOWN", "SHORT", "BEARISH", "USDJPY_DOWN"}:
        return "DOWN"
    if raw in {"FLAT", "NO_SIGNAL", "NO_CLEAR_DIRECTION", "NEUTRAL", "NONE"}:
        return "FLAT"
    return raw


def _expected_strength(pips: Optional[float], weak_threshold: float, medium_threshold: float) -> str:
    if pips is None:
        return ""
    magnitude = abs(pips)
    if magnitude < weak_threshold:
        return "WEAK"
    if magnitude < medium_threshold:
        return "MEDIUM"
    return "STRONG"


def _normalize_strength(value: Any) -> str:
    raw = _upper(value).replace("-", "_").replace(" ", "_")
    if raw in {"LOW", "SMALL"}:
        return "WEAK"
    if raw in {"MODERATE", "MID"}:
        return "MEDIUM"
    return raw


def _row_identity(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "row_id": _norm(row.get("__source_row_number__")),
        "event_id": _first(row, ["event_id", "matched_event_id"]),
        "batch_id": _first(row, ["batch_id", "matched_batch_id"]),
        "provider": _first(row, ["ai_name", "provider"]),
        "provider_source": _first(row, ["mr_final_provider", "provider", "score_source"]),
        "release_ts": _first(row, ["release_ts"]),
    }


def _pips_value(row: Dict[str, Any]) -> Optional[float]:
    return _float(_first(row, ["realized_pips", "reported_realized_pips"]))


def _direction_value(row: Dict[str, Any]) -> str:
    return _first(row, ["real_dir", "mr_real_dir", "realized_direction", "outcome_direction"])


def _strength_value(row: Dict[str, Any]) -> str:
    return _first(row, ["real_strength", "mr_real_strength", "reported_strength"])


def _issue_rate(issues: int, rows: int) -> str:
    return _fmt(issues / rows) if rows else ""


def _build_pips_rows(generated_ts: str, audit_run_id: str, mr_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for source in mr_rows:
        ident = _row_identity(source)
        start_price = _float(source.get("start_price"))
        end_price = _float(source.get("end_price"))
        reported = _float(source.get("realized_pips"))
        recomputed = None
        diff = None
        if start_price is not None and end_price is not None:
            recomputed = (end_price - start_price) * 100.0
        if recomputed is not None and reported is not None:
            diff = abs(recomputed - reported)
        formula_match = diff is not None and diff <= 0.01
        if formula_match:
            issue = "NONE"
        elif start_price is None or end_price is None:
            issue = "MISSING_PRICE"
        elif reported is None:
            issue = "MISSING_REPORTED_PIPS"
        else:
            issue = "PIPS_FORMULA_MISMATCH"
        row = _base(generated_ts, audit_run_id)
        row.update(
            {
                "source_sheet": "MR_ProviderRuns",
                "row_id": ident["row_id"],
                "event_id": ident["event_id"],
                "batch_id": ident["batch_id"],
                "provider": ident["provider"],
                "provider_source": ident["provider_source"],
                "start_ts": source.get("start_ts"),
                "end_ts": source.get("end_ts"),
                "start_price": source.get("start_price"),
                "end_price": source.get("end_price"),
                "reported_realized_pips": source.get("realized_pips"),
                "recomputed_realized_pips": _fmt(recomputed),
                "absolute_difference": _fmt(diff),
                "formula_match": "TRUE" if formula_match else "FALSE",
                "issue_type": issue,
                "notes": "Expected formula: (end_price - start_price) * 100 for USDJPY.",
            }
        )
        rows.append(row)
    return rows


def _build_direction_rows(
    generated_ts: str,
    audit_run_id: str,
    source_groups: Sequence[Tuple[str, Sequence[Dict[str, Any]]]],
    threshold: float,
) -> List[Dict[str, Any]]:
    rows = []
    threshold_label = f"config:MR_FLAT_MAX_ABS_PIPS={threshold}" if threshold != 1.0 else "config_or_default:flat_abs_pips=1.0"
    for source_sheet, source_rows in source_groups:
        for source in source_rows:
            ident = _row_identity(source)
            pips = _pips_value(source)
            reported = _normalize_direction(_direction_value(source))
            expected = _expected_direction(pips, threshold)
            match = bool(reported and expected and reported == expected)
            if match:
                issue = "NONE"
            elif pips is None:
                issue = "MISSING_REALIZED_PIPS"
            elif not reported:
                issue = "MISSING_DIRECTION"
            else:
                issue = "DIRECTION_LABEL_MISMATCH"
            row = _base(generated_ts, audit_run_id)
            row.update(
                {
                    "source_sheet": source_sheet,
                    "row_id": ident["row_id"],
                    "event_id": ident["event_id"],
                    "batch_id": ident["batch_id"],
                    "provider": ident["provider"],
                    "provider_source": ident["provider_source"],
                    "realized_pips": _fmt(pips),
                    "reported_direction": reported,
                    "expected_direction": expected,
                    "direction_match": "TRUE" if match else "FALSE",
                    "threshold_used": threshold_label,
                    "issue_type": issue,
                    "notes": "Audit-only direction reconstruction; no forecast correctness calculated.",
                }
            )
            rows.append(row)
    return rows


def _build_strength_rows(
    generated_ts: str,
    audit_run_id: str,
    source_groups: Sequence[Tuple[str, Sequence[Dict[str, Any]]]],
    weak_threshold: float,
    medium_threshold: float,
    threshold_label: str,
) -> List[Dict[str, Any]]:
    rows = []
    for source_sheet, source_rows in source_groups:
        for source in source_rows:
            ident = _row_identity(source)
            pips = _pips_value(source)
            reported = _normalize_strength(_strength_value(source))
            expected = _expected_strength(pips, weak_threshold, medium_threshold)
            match = bool(reported and expected and reported == expected)
            if match:
                issue = "NONE"
            elif pips is None:
                issue = "MISSING_REALIZED_PIPS"
            elif not reported:
                issue = "MISSING_STRENGTH"
            else:
                issue = "STRENGTH_LABEL_MISMATCH"
            row = _base(generated_ts, audit_run_id)
            row.update(
                {
                    "source_sheet": source_sheet,
                    "row_id": ident["row_id"],
                    "event_id": ident["event_id"],
                    "batch_id": ident["batch_id"],
                    "provider": ident["provider"],
                    "provider_source": ident["provider_source"],
                    "realized_pips": _fmt(pips),
                    "abs_realized_pips": _fmt(abs(pips) if pips is not None else None),
                    "reported_strength": reported,
                    "expected_strength": expected,
                    "strength_match": "TRUE" if match else "FALSE",
                    "threshold_used": threshold_label,
                    "issue_type": issue,
                    "notes": "Audit-only strength reconstruction; no forecast correctness calculated.",
                }
            )
            rows.append(row)
    return rows


def _build_window_rows(
    generated_ts: str,
    audit_run_id: str,
    mr_rows: Sequence[Dict[str, Any]],
    expected_window: Optional[float],
) -> List[Dict[str, Any]]:
    rows = []
    for source in mr_rows:
        ident = _row_identity(source)
        start_ts = _parse_ts(source.get("start_ts"))
        end_ts = _parse_ts(source.get("end_ts"))
        start_price = _float(source.get("start_price"))
        end_price = _float(source.get("end_price"))
        candle_count = _int(source.get("candle_count"))
        window_minutes = None
        status = "PASS"
        issue = "NONE"
        if not start_ts:
            status = "MISSING_START"
            issue = "MISSING_START_TS"
        elif not end_ts:
            status = "MISSING_END"
            issue = "MISSING_END_TS"
        else:
            window_minutes = (end_ts - start_ts).total_seconds() / 60.0
            if window_minutes <= 0:
                status = "INVALID_ORDER"
                issue = "START_NOT_BEFORE_END"
            elif expected_window is None:
                status = "UNKNOWN_EXPECTED_WINDOW"
                issue = "UNKNOWN_EXPECTED_WINDOW"
            elif abs(window_minutes - expected_window) > 0.1:
                status = "WINDOW_MISMATCH"
                issue = "WINDOW_LENGTH_MISMATCH"
        if status == "PASS" and candle_count <= 0:
            status = "NO_CANDLES"
            issue = "NO_CANDLES"
        if status == "PASS" and (start_price is None or end_price is None or start_price <= 0 or end_price <= 0):
            status = "PRICE_MISSING"
            issue = "PRICE_MISSING_OR_INVALID"
        window_match = status == "PASS"
        row = _base(generated_ts, audit_run_id)
        row.update(
            {
                "source_sheet": "MR_ProviderRuns",
                "row_id": ident["row_id"],
                "event_id": ident["event_id"],
                "batch_id": ident["batch_id"],
                "provider": ident["provider"],
                "provider_source": ident["provider_source"],
                "start_ts": source.get("start_ts"),
                "end_ts": source.get("end_ts"),
                "window_minutes": _fmt(window_minutes),
                "expected_window_minutes": _fmt(expected_window),
                "window_match": "TRUE" if window_match else "FALSE",
                "candle_count": source.get("candle_count"),
                "start_price": source.get("start_price"),
                "end_price": source.get("end_price"),
                "window_status": status,
                "issue_type": issue,
                "notes": "Window audit checks data integrity only; no market reaction repair performed.",
            }
        )
        rows.append(row)
    return rows


def _dedupe_provider_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_provider: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        provider = _first(row, ["provider", "mr_final_provider", "score_source"]) or "UNKNOWN"
        current = by_provider.get(provider)
        if current is None or _int(row.get("__source_row_number__")) > _int(current.get("__source_row_number__")):
            by_provider[provider] = row
    return by_provider


def _source_group_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            _first(row, ["event_id"]) or _first(row, ["batch_id"]) or "NO_EVENT",
            _first(row, ["batch_id"]),
            _first(row, ["release_ts"]),
            _first(row, ["start_ts"]),
            _first(row, ["end_ts"]),
        ]
    )


def _build_source_rows(generated_ts: str, audit_run_id: str, mr_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in mr_rows:
        grouped[_source_group_key(row)].append(row)
    rows = []
    for key, source_rows in grouped.items():
        by_provider = _dedupe_provider_rows(source_rows)
        if len(by_provider) < 2:
            continue
        for provider_a, provider_b in itertools.combinations(sorted(by_provider), 2):
            row_a = by_provider[provider_a]
            row_b = by_provider[provider_b]
            pips_a = _float(row_a.get("realized_pips"))
            pips_b = _float(row_b.get("realized_pips"))
            diff = abs(pips_a - pips_b) if pips_a is not None and pips_b is not None else None
            direction_a = _normalize_direction(row_a.get("real_dir"))
            direction_b = _normalize_direction(row_b.get("real_dir"))
            strength_a = _normalize_strength(row_a.get("real_strength"))
            strength_b = _normalize_strength(row_b.get("real_strength"))
            direction_agreement = bool(direction_a and direction_b and direction_a == direction_b)
            strength_agreement = bool(strength_a and strength_b and strength_a == strength_b)
            if diff is None:
                status = "INSUFFICIENT_PROVIDER_OVERLAP"
                issue = "MISSING_PIPS_FOR_COMPARISON"
            elif not direction_agreement:
                status = "DIRECTION_DISAGREEMENT"
                issue = "SOURCE_DIRECTION_DISAGREEMENT"
            elif diff >= 5:
                status = "LARGE_PIPS_DIFFERENCE"
                issue = "LARGE_PIPS_DIFFERENCE"
            elif not strength_agreement:
                status = "STRENGTH_DISAGREEMENT"
                issue = "SOURCE_STRENGTH_DISAGREEMENT"
            elif diff > 1:
                status = "MINOR_DIFFERENCE"
                issue = "MINOR_PIPS_DIFFERENCE"
            else:
                status = "PASS"
                issue = "NONE"
            out = _base(generated_ts, audit_run_id)
            out.update(
                {
                    "comparison_key": key,
                    "event_id": _first(row_a, ["event_id"]),
                    "batch_id": _first(row_a, ["batch_id"]),
                    "release_ts": _first(row_a, ["release_ts"]),
                    "start_ts": _first(row_a, ["start_ts"]),
                    "end_ts": _first(row_a, ["end_ts"]),
                    "provider_source_a": provider_a,
                    "provider_source_b": provider_b,
                    "realized_pips_a": _fmt(pips_a),
                    "realized_pips_b": _fmt(pips_b),
                    "pips_difference": _fmt(diff),
                    "direction_a": direction_a,
                    "direction_b": direction_b,
                    "direction_agreement": "TRUE" if direction_agreement else "FALSE",
                    "strength_a": strength_a,
                    "strength_b": strength_b,
                    "strength_agreement": "TRUE" if strength_agreement else "FALSE",
                    "candle_count_a": row_a.get("candle_count"),
                    "candle_count_b": row_b.get("candle_count"),
                    "comparison_status": status,
                    "issue_type": issue,
                    "notes": "Provider-source comparison uses latest row per provider for identical event/window key.",
                }
            )
            rows.append(out)
    return rows


def _eval_match_key(row: Dict[str, Any]) -> str:
    return f"{_first(row, ['country'])}|{_first(row, ['release_ts'])}"


def _build_eval_index(eval_rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in eval_rows:
        key = _eval_match_key(row)
        if key != "|":
            index[key].append(row)
    return index


def _parse_outcome_key(value: str) -> Tuple[str, str]:
    if "|" not in value:
        return "", ""
    country, release_ts = value.split("|", 1)
    return country, release_ts


def _build_match_rows(
    generated_ts: str,
    audit_run_id: str,
    accuracy_rows: Sequence[Dict[str, Any]],
    eval_index: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    rows = []
    for acc in accuracy_rows:
        country, release_ts = _parse_outcome_key(_norm(acc.get("outcome_match_key")))
        matches = eval_index.get(f"{country}|{release_ts}", [])
        duplicate_count = len(matches)
        missing = duplicate_count == 0
        ambiguous = duplicate_count > 1
        if missing:
            status = "MISSING"
        elif ambiguous:
            status = "MATCHED_WITH_WARNING"
        else:
            status = "MATCHED_EXACT"
        event_ids = sorted({_norm(row.get("event_id")) for row in matches if _norm(row.get("event_id"))})
        batch_ids = sorted({_norm(row.get("batch_id")) for row in matches if _norm(row.get("batch_id"))})
        row = _base(generated_ts, audit_run_id)
        row.update(
            {
                "accuracy_row_id": acc.get("__source_row_number__"),
                "experiment_id": acc.get("experiment_id"),
                "session_id": acc.get("session_id"),
                "provider": acc.get("provider"),
                "pack_level": acc.get("pack_level"),
                "country": country,
                "release_ts": release_ts,
                "matched_outcome_source": acc.get("outcome_source_sheet") or "Evaluation_Rows",
                "matched_event_id": "|".join(event_ids),
                "matched_batch_id": "|".join(batch_ids),
                "matched_eval_row_key": acc.get("outcome_match_key"),
                "match_status": status,
                "duplicate_match_count": duplicate_count,
                "missing_match": "TRUE" if missing else "FALSE",
                "ambiguous_match": "TRUE" if ambiguous else "FALSE",
                "notes": "Accuracy row matched by exact country + release_ts; duplicate rows reflect provider/prediction multiplicity.",
            }
        )
        rows.append(row)
    return rows


def _mr_release_key(row: Dict[str, Any]) -> str:
    return f"{_first(row, ['country'])}|{_first(row, ['release_ts'])}"


def _build_release_issue_maps(
    mr_rows: Sequence[Dict[str, Any]],
    pips_rows: Sequence[Dict[str, Any]],
    window_rows: Sequence[Dict[str, Any]],
    source_rows: Sequence[Dict[str, Any]],
) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    formula_issue: Set[str] = set()
    window_issue: Set[str] = set()
    direction_disagreement: Set[str] = set()
    strength_disagreement: Set[str] = set()
    source_by_group = {_source_group_key(row): row for row in mr_rows}
    for mr, pips in zip(mr_rows, pips_rows):
        if _norm(pips.get("formula_match")) != "TRUE":
            formula_issue.add(_mr_release_key(mr))
    for mr, window in zip(mr_rows, window_rows):
        if _norm(window.get("window_status")) != "PASS":
            window_issue.add(_mr_release_key(mr))
    for source in source_rows:
        group_mr = source_by_group.get(_norm(source.get("comparison_key")))
        release_key = _mr_release_key(group_mr or {"country": "", "release_ts": source.get("release_ts")})
        if _norm(source.get("direction_agreement")) != "TRUE":
            direction_disagreement.add(release_key)
        if _norm(source.get("strength_agreement")) != "TRUE":
            strength_disagreement.add(release_key)
    return formula_issue, window_issue, direction_disagreement, strength_disagreement


def _build_impact_rows(
    generated_ts: str,
    audit_run_id: str,
    accuracy_rows: Sequence[Dict[str, Any]],
    formula_issue_keys: Set[str],
    window_issue_keys: Set[str],
    direction_disagreement_keys: Set[str],
    strength_disagreement_keys: Set[str],
    direction_threshold: float,
    weak_strength: float,
    medium_strength: float,
) -> List[Dict[str, Any]]:
    rows = []
    for acc in accuracy_rows:
        country, release_ts = _parse_outcome_key(_norm(acc.get("outcome_match_key")))
        release_key = f"{country}|{release_ts}"
        pips = _float(acc.get("realized_pips"))
        threshold_distance = abs(abs(pips) - direction_threshold) if pips is not None else None
        near_direction = threshold_distance is not None and threshold_distance <= 0.25
        near_strength = False
        if pips is not None:
            magnitude = abs(pips)
            near_strength = min(abs(magnitude - weak_strength), abs(magnitude - medium_strength)) <= 0.5
        source_dir = release_key in direction_disagreement_keys
        source_strength = release_key in strength_disagreement_keys
        window_issue = release_key in window_issue_keys
        pips_issue = release_key in formula_issue_keys
        if near_direction or source_dir or window_issue or pips_issue:
            sensitivity = "HIGH"
            handling = "REVIEW_OUTCOME_SOURCE" if source_dir or pips_issue else "REVIEW_WINDOW" if window_issue else "REVIEW_METRIC"
        elif source_strength or near_strength:
            sensitivity = "MEDIUM"
            handling = "KEEP_WITH_WARNING"
        elif pips is None:
            sensitivity = "UNKNOWN"
            handling = "REVIEW_OUTCOME_SOURCE"
        else:
            sensitivity = "LOW"
            handling = "KEEP"
        affected = []
        if near_direction or source_dir:
            affected.append("direction_match_rate")
        if source_strength or near_strength:
            affected.append("overall_ok")
        if window_issue or pips_issue:
            affected.append("all_accuracy_metrics")
        row = _base(generated_ts, audit_run_id)
        row.update(
            {
                "accuracy_row_id": acc.get("__source_row_number__"),
                "experiment_id": acc.get("experiment_id"),
                "session_id": acc.get("session_id"),
                "provider": acc.get("provider"),
                "pack_level": acc.get("pack_level"),
                "forecast_direction": acc.get("forecast_direction_normalized") or acc.get("forecast_direction"),
                "reported_outcome_direction": acc.get("outcome_direction"),
                "reported_realized_pips": acc.get("realized_pips"),
                "direction_threshold_distance": _fmt(threshold_distance),
                "near_direction_boundary": "TRUE" if near_direction else "FALSE",
                "source_direction_disagreement": "TRUE" if source_dir else "FALSE",
                "source_strength_disagreement": "TRUE" if source_strength else "FALSE",
                "window_issue": "TRUE" if window_issue else "FALSE",
                "pips_formula_issue": "TRUE" if pips_issue else "FALSE",
                "accuracy_label_sensitivity": sensitivity,
                "affected_metric": "|".join(sorted(set(affected))) or "NONE",
                "recommended_handling": handling,
                "notes": "Flags possible outcome sensitivity only; does not rerun or modify accuracy labels.",
            }
        )
        rows.append(row)
    return rows


def _trust_classification(issue_count: int, row_count: int, warning_only: bool = False) -> Tuple[str, str]:
    if row_count == 0:
        return "BLOCKED", "INSUFFICIENT_EVIDENCE"
    rate = issue_count / row_count
    if issue_count == 0:
        return "PASS", "TRUSTED"
    if warning_only or rate <= 0.01:
        return "PASS_WITH_WARNINGS", "MOSTLY_TRUSTED_WITH_WARNINGS"
    if rate <= 0.10:
        return "NEEDS_REPAIR", "QUESTIONABLE"
    return "BLOCKED", "NOT_TRUSTED"


def _build_integrity_rows(
    generated_ts: str,
    audit_run_id: str,
    counts: Dict[str, Any],
    missing_critical: Sequence[str],
) -> List[Dict[str, Any]]:
    areas = [
        (
            "pips_construction",
            "MR_ProviderRuns",
            counts["mr_rows_checked"],
            counts["pips_formula_mismatches"],
            "Pips formula should be trusted only if start/end price reconstruction matches reported pips.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            False,
        ),
        (
            "direction_label_construction",
            "MR_ProviderRuns",
            counts["direction_rows_checked"],
            counts["direction_label_mismatches"],
            "Direction labels are threshold-sensitive and should match realized_pips.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            False,
        ),
        (
            "strength_label_construction",
            "MR_ProviderRuns",
            counts["strength_rows_checked"],
            counts["strength_label_mismatches"],
            "Strength labels are threshold-sensitive and affect overall_ok-style metrics.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            False,
        ),
        (
            "window_integrity",
            "MR_ProviderRuns",
            counts["mr_rows_checked"],
            counts["window_issues"],
            "Window integrity controls whether the pips outcome reflects the intended reaction horizon.",
            "PROCEED_TO_PHASE9A5M_WINDOW_DEFINITION_REPAIR"
            if counts["window_issues"]
            else "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            False,
        ),
        (
            "source_consistency",
            "MR_ProviderRuns",
            counts["source_comparison_pairs"],
            counts["source_direction_disagreements"] + counts["large_pips_disagreements"],
            "Provider-source disagreement can make the outcome unstable without proving it wrong.",
            "PROCEED_TO_PHASE9A5M_OUTCOME_SOURCE_REPAIR"
            if counts["source_direction_disagreements"]
            else "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            True,
        ),
        (
            "outcome_matching",
            "Controlled_Accuracy_Evaluation|Evaluation_Rows",
            counts["outcome_matches_checked"],
            counts["outcome_matches_missing"] + counts["outcome_matches_ambiguous"],
            "Accuracy rows should map to intended market outcomes by exact country + release_ts.",
            "PROCEED_TO_PHASE9A5M_OUTCOME_SOURCE_REPAIR"
            if counts["outcome_matches_missing"]
            else "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            True,
        ),
        (
            "accuracy_interpretation_sensitivity",
            "Controlled_Accuracy_Evaluation|MR_ProviderRuns",
            counts["impact_rows_checked"],
            counts["accuracy_rows_high_sensitivity"] + counts["accuracy_rows_medium_sensitivity"],
            "Rows near thresholds or affected by source/window uncertainty need careful interpretation.",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
            True,
        ),
    ]
    rows = []
    for area, source_sheet, checked, issues, impact, action, warning_only in areas:
        status, trust = _trust_classification(issues, checked, warning_only)
        if missing_critical:
            status = "BLOCKED"
            trust = "INSUFFICIENT_EVIDENCE"
        row = {
            **_base(generated_ts, audit_run_id),
            "audit_version": AUDIT_VERSION,
            "audit_area": area,
            "source_sheet": source_sheet,
            "rows_checked": checked,
            "issues_found": issues,
            "issue_rate": _issue_rate(issues, checked),
            "audit_status": status,
            "trust_classification": trust,
            "impact_on_accuracy_evaluation": impact,
            "recommended_action": action if not missing_critical else "RUN_MARKET_REACTION_AUDIT_REPAIR",
            "notes": "missing_critical_inputs=" + "|".join(missing_critical) if missing_critical else "Audit-only; source sheets were read-only.",
        }
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, audit_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("provider_calls_performed", 0, 0),
        ("forecast_generation_performed", 0, 0),
        ("provider_rerun_count", 0, 0),
        ("evaluation_rerun_count", 0, 0),
        ("accuracy_results_modified", 0, 0),
        ("market_reaction_values_modified", 0, 0),
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
        row = _base(generated_ts, audit_run_id)
        row.update(
            {
                "check_id": f"CHK_{name.upper()}",
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if str(expected) == str(actual) else "FAIL",
                "notes": "Outcome integrity audit is read-only and diagnostic-only.",
            }
        )
        rows.append(row)
    return rows


def _highest_risk_source_pair(source_rows: Sequence[Dict[str, Any]]) -> str:
    issue_counter: Counter[str] = Counter()
    for row in source_rows:
        if _norm(row.get("comparison_status")) in {"PASS", "MINOR_DIFFERENCE"}:
            continue
        pair = "|".join(sorted([_norm(row.get("provider_source_a")), _norm(row.get("provider_source_b"))]))
        issue_counter[pair] += 1
    return issue_counter.most_common(1)[0][0] if issue_counter else "NONE"


def _overall_trust(counts: Dict[str, Any], missing_critical: Sequence[str]) -> Tuple[str, str, str, str, str]:
    if missing_critical:
        return (
            "FAIL",
            "MARKET_REACTION_OUTCOME_INTEGRITY_BLOCKED",
            "INSUFFICIENT_EVIDENCE",
            "missing_critical_inputs",
            "RUN_MARKET_REACTION_AUDIT_REPAIR",
        )
    if counts["pips_formula_mismatches"] or counts["direction_label_mismatches"] or counts["window_issues"]:
        return (
            "PASS_WITH_WARNINGS",
            "MARKET_REACTION_OUTCOME_INTEGRITY_NEEDS_REPAIR",
            "QUESTIONABLE",
            "market_reaction_construction_or_window_issue",
            "PROCEED_TO_PHASE9A5M_OUTCOME_SOURCE_REPAIR",
        )
    if counts["source_direction_disagreements"] or counts["large_pips_disagreements"] or counts["accuracy_rows_high_sensitivity"]:
        return (
            "PASS_WITH_WARNINGS",
            "MARKET_REACTION_OUTCOME_INTEGRITY_TRUSTED_WITH_WARNINGS",
            "MOSTLY_TRUSTED_WITH_WARNINGS",
            "source_or_threshold_sensitivity",
            "PROCEED_TO_PHASE9A5M_METRIC_OR_OUTCOME_REPAIR",
        )
    if counts["strength_label_mismatches"] or counts["source_strength_disagreements"] or counts["accuracy_rows_medium_sensitivity"]:
        return (
            "PASS_WITH_WARNINGS",
            "MARKET_REACTION_OUTCOME_INTEGRITY_TRUSTED_WITH_WARNINGS",
            "MOSTLY_TRUSTED_WITH_WARNINGS",
            "strength_or_metric_boundary_sensitivity",
            "PROCEED_TO_PHASE9A5M_METRIC_REPAIR_ONLY",
        )
    return (
        "PASS",
        "MARKET_REACTION_OUTCOME_INTEGRITY_TRUSTED",
        "TRUSTED",
        "none_detected",
        "PROCEED_TO_PHASE9A5M_METRIC_REPAIR_ONLY",
    )


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("MARKET_REACTION_OUTCOME_INTEGRITY_AUDIT", OUTPUT_INTEGRITY, "market_reaction_outcome_integrity_audit"),
        ("MARKET_REACTION_PIPS_FORMULA_AUDIT", OUTPUT_PIPS, "market_reaction_pips_formula_audit"),
        ("MARKET_REACTION_DIRECTION_LABEL_AUDIT", OUTPUT_DIRECTION, "market_reaction_direction_label_audit"),
        ("MARKET_REACTION_STRENGTH_LABEL_AUDIT", OUTPUT_STRENGTH, "market_reaction_strength_label_audit"),
        ("MARKET_REACTION_WINDOW_AUDIT", OUTPUT_WINDOW, "market_reaction_window_audit"),
        ("MARKET_REACTION_SOURCE_COMPARISON_AUDIT", OUTPUT_SOURCE, "market_reaction_source_comparison_audit"),
        ("MARKET_REACTION_OUTCOME_MATCH_AUDIT", OUTPUT_MATCH, "market_reaction_outcome_match_audit"),
        ("MARKET_REACTION_ACCURACY_IMPACT_AUDIT", OUTPUT_IMPACT, "market_reaction_accuracy_impact_audit"),
        ("MARKET_REACTION_GOVERNANCE_AUDIT", OUTPUT_GOVERNANCE, "market_reaction_governance_audit"),
        ("MARKET_REACTION_OUTCOME_INTEGRITY_SUMMARY", OUTPUT_SUMMARY, "market_reaction_outcome_integrity_summary"),
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
            "notes": "Phase 9A-5M-0 market reaction outcome integrity audit; read-only diagnostics.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5M-0 market reaction outcome integrity audit.")
    return parser.parse_args(argv)


def build_market_reaction_outcome_integrity_audit_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    _ = args
    generated_ts = _iso_now()
    audit_run_id = _run_id(generated_ts)
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

    config = _config_map(main_inputs["Config"])
    direction_threshold = _direction_threshold(config)
    weak_strength, medium_strength, strength_threshold_label = _strength_thresholds(config)
    expected_window = _float(config.get("MR_HORIZON_MIN"))

    mr_rows = main_inputs["MR_ProviderRuns"]
    eval_rows = main_inputs["Evaluation_Rows"]
    outcome_rows = main_inputs["Outcome_Ledger"]
    accuracy_rows = diag_inputs["Controlled_Accuracy_Evaluation"]

    pips_rows = _build_pips_rows(generated_ts, audit_run_id, mr_rows)
    # Row-level label construction audits are intentionally anchored to the
    # market-reaction source sheet. Derived Evaluation/Outcome sheets are read
    # for matching/context, but duplicating them here can exceed workbook cell
    # limits without adding source-construction evidence.
    direction_rows = _build_direction_rows(
        generated_ts,
        audit_run_id,
        [("MR_ProviderRuns", mr_rows)],
        direction_threshold,
    )
    strength_rows = _build_strength_rows(
        generated_ts,
        audit_run_id,
        [("MR_ProviderRuns", mr_rows)],
        weak_strength,
        medium_strength,
        strength_threshold_label,
    )
    window_rows = _build_window_rows(generated_ts, audit_run_id, mr_rows, expected_window)
    source_rows = _build_source_rows(generated_ts, audit_run_id, mr_rows)
    eval_index = _build_eval_index(eval_rows)
    match_rows = _build_match_rows(generated_ts, audit_run_id, accuracy_rows, eval_index)
    formula_issue_keys, window_issue_keys, source_direction_keys, source_strength_keys = _build_release_issue_maps(
        mr_rows, pips_rows, window_rows, source_rows
    )
    impact_rows = _build_impact_rows(
        generated_ts,
        audit_run_id,
        accuracy_rows,
        formula_issue_keys,
        window_issue_keys,
        source_direction_keys,
        source_strength_keys,
        direction_threshold,
        weak_strength,
        medium_strength,
    )
    governance_rows = _build_governance_rows(generated_ts, audit_run_id)

    counts = {
        "mr_rows_checked": len(mr_rows),
        "pips_formula_mismatches": sum(1 for row in pips_rows if _norm(row.get("formula_match")) != "TRUE"),
        "direction_rows_checked": len(direction_rows),
        "direction_label_mismatches": sum(1 for row in direction_rows if _norm(row.get("direction_match")) != "TRUE"),
        "strength_rows_checked": len(strength_rows),
        "strength_label_mismatches": sum(1 for row in strength_rows if _norm(row.get("strength_match")) != "TRUE"),
        "window_issues": sum(1 for row in window_rows if _norm(row.get("window_status")) != "PASS"),
        "source_comparison_pairs": len(source_rows),
        "source_direction_disagreements": sum(1 for row in source_rows if _norm(row.get("direction_agreement")) != "TRUE"),
        "source_strength_disagreements": sum(1 for row in source_rows if _norm(row.get("strength_agreement")) != "TRUE"),
        "large_pips_disagreements": sum(1 for row in source_rows if _norm(row.get("comparison_status")) == "LARGE_PIPS_DIFFERENCE"),
        "outcome_matches_checked": len(match_rows),
        "outcome_matches_missing": sum(1 for row in match_rows if _norm(row.get("missing_match")) == "TRUE"),
        "outcome_matches_ambiguous": sum(1 for row in match_rows if _norm(row.get("ambiguous_match")) == "TRUE"),
        "impact_rows_checked": len(impact_rows),
        "accuracy_rows_high_sensitivity": sum(1 for row in impact_rows if _norm(row.get("accuracy_label_sensitivity")) == "HIGH"),
        "accuracy_rows_medium_sensitivity": sum(1 for row in impact_rows if _norm(row.get("accuracy_label_sensitivity")) == "MEDIUM"),
    }
    integrity_rows = _build_integrity_rows(generated_ts, audit_run_id, counts, missing_critical)
    build_status, final_interpretation, trust, primary_risk, recommended_next = _overall_trust(counts, missing_critical)
    highest_risk_pair = _highest_risk_source_pair(source_rows)
    recommended_metric = (
        "REVIEW_DIRECTION_AND_OVERALL_OK_THRESHOLD_SENSITIVITY"
        if counts["accuracy_rows_high_sensitivity"] or counts["accuracy_rows_medium_sensitivity"]
        else "PROCEED_WITH_METRIC_REPAIR_USING_CURRENT_OUTCOME_LAYER"
    )
    recommended_outcome = (
        "REVIEW_OUTCOME_SOURCE"
        if counts["source_direction_disagreements"] or counts["large_pips_disagreements"] or counts["window_issues"]
        else "KEEP_WITH_WARNING"
        if counts["accuracy_rows_high_sensitivity"] or counts["accuracy_rows_medium_sensitivity"]
        else "KEEP"
    )
    summary_row = {
        **_base(generated_ts, audit_run_id),
        "audit_version": AUDIT_VERSION,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "mr_rows_checked": counts["mr_rows_checked"],
        "pips_formula_mismatches": counts["pips_formula_mismatches"],
        "direction_label_mismatches": counts["direction_label_mismatches"],
        "strength_label_mismatches": counts["strength_label_mismatches"],
        "window_issues": counts["window_issues"],
        "source_comparison_pairs": counts["source_comparison_pairs"],
        "source_direction_disagreements": counts["source_direction_disagreements"],
        "source_strength_disagreements": counts["source_strength_disagreements"],
        "large_pips_disagreements": counts["large_pips_disagreements"],
        "outcome_matches_checked": counts["outcome_matches_checked"],
        "outcome_matches_missing": counts["outcome_matches_missing"],
        "outcome_matches_ambiguous": counts["outcome_matches_ambiguous"],
        "accuracy_rows_high_sensitivity": counts["accuracy_rows_high_sensitivity"],
        "accuracy_rows_medium_sensitivity": counts["accuracy_rows_medium_sensitivity"],
        "market_reaction_trust_classification": trust,
        "primary_risk": primary_risk,
        "highest_risk_source_pair": highest_risk_pair,
        "recommended_outcome_handling": recommended_outcome,
        "recommended_metric_handling": recommended_metric,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_phase9a5m_metric_or_outcome_repair": "TRUE" if not missing_critical else "FALSE",
        "ready_for_accuracy_replication": "FALSE",
        "ready_for_production": "FALSE",
        "recommended_next_step": recommended_next,
        "notes": json.dumps(
            {
                "missing_main_inputs": sorted(missing_main),
                "missing_diagnostics_inputs": sorted(missing_diag),
                "missing_critical_inputs": missing_critical,
                "direction_threshold_pips": direction_threshold,
                "strength_thresholds": {"weak_lt": weak_strength, "medium_lt": medium_strength},
                "expected_window_minutes": expected_window,
                "read_only_audit": True,
            },
            sort_keys=True,
        ),
    }
    summary_rows = [summary_row]

    outputs = [
        (OUTPUT_INTEGRITY, INTEGRITY_HEADERS, integrity_rows),
        (OUTPUT_PIPS, PIPS_HEADERS, pips_rows),
        (OUTPUT_DIRECTION, DIRECTION_HEADERS, direction_rows),
        (OUTPUT_STRENGTH, STRENGTH_HEADERS, strength_rows),
        (OUTPUT_WINDOW, WINDOW_HEADERS, window_rows),
        (OUTPUT_SOURCE, SOURCE_HEADERS, source_rows),
        (OUTPUT_MATCH, MATCH_HEADERS, match_rows),
        (OUTPUT_IMPACT, IMPACT_HEADERS, impact_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_market_reaction_outcome_integrity_audit_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "mr_rows_checked": counts["mr_rows_checked"],
        "pips_formula_mismatches": counts["pips_formula_mismatches"],
        "direction_label_mismatches": counts["direction_label_mismatches"],
        "strength_label_mismatches": counts["strength_label_mismatches"],
        "window_issues": counts["window_issues"],
        "source_comparison_pairs": counts["source_comparison_pairs"],
        "source_direction_disagreements": counts["source_direction_disagreements"],
        "source_strength_disagreements": counts["source_strength_disagreements"],
        "large_pips_disagreements": counts["large_pips_disagreements"],
        "outcome_matches_checked": counts["outcome_matches_checked"],
        "outcome_matches_missing": counts["outcome_matches_missing"],
        "outcome_matches_ambiguous": counts["outcome_matches_ambiguous"],
        "accuracy_rows_high_sensitivity": counts["accuracy_rows_high_sensitivity"],
        "accuracy_rows_medium_sensitivity": counts["accuracy_rows_medium_sensitivity"],
        "market_reaction_trust_classification": trust,
        "primary_risk": primary_risk,
        "highest_risk_source_pair": highest_risk_pair,
        "recommended_outcome_handling": recommended_outcome,
        "recommended_metric_handling": recommended_metric,
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "evaluation_rerun_count": 0,
        "accuracy_results_modified": 0,
        "market_reaction_values_modified": 0,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_phase9a5m_metric_or_outcome_repair": not bool(missing_critical),
        "ready_for_accuracy_replication": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_market_reaction_outcome_integrity_audit_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
