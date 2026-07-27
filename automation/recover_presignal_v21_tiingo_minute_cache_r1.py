#!/usr/bin/env python3
"""Locate or recover the Round 1 Tiingo minute cache for Immediate Impulse recovery.

This tool does not modify the frozen Round 1 directories. It reconstructs the
original per-day Tiingo minute cache shape in a new recovery output tree and
validates that recovered observations reconcile against the frozen Round 1
outcome rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FULL_RUN_ID = "PPHB-R1-FULL-20260726T160036Z-ca5d238916f1"
FULL_RUN_DIR = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / FULL_RUN_ID
FULL_OUTCOME_ROWS = FULL_RUN_DIR / "outcomes" / "outcome_rows.jsonl"
MATRIX_FREEZE_ID = "PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719"

EXPECTED_CACHE_PATH = ROOT / "outputs" / "presignal_v21_episode_outcomes_v1_1" / "market_data_observation_cache.jsonl"
RECOVERY_ROOT = ROOT / "outputs" / "presignal_v21_immediate_impulse_minute_cache_recovery"

SOURCE_WORKSPACE_TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
ENDPOINT_DEPLOYMENT = "AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN"
ENDPOINT_FUNCTION = "apiFetchGovernedHistoricalUsdJpyObservation"
INSTRUMENT = "USD/JPY"
SOURCE_RESOLUTION = "ONE_MINUTE"
OBSERVATION_TYPE = "OHLC"

HORIZONS = (5, 15, 30, 60)


class RecoveryError(RuntimeError):
    pass


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def round2(value: float) -> float:
    return round(float(value), 2)


def day_request_id(day_text: str) -> str:
    return "MD_DAY_" + hashlib.sha256(day_text.encode()).hexdigest()[:20]


def recovery_run_id(now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "PPHB-R1-TIINGO-MINUTE-CACHE-RECOVERY-" + stamp + "-" + sha256_text(stamp)[:12]


@dataclass(frozen=True)
class CredentialRouteStatus:
    route_present: bool
    endpoint_path_available: bool
    token_path: Path | None
    call_authorization_status: str


def detect_credential_route() -> CredentialRouteStatus:
    env_path = os.environ.get("PRESIGNAL_GOOGLE_TOKEN_PATH")
    env_token = Path(env_path) if env_path else None
    if env_token and env_token.exists():
        chosen = env_token
    elif SOURCE_WORKSPACE_TOKEN_PATH.exists():
        chosen = SOURCE_WORKSPACE_TOKEN_PATH
    else:
        chosen = None
    return CredentialRouteStatus(
        route_present=chosen is not None,
        endpoint_path_available=(ROOT / "apps_script" / "historical_market_data_endpoint.js").exists(),
        token_path=chosen,
        call_authorization_status="AUTHORIZED_BY_MOVE_4A" if chosen else "BLOCKED_PENDING_TOKEN",
    )


def load_full_run_outcomes() -> list[dict[str, Any]]:
    rows = read_jsonl(FULL_OUTCOME_ROWS)
    if len(rows) != 47:
        raise RecoveryError(f"UNEXPECTED_FULL_ROUND1_OUTCOME_COUNT:{len(rows)}")
    return sorted(rows, key=lambda row: (row["release_ts"], row["episode_id"]))


def request_rows_from_outcomes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    for row in rows:
        release = utc(row["release_ts"])
        day_text = str(release.date())
        start = datetime(release.year, release.month, release.day, tzinfo=timezone.utc)
        end = start + timedelta(days=1) - timedelta(minutes=1)
        entry = by_day.setdefault(day_text, {
            "day": day_text,
            "request_id": day_request_id(day_text),
            "requested_window_start": iso(start),
            "requested_window_end": iso(end),
            "episode_ids": [],
            "release_timestamps": [],
        })
        entry["episode_ids"].append(row["episode_id"])
        entry["release_timestamps"].append(row["release_ts"])
    return [by_day[day] for day in sorted(by_day)]


def window_index_rows(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in outcomes:
        release = utc(row["release_ts"])
        rows.append({
            "episode_id": row["episode_id"],
            "release_ts": row["release_ts"],
            "request_day": str(release.date()),
            "window_start": iso(release - timedelta(minutes=10)),
            "window_end": iso(release + timedelta(minutes=2)),
            "anchor_ts": row["anchor_price_ts"],
            "first_completed_minute_ts": iso(release + timedelta(minutes=1)),
            "second_completed_minute_ts": iso(release + timedelta(minutes=2)),
            "expected_horizon_timestamps": {
                "5": iso(release + timedelta(minutes=5)),
                "15": iso(release + timedelta(minutes=15)),
                "30": iso(release + timedelta(minutes=30)),
                "60": iso(release + timedelta(minutes=60)),
            },
        })
    return rows


def normalize_response(day_row: dict[str, Any], result: dict[str, Any], retrieval_ts: str, raw_relpath: str, raw_sha: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = result["result"]
    if payload.get("selected_provider") != "tiingo":
        raise RecoveryError("NON_TIINGO_PROVIDER_RETURNED:" + str(payload.get("selected_provider", "")))
    if payload.get("status") != "SUCCESS":
        raise RecoveryError("TIINGO_RECOVERY_STATUS_" + str(payload.get("status", "")))
    provider_attempts = payload.get("provider_attempts", [])
    for attempt in provider_attempts:
        if attempt.get("provider") == "tiingo" and attempt.get("status") != "SUCCESS":
            raise RecoveryError("TIINGO_ATTEMPT_NOT_SUCCESS")
    request_lineage = {
        "request_id": day_row["request_id"],
        "day": day_row["day"],
        "window_start": day_row["requested_window_start"],
        "window_end": day_row["requested_window_end"],
        "status": payload.get("status", ""),
        "selected_provider": payload.get("selected_provider", ""),
        "returned_observation_count": payload.get("returned_observation_count", 0),
        "provider_attempts": [
            {
                "provider": attempt.get("provider", ""),
                "credential_property_name": attempt.get("credential_property_name", ""),
                "credential_available": bool(attempt.get("credential_available", False)),
                "requested_window_start": attempt.get("requested_window_start", ""),
                "requested_window_end": attempt.get("requested_window_end", ""),
                "http_status": attempt.get("http_status"),
                "status": attempt.get("status", ""),
                "missing_data_reason": attempt.get("missing_data_reason", ""),
            }
            for attempt in provider_attempts
        ],
        "transport_error": "",
        "retrieval_timestamp": retrieval_ts,
        "raw_artifact_reference": raw_relpath,
        "raw_artifact_sha256": raw_sha,
    }
    normalized = []
    seen = set()
    duplicates = 0
    for index, observation in enumerate(payload.get("observations", [])):
        timestamp = iso(utc(observation["returned_observation_timestamp"]))
        if timestamp in seen:
            duplicates += 1
            continue
        seen.add(timestamp)
        normalized.append({
            "provider": payload["selected_provider"],
            "instrument": payload["instrument"],
            "timestamp": timestamp,
            "source_resolution": SOURCE_RESOLUTION,
            "observation_type": OBSERVATION_TYPE,
            "open": observation.get("open"),
            "high": observation.get("high"),
            "low": observation.get("low"),
            "close": observation.get("close"),
            "bid": None,
            "ask": None,
            "midpoint": None,
            "accepted_raw_price_field": observation.get("accepted_raw_price_field", ""),
            "accepted_raw_price": observation.get("accepted_raw_price"),
            "provider_returned_timestamp_raw": observation.get("provider_returned_timestamp_raw"),
            "source_observation_id": None,
            "request_identity": day_row["request_id"],
            "raw_artifact_reference": raw_relpath,
            "raw_artifact_sha256": raw_sha,
            "retrieval_timestamp": retrieval_ts,
            "day": day_row["day"],
            "position": index,
        })
    request_lineage["duplicate_timestamp_count"] = duplicates
    return request_lineage, sorted(normalized, key=lambda row: row["timestamp"])


def find_by_timestamp(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["timestamp"]: row for row in observations}


def selected_horizon_timestamp(outcome: dict[str, Any], horizon: int, fallback_ts: str) -> str:
    source_lineage = outcome.get("source_lineage") or {}
    selected = (source_lineage.get("selected_observations") or {}).get(str(horizon)) or {}
    return selected.get("timestamp") or fallback_ts


def classify_episode_reconciliation(anchor_ok: bool, horizon_ok: dict[int, bool], horizon_explained: dict[int, bool], first_present: bool, second_present: bool) -> str:
    if not first_present or not second_present:
        return "MISSING_OBSERVATIONS"
    if anchor_ok and all(horizon_ok.values()):
        return "EXACT_RECONCILIATION"
    if anchor_ok and all(horizon_ok[h] or horizon_explained[h] for h in horizon_ok):
        return "EXPLAINED_RECONCILIATION"
    return "MISMATCH"


def validate_against_full_run(outcomes: list[dict[str, Any]], observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_ts = find_by_timestamp(observations)
    rows = []
    counts = {
        "episodes": len(outcomes),
        "first_minute_coverage": 0,
        "second_minute_coverage": 0,
        "anchor_exact": 0,
        "horizon_5_exact": 0,
        "horizon_15_exact": 0,
        "horizon_30_exact": 0,
        "horizon_60_exact": 0,
        "mismatch_count": 0,
        "missing_count": 0,
    }
    for outcome in outcomes:
        release = utc(outcome["release_ts"])
        first_ts = iso(release + timedelta(minutes=1))
        second_ts = iso(release + timedelta(minutes=2))
        anchor_observation = by_ts.get(outcome["anchor_price_ts"])
        first_observation = by_ts.get(first_ts)
        second_observation = by_ts.get(second_ts)
        first_present = first_observation is not None
        second_present = second_observation is not None
        counts["first_minute_coverage"] += 1 if first_present else 0
        counts["second_minute_coverage"] += 1 if second_present else 0

        anchor_ok = bool(anchor_observation) and round2(anchor_observation["close"]) == round2(outcome["anchor_price"])
        counts["anchor_exact"] += 1 if anchor_ok else 0
        horizons = {}
        explained_horizons = {}
        horizon_price_matches = {}
        for horizon in HORIZONS:
            nominal_ts = iso(release + timedelta(minutes=horizon))
            selected_ts = selected_horizon_timestamp(outcome, horizon, nominal_ts)
            selected_obs = by_ts.get(selected_ts)
            exact_obs = by_ts.get(nominal_ts)
            ok = bool(exact_obs) and round2(exact_obs["close"]) == round2(outcome[f"price_{horizon}m"])
            explained = (
                selected_ts != nominal_ts
                and bool(selected_obs)
                and round2(selected_obs["close"]) == round2(outcome[f"price_{horizon}m"])
            )
            horizons[horizon] = ok
            explained_horizons[horizon] = explained
            horizon_price_matches[horizon] = {
                "timestamp": nominal_ts,
                "selected_timestamp": selected_ts,
                "found": bool(exact_obs),
                "selected_found": bool(selected_obs),
                "expected_price": outcome[f"price_{horizon}m"],
                "observed_price": None if not exact_obs else exact_obs["close"],
                "selected_observed_price": None if not selected_obs else selected_obs["close"],
                "exact_match": ok,
                "explained_match": explained,
            }
            if ok:
                counts[f"horizon_{horizon}_exact"] += 1

        classification = classify_episode_reconciliation(anchor_ok, horizons, explained_horizons, first_present, second_present)
        if classification == "MISMATCH":
            counts["mismatch_count"] += 1
        if classification == "MISSING_OBSERVATIONS":
            counts["missing_count"] += 1
        rows.append({
            "episode_id": outcome["episode_id"],
            "release_ts": outcome["release_ts"],
            "classification": classification,
            "anchor_match": {
                "timestamp_match": bool(anchor_observation) and anchor_observation["timestamp"] == outcome["anchor_price_ts"],
                "price_match": anchor_ok,
                "expected_price": outcome["anchor_price"],
                "observed_price": None if not anchor_observation else anchor_observation["close"],
            },
            "first_minute": {
                "timestamp": first_ts,
                "present": first_present,
                "open": None if not first_observation else first_observation["open"],
                "high": None if not first_observation else first_observation["high"],
                "low": None if not first_observation else first_observation["low"],
                "close": None if not first_observation else first_observation["close"],
            },
            "second_minute": {
                "timestamp": second_ts,
                "present": second_present,
                "close": None if not second_observation else second_observation["close"],
            },
            "horizon_matches": horizon_price_matches,
        })
    return rows, counts


def run_recovery(output_root: Path | None = None) -> dict[str, Any]:
    from automation.google_clients import load_credentials, build_script_service, run_script_function_with_metadata

    outcomes = load_full_run_outcomes()
    credential_status = detect_credential_route()
    if not credential_status.route_present or credential_status.token_path is None:
        raise RecoveryError("BLOCKED_BY_MISSING_CREDENTIALS")

    now = datetime.now(timezone.utc)
    run_id = recovery_run_id(now)
    run_dir = (output_root or RECOVERY_ROOT) / run_id
    raw_dir = run_dir / "raw_responses"

    request_rows = request_rows_from_outcomes(outcomes)
    window_rows = window_index_rows(outcomes)
    creds = load_credentials(token_path=credential_status.token_path, persist_refresh=False)
    service = build_script_service(creds)

    request_manifest = []
    all_observations = []
    request_lineage_rows = []
    for row in request_rows:
        params = {
            "request_identity": row["request_id"],
            "instrument": INSTRUMENT,
            "requested_window_start": row["requested_window_start"],
            "requested_window_end": row["requested_window_end"],
            "timezone": "UTC",
        }
        metadata = run_script_function_with_metadata(service, ENDPOINT_DEPLOYMENT, ENDPOINT_FUNCTION, [params])
        retrieval_ts = iso(datetime.now(timezone.utc))
        raw_payload = canonical(metadata)
        raw_name = row["day"] + "_" + row["request_id"] + ".json"
        raw_path = raw_dir / raw_name
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw_payload + "\n")
        raw_relpath = str(raw_path.relative_to(ROOT))
        raw_sha = sha256_text(raw_payload)
        if not metadata.get("ok"):
            raise RecoveryError("TIINGO_RECOVERY_TRANSPORT_FAILURE:" + row["day"])
        request_lineage, normalized = normalize_response(row, metadata, retrieval_ts, raw_relpath, raw_sha)
        request_manifest.append({
            **row,
            "transport_ok": metadata["ok"],
            "elapsed_ms": metadata["elapsed_ms"],
            "selected_provider": metadata["result"].get("selected_provider", ""),
            "returned_observation_count": metadata["result"].get("returned_observation_count", 0),
            "raw_artifact_reference": raw_relpath,
            "raw_artifact_sha256": raw_sha,
        })
        request_lineage_rows.append(request_lineage)
        all_observations.extend(normalized)

    all_observations = sorted(all_observations, key=lambda item: item["timestamp"])
    validation_rows, validation_summary = validate_against_full_run(outcomes, all_observations)

    status = {
        "run_id": run_id,
        "source_full_run_id": FULL_RUN_ID,
        "source_matrix_freeze_id": MATRIX_FREEZE_ID,
        "credential_route_present": True,
        "endpoint_path_available": credential_status.endpoint_path_available,
        "provider": "tiingo",
        "instrument": INSTRUMENT,
        "source_resolution": SOURCE_RESOLUTION,
        "observation_type": OBSERVATION_TYPE,
        "request_count": len(request_rows),
        "utc_day_count": len(request_rows),
        "normalized_observation_count": len(all_observations),
        "episode_coverage_count": validation_summary["episodes"],
        "first_minute_coverage_count": validation_summary["first_minute_coverage"],
        "second_minute_coverage_count": validation_summary["second_minute_coverage"],
        "anchor_exact_count": validation_summary["anchor_exact"],
        "horizon_exact_counts": {str(h): validation_summary[f"horizon_{h}_exact"] for h in HORIZONS},
        "mismatch_count": validation_summary["mismatch_count"],
        "missing_count": validation_summary["missing_count"],
        "recovered_cache_decision": "RECOVERED_CACHE_ADMISSIBLE" if validation_summary["mismatch_count"] == 0 and validation_summary["missing_count"] == 0 else "CACHE_PARTIALLY_ADMISSIBLE",
        "no_ai_forecast_calls": True,
        "no_new_provider": True,
    }

    checksums = {
        "request_manifest.jsonl": sha256_bytes("".join(canonical(row) + "\n" for row in request_manifest).encode()),
        "normalized_minute_observations.jsonl": sha256_bytes("".join(canonical(row) + "\n" for row in all_observations).encode()),
        "validation_against_round1.jsonl": sha256_bytes("".join(canonical(row) + "\n" for row in validation_rows).encode()),
    }

    write_json(run_dir / "run_manifest.json", status)
    write_jsonl(run_dir / "request_manifest.jsonl", request_manifest)
    write_jsonl(run_dir / "normalized_minute_observations.jsonl", all_observations)
    write_jsonl(run_dir / "episode_window_index.jsonl", window_rows)
    write_jsonl(run_dir / "validation_against_round1.jsonl", validation_rows)
    write_jsonl(run_dir / "request_lineage.jsonl", request_lineage_rows)
    write_json(run_dir / "checksums.json", checksums)
    summary = (
        "# Tiingo Minute Cache Recovery\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Source Round 1: `{FULL_RUN_ID}`\n"
        f"- Provider: `tiingo`\n"
        f"- Instrument: `{INSTRUMENT}`\n"
        f"- Requests: {len(request_rows)}\n"
        f"- Normalized observations: {len(all_observations)}\n"
        f"- Episodes validated: {validation_summary['episodes']}\n"
        f"- Anchor exact matches: {validation_summary['anchor_exact']}\n"
        f"- First-minute coverage: {validation_summary['first_minute_coverage']}\n"
        f"- Second-minute coverage: {validation_summary['second_minute_coverage']}\n"
        f"- Mismatches: {validation_summary['mismatch_count']}\n"
        f"- Missing observations: {validation_summary['missing_count']}\n"
    )
    (run_dir / "summary.md").write_text(summary)
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=RECOVERY_ROOT)
    args = parser.parse_args()
    print(json.dumps(run_recovery(args.output_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
