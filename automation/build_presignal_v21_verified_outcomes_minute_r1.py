#!/usr/bin/env python3
"""Build a verified multi-provider minute Outcome release for Round 1.

This tool is intentionally additive:

original Round 1
-> seven-day all-available historical acquisition
-> provider normalization and verification
-> verified minute outcomes
-> verified T+15 / Immediate Impulse approximation evaluations
-> new verified release
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract  # noqa: E402
from automation.google_clients import build_script_service, load_credentials, run_script_function_with_metadata  # noqa: E402


ORIGINAL_ROUND1_RUN_ID = "PPHB-R1-FULL-20260726T160036Z-ca5d238916f1"
MATRIX_FREEZE_RUN_ID = "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"
TIINGO_RECOVERY_RUN_ID = "PPHB-R1-TIINGO-MINUTE-CACHE-RECOVERY-20260727T081850Z-66c010cb396c"
TIINGO_ONLY_BASELINE_RUN_ID = "PPHB-R1-ENRICHED-IMMEDIATE-IMPULSE-MINUTE-CORRECTED-20260727T092519Z-71c52d96c595"

ROUND1_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / ORIGINAL_ROUND1_RUN_ID
MATRIX_FREEZE_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / MATRIX_FREEZE_RUN_ID
TIINGO_RECOVERY_ROOT = ROOT / "outputs" / "presignal_v21_immediate_impulse_minute_cache_recovery" / TIINGO_RECOVERY_RUN_ID
TIINGO_ONLY_BASELINE_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline_enriched" / TIINGO_ONLY_BASELINE_RUN_ID

ACQUISITION_ROOT = ROOT / "outputs" / "presignal_v21_multi_provider_minute_verification_acquisition"
VERIFIED_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline_verified"

TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
ENDPOINT_DEPLOYMENT = "AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN"
ENDPOINT_FUNCTION = "apiFetchGovernedHistoricalUsdJpyObservation"
APPS_SCRIPT_VERSION = 82
INSTRUMENT = "USD/JPY"

AUTHORIZED_PROVIDERS = ("tiingo", "eodhd", "twelvedata")
ENDPOINT_PROVIDER_ORDER = ("tiingo", "eodhd", "massive", "twelvedata")
UTC_DAYS = (
    "2024-05-08",
    "2024-05-09",
    "2024-05-10",
    "2024-05-14",
    "2024-05-15",
    "2024-05-16",
    "2024-05-20",
)
TARGET_ORDER = ("anchor", "first_minute", "second_minute", "5m", "15m", "30m", "60m")
QUALITY_STATUSES = (
    "MULTI_SOURCE_CONFIRMED",
    "MULTI_SOURCE_CONSENSUS",
    "SINGLE_SOURCE_ONLY",
    "SOURCE_DISAGREEMENT",
    "OUTCOME_UNAVAILABLE",
)
SOURCE_RESOLUTIONS = {"TICK", "ONE_SECOND", "FIVE_SECOND", "ONE_MINUTE", "UNKNOWN"}
OBSERVATION_TYPES = {"BBO_QUOTE", "MIDPOINT", "OHLC", "LAST_PRICE", "UNKNOWN"}
PAIR_CLASSIFICATIONS = ("both correct", "correction", "degradation", "both incorrect", "not evaluable")
PAIR_TRANSITIONS = ("BOTH_DIRECTIONAL", "BOTH_NO_SIGNAL", "A_NO_SIGNAL_TO_E_DIRECTIONAL", "A_DIRECTIONAL_TO_E_NO_SIGNAL", "PAIR_NOT_EVALUABLE")

VERIFICATION_CONTRACT_VERSION = "presignal_multi_provider_minute_verification_r1"
OBSERVATION_CONTRACT_VERSION = "presignal_resolution_aware_market_observation_r1"
VERIFIED_OUTCOME_CONTRACT_VERSION = "presignal_verified_minute_outcomes_r1"
IMMEDIATE_EVALUATOR_VERSION = "presignal_verified_immediate_impulse_minute_eval_r1"
T15_EVALUATOR_VERSION = "presignal_verified_event_path_eval_r1"
DETECTOR_VERSION = "presignal_immediate_impulse_minute_approximation_v1"
ANCHOR_SOURCE = "VERIFIED_MULTI_PROVIDER_MINUTE_OUTCOME"
SUPERSESSION_REASON = "SINGLE_SOURCE_MARKET_DATA_NOT_INDEPENDENTLY_VERIFIED"


class VerifiedBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderObservation:
    provider: str
    day: str
    timestamp: str
    timestamp_raw: str | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    bid: float | None
    ask: float | None
    midpoint: float | None
    accepted_comparison_field: str
    accepted_comparison_value: float | None
    source_resolution: str
    observation_type: str
    instrument: str
    raw_artifact_reference: str
    raw_artifact_sha256: str
    retrieval_timestamp: str
    request_identity: str


@dataclass(frozen=True)
class VerifiedPoint:
    provider: str
    target: str
    timestamp: str
    price: float
    direction: str
    pips: float
    observation: ProviderObservation
    anchor_timestamp: str


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


def reaction_flat_threshold_pips() -> float:
    return float(contract.FLAT_MAX_ABS_PIPS)


def direction_from_pips(pips: float | None, threshold: float | None = None) -> str:
    if pips is None:
        return "flat"
    limit = reaction_flat_threshold_pips() if threshold is None else float(threshold)
    if abs(float(pips)) < limit:
        return "flat"
    return "up" if float(pips) > 0 else "down"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise VerifiedBuildError(code)


def acquisition_run_id(now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "PPHB-R1-MULTI-PROVIDER-MINUTE-VERIFICATION-ACQUISITION-" + stamp + "-" + sha256_text(stamp)[:12]


def verified_run_id(now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "PPHB-R1-VERIFIED-OUTCOMES-MINUTE-" + stamp + "-" + sha256_text(stamp)[:12]


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def request_day_manifest() -> list[dict[str, Any]]:
    return [
        {
            "day": day,
            "request_id": "MD_VERIFY_" + sha256_text(day)[:20],
            "request_mode": "all_available",
            "requested_window_start": f"{day}T00:00:00Z",
            "requested_window_end": f"{day}T23:59:00Z",
        }
        for day in UTC_DAYS
    ]


def load_round1_inputs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    outcomes = sorted(read_jsonl(ROUND1_ROOT / "outcomes" / "outcome_rows.jsonl"), key=lambda row: (row["release_ts"], row["episode_id"]))
    outcome_by_episode = {row["episode_id"]: row for row in outcomes}
    forecasts = []
    for path in sorted((ROUND1_ROOT / "canonical_forecasts").glob("*.json")):
        if path.name.endswith("_paths.jsonl"):
            continue
        forecasts.append(read_json(path))
    forecast_by_identity = {(row["episode_id"], row["provider"], row["model"], row["information_arm"]): row for row in forecasts}
    call_ledger = read_jsonl(ROUND1_ROOT / "call_ledger.jsonl")
    original_evaluations = []
    for path in sorted((ROUND1_ROOT / "evaluations").glob("*.json")):
        original_evaluations.append(read_json(path))
    original_pairs = []
    for path in sorted((ROUND1_ROOT / "pair_comparisons").glob("*.json")):
        original_pairs.append(read_json(path))
    cache_validation = {row["episode_id"]: row for row in read_jsonl(TIINGO_RECOVERY_ROOT / "validation_against_round1.jsonl")}
    return outcomes, outcome_by_episode, forecast_by_identity, call_ledger, original_evaluations, original_pairs, cache_validation


def verify_static_inputs(outcomes: list[dict[str, Any]], cache_validation: Mapping[str, dict[str, Any]]) -> None:
    _require(len(outcomes) == 47, "ROUND1_OUTCOME_COUNT_UNEXPECTED")
    _require(set(row["episode_id"] for row in outcomes) == set(cache_validation), "CACHE_VALIDATION_EPISODE_MISMATCH")
    recovered_days = sorted({row["release_ts"][:10] for row in outcomes})
    _require(recovered_days == list(UTC_DAYS), "ROUND1_DAY_SET_MISMATCH")


def normalize_provider_observation(day: str, provider_result: Mapping[str, Any], observation: Mapping[str, Any], raw_relpath: str, raw_sha: str, retrieval_ts: str, request_identity: str) -> ProviderObservation:
    resolution = str(provider_result.get("source_resolution") or "UNKNOWN")
    obs_type = str(provider_result.get("observation_type") or "UNKNOWN")
    _require(resolution in SOURCE_RESOLUTIONS, "UNKNOWN_SOURCE_RESOLUTION:" + resolution)
    _require(obs_type in OBSERVATION_TYPES, "UNKNOWN_OBSERVATION_TYPE:" + obs_type)
    accepted_field = str(observation.get("accepted_raw_price_field") or "close")
    accepted_value = observation.get("accepted_raw_price")
    return ProviderObservation(
        provider=str(provider_result["provider"]),
        day=day,
        timestamp=str(observation["timestamp"]),
        timestamp_raw=None if observation.get("timestamp_raw") is None else str(observation.get("timestamp_raw")),
        open=observation.get("open"),
        high=observation.get("high"),
        low=observation.get("low"),
        close=observation.get("close"),
        bid=observation.get("bid"),
        ask=observation.get("ask"),
        midpoint=observation.get("midpoint"),
        accepted_comparison_field=accepted_field,
        accepted_comparison_value=None if accepted_value is None else float(accepted_value),
        source_resolution=resolution,
        observation_type=obs_type,
        instrument=str(provider_result["instrument"]),
        raw_artifact_reference=raw_relpath,
        raw_artifact_sha256=raw_sha,
        retrieval_timestamp=retrieval_ts,
        request_identity=request_identity,
    )


def run_acquisition(output_root: Path = ACQUISITION_ROOT) -> tuple[Path, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], ProviderObservation]]:
    manifest_rows = request_day_manifest()
    creds = load_credentials(token_path=TOKEN_PATH, persist_refresh=False)
    service = build_script_service(creds)
    now = datetime.now(timezone.utc)
    run_id = acquisition_run_id(now)
    run_dir = output_root / run_id
    raw_dir = run_dir / "raw_responses"
    request_records: list[dict[str, Any]] = []
    normalized_rows: list[dict[str, Any]] = []
    day_coverage_rows: list[dict[str, Any]] = []
    observation_index: dict[tuple[str, str], ProviderObservation] = {}

    for day_row in manifest_rows:
        params = {
            "request_identity": day_row["request_id"],
            "instrument": INSTRUMENT,
            "requested_window_start": day_row["requested_window_start"],
            "requested_window_end": day_row["requested_window_end"],
            "timezone": "UTC",
            "mode": "all_available",
        }
        result = run_script_function_with_metadata(service, ENDPOINT_DEPLOYMENT, ENDPOINT_FUNCTION, [params], dev_mode=True)
        retrieval_ts = iso(datetime.now(timezone.utc))
        raw_payload = canonical_json(result)
        raw_name = f"{day_row['day']}_{day_row['request_id']}.json"
        raw_path = raw_dir / raw_name
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_payload + "\n")
        raw_relpath = str(raw_path.relative_to(ROOT))
        raw_sha = "sha256:" + sha256_text(raw_payload)
        _require(result.get("ok") is True, "ACQUISITION_TRANSPORT_FAILURE:" + day_row["day"])
        payload = result["response"]["response"]["result"]
        provider_results = payload.get("provider_results") or []
        _require([row["provider"] for row in provider_results] == list(ENDPOINT_PROVIDER_ORDER), "PROVIDER_ORDER_CHANGED:" + day_row["day"])

        request_records.append({
            **day_row,
            "endpoint_deployment_identity": ENDPOINT_DEPLOYMENT,
            "apps_script_version": APPS_SCRIPT_VERSION,
            "elapsed_ms": result["elapsed_ms"],
            "retrieval_timestamp": retrieval_ts,
            "raw_response_path": raw_relpath,
            "raw_response_sha256": raw_sha,
            "status": payload["status"],
            "comparable_provider_count": payload.get("comparable_provider_count", 0),
        })

        for provider_result in provider_results:
            provider = str(provider_result["provider"])
            observations = provider_result.get("observations") or []
            coverage_row = {
                "day": day_row["day"],
                "provider": provider,
                "status": provider_result["status"],
                "request_start": provider_result["request_start"],
                "request_end": provider_result["request_end"],
                "source_resolution": provider_result["source_resolution"],
                "observation_type": provider_result["observation_type"],
                "observation_count": provider_result["observation_count"],
                "first_timestamp": observations[0]["timestamp"] if observations else None,
                "last_timestamp": observations[-1]["timestamp"] if observations else None,
                "error_code": provider_result.get("error_code"),
                "error_summary": provider_result.get("error_summary"),
                "credential_route_present": bool(provider_result.get("credential_route_present")),
                "raw_response_path": raw_relpath,
                "raw_response_sha256": raw_sha,
                "retrieval_timestamp": retrieval_ts,
            }
            day_coverage_rows.append(coverage_row)
            if provider not in AUTHORIZED_PROVIDERS or provider_result["status"] != "SUCCESS":
                continue
            for observation in observations:
                normalized = normalize_provider_observation(day_row["day"], provider_result, observation, raw_relpath, raw_sha, retrieval_ts, day_row["request_id"])
                key = (provider, normalized.timestamp)
                if key in observation_index:
                    continue
                observation_index[key] = normalized
                normalized_rows.append({
                    "provider": normalized.provider,
                    "day": normalized.day,
                    "timestamp": normalized.timestamp,
                    "timestamp_raw": normalized.timestamp_raw,
                    "open": normalized.open,
                    "high": normalized.high,
                    "low": normalized.low,
                    "close": normalized.close,
                    "bid": normalized.bid,
                    "ask": normalized.ask,
                    "midpoint": normalized.midpoint,
                    "accepted_comparison_field": normalized.accepted_comparison_field,
                    "accepted_comparison_value": normalized.accepted_comparison_value,
                    "source_resolution": normalized.source_resolution,
                    "observation_type": normalized.observation_type,
                    "instrument": normalized.instrument,
                    "request_identity": normalized.request_identity,
                    "raw_artifact_reference": normalized.raw_artifact_reference,
                    "raw_artifact_sha256": normalized.raw_artifact_sha256,
                    "retrieval_timestamp": normalized.retrieval_timestamp,
                })

    normalized_rows.sort(key=lambda row: (row["provider"], row["timestamp"]))
    write_json(run_dir / "run_manifest.json", {
        "run_id": run_id,
        "days": list(UTC_DAYS),
        "request_count": len(manifest_rows),
        "endpoint_deployment_identity": ENDPOINT_DEPLOYMENT,
        "apps_script_version": APPS_SCRIPT_VERSION,
        "source_commit": git_head(),
        "provider_order": list(ENDPOINT_PROVIDER_ORDER),
        "authorized_providers": list(AUTHORIZED_PROVIDERS),
        "no_ai_forecast_calls": True,
        "no_google_workbook_writes": True,
    })
    write_jsonl(run_dir / "provider_request_manifest.jsonl", request_records)
    write_jsonl(run_dir / "normalized_provider_observations.jsonl", normalized_rows)
    write_jsonl(run_dir / "provider_day_coverage.jsonl", day_coverage_rows)
    write_json(run_dir / "checksums.json", {
        "provider_request_manifest.jsonl": sha256_value(request_records),
        "normalized_provider_observations.jsonl": sha256_value(normalized_rows),
        "provider_day_coverage.jsonl": sha256_value(day_coverage_rows),
    })
    (run_dir / "summary.md").write_text(
        "# Multi-provider minute verification acquisition\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Days: {', '.join(UTC_DAYS)}\n"
        f"- Comparable providers available in bounded probe: tiingo, eodhd, twelvedata\n"
        f"- Massive remained preserved as transport failure when unavailable.\n"
    )
    return run_dir, read_json(run_dir / "run_manifest.json"), request_records, day_coverage_rows, observation_index


def reaction_distance(left: VerifiedPoint, right: VerifiedPoint) -> dict[str, float | None]:
    return {
        "anchor_delta_min": abs((utc(left.anchor_timestamp) - utc(right.anchor_timestamp)).total_seconds()) / 60.0 if left.anchor_timestamp and right.anchor_timestamp else None,
        "pips_delta": abs(left.pips - right.pips),
    }


def points_agree(left: VerifiedPoint, right: VerifiedPoint) -> bool:
    if left.direction != right.direction:
        return False
    dist = reaction_distance(left, right)
    return (
        dist["anchor_delta_min"] is not None
        and dist["pips_delta"] is not None
        and dist["anchor_delta_min"] <= 1.0
        and dist["pips_delta"] <= 3.0
    )


def clustered_subset(points: list[VerifiedPoint]) -> list[VerifiedPoint]:
    if len(points) < 2:
        return []
    best: list[VerifiedPoint] = []
    best_score = float("inf")
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            left, right = points[i], points[j]
            if not points_agree(left, right):
                continue
            cluster = [left, right]
            for k, candidate in enumerate(points):
                if k in (i, j):
                    continue
                if all(points_agree(candidate, member) for member in cluster):
                    cluster.append(candidate)
            score = 0.0
            for a in range(len(cluster)):
                for b in range(a + 1, len(cluster)):
                    dist = reaction_distance(cluster[a], cluster[b])
                    score += float(dist["anchor_delta_min"]) * 10.0 + float(dist["pips_delta"])
            if len(cluster) > len(best) or (len(cluster) == len(best) and score < best_score):
                best = cluster
                best_score = score
    return best


def representative_point(points: list[VerifiedPoint]) -> VerifiedPoint | None:
    if not points:
        return None
    if len(points) == 1:
        return points[0]
    best = points[0]
    best_score = float("inf")
    for candidate in points:
        score = 0.0
        for other in points:
            if candidate is other:
                continue
            dist = reaction_distance(candidate, other)
            score += float(dist["anchor_delta_min"] or 999.0) * 10.0 + float(dist["pips_delta"] or 999.0)
        if score < best_score:
            best = candidate
            best_score = score
    return best


def build_verified_point(provider: str, target: str, target_ts: str, anchor_observation: ProviderObservation | None, target_observation: ProviderObservation | None) -> VerifiedPoint | None:
    if anchor_observation is None or target_observation is None:
        return None
    anchor_price = anchor_observation.accepted_comparison_value
    target_price = target_observation.accepted_comparison_value
    if anchor_price is None or target_price is None:
        return None
    pips = signed_pips(target_price, anchor_price)
    return VerifiedPoint(
        provider=provider,
        target=target,
        timestamp=target_observation.timestamp,
        price=target_price,
        direction=direction_from_pips(pips),
        pips=pips,
        observation=target_observation,
        anchor_timestamp=anchor_observation.timestamp,
    )


def classify_target(primary_point: VerifiedPoint | None, compare_points: list[VerifiedPoint]) -> tuple[str, VerifiedPoint | None, str, list[str], list[str]]:
    available = ([primary_point] if primary_point else []) + compare_points
    if not available:
        return "OUTCOME_UNAVAILABLE", None, "no provider observations available", [], []
    if len(available) == 1:
        point = available[0]
        return "SINGLE_SOURCE_ONLY", point, "only one provider available", [point.provider], []

    agreeing_with_primary = [point.provider for point in compare_points if primary_point and points_agree(primary_point, point)]
    contradicting_primary = [point.provider for point in compare_points if primary_point and not points_agree(primary_point, point)]
    if primary_point and agreeing_with_primary and not contradicting_primary:
        return "MULTI_SOURCE_CONFIRMED", primary_point, "primary confirmed by independent provider", [primary_point.provider] + agreeing_with_primary, []

    cluster = clustered_subset(compare_points)
    if len(cluster) >= 2:
        representative = representative_point(cluster)
        if primary_point is None:
            return "MULTI_SOURCE_CONSENSUS", representative, "compare providers clustered without primary", [point.provider for point in cluster], []
        primary_distances = [reaction_distance(primary_point, point) for point in cluster]
        primary_outlier = all(
            ((dist["anchor_delta_min"] is not None and dist["anchor_delta_min"] >= 1.0) or (dist["pips_delta"] is not None and dist["pips_delta"] >= 5.0))
            for dist in primary_distances
        )
        if primary_outlier:
            outliers = [primary_point.provider] + [point.provider for point in compare_points if point not in cluster]
            return "MULTI_SOURCE_CONSENSUS", representative, "compare-provider cluster override", [point.provider for point in cluster], outliers

    if primary_point and agreeing_with_primary:
        return "MULTI_SOURCE_CONFIRMED", primary_point, "primary confirmed with remaining providers unavailable or non-comparable", [primary_point.provider] + agreeing_with_primary, contradicting_primary
    return "SOURCE_DISAGREEMENT", None, "providers disagree without valid consensus", [point.provider for point in available], []


def target_timestamp_map(outcome: Mapping[str, Any], cache_row: Mapping[str, Any]) -> dict[str, str]:
    release = utc(outcome["release_ts"])
    return {
        "anchor": iso(utc(outcome["anchor_price_ts"])),
        "first_minute": iso(utc(cache_row["first_minute"]["timestamp"])),
        "second_minute": iso(utc(cache_row["second_minute"]["timestamp"])),
        "5m": iso(utc(outcome["source_lineage"]["horizon_observation_ts"]["5"])),
        "15m": iso(utc(outcome["source_lineage"]["horizon_observation_ts"]["15"])),
        "30m": iso(utc(outcome["source_lineage"]["horizon_observation_ts"]["30"])),
        "60m": iso(utc(outcome["source_lineage"]["horizon_observation_ts"]["60"])),
        "release": iso(release),
    }


def load_acquisition_run(acquisition_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, str], ProviderObservation]]:
    manifest = read_json(acquisition_dir / "run_manifest.json")
    request_rows = read_jsonl(acquisition_dir / "provider_request_manifest.jsonl")
    day_coverage_rows = read_jsonl(acquisition_dir / "provider_day_coverage.jsonl")
    normalized_rows = read_jsonl(acquisition_dir / "normalized_provider_observations.jsonl")
    observation_index: dict[tuple[str, str], ProviderObservation] = {}
    for row in normalized_rows:
        observation = ProviderObservation(
            provider=row["provider"],
            day=row["day"],
            timestamp=iso(utc(row["timestamp"])),
            timestamp_raw=row.get("timestamp_raw"),
            open=row.get("open"),
            high=row.get("high"),
            low=row.get("low"),
            close=row.get("close"),
            bid=row.get("bid"),
            ask=row.get("ask"),
            midpoint=row.get("midpoint"),
            accepted_comparison_field=row["accepted_comparison_field"],
            accepted_comparison_value=row.get("accepted_comparison_value"),
            source_resolution=row["source_resolution"],
            observation_type=row["observation_type"],
            instrument=row["instrument"],
            raw_artifact_reference=row["raw_artifact_reference"],
            raw_artifact_sha256=row["raw_artifact_sha256"],
            retrieval_timestamp=row["retrieval_timestamp"],
            request_identity=row["request_identity"],
        )
        observation_index[(observation.provider, observation.timestamp)] = observation
    return manifest, request_rows, day_coverage_rows, observation_index


def verify_episode_targets(
    outcome: Mapping[str, Any],
    cache_row: Mapping[str, Any],
    observations: Mapping[tuple[str, str], ProviderObservation],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episode_id = str(outcome["episode_id"])
    release_ts = str(outcome["release_ts"])
    timestamps = target_timestamp_map(outcome, cache_row)
    rows: list[dict[str, Any]] = []
    accepted_points: dict[str, Any] = {}

    anchor_by_provider = {provider: observations.get((provider, timestamps["anchor"])) for provider in AUTHORIZED_PROVIDERS}
    release_ts_text = timestamps["release"]
    for target in TARGET_ORDER:
        target_ts = timestamps["anchor"] if target == "anchor" else timestamps[target]
        points: list[VerifiedPoint] = []
        for provider in AUTHORIZED_PROVIDERS:
            anchor_observation = anchor_by_provider.get(provider)
            target_observation = observations.get((provider, target_ts))
            if target == "anchor":
                if target_observation is None:
                    target_observation = anchor_observation
                point = build_verified_point(provider, target, target_ts, anchor_observation, target_observation)
                if point and point.pips == 0.0:
                    point = VerifiedPoint(
                        provider=point.provider,
                        target=point.target,
                        timestamp=point.timestamp,
                        price=point.price,
                        direction="flat",
                        pips=0.0,
                        observation=point.observation,
                        anchor_timestamp=point.anchor_timestamp,
                    )
            else:
                point = build_verified_point(provider, target, target_ts, anchor_observation, target_observation)
            if point:
                points.append(point)

        primary = next((point for point in points if point.provider == "tiingo"), None)
        compares = [point for point in points if point.provider != "tiingo"]
        quality, accepted, selection_reason, agreeing_providers, outlier_providers = classify_target(primary, compares)
        accepted_points[target] = accepted
        rows.append({
            "episode_id": episode_id,
            "release_ts": release_ts,
            "target": target,
            "target_timestamp": target_ts,
            "quality_status": quality,
            "selection_reason": selection_reason,
            "accepted_provider": None if accepted is None else accepted.provider,
            "accepted_timestamp": None if accepted is None else accepted.timestamp,
            "accepted_price": None if accepted is None else accepted.price,
            "accepted_direction_relative_to_anchor": None if accepted is None else accepted.direction.upper(),
            "accepted_pips_relative_to_anchor": None if accepted is None else accepted.pips,
            "source_resolution": None if accepted is None else accepted.observation.source_resolution,
            "observation_type": None if accepted is None else accepted.observation.observation_type,
            "agreeing_providers": agreeing_providers,
            "outlier_providers": outlier_providers,
            "provider_observations": [
                {
                    "provider": point.provider,
                    "timestamp": point.timestamp,
                    "price": point.price,
                    "direction_relative_to_anchor": point.direction.upper(),
                    "pips_relative_to_anchor": point.pips,
                    "anchor_timestamp": point.anchor_timestamp,
                    "source_resolution": point.observation.source_resolution,
                    "observation_type": point.observation.observation_type,
                    "raw_artifact_reference": point.observation.raw_artifact_reference,
                }
                for point in points
            ],
            "verification_contract_version": VERIFICATION_CONTRACT_VERSION,
        })
    return rows, accepted_points


def build_verified_outcome_row(
    outcome: Mapping[str, Any],
    cache_row: Mapping[str, Any],
    accepted_points: Mapping[str, VerifiedPoint | None],
    verification_rows: list[dict[str, Any]],
    construction_ts: str,
) -> dict[str, Any]:
    episode_id = str(outcome["episode_id"])
    release_ts = str(outcome["release_ts"])
    anchor = accepted_points["anchor"]
    first = accepted_points["first_minute"]
    second = accepted_points["second_minute"]
    target5 = accepted_points["5m"]
    target15 = accepted_points["15m"]
    target30 = accepted_points["30m"]
    target60 = accepted_points["60m"]
    _require(anchor is not None, "VERIFIED_ANCHOR_MISSING:" + episode_id)

    availability = "APPROXIMATION_ONLY"
    first_direction = "UNAVAILABLE" if first is None else contract.direction_for_pips(first.pips)
    second_direction = "UNAVAILABLE" if second is None else contract.direction_for_pips(second.pips)
    up_excursion = None
    down_excursion = None
    first_range = None
    intraminute_sequence_known = None
    ambiguity_reason = None
    if first and first.observation.high is not None and first.observation.low is not None:
        up_excursion = max(round2((float(first.observation.high) - anchor.price) / 0.01), 0.0)
        down_excursion = min(round2((float(first.observation.low) - anchor.price) / 0.01), 0.0)
        first_range = round2(up_excursion - down_excursion)
        both_sides = up_excursion >= contract.FLAT_MAX_ABS_PIPS and down_excursion <= -contract.FLAT_MAX_ABS_PIPS
        intraminute_sequence_known = not both_sides
        ambiguity_reason = "BOTH_SIDES_EXCURSION_ORDER_UNKNOWN" if both_sides else None
    else:
        intraminute_sequence_known = None
        ambiguity_reason = "OHLC_UNAVAILABLE"

    contiguous = first is not None and second is not None and (utc(second.timestamp) - utc(first.timestamp)).total_seconds() == 60
    if not contiguous:
        path_class = "UNAVAILABLE"
    elif first_direction not in {"UP", "DOWN"} or second_direction not in {"UP", "DOWN"}:
        path_class = "FLAT_OR_INDETERMINATE"
    else:
        path_class = "CONTINUATION" if first_direction == second_direction else "REVERSAL"

    quality_by_target = {row["target"]: row["quality_status"] for row in verification_rows}
    row = {
        "object": "VERIFIED_MINUTE_OUTCOME",
        "episode_id": episode_id,
        "release_timestamp": release_ts,
        "original_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "original_outcome_reference": outcome["outcome_id"],
        "original_outcome_fingerprint": outcome["outcome_fingerprint"],
        "source_resolution": "ONE_MINUTE",
        "observation_type": "OHLC",
        "detector_mode": "ONE_MINUTE_APPROXIMATION",
        "availability_status": availability,
        "verification_status_by_target": quality_by_target,
        "anchor_price": anchor.price,
        "anchor_price_ts": anchor.timestamp,
        "anchor_source": ANCHOR_SOURCE,
        "anchor_reconciliation_status": quality_by_target["anchor"],
        "anchor_provider": anchor.provider,
        "first_minute_timestamp": None if first is None else first.timestamp,
        "first_minute_open": None if first is None else first.observation.open,
        "first_minute_high": None if first is None else first.observation.high,
        "first_minute_low": None if first is None else first.observation.low,
        "first_minute_close": None if first is None else first.observation.close,
        "first_minute_provider": None if first is None else first.provider,
        "first_minute_net_direction": first_direction,
        "first_minute_net_pips": None if first is None else first.pips,
        "first_minute_up_excursion_pips": up_excursion,
        "first_minute_down_excursion_pips": down_excursion,
        "first_minute_range_pips": first_range,
        "second_minute_timestamp": None if second is None else second.timestamp,
        "second_minute_open": None if second is None else second.observation.open,
        "second_minute_high": None if second is None else second.observation.high,
        "second_minute_low": None if second is None else second.observation.low,
        "second_minute_close": None if second is None else second.observation.close,
        "second_minute_provider": None if second is None else second.provider,
        "two_minute_net_direction": second_direction,
        "two_minute_net_pips": None if second is None else second.pips,
        "intraminute_sequence_known": intraminute_sequence_known,
        "ambiguity_reason": ambiguity_reason,
        "minute_resolution_path_class": path_class,
        "verified_direction_5m": "UNAVAILABLE" if target5 is None else contract.direction_for_pips(target5.pips),
        "verified_direction_15m": "UNAVAILABLE" if target15 is None else contract.direction_for_pips(target15.pips),
        "verified_direction_30m": "UNAVAILABLE" if target30 is None else contract.direction_for_pips(target30.pips),
        "verified_direction_60m": "UNAVAILABLE" if target60 is None else contract.direction_for_pips(target60.pips),
        "verified_pips_5m": None if target5 is None else target5.pips,
        "verified_pips_15m": None if target15 is None else target15.pips,
        "verified_pips_30m": None if target30 is None else target30.pips,
        "verified_pips_60m": None if target60 is None else target60.pips,
        "verified_provider_5m": None if target5 is None else target5.provider,
        "verified_provider_15m": None if target15 is None else target15.provider,
        "verified_provider_30m": None if target30 is None else target30.provider,
        "verified_provider_60m": None if target60 is None else target60.provider,
        "contract_version": VERIFIED_OUTCOME_CONTRACT_VERSION,
        "detector_version": DETECTOR_VERSION,
        "construction_timestamp": construction_ts,
        "tiingo_cache_recovery_run_id": TIINGO_RECOVERY_RUN_ID,
        "raw_observation_references": {
            target: None if point is None else point.observation.raw_artifact_reference
            for target, point in accepted_points.items()
        },
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
    }
    row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
    return row


def original_forecast_paths(prediction: Mapping[str, Any]) -> list[dict[str, Any]]:
    prefix = next(iter([p for p in (ROUND1_ROOT / "canonical_forecasts").glob(f"*_{prediction['episode_id']}_{prediction['provider']}_{'PACK_A' if prediction['information_arm']=='BASELINE' else 'PACK_E'}_paths.jsonl")]), None)
    if prefix is None:
        pack = "PACK_A" if prediction["information_arm"] == "BASELINE" else "PACK_E"
        matches = list((ROUND1_ROOT / "canonical_forecasts").glob(f"*_{prediction['episode_id']}_{prediction['provider']}_{pack}_paths.jsonl"))
        _require(len(matches) == 1, "FORECAST_PATH_FILE_MISSING:" + prediction["prediction_id"])
        prefix = matches[0]
    return read_jsonl(prefix)


def evaluate_verified_t15(prediction: Mapping[str, Any], paths: list[dict[str, Any]], verified_outcome: Mapping[str, Any], original_eval_by_prediction: Mapping[str, Mapping[str, Any]], generated_ts: str) -> dict[str, Any]:
    source_quality = verified_outcome["verification_status_by_target"]["15m"]
    verified_population = source_quality in {"MULTI_SOURCE_CONFIRMED", "MULTI_SOURCE_CONSENSUS"}
    if source_quality == "OUTCOME_UNAVAILABLE":
        status = "UNAVAILABLE"
    else:
        status = "VALID"
    if prediction["status"] == "PROVIDER_ERROR" or not verified_population:
        unavailable_like = True
    else:
        unavailable_like = False

    if unavailable_like:
        directions = {h: None for h in contract.HORIZONS}
        immediate_result = "NOT_APPLICABLE"
        t5_range = None
        t5_distance = None
        t5_midpoint = None
        retention = None
        sustained = None
        faded = None
        reversed_t5 = None
        false_initial = None
        primary = None
        magnitude = None
        reversal = None
        no_signal = None
        score = None
    elif prediction["no_signal_flag"]:
        directions = {h: None for h in contract.HORIZONS}
        quiet = all(verified_outcome[f"verified_direction_{h}m"] == "FLAT" for h in contract.HORIZONS)
        immediate_result = "NOT_APPLICABLE"
        t5_range = None
        t5_distance = None
        t5_midpoint = None
        retention = None
        sustained = None
        faded = None
        reversed_t5 = None
        false_initial = None
        primary = None
        magnitude = None
        reversal = None
        no_signal = quiet
        score = None
    else:
        by_horizon = {path["horizon_min"]: path for path in paths}
        directions = {
            5: by_horizon[5]["expected_direction"] == verified_outcome["verified_direction_5m"],
            15: by_horizon[15]["expected_direction"] == verified_outcome["verified_direction_15m"],
            30: by_horizon[30]["expected_direction"] == verified_outcome["verified_direction_30m"],
            60: by_horizon[60]["expected_direction"] == verified_outcome["verified_direction_60m"],
        }
        immediate_result = "NOT_APPLICABLE"
        false_initial = None
        realized_5m_abs = abs(float(verified_outcome["verified_pips_5m"]))
        path5 = by_horizon[5]
        t5_range = path5["expected_pips_min"] <= realized_5m_abs <= path5["expected_pips_max"]
        t5_distance = contract._interval_error(realized_5m_abs, path5["expected_pips_min"], path5["expected_pips_max"])
        t5_midpoint = contract._midpoint_absolute_error(realized_5m_abs, path5["expected_pips_min"], path5["expected_pips_max"])
        retention = None
        sustained = None
        faded = None
        reversed_t5 = None
        primary = directions[15]
        realized_15m_abs = abs(float(verified_outcome["verified_pips_15m"]))
        path15 = by_horizon[15]
        magnitude = contract._interval_error(realized_15m_abs, path15["expected_pips_min"], path15["expected_pips_max"])
        original_eval = original_eval_by_prediction.get(prediction["prediction_id"])
        reversal = None if original_eval is None else original_eval.get("reversal_ok")
        no_signal = None
        score = sum(bool(value) for value in directions.values()) / len(directions)

    record = {
        "object": "EVALUATION",
        "schema_version": contract.SCHEMA_VERSION,
        "system_version": contract.SYSTEM_VERSION,
        "evaluation_id": "",
        "run_id": "",
        "prediction_id": prediction["prediction_id"],
        "outcome_id": verified_outcome["original_outcome_reference"],
        "episode_id": prediction["episode_id"],
        "provider": prediction["provider"],
        "model": prediction["model"],
        "information_arm": prediction["information_arm"],
        "immediate_impulse_direction_result": immediate_result,
        "immediate_impulse_peak_range_covered": None,
        "immediate_impulse_peak_range_distance_error_pips": None,
        "immediate_impulse_peak_midpoint_absolute_error_pips": None,
        "false_initial_excursion_observed": false_initial,
        "direction_5m_ok": directions[5],
        "direction_15m_ok": directions[15],
        "direction_30m_ok": directions[30],
        "direction_60m_ok": directions[60],
        "t5_range_covered": t5_range,
        "t5_range_distance_error_pips": t5_distance,
        "t5_midpoint_absolute_error_pips": t5_midpoint,
        "initial_peak_retention_at_t5": retention,
        "initial_impulse_sustained_to_t5": sustained,
        "initial_impulse_faded_by_t5": faded,
        "initial_impulse_reversed_by_t5": reversed_t5,
        "magnitude_15m_error": magnitude,
        "reversal_ok": reversal,
        "no_signal_ok": no_signal,
        "primary_endpoint_name": "EPISODE_REACTION_DIRECTION_15M",
        "primary_endpoint_value": primary,
        "overall_path_score": score,
        "evaluation_note": "Verified multi-provider minute Outcome rebuild; unchanged forecasts re-evaluated against independently verified market observations.",
        "evaluation_contract_version": contract.CONTRACT_VERSION,
        "evaluation_fingerprint": "",
        "generated_ts": generated_ts,
        "status": status,
        "error_message": None,
        "verified_target_quality_status": source_quality,
        "verified_population_included": verified_population,
    }
    base_fingerprint = {k: v for k, v in record.items() if k != "evaluation_fingerprint"}
    record["evaluation_id"] = contract.evaluation_id_for(record)
    record["evaluation_fingerprint"] = sha256_value(base_fingerprint | {"evaluation_id": record["evaluation_id"]})
    return record


def evaluate_verified_immediate_impulse(
    call_row: Mapping[str, Any],
    forecast: Mapping[str, Any] | None,
    verified_outcome: Mapping[str, Any],
    construction_ts: str,
) -> dict[str, Any]:
    if forecast is None:
        return {
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
            "approximation_outcome_reference": verified_outcome["episode_id"],
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
            "verified_first_minute_quality_status": verified_outcome["verification_status_by_target"]["first_minute"],
            "verified_second_minute_quality_status": verified_outcome["verification_status_by_target"]["second_minute"],
            "verified_population_included": False,
            "construction_timestamp": construction_ts,
            "contract_version": VERIFIED_OUTCOME_CONTRACT_VERSION,
            "evaluator_version": IMMEDIATE_EVALUATOR_VERSION,
            "record_fingerprint": "",
        }
    first_quality = verified_outcome["verification_status_by_target"]["first_minute"]
    second_quality = verified_outcome["verification_status_by_target"]["second_minute"]
    included = first_quality in {"MULTI_SOURCE_CONFIRMED", "MULTI_SOURCE_CONSENSUS"}
    close_direction = verified_outcome["first_minute_net_direction"]
    two_direction = verified_outcome["two_minute_net_direction"]
    observed_path = verified_outcome["minute_resolution_path_class"]
    immediate_prediction = forecast.get("immediate_impulse_direction")
    sequence_unambiguous = bool(verified_outcome["intraminute_sequence_known"]) if included else None
    close_evaluable = (
        included
        and forecast["status"] == "VALID"
        and not forecast["no_signal_flag"]
        and close_direction in {"UP", "DOWN", "FLAT"}
    )
    if forecast["no_signal_flag"]:
        first_result = second_result = approx_result = sequence_result = path_result = "NOT_EVALUABLE"
        predicted_path = "UNAVAILABLE"
        evaluation_status = "VALID_NO_SIGNAL"
    else:
        first_result = "CORRECT" if close_evaluable and immediate_prediction == close_direction else ("INCORRECT" if close_evaluable else "NOT_EVALUABLE")
        second_result = "CORRECT" if close_evaluable and immediate_prediction == two_direction else ("INCORRECT" if close_evaluable else "NOT_EVALUABLE")
        approx_result = first_result
        sequence_result = first_result if close_evaluable and sequence_unambiguous else "NOT_EVALUABLE"
        early = forecast.get("early_reaction_5m_direction")
        if immediate_prediction in {"UP", "DOWN"} and early in {"UP", "DOWN"}:
            predicted_path = "CONTINUATION" if immediate_prediction == early else "REVERSAL"
        elif immediate_prediction in {"FLAT"} or early in {"FLAT"}:
            predicted_path = "FLAT_OR_INDETERMINATE"
        else:
            predicted_path = "UNAVAILABLE"
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
        "approximation_outcome_reference": verified_outcome["episode_id"],
        "availability_status": verified_outcome["availability_status"],
        "close_direction_evaluable": close_evaluable,
        "sequence_unambiguous": sequence_unambiguous,
        "first_minute_direction_result": first_result,
        "two_minute_direction_result": second_result,
        "one_minute_approximation_direction_result": approx_result,
        "sequence_unambiguous_direction_result": sequence_result,
        "predicted_minute_path_class": predicted_path,
        "observed_minute_path_class": observed_path if close_evaluable else "UNAVAILABLE",
        "minute_path_result": path_result,
        "evaluation_status": evaluation_status,
        "verified_first_minute_quality_status": first_quality,
        "verified_second_minute_quality_status": second_quality,
        "verified_population_included": included,
        "construction_timestamp": construction_ts,
        "contract_version": VERIFIED_OUTCOME_CONTRACT_VERSION,
        "evaluator_version": IMMEDIATE_EVALUATOR_VERSION,
    }
    row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
    return row


def pair_transition(base_prediction: Mapping[str, Any] | None, full_prediction: Mapping[str, Any] | None) -> str:
    if not base_prediction or not full_prediction:
        return "PAIR_NOT_EVALUABLE"
    base_signal = not base_prediction["no_signal_flag"]
    full_signal = not full_prediction["no_signal_flag"]
    if not base_signal and full_signal:
        return "A_NO_SIGNAL_TO_E_DIRECTIONAL"
    if base_signal and not full_signal:
        return "A_DIRECTIONAL_TO_E_NO_SIGNAL"
    if not base_signal and not full_signal:
        return "BOTH_NO_SIGNAL"
    return "BOTH_DIRECTIONAL"


def pair_classification(left: Any, right: Any) -> str:
    if left not in {True, False, "CORRECT", "INCORRECT"} or right not in {True, False, "CORRECT", "INCORRECT"}:
        return "not evaluable"
    left_correct = left is True or left == "CORRECT"
    right_correct = right is True or right == "CORRECT"
    if left_correct and right_correct:
        return "both correct"
    if (not left_correct) and right_correct:
        return "correction"
    if left_correct and (not right_correct):
        return "degradation"
    return "both incorrect"


def build_pair_rows(
    call_ledger: list[dict[str, Any]],
    forecast_by_identity: Mapping[tuple[str, str, str, str], dict[str, Any]],
    verified_t15_by_prediction: Mapping[str, dict[str, Any]],
    verified_ii_by_prediction: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in call_ledger:
        arm = "BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT"
        grouped[(item["episode_id"], item["provider"], item["model"])][arm] = item

    rows = []
    for (episode_id, provider, model), arms in sorted(grouped.items()):
        base_item = arms.get("BASELINE")
        full_item = arms.get("FULL_CONTEXT")
        base_prediction = None if base_item is None else forecast_by_identity.get((episode_id, provider, model, "BASELINE"))
        full_prediction = None if full_item is None else forecast_by_identity.get((episode_id, provider, model, "FULL_CONTEXT"))
        base_t15 = None if not base_prediction else verified_t15_by_prediction.get(base_prediction["prediction_id"])
        full_t15 = None if not full_prediction else verified_t15_by_prediction.get(full_prediction["prediction_id"])
        base_ii = None if not base_prediction else verified_ii_by_prediction.get(base_prediction["prediction_id"])
        full_ii = None if not full_prediction else verified_ii_by_prediction.get(full_prediction["prediction_id"])
        row = {
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "baseline_prediction_id": None if not base_prediction else base_prediction["prediction_id"],
            "full_context_prediction_id": None if not full_prediction else full_prediction["prediction_id"],
            "pair_transition": pair_transition(base_prediction, full_prediction),
            "verified_t15_pair_classification": pair_classification(
                None if not base_t15 or base_prediction["no_signal_flag"] or not base_t15["verified_population_included"] else base_t15["direction_15m_ok"],
                None if not full_t15 or full_prediction["no_signal_flag"] or not full_t15["verified_population_included"] else full_t15["direction_15m_ok"],
            ),
            "verified_first_minute_pair_classification": pair_classification(
                None if not base_ii else base_ii["one_minute_approximation_direction_result"],
                None if not full_ii else full_ii["one_minute_approximation_direction_result"],
            ),
            "verified_sequence_unambiguous_pair_classification": pair_classification(
                None if not base_ii else base_ii["sequence_unambiguous_direction_result"],
                None if not full_ii else full_ii["sequence_unambiguous_direction_result"],
            ),
        }
        row["record_fingerprint"] = sha256_value({k: row[k] for k in row if k != "record_fingerprint"})
        rows.append(row)
    return rows


def metric_block(rows: list[dict[str, Any]], result_key: str) -> dict[str, Any]:
    eligible = [row for row in rows if row[result_key] in {"CORRECT", "INCORRECT"}]
    correct = sum(row[result_key] == "CORRECT" for row in eligible)
    return {
        "numerator": correct,
        "denominator": len(eligible),
        "accuracy": None if not eligible else round(correct / len(eligible), 6),
    }


def t15_metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["verified_population_included"] and row["direction_15m_ok"] in {True, False}]
    correct = sum(bool(row["direction_15m_ok"]) for row in eligible)
    return {"numerator": correct, "denominator": len(eligible), "accuracy": None if not eligible else round(correct / len(eligible), 6)}


def build_verified_release(
    acquisition_dir: Path,
    acquisition_manifest: dict[str, Any],
    request_rows: list[dict[str, Any]],
    day_coverage_rows: list[dict[str, Any]],
    observation_index: Mapping[tuple[str, str], ProviderObservation],
    output_root: Path = VERIFIED_ROOT,
) -> tuple[Path, dict[str, Any]]:
    outcomes, outcome_by_episode, forecast_by_identity, call_ledger, original_evaluations, original_pairs, cache_validation = load_round1_inputs()
    verify_static_inputs(outcomes, cache_validation)
    construction_ts = iso(datetime.now(timezone.utc))
    run_id = verified_run_id(datetime.now(timezone.utc))
    run_dir = output_root / run_id

    original_eval_by_prediction = {row["prediction_id"]: row for row in original_evaluations}
    verification_rows: list[dict[str, Any]] = []
    verified_outcomes: list[dict[str, Any]] = []
    verified_outcome_by_episode: dict[str, dict[str, Any]] = {}
    target_quality_counts = {target: Counter() for target in TARGET_ORDER}
    tiingo_confirmed = 0
    tiingo_overridden = 0
    single_source_only = 0
    source_disagreement = 0
    outcome_unavailable = 0

    for outcome in outcomes:
        episode_rows, accepted_points = verify_episode_targets(outcome, cache_validation[outcome["episode_id"]], observation_index)
        verification_rows.extend(episode_rows)
        for row in episode_rows:
            target_quality_counts[row["target"]][row["quality_status"]] += 1
            if row["quality_status"] in {"MULTI_SOURCE_CONFIRMED", "MULTI_SOURCE_CONSENSUS"}:
                if row["accepted_provider"] == "tiingo":
                    tiingo_confirmed += 1
                else:
                    tiingo_overridden += 1
            elif row["quality_status"] == "SINGLE_SOURCE_ONLY":
                single_source_only += 1
            elif row["quality_status"] == "SOURCE_DISAGREEMENT":
                source_disagreement += 1
            elif row["quality_status"] == "OUTCOME_UNAVAILABLE":
                outcome_unavailable += 1
        verified = build_verified_outcome_row(outcome, cache_validation[outcome["episode_id"]], accepted_points, episode_rows, construction_ts)
        verified_outcomes.append(verified)
        verified_outcome_by_episode[verified["episode_id"]] = verified

    verified_t15_rows = []
    verified_ii_rows = []
    for item in sorted(call_ledger, key=lambda row: row["call_index"]):
        information_arm = "BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT"
        forecast = forecast_by_identity.get((item["episode_id"], item["provider"], item["model"], information_arm))
        paths = None if forecast is None else original_forecast_paths(forecast)
        verified_outcome = verified_outcome_by_episode[item["episode_id"]]
        t15 = evaluate_verified_t15(forecast, paths, verified_outcome, original_eval_by_prediction, construction_ts) if forecast is not None else None
        if t15 is None:
            continue
        t15["run_id"] = run_id
        t15["evaluation_fingerprint"] = sha256_value({k: t15[k] for k in t15 if k != "evaluation_fingerprint"})
        verified_t15_rows.append(t15)
        ii = evaluate_verified_immediate_impulse(item, forecast, verified_outcome, construction_ts)
        verified_ii_rows.append(ii)

    verified_t15_by_prediction = {row["prediction_id"]: row for row in verified_t15_rows if row.get("prediction_id")}
    verified_ii_by_prediction = {row["prediction_id"]: row for row in verified_ii_rows if row.get("prediction_id")}
    pair_rows = build_pair_rows(call_ledger, forecast_by_identity, verified_t15_by_prediction, verified_ii_by_prediction)

    verified_t15_population = [row for row in verified_t15_rows if row["verified_population_included"]]
    verified_t15_directional = [row for row in verified_t15_population if row["direction_15m_ok"] in {True, False}]
    verified_ii_population = [row for row in verified_ii_rows if row["verified_population_included"]]
    provider_coverage_summary = {
        "days": list(UTC_DAYS),
        "providers": {provider: {
            "success_days": sum(1 for row in day_coverage_rows if row["provider"] == provider and row["status"] == "SUCCESS"),
            "observation_count": sum(1 for observation in observation_index.values() if observation.provider == provider),
        } for provider in AUTHORIZED_PROVIDERS},
        "massive_failure_days": sum(1 for row in day_coverage_rows if row["provider"] == "massive" and row["status"] != "SUCCESS"),
    }

    quality_counts_total = Counter(row["quality_status"] for row in verification_rows)
    verification_summary = {
        "quality_status_counts_by_target": {target: dict(counter) for target, counter in target_quality_counts.items()},
        "quality_status_counts_total": dict(quality_counts_total),
        "multi_source_confirmed_denominator": int(quality_counts_total["MULTI_SOURCE_CONFIRMED"]),
        "multi_source_consensus_denominator": int(quality_counts_total["MULTI_SOURCE_CONSENSUS"]),
        "single_source_only_denominator": int(quality_counts_total["SINGLE_SOURCE_ONLY"]),
        "source_disagreement_denominator": int(quality_counts_total["SOURCE_DISAGREEMENT"]),
        "outcome_unavailable_denominator": int(quality_counts_total["OUTCOME_UNAVAILABLE"]),
        "tiingo_confirmed_count": tiingo_confirmed,
        "tiingo_overridden_count": tiingo_overridden,
        "single_source_only_count": single_source_only,
        "source_disagreement_count": source_disagreement,
        "outcome_unavailable_count": outcome_unavailable,
    }

    t15_overall = t15_metric_block(verified_t15_rows)
    t15_by_provider = {provider: t15_metric_block([row for row in verified_t15_rows if row["provider"] == provider]) for provider in ("Gemini", "OpenAI")}
    t15_by_pack = {
        "Pack A": t15_metric_block([row for row in verified_t15_rows if row["information_arm"] == "BASELINE"]),
        "Pack E": t15_metric_block([row for row in verified_t15_rows if row["information_arm"] == "FULL_CONTEXT"]),
    }
    ii_overall = metric_block(verified_ii_population, "one_minute_approximation_direction_result")
    ii_two_overall = metric_block(verified_ii_population, "two_minute_direction_result")
    ii_seq_overall = metric_block(verified_ii_population, "sequence_unambiguous_direction_result")
    ii_by_pack = {
        "Pack A": metric_block([row for row in verified_ii_population if row["information_arm"] == "BASELINE"], "one_minute_approximation_direction_result"),
        "Pack E": metric_block([row for row in verified_ii_population if row["information_arm"] == "FULL_CONTEXT"], "one_minute_approximation_direction_result"),
    }

    pair_t15_counts = Counter(row["verified_t15_pair_classification"] for row in pair_rows)
    pair_ii_counts = Counter(row["verified_first_minute_pair_classification"] for row in pair_rows)
    pair_seq_counts = Counter(row["verified_sequence_unambiguous_pair_classification"] for row in pair_rows)
    pair_transitions = Counter(row["pair_transition"] for row in pair_rows)

    supersession_record = {
        "superseded_release_id": TIINGO_ONLY_BASELINE_RUN_ID,
        "superseding_release_id": run_id,
        "supersession_reason": SUPERSESSION_REASON,
        "statement": (
            "The prior Tiingo-only minute enrichment remains valid as a reproducible single-source baseline. "
            "It is superseded for final scientific Outcome reporting because its market observations were not independently verified. "
            "The original AI predictions remain valid and unchanged. "
            "The supersession applies only to accepted Outcome construction and evaluation."
        ),
    }
    scientific_interpretation = "\n".join([
        "# Round 1 Verified Minute Outcomes",
        "",
        f"- Verified release: `{run_id}`",
        f"- Acquisition source: `{acquisition_manifest['run_id']}`",
        "- T+15 remains the primary endpoint.",
        "- Immediate Impulse remains a one-minute approximation only.",
        "- The verified denominator includes only `MULTI_SOURCE_CONFIRMED` and `MULTI_SOURCE_CONSENSUS` target populations.",
        "",
        "## Comparison with Tiingo-only baseline",
        f"- Tiingo-confirmed target points: {tiingo_confirmed}",
        f"- Tiingo-overridden target points: {tiingo_overridden}",
        f"- Single-source-only target points: {single_source_only}",
        f"- Source-disagreement target points: {source_disagreement}",
        "",
        "## Verified T+15",
        f"- Overall: {t15_overall['numerator']} / {t15_overall['denominator']} = {t15_overall['accuracy']}",
        f"- Gemini: {t15_by_provider['Gemini']['numerator']} / {t15_by_provider['Gemini']['denominator']} = {t15_by_provider['Gemini']['accuracy']}",
        f"- OpenAI: {t15_by_provider['OpenAI']['numerator']} / {t15_by_provider['OpenAI']['denominator']} = {t15_by_provider['OpenAI']['accuracy']}",
        "",
        "## Verified one-minute approximation",
        f"- First-minute: {ii_overall['numerator']} / {ii_overall['denominator']} = {ii_overall['accuracy']}",
        f"- Two-minute: {ii_two_overall['numerator']} / {ii_two_overall['denominator']} = {ii_two_overall['accuracy']}",
        f"- Sequence-unambiguous: {ii_seq_overall['numerator']} / {ii_seq_overall['denominator']} = {ii_seq_overall['accuracy']}",
    ]) + "\n"

    run_manifest = {
        "run_id": run_id,
        "source_round1_run_id": ORIGINAL_ROUND1_RUN_ID,
        "source_matrix_freeze_id": MATRIX_FREEZE_RUN_ID,
        "source_acquisition_run_id": acquisition_manifest["run_id"],
        "source_tiingo_recovery_run_id": TIINGO_RECOVERY_RUN_ID,
        "superseded_tiingo_only_release_id": TIINGO_ONLY_BASELINE_RUN_ID,
        "verification_contract_version": VERIFICATION_CONTRACT_VERSION,
        "verified_outcome_contract_version": VERIFIED_OUTCOME_CONTRACT_VERSION,
        "immediate_evaluator_version": IMMEDIATE_EVALUATOR_VERSION,
        "t15_evaluator_version": T15_EVALUATOR_VERSION,
        "detector_version": DETECTOR_VERSION,
        "git_head": git_head(),
        "construction_timestamp": construction_ts,
        "coverage_statement": "The verified release preserves T+15 as primary. Immediate Impulse is secondary and remains APPROXIMATION_ONLY at one-minute resolution. The prior Tiingo-only enrichment is superseded for final Outcome reporting but remains a reproducible single-source baseline.",
        "record_counts": {
            "observation_verification_rows": len(verification_rows),
            "verified_outcome_rows": len(verified_outcomes),
            "immediate_impulse_evaluation_rows": len(verified_ii_rows),
            "t15_evaluation_rows": len(verified_t15_rows),
            "paired_pack_comparison_rows": len(pair_rows),
        },
        "verification_decision": "MULTI_SOURCE_VERIFIED_POPULATION_AVAILABLE" if (quality_counts_total["MULTI_SOURCE_CONFIRMED"] + quality_counts_total["MULTI_SOURCE_CONSENSUS"]) > 0 else "NO_ADMISSIBLE_VERIFIED_POPULATION",
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "supersession_record.json", supersession_record)
    write_jsonl(run_dir / "provider_request_manifest.jsonl", request_rows)
    write_jsonl(run_dir / "normalized_provider_observations.jsonl", [
        {
            "provider": observation.provider,
            "day": observation.day,
            "timestamp": observation.timestamp,
            "timestamp_raw": observation.timestamp_raw,
            "open": observation.open,
            "high": observation.high,
            "low": observation.low,
            "close": observation.close,
            "bid": observation.bid,
            "ask": observation.ask,
            "midpoint": observation.midpoint,
            "accepted_comparison_field": observation.accepted_comparison_field,
            "accepted_comparison_value": observation.accepted_comparison_value,
            "source_resolution": observation.source_resolution,
            "observation_type": observation.observation_type,
            "instrument": observation.instrument,
            "request_identity": observation.request_identity,
            "raw_artifact_reference": observation.raw_artifact_reference,
            "raw_artifact_sha256": observation.raw_artifact_sha256,
            "retrieval_timestamp": observation.retrieval_timestamp,
        }
        for observation in sorted(observation_index.values(), key=lambda item: (item.provider, item.timestamp))
    ])
    write_jsonl(run_dir / "observation_verification_rows.jsonl", verification_rows)
    write_jsonl(run_dir / "verified_outcome_rows.jsonl", verified_outcomes)
    write_jsonl(run_dir / "immediate_impulse_evaluation_rows.jsonl", verified_ii_rows)
    write_jsonl(run_dir / "t15_evaluation_rows.jsonl", verified_t15_rows)
    write_jsonl(run_dir / "paired_pack_comparison_rows.jsonl", pair_rows)
    write_json(run_dir / "provider_coverage_summary.json", provider_coverage_summary)
    write_json(run_dir / "verification_summary.json", verification_summary | {
        "verified_t15_overall": t15_overall,
        "verified_t15_by_provider": t15_by_provider,
        "verified_t15_by_pack": t15_by_pack,
        "verified_first_minute_overall": ii_overall,
        "verified_two_minute_overall": ii_two_overall,
        "verified_sequence_unambiguous_overall": ii_seq_overall,
        "verified_first_minute_by_pack": ii_by_pack,
        "pair_t15_counts": dict(pair_t15_counts),
        "pair_first_minute_counts": dict(pair_ii_counts),
        "pair_sequence_unambiguous_counts": dict(pair_seq_counts),
        "pair_transition_counts": dict(pair_transitions),
    })
    (run_dir / "scientific_interpretation.md").write_text(scientific_interpretation)
    write_json(run_dir / "checksums.json", {
        "observation_verification_rows.jsonl": sha256_value(verification_rows),
        "verified_outcome_rows.jsonl": sha256_value(verified_outcomes),
        "immediate_impulse_evaluation_rows.jsonl": sha256_value(verified_ii_rows),
        "t15_evaluation_rows.jsonl": sha256_value(verified_t15_rows),
        "paired_pack_comparison_rows.jsonl": sha256_value(pair_rows),
    })
    return run_dir, run_manifest


def run_build(
    acquisition_output_root: Path = ACQUISITION_ROOT,
    verified_output_root: Path = VERIFIED_ROOT,
    existing_acquisition_run_id: str | None = None,
) -> dict[str, Any]:
    if existing_acquisition_run_id:
        acquisition_dir = acquisition_output_root / existing_acquisition_run_id
        acquisition_manifest, request_rows, day_coverage_rows, observation_index = load_acquisition_run(acquisition_dir)
    else:
        acquisition_dir, acquisition_manifest, request_rows, day_coverage_rows, observation_index = run_acquisition(acquisition_output_root)
    verified_dir, verified_manifest = build_verified_release(
        acquisition_dir,
        acquisition_manifest,
        request_rows,
        day_coverage_rows,
        observation_index,
        verified_output_root,
    )
    return {
        "acquisition_run_id": acquisition_manifest["run_id"],
        "verified_run_id": verified_manifest["run_id"],
        "acquisition_root": str(acquisition_dir),
        "verified_root": str(verified_dir),
        "verification_decision": verified_manifest["verification_decision"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquisition-output-root", type=Path, default=ACQUISITION_ROOT)
    parser.add_argument("--verified-output-root", type=Path, default=VERIFIED_ROOT)
    parser.add_argument("--existing-acquisition-run-id", type=str, default=None)
    args = parser.parse_args()
    print(json.dumps(run_build(args.acquisition_output_root, args.verified_output_root, args.existing_acquisition_run_id), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
