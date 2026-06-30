import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, load_credentials


DIAGNOSTICS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_DIAGNOSTICS_SPREADSHEET_ID",
    "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0",
)

SOURCE_SHEETS = {
    "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
    "provider_summary": "Signal_Synchrony_Provider_Slice_Summary",
    "family_slice": "Signal_Synchrony_Family_Slice_Performance",
    "family_summary": "Signal_Synchrony_Family_Slice_Summary",
    "cohort_characterization": "Signal_Synchrony_Cohort_Characterization",
    "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
}

OUTPUT_AUDIT_SHEET = "Signal_Synchrony_Conditional_Value_Audit"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Conditional_Value_Summary"


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


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


def _round4(value: Optional[float]) -> Any:
    if value is None:
        return ""
    if math.isnan(value) or math.isinf(value):
        return ""
    return round(value, 4)


def _parse_dt(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except Exception:
        return None


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
    }


def _confidence_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _decision_confidence(
    provider_family_history_rows: int,
    provider_overall_history_rows: int,
    gap_vs_family_baseline: Optional[float],
    fallback_reason: str,
) -> str:
    if fallback_reason == "global_fallback":
        return "LOW_EVIDENCE"
    if provider_family_history_rows >= 12 and gap_vs_family_baseline is not None and abs(gap_vs_family_baseline) >= 0.10:
        return "HIGH_EVIDENCE"
    if provider_family_history_rows >= 5 or provider_overall_history_rows >= 12:
        return "MEDIUM_EVIDENCE"
    return "LOW_EVIDENCE"


def _overall_interpretation(
    comparable_events: int,
    walk_forward_rate: Optional[float],
    baseline_rate: Optional[float],
    nonfallback_rate: Optional[float],
) -> str:
    if comparable_events < 20 or walk_forward_rate is None or baseline_rate is None:
        return "INSUFFICIENT_DATA"
    gain = walk_forward_rate - baseline_rate
    if gain >= 0.05 and (nonfallback_rate or 0.0) >= 0.55:
        return "PASS_SHADOW_TEST"
    if gain > 0:
        return "WATCH"
    return "FAIL_OVERFIT"


def _sheet_to_rows(service, spreadsheet_id: str, sheet_name: str) -> List[Dict[str, Any]]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:ZZZ")
        .execute()
        .get("values", [])
    )
    if not values:
        return []
    headers = values[0]
    rows: List[Dict[str, Any]] = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append(dict(zip(headers, padded)))
    return rows


def _get_sheet_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    try:
        values = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
            .execute()
            .get("values", [])
        )
        return values[0] if values else []
    except Exception:
        return []


def _ensure_sheet(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    required_headers: List[str],
) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_titles = {s["properties"]["title"] for s in metadata.get("sheets", [])}
    if sheet_name not in existing_titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
        final_headers = list(required_headers)
    else:
        final_headers = _get_sheet_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in final_headers:
                final_headers.append(header)

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [final_headers]},
    ).execute()
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A2:ZZZ",
    ).execute()
    return final_headers


def _write_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    headers: List[str],
    rows: List[Dict[str, Any]],
) -> None:
    if not rows:
        return
    values = [[row.get(header, "") for header in headers] for row in rows]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A2",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


@dataclass
class ProviderEventRow:
    sample_group_id: str
    event_id: str
    release_ts: str
    release_dt: Optional[datetime]
    provider: str
    event_family: str
    cohort_group: str
    indicator_name: str
    importance: str
    comparable: bool
    correct: bool
    outcome_result_label: str
    predictability_bucket: str
    predictability_index: Optional[float]
    forecast_direction_concentration: Optional[float]
    pattern_concentration_score: Optional[float]
    expression_similarity_mean: Optional[float]


def _build_provider_event_rows(rows: Iterable[Dict[str, Any]]) -> List[ProviderEventRow]:
    out: List[ProviderEventRow] = []
    for row in rows:
        out.append(
            ProviderEventRow(
                sample_group_id=_norm(row.get("sample_group_id")),
                event_id=_norm(row.get("event_id")),
                release_ts=_norm(row.get("release_ts")),
                release_dt=_parse_dt(row.get("release_ts")),
                provider=_norm(row.get("provider")),
                event_family=_norm(row.get("event_family")) or "unknown",
                cohort_group=_norm(row.get("cohort_group")) or _norm(row.get("cohort_id")) or "unknown",
                indicator_name=_norm(row.get("indicator_name")),
                importance=_norm(row.get("importance")),
                comparable=_is_comparable(row),
                correct=_is_correct(row),
                outcome_result_label=_norm(row.get("outcome_result_label")),
                predictability_bucket=_norm(row.get("predictability_bucket")) or "unknown",
                predictability_index=_as_float(row.get("predictability_index")),
                forecast_direction_concentration=_as_float(row.get("forecast_direction_concentration")),
                pattern_concentration_score=_as_float(row.get("pattern_concentration_score")),
                expression_similarity_mean=_as_float(row.get("expression_similarity_mean")),
            )
        )
    out.sort(key=lambda r: (r.release_dt or datetime.max, r.event_id, r.provider, r.sample_group_id))
    return out


def _make_event_units(provider_rows: List[ProviderEventRow]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[ProviderEventRow]] = defaultdict(list)
    for row in provider_rows:
        grouped[row.event_id].append(row)

    event_units: List[Dict[str, Any]] = []
    for event_id, rows in grouped.items():
        rows.sort(key=lambda r: (r.provider, r.sample_group_id))
        first = min(rows, key=lambda r: (r.release_dt or datetime.max, r.provider, r.sample_group_id))
        comparable_rows = [row for row in rows if row.comparable]
        event_units.append(
            {
                "event_id": event_id,
                "release_dt": first.release_dt,
                "release_ts": first.release_ts,
                "event_family": first.event_family,
                "cohort_group": first.cohort_group,
                "indicator_name": first.indicator_name,
                "importance": first.importance,
                "providers_available": [row.provider for row in rows],
                "rows": rows,
                "comparable_rows": comparable_rows,
            }
        )
    event_units.sort(key=lambda e: (e["release_dt"] or datetime.max, e["event_id"]))
    return event_units


def _history_rates(history_rows: List[ProviderEventRow]) -> Dict[str, Any]:
    comparable = [row for row in history_rows if row.comparable]
    correct = [row for row in comparable if row.correct]
    return {
        "comparable_rows": len(comparable),
        "correct_count": len(correct),
        "correct_rate": _safe_rate(len(correct), len(comparable)),
    }


def _walk_forward_audit_rows(event_units: List[Dict[str, Any]], generated_ts: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    audit_rows: List[Dict[str, Any]] = []
    all_provider_rows = [row for event in event_units for row in event["rows"]]
    comparable_provider_rows = [row for row in all_provider_rows if row.comparable]
    global_baseline_rate = _safe_rate(
        sum(1 for row in comparable_provider_rows if row.correct),
        len(comparable_provider_rows),
    )

    selected_comparable_events = 0
    selected_correct_events = 0
    oracle_correct_events = 0
    provider_selection_counter: Counter[str] = Counter()
    provider_selection_success: Counter[str] = Counter()
    provider_selection_total: Counter[str] = Counter()
    fallback_counter: Counter[str] = Counter()
    evidence_counter: Counter[str] = Counter()
    family_metrics: Dict[str, Dict[str, int]] = defaultdict(lambda: {"baseline_correct": 0, "baseline_total": 0, "walk_correct": 0, "walk_total": 0, "oracle_correct": 0, "oracle_total": 0})
    cohort_metrics: Dict[str, Dict[str, int]] = defaultdict(lambda: {"baseline_correct": 0, "baseline_total": 0, "walk_correct": 0, "walk_total": 0, "oracle_correct": 0, "oracle_total": 0})
    provider_baselines: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    provider_selected_metrics: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    provider_family_history_rows_used: List[int] = []
    provider_advantage_used: List[float] = []
    provider_choice_limited_events = 0
    nonfallback_decisions = 0

    for event in event_units:
        comparable_rows: List[ProviderEventRow] = event["comparable_rows"]
        for row in comparable_rows:
            family_metrics[row.event_family]["baseline_total"] += 1
            family_metrics[row.event_family]["baseline_correct"] += 1 if row.correct else 0
            cohort_metrics[row.cohort_group]["baseline_total"] += 1
            cohort_metrics[row.cohort_group]["baseline_correct"] += 1 if row.correct else 0
            provider_baselines[row.provider]["total"] += 1
            provider_baselines[row.provider]["correct"] += 1 if row.correct else 0

        comparable_count = len(comparable_rows)
        provider_count = len(event["rows"])
        selection_eligible = comparable_count >= 2
        provider_choice_limited = provider_count <= 1 or comparable_count <= 1
        if provider_choice_limited:
            provider_choice_limited_events += 1

        event_baseline_rate = _safe_rate(
            sum(1 for row in comparable_rows if row.correct),
            comparable_count,
        )
        oracle_correct = any(row.correct for row in comparable_rows)
        if comparable_count >= 1:
            family_metrics[event["event_family"]]["oracle_total"] += 1
            family_metrics[event["event_family"]]["oracle_correct"] += 1 if oracle_correct else 0
            cohort_metrics[event["cohort_group"]]["oracle_total"] += 1
            cohort_metrics[event["cohort_group"]]["oracle_correct"] += 1 if oracle_correct else 0

        row_out: Dict[str, Any] = {
            "generated_ts": generated_ts,
            "event_id": event["event_id"],
            "release_ts": event["release_ts"],
            "event_family": event["event_family"],
            "cohort_group": event["cohort_group"],
            "indicator_name": event["indicator_name"],
            "importance": event["importance"],
            "providers_available": "|".join(event["providers_available"]),
            "providers_available_count": len(event["providers_available"]),
            "comparable_provider_count": comparable_count,
            "provider_choice_limited_flag": "TRUE" if provider_choice_limited else "FALSE",
            "selection_eligible": "TRUE" if selection_eligible else "FALSE",
            "equal_aggregate_event_rate": _round4(event_baseline_rate),
            "oracle_result": "CORRECT" if oracle_correct else ("WRONG" if comparable_count else "UNAVAILABLE"),
            "oracle_correct_flag": "TRUE" if oracle_correct else "FALSE",
            "selected_provider": "",
            "selected_provider_correct_flag": "",
            "selected_provider_result_label": "",
            "provider_family_history_rows": "",
            "provider_family_history_correct_rate": "",
            "provider_overall_history_rows": "",
            "provider_overall_history_correct_rate": "",
            "global_history_rows": len([row for row in all_provider_rows if row.release_dt and event["release_dt"] and row.release_dt < event["release_dt"] and row.comparable]),
            "global_history_correct_rate": _round4(
                _safe_rate(
                    sum(
                        1
                        for row in all_provider_rows
                        if row.release_dt and event["release_dt"] and row.release_dt < event["release_dt"] and row.comparable and row.correct
                    ),
                    sum(
                        1
                        for row in all_provider_rows
                        if row.release_dt and event["release_dt"] and row.release_dt < event["release_dt"] and row.comparable
                    ),
                )
            ),
            "selection_level": "",
            "fallback_reason": "",
            "evidence_quality": "",
            "available_provider_scores": "",
            "conditional_value_gain_vs_baseline": "",
            "distance_to_oracle": "",
            "notes": "",
        }

        if not selection_eligible:
            row_out["fallback_reason"] = "provider_choice_limited" if provider_choice_limited else "not_comparable"
            audit_rows.append(row_out)
            continue

        selected_comparable_events += 1
        history_rows = [
            row
            for row in all_provider_rows
            if row.release_dt and event["release_dt"] and row.release_dt < event["release_dt"] and row.comparable
        ]
        provider_scores = []
        for candidate in comparable_rows:
            family_history = [
                row
                for row in history_rows
                if row.provider == candidate.provider and row.event_family == event["event_family"]
            ]
            provider_history = [row for row in history_rows if row.provider == candidate.provider]
            family_history_rate = _history_rates(family_history)
            provider_history_rate = _history_rates(provider_history)
            family_pool = [row for row in history_rows if row.event_family == event["event_family"]]
            family_pool_rate = _history_rates(family_pool)
            family_advantage = None
            if family_history_rate["correct_rate"] is not None and family_pool_rate["correct_rate"] is not None:
                family_advantage = family_history_rate["correct_rate"] - family_pool_rate["correct_rate"]

            if family_history_rate["comparable_rows"] > 0:
                selection_level = "provider_family_history"
                primary_score = family_history_rate["correct_rate"] or -1.0
                sample_count = family_history_rate["comparable_rows"]
                fallback_reason = "none"
            elif provider_history_rate["comparable_rows"] > 0:
                selection_level = "provider_overall_history"
                primary_score = provider_history_rate["correct_rate"] or -1.0
                sample_count = provider_history_rate["comparable_rows"]
                fallback_reason = "family_history_missing"
            else:
                selection_level = "global_fallback"
                primary_score = global_baseline_rate or 0.0
                sample_count = 0
                fallback_reason = "provider_history_missing"

            provider_scores.append(
                {
                    "provider": candidate.provider,
                    "row": candidate,
                    "selection_level": selection_level,
                    "fallback_reason": fallback_reason,
                    "primary_score": primary_score,
                    "sample_count": sample_count,
                    "family_history_rows": family_history_rate["comparable_rows"],
                    "family_history_rate": family_history_rate["correct_rate"],
                    "provider_history_rows": provider_history_rate["comparable_rows"],
                    "provider_history_rate": provider_history_rate["correct_rate"],
                    "family_baseline_rate": family_pool_rate["correct_rate"],
                    "family_advantage": family_advantage,
                }
            )

        def _sort_tuple(item: Dict[str, Any]) -> Tuple[Any, ...]:
            level_rank = {
                "provider_family_history": 0,
                "provider_overall_history": 1,
                "global_fallback": 2,
            }.get(item["selection_level"], 9)
            family_advantage = item["family_advantage"]
            return (
                level_rank,
                -(item["primary_score"] if item["primary_score"] is not None else -1.0),
                -item["sample_count"],
                -(family_advantage if family_advantage is not None else -999.0),
                item["provider"],
            )

        provider_scores.sort(key=_sort_tuple)
        selected = provider_scores[0]
        selected_row = selected["row"]
        selected_correct = selected_row.correct
        if selected_correct:
            selected_correct_events += 1
        if oracle_correct:
            oracle_correct_events += 1
        provider_selection_counter[selected_row.provider] += 1
        provider_selection_total[selected_row.provider] += 1
        provider_selection_success[selected_row.provider] += 1 if selected_correct else 0
        provider_selected_metrics[selected_row.provider]["total"] += 1
        provider_selected_metrics[selected_row.provider]["correct"] += 1 if selected_correct else 0
        fallback_counter[selected["fallback_reason"]] += 1
        if selected["selection_level"] != "global_fallback":
            nonfallback_decisions += 1
        if selected["family_history_rows"] > 0:
            provider_family_history_rows_used.append(selected["family_history_rows"])
        if selected["family_advantage"] is not None:
            provider_advantage_used.append(selected["family_advantage"])

        family_metrics[event["event_family"]]["walk_total"] += 1
        family_metrics[event["event_family"]]["walk_correct"] += 1 if selected_correct else 0
        cohort_metrics[event["cohort_group"]]["walk_total"] += 1
        cohort_metrics[event["cohort_group"]]["walk_correct"] += 1 if selected_correct else 0

        family_gap = None
        family_baseline_rate = None
        if selected["family_history_rows"] > 0:
            family_baseline_rate = selected["family_baseline_rate"]
            if selected["family_history_rate"] is not None and family_baseline_rate is not None:
                family_gap = selected["family_history_rate"] - family_baseline_rate
        evidence_quality = _decision_confidence(
            provider_family_history_rows=selected["family_history_rows"],
            provider_overall_history_rows=selected["provider_history_rows"],
            gap_vs_family_baseline=family_gap,
            fallback_reason=selected["fallback_reason"],
        )
        evidence_counter[evidence_quality] += 1

        row_out.update(
            {
                "selected_provider": selected_row.provider,
                "selected_provider_correct_flag": "TRUE" if selected_correct else "FALSE",
                "selected_provider_result_label": selected_row.outcome_result_label,
                "provider_family_history_rows": selected["family_history_rows"],
                "provider_family_history_correct_rate": _round4(selected["family_history_rate"]),
                "provider_overall_history_rows": selected["provider_history_rows"],
                "provider_overall_history_correct_rate": _round4(selected["provider_history_rate"]),
                "selection_level": selected["selection_level"],
                "fallback_reason": selected["fallback_reason"],
                "evidence_quality": evidence_quality,
                "available_provider_scores": " | ".join(
                    f"{item['provider']}:{item['selection_level']}:{_round4(item['primary_score'])}:{item['sample_count']}"
                    for item in provider_scores
                ),
                "conditional_value_gain_vs_baseline": _round4(
                    (1.0 if selected_correct else 0.0) - (event_baseline_rate or 0.0)
                ),
                "distance_to_oracle": _round4((1.0 if oracle_correct else 0.0) - (1.0 if selected_correct else 0.0)),
                "notes": (
                    f"family_baseline_rate={_round4(selected['family_baseline_rate'])}; "
                    f"family_advantage={_round4(selected['family_advantage'])}"
                ),
            }
        )
        audit_rows.append(row_out)

    walk_forward_rate = _safe_rate(selected_correct_events, selected_comparable_events)
    oracle_rate = _safe_rate(oracle_correct_events, selected_comparable_events)
    nonfallback_rate = _safe_rate(
        sum(provider_selection_success[p] for p in provider_selection_success if provider_selection_total[p] > 0),
        sum(provider_selection_total.values()),
    )
    diagnostics = {
        "global_baseline_rate": global_baseline_rate,
        "walk_forward_correct_rate": walk_forward_rate,
        "oracle_correct_rate": oracle_rate,
        "conditional_value_gain": None
        if walk_forward_rate is None or global_baseline_rate is None
        else walk_forward_rate - global_baseline_rate,
        "distance_to_oracle": None
        if oracle_rate is None or walk_forward_rate is None
        else oracle_rate - walk_forward_rate,
        "selectable_events": selected_comparable_events,
        "selected_correct_events": selected_correct_events,
        "oracle_correct_events": oracle_correct_events,
        "provider_selection_counter": provider_selection_counter,
        "provider_selection_success": provider_selection_success,
        "provider_selection_total": provider_selection_total,
        "provider_baselines": provider_baselines,
        "provider_selected_metrics": provider_selected_metrics,
        "family_metrics": family_metrics,
        "cohort_metrics": cohort_metrics,
        "fallback_counter": fallback_counter,
        "evidence_counter": evidence_counter,
        "provider_choice_limited_events": provider_choice_limited_events,
        "nonfallback_decisions": nonfallback_decisions,
        "provider_family_history_rows_used": provider_family_history_rows_used,
        "provider_advantage_used": provider_advantage_used,
        "overall_interpretation": _overall_interpretation(
            comparable_events=selected_comparable_events,
            walk_forward_rate=walk_forward_rate,
            baseline_rate=global_baseline_rate,
            nonfallback_rate=nonfallback_rate,
        ),
    }
    return audit_rows, diagnostics


def _summary_rows(
    generated_ts: str,
    event_units: List[Dict[str, Any]],
    audit_rows: List[Dict[str, Any]],
    diagnostics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    providers_present = sorted({row.provider for event in event_units for row in event["rows"] if row.provider})
    families_present = sorted({event["event_family"] for event in event_units})
    cohorts_present = sorted({event["cohort_group"] for event in event_units})
    comparable_events = diagnostics["selectable_events"]
    global_baseline_rate = diagnostics["global_baseline_rate"]
    walk_forward_rate = diagnostics["walk_forward_correct_rate"]
    oracle_rate = diagnostics["oracle_correct_rate"]

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "METHODOLOGY",
            "row_type": "METHODOLOGY_NOTE",
            "scope": "methodology",
            "scope_key": "Signal Synchrony Conditional Predictive Value Audit",
            "notes": (
                "Walk-forward selection uses only prior comparable rows ordered by release_ts, with selection hierarchy "
                "provider×family history -> provider overall history -> global fallback. No minimum sample thresholds were used in the simulation; "
                "threshold recommendations below are descriptive only."
            ),
        }
    )

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "A",
            "row_type": "POPULATION",
            "scope": "overall",
            "scope_key": "population",
            "event_level_decision_units": len(event_units),
            "comparable_events": comparable_events,
            "providers_present": "|".join(providers_present),
            "families_present": "|".join(families_present),
            "cohorts_present": "|".join(cohorts_present),
            "provider_choice_limited_events": diagnostics["provider_choice_limited_events"],
            "fallback_frequency": _round4(
                _safe_rate(
                    diagnostics["fallback_counter"].get("provider_history_missing", 0)
                    + diagnostics["fallback_counter"].get("family_history_missing", 0),
                    comparable_events,
                )
            ),
            "notes": "Population includes single-provider events for counts, but provider selection evaluation excludes them.",
        }
    )

    strategy_rows = [
        (
            "Equal Aggregate Baseline",
            diagnostics["selected_correct_events"],  # placeholder corrected below
            diagnostics["selectable_events"],
            global_baseline_rate,
        ),
        (
            "Walk-Forward Provider Selection",
            diagnostics["selected_correct_events"],
            diagnostics["selectable_events"],
            walk_forward_rate,
        ),
        (
            "Oracle Ceiling",
            diagnostics["oracle_correct_events"],
            diagnostics["selectable_events"],
            oracle_rate,
        ),
    ]

    baseline_correct = 0.0
    baseline_total = 0
    for event in event_units:
        comparable_rows = event["comparable_rows"]
        if len(comparable_rows) >= 2:
            baseline_total += len(comparable_rows)
            baseline_correct += sum(1 for row in comparable_rows if row.correct)
    strategy_rows[0] = (
        "Equal Aggregate Baseline",
        int(baseline_correct),
        baseline_total,
        _safe_rate(int(baseline_correct), baseline_total),
    )

    for strategy_name, correct_count, denominator, rate in strategy_rows:
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "B",
                "row_type": "STRATEGY",
                "scope": "overall",
                "scope_key": strategy_name,
                "strategy_name": strategy_name,
                "correct_count": correct_count,
                "wrong_count": "" if denominator == 0 else denominator - correct_count,
                "denominator": denominator,
                "correct_rate": _round4(rate),
                "baseline_correct_rate": _round4(global_baseline_rate),
                "walk_forward_correct_rate": _round4(walk_forward_rate),
                "oracle_correct_rate": _round4(oracle_rate),
                "conditional_value_gain": _round4(None if rate is None or global_baseline_rate is None or strategy_name != "Walk-Forward Provider Selection" else rate - global_baseline_rate),
                "distance_to_oracle": _round4(None if rate is None or oracle_rate is None else oracle_rate - rate),
            }
        )

    for family, metrics in sorted(diagnostics["family_metrics"].items()):
        baseline_rate = _safe_rate(metrics["baseline_correct"], metrics["baseline_total"])
        walk_rate = _safe_rate(metrics["walk_correct"], metrics["walk_total"])
        oracle_family_rate = _safe_rate(metrics["oracle_correct"], metrics["oracle_total"])
        if metrics["walk_total"] < 8:
            interpretation = "Insufficient Data"
        else:
            gain = (walk_rate - baseline_rate) if walk_rate is not None and baseline_rate is not None else None
            if gain is None:
                interpretation = "Insufficient Data"
            elif gain >= 0.05:
                interpretation = "Positive Conditional Value"
            elif gain <= -0.05:
                interpretation = "Negative Conditional Value"
            else:
                interpretation = "Neutral"
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "C",
                "row_type": "FAMILY",
                "scope": "family",
                "scope_key": family,
                "event_family": family,
                "comparable_events": metrics["walk_total"],
                "baseline_correct_rate": _round4(baseline_rate),
                "walk_forward_correct_rate": _round4(walk_rate),
                "oracle_correct_rate": _round4(oracle_family_rate),
                "conditional_value_gain": _round4(None if walk_rate is None or baseline_rate is None else walk_rate - baseline_rate),
                "distance_to_oracle": _round4(None if oracle_family_rate is None or walk_rate is None else oracle_family_rate - walk_rate),
                "confidence_label": _confidence_label(metrics["walk_total"]),
                "interpretation": interpretation,
            }
        )

    for provider in sorted(diagnostics["provider_baselines"].keys()):
        baseline = diagnostics["provider_baselines"][provider]
        selected = diagnostics["provider_selected_metrics"][provider]
        provider_baseline_rate = _safe_rate(baseline["correct"], baseline["total"])
        selected_rate = _safe_rate(selected["correct"], selected["total"])
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "D",
                "row_type": "PROVIDER",
                "scope": "provider",
                "scope_key": provider,
                "provider": provider,
                "baseline_correct_rate": _round4(provider_baseline_rate),
                "walk_forward_correct_rate": _round4(selected_rate),
                "conditional_value_gain": _round4(
                    None if selected_rate is None or provider_baseline_rate is None else selected_rate - provider_baseline_rate
                ),
                "selection_frequency": _round4(_safe_rate(selected["total"], comparable_events)),
                "selection_count": selected["total"],
                "correct_count": selected["correct"],
                "confidence_label": _confidence_label(selected["total"]),
            }
        )

    for cohort in sorted(diagnostics["cohort_metrics"].keys()):
        metrics = diagnostics["cohort_metrics"][cohort]
        baseline_rate = _safe_rate(metrics["baseline_correct"], metrics["baseline_total"])
        walk_rate = _safe_rate(metrics["walk_correct"], metrics["walk_total"])
        oracle_cohort_rate = _safe_rate(metrics["oracle_correct"], metrics["oracle_total"])
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "E",
                "row_type": "COHORT",
                "scope": "cohort",
                "scope_key": cohort,
                "cohort_group": cohort,
                "baseline_correct_rate": _round4(baseline_rate),
                "walk_forward_correct_rate": _round4(walk_rate),
                "oracle_correct_rate": _round4(oracle_cohort_rate),
                "conditional_value_gain": _round4(None if walk_rate is None or baseline_rate is None else walk_rate - baseline_rate),
                "distance_to_oracle": _round4(None if oracle_cohort_rate is None or walk_rate is None else oracle_cohort_rate - walk_rate),
                "comparable_events": metrics["walk_total"],
                "confidence_label": _confidence_label(metrics["walk_total"]),
            }
        )

    history_used = diagnostics["provider_family_history_rows_used"]
    advantages = diagnostics["provider_advantage_used"]
    recommended_min_history = ""
    if history_used:
        recommended_min_history = math.ceil(median(history_used))
    recommended_min_advantage = ""
    if advantages:
        recommended_min_advantage = _round4(max(0.0, median(advantages)))
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "F",
            "row_type": "DIAGNOSTICS",
            "scope": "walk_forward",
            "scope_key": "diagnostics",
            "selection_count": comparable_events,
            "fallback_frequency": _round4(
                _safe_rate(
                    diagnostics["fallback_counter"].get("provider_history_missing", 0)
                    + diagnostics["fallback_counter"].get("family_history_missing", 0),
                    comparable_events,
                )
            ),
            "provider_choice_limited_events": diagnostics["provider_choice_limited_events"],
            "thin_sample_frequency": _round4(
                _safe_rate(
                    sum(1 for row in audit_rows if _upper(row.get("evidence_quality")) == "LOW_EVIDENCE"),
                    comparable_events,
                )
            ),
            "recommended_min_provider_family_history": recommended_min_history,
            "recommended_min_provider_advantage": recommended_min_advantage,
            "evidence_quality_distribution": "|".join(
                f"{key}:{value}" for key, value in sorted(diagnostics["evidence_counter"].items())
            ),
            "notes": "Recommended thresholds are descriptive observations from selected decisions only and were not used in the simulation.",
        }
    )

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "G",
            "row_type": "INTERPRETATION",
            "scope": "overall",
            "scope_key": "final_interpretation",
            "overall_interpretation": diagnostics["overall_interpretation"],
            "conditional_value_gain": _round4(diagnostics["conditional_value_gain"]),
            "distance_to_oracle": _round4(diagnostics["distance_to_oracle"]),
            "notes": (
                "PASS_SHADOW_TEST requires clear positive gain with usable evidence; WATCH indicates small or mixed improvement; "
                "FAIL_OVERFIT indicates the descriptive relationships did not survive walk-forward evaluation."
            ),
        }
    )
    return rows


AUDIT_HEADERS = [
    "generated_ts",
    "event_id",
    "release_ts",
    "event_family",
    "cohort_group",
    "indicator_name",
    "importance",
    "providers_available",
    "providers_available_count",
    "comparable_provider_count",
    "provider_choice_limited_flag",
    "selection_eligible",
    "equal_aggregate_event_rate",
    "oracle_result",
    "oracle_correct_flag",
    "selected_provider",
    "selected_provider_correct_flag",
    "selected_provider_result_label",
    "provider_family_history_rows",
    "provider_family_history_correct_rate",
    "provider_overall_history_rows",
    "provider_overall_history_correct_rate",
    "global_history_rows",
    "global_history_correct_rate",
    "selection_level",
    "fallback_reason",
    "evidence_quality",
    "available_provider_scores",
    "conditional_value_gain_vs_baseline",
    "distance_to_oracle",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "row_type",
    "scope",
    "scope_key",
    "strategy_name",
    "event_family",
    "provider",
    "cohort_group",
    "event_level_decision_units",
    "comparable_events",
    "providers_present",
    "families_present",
    "cohorts_present",
    "provider_choice_limited_events",
    "correct_count",
    "wrong_count",
    "denominator",
    "correct_rate",
    "baseline_correct_rate",
    "walk_forward_correct_rate",
    "oracle_correct_rate",
    "conditional_value_gain",
    "distance_to_oracle",
    "selection_frequency",
    "selection_count",
    "confidence_label",
    "interpretation",
    "fallback_frequency",
    "thin_sample_frequency",
    "recommended_min_provider_family_history",
    "recommended_min_provider_advantage",
    "evidence_quality_distribution",
    "overall_interpretation",
    "notes",
]


def build_conditional_value_audit() -> Dict[str, Any]:
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    source_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, SOURCE_SHEETS["provider_slice"])
    # Warm the required input tabs so the audit fails fast if workbook state drifted.
    for key in (
        "provider_summary",
        "family_slice",
        "family_summary",
        "cohort_characterization",
        "outcome_check",
    ):
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, SOURCE_SHEETS[key])

    provider_rows = _build_provider_event_rows(source_rows)
    event_units = _make_event_units(provider_rows)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    audit_rows, diagnostics = _walk_forward_audit_rows(event_units, generated_ts)
    summary_rows = _summary_rows(generated_ts, event_units, audit_rows, diagnostics)

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    return {
        "generated_ts": generated_ts,
        "event_level_decision_units": len(event_units),
        "comparable_events": diagnostics["selectable_events"],
        "providers_present": sorted({row.provider for row in provider_rows if row.provider}),
        "families_present": sorted({event["event_family"] for event in event_units}),
        "cohorts_present": sorted({event["cohort_group"] for event in event_units}),
        "baseline_correct_rate": _round4(diagnostics["global_baseline_rate"]),
        "walk_forward_correct_rate": _round4(diagnostics["walk_forward_correct_rate"]),
        "oracle_correct_rate": _round4(diagnostics["oracle_correct_rate"]),
        "conditional_value_gain": _round4(diagnostics["conditional_value_gain"]),
        "distance_to_oracle": _round4(diagnostics["distance_to_oracle"]),
        "overall_interpretation": diagnostics["overall_interpretation"],
        "audit_rows_written": len(audit_rows),
        "summary_rows_written": len(summary_rows),
        "fallback_counter": dict(diagnostics["fallback_counter"]),
        "provider_choice_limited_events": diagnostics["provider_choice_limited_events"],
    }


if __name__ == "__main__":
    result = build_conditional_value_audit()
    print(result)
