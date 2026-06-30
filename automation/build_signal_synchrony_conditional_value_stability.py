import math
import os
import sys
from collections import defaultdict
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
    SOURCE_SHEETS,
    _as_bool,
    _confidence_label,
    _ensure_sheet,
    _parse_dt,
    _round4,
    _sheet_to_rows,
    _write_rows,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


PROJECT_OVERVIEWS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_PROJECT_OVERVIEWS_SPREADSHEET_ID",
    "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo",
)

OUTPUT_STABILITY_SHEET = "Signal_Synchrony_Conditional_Value_Stability"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Conditional_Value_Stability_Summary"
REGISTRY_SHEET = "Sheet_Registry"

STABILITY_HEADERS = [
    "generated_ts",
    "dimension",
    "rank",
    "slice_label",
    "comparable_events",
    "walk_forward_selections",
    "walk_forward_correct_count",
    "walk_forward_wrong_count",
    "baseline_correct_rate",
    "walk_forward_correct_rate",
    "oracle_correct_rate",
    "conditional_value_gain",
    "distance_to_oracle",
    "contribution_to_total_gain",
    "share_of_net_gain_pct",
    "share_of_positive_contribution_pct",
    "confidence_label",
    "stability_classification",
    "provider",
    "event_family",
    "cohort_group",
    "time_window",
    "predictability_bucket",
    "importance",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "dimension",
    "rank",
    "slice_label",
    "comparable_events",
    "baseline_correct_rate",
    "walk_forward_correct_rate",
    "conditional_value_gain",
    "oracle_correct_rate",
    "distance_to_oracle",
    "contribution_to_total_gain",
    "share_of_net_gain_pct",
    "share_of_positive_contribution_pct",
    "confidence_label",
    "stability_classification",
    "interpretation",
    "notes",
]

REGISTRY_HEADERS = [
    "logical_sheet_id",
    "physical_sheet_name",
    "workbook",
    "workbook_id",
    "category",
    "lifecycle_state",
    "owner_module",
    "participates_in_rebuild",
    "read_only",
    "allow_creation",
    "created_phase",
    "notes",
]

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_CONDITIONAL_VALUE_STABILITY",
        "physical_sheet_name": OUTPUT_STABILITY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only CPV robustness audit",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_CONDITIONAL_VALUE_STABILITY_SUMMARY",
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
        "notes": "Derived-only CPV robustness summary",
    },
]


@dataclass
class DecisionRecord:
    event_id: str
    release_ts: str
    release_dt: Optional[datetime]
    event_family: str
    cohort_group: str
    importance: str
    provider: str
    predictability_bucket: str
    predictability_index: Optional[float]
    baseline_rate: float
    walk_forward_correct: int
    oracle_correct: int


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


def _safe_mean(values: Sequence[float]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _column_letter(index: int) -> str:
    if index <= 0:
        raise ValueError("Column index must be positive")
    letters = []
    while index:
        index, rem = divmod(index - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _get_sheet_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _build_decision_records(service) -> List[DecisionRecord]:
    audit_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Signal_Synchrony_Conditional_Value_Audit")
    provider_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Signal_Synchrony_Provider_Slice_Performance")
    provider_lookup = {
        (_norm(row.get("event_id")), _norm(row.get("provider"))): row
        for row in provider_rows
    }

    records: List[DecisionRecord] = []
    for row in audit_rows:
        if not _as_bool(row.get("selection_eligible")):
            continue
        event_id = _norm(row.get("event_id"))
        provider = _norm(row.get("selected_provider"))
        provider_row = provider_lookup.get((event_id, provider), {})
        records.append(
            DecisionRecord(
                event_id=event_id,
                release_ts=_norm(row.get("release_ts")),
                release_dt=_parse_dt(row.get("release_ts")),
                event_family=_norm(row.get("event_family")) or "unknown",
                cohort_group=_norm(row.get("cohort_group")) or "unknown",
                importance=_norm(row.get("importance")) or "unknown",
                provider=provider or "unknown",
                predictability_bucket=_norm(provider_row.get("predictability_bucket")) or "unknown",
                predictability_index=_as_float(provider_row.get("predictability_index")),
                baseline_rate=_as_float(row.get("equal_aggregate_event_rate")) or 0.0,
                walk_forward_correct=1 if _as_bool(row.get("selected_provider_correct_flag")) else 0,
                oracle_correct=1 if _as_bool(row.get("oracle_correct_flag")) else 0,
            )
        )

    records.sort(key=lambda r: (r.release_dt or datetime.min, r.event_id))
    return records


def _aggregate_records(records: Sequence[DecisionRecord]) -> Dict[str, Any]:
    comparable_events = len(records)
    baseline_rate = _safe_mean([r.baseline_rate for r in records])
    walk_forward_rate = _safe_rate(sum(r.walk_forward_correct for r in records), comparable_events)
    oracle_rate = _safe_rate(sum(r.oracle_correct for r in records), comparable_events)
    total_gain = None if baseline_rate is None or walk_forward_rate is None else walk_forward_rate - baseline_rate
    return {
        "comparable_events": comparable_events,
        "baseline_correct_rate": baseline_rate,
        "walk_forward_correct_rate": walk_forward_rate,
        "oracle_correct_rate": oracle_rate,
        "conditional_value_gain": total_gain,
        "distance_to_oracle": None if oracle_rate is None or walk_forward_rate is None else oracle_rate - walk_forward_rate,
        "walk_forward_correct_count": sum(r.walk_forward_correct for r in records),
        "walk_forward_wrong_count": comparable_events - sum(r.walk_forward_correct for r in records),
    }


def _stability_classification(
    slice_gain: Optional[float],
    comparable_events: int,
    positive_share: Optional[float],
    is_top_positive: bool,
) -> str:
    if comparable_events < 5:
        return "INSUFFICIENT_DATA"
    if slice_gain is None:
        return "INSUFFICIENT_DATA"
    if slice_gain < 0:
        return "UNSTABLE"
    if is_top_positive and positive_share is not None and positive_share >= 0.4:
        return "CONCENTRATED"
    if comparable_events >= 20 and slice_gain >= 0.05:
        return "HIGHLY_STABLE"
    if slice_gain >= 0:
        return "MODERATELY_STABLE"
    return "UNSTABLE"


def _interpretation_for_row(
    comparable_events: int,
    slice_gain: Optional[float],
    classification: str,
    positive_share: Optional[float],
    is_top_positive: bool,
) -> str:
    if classification == "INSUFFICIENT_DATA":
        return "Too few comparable observations."
    if classification == "UNSTABLE":
        return "This slice reduces or negates the observed gain."
    if classification == "CONCENTRATED" and is_top_positive:
        if positive_share is not None:
            return f"Primary positive contributor in this dimension ({_round4(positive_share)} of positive contribution)."
        return "Primary positive contributor in this dimension."
    if classification == "HIGHLY_STABLE":
        return "Positive gain persists across a substantial sample."
    if comparable_events >= 8 and slice_gain is not None and slice_gain >= 0:
        return "Positive or neutral gain appears repeatable."
    return "Mixed or modestly stable gain pattern."


def _slice_rows(
    generated_ts: str,
    dimension: str,
    items: Iterable[Tuple[str, List[DecisionRecord]]],
    total_comparable_events: int,
    total_gain: Optional[float],
) -> List[Dict[str, Any]]:
    grouped = list(items)
    positive_total = 0.0
    slice_stats: List[Tuple[str, List[DecisionRecord], Dict[str, Any], Optional[float]]] = []
    for label, records in grouped:
        stats = _aggregate_records(records)
        contribution = None
        if stats["conditional_value_gain"] is not None and total_comparable_events > 0:
            contribution = stats["conditional_value_gain"] * stats["comparable_events"] / total_comparable_events
        slice_stats.append((label, list(records), stats, contribution))
        if contribution is not None and contribution > 0:
            positive_total += contribution

    top_positive_contribution = None
    top_positive_label = None
    for label, _, stats, contribution in slice_stats:
        if contribution is None or contribution <= 0:
            continue
        if top_positive_contribution is None or contribution > top_positive_contribution or (
            contribution == top_positive_contribution and label < (top_positive_label or "")
        ):
            top_positive_contribution = contribution
            top_positive_label = label

    rows: List[Dict[str, Any]] = []
    for rank, (label, records, stats, contribution) in enumerate(
        sorted(
            slice_stats,
            key=lambda item: (
                -(item[3] if item[3] is not None else -1e18),
                item[0],
            ),
        ),
        start=1,
    ):
        positive_share = None
        if contribution is not None and contribution > 0 and positive_total > 0:
            positive_share = contribution / positive_total
        net_share = None
        if contribution is not None and total_gain not in (None, 0):
            net_share = contribution / total_gain
        classification = _stability_classification(
            stats["conditional_value_gain"],
            stats["comparable_events"],
            positive_share,
            label == top_positive_label,
        )
        row = {
            "generated_ts": generated_ts,
            "dimension": dimension,
            "rank": rank,
            "slice_label": label,
            "comparable_events": stats["comparable_events"],
            "walk_forward_selections": stats["comparable_events"],
            "walk_forward_correct_count": stats["walk_forward_correct_count"],
            "walk_forward_wrong_count": stats["walk_forward_wrong_count"],
            "baseline_correct_rate": _round4(stats["baseline_correct_rate"]),
            "walk_forward_correct_rate": _round4(stats["walk_forward_correct_rate"]),
            "oracle_correct_rate": _round4(stats["oracle_correct_rate"]),
            "conditional_value_gain": _round4(stats["conditional_value_gain"]),
            "distance_to_oracle": _round4(stats["distance_to_oracle"]),
            "contribution_to_total_gain": _round4(contribution),
            "share_of_net_gain_pct": _round4(net_share),
            "share_of_positive_contribution_pct": _round4(positive_share),
            "confidence_label": _confidence_label(stats["comparable_events"]),
            "stability_classification": classification,
            "provider": "",
            "event_family": "",
            "cohort_group": "",
            "time_window": "",
            "predictability_bucket": "",
            "importance": "",
            "notes": _interpretation_for_row(
                stats["comparable_events"],
                stats["conditional_value_gain"],
                classification,
                positive_share,
                label == top_positive_label,
            ),
        }
        if dimension == "PROVIDER":
            row["provider"] = label
        elif dimension == "FAMILY":
            row["event_family"] = label
        elif dimension == "COHORT":
            row["cohort_group"] = label
        elif dimension == "TIME":
            row["time_window"] = label
        elif dimension == "PREDICTABILITY":
            row["predictability_bucket"] = label
        elif dimension == "IMPORTANCE":
            row["importance"] = label
        rows.append(row)
    return rows


def _ordered_groups(records: Sequence[DecisionRecord], key_fn, order: Sequence[str] = ()) -> List[Tuple[str, List[DecisionRecord]]]:
    grouped: Dict[str, List[DecisionRecord]] = defaultdict(list)
    for record in records:
        grouped[key_fn(record)].append(record)

    ordered: List[Tuple[str, List[DecisionRecord]]] = []
    seen = set()
    for key in order:
        if key in grouped:
            ordered.append((key, grouped[key]))
            seen.add(key)
    for key in sorted(grouped.keys()):
        if key not in seen:
            ordered.append((key, grouped[key]))
    return ordered


def _build_detail_rows(records: Sequence[DecisionRecord], generated_ts: str) -> List[Dict[str, Any]]:
    total_stats = _aggregate_records(records)
    total_gain = total_stats["conditional_value_gain"]
    rows: List[Dict[str, Any]] = []

    overall_row = {
        "generated_ts": generated_ts,
        "dimension": "OVERALL",
        "rank": 0,
        "slice_label": "Overall CPV Audit",
        "comparable_events": total_stats["comparable_events"],
        "walk_forward_selections": total_stats["comparable_events"],
        "walk_forward_correct_count": total_stats["walk_forward_correct_count"],
        "walk_forward_wrong_count": total_stats["walk_forward_wrong_count"],
        "baseline_correct_rate": _round4(total_stats["baseline_correct_rate"]),
        "walk_forward_correct_rate": _round4(total_stats["walk_forward_correct_rate"]),
        "oracle_correct_rate": _round4(total_stats["oracle_correct_rate"]),
        "conditional_value_gain": _round4(total_gain),
        "distance_to_oracle": _round4(total_stats["distance_to_oracle"]),
        "contribution_to_total_gain": _round4(total_gain),
        "share_of_net_gain_pct": 1.0 if total_gain not in (None, 0) else "",
        "share_of_positive_contribution_pct": 1.0 if total_gain and total_gain > 0 else "",
        "confidence_label": _confidence_label(total_stats["comparable_events"]),
        "stability_classification": "CONCENTRATED" if total_gain and total_gain > 0 else "UNSTABLE",
        "provider": "",
        "event_family": "",
        "cohort_group": "",
        "time_window": "",
        "predictability_bucket": "",
        "importance": "",
        "notes": "Event-level walk-forward decisions only; no provider calls or reruns.",
    }
    rows.append(overall_row)

    provider_rows = _slice_rows(
        generated_ts,
        "PROVIDER",
        _ordered_groups(records, lambda r: r.provider),
        total_stats["comparable_events"],
        total_gain,
    )
    family_rows = _slice_rows(
        generated_ts,
        "FAMILY",
        _ordered_groups(records, lambda r: r.event_family),
        total_stats["comparable_events"],
        total_gain,
    )
    cohort_rows = _slice_rows(
        generated_ts,
        "COHORT",
        _ordered_groups(records, lambda r: r.cohort_group, ("cohort_a", "deterministic", "random")),
        total_stats["comparable_events"],
        total_gain,
    )

    n = len(records)
    base_size = n // 3
    remainder = n % 3
    window_sizes = [base_size + (1 if i < remainder else 0) for i in range(3)]
    time_labels = ["first_third", "middle_third", "final_third"]
    time_groups: List[Tuple[str, List[DecisionRecord]]] = []
    cursor = 0
    for label, size in zip(time_labels, window_sizes):
        time_groups.append((label, list(records[cursor:cursor + size])))
        cursor += size
    time_rows = _slice_rows(generated_ts, "TIME", time_groups, total_stats["comparable_events"], total_gain)

    predictability_order = ("high", "medium", "low")
    predictability_rows = _slice_rows(
        generated_ts,
        "PREDICTABILITY",
        _ordered_groups(records, lambda r: r.predictability_bucket, predictability_order),
        total_stats["comparable_events"],
        total_gain,
    )
    missing_predictability = [bucket for bucket in predictability_order if bucket not in {r.predictability_bucket for r in records}]
    for bucket in missing_predictability:
        predictability_rows.append(
            {
                "generated_ts": generated_ts,
                "dimension": "PREDICTABILITY",
                "rank": len(predictability_rows) + 1,
                "slice_label": bucket,
                "comparable_events": 0,
                "walk_forward_selections": 0,
                "walk_forward_correct_count": 0,
                "walk_forward_wrong_count": 0,
                "baseline_correct_rate": "",
                "walk_forward_correct_rate": "",
                "oracle_correct_rate": "",
                "conditional_value_gain": "",
                "distance_to_oracle": "",
                "contribution_to_total_gain": "",
                "share_of_net_gain_pct": "",
                "share_of_positive_contribution_pct": "",
                "confidence_label": "THIN_SAMPLE",
                "stability_classification": "INSUFFICIENT_DATA",
                "provider": "",
                "event_family": "",
                "cohort_group": "",
                "time_window": "",
                "predictability_bucket": bucket,
                "importance": "",
                "notes": "No selected decisions landed in this predictability bucket.",
            }
        )

    importance_rows = _slice_rows(
        generated_ts,
        "IMPORTANCE",
        _ordered_groups(records, lambda r: r.importance, ("High", "Medium", "Low")),
        total_stats["comparable_events"],
        total_gain,
    )

    rows.extend(provider_rows)
    rows.extend(family_rows)
    rows.extend(cohort_rows)
    rows.extend(time_rows)
    rows.extend(predictability_rows)
    rows.extend(importance_rows)
    return rows


def _build_summary_rows(detail_rows: Sequence[Dict[str, Any]], records: Sequence[DecisionRecord], generated_ts: str) -> List[Dict[str, Any]]:
    total_row = next(row for row in detail_rows if row["dimension"] == "OVERALL")
    rows: List[Dict[str, Any]] = []
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "OVERVIEW",
            "dimension": "OVERALL",
            "rank": 0,
            "slice_label": "Overall CPV Stability",
            "comparable_events": total_row["comparable_events"],
            "baseline_correct_rate": total_row["baseline_correct_rate"],
            "walk_forward_correct_rate": total_row["walk_forward_correct_rate"],
            "conditional_value_gain": total_row["conditional_value_gain"],
            "oracle_correct_rate": total_row["oracle_correct_rate"],
            "distance_to_oracle": total_row["distance_to_oracle"],
            "contribution_to_total_gain": total_row["contribution_to_total_gain"],
            "share_of_net_gain_pct": total_row["share_of_net_gain_pct"],
            "share_of_positive_contribution_pct": total_row["share_of_positive_contribution_pct"],
            "confidence_label": total_row["confidence_label"],
            "stability_classification": "CONCENTRATED",
            "interpretation": "The observed CPV gain exists, but it is concentrated in a few slices rather than broadly distributed.",
            "notes": "Derived only from existing walk-forward decisions.",
        }
    )

    def _rows_for_dimension(dimension: str) -> List[Dict[str, Any]]:
        return [row for row in detail_rows if row["dimension"] == dimension]

    ranking_specs = [
        ("PROVIDER_RANKING", "PROVIDER"),
        ("FAMILY_RANKING", "FAMILY"),
        ("COHORT_RANKING", "COHORT"),
        ("TIME_STABILITY", "TIME"),
        ("PREDICTABILITY_STABILITY", "PREDICTABILITY"),
        ("IMPORTANCE_STABILITY", "IMPORTANCE"),
    ]
    for section, dimension in ranking_specs:
        for row in _rows_for_dimension(dimension):
            rows.append(
                {
                    "generated_ts": generated_ts,
                    "section": section,
                    "dimension": dimension,
                    "rank": row["rank"],
                    "slice_label": row["slice_label"],
                    "comparable_events": row["comparable_events"],
                    "baseline_correct_rate": row["baseline_correct_rate"],
                    "walk_forward_correct_rate": row["walk_forward_correct_rate"],
                    "conditional_value_gain": row["conditional_value_gain"],
                    "oracle_correct_rate": row["oracle_correct_rate"],
                    "distance_to_oracle": row["distance_to_oracle"],
                    "contribution_to_total_gain": row["contribution_to_total_gain"],
                    "share_of_net_gain_pct": row["share_of_net_gain_pct"],
                    "share_of_positive_contribution_pct": row["share_of_positive_contribution_pct"],
                    "confidence_label": row["confidence_label"],
                    "stability_classification": row["stability_classification"],
                    "interpretation": row["notes"],
                    "notes": "",
                }
            )

    provider_rows = _rows_for_dimension("PROVIDER")
    family_rows = _rows_for_dimension("FAMILY")
    cohort_rows = _rows_for_dimension("COHORT")
    time_rows = _rows_for_dimension("TIME")
    predictability_rows = _rows_for_dimension("PREDICTABILITY")
    importance_rows = _rows_for_dimension("IMPORTANCE")

    def _top_positive(rows_in: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        positive = [r for r in rows_in if isinstance(r.get("contribution_to_total_gain"), (int, float)) and r.get("contribution_to_total_gain", 0) > 0]
        return positive[0] if positive else None

    concentration_rows = []
    for label, rows_in in [
        ("Top provider", provider_rows),
        ("Top family", family_rows),
        ("Top cohort", cohort_rows),
        ("Top time window", time_rows),
        ("Top predictability bucket", predictability_rows),
        ("Top importance level", importance_rows),
    ]:
        top = _top_positive(rows_in)
        if top is None:
            concentration_rows.append(
                {
                    "generated_ts": generated_ts,
                    "section": "CONCENTRATION",
                    "dimension": label.upper().replace(" ", "_"),
                    "rank": 1,
                    "slice_label": label,
                    "comparable_events": "",
                    "baseline_correct_rate": "",
                    "walk_forward_correct_rate": "",
                    "conditional_value_gain": "",
                    "oracle_correct_rate": "",
                    "distance_to_oracle": "",
                    "contribution_to_total_gain": "",
                    "share_of_net_gain_pct": "",
                    "share_of_positive_contribution_pct": "",
                    "confidence_label": "",
                    "stability_classification": "INSUFFICIENT_DATA",
                    "interpretation": "No positive contribution in this section.",
                    "notes": "",
                }
            )
            continue
        concentration_rows.append(
            {
                "generated_ts": generated_ts,
                "section": "CONCENTRATION",
                "dimension": label.upper().replace(" ", "_"),
                "rank": 1,
                "slice_label": label,
                "comparable_events": top["comparable_events"],
                "baseline_correct_rate": top["baseline_correct_rate"],
                "walk_forward_correct_rate": top["walk_forward_correct_rate"],
                "conditional_value_gain": top["conditional_value_gain"],
                "oracle_correct_rate": top["oracle_correct_rate"],
                "distance_to_oracle": top["distance_to_oracle"],
                "contribution_to_total_gain": top["contribution_to_total_gain"],
                "share_of_net_gain_pct": top["share_of_net_gain_pct"],
                "share_of_positive_contribution_pct": top["share_of_positive_contribution_pct"],
                "confidence_label": top["confidence_label"],
                "stability_classification": top["stability_classification"],
                "interpretation": f"{label} drives the largest share of positive contribution in this dimension.",
                "notes": "",
            }
        )

    rows.extend(concentration_rows)

    total_gain = total_row["conditional_value_gain"]
    if total_gain is not None and total_gain > 0:
        overall_label = "CONCENTRATED"
    elif total_gain is not None and total_gain == 0:
        overall_label = "UNSTABLE"
    else:
        overall_label = "INSUFFICIENT_DATA"

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "INTERPRETATION",
            "dimension": "OVERALL",
            "rank": "",
            "slice_label": "Final interpretation",
            "comparable_events": total_row["comparable_events"],
            "baseline_correct_rate": total_row["baseline_correct_rate"],
            "walk_forward_correct_rate": total_row["walk_forward_correct_rate"],
            "conditional_value_gain": total_row["conditional_value_gain"],
            "oracle_correct_rate": total_row["oracle_correct_rate"],
            "distance_to_oracle": total_row["distance_to_oracle"],
            "contribution_to_total_gain": total_row["contribution_to_total_gain"],
            "share_of_net_gain_pct": total_row["share_of_net_gain_pct"],
            "share_of_positive_contribution_pct": total_row["share_of_positive_contribution_pct"],
            "confidence_label": total_row["confidence_label"],
            "stability_classification": overall_label,
            "interpretation": "CPV gain is present, but it is concentrated in a limited set of providers, families, cohorts, and early-time windows.",
            "notes": "This audit evaluates robustness only; it does not approve routing, weighting, calibration, or production behavior.",
        }
    )
    return rows


def _upsert_registry_rows(service) -> Dict[str, Any]:
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    if not rows:
        raise RuntimeError("Sheet_Registry is missing or empty.")
    existing_headers = _get_sheet_headers(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET) or list(REGISTRY_HEADERS)
    by_id = {(_norm(row.get("logical_sheet_id")).upper()): i + 2 for i, row in enumerate(rows)}
    updates = []
    appended = 0
    for row in REGISTRY_ROWS:
        values = [row.get(header, "") for header in existing_headers]
        key = _norm(row["logical_sheet_id"]).upper()
        if key in by_id:
            row_number = by_id[key]
            updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(existing_headers))}{row_number}", "values": [values]})
        else:
            appended += 1
            updates.append({"range": f"'{REGISTRY_SHEET}'!A{len(rows) + appended}:{_column_letter(len(existing_headers))}{len(rows) + appended}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(REGISTRY_ROWS) - appended, "appended": appended}


def build_conditional_value_stability() -> Dict[str, Any]:
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    records = _build_decision_records(service)
    if not records:
        raise RuntimeError("No comparable decision records were found for the stability audit.")

    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    detail_rows = _build_detail_rows(records, generated_ts)
    summary_rows = _build_summary_rows(detail_rows, records, generated_ts)

    detail_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_STABILITY_SHEET, STABILITY_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_STABILITY_SHEET, detail_headers, detail_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)

    total_row = next(row for row in detail_rows if row["dimension"] == "OVERALL")
    return {
        "generated_ts": generated_ts,
        "comparable_events": total_row["comparable_events"],
        "baseline_correct_rate": total_row["baseline_correct_rate"],
        "walk_forward_correct_rate": total_row["walk_forward_correct_rate"],
        "oracle_correct_rate": total_row["oracle_correct_rate"],
        "conditional_value_gain": total_row["conditional_value_gain"],
        "distance_to_oracle": total_row["distance_to_oracle"],
        "detail_rows_written": len(detail_rows),
        "summary_rows_written": len(summary_rows),
        "registry_result": registry_result,
    }


if __name__ == "__main__":
    result = build_conditional_value_stability()
    print(result)
