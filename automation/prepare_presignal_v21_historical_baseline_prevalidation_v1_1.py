#!/usr/bin/env python3
"""Freeze Round 1 admission and build isolated v1.1 validation Outcomes.

This module is intentionally local-only. It performs no provider, market-data,
Google Sheets, Apps Script, or workbook operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract

EPISODES = ROOT / "outputs" / "presignal_v21_episode_builder" / "episode_rows.jsonl"
PARENT_MAP = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_parent_session_map.jsonl"
ATTENTION = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_attention_compatibility.jsonl"
REQUESTS = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_request_compatibility.jsonl"
PACKS = ROOT / "outputs" / "presignal_v21_step5_reuse" / "episode_pack_compatibility.jsonl"
PACK_A_INPUTS = ROOT / "outputs" / "presignal_v21_step5_reuse" / "event_path_forecast_inputs_pack_a.jsonl"
PACK_E_INPUTS = ROOT / "outputs" / "presignal_v21_step5_reuse" / "event_path_forecast_inputs_pack_e.jsonl"
LEGACY_OUTCOMES = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "outcome_rows.jsonl"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline"
LATEST_POINTER = OUTPUT_ROOT / "latest_prevalidation_manifest.json"

ROUND_START_UTC = "2024-05-01T00:00:00Z"
ROUND_END_UTC_EXCLUSIVE = "2024-08-01T00:00:00Z"
USER_FACING_TIMEZONE = "America/New_York"
GOVERNING_CONTRACT = contract.CONTRACT_VERSION
GOVERNING_SCHEMA = contract.SCHEMA_VERSION
ADMISSION_RULE = "OPTION_C_COMMON_DETERMINISTIC_PURE_PREDICTION_POPULATION"
VALIDATION_EPISODES = (
    "EP_EVENT_ccf7e8031b0d9b2e2443",
    "EP_BATCH_bd5b0d22e01fddb86cf1",
    "EP_BATCH_6fb320e5e8c5931f2373",
)


class PrevalidationError(RuntimeError):
    """A bounded prevalidation invariant was not met."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def rounded(value: float | None) -> float | None:
    return None if value is None else round(float(value), 6)


def load_round_population() -> list[dict[str, Any]]:
    episodes = read_jsonl(EPISODES)
    subset = [row for row in episodes if ROUND_START_UTC <= row["release_ts"] < ROUND_END_UTC_EXCLUSIVE]
    if len(subset) != 462:
        raise PrevalidationError("ROUND1_CANDIDATE_EPISODE_COUNT_UNEXPECTED")
    return subset


def indexed(path: Path, key: str = "episode_id") -> dict[str, dict[str, Any]]:
    return {row[key]: row for row in read_jsonl(path)}


def attention_status(attention_row: Mapping[str, Any]) -> str:
    reason = str(attention_row.get("reason") or "")
    if attention_row.get("status") == "COMPATIBLE":
        return "ATTENTION_LINEAGE_AVAILABLE"
    if reason == "ATTENTION_MAP_MISSING":
        return "ATTENTION_LINEAGE_MISSING"
    if reason == "ATTENTION_LINEAGE_MISMATCH":
        return "ATTENTION_LINEAGE_MISMATCH"
    return "ATTENTION_LINEAGE_MISMATCH"


def admission_status(
    episode: Mapping[str, Any],
    parent_row: Mapping[str, Any],
    request_row: Mapping[str, Any],
    pack_row: Mapping[str, Any],
    outcome_row: Mapping[str, Any],
) -> tuple[str, str | None]:
    if parent_row.get("status") != "MATCHED":
        return "EXCLUDED_LINEAGE_UNSAFE", "NO_EXACT_PARENT_SESSION"
    if request_row.get("status") != "COMPATIBLE":
        return "EXCLUDED_PACK_A_UNAVAILABLE", str(request_row.get("reason") or "REQUEST_COMPATIBILITY_UNAVAILABLE")
    if pack_row.get("status") != "COMPATIBLE":
        return "EXCLUDED_PACK_E_UNAVAILABLE", str(pack_row.get("reason") or "PACK_COMPATIBILITY_UNAVAILABLE")
    if outcome_row.get("status") != "VALID" or outcome_row.get("direction_15m") == "UNAVAILABLE" or outcome_row.get("pips_15m") is None:
        return "EXCLUDED_OUTCOME_UNAVAILABLE", str(outcome_row.get("error_message") or "OUTCOME_NOT_VALID")
    return "ELIGIBLE", None


def build_population_admission_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episodes = load_round_population()
    parent_map = indexed(PARENT_MAP)
    attention_map = indexed(ATTENTION)
    request_map = indexed(REQUESTS)
    pack_map = indexed(PACKS)
    outcome_map = indexed(LEGACY_OUTCOMES)
    rows: list[dict[str, Any]] = []
    validation_candidates: dict[str, dict[str, Any]] = {}
    for episode in sorted(episodes, key=lambda row: (row["release_ts"], row["episode_id"])):
        episode_id = episode["episode_id"]
        parent_row = parent_map[episode_id]
        attention_row = attention_map[episode_id]
        request_row = request_map[episode_id]
        pack_row = pack_map[episode_id]
        outcome_row = outcome_map[episode_id]
        status, exclusion_detail = admission_status(episode, parent_row, request_row, pack_row, outcome_row)
        record = {
            "episode_id": episode_id,
            "release_ts": episode["release_ts"],
            "forecast_cutoff_ts": episode["forecast_cutoff_ts"],
            "same_time_cluster_flag": episode["same_time_cluster_flag"],
            "member_event_count": episode["member_event_count"],
            "member_event_ids": list(episode["member_event_ids"]),
            "population_status": status,
            "population_exclusion_detail": exclusion_detail,
            "historical_attention_status": attention_status(attention_row),
            "parent_session_status": parent_row.get("status"),
            "parent_session_reason": parent_row.get("reason"),
            "request_compatibility_status": request_row.get("status"),
            "request_compatibility_reason": request_row.get("reason"),
            "pack_compatibility_status": pack_row.get("status"),
            "pack_compatibility_reason": pack_row.get("reason"),
            "legacy_outcome_status": outcome_row.get("status"),
            "legacy_outcome_direction_15m": outcome_row.get("direction_15m"),
            "legacy_outcome_id": outcome_row.get("outcome_id"),
            "eligible_under_round1_option_c": status == "ELIGIBLE",
        }
        if episode_id in VALIDATION_EPISODES:
            validation_candidates[episode_id] = record
        rows.append(record)
    counts = Counter(row["population_status"] for row in rows)
    if counts["ELIGIBLE"] + sum(value for key, value in counts.items() if key != "ELIGIBLE") != 462:
        raise PrevalidationError("ROUND1_POPULATION_RECONCILIATION_FAILED")
    for episode_id in VALIDATION_EPISODES:
        if episode_id not in validation_candidates:
            raise PrevalidationError("VALIDATION_EPISODE_MISSING:" + episode_id)
    return rows, {
        "candidate_episodes": len(rows),
        "eligible_episodes": counts["ELIGIBLE"],
        "excluded_episodes": len(rows) - counts["ELIGIBLE"],
        "by_population_status": dict(sorted(counts.items())),
        "attention_metadata": dict(sorted(Counter(row["historical_attention_status"] for row in rows).items())),
        "validation_candidates": validation_candidates,
    }


def approximate_sidecar(legacy: Mapping[str, Any]) -> dict[str, Any]:
    state = "APPROXIMATION_ONLY" if legacy.get("price_5m") is not None and legacy.get("anchor_price") is not None else "UNAVAILABLE_UNSUPPORTED_RESOLUTION"
    if state != "APPROXIMATION_ONLY":
        return {
            "immediate_impulse_outcome_state": state,
            "immediate_impulse_method_version": contract.IMMEDIATE_IMPULSE_METHOD_VERSION,
            "immediate_impulse_window_seconds": contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT,
            "first_meaningful_excursion_direction": "UNAVAILABLE",
            "first_meaningful_excursion_timestamp": None,
            "first_meaningful_excursion_pips": None,
            "confirmed_initial_direction": "UNAVAILABLE",
            "initial_direction_confirmation_timestamp": None,
            "initial_peak_pips": None,
            "initial_peak_timestamp": None,
            "maximum_opposite_excursion_pips": None,
            "false_initial_excursion_flag": False,
            "false_initial_excursion_direction": None,
            "initial_peak_retention_at_t5": None,
        }
    confirmed = str(legacy.get("initial_direction") or "FLAT")
    first_direction = confirmed if confirmed in {"UP", "DOWN", "FLAT"} else "FLAT"
    first_ts = (legacy.get("source_lineage") or {}).get("horizon_observation_ts", {}).get("5")
    first_pips = legacy.get("pips_5m")
    if first_direction == "UP":
        initial_peak_pips = legacy.get("max_up_pips")
        initial_peak_ts = legacy.get("max_up_ts")
        opposite_excursion = legacy.get("max_down_pips")
    elif first_direction == "DOWN":
        initial_peak_pips = legacy.get("max_down_pips")
        initial_peak_ts = legacy.get("max_down_ts")
        opposite_excursion = legacy.get("max_up_pips")
    else:
        initial_peak_pips = 0.0
        initial_peak_ts = None
        opposite_excursion = 0.0
        first_ts = None
        first_pips = 0.0
    retention = None
    if first_direction in {"UP", "DOWN"} and initial_peak_pips not in (None, 0):
        retention = rounded(float(legacy["pips_5m"]) / float(initial_peak_pips))
    return {
        "immediate_impulse_outcome_state": state,
        "immediate_impulse_method_version": contract.IMMEDIATE_IMPULSE_METHOD_VERSION,
        "immediate_impulse_window_seconds": contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT,
        "first_meaningful_excursion_direction": first_direction,
        "first_meaningful_excursion_timestamp": first_ts,
        "first_meaningful_excursion_pips": 0.0 if first_direction == "FLAT" else first_pips,
        "confirmed_initial_direction": first_direction,
        "initial_direction_confirmation_timestamp": first_ts,
        "initial_peak_pips": initial_peak_pips,
        "initial_peak_timestamp": initial_peak_ts,
        "maximum_opposite_excursion_pips": opposite_excursion,
        "false_initial_excursion_flag": False,
        "false_initial_excursion_direction": None,
        "initial_peak_retention_at_t5": retention,
    }


def convert_legacy_outcome(legacy: Mapping[str, Any], *, acquisition_ts: str) -> dict[str, Any]:
    base = {
        "object": "OUTCOME",
        "schema_version": contract.SCHEMA_VERSION,
        "system_version": contract.SYSTEM_VERSION,
        "outcome_id": "",
        "episode_id": legacy["episode_id"],
        "session_id": legacy["session_id"],
        "release_ts": legacy["release_ts"],
        "anchor_price_ts": legacy["anchor_price_ts"],
        "anchor_price": legacy["anchor_price"],
        "price_5m": legacy["price_5m"],
        "price_15m": legacy["price_15m"],
        "price_30m": legacy["price_30m"],
        "price_60m": legacy["price_60m"],
        "pips_5m": legacy["pips_5m"],
        "pips_15m": legacy["pips_15m"],
        "pips_30m": legacy["pips_30m"],
        "pips_60m": legacy["pips_60m"],
        "direction_5m": legacy["direction_5m"],
        "direction_15m": legacy["direction_15m"],
        "direction_30m": legacy["direction_30m"],
        "direction_60m": legacy["direction_60m"],
        "max_up_pips": legacy["max_up_pips"],
        "max_down_pips": legacy["max_down_pips"],
        "max_up_ts": legacy["max_up_ts"],
        "max_down_ts": legacy["max_down_ts"],
        "initial_direction": legacy["initial_direction"],
        "reversal_flag": legacy["reversal_flag"],
        "reversal_ts": legacy["reversal_ts"],
        "intervening_event_flag": legacy["intervening_event_flag"],
        "market_data_provider": legacy["market_data_provider"],
        "source_lineage": {
            **dict(legacy["source_lineage"]),
            "lineage_origin": "outputs/presignal_v21_episode_outcomes/outcome_rows.jsonl",
            "legacy_schema_version": legacy["schema_version"],
            "conversion_rule": "presignal_v21_historical_baseline_prevalidation_v1_1",
        },
        "acquisition_ts": acquisition_ts,
        "outcome_fingerprint": "",
        "status": legacy["status"],
        "error_message": legacy["error_message"],
    }
    if legacy["status"] == "VALID":
        base.update(approximate_sidecar(legacy))
        base["error_message"] = None
    else:
        base.update({
            "immediate_impulse_outcome_state": "OUTCOME_UNAVAILABLE",
            "immediate_impulse_method_version": contract.IMMEDIATE_IMPULSE_METHOD_VERSION,
            "immediate_impulse_window_seconds": contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT,
            "first_meaningful_excursion_direction": "UNAVAILABLE",
            "first_meaningful_excursion_timestamp": None,
            "first_meaningful_excursion_pips": None,
            "confirmed_initial_direction": "UNAVAILABLE",
            "initial_direction_confirmation_timestamp": None,
            "initial_peak_pips": None,
            "initial_peak_timestamp": None,
            "maximum_opposite_excursion_pips": None,
            "false_initial_excursion_flag": False,
            "false_initial_excursion_direction": None,
            "initial_peak_retention_at_t5": None,
        })
    base["outcome_id"] = contract.outcome_id_for(base)
    base["outcome_fingerprint"] = contract._fingerprint(base, "outcome_fingerprint", ("acquisition_ts", "status", "error_message"))
    contract.validate_outcome(base)
    return base


def validation_pairs_by_episode() -> dict[str, list[tuple[str, str]]]:
    rows_a = read_jsonl(PACK_A_INPUTS)
    rows_e = read_jsonl(PACK_E_INPUTS)
    keys_a = {(row["episode_id"], row["provider"], row["model"]) for row in rows_a}
    keys_e = {(row["episode_id"], row["provider"], row["model"]) for row in rows_e}
    pairs = sorted(keys_a & keys_e)
    result: dict[str, list[tuple[str, str]]] = {}
    for episode_id, provider, model in pairs:
        if episode_id in VALIDATION_EPISODES:
            result.setdefault(episode_id, []).append((provider, model))
    return result


def build_prevalidation(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    admission_rows, population_summary = build_population_admission_rows()
    validation_info = population_summary["validation_candidates"]
    for episode_id, record in validation_info.items():
        if record["population_status"] != "ELIGIBLE":
            raise PrevalidationError("VALIDATION_EPISODE_NOT_ELIGIBLE:" + episode_id)
    legacy_outcomes = indexed(LEGACY_OUTCOMES)
    pair_map = validation_pairs_by_episode()
    if set(pair_map) != set(VALIDATION_EPISODES):
        raise PrevalidationError("VALIDATION_PROVIDER_MATRIX_INCOMPLETE")
    expected_calls = sum(len(pair_map[episode_id]) * 2 for episode_id in VALIDATION_EPISODES)
    if expected_calls != 14:
        raise PrevalidationError("VALIDATION_CALL_COUNT_UNEXPECTED")
    run_id = "PPHB-R1-PREVALIDATION-" + now().replace(":", "").replace("-", "") + "-" + short({
        "contract": contract.CONTRACT_VERSION,
        "schema": contract.SCHEMA_VERSION,
        "episodes": VALIDATION_EPISODES,
    })
    run_dir = output_root / run_id
    acquisition_ts = now()
    outcomes = [convert_legacy_outcome(legacy_outcomes[episode_id], acquisition_ts=acquisition_ts) for episode_id in VALIDATION_EPISODES]
    if len({outcome["outcome_id"] for outcome in outcomes}) != len(outcomes):
        raise PrevalidationError("VALIDATION_OUTCOME_DUPLICATE_IDENTITY")
    market_lineage = [{
        "episode_id": outcome["episode_id"],
        "outcome_id": outcome["outcome_id"],
        "market_data_provider": outcome["market_data_provider"],
        "source_lineage": outcome["source_lineage"],
    } for outcome in outcomes]
    outcome_manifest = {
        "decision": "V1_1_VALIDATION_OUTCOMES_BUILT_FROM_ACCEPTED_LOCAL_LINEAGE",
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "episode_count": len(outcomes),
        "episodes": [outcome["episode_id"] for outcome in outcomes],
        "immediate_impulse_states": dict(sorted(Counter(outcome["immediate_impulse_outcome_state"] for outcome in outcomes).items())),
        "outcome_population_fingerprint": sha256([{key: row[key] for key in row if key != "acquisition_ts"} for row in outcomes]),
        "external_calls": {"provider": 0, "market_data": 0, "google": 0, "apps_script": 0},
    }
    validation_batch = []
    for episode_id in VALIDATION_EPISODES:
        candidates = pair_map[episode_id]
        validation_batch.append({
            "episode_id": episode_id,
            "release_ts": validation_info[episode_id]["release_ts"],
            "same_time_cluster_flag": validation_info[episode_id]["same_time_cluster_flag"],
            "provider_model_pairs": [{"provider": provider, "model": model} for provider, model in sorted(candidates)],
            "pack_arms_per_identity": 2,
            "expected_provider_calls": len(candidates) * 2,
            "ready_for_move2": True,
        })
    summary = {
        "round1_population_rule": ADMISSION_RULE,
        "governing_contract": GOVERNING_CONTRACT,
        "schema_version": GOVERNING_SCHEMA,
        "historical_boundaries": {
            "user_facing_timezone": USER_FACING_TIMEZONE,
            "start_utc_inclusive": ROUND_START_UTC,
            "end_utc_exclusive": ROUND_END_UTC_EXCLUSIVE,
        },
        "population_summary": population_summary,
        "validation_batch": validation_batch,
        "expected_validation_provider_calls": expected_calls,
        "outcomes_v1_1": {
            "relative_path": path_ref(run_dir / "outcomes_v1_1" / "outcome_rows.jsonl"),
            "episode_count": len(outcomes),
        },
    }
    write_jsonl(run_dir / "population_admission.jsonl", admission_rows)
    write_json(run_dir / "population_summary.json", summary)
    write_json(run_dir / "validation_batch.json", {"episodes": validation_batch, "expected_provider_calls": expected_calls})
    write_jsonl(run_dir / "outcomes_v1_1" / "outcome_rows.jsonl", outcomes)
    write_jsonl(run_dir / "outcomes_v1_1" / "market_data_lineage.jsonl", market_lineage)
    write_json(run_dir / "outcomes_v1_1" / "episode_outcome_manifest.json", outcome_manifest)
    pointer = {
        "prevalidation_run_id": run_id,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "population_admission_path": path_ref(run_dir / "population_admission.jsonl"),
        "population_summary_path": path_ref(run_dir / "population_summary.json"),
        "validation_batch_path": path_ref(run_dir / "validation_batch.json"),
        "outcomes_v1_1_path": path_ref(run_dir / "outcomes_v1_1" / "outcome_rows.jsonl"),
        "generated_at": acquisition_ts,
    }
    write_json(run_dir / "prevalidation_manifest.json", pointer)
    write_json(LATEST_POINTER, pointer)
    return run_dir, pointer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    run_dir, manifest = build_prevalidation(args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "prevalidation_manifest": manifest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
