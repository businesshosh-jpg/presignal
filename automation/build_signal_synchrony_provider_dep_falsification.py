import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
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
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_AUDIT_SHEET = "Signal_Synchrony_Provider_Dep_Falsification"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Provider_Dep_Falsification_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_PROVIDER_DEP_FALSIFICATION",
        "physical_sheet_name": OUTPUT_AUDIT_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only provider dependence falsification audit",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_PROVIDER_DEP_FALSIFICATION_SUMMARY",
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
        "notes": "Derived-only provider dependence falsification summary",
    },
]

AUDIT_HEADERS = [
    "generated_ts",
    "strategy_id",
    "strategy_type",
    "deployable_status",
    "event_id",
    "release_ts",
    "event_family",
    "importance",
    "predictability_bucket",
    "cohort_id",
    "providers_available",
    "selected_provider",
    "selected_provider_available",
    "selected_provider_correct",
    "original_selected_provider",
    "original_selected_provider_correct",
    "provider_choice_limited",
    "anthropic_available",
    "anthropic_correct",
    "anthopic_control_status",
    "cap_applied",
    "cap_value",
    "cap_displaced_provider",
    "balance_constraint_applied",
    "fallback_reason",
    "selected_slice_type",
    "selected_slice_key",
    "prior_provider_family_rows",
    "prior_provider_overall_rows",
    "prior_provider_correct_rate",
    "prior_family_baseline_rate",
    "prior_global_baseline_rate",
    "actual_comparable",
    "strategy_correct",
    "strategy_wrong",
    "oracle_correct_available",
    "baseline_correct_reference",
    "interpretation_note",
    "thin_sample_flag",
    "confidence_label",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "strategy_id",
    "strategy_type",
    "provider",
    "event_family",
    "event_units",
    "comparable_events",
    "selected_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "delta_vs_equal_aggregate_baseline",
    "delta_vs_original_cpv",
    "delta_vs_oracle",
    "provider_concentration_ratio",
    "selection_share",
    "fallback_count",
    "fallback_rate",
    "original_anthropic_selection_share",
    "anthropic_only_correct_rate",
    "no_anthropic_correct_rate",
    "provider_capped_correct_rate",
    "balanced_provider_correct_rate",
    "best_prior_provider_correct_rate",
    "delta_reference",
    "final_interpretation",
    "notes",
]

PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]


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


def _rounded_or_blank(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return _round4(float(value))
    return ""


def _confidence_label(comparable_events: int) -> str:
    if comparable_events >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_events >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_events >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


@dataclass
class ProviderOutcome:
    event_id: str
    provider: str
    release_ts: str
    release_dt: Optional[datetime]
    event_family: str
    importance: str
    cohort_id: str
    predictability_bucket: str
    actual_comparable: bool
    correct: Optional[bool]


@dataclass
class EventDecision:
    event_id: str
    release_ts: str
    release_dt: Optional[datetime]
    event_family: str
    importance: str
    predictability_bucket: str
    cohort_id: str
    providers_available: List[str]
    comparable_provider_count: int
    provider_choice_limited: bool
    original_selected_provider: str
    original_selected_provider_correct: Optional[bool]
    oracle_correct_available: Optional[bool]
    baseline_correct_reference: Optional[float]


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "cpv_audit": "Signal_Synchrony_Conditional_Value_Audit",
        "cpv_summary": "Signal_Synchrony_Conditional_Value_Summary",
        "cpv_stability": "Signal_Synchrony_Conditional_Value_Stability",
        "cpv_stability_summary": "Signal_Synchrony_Conditional_Value_Stability_Summary",
        "cpv_mechanism": "Signal_Synchrony_Conditional_Value_Mechanism",
        "cpv_mechanism_summary": "Signal_Synchrony_Conditional_Value_Mechanism_Summary",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _provider_outcomes(provider_rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], ProviderOutcome]:
    grouped: Dict[Tuple[str, str], List[ProviderOutcome]] = defaultdict(list)
    for row in provider_rows:
        event_id = _norm(row.get("event_id"))
        provider = _norm(row.get("provider"))
        if not event_id or not provider:
            continue
        outcome = ProviderOutcome(
            event_id=event_id,
            provider=provider,
            release_ts=_norm(row.get("release_ts")),
            release_dt=_parse_dt(row.get("release_ts")),
            event_family=_norm(row.get("event_family")) or "unknown",
            importance=_norm(row.get("importance")) or "unknown",
            cohort_id=_norm(row.get("cohort_id")) or _norm(row.get("cohort_group")) or "unknown",
            predictability_bucket=_norm(row.get("predictability_bucket")) or "unknown",
            actual_comparable=_as_bool(row.get("actual_comparable")),
            correct=True if _as_bool(row.get("forecast_matches_actual")) else (
                False if _upper(row.get("outcome_result_label")) in {"FORECAST_WRONG"} else None
            ),
        )
        grouped[(event_id, provider)].append(outcome)

    resolved: Dict[Tuple[str, str], ProviderOutcome] = {}
    for key, candidates in grouped.items():
        candidates.sort(
            key=lambda c: (
                0 if c.actual_comparable else 1,
                c.release_dt or datetime.max,
                c.cohort_id,
            )
        )
        resolved[key] = candidates[0]
    return resolved


def _event_decisions(
    audit_rows: Sequence[Dict[str, Any]],
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
) -> List[EventDecision]:
    out: List[EventDecision] = []
    for row in audit_rows:
        event_id = _norm(row.get("event_id"))
        if not event_id:
            continue
        providers_available = [p for p in _norm(row.get("providers_available")).split("|") if p]
        comparable_count = 0
        predictability_bucket = "unknown"
        for provider in providers_available:
            provider_row = provider_lookup.get((event_id, provider))
            if provider_row and provider_row.actual_comparable:
                comparable_count += 1
                if predictability_bucket == "unknown":
                    predictability_bucket = provider_row.predictability_bucket or "unknown"
        out.append(
            EventDecision(
                event_id=event_id,
                release_ts=_norm(row.get("release_ts")),
                release_dt=_parse_dt(row.get("release_ts")),
                event_family=_norm(row.get("event_family")) or "unknown",
                importance=_norm(row.get("importance")) or "unknown",
                predictability_bucket=predictability_bucket,
                cohort_id=_norm(row.get("cohort_group")) or "unknown",
                providers_available=providers_available,
                comparable_provider_count=comparable_count,
                provider_choice_limited=_as_bool(row.get("provider_choice_limited_flag")) or comparable_count <= 1,
                original_selected_provider=_norm(row.get("selected_provider")),
                original_selected_provider_correct=(
                    True if _as_bool(row.get("selected_provider_correct_flag")) else
                    False if _norm(row.get("selected_provider_correct_flag")) != "" else None
                ),
                oracle_correct_available=(
                    True if _as_bool(row.get("oracle_correct_flag")) else
                    False if _norm(row.get("oracle_correct_flag")) != "" else None
                ),
                baseline_correct_reference=_as_float(row.get("equal_aggregate_event_rate")),
            )
        )
    out.sort(key=lambda r: (r.release_dt or datetime.max, r.event_id))
    return out


def _available_comparable_rows(
    decision: EventDecision,
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
    allowed_providers: Optional[Sequence[str]] = None,
) -> List[ProviderOutcome]:
    allowed = set(allowed_providers) if allowed_providers else None
    out: List[ProviderOutcome] = []
    for provider in decision.providers_available:
        if allowed is not None and provider not in allowed:
            continue
        row = provider_lookup.get((decision.event_id, provider))
        if row and row.actual_comparable:
            out.append(row)
    out.sort(key=lambda r: (PROVIDER_ORDER.index(r.provider) if r.provider in PROVIDER_ORDER else 99, r.provider))
    return out


def _history_rows(
    decision: EventDecision,
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
    allowed_providers: Optional[Sequence[str]] = None,
) -> List[ProviderOutcome]:
    allowed = set(allowed_providers) if allowed_providers else None
    rows = []
    for row in provider_lookup.values():
        if not row.actual_comparable:
            continue
        if allowed is not None and row.provider not in allowed:
            continue
        if not row.release_dt or not decision.release_dt:
            continue
        if row.release_dt >= decision.release_dt:
            continue
        rows.append(row)
    return rows


def _rate(rows: Sequence[ProviderOutcome]) -> Tuple[int, int, Optional[float]]:
    comparable = [row for row in rows if row.actual_comparable and row.correct is not None]
    correct = sum(1 for row in comparable if row.correct)
    return len(comparable), correct, _safe_rate(correct, len(comparable))


def _score_candidates(
    decision: EventDecision,
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
    allowed_providers: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    candidates = _available_comparable_rows(decision, provider_lookup, allowed_providers=allowed_providers)
    history = _history_rows(decision, provider_lookup, allowed_providers=allowed_providers)
    _, global_correct, global_rate = _rate(history)
    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        family_history = [
            row for row in history
            if row.provider == candidate.provider and row.event_family == decision.event_family
        ]
        provider_history = [row for row in history if row.provider == candidate.provider]
        family_pool = [row for row in history if row.event_family == decision.event_family]
        family_rows, family_correct, family_rate = _rate(family_history)
        overall_rows, overall_correct, overall_rate = _rate(provider_history)
        pool_rows, pool_correct, pool_rate = _rate(family_pool)
        family_advantage = None
        if family_rate is not None and pool_rate is not None:
            family_advantage = family_rate - pool_rate
        if family_rows > 0:
            slice_type = "provider_family_history"
            slice_key = f"{candidate.provider}|{decision.event_family}"
            primary_score = family_rate if family_rate is not None else -1.0
            sample_count = family_rows
            fallback_reason = "none"
        elif overall_rows > 0:
            slice_type = "provider_overall_history"
            slice_key = candidate.provider
            primary_score = overall_rate if overall_rate is not None else -1.0
            sample_count = overall_rows
            fallback_reason = "family_history_missing"
        else:
            slice_type = "global_fallback"
            slice_key = "global"
            primary_score = global_rate if global_rate is not None else 0.0
            sample_count = 0
            fallback_reason = "provider_history_missing"
        scored.append(
            {
                "provider": candidate.provider,
                "row": candidate,
                "selected_slice_type": slice_type,
                "selected_slice_key": slice_key,
                "prior_provider_family_rows": family_rows,
                "prior_provider_overall_rows": overall_rows,
                "prior_provider_correct_rate": overall_rate,
                "prior_family_baseline_rate": pool_rate,
                "prior_global_baseline_rate": global_rate,
                "primary_score": primary_score,
                "sample_count": sample_count,
                "family_advantage": family_advantage,
                "fallback_reason": fallback_reason,
            }
        )
    scored.sort(
        key=lambda item: (
            {"provider_family_history": 0, "provider_overall_history": 1, "global_fallback": 2}.get(item["selected_slice_type"], 9),
            -(item["primary_score"] if item["primary_score"] is not None else -1.0),
            -item["sample_count"],
            -(item["family_advantage"] if item["family_advantage"] is not None else -999.0),
            PROVIDER_ORDER.index(item["provider"]) if item["provider"] in PROVIDER_ORDER else 99,
            item["provider"],
        )
    )
    return scored, global_rate


def _build_reference_row(
    generated_ts: str,
    decision: EventDecision,
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
) -> Dict[str, Any]:
    anthropic_row = provider_lookup.get((decision.event_id, "Anthropic"))
    comparable = decision.comparable_provider_count >= 2
    selected_provider = decision.original_selected_provider
    return {
        "generated_ts": generated_ts,
        "strategy_id": "original_cpv_reference",
        "strategy_type": "reference",
        "deployable_status": "not_production",
        "event_id": decision.event_id,
        "release_ts": decision.release_ts,
        "event_family": decision.event_family,
        "importance": decision.importance,
        "predictability_bucket": decision.predictability_bucket,
        "cohort_id": decision.cohort_id,
        "providers_available": "|".join(decision.providers_available),
        "selected_provider": selected_provider,
        "selected_provider_available": "TRUE" if selected_provider else "FALSE",
        "selected_provider_correct": "TRUE" if decision.original_selected_provider_correct is True else ("FALSE" if decision.original_selected_provider_correct is False else ""),
        "original_selected_provider": selected_provider,
        "original_selected_provider_correct": "TRUE" if decision.original_selected_provider_correct is True else ("FALSE" if decision.original_selected_provider_correct is False else ""),
        "provider_choice_limited": "TRUE" if decision.provider_choice_limited else "FALSE",
        "anthropic_available": "TRUE" if anthropic_row and anthropic_row.actual_comparable else "FALSE",
        "anthropic_correct": "TRUE" if anthropic_row and anthropic_row.correct is True else ("FALSE" if anthropic_row and anthropic_row.correct is False else ""),
        "anthopic_control_status": "reference_only",
        "cap_applied": "FALSE",
        "cap_value": "",
        "cap_displaced_provider": "",
        "balance_constraint_applied": "FALSE",
        "fallback_reason": "provider_choice_limited" if not comparable else "reference",
        "selected_slice_type": "historical_reference",
        "selected_slice_key": selected_provider,
        "prior_provider_family_rows": "",
        "prior_provider_overall_rows": "",
        "prior_provider_correct_rate": "",
        "prior_family_baseline_rate": "",
        "prior_global_baseline_rate": "",
        "actual_comparable": "TRUE" if comparable else "FALSE",
        "strategy_correct": "TRUE" if comparable and decision.original_selected_provider_correct is True else ("FALSE" if comparable and decision.original_selected_provider_correct is False else ""),
        "strategy_wrong": "TRUE" if comparable and decision.original_selected_provider_correct is False else ("FALSE" if comparable and decision.original_selected_provider_correct is True else ""),
        "oracle_correct_available": "TRUE" if decision.oracle_correct_available is True else ("FALSE" if decision.oracle_correct_available is False else ""),
        "baseline_correct_reference": _round4(decision.baseline_correct_reference),
        "interpretation_note": "Original walk-forward CPV reference row.",
        "thin_sample_flag": "FALSE" if comparable else "TRUE",
        "confidence_label": _confidence_label(1 if comparable else 0),
    }


def _build_strategy_row(
    generated_ts: str,
    strategy_id: str,
    strategy_type: str,
    decision: EventDecision,
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
    selected: Optional[Dict[str, Any]],
    fallback_reason: str,
    *,
    cap_applied: bool = False,
    cap_value: Optional[float] = None,
    cap_displaced_provider: str = "",
    balance_constraint_applied: bool = False,
    anthropic_status: str = "",
) -> Dict[str, Any]:
    anthropic_row = provider_lookup.get((decision.event_id, "Anthropic"))
    comparable = decision.comparable_provider_count >= 2
    selected_provider = _norm(selected.get("provider")) if selected else ""
    selected_row = selected.get("row") if selected else None
    selected_correct = selected_row.correct if selected_row else None
    provider_history_rows = selected.get("prior_provider_overall_rows") if selected else ""
    confidence_rows = provider_history_rows if isinstance(provider_history_rows, int) else 0
    if selected and isinstance(selected.get("prior_provider_family_rows"), int):
        confidence_rows = max(confidence_rows, selected["prior_provider_family_rows"])
    return {
        "generated_ts": generated_ts,
        "strategy_id": strategy_id,
        "strategy_type": strategy_type,
        "deployable_status": "not_production",
        "event_id": decision.event_id,
        "release_ts": decision.release_ts,
        "event_family": decision.event_family,
        "importance": decision.importance,
        "predictability_bucket": decision.predictability_bucket,
        "cohort_id": decision.cohort_id,
        "providers_available": "|".join(decision.providers_available),
        "selected_provider": selected_provider,
        "selected_provider_available": "TRUE" if selected_provider else "FALSE",
        "selected_provider_correct": "TRUE" if selected_correct is True else ("FALSE" if selected_correct is False else ""),
        "original_selected_provider": decision.original_selected_provider,
        "original_selected_provider_correct": "TRUE" if decision.original_selected_provider_correct is True else ("FALSE" if decision.original_selected_provider_correct is False else ""),
        "provider_choice_limited": "TRUE" if decision.provider_choice_limited else "FALSE",
        "anthropic_available": "TRUE" if anthropic_row and anthropic_row.actual_comparable else "FALSE",
        "anthropic_correct": "TRUE" if anthropic_row and anthropic_row.correct is True else ("FALSE" if anthropic_row and anthropic_row.correct is False else ""),
        "anthopic_control_status": anthropic_status,
        "cap_applied": "TRUE" if cap_applied else "FALSE",
        "cap_value": _round4(cap_value),
        "cap_displaced_provider": cap_displaced_provider,
        "balance_constraint_applied": "TRUE" if balance_constraint_applied else "FALSE",
        "fallback_reason": fallback_reason,
        "selected_slice_type": selected.get("selected_slice_type", "") if selected else "",
        "selected_slice_key": selected.get("selected_slice_key", "") if selected else "",
        "prior_provider_family_rows": selected.get("prior_provider_family_rows", "") if selected else "",
        "prior_provider_overall_rows": selected.get("prior_provider_overall_rows", "") if selected else "",
        "prior_provider_correct_rate": _rounded_or_blank(selected.get("prior_provider_correct_rate")) if selected else "",
        "prior_family_baseline_rate": _rounded_or_blank(selected.get("prior_family_baseline_rate")) if selected else "",
        "prior_global_baseline_rate": _rounded_or_blank(selected.get("prior_global_baseline_rate")) if selected else "",
        "actual_comparable": "TRUE" if comparable and selected_row is not None else "FALSE",
        "strategy_correct": "TRUE" if comparable and selected_correct is True else ("FALSE" if comparable and selected_correct is False else ""),
        "strategy_wrong": "TRUE" if comparable and selected_correct is False else ("FALSE" if comparable and selected_correct is True else ""),
        "oracle_correct_available": "TRUE" if decision.oracle_correct_available is True else ("FALSE" if decision.oracle_correct_available is False else ""),
        "baseline_correct_reference": _round4(decision.baseline_correct_reference),
        "interpretation_note": "",
        "thin_sample_flag": "TRUE" if confidence_rows < 8 else "FALSE",
        "confidence_label": _confidence_label(confidence_rows),
    }


def _simulate_strategies(
    decisions: Sequence[EventDecision],
    provider_lookup: Dict[Tuple[str, str], ProviderOutcome],
    generated_ts: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    capped_counts: Counter[str] = Counter()
    capped_decisions = 0
    balanced_counts: Counter[str] = Counter()

    for decision in decisions:
        rows.append(_build_reference_row(generated_ts, decision, provider_lookup))

        anthropic_row = provider_lookup.get((decision.event_id, "Anthropic"))
        anthropic_selected = None
        anthropic_fallback = "anthropic_unavailable"
        anthropic_status = "anthropic_missing"
        if anthropic_row and anthropic_row.actual_comparable and decision.comparable_provider_count >= 2:
            anthropic_selected = {
                "provider": "Anthropic",
                "row": anthropic_row,
                "selected_slice_type": "provider_baseline",
                "selected_slice_key": "Anthropic",
                "prior_provider_family_rows": "",
                "prior_provider_overall_rows": "",
                "prior_provider_correct_rate": "",
                "prior_family_baseline_rate": "",
                "prior_global_baseline_rate": "",
            }
            anthropic_fallback = "none"
            anthropic_status = "anthropic_selected"
        rows.append(
            _build_strategy_row(
                generated_ts,
                "anthropic_only_baseline",
                "provider_baseline",
                decision,
                provider_lookup,
                anthropic_selected,
                anthropic_fallback,
                anthropic_status=anthropic_status,
            )
        )

        no_anthropic_scores, _ = _score_candidates(decision, provider_lookup, allowed_providers=["Gemini", "OpenAI"])
        no_anthropic_selected = no_anthropic_scores[0] if no_anthropic_scores and decision.comparable_provider_count >= 2 else None
        no_anthropic_reason = no_anthropic_selected["fallback_reason"] if no_anthropic_selected else "no_non_anthropic_candidate"
        rows.append(
            _build_strategy_row(
                generated_ts,
                "no_anthropic_walk_forward",
                "provider_control",
                decision,
                provider_lookup,
                no_anthropic_selected,
                no_anthropic_reason,
                anthropic_status="anthropic_excluded",
            )
        )

        capped_scores, _ = _score_candidates(decision, provider_lookup)
        capped_selected = None
        cap_applied = False
        cap_displaced_provider = ""
        cap_value = 0.5
        capped_reason = "no_candidate"
        if capped_scores and decision.comparable_provider_count >= 2:
            for idx, candidate in enumerate(capped_scores):
                projected_total = capped_decisions + 1
                allowed_count = max(1, int(projected_total * cap_value))
                if projected_total * cap_value > allowed_count:
                    allowed_count += 1 if False else 0
                projected_count = capped_counts[candidate["provider"]] + 1
                if projected_count <= allowed_count:
                    capped_selected = candidate
                    if idx > 0:
                        cap_applied = True
                        cap_displaced_provider = capped_scores[0]["provider"]
                    break
            if capped_selected is None:
                capped_selected = capped_scores[0]
                capped_reason = "cap_forced_fallback"
            else:
                capped_reason = capped_selected["fallback_reason"]
            if capped_selected:
                capped_counts[capped_selected["provider"]] += 1
                capped_decisions += 1
        rows.append(
            _build_strategy_row(
                generated_ts,
                "provider_capped_walk_forward",
                "concentration_control",
                decision,
                provider_lookup,
                capped_selected,
                capped_reason,
                cap_applied=cap_applied,
                cap_value=cap_value,
                cap_displaced_provider=cap_displaced_provider,
                anthropic_status="anthropic_allowed_with_cap",
            )
        )

        balanced_scores, _ = _score_candidates(decision, provider_lookup)
        balanced_selected = None
        balance_applied = False
        balanced_reason = "no_candidate"
        if balanced_scores and decision.comparable_provider_count >= 2:
            available_counts = [balanced_counts[item["provider"]] for item in balanced_scores]
            min_count = min(available_counts) if available_counts else 0
            eligible = [item for item in balanced_scores if balanced_counts[item["provider"]] <= min_count + 1]
            if not eligible:
                eligible = balanced_scores
            balanced_selected = eligible[0]
            if balanced_selected["provider"] != balanced_scores[0]["provider"]:
                balance_applied = True
            balanced_reason = balanced_selected["fallback_reason"]
            balanced_counts[balanced_selected["provider"]] += 1
        rows.append(
            _build_strategy_row(
                generated_ts,
                "balanced_provider_simulation",
                "balance_control",
                decision,
                provider_lookup,
                balanced_selected,
                balanced_reason,
                balance_constraint_applied=balance_applied,
                anthropic_status="anthropic_allowed_balanced",
            )
        )

        best_prior_scores, global_rate = _score_candidates(decision, provider_lookup)
        best_prior_selected = None
        best_prior_reason = "no_candidate"
        if best_prior_scores and decision.comparable_provider_count >= 2:
            best_prior_scores.sort(
                key=lambda item: (
                    -(item["prior_provider_correct_rate"] if item["prior_provider_correct_rate"] is not None else (global_rate if global_rate is not None else 0.0)),
                    -item["prior_provider_overall_rows"],
                    PROVIDER_ORDER.index(item["provider"]) if item["provider"] in PROVIDER_ORDER else 99,
                    item["provider"],
                )
            )
            best_prior_selected = dict(best_prior_scores[0])
            best_prior_selected["selected_slice_type"] = "best_prior_provider_overall"
            best_prior_selected["selected_slice_key"] = best_prior_selected["provider"]
            best_prior_reason = best_prior_selected["fallback_reason"]
        rows.append(
            _build_strategy_row(
                generated_ts,
                "best_prior_provider_baseline",
                "simple_provider_history",
                decision,
                provider_lookup,
                best_prior_selected,
                best_prior_reason,
                anthropic_status="anthropic_allowed_simple_history",
            )
        )

    return rows


def _strategy_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_norm(row.get("strategy_id"))].append(row)
    metrics: Dict[str, Dict[str, Any]] = {}
    for strategy_id, strategy_rows in grouped.items():
        comparable_rows = [row for row in strategy_rows if _as_bool(row.get("actual_comparable"))]
        selected_rows = [row for row in comparable_rows if _norm(row.get("selected_provider"))]
        correct_count = sum(1 for row in comparable_rows if _as_bool(row.get("strategy_correct")))
        wrong_count = sum(1 for row in comparable_rows if _as_bool(row.get("strategy_wrong")))
        fallback_count = sum(1 for row in strategy_rows if _norm(row.get("fallback_reason")) not in {"", "none", "reference"})
        provider_counts = Counter(_norm(row.get("selected_provider")) for row in selected_rows if _norm(row.get("selected_provider")))
        total_selected = sum(provider_counts.values())
        metrics[strategy_id] = {
            "event_units": len(strategy_rows),
            "comparable_events": len(comparable_rows),
            "selected_rows": len(selected_rows),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "correct_rate": _safe_rate(correct_count, len(comparable_rows)),
            "baseline_rate": _safe_mean(_as_float(row.get("baseline_correct_reference")) for row in comparable_rows),
            "oracle_rate": _safe_rate(sum(1 for row in comparable_rows if _as_bool(row.get("oracle_correct_available"))), len(comparable_rows)),
            "provider_concentration_ratio": max((count / total_selected for count in provider_counts.values()), default=None),
            "fallback_count": fallback_count,
            "fallback_rate": _safe_rate(fallback_count, len(strategy_rows)),
            "provider_counts": provider_counts,
        }
    return metrics


def _final_interpretation(strategy_metrics: Dict[str, Dict[str, Any]]) -> str:
    original = strategy_metrics.get("original_cpv_reference", {})
    anthropic = strategy_metrics.get("anthropic_only_baseline", {})
    no_anthropic = strategy_metrics.get("no_anthropic_walk_forward", {})
    capped = strategy_metrics.get("provider_capped_walk_forward", {})
    balanced = strategy_metrics.get("balanced_provider_simulation", {})
    best_prior = strategy_metrics.get("best_prior_provider_baseline", {})

    original_rate = original.get("correct_rate")
    baseline_rate = original.get("baseline_rate")
    anthropic_rate = anthropic.get("correct_rate")
    no_anthropic_rate = no_anthropic.get("correct_rate")
    capped_rate = capped.get("correct_rate")
    balanced_rate = balanced.get("correct_rate")
    best_prior_rate = best_prior.get("correct_rate")

    if original.get("comparable_events", 0) < 20 or original_rate is None or baseline_rate is None:
        return "INSUFFICIENT_DATA"
    if best_prior_rate is not None and original_rate is not None and best_prior_rate >= original_rate:
        return "SIMPLE_PROVIDER_BASELINE_EXPLAINS_CPV"
    if anthropic_rate is not None and original_rate is not None and anthropic_rate >= original_rate:
        return "ANTHROPIC_ONLY_EXPLAINS_CPV"
    if no_anthropic.get("comparable_events", 0) < 20:
        return "INSUFFICIENT_DATA"
    if no_anthropic_rate is not None and no_anthropic_rate <= baseline_rate and original_rate > baseline_rate:
        return "CPV_COLLAPSES_WITHOUT_ANTHROPIC"
    capped_gain = (capped_rate - baseline_rate) if capped_rate is not None else None
    balanced_gain = (balanced_rate - baseline_rate) if balanced_rate is not None else None
    no_anthropic_gain = (no_anthropic_rate - baseline_rate) if no_anthropic_rate is not None else None
    if (
        no_anthropic_gain is not None and no_anthropic_gain > 0
        and capped_gain is not None and capped_gain > 0
        and balanced_gain is not None and balanced_gain > 0
    ):
        return "CPV_SURVIVES_PROVIDER_CONTROLS"
    if any(gain is not None and gain > 0 for gain in [capped_gain, balanced_gain]):
        return "CPV_PARTIALLY_SURVIVES"
    return "INSUFFICIENT_DATA"


def _build_summary_rows(
    generated_ts: str,
    rows: Sequence[Dict[str, Any]],
    final_interpretation: str,
) -> List[Dict[str, Any]]:
    strategy_metrics = _strategy_metrics(rows)
    original_metrics = strategy_metrics.get("original_cpv_reference", {})
    original_rate = original_metrics.get("correct_rate")
    baseline_rate = original_metrics.get("baseline_rate")
    oracle_rate = original_metrics.get("oracle_rate")
    original_anthropic_share = _safe_rate(
        original_metrics.get("provider_counts", {}).get("Anthropic", 0),
        sum(original_metrics.get("provider_counts", {}).values()),
    )

    summary_rows: List[Dict[str, Any]] = []
    for strategy_id in [
        "original_cpv_reference",
        "anthropic_only_baseline",
        "no_anthropic_walk_forward",
        "provider_capped_walk_forward",
        "balanced_provider_simulation",
        "best_prior_provider_baseline",
    ]:
        metrics = strategy_metrics.get(strategy_id, {})
        correct_rate = metrics.get("correct_rate")
        summary_rows.append({
            "generated_ts": generated_ts,
            "section": "A_STRATEGY_COMPARISON",
            "strategy_id": strategy_id,
            "strategy_type": next((row.get("strategy_type") for row in rows if _norm(row.get("strategy_id")) == strategy_id), ""),
            "provider": "",
            "event_family": "",
            "event_units": metrics.get("event_units", ""),
            "comparable_events": metrics.get("comparable_events", ""),
            "selected_rows": metrics.get("selected_rows", ""),
            "correct_count": metrics.get("correct_count", ""),
            "wrong_count": metrics.get("wrong_count", ""),
            "correct_rate": _round4(correct_rate),
            "delta_vs_equal_aggregate_baseline": _round4(correct_rate - baseline_rate) if correct_rate is not None and baseline_rate is not None else "",
            "delta_vs_original_cpv": _round4(correct_rate - original_rate) if correct_rate is not None and original_rate is not None else "",
            "delta_vs_oracle": _round4(correct_rate - oracle_rate) if correct_rate is not None and oracle_rate is not None else "",
            "provider_concentration_ratio": _round4(metrics.get("provider_concentration_ratio")),
            "selection_share": "",
            "fallback_count": metrics.get("fallback_count", ""),
            "fallback_rate": _round4(metrics.get("fallback_rate")),
            "original_anthropic_selection_share": _round4(original_anthropic_share),
            "anthropic_only_correct_rate": _round4(strategy_metrics.get("anthropic_only_baseline", {}).get("correct_rate")),
            "no_anthropic_correct_rate": _round4(strategy_metrics.get("no_anthropic_walk_forward", {}).get("correct_rate")),
            "provider_capped_correct_rate": _round4(strategy_metrics.get("provider_capped_walk_forward", {}).get("correct_rate")),
            "balanced_provider_correct_rate": _round4(strategy_metrics.get("balanced_provider_simulation", {}).get("correct_rate")),
            "best_prior_provider_correct_rate": _round4(strategy_metrics.get("best_prior_provider_baseline", {}).get("correct_rate")),
            "delta_reference": "",
            "final_interpretation": "",
            "notes": "",
        })

    for strategy_id, metrics in strategy_metrics.items():
        total_selected = sum(metrics.get("provider_counts", {}).values())
        for provider in PROVIDER_ORDER:
            count = metrics.get("provider_counts", {}).get(provider, 0)
            provider_rows = [
                row for row in rows
                if _norm(row.get("strategy_id")) == strategy_id and _norm(row.get("selected_provider")) == provider and _as_bool(row.get("actual_comparable"))
            ]
            correct_count = sum(1 for row in provider_rows if _as_bool(row.get("strategy_correct")))
            wrong_count = sum(1 for row in provider_rows if _as_bool(row.get("strategy_wrong")))
            summary_rows.append({
                "generated_ts": generated_ts,
                "section": "B_PROVIDER_SELECTION_DISTRIBUTION",
                "strategy_id": strategy_id,
                "strategy_type": next((row.get("strategy_type") for row in rows if _norm(row.get("strategy_id")) == strategy_id), ""),
                "provider": provider,
                "event_family": "",
                "event_units": "",
                "comparable_events": len(provider_rows),
                "selected_rows": count,
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "correct_rate": _round4(_safe_rate(correct_count, len(provider_rows))),
                "delta_vs_equal_aggregate_baseline": "",
                "delta_vs_original_cpv": "",
                "delta_vs_oracle": "",
                "provider_concentration_ratio": "",
                "selection_share": _round4(_safe_rate(count, total_selected)),
                "fallback_count": "",
                "fallback_rate": "",
                "original_anthropic_selection_share": "",
                "anthropic_only_correct_rate": "",
                "no_anthropic_correct_rate": "",
                "provider_capped_correct_rate": "",
                "balanced_provider_correct_rate": "",
                "best_prior_provider_correct_rate": "",
                "delta_reference": "",
                "final_interpretation": "",
                "notes": "",
            })

    summary_rows.append({
        "generated_ts": generated_ts,
        "section": "C_ANTHROPIC_DEPENDENCE",
        "strategy_id": "anthropic_dependence_overview",
        "strategy_type": "diagnostic",
        "provider": "Anthropic",
        "event_family": "",
        "event_units": "",
        "comparable_events": original_metrics.get("comparable_events", ""),
        "selected_rows": "",
        "correct_count": "",
        "wrong_count": "",
        "correct_rate": "",
        "delta_vs_equal_aggregate_baseline": "",
        "delta_vs_original_cpv": "",
        "delta_vs_oracle": "",
        "provider_concentration_ratio": "",
        "selection_share": "",
        "fallback_count": "",
        "fallback_rate": "",
        "original_anthropic_selection_share": _round4(original_anthropic_share),
        "anthropic_only_correct_rate": _round4(strategy_metrics.get("anthropic_only_baseline", {}).get("correct_rate")),
        "no_anthropic_correct_rate": _round4(strategy_metrics.get("no_anthropic_walk_forward", {}).get("correct_rate")),
        "provider_capped_correct_rate": _round4(strategy_metrics.get("provider_capped_walk_forward", {}).get("correct_rate")),
        "balanced_provider_correct_rate": _round4(strategy_metrics.get("balanced_provider_simulation", {}).get("correct_rate")),
        "best_prior_provider_correct_rate": _round4(strategy_metrics.get("best_prior_provider_baseline", {}).get("correct_rate")),
        "delta_reference": (
            f"anthropic_only_vs_original={_round4((strategy_metrics.get('anthropic_only_baseline', {}).get('correct_rate') or 0) - (original_rate or 0))}; "
            f"no_anthropic_vs_original={_round4((strategy_metrics.get('no_anthropic_walk_forward', {}).get('correct_rate') or 0) - (original_rate or 0))}; "
            f"capped_vs_original={_round4((strategy_metrics.get('provider_capped_walk_forward', {}).get('correct_rate') or 0) - (original_rate or 0))}; "
            f"balanced_vs_original={_round4((strategy_metrics.get('balanced_provider_simulation', {}).get('correct_rate') or 0) - (original_rate or 0))}"
        ),
        "final_interpretation": "",
        "notes": "",
    })

    summary_rows.append({
        "generated_ts": generated_ts,
        "section": "D_CONDITIONAL_LOGIC_ADDED_VALUE",
        "strategy_id": "conditional_logic_added_value",
        "strategy_type": "comparison",
        "provider": "",
        "event_family": "",
        "event_units": "",
        "comparable_events": original_metrics.get("comparable_events", ""),
        "selected_rows": "",
        "correct_count": "",
        "wrong_count": "",
        "correct_rate": _round4(original_rate),
        "delta_vs_equal_aggregate_baseline": _round4((original_rate or 0) - (baseline_rate or 0)),
        "delta_vs_original_cpv": "",
        "delta_vs_oracle": _round4((original_rate or 0) - (oracle_rate or 0)) if original_rate is not None and oracle_rate is not None else "",
        "provider_concentration_ratio": "",
        "selection_share": "",
        "fallback_count": "",
        "fallback_rate": "",
        "original_anthropic_selection_share": "",
        "anthropic_only_correct_rate": "",
        "no_anthropic_correct_rate": "",
        "provider_capped_correct_rate": "",
        "balanced_provider_correct_rate": "",
        "best_prior_provider_correct_rate": "",
        "delta_reference": (
            f"beats_best_prior={str((original_rate or -999) > (strategy_metrics.get('best_prior_provider_baseline', {}).get('correct_rate') or -999)).upper()}; "
            f"beats_anthropic_only={str((original_rate or -999) > (strategy_metrics.get('anthropic_only_baseline', {}).get('correct_rate') or -999)).upper()}; "
            f"beats_capped={str((original_rate or -999) > (strategy_metrics.get('provider_capped_walk_forward', {}).get('correct_rate') or -999)).upper()}; "
            f"beats_balanced={str((original_rate or -999) > (strategy_metrics.get('balanced_provider_simulation', {}).get('correct_rate') or -999)).upper()}"
        ),
        "final_interpretation": "",
        "notes": "",
    })

    families = sorted({_norm(row.get("event_family")) or "unknown" for row in rows if _as_bool(row.get("actual_comparable"))})
    for strategy_id in strategy_metrics:
        strategy_rows = [row for row in rows if _norm(row.get("strategy_id")) == strategy_id and _as_bool(row.get("actual_comparable"))]
        original_rows = [row for row in rows if _norm(row.get("strategy_id")) == "original_cpv_reference" and _as_bool(row.get("actual_comparable"))]
        for family in families:
            family_rows = [row for row in strategy_rows if _norm(row.get("event_family")) == family]
            original_family_rows = [row for row in original_rows if _norm(row.get("event_family")) == family]
            baseline_rows = [row for row in family_rows if _as_float(row.get("baseline_correct_reference")) is not None]
            correct_rate = _safe_rate(sum(1 for row in family_rows if _as_bool(row.get("strategy_correct"))), len(family_rows))
            original_rate_family = _safe_rate(sum(1 for row in original_family_rows if _as_bool(row.get("strategy_correct"))), len(original_family_rows))
            family_baseline = _safe_mean(_as_float(row.get("baseline_correct_reference")) for row in baseline_rows)
            summary_rows.append({
                "generated_ts": generated_ts,
                "section": "E_FAMILY_LEVEL_CONTROL_RESULTS",
                "strategy_id": strategy_id,
                "strategy_type": next((row.get("strategy_type") for row in rows if _norm(row.get("strategy_id")) == strategy_id), ""),
                "provider": "",
                "event_family": family,
                "event_units": "",
                "comparable_events": len(family_rows),
                "selected_rows": len(family_rows),
                "correct_count": sum(1 for row in family_rows if _as_bool(row.get("strategy_correct"))),
                "wrong_count": sum(1 for row in family_rows if _as_bool(row.get("strategy_wrong"))),
                "correct_rate": _round4(correct_rate),
                "delta_vs_equal_aggregate_baseline": _round4(correct_rate - family_baseline) if correct_rate is not None and family_baseline is not None else "",
                "delta_vs_original_cpv": _round4(correct_rate - original_rate_family) if correct_rate is not None and original_rate_family is not None else "",
                "delta_vs_oracle": "",
                "provider_concentration_ratio": "",
                "selection_share": "",
                "fallback_count": "",
                "fallback_rate": "",
                "original_anthropic_selection_share": "",
                "anthropic_only_correct_rate": "",
                "no_anthropic_correct_rate": "",
                "provider_capped_correct_rate": "",
                "balanced_provider_correct_rate": "",
                "best_prior_provider_correct_rate": "",
                "delta_reference": "",
                "final_interpretation": "",
                "notes": "",
            })

    summary_rows.append({
        "generated_ts": generated_ts,
        "section": "F_FINAL_FALSIFICATION_INTERPRETATION",
        "strategy_id": "final_interpretation",
        "strategy_type": "diagnostic",
        "provider": "",
        "event_family": "",
        "event_units": original_metrics.get("event_units", ""),
        "comparable_events": original_metrics.get("comparable_events", ""),
        "selected_rows": "",
        "correct_count": "",
        "wrong_count": "",
        "correct_rate": _round4(original_rate),
        "delta_vs_equal_aggregate_baseline": _round4((original_rate or 0) - (baseline_rate or 0)),
        "delta_vs_original_cpv": "",
        "delta_vs_oracle": _round4((original_rate or 0) - (oracle_rate or 0)) if original_rate is not None and oracle_rate is not None else "",
        "provider_concentration_ratio": _round4(original_metrics.get("provider_concentration_ratio")),
        "selection_share": "",
        "fallback_count": "",
        "fallback_rate": "",
        "original_anthropic_selection_share": _round4(original_anthropic_share),
        "anthropic_only_correct_rate": _round4(strategy_metrics.get("anthropic_only_baseline", {}).get("correct_rate")),
        "no_anthropic_correct_rate": _round4(strategy_metrics.get("no_anthropic_walk_forward", {}).get("correct_rate")),
        "provider_capped_correct_rate": _round4(strategy_metrics.get("provider_capped_walk_forward", {}).get("correct_rate")),
        "balanced_provider_correct_rate": _round4(strategy_metrics.get("balanced_provider_simulation", {}).get("correct_rate")),
        "best_prior_provider_correct_rate": _round4(strategy_metrics.get("best_prior_provider_baseline", {}).get("correct_rate")),
        "delta_reference": "",
        "final_interpretation": final_interpretation,
        "notes": "Historical provider-dependence falsification only; no routing, weighting, or calibration approval.",
    })
    return summary_rows


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


def build_provider_dependence_falsification() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    provider_lookup = _provider_outcomes(sources["provider_slice"])
    decisions = _event_decisions(sources["cpv_audit"], provider_lookup)
    audit_rows = _simulate_strategies(decisions, provider_lookup, generated_ts)
    final_interpretation = _final_interpretation(_strategy_metrics(audit_rows))
    summary_rows = _build_summary_rows(generated_ts, audit_rows, final_interpretation)

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)
    registry_result = _upsert_registry_rows(service)

    strategy_metrics = _strategy_metrics(audit_rows)
    return {
        "generated_ts": generated_ts,
        "event_level_units": len(decisions),
        "comparable_events": strategy_metrics.get("original_cpv_reference", {}).get("comparable_events", 0),
        "providers_represented": sorted({provider for decision in decisions for provider in decision.providers_available}),
        "families_represented": sorted({decision.event_family for decision in decisions}),
        "cohorts_represented": sorted({decision.cohort_id for decision in decisions}),
        "strategy_metrics": strategy_metrics,
        "final_interpretation": final_interpretation,
        "registry": registry_result,
    }


if __name__ == "__main__":
    result = build_provider_dependence_falsification()
    print(result)
