#!/usr/bin/env python3
"""Fail closed when the frozen Round 2 forecast calls lack canonical Pack inputs.

This is a local authority reconciliation.  It deliberately does not attempt to
reconstruct Attention, information-request, or shared-market-state evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PREP_DIR = BASE / "PPHB-R2-T-MINUS-15-FIRST-SLICE-20260804T013000Z"
ORIGINAL_BLOCKER = BASE / "PPHB-R2-FIRST-ROLLING-SLICE-001-DISPATCH-EXECUTION-20260804T020000Z" / "dispatch_governance_blocker.json"
OUTPUT_DIR = BASE / "PPHB-R2-FIRST-ROLLING-SLICE-001-PACK-INPUT-RECONCILIATION-20260804T023000Z"

SLICE_ID = "PPHB-R2-FIRST-ROLLING-SLICE-001-20260804T013000Z"
MANIFEST_FINGERPRINT = "sha256:4eba0d76f06bc29b3c6360acf1c0d18153c2a0d59ae40e02df995b1aa636342e"
ORIGINAL_AUTHORIZATION_ID = "PPHB-R2-FIRST-ROLLING-SLICE-DISPATCH-AUTHORIZATION-20260804T013000Z"


class PackInputAuthorityBlocked(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def validate_missing_lineage() -> dict[str, Any]:
    manifest = read_json(PREP_DIR / "first_slice_manifest.json")
    calls = read_json(PREP_DIR / "forecast_call_inventory.json")["calls"]
    original_blocker = read_json(ORIGINAL_BLOCKER)
    if manifest.get("manifest_fingerprint") != MANIFEST_FINGERPRINT:
        raise PackInputAuthorityBlocked("MANIFEST_FINGERPRINT_CONFLICT")
    if manifest.get("slice_id") != SLICE_ID or len(manifest.get("episodes", [])) != 31:
        raise PackInputAuthorityBlocked("SLICE_POPULATION_CONFLICT")
    if len(calls) != 186 or {call.get("pack") for call in calls} != {"A", "E"}:
        raise PackInputAuthorityBlocked("CALL_INVENTORY_CONFLICT")
    if original_blocker.get("authorization", {}).get("id") != ORIGINAL_AUTHORIZATION_ID:
        raise PackInputAuthorityBlocked("ORIGINAL_AUTHORIZATION_CONFLICT")
    if original_blocker.get("actuals", {}).get("provider_calls") != 0:
        raise PackInputAuthorityBlocked("ORIGINAL_AUTHORIZATION_ACTIVITY_CONFLICT")

    required = {
        "A": ("provider_attention_map", "information_requests"),
        "E": ("provider_attention_map", "information_requests", "shared_market_state_pack", "pack_fingerprint"),
    }
    missing_by_pack: dict[str, list[str]] = {"A": [], "E": []}
    artifact_fields = ("pack_input_payload", "pack_input_artifact", "pack_input_path")
    for call in calls:
        if not any(field in call for field in artifact_fields):
            missing_by_pack[call["pack"]].append(call["call_id"])
    if any(len(ids) != 93 for ids in missing_by_pack.values()):
        raise PackInputAuthorityBlocked("PACK_INPUT_MISSING_PARTITION_CONFLICT")

    return {
        "manifest": manifest,
        "calls": calls,
        "required_fields": required,
        "missing_by_pack": {pack: sorted(ids) for pack, ids in missing_by_pack.items()},
    }


def reconcile(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise PackInputAuthorityBlocked("RECONCILIATION_EVIDENCE_ALREADY_EXISTS")
    validation = validate_missing_lineage()
    evidence = {
        "reconciliation_id": output_dir.name,
        "slice_id": SLICE_ID,
        "decision": "ROUND_2_FIRST_SLICE_FORECAST_EXECUTION_GOVERNANCE_BLOCKED",
        "decisions": {
            "canonical_pack_construction": "ROUND_2_CANONICAL_PACK_CONSTRUCTION_CONFIRMED",
            "pack_inputs": "ROUND_2_FIRST_SLICE_PACK_INPUTS_BLOCKED",
            "replacement_dispatch_authorization": "ROUND_2_FIRST_SLICE_REPLACEMENT_DISPATCH_AUTHORIZATION_BLOCKED",
            "forecast_execution": "ROUND_2_FIRST_SLICE_FORECAST_EXECUTION_GOVERNANCE_BLOCKED",
        },
        "canonical_construction": {
            "pack_a": {
                "version": "presignal_v21_minimal_prospective_lineage_v1",
                "route": "build_prospective_attention -> build_prospective_requests -> build_episode_inputs",
                "required_pre_cutoff_fields": validation["required_fields"]["A"],
            },
            "pack_e": {
                "version": "presignal_v21_minimal_prospective_lineage_v1",
                "route": "build_prospective_attention -> build_prospective_requests -> build_prospective_packs -> build_episode_inputs",
                "required_pre_cutoff_fields": validation["required_fields"]["E"],
            },
            "canonical_builder_sources": [
                "automation/presignal_v21_minimal_prospective_lineage_v1.py",
                "automation/build_presignal_v21_event_path_inputs.py",
                "automation/run_presignal_v21_single_event_path_pair_v1_1.py",
            ],
        },
        "binding": {
            "manifest_fingerprint": MANIFEST_FINGERPRINT,
            "original_authorization_id": ORIGINAL_AUTHORIZATION_ID,
            "original_authorization_status": "BLOCKED_NON_REUSABLE",
        },
        "population": {"episodes": 31, "calls": 186, "pack_a_calls": 93, "pack_e_calls": 93},
        "materialization": {
            "pack_a_input_artifacts": 0,
            "pack_e_input_artifacts": 0,
            "pack_a_missing_call_ids": validation["missing_by_pack"]["A"],
            "pack_e_missing_call_ids": validation["missing_by_pack"]["E"],
            "reason": "The frozen inventory retains only placeholder fingerprints. It has no immutable provider-visible inputs, and the Event snapshot cannot supply Attention, information-request, or timestamped shared-market-state lineage.",
        },
        "authority_boundary": {
            "prohibited_action": "Do not synthesize the missing canonical inputs or substitute post-cutoff evidence.",
            "missing_authority": "A separate pre-cutoff Attention, information-request, and shared-market-state acquisition/materialization authorization is required before a new prospective Slice can be dispatched.",
            "replacement_authorization_created": False,
            "cutoff_recheck_performed": False,
        },
        "actuals": {
            "provider_calls": 0,
            "google_writes": 0,
            "market_data_calls": 0,
            "outcome_activity": 0,
            "evaluation_activity": 0,
            "retries": 0,
            "lease_acquired": False,
            "reservations_created": 0,
        },
        "identity_partition": {
            "GOVERNANCE_BLOCKED_PACK_INPUT_AUTHORITY": sorted(call["call_id"] for call in validation["calls"]),
            "AUTHORITATIVE_VALID_FORECAST": [],
            "TERMINAL_INVALID_DISPATCHED_CALL": [],
            "CUTOFF_PASSED_NOT_AUTHORIZED": [],
            "REMOTE_STATE_UNKNOWN": [],
            "DUPLICATE_OR_UNRESOLVED": [],
        },
        "recorded_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    evidence["fingerprint"] = fingerprint({key: value for key, value in evidence.items() if key not in {"recorded_utc", "fingerprint"}})
    output_dir.mkdir(parents=True)
    (output_dir / "pack_input_authority_reconciliation.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
