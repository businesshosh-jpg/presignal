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
from automation.build_character_learning_hypothesis_candidates import (
    _as_float,
    _confidence_label,
    _norm,
    _safe_mean,
    _safe_rate,
    _source_final_label,
    _source_summary_note,
    _upper,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_QUEUE_SHEET = "Character_Learning_Validation_Queue"
OUTPUT_SUMMARY_SHEET = "Character_Learning_Validation_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "CHARACTER_LEARNING_VALIDATION_QUEUE",
        "physical_sheet_name": OUTPUT_QUEUE_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v0B",
        "notes": "Derived-only character learning validation queue",
    },
    {
        "logical_sheet_id": "CHARACTER_LEARNING_VALIDATION_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "PROVIDER_CHARACTER",
        "lifecycle_state": "ACTIVE",
        "owner_module": "provider_character",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Character Learning Layer v0B",
        "notes": "Derived-only character learning validation summary",
    },
]

QUEUE_HEADERS = [
    "generated_ts",
    "queue_id",
    "candidate_id",
    "source_slice_type",
    "source_slice_key",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "candidate_label",
    "learning_priority",
    "evidence_score",
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
    "direction_synchrony_summary",
    "stability_summary",
    "cohort_summary",
    "importance_summary",
    "predictability_summary",
    "protocol_summary",
    "sample_adequacy_label",
    "effect_size_label",
    "misleading_stability_severity_label",
    "repetition_label",
    "cohort_fragility_label",
    "provider_family_fragility_label",
    "contradiction_label",
    "interpretability_label",
    "validation_score",
    "validation_strength_label",
    "validation_queue_label",
    "validation_reason",
    "next_validation_action",
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
    "queue_id",
    "candidate_id",
    "source_slice_type",
    "source_slice_key",
    "provider",
    "event_family",
    "condition_dimension",
    "condition_value",
    "candidate_label",
    "learning_priority",
    "source_confidence_label",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "provider_family_baseline_rate",
    "delta_vs_provider_family_baseline",
    "misleading_stability_rate",
    "sample_adequacy_label",
    "effect_size_label",
    "misleading_stability_severity_label",
    "repetition_label",
    "cohort_fragility_label",
    "provider_family_fragility_label",
    "contradiction_label",
    "interpretability_label",
    "validation_score",
    "validation_strength_label",
    "validation_queue_label",
    "next_validation_action",
    "queue_count",
    "validate_first_count",
    "validate_later_count",
    "observe_only_count",
    "reject_after_filter_count",
    "candidate_label_counts",
    "validation_strength_label_counts",
    "strongest_queue_candidate",
    "strongest_queue_score",
    "dominant_risk_type",
    "source_final_label",
    "source_summary_note",
    "overall_result_label",
    "overall_result_reason",
    "interpretation_note",
    "notes",
]

REGISTRY_SHEET = REGISTRY_SHEET
PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]
FAMILY_ORDER = ["central_bank", "energy", "growth", "housing", "inflation", "labor", "manufacturing", "other"]


def _slug(value: Any) -> str:
    raw = _norm(value).lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_") or "missing"


def _get_sheet_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _parse_mix_counts(value: Any) -> Dict[str, int]:
    raw = _norm(value)
    if not raw:
        return {}
    out: Dict[str, int] = {}
    for part in raw.split("|"):
        if ":" not in part:
            continue
        key, count = part.split(":", 1)
        try:
            out[key] = int(float(count))
        except Exception:
            continue
    return out


def _dominant_share(value: Any) -> Optional[float]:
    counts = _parse_mix_counts(value)
    total = sum(counts.values())
    if total <= 0:
        return None
    return max(counts.values()) / total


def _sample_adequacy_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "STRONG_SAMPLE_SUPPORT"
    if comparable_rows >= 12:
        return "MEDIUM_SAMPLE_SUPPORT"
    if comparable_rows >= 8:
        return "WEAK_BUT_USABLE"
    return "THIN"


def _effect_size_label(row: Dict[str, Any]) -> str:
    candidate_label = _upper(row.get("candidate_label"))
    delta_pf = _as_float(row.get("delta_vs_provider_family_baseline")) or 0.0
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0
    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        if misleading_rate >= 0.50:
            return "STRONG_RISK"
        if misleading_rate >= 0.40:
            return "MODERATE_RISK"
        return "WEAK_RISK"
    if candidate_label == "LEARNING_CANDIDATE_STRENGTH":
        if delta_pf >= 0.10:
            return "STRONG_POSITIVE"
        if delta_pf >= 0.06:
            return "MODERATE_POSITIVE"
        return "WEAK_OR_LOW_EFFECT"
    if candidate_label == "LEARNING_CANDIDATE_WEAKNESS":
        if delta_pf <= -0.10:
            return "STRONG_NEGATIVE_OR_RISK"
        if delta_pf <= -0.06:
            return "MODERATE_NEGATIVE_OR_RISK"
        return "WEAK_OR_LOW_EFFECT"
    if candidate_label == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT":
        mag = max(
            abs(delta_pf),
            abs(_as_float(row.get("delta_vs_provider_baseline")) or 0.0),
            abs(_as_float(row.get("delta_vs_family_baseline")) or 0.0),
        )
        if mag >= 0.10:
            return "STRONG_CONTEXT_EFFECT"
        if mag >= 0.06:
            return "MODERATE_CONTEXT_EFFECT"
        return "WEAK_OR_LOW_EFFECT"
    return "WEAK_OR_LOW_EFFECT"


def _misleading_severity_label(row: Dict[str, Any]) -> str:
    if _upper(row.get("candidate_label")) != "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        return "NOT_APPLICABLE"
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0
    if misleading_rate >= 0.50:
        return "STRONG_RISK"
    if misleading_rate >= 0.40:
        return "MODERATE_RISK"
    return "WEAK_RISK"


def _repetition_label(row: Dict[str, Any], candidate_groups: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> str:
    key = (_norm(row.get("provider")), _norm(row.get("event_family")))
    related = candidate_groups.get(key, [])
    tier_count = len({r.get("source_slice_type") for r in related if _norm(r.get("source_slice_type"))})
    if tier_count >= 3:
        return "REPEATED_ACROSS_TIERS"
    if tier_count == 1:
        return "SINGLE_TIER_ONLY"
    if tier_count == 0:
        return "UNKNOWN_REPETITION"
    return "UNKNOWN_REPETITION"


def _cohort_fragility_label(row: Dict[str, Any]) -> str:
    share = _dominant_share(row.get("cohort_summary"))
    if share is None:
        return "UNKNOWN_COHORT_FRAGILITY"
    if share >= 0.80:
        return "HIGH_COHORT_FRAGILITY"
    if share >= 0.60:
        return "MODERATE_COHORT_FRAGILITY"
    return "LOW_COHORT_FRAGILITY"


def _provider_family_fragility_label(row: Dict[str, Any]) -> str:
    slice_type = _norm(row.get("source_slice_type"))
    if slice_type == "provider_event_family":
        return "BROAD_ENOUGH"
    if slice_type in {"provider_event_family_predictability", "provider_event_family_importance"}:
        return "NARROW_BUT_INTERPRETABLE"
    if slice_type in {
        "provider_event_family_direction_synchrony",
        "provider_event_family_stability",
        "provider_event_family_cohort",
        "provider_event_family_protocol",
    }:
        return "OVERLY_NARROW"
    return "UNKNOWN_SCOPE"


def _contradiction_label(row: Dict[str, Any]) -> str:
    candidate_label = _upper(row.get("candidate_label"))
    delta_pf = _as_float(row.get("delta_vs_provider_family_baseline")) or 0.0
    delta_provider = _as_float(row.get("delta_vs_provider_baseline")) or 0.0
    delta_family = _as_float(row.get("delta_vs_family_baseline")) or 0.0
    provider_family_rate = _as_float(row.get("provider_family_baseline_rate"))
    correct_rate = _as_float(row.get("correct_rate")) or 0.0
    misleading_rate = _as_float(row.get("misleading_stability_rate")) or 0.0

    if candidate_label == "LEARNING_CANDIDATE_STRENGTH":
        if delta_pf >= 0.08 and not (delta_provider <= -0.08 and delta_family <= -0.08):
            return "NO_MAJOR_CONTRADICTION"
        if delta_pf >= 0.06:
            return "PARTIAL_CONTRADICTION"
        return "STRONG_CONTRADICTION"

    if candidate_label == "LEARNING_CANDIDATE_WEAKNESS":
        if delta_pf <= -0.08:
            return "NO_MAJOR_CONTRADICTION"
        if delta_pf <= -0.06:
            return "PARTIAL_CONTRADICTION"
        return "STRONG_CONTRADICTION"

    if candidate_label == "LEARNING_CANDIDATE_MISLEADING_STABILITY":
        if misleading_rate >= 0.50 and (provider_family_rate is None or correct_rate <= provider_family_rate + 0.05):
            return "NO_MAJOR_CONTRADICTION"
        if misleading_rate >= 0.40:
            return "PARTIAL_CONTRADICTION"
        return "STRONG_CONTRADICTION"

    if candidate_label == "LEARNING_CANDIDATE_CONTEXT_DEPENDENT":
        if abs(delta_pf) >= 0.05 or abs(delta_provider) >= 0.05 or abs(delta_family) >= 0.05:
            if (
                (delta_pf >= 0 and delta_provider >= 0)
                or (delta_pf >= 0 and delta_family >= 0)
                or (delta_pf <= 0 and delta_provider <= 0)
                or (delta_pf <= 0 and delta_family <= 0)
            ):
                return "PARTIAL_CONTRADICTION"
            return "STRONG_CONTRADICTION"
        return "INSUFFICIENT_CONTEXT"

    return "INSUFFICIENT_CONTEXT"


def _interpretability_label(sample_label: str, effect_label: str, repetition_label: str, contradiction_label: str) -> str:
    if contradiction_label == "STRONG_CONTRADICTION":
        return "UNCLEAR"
    if sample_label in {"STRONG_SAMPLE_SUPPORT", "MEDIUM_SAMPLE_SUPPORT"} and effect_label not in {"WEAK_OR_LOW_EFFECT"}:
        if repetition_label == "REPEATED_ACROSS_TIERS":
            return "INTERPRETABLE"
        return "PARTIAL"
    if sample_label == "WEAK_BUT_USABLE" and effect_label != "WEAK_OR_LOW_EFFECT":
        return "PARTIAL"
    if contradiction_label == "INSUFFICIENT_CONTEXT":
        return "UNCLEAR"
    return "PARTIAL"


def _validation_score(
    row: Dict[str, Any],
    sample_label: str,
    effect_label: str,
    repetition_label: str,
    cohort_fragility_label: str,
    provider_family_fragility_label: str,
    contradiction_label: str,
    interpretability_label: str,
) -> float:
    evidence_score = _as_float(row.get("evidence_score")) or 0.0
    base = min(max(evidence_score, 0.0), 100.0) / 100.0 * 0.45

    sample_component = {
        "STRONG_SAMPLE_SUPPORT": 0.15,
        "MEDIUM_SAMPLE_SUPPORT": 0.10,
        "WEAK_BUT_USABLE": 0.05,
        "THIN": 0.0,
    }.get(sample_label, 0.0)

    effect_component = 0.0
    if effect_label in {"STRONG_POSITIVE", "STRONG_NEGATIVE_OR_RISK", "STRONG_RISK", "STRONG_CONTEXT_EFFECT"}:
        effect_component = 0.25
    elif effect_label in {"MODERATE_POSITIVE", "MODERATE_NEGATIVE_OR_RISK", "MODERATE_RISK", "MODERATE_CONTEXT_EFFECT"}:
        effect_component = 0.18
    elif effect_label == "WEAK_RISK":
        effect_component = 0.10
    else:
        effect_component = 0.08

    repetition_component = {
        "REPEATED_ACROSS_TIERS": 0.15,
        "SINGLE_TIER_ONLY": 0.05,
        "UNKNOWN_REPETITION": 0.02,
    }.get(repetition_label, 0.02)

    fragility_component = {
        "BROAD_ENOUGH": 0.10,
        "NARROW_BUT_INTERPRETABLE": 0.06,
        "OVERLY_NARROW": 0.02,
        "UNKNOWN_SCOPE": 0.04,
    }.get(provider_family_fragility_label, 0.04)
    if cohort_fragility_label == "HIGH_COHORT_FRAGILITY":
        fragility_component = min(fragility_component, 0.03)
    elif cohort_fragility_label == "MODERATE_COHORT_FRAGILITY":
        fragility_component = min(fragility_component, 0.06)

    contradiction_component = {
        "NO_MAJOR_CONTRADICTION": 0.10,
        "PARTIAL_CONTRADICTION": 0.05,
        "STRONG_CONTRADICTION": 0.0,
        "INSUFFICIENT_CONTEXT": 0.03,
    }.get(contradiction_label, 0.03)

    interpretability_component = {
        "INTERPRETABLE": 0.05,
        "PARTIAL": 0.03,
        "UNCLEAR": 0.01,
        "LOW": 0.0,
    }.get(interpretability_label, 0.03)

    score = base + sample_component + effect_component + repetition_component + fragility_component + contradiction_component + interpretability_component
    return max(0.0, min(1.0, score))


def _validation_strength_label(score: float) -> str:
    if score >= 0.90:
        return "VALIDATION_STRONG"
    if score >= 0.80:
        return "VALIDATION_MODERATE"
    if score >= 0.74:
        return "VALIDATION_WEAK"
    return "VALIDATION_REJECT"


def _validation_queue_label(score: float, sample_label: str, contradiction_label: str) -> str:
    if contradiction_label == "STRONG_CONTRADICTION" or score < 0.74:
        return "REJECT_AFTER_FILTER"
    if score >= 0.90 and sample_label != "THIN":
        return "VALIDATE_FIRST"
    if score >= 0.80:
        return "VALIDATE_LATER"
    return "OBSERVE_ONLY"


def _next_action(queue_label: str) -> str:
    return {
        "VALIDATE_FIRST": "REPLAY_EXPANSION_TEST",
        "VALIDATE_LATER": "SAMPLE_EXPANSION_REQUIRED",
        "OBSERVE_ONLY": "MONITOR_ONLY",
        "REJECT_AFTER_FILTER": "REJECT_NO_ACTION",
    }.get(queue_label, "REJECT_NO_ACTION")


def _queue_reason(row: Dict[str, Any], queue_label: str, sample_label: str, effect_label: str, contradiction_label: str, repetition_label: str) -> str:
    if queue_label == "VALIDATE_FIRST":
        return "Strong evidence, enough sample support, and acceptable fragility for near-term validation."
    if queue_label == "VALIDATE_LATER":
        return "Interesting candidate but still needs more support before replay or expansion."
    if queue_label == "OBSERVE_ONLY":
        return "Retain for monitoring, but the second-gate evidence is not strong enough yet."
    if contradiction_label == "STRONG_CONTRADICTION":
        return "The candidate conflicts too strongly with broader baselines."
    if sample_label == "THIN":
        return "Second-gate review rejects the candidate on sample adequacy."
    if effect_label == "WEAK_OR_LOW_EFFECT" and repetition_label != "REPEATED_ACROSS_TIERS":
        return "Effect size is too small and does not repeat across related tiers."
    return "The candidate does not clear the validation gate."


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "candidates": _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Character_Learning_Hypothesis_Candidates"),
        "summary": _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Character_Learning_Hypothesis_Summary"),
    }


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


def _build_queue_rows(generated_ts: str, candidates: Sequence[Dict[str, Any]], summary_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidate_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if _norm(row.get("candidate_label")):
            candidate_groups[(_norm(row.get("provider")), _norm(row.get("event_family")))].append(row)

    queue_rows: List[Dict[str, Any]] = []
    for row in candidates:
        if not _norm(row.get("candidate_label")):
            continue

        sample_label = _sample_adequacy_label(int(float(row.get("comparable_rows") or 0)))
        effect_label = _effect_size_label(row)
        misleading_label = _misleading_severity_label(row)
        repetition_label = _repetition_label(row, candidate_groups)
        cohort_fragility_label = _cohort_fragility_label(row)
        provider_family_fragility_label = _provider_family_fragility_label(row)
        contradiction_label = _contradiction_label(row)
        interpretability_label = _interpretability_label(sample_label, effect_label, repetition_label, contradiction_label)
        validation_score = _validation_score(
            row,
            sample_label,
            effect_label,
            repetition_label,
            cohort_fragility_label,
            provider_family_fragility_label,
            contradiction_label,
            interpretability_label,
        )
        validation_strength_label = _validation_strength_label(validation_score)
        validation_queue_label = _validation_queue_label(validation_score, sample_label, contradiction_label)
        reason = _queue_reason(row, validation_queue_label, sample_label, effect_label, contradiction_label, repetition_label)
        queue_rows.append(
            {
                "generated_ts": generated_ts,
                "queue_id": f"queue_{_slug(row.get('candidate_id'))}",
                "candidate_id": _norm(row.get("candidate_id")),
                "source_slice_type": _norm(row.get("source_slice_type")),
                "source_slice_key": _norm(row.get("source_slice_key")),
                "provider": _norm(row.get("provider")),
                "event_family": _norm(row.get("event_family")),
                "condition_dimension": _norm(row.get("condition_dimension")),
                "condition_value": _norm(row.get("condition_value")),
                "candidate_label": _norm(row.get("candidate_label")),
                "learning_priority": _norm(row.get("learning_priority")),
                "evidence_score": _round4(_as_float(row.get("evidence_score"))),
                "source_confidence_label": _norm(row.get("source_confidence_label")),
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
                "direction_synchrony_summary": _norm(row.get("direction_synchrony_summary")),
                "stability_summary": _norm(row.get("stability_summary")),
                "cohort_summary": _norm(row.get("cohort_summary")),
                "importance_summary": _norm(row.get("importance_summary")),
                "predictability_summary": _norm(row.get("predictability_summary")),
                "protocol_summary": _norm(row.get("protocol_summary")),
                "sample_adequacy_label": sample_label,
                "effect_size_label": effect_label,
                "misleading_stability_severity_label": misleading_label,
                "repetition_label": repetition_label,
                "cohort_fragility_label": cohort_fragility_label,
                "provider_family_fragility_label": provider_family_fragility_label,
                "contradiction_label": contradiction_label,
                "interpretability_label": interpretability_label,
                "validation_score": _round4(validation_score),
                "validation_strength_label": validation_strength_label,
                "validation_queue_label": validation_queue_label,
                "validation_reason": reason,
                "next_validation_action": _next_action(validation_queue_label),
                "learning_approved": "FALSE",
                "routing_approved": "FALSE",
                "weighting_approved": "FALSE",
                "calibration_approved": "FALSE",
                "production_approved": "FALSE",
                "notes": "; ".join(
                    part
                    for part in [
                        f"source_label={_norm(row.get('candidate_label'))}",
                        f"queue={validation_queue_label}",
                        f"score={_round4(validation_score)}",
                        f"repetition={repetition_label}",
                    ]
                    if part
                ),
            }
        )
    return queue_rows


def _queue_sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        -(_as_float(row.get("validation_score")) or 0.0),
        -(_as_float(row.get("evidence_score")) or 0.0),
        -int(float(row.get("comparable_rows") or 0)),
        _norm(row.get("provider")),
        _norm(row.get("event_family")),
        _norm(row.get("source_slice_type")),
    )


def _aggregate_row(
    generated_ts: str,
    section: str,
    rows: Sequence[Dict[str, Any]],
    queue_rows: Sequence[Dict[str, Any]],
    extra_notes: str = "",
) -> Dict[str, Any]:
    candidate_count = len(rows)
    validate_first_count = sum(1 for r in rows if _norm(r.get("validation_queue_label")) == "VALIDATE_FIRST")
    validate_later_count = sum(1 for r in rows if _norm(r.get("validation_queue_label")) == "VALIDATE_LATER")
    observe_only_count = sum(1 for r in rows if _norm(r.get("validation_queue_label")) == "OBSERVE_ONLY")
    reject_count = sum(1 for r in rows if _norm(r.get("validation_queue_label")) == "REJECT_AFTER_FILTER")
    candidate_label_counts = "|".join(f"{k}:{v}" for k, v in Counter(_norm(r.get("candidate_label")) for r in rows).most_common())
    validation_strength_label_counts = "|".join(f"{k}:{v}" for k, v in Counter(_norm(r.get("validation_strength_label")) for r in rows).most_common())
    strongest = max(
        rows or [{}],
        key=lambda r: (
            _as_float(r.get("validation_score")) or 0.0,
            _as_float(r.get("evidence_score")) or 0.0,
            int(float(r.get("comparable_rows") or 0)),
            _norm(r.get("candidate_id")),
        ),
    )
    dominant_risk_type = Counter(_norm(r.get("candidate_label")) for r in rows).most_common(1)
    dominant_risk_type = dominant_risk_type[0][0] if dominant_risk_type else ""
    return {
        "generated_ts": generated_ts,
        "section": section,
        "rank": "",
        "queue_id": "",
        "candidate_id": "",
        "source_slice_type": "",
        "source_slice_key": "",
        "provider": "",
        "event_family": "",
        "condition_dimension": "",
        "condition_value": "",
        "candidate_label": "",
        "learning_priority": "",
        "source_confidence_label": "",
        "sample_groups": len(rows),
        "comparable_rows": sum(int(float(r.get("comparable_rows") or 0)) for r in rows),
        "correct_count": sum(int(float(r.get("correct_count") or 0)) for r in rows),
        "wrong_count": sum(int(float(r.get("wrong_count") or 0)) for r in rows),
        "correct_rate": _round4(
            _safe_rate(
                sum(int(float(r.get("correct_count") or 0)) for r in rows),
                sum(int(float(r.get("comparable_rows") or 0)) for r in rows),
            )
        ),
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": _round4(_safe_mean([_as_float(r.get("delta_vs_provider_family_baseline")) for r in rows])),
        "misleading_stability_rate": _round4(_safe_rate(sum(int(float(r.get("misleading_stability_count") or 0)) for r in rows), sum(int(float(r.get("comparable_rows") or 0)) for r in rows))),
        "sample_adequacy_label": "",
        "effect_size_label": "",
        "misleading_stability_severity_label": "",
        "repetition_label": "",
        "cohort_fragility_label": "",
        "provider_family_fragility_label": "",
        "contradiction_label": "",
        "interpretability_label": "",
        "validation_score": "",
        "validation_strength_label": "",
        "validation_queue_label": "",
        "next_validation_action": "",
        "queue_count": candidate_count,
        "validate_first_count": validate_first_count,
        "validate_later_count": validate_later_count,
        "observe_only_count": observe_only_count,
        "reject_after_filter_count": reject_count,
        "candidate_label_counts": candidate_label_counts,
        "validation_strength_label_counts": validation_strength_label_counts,
        "strongest_queue_candidate": _norm(strongest.get("candidate_id")),
        "strongest_queue_score": _round4(_as_float(strongest.get("validation_score"))),
        "dominant_risk_type": dominant_risk_type,
        "source_final_label": _source_final_label(queue_rows and [] or []),
        "source_summary_note": extra_notes,
        "overall_result_label": "",
        "overall_result_reason": "",
        "interpretation_note": "",
        "notes": f"section={section}; {extra_notes}".strip(),
    }


def _build_summary_rows(generated_ts: str, queue_rows: Sequence[Dict[str, Any]], source_candidates: Sequence[Dict[str, Any]], source_summary_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    final_label = ""
    final_reason = ""
    validate_first_count = sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_FIRST")
    validate_later_count = sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_LATER")
    observe_only_count = sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "OBSERVE_ONLY")
    reject_count = sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "REJECT_AFTER_FILTER")

    if validate_first_count >= 3 and validate_later_count >= 3:
        final_label = "VALIDATION_QUEUE_READY"
        final_reason = "Multiple strong queue candidates survive the second gate."
    elif validate_first_count + validate_later_count >= 5:
        final_label = "LIMITED_VALIDATION_QUEUE"
        final_reason = "A narrow but usable validation queue survives the second gate."
    elif observe_only_count >= max(1, len(queue_rows) // 2):
        final_label = "MOSTLY_OBSERVE_ONLY"
        final_reason = "Most retained candidates are better monitored than actively validated."
    elif validate_first_count == 0 and validate_later_count == 0:
        final_label = "NO_VALIDATION_READY_CANDIDATES"
        final_reason = "No retained candidates are strong enough for future replay or expansion."
    else:
        final_label = "INSUFFICIENT_DATA_FOR_VALIDATION"
        final_reason = "Candidate evidence is not deep enough to promote a clear validation queue."

    overall_row = _aggregate_row(
        generated_ts,
        "A_OVERALL_VALIDATION_QUEUE_SUMMARY",
        queue_rows,
        queue_rows,
        extra_notes=f"source_final_label={_source_final_label(source_summary_rows)}; source_summary_note={_source_summary_note(source_summary_rows)}",
    )
    overall_row.update(
        {
            "candidate_id": "",
            "queue_id": "overall",
            "provider": "",
            "event_family": "",
            "sample_groups": len(queue_rows),
            "queue_count": len(queue_rows),
            "candidate_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(_norm(r.get("candidate_label")) for r in queue_rows).most_common()),
            "validation_strength_label_counts": "|".join(f"{k}:{v}" for k, v in Counter(_norm(r.get("validation_strength_label")) for r in queue_rows).most_common()),
            "source_final_label": _source_final_label(source_summary_rows),
            "source_summary_note": _source_summary_note(source_summary_rows),
            "overall_result_label": final_label,
            "overall_result_reason": final_reason,
            "interpretation_note": (
                "The second gate retained a compact but meaningful set of validation candidates."
                if final_label in {"VALIDATION_QUEUE_READY", "LIMITED_VALIDATION_QUEUE"}
                else "Most retained candidates remain observational rather than ready for active validation."
            ),
            "notes": f"source_final_label={_source_final_label(source_summary_rows)}; candidate_count={len(queue_rows)}; validate_first={validate_first_count}; validate_later={validate_later_count}; observe_only={observe_only_count}; reject={reject_count}",
        }
    )
    rows.append(overall_row)

    validate_first = [r for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_FIRST"]
    validate_first.sort(key=_queue_sort_key)
    for idx, row in enumerate(validate_first, start=1):
        rows.append({
            "generated_ts": row["generated_ts"],
            "section": "B_VALIDATE_FIRST_LIST",
            "rank": idx,
            "queue_id": row["queue_id"],
            "candidate_id": row["candidate_id"],
            "source_slice_type": row["source_slice_type"],
            "source_slice_key": row["source_slice_key"],
            "provider": row["provider"],
            "event_family": row["event_family"],
            "condition_dimension": row["condition_dimension"],
            "condition_value": row["condition_value"],
            "candidate_label": row["candidate_label"],
            "learning_priority": row["learning_priority"],
            "source_confidence_label": row["source_confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "sample_adequacy_label": row["sample_adequacy_label"],
            "effect_size_label": row["effect_size_label"],
            "misleading_stability_severity_label": row["misleading_stability_severity_label"],
            "repetition_label": row["repetition_label"],
            "cohort_fragility_label": row["cohort_fragility_label"],
            "provider_family_fragility_label": row["provider_family_fragility_label"],
            "contradiction_label": row["contradiction_label"],
            "interpretability_label": row["interpretability_label"],
            "validation_score": row["validation_score"],
            "validation_strength_label": row["validation_strength_label"],
            "validation_queue_label": row["validation_queue_label"],
            "next_validation_action": row["next_validation_action"],
            "queue_count": "",
            "validate_first_count": "",
            "validate_later_count": "",
            "observe_only_count": "",
            "reject_after_filter_count": "",
            "candidate_label_counts": "",
            "validation_strength_label_counts": "",
            "strongest_queue_candidate": "",
            "strongest_queue_score": "",
            "dominant_risk_type": "",
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": row["validation_reason"],
            "notes": row["notes"],
        })

    validate_later = [r for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_LATER"]
    validate_later.sort(key=_queue_sort_key)
    for idx, row in enumerate(validate_later, start=1):
        rows.append({
            "generated_ts": row["generated_ts"],
            "section": "C_VALIDATE_LATER_LIST",
            "rank": idx,
            "queue_id": row["queue_id"],
            "candidate_id": row["candidate_id"],
            "source_slice_type": row["source_slice_type"],
            "source_slice_key": row["source_slice_key"],
            "provider": row["provider"],
            "event_family": row["event_family"],
            "condition_dimension": row["condition_dimension"],
            "condition_value": row["condition_value"],
            "candidate_label": row["candidate_label"],
            "learning_priority": row["learning_priority"],
            "source_confidence_label": row["source_confidence_label"],
            "sample_groups": row["sample_groups"],
            "comparable_rows": row["comparable_rows"],
            "correct_count": row["correct_count"],
            "wrong_count": row["wrong_count"],
            "correct_rate": row["correct_rate"],
            "provider_family_baseline_rate": row["provider_family_baseline_rate"],
            "delta_vs_provider_family_baseline": row["delta_vs_provider_family_baseline"],
            "misleading_stability_rate": row["misleading_stability_rate"],
            "sample_adequacy_label": row["sample_adequacy_label"],
            "effect_size_label": row["effect_size_label"],
            "misleading_stability_severity_label": row["misleading_stability_severity_label"],
            "repetition_label": row["repetition_label"],
            "cohort_fragility_label": row["cohort_fragility_label"],
            "provider_family_fragility_label": row["provider_family_fragility_label"],
            "contradiction_label": row["contradiction_label"],
            "interpretability_label": row["interpretability_label"],
            "validation_score": row["validation_score"],
            "validation_strength_label": row["validation_strength_label"],
            "validation_queue_label": row["validation_queue_label"],
            "next_validation_action": row["next_validation_action"],
            "queue_count": "",
            "validate_first_count": "",
            "validate_later_count": "",
            "observe_only_count": "",
            "reject_after_filter_count": "",
            "candidate_label_counts": "",
            "validation_strength_label_counts": "",
            "strongest_queue_candidate": "",
            "strongest_queue_score": "",
            "dominant_risk_type": "",
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": row["validation_reason"],
            "notes": row["notes"],
        })

    # Misleading stability summary
    misleading = [r for r in queue_rows if _norm(r.get("candidate_label")) == "LEARNING_CANDIDATE_MISLEADING_STABILITY"]
    if misleading:
        strongest = max(misleading, key=_queue_sort_key)
        rows.append({
            **_aggregate_row(generated_ts, "D_MISLEADING_STABILITY_QUEUE", misleading, queue_rows, extra_notes="misleading_stability"),
            "queue_id": "misleading_stability_summary",
            "candidate_id": "",
            "provider": "",
            "event_family": "",
            "strongest_queue_candidate": strongest["candidate_id"],
            "strongest_queue_score": strongest["validation_score"],
            "dominant_risk_type": "MISLEADING_STABILITY",
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": (
                "Misleading stability remains the dominant risk category and is the main reason to keep some candidates under review."
            ),
            "notes": f"misleading_count={len(misleading)}; strongest={strongest['candidate_id']}",
        })

    positive = [r for r in queue_rows if _norm(r.get("candidate_label")) in {"LEARNING_CANDIDATE_STRENGTH", "LEARNING_CANDIDATE_CONTEXT_DEPENDENT"}]
    if positive:
        strongest_pos = max(positive, key=_queue_sort_key)
        rows.append({
            **_aggregate_row(generated_ts, "E_STRENGTH_POSITIVE_QUEUE", positive, queue_rows, extra_notes="positive_candidates"),
            "queue_id": "positive_candidate_summary",
            "candidate_id": "",
            "provider": "",
            "event_family": "",
            "strongest_queue_candidate": strongest_pos["candidate_id"],
            "strongest_queue_score": strongest_pos["validation_score"],
            "dominant_risk_type": "POSITIVE_CANDIDATES",
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": "The retained positive candidates are narrow but worth preserving for later replay or expansion tests.",
            "notes": f"positive_count={len(positive)}; strongest={strongest_pos['candidate_id']}",
        })

    provider_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    family_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in queue_rows:
        provider_groups[_norm(row.get("provider"))].append(row)
        family_groups[_norm(row.get("event_family"))].append(row)

    for provider in PROVIDER_ORDER + sorted(set(provider_groups) - set(PROVIDER_ORDER)):
        group_rows = provider_groups.get(provider, [])
        if not group_rows:
            continue
        strongest = max(group_rows, key=_queue_sort_key)
        rows.append({
            **_aggregate_row(generated_ts, "F_PROVIDER_QUEUE_SUMMARY", group_rows, queue_rows, extra_notes=f"provider={provider}"),
            "queue_id": f"provider_{_slug(provider)}",
            "provider": provider,
            "dominant_risk_type": Counter(_norm(r.get("candidate_label")) for r in group_rows).most_common(1)[0][0],
            "strongest_queue_candidate": strongest["candidate_id"],
            "strongest_queue_score": strongest["validation_score"],
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": f"Provider {provider} retains a limited queue with its strongest candidate at the top.",
            "notes": f"provider={provider}; strongest={strongest['candidate_id']}",
        })

    for family in FAMILY_ORDER + sorted(set(family_groups) - set(FAMILY_ORDER)):
        group_rows = family_groups.get(family, [])
        if not group_rows:
            continue
        strongest = max(group_rows, key=_queue_sort_key)
        rows.append({
            **_aggregate_row(generated_ts, "G_FAMILY_QUEUE_SUMMARY", group_rows, queue_rows, extra_notes=f"family={family}"),
            "queue_id": f"family_{_slug(family)}",
            "event_family": family,
            "dominant_risk_type": Counter(_norm(r.get("candidate_label")) for r in group_rows).most_common(1)[0][0],
            "strongest_queue_candidate": strongest["candidate_id"],
            "strongest_queue_score": strongest["validation_score"],
            "source_final_label": "",
            "source_summary_note": "",
            "overall_result_label": "",
            "overall_result_reason": "",
            "interpretation_note": f"Family {family} contributes a concentrated portion of the validation queue.",
            "notes": f"family={family}; strongest={strongest['candidate_id']}",
        })

    final_row = next((r for r in rows if _norm(r.get("section")) == "A_OVERALL_VALIDATION_QUEUE_SUMMARY"), {})
    rows.append({
        **final_row,
        "section": "H_FINAL_INTERPRETATION",
        "rank": "",
        "queue_id": "",
        "candidate_id": "",
        "source_slice_type": "",
        "source_slice_key": "",
        "provider": "",
        "event_family": "",
        "condition_dimension": "",
        "condition_value": "",
        "candidate_label": "",
        "learning_priority": "",
        "source_confidence_label": "",
        "sample_groups": "",
        "comparable_rows": "",
        "correct_count": "",
        "wrong_count": "",
        "correct_rate": "",
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "misleading_stability_rate": "",
        "sample_adequacy_label": "",
        "effect_size_label": "",
        "misleading_stability_severity_label": "",
        "repetition_label": "",
        "cohort_fragility_label": "",
        "provider_family_fragility_label": "",
        "contradiction_label": "",
        "interpretability_label": "",
        "validation_score": "",
        "validation_strength_label": "",
        "validation_queue_label": "",
        "next_validation_action": "",
        "queue_count": "",
        "validate_first_count": "",
        "validate_later_count": "",
        "observe_only_count": "",
        "reject_after_filter_count": "",
        "candidate_label_counts": "",
        "validation_strength_label_counts": "",
        "strongest_queue_candidate": "",
        "strongest_queue_score": "",
        "dominant_risk_type": "",
        "source_final_label": _source_final_label(source_summary_rows),
        "source_summary_note": _source_summary_note(source_summary_rows),
        "overall_result_label": final_label,
        "overall_result_reason": final_reason,
        "interpretation_note": (
            "The validation queue is narrow but operationally useful."
            if final_label in {"VALIDATION_QUEUE_READY", "LIMITED_VALIDATION_QUEUE"}
            else "Most candidates remain better suited to observation than near-term validation."
        ),
        "notes": f"source_final_label={_source_final_label(source_summary_rows)}; candidate_count={len(queue_rows)}",
    })
    return rows


def build_character_learning_validation_queue() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    candidates = sources["candidates"]
    summary_rows = sources["summary"]
    queue_rows = _build_queue_rows(generated_ts, candidates, summary_rows)
    summary_output_rows = _build_summary_rows(generated_ts, queue_rows, candidates, summary_rows)
    registry_result = _upsert_registry_rows(service)

    queue_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_QUEUE_SHEET, QUEUE_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_QUEUE_SHEET, queue_headers, queue_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_output_rows)

    final_row = next((r for r in summary_output_rows if _norm(r.get("section")) == "H_FINAL_INTERPRETATION"), {})
    return {
        "generated_ts": generated_ts,
        "candidates_read": len([r for r in candidates if _norm(r.get("candidate_label"))]),
        "validate_first": sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_FIRST"),
        "validate_later": sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "VALIDATE_LATER"),
        "observe_only": sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "OBSERVE_ONLY"),
        "reject_after_filter": sum(1 for r in queue_rows if _norm(r.get("validation_queue_label")) == "REJECT_AFTER_FILTER"),
        "providers_represented": sorted({r["provider"] for r in queue_rows if _norm(r.get("provider"))}),
        "families_represented": sorted({r["event_family"] for r in queue_rows if _norm(r.get("event_family"))}),
        "overall_result_label": final_row.get("overall_result_label", ""),
        "registry": registry_result,
    }


if __name__ == "__main__":
    print(build_character_learning_validation_queue())
