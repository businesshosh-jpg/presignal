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


OUTPUT_CANDIDATE_SHEET = "Character_Learning_Hypothesis_Candidates"
OUTPUT_SUMMARY_SHEET = "Character_Learning_Hypothesis_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "CHARACTER_LEARNING_HYPOTHESIS_CANDIDATES",
        "physical_sheet_name": OUTPUT_CANDIDATE_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v0",
        "notes": "Derived-only character learning hypothesis candidate filter",
    },
    {
        "logical_sheet_id": "CHARACTER_LEARNING_HYPOTHESIS_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v0",
        "notes": "Derived-only character learning hypothesis summary",
    },
]

CANDIDATE_HEADERS = [
    "generated_ts",
    "candidate_id",
    "source_slice_type",
    "source_slice_key",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "source_character_understanding_label",
    "source_confidence_label",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "provider_family_baseline_rate",
    "delta_vs_provider_family_baseline",
    "provider_baseline_rate",
    "delta_vs_provider_baseline",
    "family_baseline_rate",
    "delta_vs_family_baseline",
    "misleading_stability_count",
    "misleading_stability_rate",
    "thin_sample_flag",
    "candidate_label",
    "rejection_label",
    "learning_priority",
    "evidence_score",
    "evidence_strength_label",
    "fragility_label",
    "direction_synchrony_summary",
    "stability_summary",
    "cohort_summary",
    "importance_summary",
    "predictability_summary",
    "protocol_summary",
    "interpretation_note",
    "learning_approved",
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
    "candidate_id",
    "source_slice_type",
    "source_slice_key",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "source_character_understanding_label",
    "source_confidence_label",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "provider_family_baseline_rate",
    "delta_vs_provider_family_baseline",
    "provider_baseline_rate",
    "delta_vs_provider_baseline",
    "family_baseline_rate",
    "delta_vs_family_baseline",
    "misleading_stability_count",
    "misleading_stability_rate",
    "thin_sample_flag",
    "candidate_label",
    "rejection_label",
    "learning_priority",
    "evidence_score",
    "evidence_strength_label",
    "fragility_label",
    "direction_synchrony_summary",
    "stability_summary",
    "cohort_summary",
    "importance_summary",
    "predictability_summary",
    "protocol_summary",
    "candidate_count",
    "strength_candidate_count",
    "weakness_candidate_count",
    "misleading_candidate_count",
    "context_candidate_count",
    "rejected_count",
    "highest_priority_candidate",
    "highest_priority_score",
    "candidate_label_counts",
    "learning_priority_counts",
    "rejection_label_counts",
    "source_final_label",
    "source_summary_note",
    "likely_dependency_source",
    "overall_result_label",
    "overall_result_reason",
    "interpretation_note",
    "notes",
]

SLICE_DIMENSION_MAP = {
    "provider_event_family": ("event_family", "family"),
    "provider_event_family_predictability": ("predictability_bucket", "predictability"),
    "provider_event_family_direction_synchrony": ("direction_synchrony_bucket", "direction_synchrony"),
    "provider_event_family_stability": ("stability_label", "stability"),
    "provider_event_family_importance": ("importance", "importance"),
    "provider_event_family_cohort": ("cohort_bucket", "cohort"),
    "provider_event_family_protocol": ("recommended_protocol", "protocol"),
}

CATEGORY_ORDER = [
    ("LEARNING_CANDIDATE_STRENGTH", "B_STRENGTH_CANDIDATE_SUMMARY"),
    ("LEARNING_CANDIDATE_WEAKNESS", "C_WEAKNESS_CANDIDATE_SUMMARY"),
    ("LEARNING_CANDIDATE_MISLEADING_STABILITY", "D_MISLEADING_STABILITY_SUMMARY"),
    ("LEARNING_CANDIDATE_CONTEXT_DEPENDENT", "E_CONTEXT_DEPENDENT_SUMMARY"),
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


def _slug(value: Any) -> str:
    raw = _norm(value).lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_") or "missing"


def _mix_string(rows: Sequence[Dict[str, Any]], field: str) -> str:
    counter = Counter(_norm(r.get(field)) or "MISSING" for r in rows)
    return "|".join(f"{key}:{count}" for key, count in counter.most_common())


def _get_sheet_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "pattern_map": _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Character_Understanding_Pattern_Map"),
        "pattern_summary": _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Character_Understanding_Pattern_Summary"),
    }


def _slice_condition(slice_type: str, slice_key: str, row: Dict[str, Any]) -> Tuple[str, str]:
    if slice_type not in SLICE_DIMENSION_MAP:
        return ("condition", _norm(slice_key).split("|")[-1] if _norm(slice_key) else "")
    condition_dimension, _ = SLICE_DIMENSION_MAP[slice_type]
    parts = [_norm(part) for part in _norm(slice_key).split("|")]
    if slice_type == "provider_event_family":
        return condition_dimension, parts[-1] if parts else _norm(row.get("event_family"))
    return condition_dimension, parts[-1] if parts else _norm(row.get(condition_dimension))


def _candidate_type(row: Dict[str, Any]) -> Tuple[str, str]:
    label = _upper(row.get("character_understanding_label"))
    comparable_rows = int(float(row.get("comparable_rows") or 0))
    delta_pf = _as_float(row.get("delta_vs_provider_family_baseline")) or 0.0
    delta_provider = _as_float(row.get("delta_vs_provider_baseline")) or 0.0
    delta_family = _as_float(row.get("delta_vs_family_baseline")) or 0.0
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0
    correct_rate = _as_float(row.get("correct_rate")) or 0.0
    provider_family_baseline = _as_float(row.get("provider_family_baseline_rate"))
    provider_baseline = _as_float(row.get("provider_baseline_rate"))
    family_baseline = _as_float(row.get("family_baseline_rate"))

    if comparable_rows < 8:
        return "", "DO_NOT_LEARN_THIN_SAMPLE"
    if label == "INSUFFICIENT_DATA":
        return "", "DO_NOT_LEARN_INSUFFICIENT_DATA"

    if label == "CHARACTER_STRENGTH" and delta_pf >= 0.08 and correct_rate >= (provider_family_baseline or correct_rate):
        return "LEARNING_CANDIDATE_STRENGTH", ""

    if label == "CHARACTER_WEAKNESS" and delta_pf <= -0.08:
        return "LEARNING_CANDIDATE_WEAKNESS", ""

    if delta_pf <= -0.10 and comparable_rows >= 12 and misleading_rate < 0.40:
        return "LEARNING_CANDIDATE_WEAKNESS", ""

    if label == "MISLEADING_STABILITY" and misleading_rate >= 0.50 and comparable_rows >= 8:
        return "LEARNING_CANDIDATE_MISLEADING_STABILITY", ""

    if label == "CONTEXT_DEPENDENT" and comparable_rows >= 8 and (
        abs(delta_pf) >= 0.05 or abs(delta_provider) >= 0.05 or abs(delta_family) >= 0.05
    ):
        return "LEARNING_CANDIDATE_CONTEXT_DEPENDENT", ""

    if label == "NOISY":
        return "", "DO_NOT_LEARN_NOISY"

    if abs(delta_pf) >= 0.08 and comparable_rows >= 12:
        return "LEARNING_CANDIDATE_CONTEXT_DEPENDENT", ""

    if label == "MISLEADING_STABILITY" and misleading_rate >= 0.40 and comparable_rows >= 12 and correct_rate <= 0.45:
        return "LEARNING_CANDIDATE_MISLEADING_STABILITY", ""

    return "", "DO_NOT_LEARN_LOW_EFFECT_SIZE"


def _evidence_score(row: Dict[str, Any], candidate_label: str) -> float:
    comparable_rows = int(float(row.get("comparable_rows") or 0))
    correct_rate = _as_float(row.get("correct_rate")) or 0.0
    provider_family_baseline = _as_float(row.get("provider_family_baseline_rate"))
    provider_baseline = _as_float(row.get("provider_baseline_rate"))
    family_baseline = _as_float(row.get("family_baseline_rate"))
    delta_pf = _as_float(row.get("delta_vs_provider_family_baseline")) or 0.0
    delta_provider = _as_float(row.get("delta_vs_provider_baseline")) or 0.0
    delta_family = _as_float(row.get("delta_vs_family_baseline")) or 0.0
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0

    depth_score = min(comparable_rows / 20.0, 1.0) * 28.0
    if candidate_label == "LEARNING_CANDIDATE_STRENGTH":
        effect_score = min(max(delta_pf, 0.0) / 0.16, 1.0) * 34.0
    elif candidate_label == "LEARNING_CANDIDATE_WEAKNESS":
        effect_score = min(max(-delta_pf, 0.0) / 0.16, 1.0) * 34.0
    elif candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        effect_score = min(misleading_rate / 0.60, 1.0) * 28.0 + min(max(-delta_pf, 0.0) / 0.12, 1.0) * 12.0
    elif candidate_label == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT":
        effect_score = min(max(abs(delta_pf), abs(delta_provider), abs(delta_family)) / 0.10, 1.0) * 32.0
    else:
        effect_score = min(abs(delta_pf) / 0.10, 1.0) * 20.0

    if candidate_label == "LEARNING_CANDIDATE_STRENGTH" and provider_family_baseline is not None and correct_rate >= provider_family_baseline:
        effect_score += 4.0
    if candidate_label == "LEARNING_CANDIDATE_WEAKNESS" and provider_family_baseline is not None and correct_rate <= provider_family_baseline:
        effect_score += 4.0
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        effect_score += min(misleading_rate / 0.40, 1.0) * 8.0

    slice_type = _norm(row.get("source_slice_type"))
    if slice_type == "provider_event_family":
        generality_score = 14.0
        fragility_penalty = 0.0
    elif slice_type in {"provider_event_family_predictability", "provider_event_family_importance"}:
        generality_score = 11.0
        fragility_penalty = 4.0
    elif slice_type in {"provider_event_family_direction_synchrony", "provider_event_family_stability"}:
        generality_score = 8.0
        fragility_penalty = 7.0
    else:
        generality_score = 6.0
        fragility_penalty = 9.0

    if misleading_rate >= 0.40:
        fragility_penalty += 4.0
    if comparable_rows < 12:
        fragility_penalty += 4.0

    confidence_bonus = 6.0 if _confidence_label(comparable_rows) == "HIGHER_CONFIDENCE" else 3.0 if _confidence_label(comparable_rows) == "MEDIUM_CONFIDENCE" else 1.0

    score = depth_score + effect_score + generality_score + confidence_bonus - fragility_penalty
    return max(0.0, min(100.0, score))


def _evidence_strength_label(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    if score >= 45:
        return "LOW"
    return "VERY_LOW"


def _fragility_label(row: Dict[str, Any]) -> str:
    slice_type = _norm(row.get("source_slice_type"))
    comparable_rows = int(float(row.get("comparable_rows") or 0))
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0
    score = 0
    if slice_type == "provider_event_family":
        score += 0
    elif slice_type in {"provider_event_family_predictability", "provider_event_family_importance"}:
        score += 1
    elif slice_type in {"provider_event_family_direction_synchrony", "provider_event_family_stability"}:
        score += 2
    else:
        score += 3
    if comparable_rows < 12:
        score += 1
    if misleading_rate >= 0.40:
        score += 1
    if score <= 1:
        return "LOW"
    if score == 2:
        return "MODERATE"
    if score == 3:
        return "HIGH"
    return "VERY_HIGH"


def _learning_priority(score: float, candidate_label: str) -> str:
    if not candidate_label:
        return "REJECT"
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    if score >= 45:
        return "LOW"
    return "REJECT"


def _interpretation_note(row: Dict[str, Any], candidate_label: str, rejection_label: str) -> str:
    source_label = _upper(row.get("character_understanding_label"))
    if candidate_label == "LEARNING_CANDIDATE_STRENGTH":
        return "Materially above provider-family baseline and worth later validation."
    if candidate_label == "LEARNING_CANDIDATE_WEAKNESS":
        return "Consistently below provider-family baseline and worth later falsification."
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        return "High synchrony looks confident but is often wrong."
    if candidate_label == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT":
        return "Condition-sensitive slice with meaningful delta under at least one control."
    if rejection_label == "DO_NOT_LEARN_THIN_SAMPLE":
        return "Sample depth is too thin for learning-layer use."
    if rejection_label == "DO_NOT_LEARN_NOISY":
        return "Slice is noisy and does not support a stable hypothesis."
    if rejection_label == "DO_NOT_LEARN_INSUFFICIENT_DATA":
        return "Source slice is missing the minimum evidence needed."
    if rejection_label == "DO_NOT_LEARN_LOW_EFFECT_SIZE":
        return "Effect size is too small to justify future learning."
    if rejection_label == "DO_NOT_LEARN_DUPLICATE_OR_REDUNDANT":
        return "Slice is redundant relative to a stronger nearby candidate."
    return f"Source label {source_label} does not justify a learning hypothesis."


def _source_summary_note(pattern_summary_rows: Sequence[Dict[str, Any]]) -> str:
    final_row = next((r for r in pattern_summary_rows if _upper(r.get("section")) == "I_FINAL_INTERPRETATION"), {})
    return _norm(final_row.get("notes"))


def _source_final_label(pattern_summary_rows: Sequence[Dict[str, Any]]) -> str:
    final_row = next((r for r in pattern_summary_rows if _upper(r.get("section")) == "I_FINAL_INTERPRETATION"), {})
    return _norm(final_row.get("character_understanding_label"))


def _build_candidate_rows(
    generated_ts: str,
    pattern_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in pattern_rows:
        slice_type = _norm(row.get("slice_type"))
        slice_key = _norm(row.get("slice_key"))
        condition_dimension, condition_value = _slice_condition(slice_type, slice_key, row)
        candidate_label, rejection_label = _candidate_type(row)
        score = _evidence_score(row, candidate_label)
        if not rejection_label:
            priority = _learning_priority(score, candidate_label)
        else:
            priority = "REJECT"

        if not candidate_label and not rejection_label:
            rejection_label = "DO_NOT_LEARN_LOW_EFFECT_SIZE"

        if candidate_label and score < 45:
            candidate_label = ""
            rejection_label = rejection_label or "DO_NOT_LEARN_LOW_EFFECT_SIZE"
            priority = "REJECT"

        row_out = {
            "generated_ts": generated_ts,
            "candidate_id": f"cand_{_slug(slice_type)}_{_slug(slice_key)}",
            "source_slice_type": slice_type,
            "source_slice_key": slice_key,
            "provider": _norm(row.get("provider")),
            "event_family": _norm(row.get("event_family")),
            "condition_dimension": condition_dimension,
            "condition_value": condition_value,
            "source_character_understanding_label": _norm(row.get("character_understanding_label")),
            "source_confidence_label": _norm(row.get("confidence_label")),
            "sample_groups": int(float(row.get("sample_groups") or 0)),
            "comparable_rows": int(float(row.get("comparable_rows") or 0)),
            "correct_count": int(float(row.get("correct_count") or 0)),
            "wrong_count": int(float(row.get("wrong_count") or 0)),
            "correct_rate": _round4(_as_float(row.get("correct_rate"))),
            "provider_family_baseline_rate": _round4(_as_float(row.get("provider_family_baseline_rate"))),
            "delta_vs_provider_family_baseline": _round4(_as_float(row.get("delta_vs_provider_family_baseline"))),
            "provider_baseline_rate": _round4(_as_float(row.get("provider_baseline_rate"))),
            "delta_vs_provider_baseline": _round4(_as_float(row.get("delta_vs_provider_baseline"))),
            "family_baseline_rate": _round4(_as_float(row.get("family_baseline_rate"))),
            "delta_vs_family_baseline": _round4(_as_float(row.get("delta_vs_family_baseline"))),
            "misleading_stability_count": int(float(row.get("misleading_stability_count") or 0)),
            "misleading_stability_rate": _round4(_as_float(row.get("misleading_stability_rate"))),
            "thin_sample_flag": _norm(row.get("thin_sample_flag")) or ("TRUE" if int(float(row.get("comparable_rows") or 0)) < 8 else "FALSE"),
            "candidate_label": candidate_label,
            "rejection_label": rejection_label,
            "learning_priority": priority,
            "evidence_score": _round4(score),
            "evidence_strength_label": _evidence_strength_label(score),
            "fragility_label": _fragility_label(row),
            "direction_synchrony_summary": _norm(row.get("direction_synchrony_mix")),
            "stability_summary": _norm(row.get("stability_label_mix")),
            "cohort_summary": _norm(row.get("cohort_mix")),
            "importance_summary": _norm(row.get("importance_mix")),
            "predictability_summary": _norm(row.get("predictability_mix")),
            "protocol_summary": _norm(row.get("recommended_protocol_mix")),
            "interpretation_note": _interpretation_note(row, candidate_label, rejection_label),
            "learning_approved": "FALSE",
            "routing_approved": "FALSE",
            "weighting_approved": "FALSE",
            "calibration_approved": "FALSE",
            "production_approved": "FALSE",
            "notes": "; ".join(
                part
                for part in [
                    f"source_label={_norm(row.get('character_understanding_label'))}",
                    f"candidate={candidate_label or rejection_label}",
                    f"score={_round4(score)}",
                    f"slice={slice_type}",
                ]
                if part
            ),
        }
        rows.append(row_out)
    return rows


def _top_rows(rows: Sequence[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    return list(rows[:limit])


def _candidate_sort_key(row: Dict[str, Any], mode: str) -> Tuple[Any, ...]:
    score = _as_float(row.get("evidence_score")) or 0.0
    comparable = int(float(row.get("comparable_rows") or 0))
    delta_pf = _as_float(row.get("delta_vs_provider_family_baseline")) or 0.0
    misleading = _as_float(row.get("misleading_stability_rate")) or 0.0
    if mode == "strength":
        return (-score, -delta_pf, -comparable, row.get("provider", ""), row.get("event_family", ""), row.get("source_slice_type", ""))
    if mode == "weakness":
        return (-score, delta_pf, -comparable, row.get("provider", ""), row.get("event_family", ""), row.get("source_slice_type", ""))
    if mode == "misleading":
        return (-score, -misleading, -comparable, row.get("provider", ""), row.get("event_family", ""), row.get("source_slice_type", ""))
    if mode == "context":
        return (-score, -abs(delta_pf), -comparable, row.get("provider", ""), row.get("event_family", ""), row.get("source_slice_type", ""))
    return (-score, row.get("provider", ""), row.get("event_family", ""), row.get("source_slice_type", ""))


def _provider_summary_rows(candidates: Sequence[Dict[str, Any]], generated_ts: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[row["provider"]].append(row)
    for provider in PROVIDER_ORDER + sorted(set(grouped) - set(PROVIDER_ORDER)):
        group_rows = grouped.get(provider, [])
        if not group_rows:
            continue
        strength = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_STRENGTH")
        weakness = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_WEAKNESS")
        misleading = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY")
        context = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT")
        rejected = sum(1 for r in group_rows if r["rejection_label"])
        best = max(
            group_rows,
            key=lambda r: (
                {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "REJECT": 0}.get(r["learning_priority"], 0),
                _as_float(r.get("evidence_score")) or 0.0,
                _as_float(r.get("correct_rate")) or 0.0,
                r["candidate_id"],
            ),
        )
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "F_PROVIDER_CANDIDATE_SUMMARY",
                "rank": "",
                "candidate_id": "",
                "source_slice_type": "",
                "source_slice_key": "",
                "provider": provider,
                "event_family": "",
                "condition_dimension": "",
                "condition_value": "",
                "source_character_understanding_label": "",
                "source_confidence_label": "",
                "sample_groups": "",
                "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
                "correct_count": sum(r["correct_count"] for r in group_rows),
                "wrong_count": sum(r["wrong_count"] for r in group_rows),
                "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "provider_family_baseline_rate": "",
                "delta_vs_provider_family_baseline": _round4(_safe_mean([_as_float(r.get("delta_vs_provider_family_baseline")) for r in group_rows])),
                "provider_baseline_rate": "",
                "delta_vs_provider_baseline": "",
                "family_baseline_rate": "",
                "delta_vs_family_baseline": "",
                "misleading_stability_count": sum(r["misleading_stability_count"] for r in group_rows),
                "misleading_stability_rate": _round4(_safe_rate(sum(r["misleading_stability_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "thin_sample_flag": "TRUE" if sum(r["comparable_rows"] for r in group_rows) < 8 else "FALSE",
                "candidate_label": "",
                "rejection_label": "",
                "learning_priority": "",
                "evidence_score": "",
                "evidence_strength_label": "",
                "fragility_label": "",
                "direction_synchrony_summary": "",
                "stability_summary": "",
                "cohort_summary": "",
                "importance_summary": "",
                "predictability_summary": "",
                "protocol_summary": "",
                "candidate_count": len(group_rows),
                "strength_candidate_count": strength,
                "weakness_candidate_count": weakness,
                "misleading_candidate_count": misleading,
                "context_candidate_count": context,
                "rejected_count": rejected,
                "highest_priority_candidate": f"{best['candidate_id']}|{best['candidate_label'] or best['rejection_label']}",
                "highest_priority_score": _round4(_as_float(best.get("evidence_score"))),
                "candidate_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["candidate_label"] or "REJECT" for r in group_rows).most_common()),
                "learning_priority_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["learning_priority"] or "REJECT" for r in group_rows).most_common()),
                "rejection_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["rejection_label"] or "NONE" for r in group_rows).most_common()),
                "source_final_label": "",
                "source_summary_note": "",
                "likely_dependency_source": "",
                "overall_result_label": "",
                "overall_result_reason": "",
                "interpretation_note": "",
                "notes": "; ".join(
                    part
                    for part in [
                        f"strength={strength}",
                        f"weakness={weakness}",
                        f"misleading={misleading}",
                        f"context={context}",
                        f"rejected={rejected}",
                        f"best={best['candidate_id']}",
                    ]
                    if part
                ),
            }
        )
    return rows


def _family_summary_rows(candidates: Sequence[Dict[str, Any]], generated_ts: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        grouped[row["event_family"]].append(row)
    for family in FAMILY_ORDER + sorted(set(grouped) - set(FAMILY_ORDER)):
        group_rows = grouped.get(family, [])
        if not group_rows:
            continue
        strength = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_STRENGTH")
        weakness = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_WEAKNESS")
        misleading = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_MISLEADING_STABILITY")
        context = sum(1 for r in group_rows if r["candidate_label"] == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT")
        rejected = sum(1 for r in group_rows if r["rejection_label"])
        best = max(
            group_rows,
            key=lambda r: (
                {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "REJECT": 0}.get(r["learning_priority"], 0),
                _as_float(r.get("evidence_score")) or 0.0,
                _as_float(r.get("correct_rate")) or 0.0,
                r["candidate_id"],
            ),
        )
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "G_FAMILY_CANDIDATE_SUMMARY",
                "rank": "",
                "candidate_id": "",
                "source_slice_type": "",
                "source_slice_key": "",
                "provider": "",
                "event_family": family,
                "condition_dimension": "",
                "condition_value": "",
                "source_character_understanding_label": "",
                "source_confidence_label": "",
                "sample_groups": "",
                "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
                "correct_count": sum(r["correct_count"] for r in group_rows),
                "wrong_count": sum(r["wrong_count"] for r in group_rows),
                "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "provider_family_baseline_rate": "",
                "delta_vs_provider_family_baseline": "",
                "provider_baseline_rate": "",
                "delta_vs_provider_baseline": "",
                "family_baseline_rate": "",
                "delta_vs_family_baseline": "",
                "misleading_stability_count": sum(r["misleading_stability_count"] for r in group_rows),
                "misleading_stability_rate": _round4(_safe_rate(sum(r["misleading_stability_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "thin_sample_flag": "TRUE" if sum(r["comparable_rows"] for r in group_rows) < 8 else "FALSE",
                "candidate_label": "",
                "rejection_label": "",
                "learning_priority": "",
                "evidence_score": "",
                "evidence_strength_label": "",
                "fragility_label": "",
                "direction_synchrony_summary": "",
                "stability_summary": "",
                "cohort_summary": "",
                "importance_summary": "",
                "predictability_summary": "",
                "protocol_summary": "",
                "candidate_count": len(group_rows),
                "strength_candidate_count": strength,
                "weakness_candidate_count": weakness,
                "misleading_candidate_count": misleading,
                "context_candidate_count": context,
                "rejected_count": rejected,
                "highest_priority_candidate": f"{best['candidate_id']}|{best['candidate_label'] or best['rejection_label']}",
                "highest_priority_score": _round4(_as_float(best.get("evidence_score"))),
                "candidate_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["candidate_label"] or "REJECT" for r in group_rows).most_common()),
                "learning_priority_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["learning_priority"] or "REJECT" for r in group_rows).most_common()),
                "rejection_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(r["rejection_label"] or "NONE" for r in group_rows).most_common()),
                "source_final_label": "",
                "source_summary_note": "",
                "likely_dependency_source": "",
                "overall_result_label": "",
                "overall_result_reason": "",
                "interpretation_note": "",
                "notes": "; ".join(
                    part
                    for part in [
                        f"candidate_count={len(group_rows)}",
                        f"strength={strength}",
                        f"weakness={weakness}",
                        f"misleading={misleading}",
                        f"context={context}",
                        f"best={best['candidate_id']}",
                    ]
                    if part
                ),
            }
        )
    return rows


def _overall_summary_row(
    generated_ts: str,
    pattern_rows: Sequence[Dict[str, Any]],
    summary_rows: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    candidate_rows = [r for r in candidates if _norm(r.get("candidate_label"))]
    rejected_rows = [r for r in candidates if _norm(r.get("rejection_label"))]
    candidate_counts = Counter(r["candidate_label"] for r in candidate_rows)
    priority_counts = Counter(r["learning_priority"] for r in candidate_rows)
    rejection_counts = Counter(r["rejection_label"] for r in rejected_rows)
    strength = candidate_counts.get("LEARNING_CANDIDATE_STRENGTH", 0)
    weakness = candidate_counts.get("LEARNING_CANDIDATE_WEAKNESS", 0)
    misleading = candidate_counts.get("LEARNING_CANDIDATE_MISLEADING_STABILITY", 0)
    context = candidate_counts.get("LEARNING_CANDIDATE_CONTEXT_DEPENDENT", 0)
    high_priority = priority_counts.get("HIGH", 0)
    source_final_label = _source_final_label(summary_rows)
    source_summary_note = _source_summary_note(summary_rows)

    candidate_count = len(candidate_rows)
    rejected_count = len(rejected_rows)
    if candidate_count == 0:
        overall_result_label = "INSUFFICIENT_DATA_FOR_LEARNING"
        overall_result_reason = "No learning candidates were retained after filtering."
    elif candidate_count <= 40:
        overall_result_label = "LIMITED_CANDIDATES_ONLY"
        overall_result_reason = "A compact candidate set survives filtering, but the source map remains mostly rejected or fragile."
    elif high_priority >= 4 and candidate_count >= 12:
        overall_result_label = "LEARNING_CANDIDATES_READY_FOR_VALIDATION"
        overall_result_reason = "Multiple high-priority candidate hypotheses survived evidence filtering."
    elif rejected_count >= candidate_count * 3:
        overall_result_label = "MOSTLY_REJECTED_NOISY"
        overall_result_reason = "The source map is dominated by thin, noisy, or low-effect slices."
    else:
        overall_result_label = "UNDERSTANDING_LAYER_NEEDS_MORE_DATA"
        overall_result_reason = "Candidate extraction worked, but the retained set is still too fragile for broad learning."

    best = max(
        candidate_rows or rejected_rows or [{}],
        key=lambda r: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "REJECT": 0}.get(_norm(r.get("learning_priority")) or "REJECT", 0),
            _as_float(r.get("evidence_score")) or 0.0,
            _as_float(r.get("correct_rate")) or 0.0,
            _norm(r.get("candidate_id")),
        ),
    )

    return {
        "generated_ts": generated_ts,
        "section": "A_OVERALL_CANDIDATE_SUMMARY",
        "rank": "",
        "candidate_id": "",
        "source_slice_type": "",
        "source_slice_key": "",
        "provider": "",
        "event_family": "",
        "condition_dimension": "",
        "condition_value": "",
        "source_character_understanding_label": "",
        "source_confidence_label": "",
        "sample_groups": len(pattern_rows),
        "comparable_rows": sum(int(float(r.get("comparable_rows") or 0)) for r in pattern_rows),
        "correct_count": sum(int(float(r.get("correct_count") or 0)) for r in pattern_rows),
        "wrong_count": sum(int(float(r.get("wrong_count") or 0)) for r in pattern_rows),
        "correct_rate": _round4(
            _safe_rate(
                sum(int(float(r.get("correct_count") or 0)) for r in pattern_rows),
                sum(int(float(r.get("comparable_rows") or 0)) for r in pattern_rows),
            )
        ),
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "provider_baseline_rate": "",
        "delta_vs_provider_baseline": "",
        "family_baseline_rate": "",
        "delta_vs_family_baseline": "",
        "misleading_stability_count": sum(int(float(r.get("misleading_stability_count") or 0)) for r in pattern_rows),
        "misleading_stability_rate": _round4(
            _safe_rate(
                sum(int(float(r.get("misleading_stability_count") or 0)) for r in pattern_rows),
                sum(int(float(r.get("comparable_rows") or 0)) for r in pattern_rows),
            )
        ),
        "thin_sample_flag": "TRUE" if sum(int(float(r.get("comparable_rows") or 0)) for r in pattern_rows) < 8 else "FALSE",
        "candidate_label": "",
        "rejection_label": "",
        "learning_priority": "",
        "evidence_score": "",
        "evidence_strength_label": "",
        "fragility_label": "",
        "direction_synchrony_summary": "",
        "stability_summary": "",
        "cohort_summary": "",
        "importance_summary": "",
        "predictability_summary": "",
        "protocol_summary": "",
        "candidate_count": candidate_count,
        "strength_candidate_count": strength,
        "weakness_candidate_count": weakness,
        "misleading_candidate_count": misleading,
        "context_candidate_count": context,
        "rejected_count": rejected_count,
        "highest_priority_candidate": _norm(best.get("candidate_id")),
        "highest_priority_score": _round4(_as_float(best.get("evidence_score"))),
        "candidate_label_counts": "|".join(f"{k}:{v}" for k, v in candidate_counts.most_common()),
        "learning_priority_counts": "|".join(f"{k}:{v}" for k, v in priority_counts.most_common()),
        "rejection_label_counts": "|".join(f"{k}:{v}" for k, v in rejection_counts.most_common()),
        "source_final_label": source_final_label,
        "source_summary_note": source_summary_note,
        "likely_dependency_source": "",
        "overall_result_label": overall_result_label,
        "overall_result_reason": overall_result_reason,
        "interpretation_note": (
            "Evidence filter retained only a narrow set of candidate hypotheses from a largely noisy slice map."
            if overall_result_label != "LEARNING_CANDIDATES_READY_FOR_VALIDATION"
            else "Several higher-priority candidates survived filtering and are ready for later validation."
        ),
        "notes": "; ".join(
            part
            for part in [
                f"source_final_label={source_final_label}",
                f"candidate_count={candidate_count}",
                f"rejected_count={rejected_count}",
                f"high_priority={high_priority}",
            ]
            if part
        ),
    }


def _summary_category_rows(
    candidates: Sequence[Dict[str, Any]],
    category: str,
    section: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    filtered = [r for r in candidates if r["candidate_label"] == category]
    filtered.sort(key=lambda r: _candidate_sort_key(r, "strength" if category == "LEARNING_CANDIDATE_STRENGTH" else "weakness" if category == "LEARNING_CANDIDATE_WEAKNESS" else "misleading" if category == "LEARNING_CANDIDATE_MISLEADING_STABILITY" else "context"))
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(_top_rows(filtered, limit), start=1):
        out.append({
            "generated_ts": row["generated_ts"],
            "section": section,
            "rank": idx,
            "candidate_id": row["candidate_id"],
            "source_slice_type": row["source_slice_type"],
            "source_slice_key": row["source_slice_key"],
            "provider": row["provider"],
            "event_family": row["event_family"],
            "condition_dimension": row["condition_dimension"],
            "condition_value": row["condition_value"],
            "source_character_understanding_label": row["source_character_understanding_label"],
            "source_confidence_label": row["source_confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "provider_baseline_rate": row["provider_baseline_rate"],
            "delta_vs_provider_baseline": row["delta_vs_provider_baseline"],
            "family_baseline_rate": row["family_baseline_rate"],
            "delta_vs_family_baseline": row["delta_vs_family_baseline"],
            "misleading_stability_count": row["misleading_stability_count"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "thin_sample_flag": row["thin_sample_flag"],
            "candidate_label": row["candidate_label"],
            "rejection_label": row["rejection_label"],
            "learning_priority": row["learning_priority"],
            "evidence_score": row["evidence_score"],
            "evidence_strength_label": row["evidence_strength_label"],
            "fragility_label": row["fragility_label"],
            "direction_synchrony_summary": row["direction_synchrony_summary"],
            "stability_summary": row["stability_summary"],
            "cohort_summary": row["cohort_summary"],
            "importance_summary": row["importance_summary"],
            "predictability_summary": row["predictability_summary"],
            "protocol_summary": row["protocol_summary"],
            "candidate_count": "",
            "strength_candidate_count": "",
            "weakness_candidate_count": "",
            "misleading_candidate_count": "",
            "context_candidate_count": "",
            "rejected_count": "",
            "highest_priority_candidate": "",
            "highest_priority_score": "",
            "candidate_label_counts": "",
            "learning_priority_counts": "",
            "rejection_label_counts": "",
            "source_final_label": "",
            "source_summary_note": "",
            "likely_dependency_source": _likely_dependency_source(row["source_slice_type"]),
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": row["interpretation_note"],
            "notes": row["notes"],
        })
    return out


def _likely_dependency_source(slice_type: str) -> str:
    if slice_type == "provider_event_family":
        return "family_level"
    if slice_type.endswith("_predictability"):
        return "predictability"
    if slice_type.endswith("_direction_synchrony"):
        return "direction_synchrony"
    if slice_type.endswith("_stability"):
        return "stability"
    if slice_type.endswith("_importance"):
        return "importance"
    if slice_type.endswith("_cohort"):
        return "cohort"
    if slice_type.endswith("_protocol"):
        return "protocol"
    return "unknown"


def _build_summary_rows(
    generated_ts: str,
    pattern_rows: Sequence[Dict[str, Any]],
    summary_rows: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.append(_overall_summary_row(generated_ts, pattern_rows, summary_rows, candidates))

    for category, section in CATEGORY_ORDER:
        rows.extend(_summary_category_rows(candidates, category, section, limit=20))

    rows.extend(_provider_summary_rows(candidates, generated_ts))
    rows.extend(_family_summary_rows(candidates, generated_ts))

    final_row = _overall_summary_row(generated_ts, pattern_rows, summary_rows, candidates)
    rows.append({
        **final_row,
        "section": "H_FINAL_INTERPRETATION",
        "rank": "",
        "candidate_id": "",
        "source_slice_type": "",
        "source_slice_key": "",
        "provider": "",
        "event_family": "",
        "condition_dimension": "",
        "condition_value": "",
        "source_character_understanding_label": "",
        "source_confidence_label": "",
        "sample_groups": "",
        "comparable_rows": "",
        "correct_count": "",
        "wrong_count": "",
        "correct_rate": "",
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "provider_baseline_rate": "",
        "delta_vs_provider_baseline": "",
        "family_baseline_rate": "",
        "delta_vs_family_baseline": "",
        "misleading_stability_count": "",
        "misleading_stability_rate": "",
        "thin_sample_flag": "",
        "candidate_label": "",
        "rejection_label": "",
        "learning_priority": "",
        "evidence_score": "",
        "evidence_strength_label": "",
        "fragility_label": "",
        "direction_synchrony_summary": "",
        "stability_summary": "",
        "cohort_summary": "",
        "importance_summary": "",
        "predictability_summary": "",
        "protocol_summary": "",
        "candidate_count": "",
        "strength_candidate_count": "",
        "weakness_candidate_count": "",
        "misleading_candidate_count": "",
        "context_candidate_count": "",
        "rejected_count": "",
        "highest_priority_candidate": "",
        "highest_priority_score": "",
        "candidate_label_counts": "",
        "learning_priority_counts": "",
        "rejection_label_counts": "",
        "source_final_label": _source_final_label(summary_rows),
        "source_summary_note": _source_summary_note(summary_rows),
        "likely_dependency_source": "",
        "overall_result_label": final_row["overall_result_label"],
        "overall_result_reason": final_row["overall_result_reason"],
        "interpretation_note": final_row["interpretation_note"],
        "notes": final_row["notes"],
    })
    return rows


def _upsert_registry_rows(service) -> Dict[str, Any]:
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    if not rows:
        raise RuntimeError("Sheet_Registry is missing or empty.")
    existing_headers = _get_sheet_headers(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET) or list(REGISTRY_HEADERS)
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


def build_character_learning_hypothesis_candidates() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    pattern_rows = sources["pattern_map"]
    summary_rows = sources["pattern_summary"]
    candidate_rows = _build_candidate_rows(generated_ts, pattern_rows)
    summary_output_rows = _build_summary_rows(generated_ts, pattern_rows, summary_rows, candidate_rows)
    registry_result = _upsert_registry_rows(service)

    candidate_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CANDIDATE_SHEET, CANDIDATE_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CANDIDATE_SHEET, candidate_headers, candidate_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_output_rows)

    candidate_count = sum(1 for row in candidate_rows if _norm(row.get("candidate_label")))
    rejected_count = sum(1 for row in candidate_rows if _norm(row.get("rejection_label")))
    high_priority_count = sum(1 for row in candidate_rows if _norm(row.get("learning_priority")) == "HIGH")
    final_row = next((row for row in summary_output_rows if _norm(row.get("section")) == "H_FINAL_INTERPRETATION"), {})
    return {
        "generated_ts": generated_ts,
        "source_slices_read": len(pattern_rows),
        "candidates_created": candidate_count,
        "rejected_slices": rejected_count,
        "providers_represented": sorted({row["provider"] for row in pattern_rows if _norm(row.get("provider"))}),
        "families_represented": sorted({row["event_family"] for row in pattern_rows if _norm(row.get("event_family"))}),
        "overall_result_label": final_row.get("overall_result_label", ""),
        "registry": registry_result,
        "high_priority_candidates": high_priority_count,
    }


if __name__ == "__main__":
    print(build_character_learning_hypothesis_candidates())
