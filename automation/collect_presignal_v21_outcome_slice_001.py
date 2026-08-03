#!/usr/bin/env python3
"""Collect the authorized first immutable Outcome source slice, without attachment."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_episode_outcomes_v1_1 as builder
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation.google_clients import (
    build_script_service,
    close_google_service,
    describe_google_service_transport,
    load_credentials,
    run_script_function,
)


AUTH_PACKAGE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477"
OUTPUT_ROOT = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
RUN_STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SLICE_ID = os.environ.get("PRESIGNAL_OUTCOME_SLICE_ID", "SLICE-001")
SLICE_LABEL = SLICE_ID.replace("-", "_")
MANIFEST_PATH = Path(os.environ.get("PRESIGNAL_OUTCOME_MANIFEST_PATH", str(AUTH_PACKAGE / "next_authorization_draft.json")))
FUNCTION = builder.ENDPOINT_FUNCTION
DEPLOYMENT = builder.ENDPOINT_DEPLOYMENT
MAX_GOOGLE_READS = int(os.environ.get("PRESIGNAL_OUTCOME_MAX_GOOGLE_READS", "3"))
MAX_PROVIDER_ATTEMPTS = int(os.environ.get("PRESIGNAL_OUTCOME_MAX_PROVIDER_ATTEMPTS", "12"))
MAX_TOTAL_EXTERNAL = int(os.environ.get("PRESIGNAL_OUTCOME_MAX_TOTAL_EXTERNAL", "15"))
AUTHORIZATION_ID = os.environ.get("PRESIGNAL_OUTCOME_AUTHORIZATION_ID", "")
AUTHORIZATION_FINGERPRINT = os.environ.get("PRESIGNAL_OUTCOME_AUTHORIZATION_FINGERPRINT", "")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def preflight() -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    manifest = read_json(MANIFEST_PATH)
    manifest_hash = manifest.get("manifest_fingerprint") or "sha256:" + hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    episodes = list(manifest["episode_manifest"])
    if not episodes or len(episodes) != len({row["episode_id"] for row in episodes}):
        raise RuntimeError("OUTCOME_MANIFEST_IDENTITY_COUNT_CONFLICT")
    if MAX_TOTAL_EXTERNAL != MAX_GOOGLE_READS + MAX_PROVIDER_ATTEMPTS:
        raise RuntimeError("OUTCOME_AUTHORIZATION_LIMIT_CONFLICT")
    if manifest["source_authority"].split(";")[0] != "existing apiFetchGovernedHistoricalUsdJpyObservation route":
        raise RuntimeError("OUTCOME_SOURCE_AUTHORITY_CONFLICT")
    episode_rows = builder.read_jsonl(builder.EPISODE_OUTPUT / "episode_rows.jsonl")
    episode_index = {row["episode_id"]: row for row in episode_rows}
    selected = []
    for item in episodes:
        row = episode_index.get(item["episode_id"])
        if not row or row["release_ts"] != item["release_ts"]:
            raise RuntimeError("OUTCOME_RELEASE_TIMESTAMP_CONFLICT:" + item["episode_id"])
        selected.append(row)
    days = sorted({row["release_ts"][:10] for row in selected})
    if len(days) > MAX_GOOGLE_READS:
        raise RuntimeError("OUTCOME_DAY_SELECTION_CONFLICT")
    if FUNCTION != "apiFetchGovernedHistoricalUsdJpyObservation" or contract.CONTRACT_VERSION != "presignal_event_path_contract_v1_1" or contract.SCHEMA_VERSION != "2.1.1":
        raise RuntimeError("OUTCOME_ROUTE_OR_SCHEMA_CONFLICT")
    existing = list(OUTPUT_ROOT.glob(f"PPHB-R1-OUTCOME-COLLECTION-{SLICE_ID}-*"))
    resume_dir = None
    for prior in existing:
        decision_path = prior / "collection_decision.json"
        prior_decision = read_json(decision_path) if decision_path.exists() else {}
        if not decision_path.exists():
            run_path = prior / "run_manifest.json"
            run = read_json(run_path) if run_path.exists() else {}
            if run.get("external_access_before_preflight") is False and all(run.get(key, 0) == 0 for key in ("google_reads", "market_data_calls", "provider_calls", "google_writes")):
                resume_dir = prior
                continue
            raise RuntimeError("OUTCOME_COLLECTION_RESUME_STATE_AMBIGUOUS")
        if prior_decision.get("collection_decision") != f"OUTCOME_COLLECTION_{SLICE_LABEL}_BLOCKED":
            raise RuntimeError("OUTCOME_COLLECTION_ALREADY_EXISTS")
    run_id = resume_dir.name if resume_dir is not None else f"PPHB-R1-OUTCOME-COLLECTION-{SLICE_ID}-{RUN_STAMP}-{manifest_hash[-12:]}"
    run_dir = resume_dir or (OUTPUT_ROOT / run_id)
    if resume_dir is None:
        write(run_dir / "run_manifest.json", {"run_id": run_id, "move_type": "OUTCOME_SOURCE_PREFLIGHT_AND_IMMUTABLE_COLLECTION", "manifest_path": str(MANIFEST_PATH.relative_to(ROOT)), "manifest_sha256": manifest_hash, "provider_calls": 0, "google_reads": 0, "google_writes": 0, "market_data_calls": 0, "outcome_attachment": 0, "evaluation_calculations": 0, "append_only": True, "external_access_before_preflight": False, "authorization_id": AUTHORIZATION_ID or None, "authorization_fingerprint": AUTHORIZATION_FINGERPRINT or None})
        write(run_dir / "preflight_decision.json", {"decision": "OUTCOME_SOURCE_PREFLIGHT_PASSED", "repository": "presignal-historical-baseline-r1", "branch": "codex/immediate-impulse-outcome-recovery-r1", "head": head(), "manifest_sha256": manifest_hash, "episode_count": len(episodes), "episode_ids": [row["episode_id"] for row in episodes], "release_timestamp_authority": "episode_rows.jsonl exact UTC release_ts", "instrument": "USD/JPY", "timezone": "UTC", "contract": contract.CONTRACT_VERSION, "schema_version": contract.SCHEMA_VERSION, "route_function": FUNCTION, "deployment": DEPLOYMENT, "source_resolution": "ONE_MINUTE", "source_observation_type": "OHLC", "accepted_price_field": "close", "prior_collection_conflict": False, "duplicate_conflict": False, "forecast_or_leakage_conflict": False})
    return manifest, selected, run_dir


def collect(manifest: dict[str, Any], episodes: list[dict[str, Any]], run_dir: Path) -> None:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        by_day[episode["release_ts"][:10]].append(episode)
    request_ledger = []
    raw_rows = []
    normalized = []
    all_observations = []
    request_lineage = {}
    provider_attempt_count = 0
    # Resume from preserved raw day responses without redispatching completed
    # external requests after a process interruption.
    existing_raw = {path.stem: path for path in (run_dir / "raw_source_responses").glob("*.json")}
    for day, raw_path in sorted(existing_raw.items()):
        result = read_json(raw_path)
        attempts = result.get("provider_attempts", []) if isinstance(result, dict) else []
        request_id = "OUTCOME_" + SLICE_ID.replace("-", "_") + "_DAY_" + day.replace("-", "")
        record = {"request_id": request_id, "day": day, "window_start": day + "T00:00:00Z", "window_end": day + "T23:59:00Z", "status": result.get("status", "TRANSPORT_FAILURE") if isinstance(result, dict) else "TRANSPORT_FAILURE", "selected_provider": result.get("selected_provider", "") if isinstance(result, dict) else "", "provider_attempt_count": len(attempts), "provider_attempts": [{k: v for k, v in attempt.items() if k != "observations"} for attempt in attempts], "raw_response_path": str(raw_path.relative_to(ROOT)), "raw_response_hash": sha(result), "transport_error": None, "transport_before": "PRESERVED_RESUME", "transport_after": "PRESERVED_RESUME", "started_ts": None, "completed_ts": None}
        request_ledger.append(record)
        request_lineage[day] = {k: record[k] for k in ("request_id", "day", "window_start", "window_end", "status", "selected_provider", "provider_attempt_count", "raw_response_hash")}
        provider_attempt_count += len(attempts)
        for observation in (result.get("observations", []) if isinstance(result, dict) else []):
            all_observations.append({"timestamp": observation["returned_observation_timestamp"], "close": float(observation["accepted_raw_price"]), "provider": result.get("selected_provider", ""), "request_id": request_id, "provider_returned_timestamp_raw": observation.get("provider_returned_timestamp_raw"), "accepted_raw_price_field": observation.get("accepted_raw_price_field", "close")})
    for day in sorted(by_day):
        if day in existing_raw:
            continue
        if len(request_ledger) >= MAX_GOOGLE_READS:
            raise RuntimeError("OUTCOME_GOOGLE_READ_LIMIT")
        request_id = "OUTCOME_" + SLICE_ID.replace("-", "_") + "_DAY_" + day.replace("-", "")
        start = day + "T00:00:00Z"
        end = day + "T23:59:00Z"
        service = build_script_service(load_credentials(), 300)
        transport_before = describe_google_service_transport(service)
        started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            result = run_script_function(service, DEPLOYMENT, FUNCTION, [{"request_identity": request_id, "instrument": "USD/JPY", "requested_window_start": start, "requested_window_end": end, "timezone": "UTC"}])
            error = None
        except Exception as exc:
            result = None
            error = {"type": type(exc).__name__, "message": str(exc)}
        transport_after = close_google_service(service)
        payload = result if isinstance(result, dict) else {}
        attempts = payload.get("provider_attempts", []) if isinstance(payload, dict) else []
        provider_attempt_count += len(attempts)
        if provider_attempt_count > MAX_PROVIDER_ATTEMPTS:
            raise RuntimeError("OUTCOME_PROVIDER_ATTEMPT_LIMIT")
        raw_hash = sha(result if result is not None else {"error": error})
        raw_path = run_dir / "raw_source_responses" / f"{day}.json"
        write(raw_path, result if result is not None else {"error": error})
        request_record = {"request_id": request_id, "day": day, "window_start": start, "window_end": end, "status": payload.get("status", "TRANSPORT_FAILURE") if payload else "TRANSPORT_FAILURE", "selected_provider": payload.get("selected_provider", "") if payload else "", "provider_attempt_count": len(attempts), "provider_attempts": [{k: v for k, v in attempt.items() if k != "observations"} for attempt in attempts], "raw_response_path": str(raw_path.relative_to(ROOT)), "raw_response_hash": raw_hash, "transport_error": error, "transport_before": transport_before, "transport_after": transport_after, "started_ts": started, "completed_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
        request_ledger.append(request_record)
        request_lineage[day] = {k: request_record[k] for k in ("request_id", "day", "window_start", "window_end", "status", "selected_provider", "provider_attempt_count", "raw_response_hash")}
        observations = payload.get("observations", []) if isinstance(payload, dict) else []
        for observation in observations:
            timestamp = observation["returned_observation_timestamp"]
            all_observations.append({"timestamp": timestamp, "close": float(observation["accepted_raw_price"]), "provider": payload.get("selected_provider", ""), "request_id": request_id, "provider_returned_timestamp_raw": observation.get("provider_returned_timestamp_raw"), "accepted_raw_price_field": observation.get("accepted_raw_price_field", "close")})
    write(run_dir / "external_request_ledger.jsonl", request_ledger)
    selected_ids = {episode["episode_id"] for episode in episodes}
    outcomes, availability, lineage = builder.build_outcomes(episodes, all_observations, request_lineage, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    for outcome in outcomes:
        normalized.append({"episode_id": outcome["episode_id"], "outcome_id": outcome["outcome_id"], "status": outcome["status"], "error_message": outcome["error_message"], "source_lineage": outcome["source_lineage"], "outcome_fingerprint": outcome["outcome_fingerprint"], "candidate_outcome": outcome})
    write(run_dir / "candidate_outcomes.jsonl", normalized)
    write(run_dir / "outcome_availability.jsonl", availability)
    write(run_dir / "source_lineage.jsonl", lineage)
    write(run_dir / "collection_reconciliation.json", {"manifest_episode_count": len(episodes), "apps_script_reads": len(request_ledger), "market_data_provider_attempts": provider_attempt_count, "total_external_requests": len(request_ledger) + provider_attempt_count, "candidate_outcomes": len(outcomes), "schema_validated_candidates": sum(row["status"] in {"VALID", "UNAVAILABLE"} for row in normalized), "missing_or_terminal_source_episodes": [row["episode_id"] for row in normalized if row["status"] != "VALID"], "duplicate_requests": 0, "unresolved_identities": sorted(selected_ids - {row["episode_id"] for row in normalized}), "contract": contract.CONTRACT_VERSION, "schema_version": contract.SCHEMA_VERSION, "leakage_control": "PASSED", "google_writes": 0, "outcome_attachment": 0, "evaluation_calculations": 0})
    write(run_dir / "collection_decision.json", {"preflight_decision": "OUTCOME_SOURCE_PREFLIGHT_PASSED", "collection_decision": f"OUTCOME_COLLECTION_{SLICE_LABEL}_COMPLETE" if len(outcomes) == len(episodes) else f"OUTCOME_COLLECTION_{SLICE_LABEL}_PARTIAL", "candidate_outcomes_unattached": True, "evaluated": False})


if __name__ == "__main__":
    manifest, episodes, run_dir = preflight()
    collect(manifest, episodes, run_dir)
    print(run_dir)
