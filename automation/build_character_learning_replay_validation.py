import re
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
    _ensure_sheet,
    _parse_dt,
    _round4,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_signal_synchrony_conditional_value_stability import (
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
)
from automation.build_signal_synchrony_direction_robustness import _cohort_bucket
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_VALIDATION_SHEET = "Character_Learning_Replay_Validation"
OUTPUT_SUMMARY_SHEET = "Character_Learning_Replay_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "CHARACTER_LEARNING_REPLAY_VALIDATION",
        "physical_sheet_name": OUTPUT_VALIDATION_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v1",
        "notes": "Derived-only character learning replay validation",
    },
    {
        "logical_sheet_id": "CHARACTER_LEARNING_REPLAY_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v1",
        "notes": "Derived-only character learning replay summary",
    },
]

VALIDATION_HEADERS = [
    "generated_ts",
    "replay_id",
    "hypothesis_id",
    "candidate_id",
    "queue_id",
    "replay_test_id",
    "replay_test_name",
    "replay_mode",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "source_slice_type",
    "source_slice_key",
    "candidate_label",
    "validation_queue_label",
    "validation_score",
    "original_correct_rate",
    "original_delta_vs_provider_family_baseline",
    "original_misleading_stability_rate",
    "replay_sample_groups",
    "replay_comparable_rows",
    "replay_correct_count",
    "replay_wrong_count",
    "replay_non_comparable_rows",
    "replay_thin_sample_flag",
    "replay_confidence_label",
    "replay_correct_rate",
    "provider_family_baseline_rate",
    "global_baseline_rate",
    "delta_vs_original_correct_rate",
    "delta_vs_provider_family_baseline",
    "delta_vs_global_baseline",
    "discovery_comparable_rows",
    "discovery_correct_rate",
    "replay_window_comparable_rows",
    "replay_window_correct_rate",
    "replay_window_delta",
    "cohort_bucket",
    "cohort_correct_rate",
    "cohort_delta",
    "replay_misleading_stability_count",
    "replay_misleading_stability_rate",
    "original_misleading_stability_rate",
    "misleading_stability_replay_result",
    "hypothesis_reconstruction_status",
    "time_replay_result_label",
    "cohort_replay_result_label",
    "provider_family_replay_result_label",
    "replay_result_label",
    "replay_interpretation_note",
    "learning_model_approved",
    "routing_approved",
    "weighting_approved",
    "calibration_approved",
    "production_approved",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "rank",
    "hypothesis_id",
    "candidate_id",
    "queue_id",
    "replay_test_id",
    "replay_test_name",
    "replay_mode",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "source_slice_type",
    "source_slice_key",
    "candidate_label",
    "validation_queue_label",
    "validation_score",
    "original_correct_rate",
    "original_delta_vs_provider_family_baseline",
    "original_misleading_stability_rate",
    "replay_sample_groups",
    "replay_comparable_rows",
    "replay_correct_count",
    "replay_wrong_count",
    "replay_non_comparable_rows",
    "replay_thin_sample_flag",
    "replay_confidence_label",
    "replay_correct_rate",
    "provider_family_baseline_rate",
    "global_baseline_rate",
    "delta_vs_original_correct_rate",
    "delta_vs_provider_family_baseline",
    "delta_vs_global_baseline",
    "discovery_comparable_rows",
    "discovery_correct_rate",
    "replay_window_comparable_rows",
    "replay_window_correct_rate",
    "replay_window_delta",
    "cohort_bucket",
    "cohort_correct_rate",
    "cohort_delta",
    "replay_misleading_stability_count",
    "replay_misleading_stability_rate",
    "original_misleading_stability_rate",
    "misleading_stability_replay_result",
    "hypothesis_reconstruction_status",
    "time_replay_result_label",
    "cohort_replay_result_label",
    "provider_family_replay_result_label",
    "replay_result_label",
    "replay_interpretation_note",
    "validate_first_hypotheses_read",
    "hypotheses_reconstructed",
    "hypotheses_failed_reconstruction",
    "total_replay_rows",
    "replay_result_label_counts",
    "replay_mode_counts",
    "providers_represented",
    "families_represented",
    "cohorts_represented",
    "misleading_stability_total",
    "risk_reproduces_count",
    "risk_weakens_count",
    "risk_fails_count",
    "insufficient_risk_data_count",
    "strongest_replayed_hypothesis",
    "strongest_replayed_label",
    "learning_readiness_label",
    "learning_readiness_reason",
    "final_interpretation_label",
    "final_interpretation_reason",
    "notes",
]

REPLAY_TESTS = [
    ("overall_matching_replay", "Overall Matching Replay", "ROBUSTNESS_REPLAY"),
    ("time_walk_forward_replay", "Pseudo Walk-Forward Replay", "PSEUDO_WALK_FORWARD"),
    ("cohort_replay", "Cohort Replay", "COHORT_REPLAY"),
    ("provider_family_baseline_replay", "Provider-Family Baseline Replay", "ROBUSTNESS_REPLAY"),
    ("misleading_stability_replay", "Misleading Stability Replay", "ROBUSTNESS_REPLAY"),
]

PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]
FAMILY_ORDER = ["growth", "inflation", "housing", "labor", "energy", "central_bank", "manufacturing", "other"]
COHORT_ORDER = ["cohort_a", "deterministic", "random", "unknown"]
FINAL_LABEL_ORDER = [
    "GENERALIZES",
    "PARTIALLY_GENERALIZES",
    "WINDOW_DEPENDENT",
    "COHORT_DEPENDENT",
    "FAILED_REPLAY",
    "INSUFFICIENT_REPLAY_DATA",
]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _lower(value: Any) -> str:
    return _norm(value).lower()


def _as_float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if raw == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def _confidence_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _slug(value: Any) -> str:
    raw = _lower(value)
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_") or "missing"


def _count_string(counter: Counter, order: Sequence[str]) -> str:
    parts: List[str] = []
    for key in order:
        if counter.get(key, 0):
            parts.append(f"{key}:{counter[key]}")
    for key in sorted(counter):
        if key in order or counter.get(key, 0) <= 0:
            continue
        parts.append(f"{key}:{counter[key]}")
    return "|".join(parts)


def _is_comparable(row: Dict[str, Any]) -> bool:
    if _as_bool(row.get("actual_comparable")):
        return True
    return _upper(row.get("outcome_result_label")) in {
        "FORECAST_CORRECT",
        "FORECAST_INLINE_CORRECT",
        "FORECAST_WRONG",
    }


def _is_correct(row: Dict[str, Any]) -> bool:
    return _upper(row.get("outcome_result_label")) in {
        "FORECAST_CORRECT",
        "FORECAST_INLINE_CORRECT",
    } or _as_bool(row.get("forecast_matches_actual"))


def _match_condition(row: Dict[str, Any], condition_dimension: str) -> Any:
    if condition_dimension == "event_family":
        return row.get("event_family")
    if condition_dimension == "predictability_bucket":
        return row.get("predictability_bucket")
    if condition_dimension == "direction_synchrony_bucket":
        return row.get("direction_synchrony_bucket")
    if condition_dimension == "stability_label":
        return row.get("stability_label")
    if condition_dimension == "importance":
        return row.get("importance")
    if condition_dimension == "cohort_bucket":
        return _cohort_bucket(row.get("cohort_id"))
    if condition_dimension == "recommended_protocol":
        return row.get("recommended_protocol")
    return row.get(condition_dimension)


def _canon_for_dimension(condition_dimension: str, value: Any) -> str:
    if condition_dimension in {"direction_synchrony_bucket", "stability_label", "recommended_protocol"}:
        return _upper(value)
    if condition_dimension in {"predictability_bucket", "cohort_bucket", "event_family", "importance"}:
        return _lower(value)
    return _lower(value)


def _matches_hypothesis(row: Dict[str, Any], hypothesis: Dict[str, Any]) -> bool:
    if _norm(row.get("provider")) != hypothesis["provider"]:
        return False
    if _norm(row.get("event_family")) != hypothesis["event_family"]:
        return False
    row_value = _match_condition(row, hypothesis["condition_dimension"])
    return _canon_for_dimension(hypothesis["condition_dimension"], row_value) == _canon_for_dimension(
        hypothesis["condition_dimension"], hypothesis["condition_value"]
    )


def _mix_string(rows: Sequence[Dict[str, Any]], field: str, order: Sequence[str]) -> Tuple[str, Counter]:
    counter: Counter = Counter()
    for row in rows:
        value = _norm(row.get(field))
        if not value:
            continue
        counter[value] += 1
    return _count_string(counter, order), counter


def _cohort_mix(rows: Sequence[Dict[str, Any]]) -> Tuple[str, Counter]:
    counter: Counter = Counter()
    for row in rows:
        counter[_cohort_bucket(row.get("cohort_id"))] += 1
    return _count_string(counter, COHORT_ORDER), counter


def _top_count(counter: Counter) -> int:
    return max(counter.values()) if counter else 0


def _sorted_rows_by_release(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _parse_dt(row.get("release_ts")) or datetime.min,
            _parse_dt(row.get("generated_ts")) or datetime.min,
            _norm(row.get("sample_group_id")),
        ),
    )


def _rate(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    comparable_rows = [row for row in rows if _is_comparable(row)]
    if not comparable_rows:
        return None
    return _safe_rate(sum(1 for row in comparable_rows if _is_correct(row)), len(comparable_rows))


def _baseline_rate(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    return _rate(rows)


def _row_counts(rows: Sequence[Dict[str, Any]]) -> Tuple[int, int, int]:
    comparable_rows = [row for row in rows if _is_comparable(row)]
    correct_count = sum(1 for row in comparable_rows if _is_correct(row))
    wrong_count = len(comparable_rows) - correct_count
    return len(comparable_rows), correct_count, wrong_count


def _time_split(rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ordered = _sorted_rows_by_release(rows)
    if len(ordered) <= 1:
        return ordered, []
    midpoint = len(ordered) // 2
    return ordered[:midpoint], ordered[midpoint:]


def _overall_result_label(
    candidate_label: str,
    replay_metric_rate: Optional[float],
    original_metric_rate: Optional[float],
    provider_family_baseline_rate: Optional[float],
    global_baseline_rate: Optional[float],
    time_delta: Optional[float],
    cohort_spread: Optional[float],
    dominant_cohort_share: Optional[float],
) -> str:
    if replay_metric_rate is None or original_metric_rate is None:
        return "INSUFFICIENT_REPLAY_DATA"
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        if replay_metric_rate < original_metric_rate - 0.10:
            return "FAILED_REPLAY"
        if cohort_spread is not None and cohort_spread >= 0.25 and (dominant_cohort_share or 0.0) < 0.8:
            return "COHORT_DEPENDENT"
        if time_delta is not None and abs(time_delta) >= 0.15:
            return "WINDOW_DEPENDENT"
        if (
            replay_metric_rate >= original_metric_rate - 0.05
            and abs(time_delta or 0.0) < 0.10
            and (cohort_spread or 0.0) < 0.20
        ):
            return "GENERALIZES"
        return "PARTIALLY_GENERALIZES"
    if provider_family_baseline_rate is not None and global_baseline_rate is not None:
        if replay_metric_rate < provider_family_baseline_rate - 0.10 and replay_metric_rate < global_baseline_rate - 0.10:
            return "FAILED_REPLAY"
    if cohort_spread is not None and cohort_spread >= 0.25 and (dominant_cohort_share or 0.0) < 0.8:
        return "COHORT_DEPENDENT"
    if time_delta is not None and abs(time_delta) >= 0.15:
        return "WINDOW_DEPENDENT"
    if (
        replay_metric_rate >= original_metric_rate - 0.05
        and provider_family_baseline_rate is not None
        and global_baseline_rate is not None
        and provider_family_baseline_rate >= global_baseline_rate - 0.05
        and abs(time_delta or 0.0) < 0.10
        and (cohort_spread or 0.0) < 0.20
    ):
        return "GENERALIZES"
    return "PARTIALLY_GENERALIZES"


def _time_result_label(discovery_rate: Optional[float], replay_rate: Optional[float]) -> str:
    if discovery_rate is None or replay_rate is None:
        return "INSUFFICIENT_REPLAY_DATA"
    delta = replay_rate - discovery_rate
    if abs(delta) >= 0.15:
        return "WINDOW_DEPENDENT"
    if abs(delta) <= 0.05:
        return "GENERALIZES"
    return "PARTIALLY_GENERALIZES"


def _cohort_result_label(
    cohort_spread: Optional[float],
    dominant_cohort_share: Optional[float],
    dominant_bucket_count: int,
    cohort_bucket_count: int,
) -> str:
    if cohort_bucket_count <= 0:
        return "INSUFFICIENT_REPLAY_DATA"
    if cohort_bucket_count >= 2 and cohort_spread is not None and cohort_spread >= 0.25 and (dominant_cohort_share or 0.0) < 0.8:
        return "COHORT_DEPENDENT"
    if cohort_spread is not None and cohort_spread <= 0.10 and (dominant_cohort_share or 0.0) >= 0.6:
        return "GENERALIZES"
    if cohort_spread is not None and cohort_spread <= 0.20:
        return "PARTIALLY_GENERALIZES"
    return "COHORT_DEPENDENT"


def _provider_family_result_label(
    replay_rate: Optional[float],
    provider_family_baseline_rate: Optional[float],
    global_baseline_rate: Optional[float],
) -> str:
    if replay_rate is None or provider_family_baseline_rate is None or global_baseline_rate is None:
        return "INSUFFICIENT_REPLAY_DATA"
    delta = replay_rate - provider_family_baseline_rate
    if delta <= -0.10 and replay_rate < global_baseline_rate - 0.10:
        return "FAILED_REPLAY"
    if abs(delta) <= 0.05:
        return "GENERALIZES"
    if abs(delta) <= 0.10:
        return "PARTIALLY_GENERALIZES"
    return "WINDOW_DEPENDENT"


def _misleading_replay_result(
    candidate_label: str,
    replay_misleading_rate: Optional[float],
    original_misleading_rate: Optional[float],
) -> str:
    if candidate_label != "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        return "INSUFFICIENT_RISK_DATA"
    if replay_misleading_rate is None or original_misleading_rate is None:
        return "INSUFFICIENT_RISK_DATA"
    if replay_misleading_rate >= original_misleading_rate - 0.05:
        return "RISK_REPRODUCES"
    if replay_misleading_rate >= original_misleading_rate - 0.15:
        return "RISK_WEAKENS"
    return "RISK_FAILS_TO_REPRODUCE"


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    sheet_names = {
        "validation_queue": "Character_Learning_Validation_Queue",
        "validation_summary": "Character_Learning_Validation_Summary",
        "candidates": "Character_Learning_Hypothesis_Candidates",
        "understanding": "Character_Understanding_Pattern_Map",
        "accuracy": "Signal_Synchrony_Accuracy_Audit",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in sheet_names.items()}


def _build_hypothesis_metrics(
    hypothesis: Dict[str, Any],
    accuracy_rows: Sequence[Dict[str, Any]],
    global_baseline_rate: Optional[float],
    generated_ts: str,
) -> Dict[str, Any]:
    matched_rows = [row for row in accuracy_rows if _matches_hypothesis(row, hypothesis)]
    comparable_rows = [row for row in matched_rows if _is_comparable(row)]
    correct_count = sum(1 for row in comparable_rows if _is_correct(row))
    wrong_count = len(comparable_rows) - correct_count
    replay_rate = _safe_rate(correct_count, len(comparable_rows))
    replay_sample_groups = len(matched_rows)
    replay_non_comparable_rows = replay_sample_groups - len(comparable_rows)
    replay_thin_sample_flag = "TRUE" if len(comparable_rows) < 8 else "FALSE"
    replay_confidence_label = _confidence_label(len(comparable_rows))

    provider_family_rows = [
        row
        for row in accuracy_rows
        if _norm(row.get("provider")) == hypothesis["provider"]
        and _norm(row.get("event_family")) == hypothesis["event_family"]
        and _is_comparable(row)
    ]
    provider_family_baseline_rate = _baseline_rate(provider_family_rows)
    provider_family_delta = (
        _round4(replay_rate - provider_family_baseline_rate)
        if replay_rate is not None and provider_family_baseline_rate is not None
        else ""
    )
    global_delta = _round4(replay_rate - global_baseline_rate) if replay_rate is not None and global_baseline_rate is not None else ""
    original_correct_rate = _as_float(hypothesis.get("original_correct_rate"))
    original_delta_vs_provider_family_baseline = _as_float(hypothesis.get("original_delta_vs_provider_family_baseline"))
    original_misleading_rate = _as_float(hypothesis.get("original_misleading_stability_rate"))
    delta_vs_original = _round4(replay_rate - original_correct_rate) if replay_rate is not None and original_correct_rate is not None else ""

    ordered_rows = _sorted_rows_by_release(comparable_rows)
    discovery_rows, replay_window_rows = _time_split(ordered_rows)
    discovery_correct_rate = _rate(discovery_rows)
    replay_window_correct_rate = _rate(replay_window_rows)
    replay_window_delta = (
        _round4(replay_window_correct_rate - discovery_correct_rate)
        if discovery_correct_rate is not None and replay_window_correct_rate is not None
        else ""
    )
    time_delta = (
        replay_window_correct_rate - discovery_correct_rate
        if discovery_correct_rate is not None and replay_window_correct_rate is not None
        else None
    )

    cohort_mix_string, cohort_counter = _cohort_mix(comparable_rows)
    cohort_rates: Dict[str, float] = {}
    cohort_counts: Dict[str, int] = {}
    for cohort_bucket_value in COHORT_ORDER:
        cohort_rows = [row for row in comparable_rows if _cohort_bucket(row.get("cohort_id")) == cohort_bucket_value]
        if cohort_rows:
            cohort_rates[cohort_bucket_value] = _rate(cohort_rows) or 0.0
            cohort_counts[cohort_bucket_value] = len(cohort_rows)
    cohort_bucket_count = len(cohort_rates)
    cohort_spread = (max(cohort_rates.values()) - min(cohort_rates.values())) if len(cohort_rates) >= 2 else 0.0
    dominant_cohort_bucket = ""
    dominant_cohort_rate = None
    dominant_cohort_share = None
    if cohort_counter:
        dominant_cohort_bucket, dominant_bucket_count = cohort_counter.most_common(1)[0]
        dominant_cohort_share = dominant_bucket_count / len(comparable_rows) if comparable_rows else None
        dominant_cohort_rate = cohort_rates.get(dominant_cohort_bucket, replay_rate)
    else:
        dominant_bucket_count = 0
    if dominant_cohort_bucket and dominant_cohort_share is not None and dominant_cohort_share >= 0.6:
        cohort_bucket_value = dominant_cohort_bucket
        cohort_correct_rate = dominant_cohort_rate
    else:
        cohort_bucket_value = "mixed" if cohort_bucket_count > 1 else (dominant_cohort_bucket or "unknown")
        cohort_correct_rate = replay_rate
    cohort_delta = (
        _round4(cohort_correct_rate - original_correct_rate)
        if cohort_correct_rate is not None and original_correct_rate is not None
        else ""
    )

    replay_misleading_rows = [
        row
        for row in comparable_rows
        if _upper(row.get("direction_synchrony_bucket")) in {"HIGH", "VERY_HIGH"} and not _is_correct(row)
    ]
    replay_misleading_rate = _safe_rate(len(replay_misleading_rows), len(comparable_rows))
    misleading_result = _misleading_replay_result(
        hypothesis["candidate_label"],
        replay_misleading_rate,
        original_misleading_rate,
    )

    time_result = _time_result_label(discovery_correct_rate, replay_window_correct_rate)
    cohort_result = _cohort_result_label(cohort_spread, dominant_cohort_share, dominant_bucket_count, cohort_bucket_count)
    provider_family_result = _provider_family_result_label(replay_rate, provider_family_baseline_rate, global_baseline_rate)

    overall_result = _overall_result_label(
        hypothesis["candidate_label"],
        replay_rate if hypothesis["candidate_label"] != "LEARNING_CANDIDATE_MISLEADING_STABILITY" else replay_misleading_rate,
        original_correct_rate if hypothesis["candidate_label"] != "LEARNING_CANDIDATE_MISLEADING_STABILITY" else original_misleading_rate,
        provider_family_baseline_rate,
        global_baseline_rate,
        time_delta,
        cohort_spread,
        dominant_cohort_share,
    )

    if hypothesis["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        replay_interpretation_note = (
            f"Risk replay rate={_round4(replay_misleading_rate)} across {len(comparable_rows)} comparable rows; "
            f"cohort_mix={cohort_mix_string or 'none'}; time_delta={_round4(time_delta)}; "
            f"overall_label={overall_result}"
        )
    else:
        replay_interpretation_note = (
            f"Replay rate={_round4(replay_rate)} across {len(comparable_rows)} comparable rows; "
            f"cohort_mix={cohort_mix_string or 'none'}; time_delta={_round4(time_delta)}; "
            f"overall_label={overall_result}"
        )

    return {
        "generated_ts": generated_ts,
        "hypothesis_id": hypothesis["hypothesis_id"],
        "candidate_id": hypothesis["candidate_id"],
        "queue_id": hypothesis["queue_id"],
        "provider": hypothesis["provider"],
        "event_family": hypothesis["event_family"],
        "condition_dimension": hypothesis["condition_dimension"],
        "condition_value": hypothesis["condition_value"],
        "source_slice_type": hypothesis["source_slice_type"],
        "source_slice_key": hypothesis["source_slice_key"],
        "candidate_label": hypothesis["candidate_label"],
        "validation_queue_label": hypothesis["validation_queue_label"],
        "validation_score": hypothesis["validation_score"],
        "original_correct_rate": original_correct_rate,
        "original_delta_vs_provider_family_baseline": original_delta_vs_provider_family_baseline,
        "original_misleading_stability_rate": original_misleading_rate,
        "replay_sample_groups": replay_sample_groups,
        "replay_comparable_rows": len(comparable_rows),
        "replay_correct_count": correct_count,
        "replay_wrong_count": wrong_count,
        "replay_non_comparable_rows": replay_non_comparable_rows,
        "replay_thin_sample_flag": replay_thin_sample_flag,
        "replay_confidence_label": replay_confidence_label,
        "replay_correct_rate": replay_rate,
        "provider_family_baseline_rate": provider_family_baseline_rate,
        "global_baseline_rate": global_baseline_rate,
        "delta_vs_original_correct_rate": delta_vs_original,
        "delta_vs_provider_family_baseline": provider_family_delta,
        "delta_vs_global_baseline": global_delta,
        "discovery_comparable_rows": len(discovery_rows),
        "discovery_correct_rate": discovery_correct_rate,
        "replay_window_comparable_rows": len(replay_window_rows),
        "replay_window_correct_rate": replay_window_correct_rate,
        "replay_window_delta": replay_window_delta,
        "cohort_bucket": cohort_bucket_value,
        "cohort_correct_rate": cohort_correct_rate,
        "cohort_delta": cohort_delta,
        "cohort_counter": cohort_counter,
        "cohort_rates": cohort_rates,
        "cohort_spread": cohort_spread,
        "dominant_cohort_share": dominant_cohort_share,
        "replay_misleading_stability_count": len(replay_misleading_rows) if hypothesis["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY" else "",
        "replay_misleading_stability_rate": replay_misleading_rate if hypothesis["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY" else "",
        "misleading_stability_replay_result": misleading_result,
        "hypothesis_reconstruction_status": "OK",
        "time_replay_result_label": time_result,
        "cohort_replay_result_label": cohort_result,
        "provider_family_replay_result_label": provider_family_result,
        "replay_result_label": overall_result,
        "replay_interpretation_note": replay_interpretation_note,
        "replay_mode": "",
        "notes": (
            f"match_rows={replay_sample_groups}; comparable_rows={len(comparable_rows)}; "
            f"cohort_mix={cohort_mix_string or 'none'}; replay_mode=multi-test"
        ),
    }


def _build_validation_rows(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    base = {
        "generated_ts": metrics["generated_ts"],
        "hypothesis_id": metrics["hypothesis_id"],
        "candidate_id": metrics["candidate_id"],
        "queue_id": metrics["queue_id"],
        "provider": metrics["provider"],
        "event_family": metrics["event_family"],
        "condition_dimension": metrics["condition_dimension"],
        "condition_value": metrics["condition_value"],
        "source_slice_type": metrics["source_slice_type"],
        "source_slice_key": metrics["source_slice_key"],
        "candidate_label": metrics["candidate_label"],
        "validation_queue_label": metrics["validation_queue_label"],
        "validation_score": metrics["validation_score"],
        "original_correct_rate": metrics["original_correct_rate"],
        "original_delta_vs_provider_family_baseline": metrics["original_delta_vs_provider_family_baseline"],
        "original_misleading_stability_rate": metrics["original_misleading_stability_rate"],
        "replay_sample_groups": metrics["replay_sample_groups"],
        "replay_comparable_rows": metrics["replay_comparable_rows"],
        "replay_correct_count": metrics["replay_correct_count"],
        "replay_wrong_count": metrics["replay_wrong_count"],
        "replay_non_comparable_rows": metrics["replay_non_comparable_rows"],
        "replay_thin_sample_flag": metrics["replay_thin_sample_flag"],
        "replay_confidence_label": metrics["replay_confidence_label"],
        "replay_correct_rate": metrics["replay_correct_rate"],
        "provider_family_baseline_rate": metrics["provider_family_baseline_rate"],
        "global_baseline_rate": metrics["global_baseline_rate"],
        "delta_vs_original_correct_rate": metrics["delta_vs_original_correct_rate"],
        "delta_vs_provider_family_baseline": metrics["delta_vs_provider_family_baseline"],
        "delta_vs_global_baseline": metrics["delta_vs_global_baseline"],
        "discovery_comparable_rows": metrics["discovery_comparable_rows"],
        "discovery_correct_rate": metrics["discovery_correct_rate"],
        "replay_window_comparable_rows": metrics["replay_window_comparable_rows"],
        "replay_window_correct_rate": metrics["replay_window_correct_rate"],
        "replay_window_delta": metrics["replay_window_delta"],
        "cohort_bucket": metrics["cohort_bucket"],
        "cohort_correct_rate": metrics["cohort_correct_rate"],
        "cohort_delta": metrics["cohort_delta"],
        "replay_misleading_stability_count": metrics["replay_misleading_stability_count"],
        "replay_misleading_stability_rate": metrics["replay_misleading_stability_rate"],
        "misleading_stability_replay_result": metrics["misleading_stability_replay_result"],
        "hypothesis_reconstruction_status": metrics["hypothesis_reconstruction_status"],
        "replay_result_label": metrics["replay_result_label"],
        "replay_interpretation_note": metrics["replay_interpretation_note"],
        "learning_model_approved": "FALSE",
        "routing_approved": "FALSE",
        "weighting_approved": "FALSE",
        "calibration_approved": "FALSE",
        "production_approved": "FALSE",
    }

    for replay_test_id, replay_test_name, replay_mode in REPLAY_TESTS:
        row = dict(base)
        row["replay_id"] = f"{metrics['candidate_id']}__{replay_test_id}"
        row["replay_test_id"] = replay_test_id
        row["replay_test_name"] = replay_test_name
        row["replay_mode"] = replay_mode
        row["time_replay_result_label"] = ""
        row["cohort_replay_result_label"] = ""
        row["provider_family_replay_result_label"] = ""
        row["notes"] = metrics["notes"]
        if replay_test_id == "time_walk_forward_replay":
            row["time_replay_result_label"] = metrics["time_replay_result_label"]
            row["notes"] = f"{metrics['notes']}; time_result={metrics['time_replay_result_label']}"
        elif replay_test_id == "cohort_replay":
            row["cohort_replay_result_label"] = metrics["cohort_replay_result_label"]
            row["notes"] = f"{metrics['notes']}; cohort_result={metrics['cohort_replay_result_label']}"
        elif replay_test_id == "provider_family_baseline_replay":
            row["provider_family_replay_result_label"] = metrics["provider_family_replay_result_label"]
            row["notes"] = f"{metrics['notes']}; provider_family_result={metrics['provider_family_replay_result_label']}"
        elif replay_test_id == "misleading_stability_replay":
            row["misleading_stability_replay_result"] = metrics["misleading_stability_replay_result"]
            row["notes"] = f"{metrics['notes']}; misleading_result={metrics['misleading_stability_replay_result']}"
        else:
            row["provider_family_replay_result_label"] = metrics["provider_family_replay_result_label"]
        rows.append(row)
    return rows


def _best_hypothesis_key(item: Dict[str, Any]) -> Tuple[int, float, float, str]:
    label_rank = {
        "GENERALIZES": 5,
        "PARTIALLY_GENERALIZES": 4,
        "WINDOW_DEPENDENT": 3,
        "COHORT_DEPENDENT": 2,
        "FAILED_REPLAY": 1,
        "INSUFFICIENT_REPLAY_DATA": 0,
    }.get(item.get("replay_result_label"), 0)
    return (
        label_rank,
        _as_float(item.get("replay_correct_rate")) or 0.0,
        _as_float(item.get("replay_misleading_stability_rate")) or 0.0,
        _norm(item.get("candidate_id")),
    )


def _build_summary_rows(
    hypothesis_metrics: Sequence[Dict[str, Any]],
    generated_ts: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    validated_count = len(hypothesis_metrics)
    reconstructed_count = sum(1 for item in hypothesis_metrics if item.get("hypothesis_reconstruction_status") == "OK")
    failed_reconstruction = validated_count - reconstructed_count
    total_replay_rows = len(hypothesis_metrics) * len(REPLAY_TESTS)
    replay_label_counts = Counter(item.get("replay_result_label", "") for item in hypothesis_metrics)
    replay_mode_counts = Counter()
    for _item in hypothesis_metrics:
        for _, _, replay_mode in REPLAY_TESTS:
            replay_mode_counts[replay_mode] += 1
    providers = Counter(item["provider"] for item in hypothesis_metrics)
    families = Counter(item["event_family"] for item in hypothesis_metrics)
    cohorts = Counter()
    for item in hypothesis_metrics:
        for bucket, count in item.get("cohort_counter", Counter()).items():
            cohorts[bucket] += count

    def detail_rows_for(section: str, items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for rank, item in enumerate(items, start=1):
            row = {
                "generated_ts": generated_ts,
                "section": section,
                "rank": rank,
                "hypothesis_id": item["hypothesis_id"],
                "candidate_id": item["candidate_id"],
                "queue_id": item["queue_id"],
                "provider": item["provider"],
                "event_family": item["event_family"],
                "condition_dimension": item["condition_dimension"],
                "condition_value": item["condition_value"],
                "source_slice_type": item["source_slice_type"],
                "source_slice_key": item["source_slice_key"],
                "candidate_label": item["candidate_label"],
                "validation_queue_label": item["validation_queue_label"],
                "validation_score": item["validation_score"],
                "original_correct_rate": item["original_correct_rate"],
                "original_delta_vs_provider_family_baseline": item["original_delta_vs_provider_family_baseline"],
                "original_misleading_stability_rate": item["original_misleading_stability_rate"],
                "replay_result_label": item["replay_result_label"],
                "replay_confidence_label": item["replay_confidence_label"],
                "replay_correct_rate": item["replay_correct_rate"],
                "delta_vs_original_correct_rate": item["delta_vs_original_correct_rate"],
                "delta_vs_provider_family_baseline": item["delta_vs_provider_family_baseline"],
                "delta_vs_global_baseline": item["delta_vs_global_baseline"],
                "replay_misleading_stability_rate": item["replay_misleading_stability_rate"],
                "misleading_stability_replay_result": item["misleading_stability_replay_result"],
                "replay_interpretation_note": item["replay_interpretation_note"],
                "notes": item["notes"],
            }
            out.append(row)
        return out

    generalizing_items = [item for item in hypothesis_metrics if item["replay_result_label"] in {"GENERALIZES", "PARTIALLY_GENERALIZES"}]
    dependent_items = [item for item in hypothesis_metrics if item["replay_result_label"] in {"WINDOW_DEPENDENT", "COHORT_DEPENDENT", "FAILED_REPLAY", "INSUFFICIENT_REPLAY_DATA"}]
    risk_items = [item for item in hypothesis_metrics if item["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY"]
    risk_reproduces = sum(1 for item in risk_items if item["misleading_stability_replay_result"] == "RISK_REPRODUCES")
    risk_weakens = sum(1 for item in risk_items if item["misleading_stability_replay_result"] == "RISK_WEAKENS")
    risk_fails = sum(1 for item in risk_items if item["misleading_stability_replay_result"] == "RISK_FAILS_TO_REPRODUCE")
    insufficient_risk = sum(1 for item in risk_items if item["misleading_stability_replay_result"] == "INSUFFICIENT_RISK_DATA")

    strongest = max(hypothesis_metrics, key=_best_hypothesis_key) if hypothesis_metrics else None

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "A_OVERALL_REPLAY_SUMMARY",
            "rank": 0,
            "validate_first_hypotheses_read": validated_count,
            "hypotheses_reconstructed": reconstructed_count,
            "hypotheses_failed_reconstruction": failed_reconstruction,
            "total_replay_rows": total_replay_rows,
            "replay_result_label_counts": _count_string(replay_label_counts, FINAL_LABEL_ORDER),
            "replay_mode_counts": _count_string(replay_mode_counts, ["ROBUSTNESS_REPLAY", "PSEUDO_WALK_FORWARD", "COHORT_REPLAY"]),
            "providers_represented": _count_string(providers, PROVIDER_ORDER),
            "families_represented": _count_string(families, FAMILY_ORDER),
            "cohorts_represented": _count_string(cohorts, COHORT_ORDER),
            "misleading_stability_total": len(risk_items),
            "risk_reproduces_count": risk_reproduces,
            "risk_weakens_count": risk_weakens,
            "risk_fails_count": risk_fails,
            "insufficient_risk_data_count": insufficient_risk,
            "strongest_replayed_hypothesis": strongest["candidate_id"] if strongest else "",
            "strongest_replayed_label": strongest["replay_result_label"] if strongest else "",
            "learning_readiness_label": "",
            "learning_readiness_reason": "",
            "final_interpretation_label": "",
            "final_interpretation_reason": "",
            "notes": "Replay validation uses the queued VALIDATE_FIRST hypotheses against the historical accuracy audit only.",
        }
    )

    rows.extend(
        detail_rows_for(
            "B_GENERALIZING_HYPOTHESES",
            sorted(
                generalizing_items,
                key=lambda item: (
                    0 if item["replay_result_label"] == "GENERALIZES" else 1,
                    -(item.get("validation_score") or 0),
                    -(item.get("replay_correct_rate") or 0),
                    item["candidate_id"],
                ),
            ),
        )
    )
    rows.extend(
        detail_rows_for(
            "C_FAILED_OR_DEPENDENT_HYPOTHESES",
            sorted(
                dependent_items,
                key=lambda item: (
                    FINAL_LABEL_ORDER.index(item["replay_result_label"]) if item["replay_result_label"] in FINAL_LABEL_ORDER else 99,
                    -(item.get("validation_score") or 0),
                    item["candidate_id"],
                ),
            ),
        )
    )

    strongest_risk = None
    if risk_items:
        strongest_risk = max(
            risk_items,
            key=lambda item: (
                _as_float(item.get("replay_misleading_stability_rate")) or 0.0,
                _as_float(item.get("original_misleading_stability_rate")) or 0.0,
                _as_float(item.get("validation_score")) or 0.0,
                item["candidate_id"],
            ),
        )
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "D_MISLEADING_STABILITY_SUMMARY",
            "rank": 0,
            "misleading_stability_total": len(risk_items),
            "risk_reproduces_count": risk_reproduces,
            "risk_weakens_count": risk_weakens,
            "risk_fails_count": risk_fails,
            "insufficient_risk_data_count": insufficient_risk,
            "strongest_replayed_hypothesis": strongest_risk["candidate_id"] if strongest_risk else "",
            "strongest_replayed_label": strongest_risk["misleading_stability_replay_result"] if strongest_risk else "",
            "notes": "Misleading stability risk is evaluated on the comparable matched rows for each hypothesis.",
        }
    )
    rows.extend(
        detail_rows_for(
            "D_MISLEADING_STABILITY_DETAIL",
            sorted(
                risk_items,
                key=lambda item: (
                    -(item.get("replay_misleading_stability_rate") or 0),
                    -(item.get("original_misleading_stability_rate") or 0),
                    -(item.get("validation_score") or 0),
                    item["candidate_id"],
                ),
            ),
        )
    )

    provider_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    family_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in hypothesis_metrics:
        provider_groups[item["provider"]].append(item)
        family_groups[item["event_family"]].append(item)

    provider_rows: List[Dict[str, Any]] = []
    for provider in PROVIDER_ORDER:
        items = provider_groups.get(provider, [])
        if not items:
            continue
        strongest_item = max(items, key=_best_hypothesis_key)
        row = {
            "generated_ts": generated_ts,
            "section": "E_PROVIDER_REPLAY_SUMMARY",
            "rank": len(provider_rows) + 1,
            "provider": provider,
            "validate_first_hypotheses_read": len(items),
            "hypotheses_reconstructed": sum(1 for item in items if item["hypothesis_reconstruction_status"] == "OK"),
            "hypotheses_failed_reconstruction": sum(1 for item in items if item["hypothesis_reconstruction_status"] != "OK"),
            "replay_result_label_counts": _count_string(Counter(item["replay_result_label"] for item in items), FINAL_LABEL_ORDER),
            "strongest_replayed_hypothesis": strongest_item["candidate_id"],
            "strongest_replayed_label": strongest_item["replay_result_label"],
            "learning_readiness_label": "",
            "learning_readiness_reason": "",
            "final_interpretation_label": "",
            "final_interpretation_reason": "",
            "notes": "",
        }
        provider_rows.append(row)
    rows.extend(provider_rows)

    family_rows: List[Dict[str, Any]] = []
    for family in FAMILY_ORDER:
        items = family_groups.get(family, [])
        if not items:
            continue
        strongest_item = max(items, key=_best_hypothesis_key)
        row = {
            "generated_ts": generated_ts,
            "section": "F_FAMILY_REPLAY_SUMMARY",
            "rank": len(family_rows) + 1,
            "event_family": family,
            "validate_first_hypotheses_read": len(items),
            "hypotheses_reconstructed": sum(1 for item in items if item["hypothesis_reconstruction_status"] == "OK"),
            "hypotheses_failed_reconstruction": sum(1 for item in items if item["hypothesis_reconstruction_status"] != "OK"),
            "replay_result_label_counts": _count_string(Counter(item["replay_result_label"] for item in items), FINAL_LABEL_ORDER),
            "strongest_replayed_hypothesis": strongest_item["candidate_id"],
            "strongest_replayed_label": strongest_item["replay_result_label"],
            "learning_readiness_label": "",
            "learning_readiness_reason": "",
            "final_interpretation_label": "",
            "final_interpretation_reason": "",
            "notes": "",
        }
        family_rows.append(row)
    rows.extend(family_rows)

    generalize_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "GENERALIZES")
    partial_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "PARTIALLY_GENERALIZES")
    window_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "WINDOW_DEPENDENT")
    cohort_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "COHORT_DEPENDENT")
    failed_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "FAILED_REPLAY")
    insufficient_count = sum(1 for item in hypothesis_metrics if item["replay_result_label"] == "INSUFFICIENT_REPLAY_DATA")

    if validated_count == 0:
        learning_readiness_label = "INSUFFICIENT_REPLAY_DATA"
        learning_readiness_reason = "No VALIDATE_FIRST hypotheses were available for replay."
        final_interpretation = "INSUFFICIENT_REPLAY_DATA"
        final_reason = "No hypotheses were available to replay."
    elif window_count + cohort_count + failed_count >= generalize_count + partial_count:
        learning_readiness_label = "REPLAY_WEAK_OR_DEPENDENT"
        learning_readiness_reason = "Window and cohort dependence dominate the replay outcomes."
        final_interpretation = "HYPOTHESES_WINDOW_DEPENDENT"
        final_reason = "Most replay results depend on window or cohort structure."
    elif generalize_count >= 4 and (window_count + cohort_count + failed_count) < 6:
        learning_readiness_label = "READY_FOR_LEARNING_LAYER_V1_SHADOW"
        learning_readiness_reason = "Multiple hypotheses generalized with limited dependence."
        final_interpretation = "HYPOTHESES_GENERALIZE"
        final_reason = "A broad enough share of hypotheses generalized cleanly."
    elif generalize_count + partial_count >= 4:
        learning_readiness_label = "LIMITED_REPLAY_SUPPORT_ONLY"
        learning_readiness_reason = "A narrow set of hypotheses survived replay, but dependence remains."
        final_interpretation = "LIMITED_HYPOTHESES_GENERALIZE"
        final_reason = "Some hypotheses generalized, but the set remains narrow."
    else:
        learning_readiness_label = "REPLAY_WEAK_OR_DEPENDENT"
        learning_readiness_reason = "Replay support exists, but it is too narrow to treat as stable."
        final_interpretation = "HYPOTHESES_WINDOW_DEPENDENT"
        final_reason = "The replay set is mixed and dominated by dependence."

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "G_LEARNING_READINESS_SUMMARY",
            "rank": 0,
            "validate_first_hypotheses_read": validated_count,
            "hypotheses_reconstructed": reconstructed_count,
            "hypotheses_failed_reconstruction": failed_reconstruction,
            "total_replay_rows": total_replay_rows,
            "replay_result_label_counts": _count_string(replay_label_counts, FINAL_LABEL_ORDER),
            "replay_mode_counts": _count_string(replay_mode_counts, ["ROBUSTNESS_REPLAY", "PSEUDO_WALK_FORWARD", "COHORT_REPLAY"]),
            "learning_readiness_label": learning_readiness_label,
            "learning_readiness_reason": learning_readiness_reason,
            "final_interpretation_label": final_interpretation,
            "final_interpretation_reason": final_reason,
            "notes": "Learning remains conservative and replay validation is descriptive only.",
        }
    )
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "H_FINAL_INTERPRETATION",
            "rank": 0,
            "validate_first_hypotheses_read": validated_count,
            "hypotheses_reconstructed": reconstructed_count,
            "hypotheses_failed_reconstruction": failed_reconstruction,
            "total_replay_rows": total_replay_rows,
            "replay_result_label_counts": _count_string(replay_label_counts, FINAL_LABEL_ORDER),
            "replay_mode_counts": _count_string(replay_mode_counts, ["ROBUSTNESS_REPLAY", "PSEUDO_WALK_FORWARD", "COHORT_REPLAY"]),
            "learning_readiness_label": learning_readiness_label,
            "learning_readiness_reason": learning_readiness_reason,
            "final_interpretation_label": final_interpretation,
            "final_interpretation_reason": final_reason,
            "notes": "This replay validation remains a historical diagnostic only.",
        }
    )
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
            updates.append(
                {
                    "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(existing_headers))}{row_number}",
                    "values": [values],
                }
            )
        else:
            appended += 1
            target_row = len(rows) + appended
            updates.append(
                {
                    "range": f"'{REGISTRY_SHEET}'!A{target_row}:{_column_letter(len(existing_headers))}{target_row}",
                    "values": [values],
                }
            )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(REGISTRY_ROWS) - appended, "appended": appended}


def build_character_learning_replay_validation() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    queue_rows = [row for row in sources["validation_queue"] if _upper(row.get("validation_queue_label")) == "VALIDATE_FIRST"]
    if not queue_rows:
        raise RuntimeError("No VALIDATE_FIRST hypotheses were found in Character_Learning_Validation_Queue.")

    global_baseline_rate = _baseline_rate(sources["accuracy"])
    hypothesis_metrics: List[Dict[str, Any]] = []
    validation_rows: List[Dict[str, Any]] = []

    candidate_lookup = { _norm(row.get("candidate_id")): row for row in sources["candidates"] }
    for queue_row in queue_rows:
        candidate = candidate_lookup.get(_norm(queue_row.get("candidate_id")), {})
        hypothesis = {
            "hypothesis_id": _norm(queue_row.get("candidate_id")),
            "candidate_id": _norm(queue_row.get("candidate_id")),
            "queue_id": _norm(queue_row.get("queue_id")),
            "provider": _norm(queue_row.get("provider")),
            "event_family": _norm(queue_row.get("event_family")),
            "condition_dimension": _norm(queue_row.get("condition_dimension")),
            "condition_value": _norm(queue_row.get("condition_value")),
            "source_slice_type": _norm(queue_row.get("source_slice_type")),
            "source_slice_key": _norm(queue_row.get("source_slice_key")),
            "candidate_label": _norm(queue_row.get("candidate_label")),
            "validation_queue_label": _norm(queue_row.get("validation_queue_label")),
            "validation_score": _as_float(queue_row.get("validation_score")),
            "original_correct_rate": _as_float(queue_row.get("correct_rate")),
            "original_delta_vs_provider_family_baseline": _as_float(queue_row.get("delta_vs_provider_family_baseline")),
            "original_misleading_stability_rate": _as_float(queue_row.get("misleading_stability_rate")),
        }
        metrics = _build_hypothesis_metrics(hypothesis, sources["accuracy"], global_baseline_rate, generated_ts)
        metrics["source_character_understanding_label"] = _norm(candidate.get("source_character_understanding_label"))
        hypothesis_metrics.append(metrics)
        validation_rows.extend(_build_validation_rows(metrics))

    summary_rows = _build_summary_rows(hypothesis_metrics, generated_ts)

    validation_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_SHEET, VALIDATION_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_VALIDATION_SHEET, validation_headers, validation_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)

    final_row = next((row for row in summary_rows if row.get("section") == "H_FINAL_INTERPRETATION"), {})
    return {
        "generated_ts": generated_ts,
        "validate_first_hypotheses_read": len(queue_rows),
        "hypotheses_reconstructed": len(hypothesis_metrics),
        "hypotheses_failed_reconstruction": 0,
        "validation_rows_written": len(validation_rows),
        "summary_rows_written": len(summary_rows),
        "replay_result_label_counts": final_row.get("replay_result_label_counts", ""),
        "replay_mode_counts": final_row.get("replay_mode_counts", ""),
        "learning_readiness_label": final_row.get("learning_readiness_label", ""),
        "final_interpretation_label": final_row.get("final_interpretation_label", ""),
        "registry_result": registry_result,
    }


def main() -> None:
    print(build_character_learning_replay_validation())


if __name__ == "__main__":
    main()
