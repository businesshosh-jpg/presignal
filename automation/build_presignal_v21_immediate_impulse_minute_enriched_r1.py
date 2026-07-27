#!/usr/bin/env python3
"""Build a one-minute Immediate Impulse enrichment for completed Round 1.

This tool is intentionally additive. It consumes the frozen Round 1 outputs and
the authoritative recovered Tiingo minute cache, then writes a separate enriched
release without modifying any original artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract  # noqa: E402

ORIGINAL_ROUND1_RUN_ID = "PPHB-R1-FULL-20260726T160036Z-ca5d238916f1"
MATRIX_FREEZE_RUN_ID = "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"
CACHE_RECOVERY_RUN_ID = "PPHB-R1-TIINGO-MINUTE-CACHE-RECOVERY-20260727T081850Z-66c010cb396c"

ROUND1_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / ORIGINAL_ROUND1_RUN_ID
MATRIX_FREEZE_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / MATRIX_FREEZE_RUN_ID
CACHE_RECOVERY_ROOT = ROOT / "outputs" / "presignal_v21_immediate_impulse_minute_cache_recovery" / CACHE_RECOVERY_RUN_ID
ENRICHED_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline_enriched"

ENRICHMENT_CONTRACT_VERSION = "presignal_immediate_impulse_minute_enrichment_r1"
DETECTOR_VERSION = "presignal_immediate_impulse_minute_approximation_v1"
EVALUATOR_VERSION = "presignal_immediate_impulse_minute_approximation_eval_v1"
OBSERVATION_CONTRACT_VERSION = "presignal_resolution_aware_market_observation_r1"
ANCHOR_SOURCE = "ORIGINAL_ROUND_1_FROZEN_OUTCOME"

DETECTOR_MODES = {
    "TICK": "STRICT_TICK_UNIMPLEMENTED",
    "ONE_SECOND": "STRICT_ONE_SECOND_UNIMPLEMENTED",
    "FIVE_SECOND": "RESOLUTION_LIMITED_FIVE_SECOND_UNIMPLEMENTED",
    "ONE_MINUTE": "ONE_MINUTE_APPROXIMATION",
    "UNKNOWN": "OUTCOME_UNAVAILABLE",
}
AVAILABILITY_STATUSES = {"STRICT_AVAILABLE", "RESOLUTION_LIMITED", "APPROXIMATION_ONLY", "OUTCOME_UNAVAILABLE"}
SOURCE_RESOLUTIONS = {"TICK", "ONE_SECOND", "FIVE_SECOND", "ONE_MINUTE", "UNKNOWN"}
OBSERVATION_TYPES = {"BBO_QUOTE", "MIDPOINT", "OHLC", "LAST_PRICE", "UNKNOWN"}
PATH_CLASSES = {"CONTINUATION", "REVERSAL", "FLAT_OR_INDETERMINATE", "UNAVAILABLE"}
APPROXIMATION_DIRECTIONS = {"UP", "DOWN", "FLAT", "AMBIGUOUS", "UNAVAILABLE"}
PAIR_CLASSIFICATIONS = {"both correct", "correction", "degradation", "both incorrect", "not evaluable"}
PAIR_TRANSITIONS = {"BOTH_DIRECTIONAL", "BOTH_NO_SIGNAL", "A_NO_SIGNAL_TO_E_DIRECTIONAL", "A_DIRECTIONAL_TO_E_NO_SIGNAL", "PAIR_NOT_EVALUABLE"}


class EnrichmentError(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    timestamp: str
    instrument: str
    provider: str
    source_resolution: str
    observation_type: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    bid: float | None
    ask: float | None
    midpoint: float | None
    source_observation_id: str | None
    request_identity: str
    raw_artifact_reference: str
    raw_artifact_sha256: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_value(value: Any) -> str:
    return "sha256:" + sha256_text(canonical_json(value))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(row) + "\n" for row in rows))


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def round2(value: float) -> float:
    return round(float(value), 2)


def signed_pips(price: float, anchor: float) -> float:
    return round2((price - anchor) / 0.01)


def source_resolution_to_detector_mode(source_resolution: str) -> str:
    return DETECTOR_MODES.get(source_resolution, "OUTCOME_UNAVAILABLE")


def unsupported_detector_result(source_resolution: str) -> dict[str, Any]:
    _require(source_resolution in {"TICK", "ONE_SECOND", "FIVE_SECOND"}, "UNSUPPORTED_STRICT_ROUTE")
    availability = "STRICT_AVAILABLE" if source_resolution in {"TICK", "ONE_SECOND"} else "RESOLUTION_LIMITED"
    return {
        "availability_status": availability,
        "detector_mode": source_resolution_to_detector_mode(source_resolution),
        "outcome_status": "UNIMPLEMENTED_DETECTOR_PATH",
    }


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise EnrichmentError(code)


def enrichment_run_id(now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "PPHB-R1-ENRICHED-IMMEDIATE-IMPULSE-MINUTE-" + stamp + "-" + sha256_text(stamp)[:12]


def forecast_identity_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (record["episode_id"], record["provider"], record["model"], record["information_arm"])


def call_identity_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    arm = "BASELINE" if record["pack_arm"] == "PACK_A" else "FULL_CONTEXT"
    return (record["episode_id"], record["provider"], record["model"], arm)


def load_recovered_observations() -> dict[str, Observation]:
    rows = read_jsonl(CACHE_RECOVERY_ROOT / "normalized_minute_observations.jsonl")
    observations: dict[str, Observation] = {}
    for row in rows:
        observation = Observation(
            timestamp=row["timestamp"],
            instrument=row["instrument"],
            provider=row["provider"],
            source_resolution=row["source_resolution"],
            observation_type=row["observation_type"],
            open=row.get("open"),
            high=row.get("high"),
            low=row.get("low"),
            close=row.get("close"),
            bid=row.get("bid"),
            ask=row.get("ask"),
            midpoint=row.get("midpoint"),
            source_observation_id=row.get("source_observation_id"),
            request_identity=row["request_identity"],
            raw_artifact_reference=row["raw_artifact_reference"],
            raw_artifact_sha256=row["raw_artifact_sha256"],
        )
        observations[observation.timestamp] = observation
    return observations


def load_round1_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    outcomes = sorted(read_jsonl(ROUND1_ROOT / "outcomes" / "outcome_rows.jsonl"), key=lambda row: (row["release_ts"], row["episode_id"]))
    outcome_by_episode = {row["episode_id"]: row for row in outcomes}
    forecasts = []
    for path in sorted((ROUND1_ROOT / "canonical_forecasts").glob("*.json")):
        if path.name.endswith("_paths.jsonl"):
            continue
        forecasts.append(read_json(path))
    forecast_by_identity = {forecast_identity_key(row): row for row in forecasts}
    call_ledger = read_jsonl(ROUND1_ROOT / "call_ledger.jsonl")
    cache_validation = {row["episode_id"]: row for row in read_jsonl(CACHE_RECOVERY_ROOT / "validation_against_round1.jsonl")}
    return outcomes, outcome_by_episode, forecast_by_identity, call_ledger, cache_validation


def verify_recovered_cache(cache_validation: dict[str, dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> None:
    _require(set(cache_validation) == set(outcomes), "CACHE_EPISODE_COVERAGE_MISMATCH")
    for episode_id, row in cache_validation.items():
        _require(row["classification"] in {"EXACT_RECONCILIATION", "EXPLAINED_RECONCILIATION"}, "CACHE_RECONCILIATION_BLOCK:" + episode_id)
        _require(row["anchor_match"]["price_match"] is True and row["anchor_match"]["timestamp_match"] is True, "CACHE_ANCHOR_BLOCK:" + episode_id)
        _require(row["first_minute"]["present"] is True, "CACHE_FIRST_MINUTE_BLOCK:" + episode_id)
        _require(row["second_minute"]["present"] is True, "CACHE_SECOND_MINUTE_BLOCK:" + episode_id)


def approximate_direction(pips: float | None) -> str:
    if pips is None:
        return "UNAVAILABLE"
    result = contract.direction_for_pips(pips)
    return result


def minute_path_class(first_direction: str, second_direction: str, contiguous: bool) -> str:
    if not contiguous:
        return "UNAVAILABLE"
    if first_direction not in {"UP", "DOWN"} or second_direction not in {"UP", "DOWN"}:
        return "FLAT_OR_INDETERMINATE"
    if first_direction == second_direction:
        return "CONTINUATION"
    return "REVERSAL"


def predicted_path_class(prediction: dict[str, Any]) -> str:
    if prediction["no_signal_flag"]:
        return "UNAVAILABLE"
    immediate = prediction.get("immediate_impulse_direction")
    early = prediction.get("early_reaction_5m_direction")
    if immediate not in {"UP", "DOWN", "FLAT"} or early not in {"UP", "DOWN", "FLAT"}:
        return "UNAVAILABLE"
    if immediate == "FLAT" or early == "FLAT":
        return "FLAT_OR_INDETERMINATE"
    return "CONTINUATION" if immediate == early else "REVERSAL"


def build_enriched_outcome_row(
    outcome: dict[str, Any],
    cache_validation: dict[str, Any],
    observations: dict[str, Observation],
    construction_ts: str,
) -> dict[str, Any]:
    episode_id = outcome["episode_id"]
    release_ts = outcome["release_ts"]
    first_ts = cache_validation["first_minute"]["timestamp"]
    second_ts = cache_validation["second_minute"]["timestamp"]
    first = observations.get(first_ts)
    second = observations.get(second_ts)
    _require(first is not None and second is not None, "MISSING_REQUIRED_MINUTES:" + episode_id)

    anchor_price = outcome["anchor_price"]
    anchor_ts = outcome["anchor_price_ts"]
    contiguous = utc(second.timestamp) == utc(first.timestamp).replace(second=0, microsecond=0) + (utc(second.timestamp) - utc(first.timestamp))
    contiguous = contiguous and (utc(second.timestamp) - utc(first.timestamp)).total_seconds() == 60
    first_net_pips = signed_pips(first.close, anchor_price)
    second_net_pips = signed_pips(second.close, anchor_price)
    first_net_direction = approximate_direction(first_net_pips)
    second_net_direction = approximate_direction(second_net_pips)

    up_excursion = max(round2((first.high - anchor_price) / 0.01), 0.0)
    down_excursion = min(round2((first.low - anchor_price) / 0.01), 0.0)
    first_range = round2(up_excursion - down_excursion)
    both_sides = up_excursion >= contract.FLAT_MAX_ABS_PIPS and down_excursion <= -contract.FLAT_MAX_ABS_PIPS

    row = {
        "object": "IMMEDIATE_IMPULSE_MINUTE_OUTCOME",
        "episode_id": episode_id,
        "release_timestamp": release_ts,
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "original_outcome_reference": outcome["outcome_id"],
        "original_outcome_fingerprint": outcome["outcome_fingerprint"],
        "provider": first.provider,
        "instrument": first.instrument,
        "source_resolution": first.source_resolution,
        "observation_type": first.observation_type,
        "detector_mode": source_resolution_to_detector_mode(first.source_resolution),
        "availability_status": "APPROXIMATION_ONLY",
        "anchor_price": anchor_price,
        "anchor_price_ts": anchor_ts,
        "anchor_source": ANCHOR_SOURCE,
        "anchor_reconciliation_status": cache_validation["classification"],
        "first_minute_timestamp": first.timestamp,
        "first_minute_open": first.open,
        "first_minute_high": first.high,
        "first_minute_low": first.low,
        "first_minute_close": first.close,
        "first_minute_net_direction": first_net_direction,
        "first_minute_net_pips": first_net_pips,
        "first_minute_up_excursion_pips": up_excursion,
        "first_minute_down_excursion_pips": down_excursion,
        "first_minute_range_pips": first_range,
        "second_minute_timestamp": second.timestamp,
        "second_minute_open": second.open,
        "second_minute_high": second.high,
        "second_minute_low": second.low,
        "second_minute_close": second.close,
        "two_minute_net_direction": second_net_direction,
        "two_minute_net_pips": second_net_pips,
        "intraminute_sequence_known": not both_sides,
        "ambiguity_reason": "BOTH_SIDES_EXCURSION_ORDER_UNKNOWN" if both_sides else None,
        "minute_resolution_path_class": minute_path_class(first_net_direction, second_net_direction, contiguous),
        "contract_version": ENRICHMENT_CONTRACT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "construction_timestamp": construction_ts,
        "cache_recovery_run_id": CACHE_RECOVERY_RUN_ID,
        "raw_observation_reference": first.raw_artifact_reference,
        "source_request_identity": first.request_identity,
        "source_artifact_sha256": first.raw_artifact_sha256,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
    }
    row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
    return row


def evaluation_row_for_schema_failure(call_row: dict[str, Any], construction_ts: str) -> dict[str, Any]:
    row = {
        "object": "IMMEDIATE_IMPULSE_MINUTE_EVALUATION",
        "call_id": call_row["call_id"],
        "episode_id": call_row["episode_id"],
        "provider": call_row["provider"],
        "model": call_row["model"],
        "information_arm": "BASELINE" if call_row["pack_arm"] == "PACK_A" else "FULL_CONTEXT",
        "pack_arm": call_row["pack_arm"],
        "prediction_id": None,
        "prediction_status": "SCHEMA_FAILURE",
        "no_signal_flag": None,
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "approximation_outcome_reference": call_row["canonical_outcome_id"],
        "availability_status": "OUTCOME_UNAVAILABLE",
        "close_direction_evaluable": False,
        "sequence_unambiguous": None,
        "first_minute_direction_result": "NOT_EVALUABLE",
        "two_minute_direction_result": "NOT_EVALUABLE",
        "one_minute_approximation_direction_result": "NOT_EVALUABLE",
        "sequence_unambiguous_direction_result": "NOT_EVALUABLE",
        "predicted_minute_path_class": "UNAVAILABLE",
        "observed_minute_path_class": "UNAVAILABLE",
        "minute_path_result": "NOT_EVALUABLE",
        "evaluation_status": "SCHEMA_FAILURE",
        "construction_timestamp": construction_ts,
        "contract_version": ENRICHMENT_CONTRACT_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
    }
    row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
    return row


def build_evaluation_row(
    call_row: dict[str, Any],
    forecast: dict[str, Any] | None,
    enriched_outcome: dict[str, Any],
    construction_ts: str,
) -> dict[str, Any]:
    if forecast is None:
        return evaluation_row_for_schema_failure(call_row, construction_ts)

    availability = enriched_outcome["availability_status"]
    sequence_unambiguous = bool(enriched_outcome["intraminute_sequence_known"])
    close_direction = enriched_outcome["first_minute_net_direction"]
    two_minute_direction = enriched_outcome["two_minute_net_direction"]
    observed_path = enriched_outcome["minute_resolution_path_class"]
    immediate_prediction = forecast.get("immediate_impulse_direction")

    close_evaluable = (
        forecast["status"] == "VALID"
        and not forecast["no_signal_flag"]
        and availability == "APPROXIMATION_ONLY"
        and close_direction in {"UP", "DOWN", "FLAT"}
    )
    if forecast["no_signal_flag"]:
        first_result = "NOT_EVALUABLE"
        second_result = "NOT_EVALUABLE"
        approx_result = "NOT_EVALUABLE"
        sequence_result = "NOT_EVALUABLE"
        path_result = "NOT_EVALUABLE"
        predicted_path = "UNAVAILABLE"
        evaluation_status = "VALID_NO_SIGNAL"
    else:
        first_result = "CORRECT" if close_evaluable and immediate_prediction == close_direction else ("INCORRECT" if close_evaluable else "NOT_EVALUABLE")
        second_result = "CORRECT" if close_evaluable and immediate_prediction == two_minute_direction else ("INCORRECT" if close_evaluable else "NOT_EVALUABLE")
        approx_result = first_result
        sequence_result = first_result if close_evaluable and sequence_unambiguous else "NOT_EVALUABLE"
        predicted_path = predicted_path_class(forecast)
        path_result = "CORRECT" if close_evaluable and predicted_path == observed_path else ("INCORRECT" if close_evaluable and predicted_path in {"CONTINUATION", "REVERSAL", "FLAT_OR_INDETERMINATE"} else "NOT_EVALUABLE")
        evaluation_status = "COMPLETED_DIRECTIONAL_FORECAST"

    row = {
        "object": "IMMEDIATE_IMPULSE_MINUTE_EVALUATION",
        "call_id": call_row["call_id"],
        "episode_id": call_row["episode_id"],
        "provider": call_row["provider"],
        "model": call_row["model"],
        "information_arm": forecast["information_arm"],
        "pack_arm": call_row["pack_arm"],
        "prediction_id": forecast["prediction_id"],
        "prediction_status": forecast["status"],
        "no_signal_flag": forecast["no_signal_flag"],
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "approximation_outcome_reference": enriched_outcome["episode_id"],
        "availability_status": availability,
        "close_direction_evaluable": close_evaluable,
        "sequence_unambiguous": sequence_unambiguous if close_evaluable else None,
        "first_minute_direction_result": first_result,
        "two_minute_direction_result": second_result,
        "one_minute_approximation_direction_result": approx_result,
        "sequence_unambiguous_direction_result": sequence_result,
        "predicted_minute_path_class": predicted_path,
        "observed_minute_path_class": observed_path if close_evaluable else "UNAVAILABLE",
        "minute_path_result": path_result,
        "evaluation_status": evaluation_status,
        "construction_timestamp": construction_ts,
        "contract_version": ENRICHMENT_CONTRACT_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
    }
    row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
    return row


def pair_transition_for(base: dict[str, Any] | None, full: dict[str, Any] | None) -> str:
    if not base or not full:
        return "PAIR_NOT_EVALUABLE"
    if base["evaluation_status"] == "SCHEMA_FAILURE" or full["evaluation_status"] == "SCHEMA_FAILURE":
        return "PAIR_NOT_EVALUABLE"
    if base["no_signal_flag"] and full["no_signal_flag"]:
        return "BOTH_NO_SIGNAL"
    if base["no_signal_flag"] and not full["no_signal_flag"]:
        return "A_NO_SIGNAL_TO_E_DIRECTIONAL"
    if not base["no_signal_flag"] and full["no_signal_flag"]:
        return "A_DIRECTIONAL_TO_E_NO_SIGNAL"
    if not base["no_signal_flag"] and not full["no_signal_flag"]:
        return "BOTH_DIRECTIONAL"
    return "PAIR_NOT_EVALUABLE"


def pair_classification(a_result: str, e_result: str) -> str:
    if a_result not in {"CORRECT", "INCORRECT"} or e_result not in {"CORRECT", "INCORRECT"}:
        return "not evaluable"
    if a_result == "CORRECT" and e_result == "CORRECT":
        return "both correct"
    if a_result == "INCORRECT" and e_result == "CORRECT":
        return "correction"
    if a_result == "CORRECT" and e_result == "INCORRECT":
        return "degradation"
    return "both incorrect"


def build_pair_rows(evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in evaluations:
        grouped[(row["episode_id"], row["provider"], row["model"])][row["information_arm"]] = row

    rows = []
    for (episode_id, provider, model), arms in sorted(grouped.items()):
        base = arms.get("BASELINE")
        full = arms.get("FULL_CONTEXT")
        row = {
            "object": "IMMEDIATE_IMPULSE_MINUTE_PAIR_COMPARISON",
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "baseline_prediction_id": None if not base else base["prediction_id"],
            "full_context_prediction_id": None if not full else full["prediction_id"],
            "pair_transition": pair_transition_for(base, full),
            "all_close_direction_evaluable_pair_classification": "not evaluable" if not base or not full else pair_classification(base["one_minute_approximation_direction_result"], full["one_minute_approximation_direction_result"]),
            "sequence_unambiguous_pair_classification": "not evaluable" if not base or not full else pair_classification(base["sequence_unambiguous_direction_result"], full["sequence_unambiguous_direction_result"]),
            "construction_timestamp": base["construction_timestamp"] if base else (full["construction_timestamp"] if full else ""),
            "contract_version": ENRICHMENT_CONTRACT_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
        }
        row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
        rows.append(row)
    return rows


def _ratio(correct: int, total: int) -> float | None:
    return None if total == 0 else round(correct / total, 6)


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    close_rows = [row for row in rows if row["one_minute_approximation_direction_result"] in {"CORRECT", "INCORRECT"}]
    sequence_rows = [row for row in rows if row["sequence_unambiguous_direction_result"] in {"CORRECT", "INCORRECT"}]
    continuation_rows = [row for row in rows if row["observed_minute_path_class"] == "CONTINUATION" and row["predicted_minute_path_class"] in {"CONTINUATION", "REVERSAL", "FLAT_OR_INDETERMINATE"}]
    reversal_rows = [row for row in rows if row["observed_minute_path_class"] == "REVERSAL" and row["predicted_minute_path_class"] in {"CONTINUATION", "REVERSAL", "FLAT_OR_INDETERMINATE"}]
    return {
        "directional_forecast_count": sum(row["evaluation_status"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in rows),
        "valid_no_signal_count": sum(row["evaluation_status"] == "VALID_NO_SIGNAL" for row in rows),
        "schema_failure_count": sum(row["evaluation_status"] == "SCHEMA_FAILURE" for row in rows),
        "approximation_evaluable_count": len(close_rows),
        "sequence_unambiguous_count": len(sequence_rows),
        "ambiguous_bar_count": sum(row["close_direction_evaluable"] and row["sequence_unambiguous"] is False for row in rows),
        "first_minute_net_directional_accuracy": _ratio(sum(row["first_minute_direction_result"] == "CORRECT" for row in close_rows), len(close_rows)),
        "two_minute_net_directional_accuracy": _ratio(sum(row["two_minute_direction_result"] == "CORRECT" for row in close_rows), len(close_rows)),
        "one_minute_approximation_directional_accuracy": _ratio(sum(row["one_minute_approximation_direction_result"] == "CORRECT" for row in close_rows), len(close_rows)),
        "sequence_unambiguous_approximation_directional_accuracy": _ratio(sum(row["sequence_unambiguous_direction_result"] == "CORRECT" for row in sequence_rows), len(sequence_rows)),
        "minute_resolution_continuation_accuracy": _ratio(sum(row["predicted_minute_path_class"] == "CONTINUATION" for row in continuation_rows), len(continuation_rows)),
        "minute_resolution_reversal_accuracy": _ratio(sum(row["predicted_minute_path_class"] == "REVERSAL" for row in reversal_rows), len(reversal_rows)),
    }


def build_summary(
    enriched_outcomes: list[dict[str, Any]],
    evaluations: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    call_ledger: list[dict[str, Any]],
    run_id: str,
    construction_ts: str,
    source_head: str,
) -> tuple[dict[str, Any], str]:
    total_arms = len(call_ledger)
    schema_failures = sum(row["evaluation_status"] == "SCHEMA_FAILURE" for row in evaluations)
    no_signals = sum(row["evaluation_status"] == "VALID_NO_SIGNAL" for row in evaluations)
    directional = sum(row["evaluation_status"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in evaluations)
    ambiguous = sum(row["close_direction_evaluable"] and row["sequence_unambiguous"] is False for row in evaluations)
    sequence_unambiguous = sum(row["sequence_unambiguous_direction_result"] in {"CORRECT", "INCORRECT"} for row in evaluations)
    close_evaluable = sum(row["one_minute_approximation_direction_result"] in {"CORRECT", "INCORRECT"} for row in evaluations)

    directional_rows = [row for row in evaluations if row["evaluation_status"] == "COMPLETED_DIRECTIONAL_FORECAST"]
    by_provider = {provider: metric_block([row for row in evaluations if row["provider"] == provider]) for provider in sorted({row["provider"] for row in evaluations})}
    by_pack = {arm: metric_block([row for row in evaluations if row["information_arm"] == arm]) for arm in ("BASELINE", "FULL_CONTEXT")}

    pair_all = Counter(row["all_close_direction_evaluable_pair_classification"] for row in pair_rows)
    pair_unambiguous = Counter(row["sequence_unambiguous_pair_classification"] for row in pair_rows)

    summary = {
        "run_id": run_id,
        "source_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "source_matrix_freeze_id": MATRIX_FREEZE_RUN_ID,
        "cache_recovery_run_id": CACHE_RECOVERY_RUN_ID,
        "contract_version": ENRICHMENT_CONTRACT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "construction_timestamp": construction_ts,
        "git_head": source_head,
        "t15_primary_status": "UNCHANGED",
        "scientific_availability_decision": "APPROXIMATION_ONLY_AVAILABLE",
        "total_forecast_arms": total_arms,
        "directional_immediate_impulse_predictions": directional,
        "no_signal_arms": no_signals,
        "schema_invalid_arms": schema_failures,
        "approximation_evaluable_arms": close_evaluable,
        "ambiguous_bar_arms": ambiguous,
        "unavailable_arms": sum(row["availability_status"] == "OUTCOME_UNAVAILABLE" for row in evaluations),
        "all_close_direction_evaluable_arms": close_evaluable,
        "sequence_unambiguous_arms": sequence_unambiguous,
        "overall_approximation_results": metric_block(evaluations),
        "gemini_approximation_results": by_provider.get("Gemini", {}),
        "openai_approximation_results": by_provider.get("OpenAI", {}),
        "pack_a_approximation_results": by_pack["BASELINE"],
        "pack_e_approximation_results": by_pack["FULL_CONTEXT"],
        "paired_pack_results": {
            "all_close_direction_evaluable_pairs": dict(pair_all),
            "sequence_unambiguous_pairs": dict(pair_unambiguous),
            "pair_transition_counts": dict(Counter(row["pair_transition"] for row in pair_rows)),
        },
    }

    summary_md = "\n".join([
        "# Round 1 Enriched Immediate Impulse Minute Approximation",
        "",
        f"- Enriched run: `{run_id}`",
        f"- Source Round 1: `{ORIGINAL_ROUND1_RUN_ID}`",
        f"- Source cache recovery: `{CACHE_RECOVERY_RUN_ID}`",
        "- T+15 remains the primary endpoint.",
        "- Immediate Impulse is secondary.",
        "- These Immediate Impulse Outcomes are one-minute approximations.",
        "- True sub-minute first-move ordering is unavailable.",
        "- The enriched release does not modify or replace the original Round 1 release.",
        "",
        "## Denominators",
        f"- Total forecast arms: {total_arms}",
        f"- Directional Immediate Impulse predictions: {directional}",
        f"- NO_SIGNAL arms: {no_signals}",
        f"- Schema-invalid arms: {schema_failures}",
        f"- Approximation-evaluable arms: {close_evaluable}",
        f"- Sequence-ambiguous arms: {ambiguous}",
        f"- Sequence-unambiguous arms: {sequence_unambiguous}",
        "",
        "## Overall",
        f"- First-minute net directional accuracy: {summary['overall_approximation_results']['first_minute_net_directional_accuracy']}",
        f"- Two-minute net directional accuracy: {summary['overall_approximation_results']['two_minute_net_directional_accuracy']}",
        f"- One-minute approximation directional accuracy: {summary['overall_approximation_results']['one_minute_approximation_directional_accuracy']}",
        f"- Sequence-unambiguous approximation directional accuracy: {summary['overall_approximation_results']['sequence_unambiguous_approximation_directional_accuracy']}",
    ]) + "\n"
    return summary, summary_md


def build_checksums(run_dir: Path) -> dict[str, str]:
    checksums = {}
    for path in sorted(run_dir.iterdir()):
        if path.is_file():
            checksums[path.name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return checksums


def run_enrichment(output_root: Path | None = None) -> dict[str, Any]:
    source_head = ""
    try:
        import subprocess
        source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        git_ref = ROOT / ".git"
        if git_ref.exists():
            source_head = sha256_text(git_ref.read_text())

    cache_manifest = read_json(CACHE_RECOVERY_ROOT / "run_manifest.json")
    _require(cache_manifest["recovered_cache_decision"] == "RECOVERED_CACHE_ADMISSIBLE", "CACHE_NOT_ADMISSIBLE")
    _require(cache_manifest["provider"] == "tiingo", "CACHE_PROVIDER")
    _require(cache_manifest["source_resolution"] == "ONE_MINUTE", "CACHE_RESOLUTION")

    observations = load_recovered_observations()
    outcomes, outcome_by_episode, forecast_by_identity, call_ledger, cache_validation = load_round1_inputs()
    verify_recovered_cache(cache_validation, outcome_by_episode)

    construction_ts = iso(datetime.now(timezone.utc))
    run_id = enrichment_run_id(datetime.now(timezone.utc))
    run_dir = (output_root or ENRICHED_ROOT) / run_id

    enriched_outcomes = [
        build_enriched_outcome_row(outcome, cache_validation[outcome["episode_id"]], observations, construction_ts)
        for outcome in outcomes
    ]
    enriched_outcome_by_episode = {row["episode_id"]: row for row in enriched_outcomes}

    evaluations = []
    for call_row in sorted(call_ledger, key=lambda row: row["call_index"]):
        key = call_identity_key(call_row)
        forecast = forecast_by_identity.get(key)
        evaluations.append(build_evaluation_row(call_row, forecast, enriched_outcome_by_episode[call_row["episode_id"]], construction_ts))

    pair_rows = build_pair_rows(evaluations)
    summary_json, summary_md = build_summary(enriched_outcomes, evaluations, pair_rows, call_ledger, run_id, construction_ts, source_head)

    manifest = {
        "run_id": run_id,
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "original_matrix_freeze_run_id": MATRIX_FREEZE_RUN_ID,
        "cache_recovery_run_id": CACHE_RECOVERY_RUN_ID,
        "contract_version": ENRICHMENT_CONTRACT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "git_head": source_head,
        "construction_timestamp": construction_ts,
        "coverage_statement": "T+15 remains the primary endpoint. Immediate Impulse is secondary. The present Immediate Impulse Outcomes are one-minute approximations. True sub-minute first-move ordering is unavailable. The enriched release does not modify or replace the original Round 1 release.",
        "record_counts": {
            "immediate_impulse_outcome_rows": len(enriched_outcomes),
            "immediate_impulse_evaluation_rows": len(evaluations),
            "paired_pack_comparison_rows": len(pair_rows),
        },
        "source_checks": {
            "cache_recovered_admissible": cache_manifest["recovered_cache_decision"],
            "unexplained_cache_mismatches": cache_manifest["mismatch_count"],
            "missing_cache_observations": cache_manifest["missing_count"],
        },
        "scientific_availability_decision": "APPROXIMATION_ONLY_AVAILABLE",
        "t15_primary_status": "UNCHANGED",
    }

    write_json(run_dir / "run_manifest.json", manifest)
    write_jsonl(run_dir / "immediate_impulse_outcome_rows.jsonl", enriched_outcomes)
    write_jsonl(run_dir / "immediate_impulse_evaluation_rows.jsonl", evaluations)
    write_jsonl(run_dir / "paired_pack_comparison_rows.jsonl", pair_rows)
    write_json(run_dir / "summary.json", summary_json)
    (run_dir / "summary.md").write_text(summary_md)
    checksums = build_checksums(run_dir)
    write_json(run_dir / "checksums.json", checksums)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ENRICHED_ROOT)
    args = parser.parse_args()
    print(json.dumps(run_enrichment(args.output_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
