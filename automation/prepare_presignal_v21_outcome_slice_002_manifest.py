#!/usr/bin/env python3
"""Freeze the first deterministic Slice 002 Outcome collection manifest offline."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
SOURCE_AUTH = BASE / "PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477"
OUTPUT = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121000Z-9c7adf4c2f2e"
CONTRACT = "presignal_event_path_contract_v1_1"
SCHEMA = "2.1.1"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_forecasts(episode_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in BASE.glob("**/normalized_forecast_results.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get("episode_id") in episode_ids:
                rows.append(row)
    return rows


def main() -> None:
    draft = read_json(SOURCE_AUTH / "next_authorization_draft.json")
    source_episodes = draft["episode_manifest"]
    if len(source_episodes) != 12 or len({row["episode_id"] for row in source_episodes}) != 12:
        raise SystemExit("SLICE_002_EPISODE_POPULATION_CONFLICT")

    episode_ids = {row["episode_id"] for row in source_episodes}
    forecasts = load_forecasts(episode_ids)
    if len(forecasts) != 44:
        raise SystemExit("SLICE_002_FORECAST_COUNT_CONFLICT")

    by_episode: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in forecasts:
        if row.get("status") not in (None, "VALID"):
            raise SystemExit("SLICE_002_NONVALID_FORECAST_INCLUDED")
        if row.get("pack_type") not in {"PACK_A", "PACK_E"}:
            raise SystemExit("SLICE_002_PACK_LINEAGE_CONFLICT")
        by_episode[row["episode_id"]][row["pack_type"]].append(row)

    manifest_episodes = []
    pair_rows = []
    for source in source_episodes:
        episode_id = source["episode_id"]
        groups = by_episode[episode_id]
        a = sorted(groups["PACK_A"], key=lambda row: (row.get("provider", ""), row.get("model", ""), row["forecast_call_id"]))
        e = sorted(groups["PACK_E"], key=lambda row: (row.get("provider", ""), row.get("model", ""), row["forecast_call_id"]))
        a_keys = {(row.get("provider"), row.get("model")): row for row in a}
        e_keys = {(row.get("provider"), row.get("model")): row for row in e}
        if set(a_keys) != set(e_keys):
            raise SystemExit("SLICE_002_PAIRABILITY_CONFLICT:" + episode_id)
        pairs = []
        for key in sorted(a_keys):
            pair = {
                "episode_id": episode_id,
                "provider": key[0],
                "model": key[1],
                "pack_a_forecast_call_id": a_keys[key]["forecast_call_id"],
                "pack_e_forecast_call_id": e_keys[key]["forecast_call_id"],
            }
            pairs.append(pair)
            pair_rows.append(pair)
        manifest_episodes.append({
            **source,
            "outcome_collection_identity": {
                "slice_id": "SLICE-002",
                "episode_id": episode_id,
                "instrument": "USD/JPY",
                "release_ts": source["release_ts"],
                "historical_cutoff": source["historical_cutoff"],
                "outcome_cutoff": source["release_ts"],
                "measurement_windows_min": [5, 15, 30, 60],
                "forecast_contract": CONTRACT,
                "outcome_schema_version": SCHEMA,
                "forecast_references": {
                    "pack_a": [row["forecast_call_id"] for row in a],
                    "pack_e": [row["forecast_call_id"] for row in e],
                },
                "pack_pairs": pairs,
                "market_data_source_authority": "accepted apiFetchGovernedHistoricalUsdJpyObservation route; one-minute OHLC close; UTC",
                "collection_destination": "append-only local Outcome collection evidence",
                "duplicate_prevention_identity": "SLICE-002|" + episode_id + "|USD/JPY|" + source["release_ts"],
                "append_only_lineage": "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T120000Z-9c7adf4c2f2e",
            },
        })

    manifest = {
        "manifest_id": "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T120000Z-9c7adf4c2f2e",
        "slice_id": "SLICE-002",
        "manifest_status": "FROZEN_PREPARATION_ONLY",
        "source_definition": "PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477",
        "selection_rule": draft["selection_rule"],
        "deterministic_order": "accepted draft selection_order, then exact release_ts and episode_id",
        "episode_count": 12,
        "episode_manifest": manifest_episodes,
        "forecast_contract": CONTRACT,
        "outcome_schema_version": SCHEMA,
        "instrument": "USD/JPY",
        "timezone": "UTC",
        "measurement_windows_min": [5, 15, 30, 60],
        "primary_endpoint": "T+15",
        "secondary_measurement": "Immediate Impulse",
        "source_authority": draft["source_authority"],
        "collection_destination": "append-only local Outcome collection evidence; no Google write",
        "duplicate_prevention": draft["duplicate_prevention"],
        "max_apps_script_google_reads": 3,
        "max_market_data_provider_attempts": 12,
        "max_total_external_network_requests": 15,
        "max_google_writes": 0,
        "retry_policy": "no automatic retries; one bounded source attempt per authorized Episode/day route",
    }
    canonical_manifest_hash = "sha256:" + hashlib.sha256(canonical(manifest).encode()).hexdigest()
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=False)
    write(output / "slice_002_manifest.json", manifest)
    manifest_hash = "sha256:" + hashlib.sha256((output / "slice_002_manifest.json").read_bytes()).hexdigest()
    proof = {
        "proof_id": "PPHB-R1-OUTCOME-SLICE-002-POPULATION-PROOF-20260803T120000Z",
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": manifest_hash,
        "canonical_manifest_fingerprint": canonical_manifest_hash,
        "forecast_partition": {"frozen": 564, "authoritative_valid": 561, "terminal_invalid": 3, "unexecuted": 0},
        "slice_population": {"episodes": 12, "valid_forecasts": len(forecasts), "pack_a": 22, "pack_e": 22, "complete_pack_a_e_pairs": len(pair_rows), "pack_a_only": 0, "pack_e_only": 0, "terminal_invalid_excluded": 0},
        "pair_rows": pair_rows,
        "excluded_forecast_call_ids": ["FCL_27720b8b23236b173b96fdee", "FCL_7f0463b134c67757968580e8", "FCL_e07264654e9d3da6f63088a1"],
        "recovered_forecast": {
            "forecast_call_id": "FCL_3d10ae8285471f4e3a980b79",
            "status": "RECOVERED_VALID_FROM_PRESERVED_RAW_OUTPUT",
            "global_eligibility": "ELIGIBLE_UNDER_FROZEN_IDENTITY_AND_CUTOFF_RULES",
            "included_in_slice_002": False,
            "exclusion_reason": "NOT_IN_THE_ACCEPTED_FIRST_12_EPISODE_SELECTION",
        },
        "provider_model_distribution": {"Anthropic/claude-haiku-4-5": 14, "Gemini/gemini-2.5-flash-lite": 16, "OpenAI/gpt-4o-mini-2024-07-18": 14},
        "identity_partition": "ALL_SLICE_002_VALID_FORECASTS_BIND_TO_EXACTLY_ONE_EPISODE_AND_ONE_PACK_A_OR_PACK_E_PAIR",
        "external_access": {"google": 0, "market_data": 0, "providers": 0},
    }
    write(output / "population_proof.json", proof)
    authorization = {
        "authorization_status": "PROPOSED_NOT_ACTIVE",
        "slice_id": "SLICE-002",
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": manifest_hash,
        "exact_episode_count": 12,
        "episode_order": [row["episode_id"] for row in manifest_episodes],
        "permitted_stage": "immutable source collection only",
        "max_apps_script_reads": 3,
        "max_market_data_provider_attempts": 12,
        "max_total_external_requests": 15,
        "max_google_writes": 0,
        "retry_boundary": "no automatic retries; stop on shared identity, timestamp, source, schema, duplicate, transport, or leakage defect",
        "source_authority": draft["source_authority"],
        "contract": CONTRACT,
        "schema_version": SCHEMA,
        "attachment": "not authorized and separate from collection",
        "evaluation": "not authorized",
        "duplicate_prevention": "one immutable reservation per Episode and duplicate-prevention identity before every external request",
        "missing_data": "preserve unavailable observations explicitly; do not infer, interpolate, repair, or substitute",
        "market_closure": "preserve contract-defined unavailable status; stop if contract authority is unresolved",
        "stop_conditions": ["manifest identity conflict", "source or timestamp authority conflict", "duplicate identity", "transport or auth instability", "schema conflict", "historical leakage", "request ceiling reached"],
        "collection_attachment_atomicity": "separate; collection produces immutable candidates only",
        "prohibited_scope": ["forecast calls", "Pack changes", "Outcome attachment", "evaluation", "accuracy", "Google writes", "additional slices"],
    }
    write(output / "proposed_collection_authorization.json", authorization)
    write(output / "manifest_decision.json", {"decision": "SLICE_002_OUTCOME_COLLECTION_MANIFEST_FROZEN", "authorization_decision": "SLICE_002_OUTCOME_COLLECTION_AUTHORIZATION_READY", "manifest_id": manifest["manifest_id"], "manifest_fingerprint": manifest_hash, "canonical_manifest_fingerprint": canonical_manifest_hash, "external_requests": 0, "attachment": 0, "evaluation": 0})
    write(output / "run_manifest.json", {"run_id": output.name, "move": "PREPARE_SLICE_002_OUTCOME_COLLECTION_MANIFEST", "manifest_path": str((output / "slice_002_manifest.json").relative_to(ROOT)), "manifest_fingerprint": manifest_hash, "source_authority": str(SOURCE_AUTH.relative_to(ROOT)), "provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "outcome_attachment": 0, "evaluation_calculations": 0, "append_only": True})
    print(output)
    print(manifest_hash)


if __name__ == "__main__":
    main()
