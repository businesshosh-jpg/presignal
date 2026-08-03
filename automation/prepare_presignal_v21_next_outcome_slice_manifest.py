#!/usr/bin/env python3
"""Freeze the next prospective Outcome slice from accepted local ledgers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PLAN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_planning" / "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
EPISODE_SOURCE = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit" / "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6" / "episode_population_manifest.jsonl"
SLICE_001 = BASE / "PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320" / "attached_outcomes.jsonl"
SLICE_002 = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121500Z-9c7adf4c2f2e" / "slice_002_manifest.json"
INVALID_CALLS = {
    "FCL_27720b8b23236b173b96fdee",
    "FCL_7f0463b134c67757968580e8",
    "FCL_e07264654e9d3da6f63088a1",
}
CONTRACT = "presignal_event_path_contract_v1_1"
SCHEMA = "2.1.1"
SLICE_ID = "SLICE-003"
TIMESTAMP = "20260803T154000Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def previous_episode_ids() -> set[str]:
    ids = {row["candidate_outcome"]["episode_id"] for row in load_jsonl(SLICE_001)}
    ids.update(row["episode_id"] for row in json.loads(SLICE_002.read_text())["episode_manifest"])
    if len(ids) != 12:
        raise ValueError("PREVIOUS_OUTCOME_SLICE_IDENTITY_CONFLICT")
    return ids


def build_package() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    ledger = {row["forecast_call_id"]: row for row in load_jsonl(PLAN / "authorized_forecast_call_ledger.jsonl")}
    if len(ledger) != 564:
        raise ValueError("FROZEN_FORECAST_CALL_COUNT_CONFLICT")
    episode_source = {row["episode_id"]: row for row in load_jsonl(EPISODE_SOURCE)}
    previous = previous_episode_ids()

    by_episode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call_id, row in ledger.items():
        if call_id in INVALID_CALLS:
            continue
        by_episode[row["episode_id"]].append(row)

    ordered = sorted(by_episode, key=lambda episode_id: min(row["execution_order"] for row in by_episode[episode_id]))
    excluded_pairability: list[dict[str, Any]] = []
    candidates: list[str] = []
    for episode_id in ordered:
        rows = by_episode[episode_id]
        if episode_id in previous:
            continue
        pack_a = {(row["provider"], row["model"]) for row in rows if row["pack_type"] == "PACK_A"}
        pack_e = {(row["provider"], row["model"]) for row in rows if row["pack_type"] == "PACK_E"}
        if pack_a != pack_e or not pack_a:
            excluded_pairability.append({
                "episode_id": episode_id,
                "reason": "PACK_A_E_PROVIDER_MODEL_PAIRABILITY_CONFLICT",
                "pack_a_provider_models": sorted(pack_a),
                "pack_e_provider_models": sorted(pack_e),
                "valid_forecast_call_ids": sorted(row["forecast_call_id"] for row in rows),
            })
            continue
        source = episode_source.get(episode_id)
        if not source or not source.get("release_ts"):
            raise ValueError("EPISODE_RELEASE_TIMESTAMP_CONFLICT:" + episode_id)
        candidates.append(episode_id)

    selected = candidates[:12]
    if len(selected) != 12:
        raise ValueError("NEXT_SLICE_UNIQUE_SELECTION_CONFLICT")

    manifest_episodes: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    for selection_order, episode_id in enumerate(selected, 1):
        rows = by_episode[episode_id]
        source = episode_source[episode_id]
        pack_a = sorted((row for row in rows if row["pack_type"] == "PACK_A"), key=lambda row: (row["provider"], row["model"], row["forecast_call_id"]))
        pack_e = sorted((row for row in rows if row["pack_type"] == "PACK_E"), key=lambda row: (row["provider"], row["model"], row["forecast_call_id"]))
        a_by_key = {(row["provider"], row["model"]): row for row in pack_a}
        e_by_key = {(row["provider"], row["model"]): row for row in pack_e}
        pairs = []
        for provider, model in sorted(a_by_key):
            pair = {
                "episode_id": episode_id,
                "provider": provider,
                "model": model,
                "pack_a_forecast_call_id": a_by_key[(provider, model)]["forecast_call_id"],
                "pack_e_forecast_call_id": e_by_key[(provider, model)]["forecast_call_id"],
            }
            pairs.append(pair)
            pair_rows.append(pair)
        first = min(rows, key=lambda row: row["execution_order"])
        selected_rows.append({
            "episode_id": episode_id,
            "selection_order": selection_order,
            "execution_order": min(row["execution_order"] for row in rows),
            "release_ts": source["release_ts"],
            "historical_cutoff": first["historical_cutoff"],
            "valid_forecast_count": len(rows),
            "pack_a_count": len(pack_a),
            "pack_e_count": len(pack_e),
            "pack_pairs": pairs,
        })
        manifest_episodes.append({
            "episode_id": episode_id,
            "first_forecast_call_id": first["forecast_call_id"],
            "first_pack": first["pack_type"],
            "historical_cutoff": first["historical_cutoff"],
            "release_ts": source["release_ts"],
            "selection_order": selection_order,
            "outcome_collection_identity": {
                "slice_id": SLICE_ID,
                "episode_id": episode_id,
                "instrument": "USD/JPY",
                "release_ts": source["release_ts"],
                "historical_cutoff": first["historical_cutoff"],
                "outcome_cutoff": source["release_ts"],
                "measurement_windows_min": [5, 15, 30, 60],
                "forecast_contract": CONTRACT,
                "outcome_schema_version": SCHEMA,
                "forecast_references": {
                    "pack_a": [row["forecast_call_id"] for row in pack_a],
                    "pack_e": [row["forecast_call_id"] for row in pack_e],
                },
                "pack_pairs": pairs,
                "market_data_source_authority": "existing apiFetchGovernedHistoricalUsdJpyObservation route; USD/JPY; UTC; one-minute OHLC close; provider fallback tiingo -> eodhd -> massive -> twelvedata",
                "collection_destination": "append-only local Outcome collection evidence",
                "duplicate_prevention_identity": f"{SLICE_ID}|{episode_id}|USD/JPY|{source['release_ts']}",
                "append_only_lineage": f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE_ID}-{TIMESTAMP}",
            },
        })

    base_manifest = {
        "manifest_id": f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE_ID}-{TIMESTAMP}",
        "slice_id": SLICE_ID,
        "manifest_status": "FROZEN_PREPARATION_ONLY",
        "source_definition": "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1",
        "selection_rule": "first 12 unique eligible Episode identities after accepted Slice 002, ordered by earliest frozen forecast execution_order; exclude prior accepted Outcome Episodes, terminal-invalid calls, and unresolved Pack A/E pairability conflicts",
        "deterministic_order": "earliest frozen forecast execution_order, then exact release_ts and episode_id",
        "episode_count": len(manifest_episodes),
        "episode_manifest": manifest_episodes,
        "forecast_contract": CONTRACT,
        "outcome_schema_version": SCHEMA,
        "instrument": "USD/JPY",
        "timezone": "UTC",
        "measurement_windows_min": [5, 15, 30, 60],
        "primary_endpoint": "T+15",
        "secondary_measurement": "Immediate Impulse",
        "source_authority": "existing apiFetchGovernedHistoricalUsdJpyObservation route; one-minute OHLC close; UTC",
        "collection_destination": "append-only local Outcome collection evidence; no Google write",
        "duplicate_prevention": "one immutable outcome_id and one reservation per Slice/Episode/instrument/release timestamp; fail closed on conflict",
        "max_apps_script_google_reads": 3,
        "max_market_data_provider_attempts": 12,
        "max_total_external_network_requests": 15,
        "max_google_writes": 0,
        "retry_policy": "no automatic retries; one bounded source attempt per authorized Episode/day route",
        "authorized_forecast_population": {
            "valid_forecasts": len(selected_rows and [row for episode_id in selected for row in by_episode[episode_id]]),
            "pack_a": sum(row["pack_a_count"] for row in selected_rows),
            "pack_e": sum(row["pack_e_count"] for row in selected_rows),
            "complete_pack_a_e_pairs": len(pair_rows),
            "pack_a_only": 0,
            "pack_e_only": 0,
        },
    }
    manifest_hash = digest(base_manifest)
    manifest = {**base_manifest, "manifest_fingerprint": manifest_hash}

    auth = {
        "authorization_status": "PROPOSED_NOT_ACTIVE",
        "authorization_scope": "inputs only; no external activity authorized",
        "slice_id": SLICE_ID,
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": manifest_hash,
        "exact_episode_count": len(manifest_episodes),
        "episode_order": selected,
        "collection_identities": [episode["outcome_collection_identity"] for episode in manifest_episodes],
        "max_apps_script_reads": 3,
        "max_market_data_provider_attempts": 12,
        "max_total_external_requests": 15,
        "max_google_writes": 0,
        "max_attachment_records": len(manifest_episodes),
        "attachment_destination": "append-only local Outcome attachment evidence",
        "evaluation_population": manifest["authorized_forecast_population"],
        "permitted_metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"],
        "primary_endpoint": "T+15",
        "secondary_measurement": "Immediate Impulse",
        "retry_boundary": "no automatic retries",
        "stop_conditions": ["identity or cutoff conflict", "source/schema authority conflict", "duplicate identity", "transport/auth instability", "historical leakage", "partial or ambiguous remote state", "ceiling exceeded"],
        "single_use_and_resume": "inactive until separately frozen; later authorization is single-use and resumes only from accepted append-only stage artifacts",
        "permitted_mechanical_repairs": "general deterministic stage-interface repairs only; preserve semantic values, hashes, ceilings, and canonical stages",
        "evaluation_authorized": False,
        "prohibited_scope": ["Google writes", "external collection", "attachment", "evaluation", "accuracy calculation", "additional slices", "forecast changes", "Pack changes"],
    }
    proof = {
        "proof_id": f"PPHB-R1-OUTCOME-{SLICE_ID}-POPULATION-PROOF-{TIMESTAMP}",
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": manifest_hash,
        "selection_rule": base_manifest["selection_rule"],
        "prior_slice_exclusions": {"slice_001_and_slice_002_unique_episode_count": len(previous), "episode_ids": sorted(previous)},
        "terminal_invalid_exclusions": sorted(INVALID_CALLS),
        "pairability_exclusions": excluded_pairability,
        "selected_episodes": selected_rows,
        "population": manifest["authorized_forecast_population"] | {"episodes": len(manifest_episodes)},
        "forecast_partition": {"frozen": 564, "authoritative_valid": 561, "terminal_invalid": 3, "unexecuted": 0, "remote_state_unknown": 0},
        "recovered_forecast": {"forecast_call_id": "FCL_3d10ae8285471f4e3a980b79", "status": "RECOVERED_VALID_FROM_PRESERVED_RAW_OUTPUT", "eligible_under_identity_and_cutoff_rules": True, "included_in_slice": False},
        "external_access": {"provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "attachment": 0, "evaluation": 0},
        "unresolved_conflicts": [],
    }
    decision = {
        "decision": "NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN",
        "authorization_inputs_decision": "NEXT_PROSPECTIVE_SLICE_AUTHORIZATION_INPUTS_READY",
        "manifest_id": manifest["manifest_id"],
        "manifest_fingerprint": manifest_hash,
        "next_move": "freeze one active end-to-end authorization for this new Slice",
        "external_access": 0,
    }
    return manifest, auth, proof, decision


def main() -> None:
    manifest, auth, proof, decision = build_package()
    fingerprint = manifest["manifest_fingerprint"].split(":", 1)[1][:20]
    output = BASE / f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE_ID}-{TIMESTAMP}-{fingerprint}"
    if output.exists():
        raise SystemExit("OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write_json(output / "slice_003_manifest.json", manifest)
    write_json(output / "population_proof.json", proof)
    write_json(output / "exclusion_proof.json", {"prior_slices": proof["prior_slice_exclusions"], "terminal_invalid": proof["terminal_invalid_exclusions"], "pairability": proof["pairability_exclusions"], "unresolved_conflicts": []})
    write_json(output / "proposed_end_to_end_authorization_inputs.json", auth)
    write_json(output / "manifest_decision.json", decision)
    write_json(output / "run_manifest.json", {"run_id": output.name, "move": "PREPARE_NEXT_PROSPECTIVE_OUTCOME_SLICE_MANIFEST", "manifest_path": str((output / "slice_003_manifest.json").relative_to(ROOT)), "manifest_fingerprint": manifest["manifest_fingerprint"], "provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "outcome_attachment": 0, "evaluation_calculations": 0, "append_only": True})
    print(output)
    print(manifest["manifest_id"])
    print(manifest["manifest_fingerprint"])


if __name__ == "__main__":
    main()
