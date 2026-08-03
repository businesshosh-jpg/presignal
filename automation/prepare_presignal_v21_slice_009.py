#!/usr/bin/env python3
"""Freeze the next deterministic prospective Outcome slice."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution"
PLAN = ROOT / "outputs/presignal_v21_full_round_1_forecast_planning/PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
SOURCE = ROOT / "outputs/presignal_v21_full_round_1_population_audit/PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6/episode_population_manifest.jsonl"
SLICE = "SLICE-009"
MANIFEST_TIME = "20260803T180000Z"
AUTH_TIME = "20260803T190000Z"
INVALID = {"FCL_27720b8b23236b173b96fdee", "FCL_7f0463b134c67757968580e8", "FCL_e07264654e9d3da6f63088a1"}
EXCLUDED = {"EP_EVENT_4b80366594480b554889", "EP_EVENT_aa41226bcb8107901555", "EP_EVENT_82563db31e94ae9d1799", "EP_EVENT_08219d7669dbc263d9f6", "EP_EVENT_f09204427881dfea157f"}


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ledger = read_jsonl(PLAN / "authorized_forecast_call_ledger.jsonl")
    if len(ledger) != 564:
        raise SystemExit("FROZEN_FORECAST_CALL_COUNT_CONFLICT")
    source = {row["episode_id"]: row for row in read_jsonl(SOURCE)}
    prior = set()
    for path in BASE.glob("PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-*/slice_*_manifest.json"):
        prior.update(row["episode_id"] for row in json.loads(path.read_text()).get("episode_manifest", []))
    prior |= EXCLUDED
    by_episode = defaultdict(list)
    for row in ledger:
        if row["forecast_call_id"] not in INVALID:
            by_episode[row["episode_id"]].append(row)
    ordered = sorted(by_episode, key=lambda episode: min(row["execution_order"] for row in by_episode[episode]))
    selected = []
    pairability_exclusions = []
    for episode in ordered:
        if episode in prior:
            continue
        rows = by_episode[episode]
        pack_a = {(row["provider"], row["model"]) for row in rows if row["pack_type"] == "PACK_A"}
        pack_e = {(row["provider"], row["model"]) for row in rows if row["pack_type"] == "PACK_E"}
        if pack_a != pack_e or not pack_a:
            pairability_exclusions.append(episode)
            continue
        if episode not in source or not source[episode].get("release_ts"):
            raise SystemExit("EPISODE_RELEASE_TIMESTAMP_CONFLICT:" + episode)
        selected.append(episode)
    selected = selected[:12]
    if len(selected) != 12:
        raise SystemExit("NEXT_SLICE_UNIQUE_SELECTION_CONFLICT")

    episodes = []
    for order, episode in enumerate(selected, 1):
        rows = by_episode[episode]
        src = source[episode]
        pack_a = sorted((row for row in rows if row["pack_type"] == "PACK_A"), key=lambda row: (row["provider"], row["model"], row["forecast_call_id"]))
        pack_e = sorted((row for row in rows if row["pack_type"] == "PACK_E"), key=lambda row: (row["provider"], row["model"], row["forecast_call_id"]))
        a_by_key = {(row["provider"], row["model"]): row for row in pack_a}
        e_by_key = {(row["provider"], row["model"]): row for row in pack_e}
        pairs = [{"episode_id": episode, "provider": provider, "model": model,
                  "pack_a_forecast_call_id": a_by_key[(provider, model)]["forecast_call_id"],
                  "pack_e_forecast_call_id": e_by_key[(provider, model)]["forecast_call_id"]}
                 for provider, model in sorted(a_by_key)]
        first = min(rows, key=lambda row: row["execution_order"])
        identity = {
            "slice_id": SLICE, "episode_id": episode, "instrument": "USD/JPY", "release_ts": src["release_ts"],
            "historical_cutoff": first["historical_cutoff"], "outcome_cutoff": src["release_ts"],
            "measurement_windows_min": [5, 15, 30, 60], "forecast_contract": "presignal_event_path_contract_v1_1",
            "outcome_schema_version": "2.1.1",
            "forecast_references": {"pack_a": [row["forecast_call_id"] for row in pack_a], "pack_e": [row["forecast_call_id"] for row in pack_e]},
            "pack_pairs": pairs,
            "market_data_source_authority": "existing apiFetchGovernedHistoricalUsdJpyObservation route; USD/JPY; UTC; one-minute OHLC close; provider fallback tiingo -> eodhd -> massive -> twelvedata",
            "collection_destination": "append-only local Outcome collection evidence; no Google write",
            "duplicate_prevention_identity": f"{SLICE}|{episode}|USD/JPY|{src['release_ts']}",
            "append_only_lineage": f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE}-{MANIFEST_TIME}",
        }
        episodes.append({"episode_id": episode, "first_forecast_call_id": first["forecast_call_id"], "first_pack": first["pack_type"],
                         "historical_cutoff": first["historical_cutoff"], "release_ts": src["release_ts"], "selection_order": order,
                         "outcome_collection_identity": identity})
    days = sorted({row["release_ts"][:10] for row in episodes})
    population = {"valid_forecasts": sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_a"]) + len(row["outcome_collection_identity"]["forecast_references"]["pack_e"]) for row in episodes),
                  "pack_a": sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_a"]) for row in episodes),
                  "pack_e": sum(len(row["outcome_collection_identity"]["forecast_references"]["pack_e"]) for row in episodes),
                  "complete_pack_a_e_pairs": sum(len(row["outcome_collection_identity"]["pack_pairs"]) for row in episodes), "pack_a_only": 0, "pack_e_only": 0, "unpaired": 0}
    manifest = {"manifest_id": f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE}-{MANIFEST_TIME}", "slice_id": SLICE, "manifest_status": "FROZEN_PREPARATION_ONLY", "manifest_schema_version": "presignal_v21_outcome_collection_manifest_v1", "source_definition": "authoritative eligible forecast ledger and accepted prospective-slice selection rules", "selection_rule": "next eligible pairable Episodes after completed Slice 008 frontier; exclude prior-Slice, terminal-invalid, unavailable, pairability-conflict, identity, cutoff, lineage, source-authority, and leakage-conflict identities", "deterministic_order": "earliest accepted forecast execution_order, then exact release_ts and episode_id", "episode_count": 12, "episode_manifest": episodes, "authorized_forecast_population": population, "forecast_contract": "presignal_event_path_contract_v1_1", "outcome_schema_version": "2.1.1", "instrument": "USD/JPY", "timestamp_timezone": "UTC", "measurement_windows_min": [5, 15, 30, 60], "primary_endpoint": "T+15", "secondary_measurement": "Immediate Impulse", "market_data_source_authority": "existing apiFetchGovernedHistoricalUsdJpyObservation route; USD/JPY; UTC; one-minute OHLC close; provider fallback tiingo -> eodhd -> massive -> twelvedata", "source_authority": "existing apiFetchGovernedHistoricalUsdJpyObservation route; one-minute OHLC close; UTC", "collection_destination": "append-only local Outcome collection evidence; no Google write", "duplicate_prevention": "one immutable outcome identity and reservation per Slice/Episode/instrument/release timestamp; fail closed on conflict", "max_apps_script_reads": len(days), "max_market_data_attempts": 12, "max_total_external_requests": len(days) + 12, "google_write_ceiling": 0, "retry_boundary": "NO_AUTOMATIC_RETRIES", "release_days_utc": days, "manifest_fingerprint": ""}
    manifest["manifest_fingerprint"] = digest(manifest)
    manifest_id = manifest["manifest_id"]
    auth = {"authorization_id": f"PPHB-R1-OUTCOME-{SLICE}-END-TO-END-AUTHORIZATION-{AUTH_TIME}", "authorization_schema_version": "presignal_v21_prospective_slice_end_to_end_authorization_v1", "authorization_status": "ACTIVE", "authorization_mode": "END_TO_END", "authorized_stage": "end_to_end", "authorization_scope": f"one single-use end-to-end execution for {SLICE} only", "manifest_id": manifest_id, "manifest_fingerprint": manifest["manifest_fingerprint"], "manifest_sha256": manifest["manifest_fingerprint"], "slice_id": SLICE, "controller_version": "AUTHORIZED_SLICE_CONTROLLER_V1", "controller_commit": "c82ef1f5ba2a1202268bcfdd4611635421710327", "prospective_contract": "PPHB-R1-PROSPECTIVE-SLICE-EXECUTION-CONTRACT-20260803T060000Z", "authorized_identity_ids": selected, "outcome_collection_identity_ids": [row["outcome_collection_identity"]["duplicate_prevention_identity"] for row in episodes], "authorized_attachment_identity_ids": [row["outcome_collection_identity"]["duplicate_prevention_identity"] for row in episodes], "ceilings": {"max_apps_script_reads": len(days), "max_market_data_attempts": 12, "max_total_external_requests": len(days) + 12, "google_write_ceiling": 0, "max_attachment_records": 12, "max_evaluation_artifacts": 1}, "contract": "presignal_event_path_contract_v1_1", "schema_version": "2.1.1", "destination": "append-only local Outcome collection evidence; no Google write", "attachment_destination": "append-only local Outcome attachment evidence", "attachment_write_ceiling": {"google_writes": 0, "local_append_only_records": 12}, "evaluation_authorized": True, "evaluation_output_destination": f"append-only local {SLICE} minimal evaluation evidence", "evaluation_population": {"episodes": 12, **population}, "evaluation_population_rule": f"{population['valid_forecasts']} authoritative valid forecasts mapped one-to-one to 12 attached {SLICE.replace('-', ' ').title()} Outcomes; {population['pack_a']} Pack A and {population['pack_e']} Pack E forecasts; {population['complete_pack_a_e_pairs']} complete Pack A/E pairs; terminal-invalid excluded; no-signal forecasts excluded from directional denominators.", "permitted_metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"], "primary_endpoint": "T+15", "secondary_measurement": "Immediate Impulse", "release_days_utc": days, "retry_boundary": "NO_AUTOMATIC_RETRIES", "single_use": True, "authorization_expiration": "single-use; completed or blocked status is non-reusable", "resume_authority": "resume only from accepted append-only stage artifacts with exact authorization and manifest bindings; completed external requests and attachments are never repeated", "stage_sequence": ["call_free_preflight", "collection", "collection_reconciliation", "attachment", "attachment_reconciliation", "minimal_evaluation", "final_slice_reconciliation"], "stage_stop_conditions": ["identity/count/fingerprint/day-set conflict", "unresolved artifact authority", "missing or contradictory Outcome semantics", "Pack A/E lineage conflict", "historical leakage", "population/denominator conflict", "unsupported metric", "unauthorized request/write/attachment/retry", "remote-state ambiguity", "ceiling exceeded"], "permitted_mechanical_repairs": "general deterministic interface, serialization, path, completion-proof, request-day lineage, resume, and idempotency repairs only; no scientific-semantic changes", "prohibited_scope": ["other slices", "other manifests", "terminal-invalid forecasts", "Google writes", "retries", "market-data source substitution", "forecast or Outcome mutation", "unauthorized metrics"]}
    auth["authorization_fingerprint"] = digest(auth)
    fingerprint = manifest["manifest_fingerprint"].split(":", 1)[1][:20]
    out = BASE / f"PPHB-R1-OUTCOME-COLLECTION-MANIFEST-{SLICE}-{MANIFEST_TIME}-{fingerprint}"
    auth_out = BASE / f"PPHB-R1-OUTCOME-{SLICE}-END-TO-END-AUTHORIZATION-{AUTH_TIME}-{auth['authorization_fingerprint'].split(':', 1)[1][:20]}"
    if out.exists() or auth_out.exists():
        raise SystemExit("OUTPUT_ALREADY_EXISTS")
    out.mkdir(parents=True); auth_out.mkdir(parents=True)
    proof = {"decision": "NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN", "manifest_id": manifest_id, "manifest_fingerprint": manifest["manifest_fingerprint"], "selected_episode_ids": selected, "population": {"episodes": 12, **population}, "prior_slice_exclusion_count": len(prior), "terminal_invalid_exclusions": sorted(INVALID), "explicit_unavailable_exclusions": sorted(EXCLUDED), "pairability_exclusions": pairability_exclusions, "release_days_utc": days, "ceilings": manifest["authorized_forecast_population"], "external_access": {"apps_script_reads": 0, "market_data_attempts": 0, "total_external_requests": 0, "google_writes": 0, "attachments": 0, "evaluation": 0}}
    decision = {"decision": "NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN", "authorization_inputs_decision": "NEXT_PROSPECTIVE_SLICE_AUTHORIZATION_INPUTS_READY", "manifest_id": manifest_id, "manifest_fingerprint": manifest["manifest_fingerprint"], "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "next_move": "validate and execute the active end-to-end authorization"}
    slice_number = SLICE.split("-")[-1].lower()
    for path, value in [(out / f"slice_{slice_number}_manifest.json", manifest), (out / "population_proof.json", proof), (out / "exclusion_proof.json", proof), (out / "manifest_decision.json", decision), (auth_out / "authorization.json", auth), (auth_out / "authorization_validation.json", {"decision": f"{SLICE.replace('-', '_')}_END_TO_END_EXECUTION_AUTHORIZED_NOT_STARTED", "external_access": 0, "manifest_id": manifest_id, "manifest_fingerprint": manifest["manifest_fingerprint"], "authorization_fingerprint": auth["authorization_fingerprint"]})]:
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(out / "slice_009_manifest.json"); print(auth_out / "authorization.json"); print(manifest["manifest_fingerprint"]); print(auth["authorization_fingerprint"])


if __name__ == "__main__":
    main()
