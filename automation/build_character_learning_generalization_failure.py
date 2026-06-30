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


OUTPUT_FAILURE_SHEET = "Character_Learning_Generalization_Failure"
OUTPUT_SUMMARY_SHEET = "Character_Learning_Generalization_Failure_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "CHARACTER_LEARNING_GENERALIZATION_FAILURE",
        "physical_sheet_name": OUTPUT_FAILURE_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v1A",
        "notes": "Derived-only character learning generalization failure audit",
    },
    {
        "logical_sheet_id": "CHARACTER_LEARNING_GENERALIZATION_FAILURE_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v1A",
        "notes": "Derived-only character learning generalization failure summary",
    },
]

FAILURE_HEADERS = [
    "generated_ts",
    "failure_audit_id",
    "hypothesis_id",
    "candidate_id",
    "queue_id",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "candidate_label",
    "validation_queue_label",
    "validation_score",
    "original_correct_rate",
    "original_delta_vs_provider_family_baseline",
    "original_misleading_stability_rate",
    "final_replay_result_label",
    "replay_consolidation_label",
    "replay_modes_used",
    "replay_result_label_mix",
    "replay_confidence_label_mix",
    "replay_rows_count",
    "total_replay_sample_groups",
    "total_replay_comparable_rows",
    "total_replay_correct_count",
    "total_replay_wrong_count",
    "replay_correct_rate",
    "replay_confidence_label",
    "discovery_comparable_rows",
    "discovery_correct_rate",
    "replay_window_comparable_rows",
    "replay_window_correct_rate",
    "replay_window_delta",
    "time_window_failure_label",
    "cohort_a_correct_rate",
    "deterministic_correct_rate",
    "random_correct_rate",
    "best_cohort",
    "worst_cohort",
    "cohort_spread",
    "cohort_shift_label",
    "min_replay_comparable_rows",
    "thin_replay_rows_count",
    "sample_fragility_label",
    "provider_family_scope_label",
    "synchrony_drift_label",
    "misleading_stability_persistence_label",
    "dominant_failure_attribution",
    "secondary_failure_attribution",
    "failure_confidence_label",
    "interpretation_note",
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
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "candidate_label",
    "validation_queue_label",
    "validation_score",
    "original_correct_rate",
    "original_delta_vs_provider_family_baseline",
    "original_misleading_stability_rate",
    "final_replay_result_label",
    "replay_consolidation_label",
    "replay_modes_used",
    "replay_result_label_mix",
    "replay_confidence_label_mix",
    "replay_rows_count",
    "total_replay_sample_groups",
    "total_replay_comparable_rows",
    "total_replay_correct_count",
    "total_replay_wrong_count",
    "replay_correct_rate",
    "replay_confidence_label",
    "discovery_comparable_rows",
    "discovery_correct_rate",
    "replay_window_comparable_rows",
    "replay_window_correct_rate",
    "replay_window_delta",
    "time_window_failure_label",
    "cohort_a_correct_rate",
    "deterministic_correct_rate",
    "random_correct_rate",
    "best_cohort",
    "worst_cohort",
    "cohort_spread",
    "cohort_shift_label",
    "min_replay_comparable_rows",
    "thin_replay_rows_count",
    "sample_fragility_label",
    "provider_family_scope_label",
    "synchrony_drift_label",
    "misleading_stability_persistence_label",
    "dominant_failure_attribution",
    "secondary_failure_attribution",
    "failure_confidence_label",
    "interpretation_note",
    "hypothesis_count",
    "percent_of_hypotheses",
    "representative_hypothesis",
    "average_replay_window_delta",
    "time_window_stable_count",
    "time_window_weakens_count",
    "time_window_reversal_count",
    "time_window_insufficient_count",
    "low_cohort_shift_count",
    "moderate_cohort_shift_count",
    "high_cohort_shift_count",
    "cohort_insufficient_count",
    "most_cohort_dependent_hypothesis",
    "low_sample_fragility_count",
    "moderate_sample_fragility_count",
    "high_sample_fragility_count",
    "insufficient_sample_count",
    "misleading_stability_candidates_analyzed",
    "misleading_stability_persists_count",
    "misleading_stability_weakens_count",
    "misleading_stability_fails_count",
    "strongest_persistent_misleading_stability_hypothesis",
    "average_replay_misleading_stability_rate",
    "replay_result_label_counts",
    "dominant_failure_attribution_counts",
    "replay_consolidation_label_counts",
    "failure_confidence_label_counts",
    "learning_implication_label",
    "learning_implication_reason",
    "final_interpretation_label",
    "final_interpretation_reason",
    "notes",
]

PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]
FAMILY_ORDER = ["growth", "inflation", "housing", "labor", "energy", "central_bank", "manufacturing", "other"]
COHORT_ORDER = ["cohort_a", "deterministic", "random", "unknown"]
FAILURE_ATTRIBUTION_ORDER = [
    "MISLEADING_STABILITY_PERSISTS",
    "TIME_WINDOW_SHIFT",
    "COHORT_SHIFT",
    "SAMPLE_FRAGILITY",
    "PROVIDER_DEPENDENCE",
    "EVENT_FAMILY_SHIFT",
    "SYNCHRONY_DRIFT",
    "MULTI_FACTOR_FAILURE",
    "NO_FAILURE_GENERALIZES",
    "INSUFFICIENT_TRACEABILITY",
]
CONSOLIDATION_ORDER = [
    "MOSTLY_GENERALIZES",
    "PARTIAL_SUPPORT",
    "WINDOW_DEPENDENT",
    "COHORT_DEPENDENT",
    "MIXED_DEPENDENT",
    "INSUFFICIENT_REPLAY_DATA",
]
FINAL_REPLAY_ORDER = [
    "GENERALIZES",
    "PARTIALLY_GENERALIZES",
    "WINDOW_DEPENDENT",
    "COHORT_DEPENDENT",
    "FAILED_REPLAY",
    "INSUFFICIENT_REPLAY_DATA",
]
CONFIDENCE_ORDER = ["HIGHER_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE", "THIN_SAMPLE"]


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


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    sheet_names = {
        "replay_validation": "Character_Learning_Replay_Validation",
        "replay_summary": "Character_Learning_Replay_Summary",
        "validation_queue": "Character_Learning_Validation_Queue",
        "candidates": "Character_Learning_Hypothesis_Candidates",
        "understanding": "Character_Understanding_Pattern_Map",
        "accuracy": "Signal_Synchrony_Accuracy_Audit",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in sheet_names.items()}


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


def _group_replay_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_norm(row.get("hypothesis_id"))].append(row)
    return grouped


def _row_replay_test(rows: Sequence[Dict[str, Any]], replay_test_id: str) -> Dict[str, Any]:
    for row in rows:
        if _norm(row.get("replay_test_id")) == replay_test_id:
            return row
    return {}


def _cohort_rates_for_hypothesis(
    hypothesis: Dict[str, Any],
    accuracy_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, int], List[Dict[str, Any]]]:
    matched = [row for row in accuracy_rows if _matches_hypothesis(row, hypothesis)]
    comparable = [row for row in matched if _is_comparable(row)]
    by_cohort: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in comparable:
        by_cohort[_cohort_bucket(row.get("cohort_id"))].append(row)
    rates: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for cohort_key, cohort_rows in by_cohort.items():
        counts[cohort_key] = len(cohort_rows)
        rate = _safe_rate(sum(1 for row in cohort_rows if _is_correct(row)), len(cohort_rows))
        if rate is not None:
            rates[cohort_key] = rate
    return rates, counts, comparable


def _time_window_label(delta: Optional[float]) -> str:
    if delta is None:
        return "TIME_WINDOW_INSUFFICIENT"
    if abs(delta) <= 0.05:
        return "TIME_WINDOW_STABLE"
    if abs(delta) <= 0.15:
        return "TIME_WINDOW_WEAKENS"
    return "TIME_WINDOW_REVERSAL"


def _cohort_shift_label(rates: Dict[str, float], counts: Dict[str, int]) -> str:
    if len(rates) < 2:
        return "COHORT_INSUFFICIENT"
    spread = max(rates.values()) - min(rates.values())
    total = sum(counts.values())
    if total <= 0:
        return "COHORT_INSUFFICIENT"
    if spread < 0.10:
        return "LOW_COHORT_SHIFT"
    if spread < 0.25:
        return "MODERATE_COHORT_SHIFT"
    return "HIGH_COHORT_SHIFT"


def _sample_fragility_label(total_comparable_rows: int, min_replay_comparable_rows: int, thin_rows: int) -> str:
    if total_comparable_rows <= 0:
        return "INSUFFICIENT_SAMPLE"
    if total_comparable_rows < 8 or min_replay_comparable_rows < 5 or thin_rows >= 3:
        return "HIGH_SAMPLE_FRAGILITY"
    if total_comparable_rows < 12 or thin_rows >= 2:
        return "MODERATE_SAMPLE_FRAGILITY"
    if total_comparable_rows < 20 or thin_rows >= 1:
        return "LOW_SAMPLE_FRAGILITY"
    return "LOW_SAMPLE_FRAGILITY"


def _provider_family_scope_label(
    final_replay_result_label: str,
    source_slice_type: str,
    condition_dimension: str,
    total_comparable_rows: int,
) -> str:
    if total_comparable_rows <= 0:
        return "UNKNOWN_SCOPE"
    if final_replay_result_label == "GENERALIZES" and total_comparable_rows >= 12:
        return "BROAD_ENOUGH"
    if condition_dimension in {"direction_synchrony_bucket", "stability_label", "recommended_protocol", "cohort_bucket", "predictability_bucket"}:
        return "OVERLY_NARROW" if final_replay_result_label in {"WINDOW_DEPENDENT", "COHORT_DEPENDENT", "FAILED_REPLAY"} else "NARROW_BUT_INTERPRETABLE"
    if condition_dimension in {"event_family", "importance"}:
        return "BROAD_ENOUGH" if total_comparable_rows >= 12 else "NARROW_BUT_INTERPRETABLE"
    if "provider_event_family" in _lower(source_slice_type):
        return "NARROW_BUT_INTERPRETABLE" if final_replay_result_label in {"PARTIALLY_GENERALIZES", "GENERALIZES"} else "OVERLY_NARROW"
    return "UNKNOWN_SCOPE"


def _synchrony_drift_label(
    final_replay_result_label: str,
    replay_rate: Optional[float],
    original_rate: Optional[float],
    time_window_delta: Optional[float],
    cohort_shift_label: str,
    candidate_label: str,
) -> str:
    if replay_rate is None or original_rate is None:
        return "SYNCHRONY_DRIFT_UNKNOWN"
    delta = abs(replay_rate - original_rate)
    if final_replay_result_label == "GENERALIZES" and delta <= 0.05:
        return "LOW_SYNCHRONY_DRIFT"
    if final_replay_result_label == "PARTIALLY_GENERALIZES" and delta <= 0.10 and cohort_shift_label in {"LOW_COHORT_SHIFT", "MODERATE_COHORT_SHIFT"}:
        return "MODERATE_SYNCHRONY_DRIFT"
    if final_replay_result_label in {"WINDOW_DEPENDENT", "COHORT_DEPENDENT", "FAILED_REPLAY"} or delta > 0.10:
        return "HIGH_SYNCHRONY_DRIFT"
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY" and (time_window_delta is not None or cohort_shift_label != "COHORT_INSUFFICIENT"):
        return "MODERATE_SYNCHRONY_DRIFT"
    return "LOW_SYNCHRONY_DRIFT"


def _misleading_persistence_label(
    candidate_label: str,
    original_rate: Optional[float],
    replay_rate: Optional[float],
) -> str:
    if candidate_label != "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        return "NOT_MISLEADING_STABILITY_CANDIDATE"
    if original_rate is None or replay_rate is None:
        return "INSUFFICIENT_MISLEADING_STABILITY_DATA"
    if replay_rate >= original_rate - 0.05:
        return "MISLEADING_STABILITY_PERSISTS"
    if replay_rate >= original_rate - 0.15:
        return "MISLEADING_STABILITY_WEAKENS"
    return "MISLEADING_STABILITY_FAILS"


def _replay_consolidation_label(final_replay_result_label: str, label_mix: Counter) -> str:
    if not label_mix:
        return "INSUFFICIENT_REPLAY_DATA"
    if final_replay_result_label == "GENERALIZES":
        return "MOSTLY_GENERALIZES"
    if final_replay_result_label == "PARTIALLY_GENERALIZES":
        return "PARTIAL_SUPPORT"
    if final_replay_result_label == "WINDOW_DEPENDENT":
        return "WINDOW_DEPENDENT"
    if final_replay_result_label == "COHORT_DEPENDENT":
        return "COHORT_DEPENDENT"
    if final_replay_result_label == "INSUFFICIENT_REPLAY_DATA":
        return "INSUFFICIENT_REPLAY_DATA"
    if len(label_mix) > 1:
        return "MIXED_DEPENDENT"
    return "PARTIAL_SUPPORT"


def _dominant_failure_attribution(
    final_replay_result_label: str,
    candidate_label: str,
    misleading_persistence_label: str,
    time_window_label: str,
    cohort_shift_label: str,
    sample_fragility_label: str,
    synchrony_drift_label: str,
) -> str:
    if final_replay_result_label == "GENERALIZES":
        return "NO_FAILURE_GENERALIZES"
    if sample_fragility_label == "HIGH_SAMPLE_FRAGILITY":
        return "SAMPLE_FRAGILITY"
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY" and misleading_persistence_label == "MISLEADING_STABILITY_PERSISTS":
        return "MISLEADING_STABILITY_PERSISTS"
    if time_window_label in {"TIME_WINDOW_WEAKENS", "TIME_WINDOW_REVERSAL"}:
        return "TIME_WINDOW_SHIFT"
    if cohort_shift_label in {"MODERATE_COHORT_SHIFT", "HIGH_COHORT_SHIFT"}:
        return "COHORT_SHIFT"
    if synchrony_drift_label == "HIGH_SYNCHRONY_DRIFT":
        return "SYNCHRONY_DRIFT"
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        return "MISLEADING_STABILITY_PERSISTS"
    return "MULTI_FACTOR_FAILURE"


def _secondary_failure_attribution(
    dominant: str,
    time_window_label: str,
    cohort_shift_label: str,
    sample_fragility_label: str,
    synchrony_drift_label: str,
    candidate_label: str,
    misleading_persistence_label: str,
) -> str:
    candidates = []
    if time_window_label in {"TIME_WINDOW_WEAKENS", "TIME_WINDOW_REVERSAL"}:
        candidates.append("TIME_WINDOW_SHIFT")
    if cohort_shift_label in {"MODERATE_COHORT_SHIFT", "HIGH_COHORT_SHIFT"}:
        candidates.append("COHORT_SHIFT")
    if sample_fragility_label in {"MODERATE_SAMPLE_FRAGILITY", "HIGH_SAMPLE_FRAGILITY"}:
        candidates.append("SAMPLE_FRAGILITY")
    if synchrony_drift_label in {"MODERATE_SYNCHRONY_DRIFT", "HIGH_SYNCHRONY_DRIFT"}:
        candidates.append("SYNCHRONY_DRIFT")
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY" and misleading_persistence_label != "MISLEADING_STABILITY_PERSISTS":
        candidates.append(misleading_persistence_label)
    else:
        candidates.append("MISLEADING_STABILITY_PERSISTS")
    for cand in candidates:
        if cand != dominant:
            return cand
    return "MULTI_FACTOR_FAILURE"


def _failure_confidence_label(total_comparable_rows: int, dominant: str, sample_fragility_label: str) -> str:
    if total_comparable_rows >= 20 and sample_fragility_label == "LOW_SAMPLE_FRAGILITY" and dominant != "MULTI_FACTOR_FAILURE":
        return "HIGHER_CONFIDENCE"
    if total_comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if total_comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _build_hypothesis_row(
    generated_ts: str,
    hypothesis_id: str,
    replay_rows: Sequence[Dict[str, Any]],
    queue_lookup: Dict[str, Dict[str, Any]],
    candidate_lookup: Dict[str, Dict[str, Any]],
    accuracy_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    replay_rows = sorted(replay_rows, key=lambda row: (_norm(row.get("replay_test_id")), _norm(row.get("generated_ts"))))
    base = _row_replay_test(replay_rows, "overall_matching_replay") or replay_rows[0]
    time_row = _row_replay_test(replay_rows, "time_walk_forward_replay")
    cohort_row = _row_replay_test(replay_rows, "cohort_replay")
    provider_family_row = _row_replay_test(replay_rows, "provider_family_baseline_replay")
    misleading_row = _row_replay_test(replay_rows, "misleading_stability_replay")

    queue_row = queue_lookup.get(hypothesis_id, {})
    candidate = candidate_lookup.get(_norm(queue_row.get("candidate_id")), {})
    candidate_label = _norm(base.get("candidate_label")) or _norm(queue_row.get("candidate_label"))
    original_correct_rate = _as_float(base.get("original_correct_rate"))
    original_delta_vs_provider_family_baseline = _as_float(base.get("original_delta_vs_provider_family_baseline"))
    original_misleading_stability_rate = _as_float(base.get("original_misleading_stability_rate"))

    replay_result_label_mix = Counter(_norm(row.get("replay_result_label")) for row in replay_rows if _norm(row.get("replay_result_label")))
    replay_confidence_label_mix = Counter(_norm(row.get("replay_confidence_label")) for row in replay_rows if _norm(row.get("replay_confidence_label")))
    replay_mode_mix = Counter(_norm(row.get("replay_mode")) for row in replay_rows if _norm(row.get("replay_mode")))
    final_replay_result_label = _norm(base.get("replay_result_label")) or replay_result_label_mix.most_common(1)[0][0]
    replay_consolidation_label = _replay_consolidation_label(final_replay_result_label, replay_result_label_mix)

    total_replay_sample_groups = _as_float(base.get("replay_sample_groups"))
    total_replay_comparable_rows = _as_float(base.get("replay_comparable_rows"))
    total_replay_correct_count = _as_float(base.get("replay_correct_count"))
    total_replay_wrong_count = _as_float(base.get("replay_wrong_count"))
    replay_correct_rate = _as_float(base.get("replay_correct_rate"))
    replay_confidence_label = _norm(base.get("replay_confidence_label")) or _confidence_label(int(total_replay_comparable_rows or 0))

    discovery_rows = _as_float(time_row.get("discovery_comparable_rows"))
    discovery_rate = _as_float(time_row.get("discovery_correct_rate"))
    replay_window_rows = _as_float(time_row.get("replay_window_comparable_rows"))
    replay_window_rate = _as_float(time_row.get("replay_window_correct_rate"))
    replay_window_delta = _as_float(time_row.get("replay_window_delta"))
    time_window_failure_label = _time_window_label(replay_window_delta)

    cohort_rates, cohort_counts, comparable_rows = _cohort_rates_for_hypothesis(
        {
            "provider": _norm(base.get("provider")),
            "event_family": _norm(base.get("event_family")),
            "condition_dimension": _norm(base.get("condition_dimension")),
            "condition_value": _norm(base.get("condition_value")),
        },
        accuracy_rows,
    )
    cohort_a_rate = cohort_rates.get("cohort_a")
    deterministic_rate = cohort_rates.get("deterministic")
    random_rate = cohort_rates.get("random")
    cohort_spread = (max(cohort_rates.values()) - min(cohort_rates.values())) if len(cohort_rates) >= 2 else None
    best_cohort = ""
    worst_cohort = ""
    if cohort_rates:
        best_cohort = max(cohort_rates.items(), key=lambda item: (item[1], item[0]))[0]
        worst_cohort = min(cohort_rates.items(), key=lambda item: (item[1], item[0]))[0]
    cohort_shift_label = _cohort_shift_label(cohort_rates, cohort_counts)

    min_replay_comparable_rows = int(min((_as_float(row.get("replay_comparable_rows")) or 0) for row in replay_rows)) if replay_rows else 0
    thin_replay_rows_count = sum(1 for row in replay_rows if _upper(row.get("replay_thin_sample_flag")) == "TRUE")
    sample_fragility_label = _sample_fragility_label(int(total_replay_comparable_rows or 0), min_replay_comparable_rows, thin_replay_rows_count)

    provider_family_scope_label = _provider_family_scope_label(
        final_replay_result_label,
        _norm(base.get("source_slice_type")),
        _norm(base.get("condition_dimension")),
        int(total_replay_comparable_rows or 0),
    )
    synchrony_drift_label = _synchrony_drift_label(
        final_replay_result_label,
        replay_correct_rate,
        original_correct_rate,
        replay_window_delta,
        cohort_shift_label,
        candidate_label,
    )
    misleading_persistence_label = _misleading_persistence_label(
        candidate_label,
        original_misleading_stability_rate,
        _as_float(base.get("replay_misleading_stability_rate")),
    )

    dominant_failure_attribution = _dominant_failure_attribution(
        final_replay_result_label,
        candidate_label,
        misleading_persistence_label,
        time_window_failure_label,
        cohort_shift_label,
        sample_fragility_label,
        synchrony_drift_label,
    )
    secondary_failure_attribution = _secondary_failure_attribution(
        dominant_failure_attribution,
        time_window_failure_label,
        cohort_shift_label,
        sample_fragility_label,
        synchrony_drift_label,
        candidate_label,
        misleading_persistence_label,
    )
    failure_confidence_label = _failure_confidence_label(int(total_replay_comparable_rows or 0), dominant_failure_attribution, sample_fragility_label)

    interpretation_note = (
        f"final={final_replay_result_label}; replay_mix={_count_string(replay_result_label_mix, FINAL_REPLAY_ORDER)}; "
        f"time={time_window_failure_label}; cohort={cohort_shift_label}; mislead={misleading_persistence_label}; "
        f"scope={provider_family_scope_label}; drift={synchrony_drift_label}"
    )

    row = {
        "generated_ts": generated_ts,
        "failure_audit_id": "generalization_failure_v1a",
        "hypothesis_id": hypothesis_id,
        "candidate_id": _norm(base.get("candidate_id")) or _norm(queue_row.get("candidate_id")),
        "queue_id": _norm(base.get("queue_id")) or _norm(queue_row.get("queue_id")),
        "provider": _norm(base.get("provider")),
        "event_family": _norm(base.get("event_family")),
        "condition_dimension": _norm(base.get("condition_dimension")),
        "condition_value": _norm(base.get("condition_value")),
        "candidate_label": candidate_label,
        "validation_queue_label": _norm(base.get("validation_queue_label")) or _norm(queue_row.get("validation_queue_label")),
        "validation_score": _as_float(base.get("validation_score")) or _as_float(queue_row.get("validation_score")),
        "original_correct_rate": original_correct_rate,
        "original_delta_vs_provider_family_baseline": original_delta_vs_provider_family_baseline,
        "original_misleading_stability_rate": original_misleading_stability_rate,
        "final_replay_result_label": final_replay_result_label,
        "replay_consolidation_label": replay_consolidation_label,
        "replay_modes_used": _count_string(replay_mode_mix, ["ROBUSTNESS_REPLAY", "PSEUDO_WALK_FORWARD", "COHORT_REPLAY"]),
        "replay_result_label_mix": _count_string(replay_result_label_mix, FINAL_REPLAY_ORDER),
        "replay_confidence_label_mix": _count_string(replay_confidence_label_mix, CONFIDENCE_ORDER),
        "replay_rows_count": len(replay_rows),
        "total_replay_sample_groups": int(total_replay_sample_groups or 0),
        "total_replay_comparable_rows": int(total_replay_comparable_rows or 0),
        "total_replay_correct_count": int(total_replay_correct_count or 0),
        "total_replay_wrong_count": int(total_replay_wrong_count or 0),
        "replay_correct_rate": replay_correct_rate,
        "replay_confidence_label": replay_confidence_label,
        "discovery_comparable_rows": int(discovery_rows or 0),
        "discovery_correct_rate": discovery_rate,
        "replay_window_comparable_rows": int(replay_window_rows or 0),
        "replay_window_correct_rate": replay_window_rate,
        "replay_window_delta": replay_window_delta,
        "time_window_failure_label": time_window_failure_label,
        "cohort_a_correct_rate": cohort_a_rate,
        "deterministic_correct_rate": deterministic_rate,
        "random_correct_rate": random_rate,
        "best_cohort": best_cohort,
        "worst_cohort": worst_cohort,
        "cohort_spread": _round4(cohort_spread),
        "cohort_shift_label": cohort_shift_label,
        "min_replay_comparable_rows": min_replay_comparable_rows,
        "thin_replay_rows_count": thin_replay_rows_count,
        "sample_fragility_label": sample_fragility_label,
        "provider_family_scope_label": provider_family_scope_label,
        "synchrony_drift_label": synchrony_drift_label,
        "misleading_stability_persistence_label": misleading_persistence_label,
        "dominant_failure_attribution": dominant_failure_attribution,
        "secondary_failure_attribution": secondary_failure_attribution,
        "failure_confidence_label": failure_confidence_label,
        "interpretation_note": interpretation_note,
        "learning_model_approved": "FALSE",
        "routing_approved": "FALSE",
        "weighting_approved": "FALSE",
        "calibration_approved": "FALSE",
        "production_approved": "FALSE",
        "notes": _norm(candidate.get("source_summary_note")) or _norm(candidate.get("source_character_understanding_label")) or "",
    }

    meta = {
        "final_replay_result_label": final_replay_result_label,
        "replay_consolidation_label": replay_consolidation_label,
        "replay_modes_used": row["replay_modes_used"],
        "replay_result_label_mix": row["replay_result_label_mix"],
        "replay_confidence_label_mix": row["replay_confidence_label_mix"],
        "replay_rows_count": len(replay_rows),
        "total_replay_sample_groups": row["total_replay_sample_groups"],
        "total_replay_comparable_rows": row["total_replay_comparable_rows"],
        "total_replay_correct_count": row["total_replay_correct_count"],
        "total_replay_wrong_count": row["total_replay_wrong_count"],
        "replay_correct_rate": replay_correct_rate,
        "replay_confidence_label": replay_confidence_label,
        "discovery_comparable_rows": row["discovery_comparable_rows"],
        "discovery_correct_rate": discovery_rate,
        "replay_window_comparable_rows": row["replay_window_comparable_rows"],
        "replay_window_correct_rate": replay_window_rate,
        "replay_window_delta": replay_window_delta,
        "time_window_failure_label": time_window_failure_label,
        "cohort_a_correct_rate": cohort_a_rate,
        "deterministic_correct_rate": deterministic_rate,
        "random_correct_rate": random_rate,
        "best_cohort": best_cohort,
        "worst_cohort": worst_cohort,
        "cohort_spread": _round4(cohort_spread),
        "cohort_shift_label": cohort_shift_label,
        "min_replay_comparable_rows": min_replay_comparable_rows,
        "thin_replay_rows_count": thin_replay_rows_count,
        "sample_fragility_label": sample_fragility_label,
        "provider_family_scope_label": provider_family_scope_label,
        "synchrony_drift_label": synchrony_drift_label,
        "misleading_stability_persistence_label": misleading_persistence_label,
        "dominant_failure_attribution": dominant_failure_attribution,
        "secondary_failure_attribution": secondary_failure_attribution,
        "failure_confidence_label": failure_confidence_label,
        "interpretation_note": interpretation_note,
        "queue_row": queue_row,
    }
    return row, meta


def _build_failure_rows(
    sources: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    replay_groups = _group_replay_rows(sources["replay_validation"])
    queue_lookup = { _norm(row.get("candidate_id")): row for row in sources["validation_queue"] }
    candidate_lookup = { _norm(row.get("candidate_id")): row for row in sources["candidates"] }
    failures: List[Dict[str, Any]] = []
    meta_rows: List[Dict[str, Any]] = []
    for hypothesis_id, replay_rows in sorted(replay_groups.items()):
        row, meta = _build_hypothesis_row(
            generated_ts,
            hypothesis_id,
            replay_rows,
            queue_lookup,
            candidate_lookup,
            sources["accuracy"],
        )
        failures.append(row)
        meta["hypothesis_id"] = hypothesis_id
        meta_rows.append(meta)
    summary_context = {
        "replay_groups": replay_groups,
        "queue_lookup": queue_lookup,
        "candidate_lookup": candidate_lookup,
    }
    return failures, meta_rows, summary_context


def _build_summary_rows(
    failure_rows: Sequence[Dict[str, Any]],
    meta_rows: Sequence[Dict[str, Any]],
    generated_ts: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    total_hypotheses = len(failure_rows)

    final_label_counts = Counter(row["final_replay_result_label"] for row in failure_rows)
    dominant_attr_counts = Counter(row["dominant_failure_attribution"] for row in failure_rows)
    consolidation_counts = Counter(row["replay_consolidation_label"] for row in failure_rows)
    confidence_counts = Counter(row["failure_confidence_label"] for row in failure_rows)

    overall_row = {
        "generated_ts": generated_ts,
        "section": "A_OVERALL_FAILURE_SUMMARY",
        "rank": 0,
        "hypothesis_count": total_hypotheses,
        "replay_result_label_counts": _count_string(final_label_counts, FINAL_REPLAY_ORDER),
        "dominant_failure_attribution_counts": _count_string(dominant_attr_counts, FAILURE_ATTRIBUTION_ORDER),
        "replay_consolidation_label_counts": _count_string(consolidation_counts, CONSOLIDATION_ORDER),
        "failure_confidence_label_counts": _count_string(confidence_counts, CONFIDENCE_ORDER),
        "notes": "All replay-tested hypotheses were originally misleading-stability candidates; the summary focuses on replay failure mechanisms.",
    }
    rows.append(overall_row)

    for rank, attr in enumerate(FAILURE_ATTRIBUTION_ORDER, start=1):
        attr_rows = [row for row in failure_rows if row["dominant_failure_attribution"] == attr]
        if not attr_rows:
            continue
        representative = max(attr_rows, key=lambda row: (_as_float(row.get("validation_score")) or 0.0, _as_float(row.get("replay_correct_rate")) or 0.0, row["candidate_id"]))
        note_map = {
            "MISLEADING_STABILITY_PERSISTS": "Replay preserved stable-error risk across the majority of retained hypotheses.",
            "TIME_WINDOW_SHIFT": "The discovery/replay split changed enough to explain the weakness.",
            "COHORT_SHIFT": "The cohort construction materially changed the result.",
            "SAMPLE_FRAGILITY": "The replay depth was too thin to stabilize the hypothesis.",
            "PROVIDER_DEPENDENCE": "The hypothesis appears tightly tied to a single provider's historical pattern.",
            "EVENT_FAMILY_SHIFT": "Family composition appears to dominate the replay behavior.",
            "SYNCHRONY_DRIFT": "The synchrony/stability condition moved enough to weaken generalization.",
            "MULTI_FACTOR_FAILURE": "No single failure mechanism dominated the replay weakness.",
            "NO_FAILURE_GENERALIZES": "This is an exception row where the hypothesis held up under replay.",
            "INSUFFICIENT_TRACEABILITY": "Source information was not rich enough to isolate a dominant mechanism.",
        }
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "B_FAILURE_ATTRIBUTION_BREAKDOWN",
                "rank": rank,
                "hypothesis_count": len(attr_rows),
                "percent_of_hypotheses": _round4(len(attr_rows) / total_hypotheses if total_hypotheses else None),
                "representative_hypothesis": representative["candidate_id"],
                "interpretation_note": note_map.get(attr, ""),
            }
        )

    time_rows = [row for row in failure_rows if row["time_window_failure_label"] in {"TIME_WINDOW_STABLE", "TIME_WINDOW_WEAKENS", "TIME_WINDOW_REVERSAL", "TIME_WINDOW_INSUFFICIENT"}]
    avg_time_delta = _safe_mean([_as_float(row.get("replay_window_delta")) for row in failure_rows if _as_float(row.get("replay_window_delta")) is not None])
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "C_TIME_WINDOW_FAILURE_SUMMARY",
            "rank": 0,
            "time_window_stable_count": sum(1 for row in failure_rows if row["time_window_failure_label"] == "TIME_WINDOW_STABLE"),
            "time_window_weakens_count": sum(1 for row in failure_rows if row["time_window_failure_label"] == "TIME_WINDOW_WEAKENS"),
            "time_window_reversal_count": sum(1 for row in failure_rows if row["time_window_failure_label"] == "TIME_WINDOW_REVERSAL"),
            "time_window_insufficient_count": sum(1 for row in failure_rows if row["time_window_failure_label"] == "TIME_WINDOW_INSUFFICIENT"),
            "average_replay_window_delta": _round4(avg_time_delta),
            "notes": "Time-window labels are derived from the discovery-vs-replay-window delta in the replay validation sheet.",
        }
    )

    cohort_shift_counts = Counter(row["cohort_shift_label"] for row in failure_rows)
    most_cohort_dependent = max(
        failure_rows,
        key=lambda row: (
            {"HIGH_COHORT_SHIFT": 3, "MODERATE_COHORT_SHIFT": 2, "LOW_COHORT_SHIFT": 1, "COHORT_INSUFFICIENT": 0}.get(row["cohort_shift_label"], 0),
            _as_float(row.get("cohort_spread")) or 0.0,
            _as_float(row.get("replay_correct_rate")) or 0.0,
            row["candidate_id"],
        ),
    ) if failure_rows else {}
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "D_COHORT_SHIFT_SUMMARY",
            "rank": 0,
            "low_cohort_shift_count": cohort_shift_counts.get("LOW_COHORT_SHIFT", 0),
            "moderate_cohort_shift_count": cohort_shift_counts.get("MODERATE_COHORT_SHIFT", 0),
            "high_cohort_shift_count": cohort_shift_counts.get("HIGH_COHORT_SHIFT", 0),
            "cohort_insufficient_count": cohort_shift_counts.get("COHORT_INSUFFICIENT", 0),
            "most_cohort_dependent_hypothesis": most_cohort_dependent.get("candidate_id", ""),
            "notes": "Cohort shift uses the spread across cohort_a, deterministic, and random replay rates.",
        }
    )

    fragility_counts = Counter(row["sample_fragility_label"] for row in failure_rows)
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "E_SAMPLE_FRAGILITY_SUMMARY",
            "rank": 0,
            "low_sample_fragility_count": fragility_counts.get("LOW_SAMPLE_FRAGILITY", 0),
            "moderate_sample_fragility_count": fragility_counts.get("MODERATE_SAMPLE_FRAGILITY", 0),
            "high_sample_fragility_count": fragility_counts.get("HIGH_SAMPLE_FRAGILITY", 0),
            "insufficient_sample_count": fragility_counts.get("INSUFFICIENT_SAMPLE", 0),
            "notes": "Sample fragility uses total comparable rows and the thin-row mix across replay modes.",
        }
    )

    misleading_rows = [row for row in failure_rows if row["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY"]
    strongest_persistent = max(
        misleading_rows,
        key=lambda row: (
            _as_float(row.get("original_misleading_stability_rate")) or 0.0,
            _as_float(row.get("total_replay_comparable_rows")) or 0.0,
            _as_float(row.get("replay_correct_rate")) or 0.0,
            row["candidate_id"],
        ),
    ) if misleading_rows else {}
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "F_MISLEADING_STABILITY_FAILURE_SUMMARY",
            "rank": 0,
            "misleading_stability_candidates_analyzed": len(misleading_rows),
            "misleading_stability_persists_count": sum(1 for row in misleading_rows if row["misleading_stability_persistence_label"] == "MISLEADING_STABILITY_PERSISTS"),
            "misleading_stability_weakens_count": sum(1 for row in misleading_rows if row["misleading_stability_persistence_label"] == "MISLEADING_STABILITY_WEAKENS"),
            "misleading_stability_fails_count": sum(1 for row in misleading_rows if row["misleading_stability_persistence_label"] == "MISLEADING_STABILITY_FAILS"),
            "strongest_persistent_misleading_stability_hypothesis": strongest_persistent.get("candidate_id", ""),
            "average_replay_misleading_stability_rate": _round4(_safe_mean([_as_float(row.get("original_misleading_stability_rate")) for row in misleading_rows])),
            "notes": "Every VALIDATE_FIRST hypothesis in this batch is a misleading-stability candidate, so persistence is the central risk signal.",
        }
    )

    generalizing_rows = [row for row in failure_rows if row["final_replay_result_label"] == "GENERALIZES" or row["dominant_failure_attribution"] == "NO_FAILURE_GENERALIZES"]
    for rank, row in enumerate(sorted(generalizing_rows, key=lambda item: (_as_float(item.get("replay_correct_rate")) or 0.0, item["candidate_id"]), reverse=True), start=1):
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "G_GENERALIZING_EXCEPTIONS",
                "rank": rank,
                "hypothesis_id": row["hypothesis_id"],
                "candidate_id": row["candidate_id"],
                "provider": row["provider"],
                "event_family": row["event_family"],
                "condition_dimension": row["condition_dimension"],
                "condition_value": row["condition_value"],
                "candidate_label": row["candidate_label"],
                "replay_correct_rate": row["replay_correct_rate"],
                "failure_confidence_label": row["failure_confidence_label"],
                "interpretation_note": row["interpretation_note"],
                "notes": "Replay exception retained as a generalizing hypothesis.",
            }
        )

    if len(failure_rows) == 0:
        final_label = "INSUFFICIENT_FAILURE_TRACEABILITY"
        learning_implication = "PAUSE_LEARNING_LAYER"
        final_reason = "No replay rows were available to explain the failure."
        implication_reason = "Replay traceability is insufficient."
    else:
        dominant_counts = Counter(row["dominant_failure_attribution"] for row in failure_rows)
        non_failure = dominant_counts.get("NO_FAILURE_GENERALIZES", 0)
        misleading = dominant_counts.get("MISLEADING_STABILITY_PERSISTS", 0)
        time_or_cohort = dominant_counts.get("TIME_WINDOW_SHIFT", 0) + dominant_counts.get("COHORT_SHIFT", 0)
        sample = dominant_counts.get("SAMPLE_FRAGILITY", 0)
        if misleading >= max(time_or_cohort, sample, non_failure) and misleading >= len(failure_rows) / 2:
            final_label = "MISLEADING_STABILITY_DOMINATES"
            learning_implication = "PIVOT_TO_RISK_MODELING"
            final_reason = "Persistent misleading-stability risk is the clearest repeatable mechanism across replay-tested hypotheses."
            implication_reason = "The evidence points toward modeling stable-error risk rather than promoting learning rules."
        elif time_or_cohort >= max(misleading, sample):
            final_label = "FAILURE_MAINLY_WINDOW_OR_COHORT"
            learning_implication = "REPLAY_MORE_DATA_REQUIRED"
            final_reason = "Time-window and cohort structure explain most replay weakness."
            implication_reason = "More data is needed to separate window effects from cohort construction."
        elif sample >= max(misleading, time_or_cohort):
            final_label = "FAILURE_MAINLY_SAMPLE_FRAGILITY"
            learning_implication = "REPLAY_MORE_DATA_REQUIRED"
            final_reason = "Thin replay depth is the main constraint."
            implication_reason = "Replay should be expanded before any learning decision."
        elif misleading + time_or_cohort > 0:
            final_label = "FAILURE_MULTI_FACTOR"
            learning_implication = "PAUSE_LEARNING_LAYER"
            final_reason = "No single failure mechanism dominates; the replay weakness is distributed."
            implication_reason = "The current replay evidence is too mixed for learning."
        else:
            final_label = "INSUFFICIENT_FAILURE_TRACEABILITY"
            learning_implication = "PAUSE_LEARNING_LAYER"
            final_reason = "The replay evidence does not isolate a dominant failure mechanism."
            implication_reason = "Traceability is too weak to classify the failure."

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "H_FINAL_INTERPRETATION",
            "rank": 0,
            "hypothesis_count": len(failure_rows),
            "replay_result_label_counts": _count_string(final_label_counts, FINAL_REPLAY_ORDER),
            "dominant_failure_attribution_counts": _count_string(dominant_attr_counts, FAILURE_ATTRIBUTION_ORDER),
            "replay_consolidation_label_counts": _count_string(consolidation_counts, CONSOLIDATION_ORDER),
            "failure_confidence_label_counts": _count_string(confidence_counts, CONFIDENCE_ORDER),
            "learning_implication_label": learning_implication,
            "learning_implication_reason": implication_reason,
            "final_interpretation_label": final_label,
            "final_interpretation_reason": final_reason,
            "notes": "This audit explains replay weakness only; it does not approve learning or production behavior.",
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


def build_character_learning_generalization_failure() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    failure_rows, meta_rows, _ = _build_failure_rows(sources, generated_ts)
    summary_rows = _build_summary_rows(failure_rows, meta_rows, generated_ts)

    failure_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FAILURE_SHEET, FAILURE_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FAILURE_SHEET, failure_headers, failure_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)
    final_row = next((row for row in summary_rows if row.get("section") == "H_FINAL_INTERPRETATION"), {})
    return {
        "generated_ts": generated_ts,
        "hypotheses_analyzed": len(failure_rows),
        "replay_rows_read": len(sources["replay_validation"]),
        "providers_represented": _count_string(Counter(row["provider"] for row in failure_rows), PROVIDER_ORDER),
        "families_represented": _count_string(Counter(row["event_family"] for row in failure_rows), FAMILY_ORDER),
        "dominant_failure_attribution_counts": final_row.get("dominant_failure_attribution_counts", ""),
        "final_interpretation_label": final_row.get("final_interpretation_label", ""),
        "learning_implication_label": final_row.get("learning_implication_label", ""),
        "registry_result": registry_result,
    }


def main() -> None:
    print(build_character_learning_generalization_failure())


if __name__ == "__main__":
    main()
