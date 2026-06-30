import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_signal_synchrony_conditional_value_audit import (
    DIAGNOSTICS_SPREADSHEET_ID,
    _as_bool,
    _parse_dt,
    _round4,
    _sheet_to_rows,
    _ensure_sheet,
    _write_rows,
)
from automation.build_signal_synchrony_conditional_value_stability import (
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_MECHANISM_SHEET = "Signal_Synchrony_Conditional_Value_Mechanism"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Conditional_Value_Mechanism_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_CONDITIONAL_VALUE_MECHANISM",
        "physical_sheet_name": OUTPUT_MECHANISM_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only CPV mechanism audit",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_CONDITIONAL_VALUE_MECHANISM_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only CPV mechanism summary",
    },
]

MECHANISM_HEADERS = [
    "generated_ts",
    "row_type",
    "mechanism",
    "mechanism_rank",
    "mechanism_strength",
    "mechanism_interpretation",
    "dimension",
    "slice_label",
    "provider",
    "event_family",
    "cohort_group",
    "time_window",
    "predictability_bucket",
    "importance",
    "comparable_events",
    "baseline_correct_rate",
    "walk_forward_correct_rate",
    "conditional_value_gain",
    "oracle_correct_rate",
    "distance_to_oracle",
    "contribution_to_total_gain",
    "share_of_positive_contribution_pct",
    "concentration_ratio",
    "positive_slice_count",
    "negative_slice_count",
    "confidence_label",
    "stability_label",
    "drift_label",
    "avg_forecast_direction_concentration",
    "avg_pattern_concentration_score",
    "avg_expression_similarity",
    "dominant_direction",
    "dominant_causal_family",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "rank",
    "mechanism",
    "mechanism_strength",
    "confidence_label",
    "cpv_gain",
    "concentration_ratio",
    "comparable_events",
    "dominant_slice",
    "positive_contributor",
    "negative_contributor",
    "interpretation",
    "overall_interpretation",
    "notes",
]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _as_float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if raw == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def _confidence_label(comparable_events: int) -> str:
    if comparable_events >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_events >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_events >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _mechanism_strength_from_ratio(
    comparable_events: int,
    concentration_ratio: Optional[float],
    positive_count: int,
    negative_count: int,
) -> str:
    if comparable_events < 5:
        return "INSUFFICIENT_DATA"
    if concentration_ratio is None or concentration_ratio <= 0:
        return "VERY_LOW"
    if concentration_ratio >= 0.85:
        return "VERY_HIGH"
    if concentration_ratio >= 0.65:
        return "HIGH"
    if concentration_ratio >= 0.45:
        return "MODERATE"
    if concentration_ratio >= 0.20:
        return "LOW"
    if positive_count == 0 and negative_count > 0:
        return "VERY_LOW"
    return "LOW"


def _dependence_interpretation(concentration_ratio: Optional[float], comparable_events: int) -> str:
    if comparable_events < 5 or concentration_ratio is None:
        return "LOW"
    if concentration_ratio >= 0.65:
        return "HIGH"
    if concentration_ratio >= 0.35:
        return "MODERATE"
    return "LOW"


def _rank_strength(strength: str) -> int:
    order = {
        "VERY_HIGH": 5,
        "HIGH": 4,
        "MODERATE": 3,
        "LOW": 2,
        "VERY_LOW": 1,
        "INSUFFICIENT_DATA": 0,
    }
    return order.get(strength, -1)


def _read_required_rows(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "cpv_audit": "Signal_Synchrony_Conditional_Value_Audit",
        "cpv_summary": "Signal_Synchrony_Conditional_Value_Summary",
        "stability": "Signal_Synchrony_Conditional_Value_Stability",
        "stability_summary": "Signal_Synchrony_Conditional_Value_Stability_Summary",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "family_slice": "Signal_Synchrony_Family_Slice_Performance",
        "cohort_characterization": "Signal_Synchrony_Cohort_Characterization",
        "microcohort": "Provider_Character_Direct_Expression_Microcohort",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _stability_dimension_rows(rows: Sequence[Dict[str, Any]], dimension: str) -> List[Dict[str, Any]]:
    return [row for row in rows if _norm(row.get("dimension")).upper() == dimension.upper()]


def _top_positive(rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    positives = [
        row for row in rows
        if _as_float(row.get("contribution_to_total_gain")) is not None
        and (_as_float(row.get("contribution_to_total_gain")) or 0.0) > 0
    ]
    if not positives:
        return None
    positives.sort(
        key=lambda row: (
            -(_as_float(row.get("contribution_to_total_gain")) or 0.0),
            _norm(row.get("slice_label")),
        )
    )
    return positives[0]


def _top_negative(rows: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    negatives = [
        row for row in rows
        if _as_float(row.get("contribution_to_total_gain")) is not None
        and (_as_float(row.get("contribution_to_total_gain")) or 0.0) < 0
    ]
    if not negatives:
        return None
    negatives.sort(
        key=lambda row: (
            _as_float(row.get("contribution_to_total_gain")) or 0.0,
            _norm(row.get("slice_label")),
        )
    )
    return negatives[0]


def _mechanism_rows_from_dimension(
    generated_ts: str,
    mechanism_name: str,
    dimension: str,
    rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    positive_contributions = [
        _as_float(row.get("contribution_to_total_gain")) or 0.0
        for row in rows
        if (_as_float(row.get("contribution_to_total_gain")) or 0.0) > 0
    ]
    total_positive = sum(positive_contributions)
    top_positive = _top_positive(rows)
    top_negative = _top_negative(rows)
    top_positive_contribution = _as_float(top_positive.get("contribution_to_total_gain")) if top_positive else None
    concentration_ratio = None
    if top_positive_contribution is not None and total_positive > 0:
        concentration_ratio = top_positive_contribution / total_positive
    positive_count = sum(1 for row in rows if (_as_float(row.get("conditional_value_gain")) or 0.0) > 0)
    negative_count = sum(1 for row in rows if (_as_float(row.get("conditional_value_gain")) or 0.0) < 0)
    comparable_events = sum(int(float(_norm(row.get("comparable_events")) or 0)) for row in rows if _norm(row.get("comparable_events")))
    mechanism_strength = _mechanism_strength_from_ratio(comparable_events, concentration_ratio, positive_count, negative_count)
    mechanism_interpretation = _dependence_interpretation(concentration_ratio, comparable_events)

    out_rows: List[Dict[str, Any]] = []
    overview_row = {
        "generated_ts": generated_ts,
        "row_type": "MECHANISM_OVERVIEW",
        "mechanism": mechanism_name,
        "mechanism_rank": "",
        "mechanism_strength": mechanism_strength,
        "mechanism_interpretation": mechanism_interpretation,
        "dimension": dimension,
        "slice_label": mechanism_name,
        "provider": "",
        "event_family": "",
        "cohort_group": "",
        "time_window": "",
        "predictability_bucket": "",
        "importance": "",
        "comparable_events": comparable_events,
        "baseline_correct_rate": "",
        "walk_forward_correct_rate": "",
        "conditional_value_gain": "",
        "oracle_correct_rate": "",
        "distance_to_oracle": "",
        "contribution_to_total_gain": _round4(sum((_as_float(r.get("contribution_to_total_gain")) or 0.0) for r in rows)),
        "share_of_positive_contribution_pct": _round4(concentration_ratio),
        "concentration_ratio": _round4(concentration_ratio),
        "positive_slice_count": positive_count,
        "negative_slice_count": negative_count,
        "confidence_label": _confidence_label(comparable_events),
        "stability_label": "",
        "drift_label": "",
        "avg_forecast_direction_concentration": "",
        "avg_pattern_concentration_score": "",
        "avg_expression_similarity": "",
        "dominant_direction": "",
        "dominant_causal_family": "",
        "notes": (
            f"Top positive slice={_norm(top_positive.get('slice_label')) if top_positive else ''}; "
            f"top negative slice={_norm(top_negative.get('slice_label')) if top_negative else ''}"
        ),
    }
    out_rows.append(overview_row)

    for row in rows:
        item = {
            "generated_ts": generated_ts,
            "row_type": "SLICE",
            "mechanism": mechanism_name,
            "mechanism_rank": "",
            "mechanism_strength": mechanism_strength,
            "mechanism_interpretation": mechanism_interpretation,
            "dimension": dimension,
            "slice_label": _norm(row.get("slice_label")),
            "provider": _norm(row.get("provider")),
            "event_family": _norm(row.get("event_family")),
            "cohort_group": _norm(row.get("cohort_group")),
            "time_window": _norm(row.get("time_window")),
            "predictability_bucket": _norm(row.get("predictability_bucket")),
            "importance": _norm(row.get("importance")),
            "comparable_events": _norm(row.get("comparable_events")),
            "baseline_correct_rate": _norm(row.get("baseline_correct_rate")),
            "walk_forward_correct_rate": _norm(row.get("walk_forward_correct_rate")),
            "conditional_value_gain": _norm(row.get("conditional_value_gain")),
            "oracle_correct_rate": _norm(row.get("oracle_correct_rate")),
            "distance_to_oracle": _norm(row.get("distance_to_oracle")),
            "contribution_to_total_gain": _norm(row.get("contribution_to_total_gain")),
            "share_of_positive_contribution_pct": _norm(row.get("share_of_positive_contribution_pct")),
            "concentration_ratio": _round4(concentration_ratio),
            "positive_slice_count": positive_count,
            "negative_slice_count": negative_count,
            "confidence_label": _norm(row.get("confidence_label")),
            "stability_label": _norm(row.get("stability_classification")),
            "drift_label": "",
            "avg_forecast_direction_concentration": "",
            "avg_pattern_concentration_score": "",
            "avg_expression_similarity": "",
            "dominant_direction": "",
            "dominant_causal_family": "",
            "notes": _norm(row.get("notes")),
        }
        out_rows.append(item)

    mechanism_summary = {
        "mechanism": mechanism_name,
        "dimension": dimension,
        "mechanism_strength": mechanism_strength,
        "mechanism_interpretation": mechanism_interpretation,
        "concentration_ratio": concentration_ratio,
        "comparable_events": comparable_events,
        "top_positive": top_positive,
        "top_negative": top_negative,
        "confidence_label": _confidence_label(comparable_events),
        "cpv_gain": sum((_as_float(r.get("contribution_to_total_gain")) or 0.0) for r in rows),
    }
    return out_rows, mechanism_summary


def _temporal_mechanism(
    generated_ts: str,
    time_rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    gains = [_as_float(row.get("conditional_value_gain")) for row in time_rows if _as_float(row.get("conditional_value_gain")) is not None]
    comparable_events = sum(int(float(_norm(row.get("comparable_events")) or 0)) for row in time_rows if _norm(row.get("comparable_events")))
    gain_range = (max(gains) - min(gains)) if gains else None
    nonnegative = sum(1 for g in gains if g is not None and g >= 0)
    if len(gains) < 2 or comparable_events < 8:
        label = "INSUFFICIENT_DATA"
        interpretation = "INSUFFICIENT_DATA"
    elif nonnegative == len(gains) and (gain_range or 0.0) <= 0.08:
        label = "LOW"
        interpretation = "STABLE"
    elif nonnegative >= max(1, len(gains) - 1) and (gain_range or 0.0) <= 0.18:
        label = "MODERATE"
        interpretation = "MODERATELY_STABLE"
    else:
        label = "HIGH"
        interpretation = "DRIFTING"

    out_rows = [{
        "generated_ts": generated_ts,
        "row_type": "MECHANISM_OVERVIEW",
        "mechanism": "Temporal Stability",
        "mechanism_rank": "",
        "mechanism_strength": label,
        "mechanism_interpretation": interpretation,
        "dimension": "TIME",
        "slice_label": "Temporal Stability",
        "provider": "",
        "event_family": "",
        "cohort_group": "",
        "time_window": "",
        "predictability_bucket": "",
        "importance": "",
        "comparable_events": comparable_events,
        "baseline_correct_rate": "",
        "walk_forward_correct_rate": "",
        "conditional_value_gain": _round4(_safe_mean(gains)),
        "oracle_correct_rate": "",
        "distance_to_oracle": "",
        "contribution_to_total_gain": _round4(sum((_as_float(r.get("contribution_to_total_gain")) or 0.0) for r in time_rows)),
        "share_of_positive_contribution_pct": "",
        "concentration_ratio": _round4(gain_range),
        "positive_slice_count": sum(1 for g in gains if g is not None and g > 0),
        "negative_slice_count": sum(1 for g in gains if g is not None and g < 0),
        "confidence_label": _confidence_label(comparable_events),
        "stability_label": interpretation,
        "drift_label": "",
        "avg_forecast_direction_concentration": "",
        "avg_pattern_concentration_score": "",
        "avg_expression_similarity": "",
        "dominant_direction": "",
        "dominant_causal_family": "",
        "notes": f"time_gain_range={_round4(gain_range)}",
    }]
    for row in time_rows:
        out_rows.append({
            "generated_ts": generated_ts,
            "row_type": "SLICE",
            "mechanism": "Temporal Stability",
            "mechanism_rank": "",
            "mechanism_strength": label,
            "mechanism_interpretation": interpretation,
            "dimension": "TIME",
            "slice_label": _norm(row.get("slice_label")),
            "provider": "",
            "event_family": "",
            "cohort_group": "",
            "time_window": _norm(row.get("time_window")) or _norm(row.get("slice_label")),
            "predictability_bucket": "",
            "importance": "",
            "comparable_events": _norm(row.get("comparable_events")),
            "baseline_correct_rate": _norm(row.get("baseline_correct_rate")),
            "walk_forward_correct_rate": _norm(row.get("walk_forward_correct_rate")),
            "conditional_value_gain": _norm(row.get("conditional_value_gain")),
            "oracle_correct_rate": _norm(row.get("oracle_correct_rate")),
            "distance_to_oracle": _norm(row.get("distance_to_oracle")),
            "contribution_to_total_gain": _norm(row.get("contribution_to_total_gain")),
            "share_of_positive_contribution_pct": _norm(row.get("share_of_positive_contribution_pct")),
            "concentration_ratio": _round4(gain_range),
            "positive_slice_count": sum(1 for g in gains if g is not None and g > 0),
            "negative_slice_count": sum(1 for g in gains if g is not None and g < 0),
            "confidence_label": _norm(row.get("confidence_label")),
            "stability_label": _norm(row.get("stability_classification")),
            "drift_label": "",
            "avg_forecast_direction_concentration": "",
            "avg_pattern_concentration_score": "",
            "avg_expression_similarity": "",
            "dominant_direction": "",
            "dominant_causal_family": "",
            "notes": _norm(row.get("notes")),
        })
    summary = {
        "mechanism": "Temporal Stability",
        "dimension": "TIME",
        "mechanism_strength": label,
        "mechanism_interpretation": interpretation,
        "concentration_ratio": gain_range,
        "comparable_events": comparable_events,
        "top_positive": _top_positive(time_rows),
        "top_negative": _top_negative(time_rows),
        "confidence_label": _confidence_label(comparable_events),
        "cpv_gain": sum((_as_float(r.get("contribution_to_total_gain")) or 0.0) for r in time_rows),
    }
    return out_rows, summary


def _drift_mechanism(
    generated_ts: str,
    microcohort_rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    sorted_rows = sorted(
        [row for row in microcohort_rows if _parse_dt(row.get("release_ts")) is not None],
        key=lambda row: (_parse_dt(row.get("release_ts")), _norm(row.get("sample_group_id"))),
    )
    total = len(sorted_rows)
    base = total // 3
    rem = total % 3
    sizes = [base + (1 if i < rem else 0) for i in range(3)]
    labels = ["early", "middle", "late"]
    windows: List[Tuple[str, List[Dict[str, Any]]]] = []
    cursor = 0
    for label, size in zip(labels, sizes):
        windows.append((label, sorted_rows[cursor:cursor + size]))
        cursor += size

    drift_rows: List[Dict[str, Any]] = []
    avg_dir_values: List[Optional[float]] = []
    avg_pattern_values: List[Optional[float]] = []
    avg_expr_values: List[Optional[float]] = []
    dominant_dirs: List[str] = []
    dominant_causal: List[str] = []

    for label, rows in windows:
        dir_avg = _safe_mean(_as_float(r.get("forecast_direction_concentration")) for r in rows)
        pattern_avg = _safe_mean(_as_float(r.get("pattern_concentration_score")) for r in rows)
        expr_avg = _safe_mean(_as_float(r.get("expression_similarity_mean_if_available")) for r in rows)
        dir_counter = Counter(_norm(r.get("dominant_forecast_direction")) or "unknown" for r in rows)
        causal_counter = Counter(_norm(r.get("dominant_causal_family_if_classifiable")) or "unknown" for r in rows)
        dominant_direction = dir_counter.most_common(1)[0][0] if dir_counter else "unknown"
        dominant_causal_family = causal_counter.most_common(1)[0][0] if causal_counter else "unknown"
        avg_dir_values.append(dir_avg)
        avg_pattern_values.append(pattern_avg)
        avg_expr_values.append(expr_avg)
        dominant_dirs.append(dominant_direction)
        dominant_causal.append(dominant_causal_family)
        drift_rows.append({
            "generated_ts": generated_ts,
            "row_type": "DRIFT_WINDOW",
            "mechanism": "Character Drift",
            "mechanism_rank": "",
            "mechanism_strength": "",
            "mechanism_interpretation": "",
            "dimension": "CHARACTER_DRIFT",
            "slice_label": label,
            "provider": "",
            "event_family": "",
            "cohort_group": "",
            "time_window": label,
            "predictability_bucket": "",
            "importance": "",
            "comparable_events": len(rows),
            "baseline_correct_rate": "",
            "walk_forward_correct_rate": "",
            "conditional_value_gain": "",
            "oracle_correct_rate": "",
            "distance_to_oracle": "",
            "contribution_to_total_gain": "",
            "share_of_positive_contribution_pct": "",
            "concentration_ratio": "",
            "positive_slice_count": "",
            "negative_slice_count": "",
            "confidence_label": _confidence_label(len(rows)),
            "stability_label": "",
            "drift_label": "",
            "avg_forecast_direction_concentration": _round4(dir_avg),
            "avg_pattern_concentration_score": _round4(pattern_avg),
            "avg_expression_similarity": _round4(expr_avg),
            "dominant_direction": dominant_direction,
            "dominant_causal_family": dominant_causal_family,
            "notes": "",
        })

    dir_range = None
    pat_range = None
    expr_range = None
    valid_dir = [v for v in avg_dir_values if v is not None]
    valid_pat = [v for v in avg_pattern_values if v is not None]
    valid_expr = [v for v in avg_expr_values if v is not None]
    if valid_dir:
        dir_range = max(valid_dir) - min(valid_dir)
    if valid_pat:
        pat_range = max(valid_pat) - min(valid_pat)
    if valid_expr:
        expr_range = max(valid_expr) - min(valid_expr)
    direction_shift_count = max(0, len(set(dominant_dirs)) - 1)
    causal_shift_count = max(0, len(set(dominant_causal)) - 1)

    if total < 15:
        drift_label = "INSUFFICIENT_DATA"
        strength = "INSUFFICIENT_DATA"
    elif (dir_range or 0.0) >= 0.15 or (pat_range or 0.0) >= 0.15 or direction_shift_count >= 2:
        drift_label = "MAJOR_DRIFT"
        strength = "HIGH"
    elif (dir_range or 0.0) >= 0.07 or (pat_range or 0.0) >= 0.07 or direction_shift_count >= 1 or causal_shift_count >= 1:
        drift_label = "MINOR_DRIFT"
        strength = "MODERATE"
    else:
        drift_label = "STABLE"
        strength = "LOW"

    overview = {
        "generated_ts": generated_ts,
        "row_type": "MECHANISM_OVERVIEW",
        "mechanism": "Character Drift",
        "mechanism_rank": "",
        "mechanism_strength": strength,
        "mechanism_interpretation": drift_label,
        "dimension": "CHARACTER_DRIFT",
        "slice_label": "Character Drift",
        "provider": "",
        "event_family": "",
        "cohort_group": "",
        "time_window": "",
        "predictability_bucket": "",
        "importance": "",
        "comparable_events": total,
        "baseline_correct_rate": "",
        "walk_forward_correct_rate": "",
        "conditional_value_gain": "",
        "oracle_correct_rate": "",
        "distance_to_oracle": "",
        "contribution_to_total_gain": "",
        "share_of_positive_contribution_pct": "",
        "concentration_ratio": _round4(max(v for v in [dir_range, pat_range, expr_range] if v is not None) if any(v is not None for v in [dir_range, pat_range, expr_range]) else None),
        "positive_slice_count": direction_shift_count,
        "negative_slice_count": causal_shift_count,
        "confidence_label": _confidence_label(total),
        "stability_label": "",
        "drift_label": drift_label,
        "avg_forecast_direction_concentration": _round4(_safe_mean(avg_dir_values)),
        "avg_pattern_concentration_score": _round4(_safe_mean(avg_pattern_values)),
        "avg_expression_similarity": _round4(_safe_mean(avg_expr_values)),
        "dominant_direction": Counter(dominant_dirs).most_common(1)[0][0] if dominant_dirs else "unknown",
        "dominant_causal_family": Counter(dominant_causal).most_common(1)[0][0] if dominant_causal else "unknown",
        "notes": (
            f"dir_range={_round4(dir_range)}; pattern_range={_round4(pat_range)}; "
            f"expr_range={_round4(expr_range)}; direction_shift_count={direction_shift_count}; "
            f"causal_shift_count={causal_shift_count}"
        ),
    }
    out_rows = [overview]
    for row in drift_rows:
        row["mechanism_strength"] = strength
        row["mechanism_interpretation"] = drift_label
        row["drift_label"] = drift_label
        out_rows.append(row)

    summary = {
        "mechanism": "Character Drift",
        "dimension": "CHARACTER_DRIFT",
        "mechanism_strength": strength,
        "mechanism_interpretation": drift_label,
        "concentration_ratio": max(v for v in [dir_range, pat_range, expr_range] if v is not None) if any(v is not None for v in [dir_range, pat_range, expr_range]) else None,
        "comparable_events": total,
        "top_positive": None,
        "top_negative": None,
        "confidence_label": _confidence_label(total),
        "cpv_gain": None,
        "drift_label": drift_label,
    }
    return out_rows, summary


def _overall_interpretation(mechanism_summaries: Sequence[Dict[str, Any]]) -> str:
    lookup = {m["mechanism"]: m for m in mechanism_summaries}
    provider = lookup.get("Provider Dependence")
    family = lookup.get("Event Family Dependence")
    cohort = lookup.get("Cohort Dependence")
    time = lookup.get("Temporal Stability")
    predictability = lookup.get("Predictability Dependence")
    drift = lookup.get("Character Drift")

    if not mechanism_summaries:
        return "INSUFFICIENT_DATA"
    if drift and drift.get("mechanism_interpretation") == "MAJOR_DRIFT" and time and time.get("mechanism_interpretation") == "DRIFTING":
        return "TEMPORAL_DRIFT_DOMINATED"
    if provider and _rank_strength(provider.get("mechanism_strength", "")) >= 4:
        return "PROVIDER_DOMINATED"
    if family and _rank_strength(family.get("mechanism_strength", "")) >= 4:
        return "FAMILY_DOMINATED"
    if predictability and _rank_strength(predictability.get("mechanism_strength", "")) >= 4:
        return "PREDICTABILITY_DOMINATED"
    if any(_rank_strength(m.get("mechanism_strength", "")) >= 3 for m in mechanism_summaries):
        return "MIXED_MECHANISM"
    return "INSUFFICIENT_DATA"


def _build_summary_rows(
    generated_ts: str,
    overall_row: Dict[str, Any],
    mechanism_summaries: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    sorted_mechanisms = sorted(
        mechanism_summaries,
        key=lambda m: (
            -_rank_strength(m.get("mechanism_strength", "")),
            -(m.get("concentration_ratio") if isinstance(m.get("concentration_ratio"), (int, float)) else -1.0),
            m.get("mechanism", ""),
        ),
    )
    overall_interpretation = _overall_interpretation(sorted_mechanisms)

    rows.append({
        "generated_ts": generated_ts,
        "section": "OVERVIEW",
        "rank": 0,
        "mechanism": "Overall CPV",
        "mechanism_strength": "",
        "confidence_label": overall_row.get("confidence_label", ""),
        "cpv_gain": overall_row.get("conditional_value_gain", ""),
        "concentration_ratio": overall_row.get("concentration_ratio", ""),
        "comparable_events": overall_row.get("comparable_events", ""),
        "dominant_slice": "",
        "positive_contributor": "",
        "negative_contributor": "",
        "interpretation": "Overall CPV remains positive but concentrated.",
        "overall_interpretation": overall_interpretation,
        "notes": f"oracle_gap={overall_row.get('distance_to_oracle','')}",
    })

    for rank, summary in enumerate(sorted_mechanisms, start=1):
        top_positive = summary.get("top_positive") or {}
        top_negative = summary.get("top_negative") or {}
        rows.append({
            "generated_ts": generated_ts,
            "section": "MECHANISM_RANKING",
            "rank": rank,
            "mechanism": summary.get("mechanism", ""),
            "mechanism_strength": summary.get("mechanism_strength", ""),
            "confidence_label": summary.get("confidence_label", ""),
            "cpv_gain": _round4(summary.get("cpv_gain")) if summary.get("cpv_gain") is not None else "",
            "concentration_ratio": _round4(summary.get("concentration_ratio")) if summary.get("concentration_ratio") is not None else "",
            "comparable_events": summary.get("comparable_events", ""),
            "dominant_slice": _norm(top_positive.get("slice_label")),
            "positive_contributor": _norm(top_positive.get("slice_label")),
            "negative_contributor": _norm(top_negative.get("slice_label")),
            "interpretation": summary.get("mechanism_interpretation", ""),
            "overall_interpretation": "",
            "notes": f"dimension={summary.get('dimension','')}",
        })

    for summary in sorted_mechanisms:
        rows.append({
            "generated_ts": generated_ts,
            "section": "INTERACTION_MATRIX",
            "rank": "",
            "mechanism": summary.get("mechanism", ""),
            "mechanism_strength": summary.get("mechanism_strength", ""),
            "confidence_label": summary.get("confidence_label", ""),
            "cpv_gain": _round4(summary.get("cpv_gain")) if summary.get("cpv_gain") is not None else "",
            "concentration_ratio": _round4(summary.get("concentration_ratio")) if summary.get("concentration_ratio") is not None else "",
            "comparable_events": summary.get("comparable_events", ""),
            "dominant_slice": _norm((summary.get("top_positive") or {}).get("slice_label")),
            "positive_contributor": _norm((summary.get("top_positive") or {}).get("slice_label")),
            "negative_contributor": _norm((summary.get("top_negative") or {}).get("slice_label")),
            "interpretation": summary.get("mechanism_interpretation", ""),
            "overall_interpretation": "",
            "notes": "Mechanism interaction matrix row.",
        })

    rows.append({
        "generated_ts": generated_ts,
        "section": "FINAL_INTERPRETATION",
        "rank": "",
        "mechanism": "Overall interpretation",
        "mechanism_strength": "",
        "confidence_label": overall_row.get("confidence_label", ""),
        "cpv_gain": overall_row.get("conditional_value_gain", ""),
        "concentration_ratio": overall_row.get("concentration_ratio", ""),
        "comparable_events": overall_row.get("comparable_events", ""),
        "dominant_slice": "",
        "positive_contributor": "",
        "negative_contributor": "",
        "interpretation": (
            "Conditional Value appears to be explained primarily by the highest-ranked mechanisms shown above; "
            "secondary mechanisms remain descriptive only."
        ),
        "overall_interpretation": overall_interpretation,
        "notes": "No provider calls, reruns, or methodology changes were made.",
    })
    return rows


def _upsert_registry_rows(service) -> Dict[str, Any]:
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    if not rows:
        raise RuntimeError("Sheet_Registry is missing or empty.")
    existing_headers = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=PROJECT_OVERVIEWS_SPREADSHEET_ID, range=f"'{REGISTRY_SHEET}'!1:1")
        .execute()
        .get("values", [[]])[0]
    ) or list(REGISTRY_HEADERS)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    by_id = {(_norm(row.get("logical_sheet_id")).upper()): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {(_norm(row.get("logical_sheet_id")).upper()): row for row in rows}
    updates = []
    appended = 0
    for row in REGISTRY_ROWS:
        key = _norm(row["logical_sheet_id"]).upper()
        existing = existing_by_id.get(key, {})
        merged = dict(row)
        if "registry_created_ts" in existing_headers:
            merged["registry_created_ts"] = _norm(existing.get("registry_created_ts")) or now
        if "registry_last_verified_ts" in existing_headers:
            merged["registry_last_verified_ts"] = now
        if "registry_migration_ts" in existing_headers:
            merged["registry_migration_ts"] = _norm(existing.get("registry_migration_ts"))
        if "registry_rename_ts" in existing_headers:
            merged["registry_rename_ts"] = _norm(existing.get("registry_rename_ts"))
        values = [merged.get(header, "") for header in existing_headers]
        if key in by_id:
            row_number = by_id[key]
            updates.append({
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(existing_headers))}{row_number}",
                "values": [values],
            })
        else:
            appended += 1
            target_row = len(rows) + appended
            updates.append({
                "range": f"'{REGISTRY_SHEET}'!A{target_row}:{_column_letter(len(existing_headers))}{target_row}",
                "values": [values],
            })
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(REGISTRY_ROWS) - appended, "appended": appended}


def build_conditional_value_mechanism() -> Dict[str, Any]:
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    sources = _read_required_rows(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    stability_rows = sources["stability"]
    overall_row = next((row for row in stability_rows if _norm(row.get("dimension")).upper() == "OVERALL"), None)
    if not overall_row:
        raise RuntimeError("Signal_Synchrony_Conditional_Value_Stability is missing an OVERALL row.")

    detail_rows: List[Dict[str, Any]] = []
    mechanism_summaries: List[Dict[str, Any]] = []

    for mechanism_name, dimension in [
        ("Provider Dependence", "PROVIDER"),
        ("Event Family Dependence", "FAMILY"),
        ("Cohort Dependence", "COHORT"),
        ("Predictability Dependence", "PREDICTABILITY"),
        ("Importance Dependence", "IMPORTANCE"),
    ]:
        rows, summary = _mechanism_rows_from_dimension(
            generated_ts,
            mechanism_name,
            dimension,
            _stability_dimension_rows(stability_rows, dimension),
        )
        detail_rows.extend(rows)
        mechanism_summaries.append(summary)

    time_rows, time_summary = _temporal_mechanism(
        generated_ts,
        _stability_dimension_rows(stability_rows, "TIME"),
    )
    detail_rows.extend(time_rows)
    mechanism_summaries.append(time_summary)

    drift_rows, drift_summary = _drift_mechanism(
        generated_ts,
        sources["microcohort"],
    )
    detail_rows.extend(drift_rows)
    mechanism_summaries.append(drift_summary)

    mechanism_summaries_sorted = sorted(
        mechanism_summaries,
        key=lambda m: (
            -_rank_strength(m.get("mechanism_strength", "")),
            -(m.get("concentration_ratio") if isinstance(m.get("concentration_ratio"), (int, float)) else -1.0),
            m.get("mechanism", ""),
        ),
    )
    rank_map = {m["mechanism"]: idx + 1 for idx, m in enumerate(mechanism_summaries_sorted)}
    for row in detail_rows:
        if row["row_type"] == "MECHANISM_OVERVIEW":
            row["mechanism_rank"] = rank_map.get(row["mechanism"], "")
        else:
            row["mechanism_rank"] = rank_map.get(row["mechanism"], "")

    summary_rows = _build_summary_rows(generated_ts, overall_row, mechanism_summaries_sorted)

    detail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MECHANISM_SHEET, MECHANISM_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MECHANISM_SHEET, detail_headers, detail_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)
    overall_interpretation = next((row.get("overall_interpretation", "") for row in summary_rows if row.get("section") == "FINAL_INTERPRETATION"), "")
    return {
        "generated_ts": generated_ts,
        "detail_rows_written": len(detail_rows),
        "summary_rows_written": len(summary_rows),
        "mechanisms_ranked": [m["mechanism"] for m in mechanism_summaries_sorted],
        "overall_interpretation": overall_interpretation,
        "registry_result": registry_result,
    }


if __name__ == "__main__":
    result = build_conditional_value_mechanism()
    print(result)
