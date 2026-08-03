#!/usr/bin/env python3
"""Create one inactive-to-active Slice 003 end-to-end authorization package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
MANIFEST_DIR = BASE / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-003-20260803T154000Z-c15ec51effbb6ac5d26a"
AUTHORIZATION_ID = "PPHB-R1-OUTCOME-SLICE-003-END-TO-END-AUTHORIZATION-20260803T160000Z"
SCHEMA = "AUTHORIZED_SLICE_END_TO_END_AUTH_V1"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def auth_fingerprint(value: dict[str, Any]) -> str:
    body = {key: value[key] for key in value if key != "authorization_fingerprint"}
    return "sha256:" + hashlib.sha256(canonical(body).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build_authorization(controller_commit: str) -> dict[str, Any]:
    manifest = json.loads((MANIFEST_DIR / "slice_003_manifest.json").read_text())
    proof = json.loads((MANIFEST_DIR / "population_proof.json").read_text())
    population = manifest["authorized_forecast_population"]
    identities = [row["episode_id"] for row in manifest["episode_manifest"]]
    collection_ids = [row["outcome_collection_identity"]["duplicate_prevention_identity"] for row in manifest["episode_manifest"]]
    auth = {
        "authorization_id": AUTHORIZATION_ID,
        "authorization_schema_version": SCHEMA,
        "authorization_status": "ACTIVE",
        "authorization_mode": "END_TO_END",
        "slice_id": manifest["slice_id"],
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_fingerprint"],
        "manifest_fingerprint": manifest["manifest_fingerprint"],
        "controller_version": "AUTHORIZED_SLICE_CONTROLLER_V1_END_TO_END",
        "controller_commit": controller_commit,
        "contract_binding": "PPHB-R1-PROSPECTIVE-SLICE-EXECUTION-CONTRACT-20260803T060000Z",
        "authorized_stage": "end_to_end",
        "authorized_identity_ids": identities,
        "outcome_collection_identity_ids": collection_ids,
        "authorized_attachment_identity_ids": collection_ids,
        "ceilings": {"max_apps_script_reads": 3, "max_market_data_attempts": 12, "max_total_external_requests": 15, "google_write_ceiling": 0, "max_attachment_records": len(identities), "max_evaluation_artifacts": 1},
        "attachment_write_ceiling": {"google_writes": 0, "local_append_only_records": len(identities)},
        "retry_boundary": "NO_AUTOMATIC_RETRIES",
        "contract": manifest["forecast_contract"],
        "schema_version": manifest["outcome_schema_version"],
        "destination": manifest["collection_destination"],
        "attachment_destination": "append-only local Outcome attachment evidence",
        "evaluation_output_destination": "append-only local minimal evaluation evidence",
        "required_collection_artifact": {"stage": "collection", "required_files": ["collection_reconciliation.json", "candidate_outcomes.jsonl"], "manifest_sha256": manifest["manifest_fingerprint"]},
        "evaluation_population_rule": f"{population['valid_forecasts']} authoritative valid forecasts mapped one-to-one to {len(identities)} attached Slice 003 Outcomes; terminal-invalid excluded; Pack A/E remain distinct",
        "evaluation_population": population,
        "permitted_metrics": ["T+15 directional accuracy", "Immediate Impulse directional accuracy", "magnitude or pip error", "horizon accuracy", "path accuracy", "reversal accuracy"],
        "stage_sequence": ["call_free_preflight", "collection", "collection_reconciliation", "attachment", "attachment_reconciliation", "minimal_evaluation", "final_slice_reconciliation"],
        "stage_stop_conditions": ["partial or ambiguous stage artifact", "identity, count, fingerprint, or schema conflict", "duplicate Outcome or attachment", "remote-state ambiguity", "ceiling exceeded", "historical leakage", "unsupported metric", "provider/source authority conflict"],
        "resume_authority": "resume only from accepted append-only completion artifact with exact Slice 003 manifest and authorization fingerprints; otherwise new explicit authorization required",
        "single_use": True,
        "expiration": "single Slice 003 execution route; deterministic timestamp is artifact naming metadata, not a future-effective validity boundary",
        "source_authority": manifest["source_authority"],
        "apps_script_route": "apiFetchGovernedHistoricalUsdJpyObservation",
        "instrument": manifest["instrument"],
        "timestamp_rules": "frozen release_ts and one-minute observations normalized to UTC",
        "measurement_windows_min": manifest["measurement_windows_min"],
        "primary_endpoint": manifest["primary_endpoint"],
        "secondary_measurement": manifest["secondary_measurement"],
        "missing_data_behavior": "preserve unavailable observations explicitly; do not infer, interpolate, repair, or substitute",
        "market_closure_behavior": "preserve contract-defined unavailable status; stop if authority is unresolved",
        "exclusion_proof": {"prior_slice_episodes": proof["prior_slice_exclusions"], "terminal_invalid_calls": proof["terminal_invalid_exclusions"], "pairability_conflicts": proof["pairability_exclusions"]},
        "permitted_mechanical_repairs": "general deterministic stage-interface repairs only; preserve semantic values, hashes, ceilings, and canonical stages",
        "live_stop_state_before_execution": "SLICE_003_END_TO_END_EXECUTION_AUTHORIZED_NOT_STARTED",
    }
    auth["authorization_fingerprint"] = auth_fingerprint(auth)
    return auth


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--controller-commit", required=True)
    args = parser.parse_args()
    auth = build_authorization(args.controller_commit)
    suffix = auth["authorization_fingerprint"].split(":", 1)[1][:20]
    output = BASE / f"PPHB-R1-OUTCOME-SLICE-003-END-TO-END-AUTHORIZATION-20260803T160000Z-{suffix}"
    if output.exists():
        raise SystemExit("OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    write(output / "authorization.json", auth)
    write(output / "timestamp_preflight.json", {"authorization_id": auth["authorization_id"], "classification": "DETERMINISTIC_ARTIFACT_NAMING_METADATA", "validity_boundary": "not an issuance or future-effective time", "decision": "TIMESTAMP_AUTHORITY_CONFIRMED", "external_access": 0})
    write(output / "authorization_decision.json", {"decision": "SLICE_003_END_TO_END_AUTHORIZATION_FROZEN", "readiness": "SLICE_003_END_TO_END_EXECUTION_READY", "live_state": auth["live_stop_state_before_execution"], "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "manifest_id": auth["manifest_id"], "manifest_fingerprint": auth["manifest_fingerprint"], "external_access": 0})
    write(output / "run_manifest.json", {"run_id": output.name, "move": "FREEZE_SLICE_003_END_TO_END_AUTHORIZATION", "authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"], "manifest_id": auth["manifest_id"], "manifest_fingerprint": auth["manifest_fingerprint"], "controller_commit": args.controller_commit, "provider_calls": 0, "google_reads": 0, "market_data_calls": 0, "google_writes": 0, "attachment": 0, "evaluation": 0, "append_only": True})
    print(output)
    print(auth["authorization_id"])
    print(auth["authorization_fingerprint"])


if __name__ == "__main__":
    main()
