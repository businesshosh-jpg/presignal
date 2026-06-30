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
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_MAP_SHEET = "Character_Understanding_Pattern_Map"
OUTPUT_SUMMARY_SHEET = "Character_Understanding_Pattern_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "PROVIDER_CHARACTER_UNDERSTANDING_PATTERN_MAP",
        "physical_sheet_name": OUTPUT_MAP_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Understanding Layer v1",
        "notes": "Derived-only character understanding pattern map",
    },
    {
        "logical_sheet_id": "PROVIDER_CHARACTER_UNDERSTANDING_PATTERN_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Understanding Layer v1",
        "notes": "Derived-only character understanding pattern summary",
    },
]

MAP_HEADERS = [
    "generated_ts",
    "slice_type",
    "slice_key",
    "provider",
    "event_family",
    "importance",
    "predictability_bucket",
    "direction_synchrony_bucket",
    "stability_label",
    "recommended_protocol",
    "cohort_bucket",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "non_comparable_rows",
    "thin_sample_flag",
    "confidence_label",
    "global_baseline_rate",
    "provider_baseline_rate",
    "family_baseline_rate",
    "provider_family_baseline_rate",
    "correct_rate",
    "delta_vs_global_baseline",
    "delta_vs_provider_baseline",
    "delta_vs_family_baseline",
    "delta_vs_provider_family_baseline",
    "avg_forecast_direction_concentration",
    "avg_pattern_concentration_score",
    "avg_expression_similarity_mean",
    "direction_synchrony_mix",
    "stability_label_mix",
    "reproducibility_label_mix",
    "recommended_protocol_mix",
    "dominant_forecast_direction_mix",
    "dominant_pattern_mix",
    "cohort_mix",
    "importance_mix",
    "predictability_mix",
    "outcome_result_mix",
    "misleading_stability_count",
    "misleading_stability_rate",
    "missing_metric_flag",
    "character_understanding_label",
    "interpretation_note",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "provider",
    "event_family",
    "slice_type",
    "slice_key",
    "character_understanding_label",
    "confidence_label",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "provider_family_baseline_rate",
    "delta_vs_provider_family_baseline",
    "misleading_stability_count",
    "misleading_stability_rate",
    "thin_sample_flag",
    "notes",
]

SLICE_TYPES = [
    ("provider_event_family", ("provider", "event_family")),
    ("provider_event_family_predictability", ("provider", "event_family", "predictability_bucket")),
    ("provider_event_family_direction_synchrony", ("provider", "event_family", "direction_synchrony_bucket")),
    ("provider_event_family_stability", ("provider", "event_family", "stability_label")),
    ("provider_event_family_importance", ("provider", "event_family", "importance")),
    ("provider_event_family_cohort", ("provider", "event_family", "cohort_bucket")),
    ("provider_event_family_protocol", ("provider", "event_family", "recommended_protocol")),
]

PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]
FAMILY_ORDER = ["central_bank", "energy", "growth", "housing", "inflation", "labor", "manufacturing", "other"]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


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
    cleaned = [v for v in values if v is not None]
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


def _cohort_bucket(cohort_id: Any, cohort_group: Any = "") -> str:
    raw = _upper(cohort_group or cohort_id)
    if raw.startswith("COHORT_A") or "COHORT_A" in raw:
        return "cohort_a"
    if "RANDOM" in raw:
        return "random"
    if "DETERMINISTIC" in raw or raw.startswith("COHORT_B") or raw.startswith("COHORT_C"):
        return "deterministic"
    return "unknown"


def _is_comparable(row: Dict[str, Any]) -> bool:
    if _as_bool(row.get("actual_comparable")):
        return True
    return _upper(row.get("outcome_result_label")) in {"FORECAST_CORRECT", "FORECAST_INLINE_CORRECT", "FORECAST_WRONG"}


def _is_correct(row: Dict[str, Any]) -> bool:
    return _upper(row.get("outcome_result_label")) in {"FORECAST_CORRECT", "FORECAST_INLINE_CORRECT"} or _as_bool(row.get("forecast_matches_actual"))


def _mix_string(rows: Sequence[Dict[str, Any]], field: str) -> str:
    counter = Counter(_norm(r.get(field)) or "MISSING" for r in rows)
    return "|".join(f"{key}:{count}" for key, count in counter.most_common())


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "accuracy_audit": "Signal_Synchrony_Accuracy_Audit",
        "direction_robustness": "Signal_Synchrony_Direction_Robustness",
        "direction_robustness_summary": "Signal_Synchrony_Direction_Robustness_Summary",
        "microcohort": "Provider_Character_Direct_Expression_Microcohort",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
        "cohort_characterization": "Signal_Synchrony_Cohort_Characterization",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "family_slice": "Signal_Synchrony_Family_Slice_Performance",
        "conditional_value_mechanism": "Signal_Synchrony_Conditional_Value_Mechanism",
        "provider_dep_falsification": "Signal_Synchrony_Provider_Dep_Falsification",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _join_base_rows(sources: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    accuracy_lookup = {_norm(row.get("sample_group_id")): row for row in sources["accuracy_audit"]}
    micro_lookup = {_norm(row.get("sample_group_id")): row for row in sources["microcohort"]}
    outcome_lookup = {_norm(row.get("sample_group_id")): row for row in sources["outcome_check"]}
    merged_rows: List[Dict[str, Any]] = []
    for row in sources["provider_slice"]:
        sample_group_id = _norm(row.get("sample_group_id"))
        if not sample_group_id:
            continue
        acc = accuracy_lookup.get(sample_group_id, {})
        micro = micro_lookup.get(sample_group_id, {})
        outcome = outcome_lookup.get(sample_group_id, {})
        merged = dict(row)
        merged["sample_group_id"] = sample_group_id
        merged["cohort_id"] = _norm(merged.get("cohort_id") or acc.get("cohort_id") or outcome.get("cohort_id"))
        merged["cohort_group"] = _norm(merged.get("cohort_group") or acc.get("cohort_group"))
        merged["cohort_bucket"] = _cohort_bucket(merged.get("cohort_id"), merged.get("cohort_group"))
        merged["direction_synchrony_bucket"] = _norm(acc.get("direction_synchrony_bucket") or row.get("direction_synchrony_bucket"))
        merged["pattern_synchrony_bucket"] = _norm(acc.get("pattern_synchrony_bucket") or row.get("pattern_synchrony_bucket"))
        merged["expression_similarity_bucket"] = _norm(acc.get("expression_similarity_bucket") or row.get("expression_similarity_bucket"))
        merged["overall_synchrony_bucket"] = _norm(acc.get("overall_synchrony_bucket") or row.get("overall_synchrony_bucket"))
        merged["dominant_pattern_label"] = _norm(acc.get("dominant_pattern_label") or micro.get("dominant_pattern_label"))
        merged["provider_control_key"] = _norm(acc.get("provider_control_key") or row.get("provider_control_key"))
        merged["family_control_key"] = _norm(acc.get("family_control_key") or row.get("family_control_key"))
        merged["cohort_control_key"] = _norm(acc.get("cohort_control_key") or row.get("cohort_control_key"))
        merged["provider_family_key"] = _norm(acc.get("provider_family_key") or row.get("provider_family_key"))
        merged["family_predictability_key"] = _norm(acc.get("family_predictability_key") or row.get("family_predictability_key"))
        merged["actual_available"] = _norm(row.get("actual_available") or outcome.get("actual_available") or acc.get("actual_available"))
        merged["actual_comparable"] = _norm(row.get("actual_comparable") or outcome.get("actual_comparable") or acc.get("actual_comparable"))
        merged["forecast_matches_actual"] = _norm(row.get("forecast_matches_actual") or outcome.get("forecast_matches_actual") or acc.get("forecast_matches_actual"))
        merged["outcome_result_label"] = _norm(row.get("outcome_result_label") or outcome.get("outcome_result_label") or acc.get("outcome_result_label"))
        merged["outcome_check_status"] = _norm(row.get("outcome_check_status") or outcome.get("outcome_check_status") or acc.get("outcome_check_status"))
        merged["predictability_bucket"] = _norm(row.get("predictability_bucket") or acc.get("predictability_bucket"))
        merged["predictability_index"] = _norm(row.get("predictability_index") or acc.get("predictability_index"))
        merged["stability_label"] = _norm(row.get("stability_label") or acc.get("stability_label"))
        merged["recommended_protocol"] = _norm(row.get("recommended_protocol") or acc.get("recommended_protocol"))
        merged["reproducibility_outcome_label"] = _norm(row.get("reproducibility_outcome_label") or acc.get("reproducibility_outcome_label"))
        merged["global_baseline_rate"] = _as_float(row.get("global_baseline_rate") or row.get("global_baseline") or acc.get("global_baseline_rate"))
        merged["family_baseline_rate"] = _as_float(row.get("family_baseline_rate") or acc.get("family_baseline_rate"))
        merged["family_delta_vs_global_baseline"] = _as_float(row.get("family_delta_vs_global_baseline") or acc.get("family_delta_vs_global_baseline"))
        merged["provider_in_family_correct_rate"] = _as_float(row.get("provider_in_family_correct_rate") or acc.get("provider_in_family_correct_rate"))
        merged["provider_delta_vs_family_baseline"] = _as_float(row.get("provider_delta_vs_family_baseline") or acc.get("provider_delta_vs_family_baseline"))
        merged["provider_delta_vs_global_baseline"] = _as_float(row.get("provider_delta_vs_global_baseline") or acc.get("provider_delta_vs_global_baseline"))
        merged["provider_dependency_score"] = _as_float(row.get("provider_dependency_score") or acc.get("provider_dependency_score"))
        merged["provider_dependency_label"] = _norm(row.get("provider_dependency_label") or acc.get("provider_dependency_label"))
        merged["family_difficulty_label"] = _norm(row.get("family_difficulty_label") or acc.get("family_difficulty_label"))
        merged["family_routing_relevance_label"] = _norm(row.get("family_routing_relevance_label") or acc.get("family_routing_relevance_label"))
        merged["family_stability_label"] = _norm(row.get("family_stability_label") or acc.get("family_stability_label"))
        merged["provider_correct_rate_min"] = _as_float(row.get("provider_correct_rate_min") or acc.get("provider_correct_rate_min"))
        merged["provider_correct_rate_max"] = _as_float(row.get("provider_correct_rate_max") or acc.get("provider_correct_rate_max"))
        merged["provider_correct_rate_range"] = _as_float(row.get("provider_correct_rate_range") or acc.get("provider_correct_rate_range"))
        merged["cohort_correct_rate_min"] = _as_float(row.get("cohort_correct_rate_min") or acc.get("cohort_correct_rate_min"))
        merged["cohort_correct_rate_max"] = _as_float(row.get("cohort_correct_rate_max") or acc.get("cohort_correct_rate_max"))
        merged["cohort_correct_rate_range"] = _as_float(row.get("cohort_correct_rate_range") or acc.get("cohort_correct_rate_range"))
        merged["thin_sample_flag"] = _norm(row.get("thin_sample_flag") or acc.get("thin_sample_flag"))
        merged["confidence_label"] = _norm(row.get("confidence_label") or acc.get("confidence_label"))
        merged["consensus_value"] = _as_float(row.get("consensus_value") or acc.get("consensus_value"))
        merged["prev_revision"] = _as_float(row.get("prev_revision") or acc.get("prev_revision"))
        merged["released_value"] = _as_float(row.get("released_value") or acc.get("released_value"))
        merged["surprise_value"] = _as_float(row.get("surprise_value") or acc.get("surprise_value"))
        merged["abs_surprise_value"] = _as_float(row.get("abs_surprise_value") or acc.get("abs_surprise_value"))
        merged["consensus_prev_gap"] = _as_float(row.get("consensus_prev_gap") or acc.get("consensus_prev_gap"))
        merged["abs_consensus_prev_gap"] = _as_float(row.get("abs_consensus_prev_gap") or acc.get("abs_consensus_prev_gap"))
        merged["actual_economic_direction"] = _norm(row.get("actual_economic_direction") or acc.get("actual_economic_direction"))
        merged["actual_vs_previous_direction"] = _norm(row.get("actual_vs_previous_direction") or acc.get("actual_vs_previous_direction"))
        merged["actual_source_provider"] = _norm(row.get("actual_source_provider") or acc.get("actual_source_provider"))
        merged["actual_source_series_id"] = _norm(row.get("actual_source_series_id") or acc.get("actual_source_series_id"))
        merged["actual_transform"] = _norm(row.get("actual_transform") or acc.get("actual_transform"))
        merged["dominant_forecast_direction"] = _norm(row.get("dominant_forecast_direction") or acc.get("dominant_forecast_direction"))
        merged["forecast_direction_concentration"] = _as_float(row.get("forecast_direction_concentration") or acc.get("forecast_direction_concentration"))
        merged["pattern_concentration_score"] = _as_float(row.get("pattern_concentration_score") or acc.get("pattern_concentration_score"))
        merged["expression_similarity_mean"] = _as_float(row.get("expression_similarity_mean") or acc.get("expression_similarity_mean"))
        merged["dominant_pattern_label"] = _norm(merged.get("dominant_pattern_label"))
        merged["direction_synchrony_bucket"] = _norm(merged.get("direction_synchrony_bucket"))
        merged["pattern_synchrony_bucket"] = _norm(merged.get("pattern_synchrony_bucket"))
        merged["expression_similarity_bucket"] = _norm(merged.get("expression_similarity_bucket"))
        merged["overall_synchrony_bucket"] = _norm(merged.get("overall_synchrony_bucket"))
        merged["missing_metric_flag"] = _norm(acc.get("missing_metric_flag") or row.get("missing_metric_flag"))
        merged["notes"] = _norm(row.get("notes") or acc.get("notes"))
        merged["microcohort_interpretation_label"] = _norm(micro.get("interpretation_label"))
        merged["source_row_type"] = "provider_slice"
        merged["has_actual"] = _is_comparable(merged)
        merged["is_correct"] = _is_correct(merged)
        merged["cohort_bucket"] = _cohort_bucket(merged.get("cohort_id"), merged.get("cohort_group"))
        merged["source_event_family"] = _norm(merged.get("event_family"))
        merged["source_provider"] = _norm(merged.get("provider"))
        merged["source_importance"] = _norm(merged.get("importance"))
        merged["source_predictability_bucket"] = _norm(merged.get("predictability_bucket"))
        merged["source_direction_bucket"] = _norm(merged.get("direction_synchrony_bucket"))
        merged["source_stability_label"] = _norm(merged.get("stability_label"))
        merged["source_recommended_protocol"] = _norm(merged.get("recommended_protocol"))
        merged["source_cohort_bucket"] = _norm(merged.get("cohort_bucket"))
        merged["source_sample_group_id"] = sample_group_id
        merged["source_accuracy_row_present"] = "TRUE" if sample_group_id in accuracy_lookup else "FALSE"
        merged["source_outcome_row_present"] = "TRUE" if sample_group_id in outcome_lookup else "FALSE"
        merged["source_microcohort_row_present"] = "TRUE" if sample_group_id in micro_lookup else "FALSE"
        merged["source_direction_robustness_row_present"] = "FALSE"
        merged["source_family_slice_row_present"] = "TRUE" if merged.get("family_baseline_rate") is not None else "FALSE"
        merged["source_provider_family_key"] = _norm(merged.get("provider_family_key") or f"{merged['provider']}|{merged['event_family']}")
        merged["source_family_predictability_key"] = _norm(merged.get("family_predictability_key") or f"{merged['event_family']}|{merged['predictability_bucket']}")
        merged["source_provider_control_key"] = _norm(merged.get("provider_control_key") or merged["provider"])
        merged["source_family_control_key"] = _norm(merged.get("family_control_key") or merged["event_family"])
        merged["source_cohort_control_key"] = _norm(merged.get("cohort_control_key") or merged["cohort_bucket"])
        merged["source_notes"] = f"merged_from_provider_slice; accuracy_join={'yes' if sample_group_id in accuracy_lookup else 'no'}"
        merged_rows.append(merged)
    return merged_rows


def _slice_entries(row: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    provider = _norm(row.get("provider"))
    family = _norm(row.get("event_family"))
    predictability = _norm(row.get("predictability_bucket")) or "MISSING"
    direction = _norm(row.get("direction_synchrony_bucket")) or "MISSING"
    stability = _norm(row.get("stability_label")) or "MISSING"
    importance = _norm(row.get("importance")) or "MISSING"
    cohort_bucket = _norm(row.get("cohort_bucket")) or "MISSING"
    protocol = _norm(row.get("recommended_protocol")) or "MISSING"
    values = {
        "provider": provider,
        "event_family": family,
        "predictability_bucket": predictability,
        "direction_synchrony_bucket": direction,
        "stability_label": stability,
        "importance": importance,
        "cohort_bucket": cohort_bucket,
        "recommended_protocol": protocol,
    }
    return [
        ("provider_event_family", f"{provider}|{family}", values),
        ("provider_event_family_predictability", f"{provider}|{family}|{predictability}", values),
        ("provider_event_family_direction_synchrony", f"{provider}|{family}|{direction}", values),
        ("provider_event_family_stability", f"{provider}|{family}|{stability}", values),
        ("provider_event_family_importance", f"{provider}|{family}|{importance}", values),
        ("provider_event_family_cohort", f"{provider}|{family}|{cohort_bucket}", values),
        ("provider_event_family_protocol", f"{provider}|{family}|{protocol}", values),
    ]


def _baselines(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    comparable = [r for r in rows if r["has_actual"]]
    global_baseline = _safe_rate(sum(1 for r in comparable if r["is_correct"]), len(comparable))
    provider = {}
    family = {}
    provider_family = {}
    for key_field, target in [
        ("provider", provider),
        ("event_family", family),
        ("provider_family", provider_family),
    ]:
        if key_field == "provider_family":
            groups = defaultdict(list)
            for row in comparable:
                groups[f"{row['source_provider']}|{row['source_event_family']}"].append(row)
        else:
            groups = defaultdict(list)
            for row in comparable:
                groups[row[f"source_{key_field}"]].append(row)
        for key, group in groups.items():
            target[key] = _safe_rate(sum(1 for r in group if r["is_correct"]), len(group))
    return {
        "global": global_baseline,
        "provider": provider,
        "family": family,
        "provider_family": provider_family,
    }


def _slice_character_label(
    correct_rate: Optional[float],
    provider_family_baseline: Optional[float],
    family_baseline: Optional[float],
    global_baseline: Optional[float],
    misleading_stability_rate: Optional[float],
    comparable_rows: int,
    provider_baseline: Optional[float],
) -> str:
    if comparable_rows == 0 or correct_rate is None:
        return "INSUFFICIENT_DATA"
    if comparable_rows < 8:
        return "THIN_SAMPLE"
    if misleading_stability_rate is not None and misleading_stability_rate >= 0.40:
        return "MISLEADING_STABILITY"
    delta_pf = (correct_rate - provider_family_baseline) if provider_family_baseline is not None else None
    delta_family = (correct_rate - family_baseline) if family_baseline is not None else None
    delta_global = (correct_rate - global_baseline) if global_baseline is not None else None
    if delta_pf is not None and delta_pf >= 0.08 and (delta_family is None or delta_family >= -0.02) and (delta_global is None or delta_global >= -0.02):
        return "CHARACTER_STRENGTH"
    if delta_pf is not None and delta_pf <= -0.08:
        return "CHARACTER_WEAKNESS"
    if delta_pf is not None and abs(delta_pf) < 0.08:
        other_positive = sum(1 for d in [delta_family, delta_global, (correct_rate - provider_baseline) if provider_baseline is not None else None] if d is not None and d >= 0.05)
        other_negative = sum(1 for d in [delta_family, delta_global, (correct_rate - provider_baseline) if provider_baseline is not None else None] if d is not None and d <= -0.05)
        if other_positive and other_negative:
            return "CONTEXT_DEPENDENT"
        if abs((correct_rate - (provider_baseline if provider_baseline is not None else correct_rate))) < 0.05 and abs((delta_family or 0.0)) < 0.05 and abs((delta_global or 0.0)) < 0.05:
            return "NOISY"
        if other_positive or other_negative:
            return "CONTEXT_DEPENDENT"
    return "NOISY"


def _build_map_rows(generated_ts: str, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    baselines = _baselines(rows)
    global_baseline = baselines["global"]
    provider_b = baselines["provider"]
    family_b = baselines["family"]
    provider_family_b = baselines["provider_family"]

    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    meta_by_group: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in rows:
        for slice_type, slice_key, meta in _slice_entries(row):
            groups[(slice_type, slice_key)].append(row)
            meta_by_group[(slice_type, slice_key)] = meta

    audit_rows: List[Dict[str, Any]] = []
    for (slice_type, slice_key), group_rows in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        meta = meta_by_group[(slice_type, slice_key)]
        comparable_rows = [r for r in group_rows if r["has_actual"]]
        correct_count = sum(1 for r in comparable_rows if r["is_correct"])
        wrong_count = sum(1 for r in comparable_rows if not r["is_correct"])
        correct_rate = _safe_rate(correct_count, len(comparable_rows))
        provider = meta["provider"]
        family = meta["event_family"]
        provider_family_key = f"{provider}|{family}"
        provider_baseline = provider_b.get(provider)
        family_baseline = family_b.get(family)
        provider_family_baseline = provider_family_b.get(provider_family_key)
        if slice_type == "provider_event_family":
            # For the base slice, provider/family baseline equals the slice itself.
            provider_family_baseline = correct_rate if correct_rate is not None else provider_family_baseline
        delta_global = (correct_rate - global_baseline) if correct_rate is not None and global_baseline is not None else None
        delta_provider = (correct_rate - provider_baseline) if correct_rate is not None and provider_baseline is not None else None
        delta_family = (correct_rate - family_baseline) if correct_rate is not None and family_baseline is not None else None
        delta_provider_family = (correct_rate - provider_family_baseline) if correct_rate is not None and provider_family_baseline is not None else None
        misleading_count = sum(
            1
            for r in comparable_rows
            if _upper(r.get("direction_synchrony_bucket")) in {"HIGH", "VERY_HIGH"} and not r["is_correct"]
        )
        misleading_rate = _safe_rate(misleading_count, len(comparable_rows))
        confidence = _confidence_label(len(comparable_rows))
        label = _slice_character_label(
            correct_rate,
            provider_family_baseline,
            family_baseline,
            global_baseline,
            misleading_rate,
            len(comparable_rows),
            provider_baseline,
        )
        missing_metric_flag = "TRUE" if any(
            _norm(r.get(field)) == "" for r in group_rows for field in [
                "direction_synchrony_bucket",
                "stability_label",
                "recommended_protocol",
                "forecast_direction_concentration",
                "pattern_concentration_score",
                "expression_similarity_mean",
            ]
        ) else "FALSE"
        row = {
            "generated_ts": generated_ts,
            "slice_type": slice_type,
            "slice_key": slice_key,
            "provider": provider,
            "event_family": family,
            "importance": meta["importance"],
            "predictability_bucket": meta["predictability_bucket"],
            "direction_synchrony_bucket": meta["direction_synchrony_bucket"],
            "stability_label": meta["stability_label"],
            "recommended_protocol": meta["recommended_protocol"],
            "cohort_bucket": meta["cohort_bucket"],
            "sample_groups": len(group_rows),
            "comparable_rows": len(comparable_rows),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "non_comparable_rows": len(group_rows) - len(comparable_rows),
            "thin_sample_flag": "TRUE" if len(comparable_rows) < 8 else "FALSE",
            "confidence_label": confidence,
            "global_baseline_rate": _round4(global_baseline),
            "provider_baseline_rate": _round4(provider_baseline),
            "family_baseline_rate": _round4(family_baseline),
            "provider_family_baseline_rate": _round4(provider_family_baseline),
            "correct_rate": _round4(correct_rate),
            "delta_vs_global_baseline": _round4(delta_global),
            "delta_vs_provider_baseline": _round4(delta_provider),
            "delta_vs_family_baseline": _round4(delta_family),
            "delta_vs_provider_family_baseline": _round4(delta_provider_family),
            "avg_forecast_direction_concentration": _round4(_safe_mean([_as_float(r.get("forecast_direction_concentration")) for r in group_rows])),
            "avg_pattern_concentration_score": _round4(_safe_mean([_as_float(r.get("pattern_concentration_score")) for r in group_rows])),
            "avg_expression_similarity_mean": _round4(_safe_mean([_as_float(r.get("expression_similarity_mean")) for r in group_rows])),
            "direction_synchrony_mix": _mix_string(group_rows, "direction_synchrony_bucket"),
            "stability_label_mix": _mix_string(group_rows, "stability_label"),
            "reproducibility_label_mix": _mix_string(group_rows, "reproducibility_outcome_label"),
            "recommended_protocol_mix": _mix_string(group_rows, "recommended_protocol"),
            "dominant_forecast_direction_mix": _mix_string(group_rows, "dominant_forecast_direction"),
            "dominant_pattern_mix": _mix_string(group_rows, "dominant_pattern_label"),
            "cohort_mix": _mix_string(group_rows, "cohort_bucket"),
            "importance_mix": _mix_string(group_rows, "importance"),
            "predictability_mix": _mix_string(group_rows, "predictability_bucket"),
            "outcome_result_mix": _mix_string(group_rows, "outcome_result_label"),
            "misleading_stability_count": misleading_count,
            "misleading_stability_rate": _round4(misleading_rate),
            "missing_metric_flag": missing_metric_flag,
            "character_understanding_label": label,
            "interpretation_note": _interpretation_note(label, provider_family_baseline, global_baseline, misleading_rate, correct_rate, delta_provider_family),
            "notes": "; ".join(
                part
                for part in [
                    f"source_rows={len(group_rows)}",
                    f"comparable_rows={len(comparable_rows)}",
                    f"provider_family_key={provider_family_key}",
                    f"slice={slice_type}",
                ]
                if part
            ),
        }
        audit_rows.append(row)
    return audit_rows


def _interpretation_note(
    label: str,
    provider_family_baseline: Optional[float],
    global_baseline: Optional[float],
    misleading_rate: Optional[float],
    correct_rate: Optional[float],
    delta_pf: Optional[float],
) -> str:
    if label == "CHARACTER_STRENGTH":
        return "Slice is materially above provider-family baseline and not dominated by misleading stability."
    if label == "CHARACTER_WEAKNESS":
        return "Slice underperforms its provider-family baseline."
    if label == "CONTEXT_DEPENDENT":
        return "Slice moves differently across controls; signal appears conditional rather than uniform."
    if label == "MISLEADING_STABILITY":
        return "High synchrony/stability is frequently wrong in this slice."
    if label == "NOISY":
        return "Slice is near baseline or mixed without a stable directional edge."
    if label == "THIN_SAMPLE":
        return "Sample depth is too thin for a strong pattern call."
    return "Comparable evidence is missing or incomplete."


def _summary_rows(generated_ts: str, audit_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    global_baseline = _safe_rate(sum(1 for r in audit_rows if r["comparable_rows"] > 0 and r["correct_rate"] is not None and _as_float(r.get("correct_rate")) is not None and _as_float(r.get("correct_rate")) >= 0), 1)
    # recompute properly from underlying rows
    total_comparable = sum(r["comparable_rows"] for r in audit_rows)
    total_correct = sum(r["correct_count"] for r in audit_rows)
    global_baseline = _safe_rate(total_correct, total_comparable)

    section_a_counts = Counter(r["slice_type"] for r in audit_rows)
    label_counts = Counter(r["character_understanding_label"] for r in audit_rows)
    rows.append({
        "generated_ts": generated_ts,
        "section": "A_OVERALL_MAP_SUMMARY",
        "provider": "",
        "event_family": "",
        "slice_type": "",
        "slice_key": "",
        "character_understanding_label": "",
        "confidence_label": "",
        "sample_groups": len(audit_rows),
        "comparable_rows": total_comparable,
        "correct_count": total_correct,
        "wrong_count": sum(r["wrong_count"] for r in audit_rows),
        "correct_rate": _round4(global_baseline),
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "misleading_stability_count": "",
        "misleading_stability_rate": "",
        "thin_sample_flag": "",
        "notes": f"slice_types={dict(section_a_counts)}; labels={dict(label_counts)}; slice_rows_overlap_across_tiers=TRUE",
    })

    # provider summary
    provider_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        provider_groups[row["provider"]].append(row)
    for provider in PROVIDER_ORDER + sorted(set(provider_groups) - set(PROVIDER_ORDER)):
        group_rows = provider_groups.get(provider, [])
        if not group_rows:
            continue
        strength = sum(1 for r in group_rows if r["character_understanding_label"] == "CHARACTER_STRENGTH")
        weakness = sum(1 for r in group_rows if r["character_understanding_label"] == "CHARACTER_WEAKNESS")
        context = sum(1 for r in group_rows if r["character_understanding_label"] == "CONTEXT_DEPENDENT")
        misleading = sum(1 for r in group_rows if r["character_understanding_label"] == "MISLEADING_STABILITY")
        strongest = max(group_rows, key=lambda r: (_as_float(r.get("delta_vs_provider_family_baseline")) or -999.0, _as_float(r.get("correct_rate")) or -999.0, r["slice_key"]), default=None)
        weakest = min(group_rows, key=lambda r: (_as_float(r.get("delta_vs_provider_family_baseline")) or 999.0, _as_float(r.get("correct_rate")) or 999.0, r["slice_key"]), default=None)
        avg_delta = _safe_mean([_as_float(r.get("delta_vs_provider_family_baseline")) for r in group_rows])
        rows.append({
            "generated_ts": generated_ts,
            "section": "B_PROVIDER_CHARACTER_SUMMARY",
            "provider": provider,
            "event_family": "",
            "slice_type": "",
            "slice_key": "",
            "character_understanding_label": "",
            "confidence_label": _confidence_label(sum(r["comparable_rows"] for r in group_rows)),
            "sample_groups": len(group_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
            "correct_count": sum(r["correct_count"] for r in group_rows),
            "wrong_count": sum(r["wrong_count"] for r in group_rows),
            "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
            "provider_family_baseline_rate": "",
            "delta_vs_provider_family_baseline": _round4(avg_delta),
            "misleading_stability_count": misleading,
            "misleading_stability_rate": _round4(_safe_rate(misleading, len(group_rows))),
            "thin_sample_flag": "TRUE" if sum(r["comparable_rows"] for r in group_rows) < 8 else "FALSE",
            "notes": "; ".join(
                part for part in [
                    f"strength={strength}",
                    f"weakness={weakness}",
                    f"context={context}",
                    f"misleading={misleading}",
                    f"strongest={strongest['slice_type']}|{strongest['slice_key']}" if strongest else "",
                    f"weakest={weakest['slice_type']}|{weakest['slice_key']}" if weakest else "",
                ]
                if part
            ),
        })

    # family summary
    family_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        family_groups[row["event_family"]].append(row)
    for family in FAMILY_ORDER + sorted(set(family_groups) - set(FAMILY_ORDER)):
        group_rows = family_groups.get(family, [])
        if not group_rows:
            continue
        strongest = max(group_rows, key=lambda r: (_as_float(r.get("delta_vs_provider_family_baseline")) or -999.0, _as_float(r.get("correct_rate")) or -999.0, r["provider"], r["slice_key"]), default=None)
        weakest = min(group_rows, key=lambda r: (_as_float(r.get("delta_vs_provider_family_baseline")) or 999.0, _as_float(r.get("correct_rate")) or 999.0, r["provider"], r["slice_key"]), default=None)
        misleading = _safe_rate(sum(r["misleading_stability_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
        rows.append({
            "generated_ts": generated_ts,
            "section": "C_FAMILY_CHARACTER_SUMMARY",
            "provider": "",
            "event_family": family,
            "slice_type": "",
            "slice_key": "",
            "character_understanding_label": "",
            "confidence_label": _confidence_label(sum(r["comparable_rows"] for r in group_rows)),
            "sample_groups": len(group_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
            "correct_count": sum(r["correct_count"] for r in group_rows),
            "wrong_count": sum(r["wrong_count"] for r in group_rows),
            "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
            "provider_family_baseline_rate": "",
            "delta_vs_provider_family_baseline": "",
            "misleading_stability_count": sum(r["misleading_stability_count"] for r in group_rows),
            "misleading_stability_rate": _round4(misleading),
            "thin_sample_flag": "TRUE" if sum(r["comparable_rows"] for r in group_rows) < 8 else "FALSE",
            "notes": "; ".join(
                part for part in [
                    f"providers={len(set(r['provider'] for r in group_rows))}",
                    f"strongest={strongest['provider']}|{strongest['slice_type']}|{strongest['slice_key']}" if strongest else "",
                    f"weakest={weakest['provider']}|{weakest['slice_type']}|{weakest['slice_key']}" if weakest else "",
                ]
                if part
            ),
        })

    # direction synchrony summary
    ds_rows = [r for r in audit_rows if r["slice_type"] == "provider_event_family_direction_synchrony"]
    for row in sorted(ds_rows, key=lambda r: (r["provider"], r["event_family"], r["slice_key"])):
        dir_bucket = _upper(row.get("direction_synchrony_bucket"))
        if dir_bucket not in {"HIGH", "VERY_HIGH"}:
            continue
        note = "helps" if (_as_float(row.get("delta_vs_provider_family_baseline")) or 0.0) >= 0.08 and (_as_float(row.get("misleading_stability_rate")) or 0.0) < 0.40 else "misleads"
        rows.append({
            "generated_ts": generated_ts,
            "section": "D_DIRECTION_SYNCHRONY_CHARACTER_SUMMARY",
            "provider": row["provider"],
            "event_family": row["event_family"],
            "slice_type": row["slice_type"],
            "slice_key": row["slice_key"],
            "character_understanding_label": row["character_understanding_label"],
            "confidence_label": row["confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "notes": f"direction_synchrony={dir_bucket}; {note}",
        })

    # stability summary
    stable_rows = [r for r in audit_rows if r["slice_type"] == "provider_event_family_stability"]
    for row in sorted(stable_rows, key=lambda r: (r["provider"], r["event_family"], r["slice_key"])):
        note = "aligns" if row["character_understanding_label"] in {"CHARACTER_STRENGTH", "CONTEXT_DEPENDENT"} else "does_not_help"
        rows.append({
            "generated_ts": generated_ts,
            "section": "E_STABILITY_CHARACTER_SUMMARY",
            "provider": row["provider"],
            "event_family": row["event_family"],
            "slice_type": row["slice_type"],
            "slice_key": row["slice_key"],
            "character_understanding_label": row["character_understanding_label"],
            "confidence_label": row["confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "notes": f"stability_label={row['stability_label']}; {note}",
        })

    # candidate strength map
    candidate_strength = [
        r for r in audit_rows
        if r["comparable_rows"] >= 8 and (_as_float(r.get("delta_vs_provider_family_baseline")) or 0.0) >= 0.08 and r["character_understanding_label"] in {"CHARACTER_STRENGTH", "CONTEXT_DEPENDENT"}
    ]
    candidate_strength.sort(
        key=lambda r: (
            -(_as_float(r.get("delta_vs_provider_family_baseline")) or -999.0),
            -(_as_float(r.get("correct_rate")) or -999.0),
            -r["comparable_rows"],
            r["provider"],
            r["event_family"],
            r["slice_type"],
        )
    )
    for row in candidate_strength[:30]:
        rows.append({
            "generated_ts": generated_ts,
            "section": "F_CANDIDATE_STRENGTH_MAP",
            "provider": row["provider"],
            "event_family": row["event_family"],
            "slice_type": row["slice_type"],
            "slice_key": row["slice_key"],
            "character_understanding_label": row["character_understanding_label"],
            "confidence_label": row["confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "notes": "candidate_strength",
        })

    candidate_weakness = [
        r for r in audit_rows
        if r["comparable_rows"] >= 8 and (_as_float(r.get("delta_vs_provider_family_baseline")) or 0.0) <= -0.08 and r["character_understanding_label"] in {"CHARACTER_WEAKNESS", "MISLEADING_STABILITY", "NOISY"}
    ]
    candidate_weakness.sort(
        key=lambda r: (
            _as_float(r.get("delta_vs_provider_family_baseline")) or 999.0,
            _as_float(r.get("correct_rate")) or 999.0,
            -r["comparable_rows"],
            r["provider"],
            r["event_family"],
            r["slice_type"],
        )
    )
    for row in candidate_weakness[:30]:
        rows.append({
            "generated_ts": generated_ts,
            "section": "G_CANDIDATE_WEAKNESS_MAP",
            "provider": row["provider"],
            "event_family": row["event_family"],
            "slice_type": row["slice_type"],
            "slice_key": row["slice_key"],
            "character_understanding_label": row["character_understanding_label"],
            "confidence_label": row["confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "notes": "candidate_weakness",
        })

    misleading_rows = [
        r for r in audit_rows
        if (_as_float(r["misleading_stability_rate"]) or 0.0) >= 0.40
    ]
    misleading_rows.sort(
        key=lambda r: (
            -(_as_float(r.get("misleading_stability_rate")) or -999.0),
            _as_float(r.get("correct_rate")) or 999.0,
            -r["comparable_rows"],
            r["provider"],
            r["event_family"],
            r["slice_type"],
        )
    )
    for row in misleading_rows[:30]:
        rows.append({
            "generated_ts": generated_ts,
            "section": "H_MISLEADING_STABILITY_MAP",
            "provider": row["provider"],
            "event_family": row["event_family"],
            "slice_type": row["slice_type"],
            "slice_key": row["slice_key"],
            "character_understanding_label": row["character_understanding_label"],
            "confidence_label": row["confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "notes": "misleading_stability",
        })

    # final interpretation row
    strength_count = label_counts.get("CHARACTER_STRENGTH", 0)
    weakness_count = label_counts.get("CHARACTER_WEAKNESS", 0)
    context_count = label_counts.get("CONTEXT_DEPENDENT", 0)
    noisy_count = label_counts.get("NOISY", 0)
    misleading_count = label_counts.get("MISLEADING_STABILITY", 0)
    thin_count = label_counts.get("THIN_SAMPLE", 0)
    total_slices = len(audit_rows)
    if total_comparable < 100:
        final_label = "INSUFFICIENT_DATA"
    elif strength_count >= 8 and weakness_count >= 4 and context_count >= 4 and noisy_count <= (strength_count + weakness_count):
        final_label = "CHARACTER_PATTERNS_CLEAR"
    elif strength_count + weakness_count + context_count >= 10 and (strength_count + weakness_count) >= 4:
        final_label = "CHARACTER_PATTERNS_PARTIAL"
    elif noisy_count + misleading_count > strength_count + weakness_count:
        final_label = "CHARACTER_PATTERNS_NOISY"
    elif strength_count + weakness_count < 5:
        final_label = "CHARACTER_PATTERNS_WEAK"
    else:
        final_label = "CHARACTER_PATTERNS_PARTIAL"
    rows.append({
        "generated_ts": generated_ts,
        "section": "I_FINAL_INTERPRETATION",
        "provider": "",
        "event_family": "",
        "slice_type": "",
        "slice_key": "",
        "character_understanding_label": final_label,
        "confidence_label": _confidence_label(total_comparable),
        "sample_groups": total_slices,
        "comparable_rows": total_comparable,
        "correct_count": total_correct,
        "wrong_count": sum(r["wrong_count"] for r in audit_rows),
        "correct_rate": _round4(global_baseline),
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "misleading_stability_count": misleading_count,
        "misleading_stability_rate": _round4(_safe_rate(sum(r["misleading_stability_count"] for r in audit_rows), total_comparable)),
        "thin_sample_flag": "TRUE" if thin_count > 0 else "FALSE",
        "notes": f"strength={strength_count}; weakness={weakness_count}; context={context_count}; noisy={noisy_count}; misleading={misleading_count}; thin={thin_count}",
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


def build_character_understanding_pattern_map() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    base_rows = _join_base_rows(sources)
    map_rows = _build_map_rows(generated_ts, base_rows)
    summary_rows = _summary_rows(generated_ts, map_rows)
    registry_result = _upsert_registry_rows(service)

    map_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAP_SHEET, MAP_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAP_SHEET, map_headers, map_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    final_row = next((r for r in summary_rows if r.get("section") == "I_FINAL_INTERPRETATION"), {})

    return {
        "generated_ts": generated_ts,
        "sample_groups": len(base_rows),
        "slice_count": len(map_rows),
        "providers_represented": sorted({r["provider"] for r in base_rows}),
        "families_represented": sorted({r["event_family"] for r in base_rows}),
        "cohorts_represented": sorted({r["cohort_bucket"] for r in base_rows}),
        "comparable_rows": sum(1 for r in base_rows if r["has_actual"]),
        "overall_result_label": final_row.get("character_understanding_label", ""),
        "registry": registry_result,
    }


if __name__ == "__main__":
    print(build_character_understanding_pattern_map())
